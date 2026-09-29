"""Actual packaged artifacts: provenance preservation, expiry and private rollback."""
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path

from lifecycle import ROOT, configure, save


def run():
    configure()
    from app.models.ingredient import NormalizedIngredient
    from app.models.product import Product
    from app.services.basket_calculator import BasketCalculator
    from app.services.basket_auditor import BasketAuditor
    from app.services.product_matcher import ProductMatcher
    from app.services.user_pricing import price_candidate_for_context
    from grocery_data.app.domain.promotion_pricing import UserPricingContext
    from grocery_data.app.services.coop_offer_job import source_plan
    from grocery_data.app.services.freshness import FreshnessPolicy
    from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path
    from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore, validate_backend_prepared_universe_artifact

    records = {mode: json.loads((ROOT/(mode+'.json')).read_bytes()) for mode in
        ['cycle-a','cycle-b','cycle-base','cycle-c','cycle-fetch-failure','cycle-recovery','cycle-xtra','cycle-xtra-off','cycle-reload-failure','cycle-withdrawal','cycle-final-recovery','cycle-final-plan','cycle-expiry']}
    for mode, record in records.items():
        assert record['exit_code'] == (2 if mode == 'cycle-reload-failure' else 0), mode
        assert record['health'] == record['ready'] == 200, mode
    def prices(record):
        return {p['product_id']: {k:p.get(k) for k in ['product_id','store_id','name','price','ordinary_price','package_quantity','package_unit','offers','source_provenance']}
                for p in record['coop_rows']}
    first = prices(records['cycle-a'])
    assert first == prices(records['cycle-b']) == prices(records['cycle-base'])
    assert len(first) == 493  # This observed run, never a runtime inventory limit.
    assert records['cycle-base']['universe_id'] != records['cycle-b']['universe_id']
    assert records['cycle-final-plan']['planning']['saved_equals_readback']
    assert all(records['cycle-final-plan']['planning']['audits'])
    request=json.loads(Path('/evaluation/request.json').read_bytes())
    plan=records['cycle-final-plan']['planning']['plan']
    assert len(plan['personal']['slots']) == sum(m['count'] for m in request['personal']['meals']) == 15
    assert plan['portions'] == sum(m['count']*m['servings'] for m in request['personal']['meals']) == 20
    assert plan['optimized_basket']['store_count'] <= request['max_stores'] == 2
    targets={m['meal_type']:m['limits']['min_protein_g'] for m in request['personal']['meals']}
    for row in plan['personal']['checks']['nutrition']:
        meal=next(s['meal_type'] for s in plan['personal']['slots'] if s['id']==row['slot_id'])
        assert row['values']['protein_g'] >= targets[meal]
    assert prices(records['cycle-c']) == first
    assert prices(records['cycle-fetch-failure']) == first
    recovered = prices(records['cycle-recovery'])
    assert len(recovered) == len(first)
    extended = records['cycle-xtra']['coop_rows']
    xtra = [p for p in extended if p['source_provenance']['provider_store_id'] == '3658']
    assert xtra and len(extended) == len(recovered)+len(xtra)
    assert prices(records['cycle-xtra-off']) == recovered
    assert records['cycle-reload-failure']['exit_code'] == 2
    assert records['cycle-expiry']['coop_products'] == 0
    withdrawn = prices(records['cycle-withdrawal'])
    assert len(withdrawn) < len(recovered) and withdrawn.keys() <= recovered.keys()
    assert len(prices(records['cycle-final-recovery'])) == len(recovered)
    assert prices(records['cycle-final-plan']) == prices(records['cycle-final-recovery'])
    result = {'at':datetime.now(UTC).isoformat(), 'source_identity_price_terms_provenance_equal_A_B_base':True,
        'real_base_source_changed':True, 'restart_preserved':True, 'fetch_failure_preserved_valid_sources':True,
        'recovered_rows':len(recovered), 'xtra_rows_when_enabled':len(xtra), 'xtra_disabled_coop_unchanged':True,
        'expired_provider_products':0, 'confirmed_empty_remaining_rows':len(withdrawn), 'final_recovered_rows':records['cycle-final-plan']['coop_products'],
        'final_plan_cost':records['cycle-final-plan']['planning']['cost'], 'expiry_checks':[], 'private_publication':{}, 'next_update':source_plan()}
    context=UserPricingContext()
    for data in records['cycle-final-recovery']['coop_rows']:
        p=Product.model_validate(data)
        if p.name != 'Kärnvetemjöl':continue
        need=NormalizedIngredient(canonical_name='vetemjöl',required_quantity=4000,unit='g')
        candidates=ProductMatcher().match(need,[p])
        if not candidates:continue
        candidate=price_candidate_for_context(candidates[0],context)
        item=BasketCalculator().calculate_item(need,candidate)
        assert item.total_price==26 and item.packages_needed==2
        assert BasketAuditor(pantry_items=frozenset()).audit([need],[item],user_pricing_context=context).passed
        expired_on=max(o.valid_to for o in p.offers if o.valid_to)+timedelta(days=1)
        try:price_candidate_for_context(candidates[0],context,on_date=expired_on)
        except ValueError:pass
        else:raise AssertionError('expired campaign priced')
        result['expiry_checks'].append({'store_id':p.store_id,'product_id':p.product_id,
            'valid_to':expired_on-timedelta(days=1),'test_purchase_date':expired_on,
            'source_observed_at':p.source_provenance.source_observed_at,'group_checkout':item.total_price,
            'expired_rejected':True,'clock':'explicit future purchase date; original source unchanged'})
        break
    assert result['expiry_checks']
    private=ROOT/'final-publication'
    private.mkdir(exist_ok=False)
    required=tuple(os.environ['PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS'].split(','))
    validator=partial(validate_backend_prepared_universe_artifact,required_context_ids=required,max_price_age_hours=48)
    baseline=Path(records['cycle-b']['artifact'])
    candidate=Path(records['cycle-base']['artifact'])
    with RefreshRunLock(production_refresh_lock_path(ROOT/'grocery.sqlite',ROOT/'price-universes')):
        store=PreparedUniverseArtifactStore(private/'pu')
        base=store.activate(baseline,city='Lund',validator=validator,freshness_policy=FreshnessPolicy())
        advanced=store.activate(candidate,city='Lund',validator=validator,freshness_policy=FreshnessPolicy())
        current=store.active_manifest_bytes('Lund')
        invalid=private/'invalid.json';invalid.write_text('{"invalid":"injected test"}')
        try:store.activate(invalid,city='Lund',validator=validator)
        except (ValueError,TypeError):pass
        else:raise AssertionError('invalid artifact published')
        assert store.active_manifest_bytes('Lund')==current
        try:store.activate(baseline,city='Lund',validator=validator,freshness_policy=FreshnessPolicy(),activated_at=datetime.now(UTC)+timedelta(hours=48))
        except ValueError:pass
        else:raise AssertionError('stale rollback admitted')
        assert store.active_manifest_bytes('Lund')==current
        restored=store.activate(baseline,city='Lund',validator=validator,freshness_policy=FreshnessPolicy())
        assert restored.universe_id==base.universe_id
        assert PreparedUniverseArtifactStore(private/'pu').read_active('Lund').universe_id==base.universe_id
        meta=validator(json.loads(baseline.read_bytes()),'Lund')
        oldest=meta.oldest_base_observed_at or meta.oldest_observed_at
        result['private_publication']={'candidate':advanced.universe_id,'rollback':restored.universe_id,
            'rollback_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),
            'oldest_base_observed_at':oldest,'rollback_valid_until':oldest+timedelta(hours=48),
            'invalid_candidate_rejected':True,'stale_rollback_rejected':True,'restart_readback':True}
    save('final-checks',result)
    print(json.dumps({k:v for k,v in result.items() if k!='next_update'},default=str))
