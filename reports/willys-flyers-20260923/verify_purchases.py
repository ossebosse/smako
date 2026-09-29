"""Real published flyer rows, existing matcher, checkout and audit, no network."""
import argparse
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from app.models.ingredient import NormalizedIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.personal_planner import PersonalPlanner
from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from grocery_data.app.services.campaign_refresh_policy import STOCKHOLM
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore


def run(root,city):
    from datetime import datetime
    purchase_day=datetime.now(STOCKHOLM).date()
    path=PreparedUniverseArtifactStore(root/'price-universes').resolve_active_artifact(city,verify_hash=True)
    prepared=PreparedPriceUniverseArtifact.model_validate_json(path.read_bytes()).restore()
    products=[p for p in prepared.universe.products if p.chain=='willys' and p.source_provenance.source_channel=='offers']
    context=UserPricingContext.from_chain_flags({'willys':True})
    facts=load_retained_facts(prepared,database=root/'grocery.sqlite',raw_root=root/'raw')
    # No declarations can be joined by name alone: these document ad identities
    # carry neither GTIN nor the retailer SKU required by existing fact registries.
    rows=[]; bread=[]
    for p in products:
        if p.name not in {'Pågenlimpan','Kycklingbröstfilé Sverige','Pizzadeg'}: continue
        quantity=p.offers[0].required_packages
        need=NormalizedIngredient(canonical_name=('chicken_breast' if p.name=='Kycklingbröstfilé Sverige' else p.name.casefold()),required_quantity=p.package_quantity*quantity,unit=p.package_unit)
        matches=ProductMatcher().match(need,[p]);assert len(matches)==1,(p.name,len(matches))
        candidate=price_candidate_for_context(matches[0],context,on_date=purchase_day)
        item=BasketCalculator().calculate_item(need,candidate)
        audit=BasketAuditor(pantry_items=frozenset()).audit([need],[item],user_pricing_context=context)
        assert audit.passed,(p.name,audit)
        assert p.price is None and p.gtin is None
        try:price_candidate_for_context(matches[0],UserPricingContext(),on_date=purchase_day)
        except ValueError:pass
        else:raise AssertionError('member-only contract leaked')
        retained=facts.get((p.store_id,p.product_id))
        assert retained is None
        planner=SimpleNamespace(spec=SimpleNamespace(allow_nutrition_estimates=False),source_facts=lambda _:retained)
        nutrition=PersonalPlanner._nutrition_evidence(planner,p,p.name.casefold(),p.package_unit,{'kcal','protein_g'},None)
        assert nutrition is None
        rows.append({'store_id':p.source_provenance.provider_store_id,'name':p.name,
            'checkout':item.model_dump(mode='json'),'audit_passed':True,'nonmember':'blocked_unknown_ordinary',
            'nutrition_status':'no_exact_identity_to_approved_declaration','source':p.source_provenance.model_dump(mode='json')})
        if p.name=='Pågenlimpan':bread.append(item)
    assert len(rows)==3*len({p.store_id for p in products})
    chosen=(bread*3)[:3]
    assert round(sum(i.total_price for i in BasketCalculator.quote_group_basket(chosen)),2)==74.7
    try:BasketCalculator.quote_group_basket([*chosen,bread[-1]])
    except GroupPricingError:pass
    else:raise AssertionError('household allowance multiplied')
    report={'kind':'published_source_checkout_replay','purchase_date':purchase_day.isoformat(),'network_requests':0,
        'physical_stores':len(bread),'audits':len(rows),'rows':rows,
        'household_limit':'fourth_Pagenlimpan_package_across_recipes_and_available_stores_blocked',
        'artifact':str(path),'universe_id':prepared.universe.universe_id}
    (root/'purchases.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'city':city,'stores':len(bread),'audits':len(rows)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--city',required=True)
    a=p.parse_args();run(a.root,a.city)
