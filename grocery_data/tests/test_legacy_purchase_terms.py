"""Real retained source facts and adversarial changes at legacy adapter gates."""
import gzip
import json
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop.parser import CoopParser
from grocery_data.app.connectors.hemkop.physical_offers import parse as hemkop_parse
from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import RawBatch, SourceStore
from grocery_data.app.domain.purchase_terms import PurchaseTerms
from grocery_data.app.services.offer_rows import qualify_rows, row_blockers

FIX=Path(__file__).parent/'fixtures'


def retained(chain):
    name={'ica':'ica-purchase-terms-20260928','coop':'coop-physical-transition-20260928','hemkop':'hemkop-physical-20260928'}[chain]
    fixture=json.loads(gzip.decompress((FIX/(name+'.json.gz')).read_bytes()))
    store=SourceStore.model_validate(fixture['store'])
    raw=RawBatch.model_validate(fixture['editions']['2026-09-28'] if chain=='coop' else fixture['batch'])
    if chain=='hemkop':
        store=store.model_copy(update={'source_fields':{**store.source_fields,'official_store_url':'https://www.hemkop.se/butik/'+store.external_id,
            'offer_policy':'hemkop-physical-singleton-offers-v1'}})
    parse={'ica':IcaParser().parse_catalog,'coop':CoopParser().parse_catalog,'hemkop':hemkop_parse}[chain]
    parsed=parse(raw,[f'raw:retained-{i}' for i in range(len(raw.documents))],store)
    return qualify_rows(parsed,store=store,observed_at=max(d.fetched_at for d in raw.documents))[0],store,raw


@pytest.mark.parametrize('chain',['ica','coop','hemkop'])
def test_actual_terms_survive_source_contract_and_observation_roundtrip(chain):
    parsed,_,raw=retained(chain)
    assert parsed.products
    for p in parsed.products:
        assert p.fetched_at in {d.fetched_at for d in raw.documents}
        assert p.regular_price is None
        terms=p.offers[0].source_payload.get('purchase_terms')
        if terms:
            assert PurchaseTerms.model_validate(terms).usage!='blocked'
            assert terms==p.source_fields['purchase_terms']
            assert not row_blockers(type(p).model_validate_json(p.model_dump_json()))
            stripped = p.model_copy(update={'source_fields': {k: v for k, v in p.source_fields.items() if k != 'purchase_terms'}})
            assert 'purchase_terms_source_mismatch' in row_blockers(stripped)
            changed=p.offers[0].model_copy(update={'source_payload':{**p.offers[0].source_payload,'purchase_terms':{**terms,'source_reference':'wrong'}}})
            assert 'purchase_terms_source_mismatch' in row_blockers(p.model_copy(update={'offers':(changed,)}))


def test_ica_real_whole_approximate_and_loose_weight_are_different():
    parsed,_,_=retained('ica')
    salmon=next(p for p in parsed.products if p.external_product_id=='5004138143')
    terms=PurchaseTerms.model_validate(salmon.source_fields['purchase_terms'])
    assert terms.purchase_form=='variable_package' and terms.approximate_package_g==1200
    assert salmon.offers[0].price==139 and salmon.offers[0].source_payload['price_basis_unit']=='kg'
    assert str(salmon.average_weight_kg)=='1.2' and salmon.basket_type=='ST'
    apples=next(p for p in parsed.products if p.external_product_id=='5004121679')
    terms=PurchaseTerms.model_validate(apples.source_fields['purchase_terms'])
    assert apples.name=='Äpplen Royal Gala'
    assert terms.purchase_form=='loose_weight' and terms.quantity_basis=='requirement'
    assert terms.usage=='estimated' and terms.approximate_package_g is None
    assert apples.offers[0].price==20 and apples.offers[0].source_payload['price_basis_unit']=='kg'
    assert apples.package_quantity is None  # No invented apple or bag weight.



def test_coop_real_group_has_only_explicit_source_ids_and_retains_other_purchase_block():
    parsed,_,_=retained('coop')
    mixed=[p for p in parsed.products if p.offers[0].quantity and p.offers[0].quantity>1]
    assert mixed and all(p.regular_price is None for p in mixed)
    for p in mixed:
        assert p.offers[0].quantity==p.source_fields['purchase_terms']['complete_group_size']
        # Välj mellan and common cluster membership alone do not prove mixing.
        assert not p.source_fields['purchase_terms'].get('mixing_allowed')
    assert any('additional_purchase_rules_requires_review' in f.error_message for f in parsed.failures)
    assert any('tiered_price_steps_requires_review' in f.error_message for f in parsed.failures)


def test_hemkop_membership_cap_and_open_variant_identity_are_separate():
    parsed,_,_=retained('hemkop')
    beef=next(p for p in parsed.products if p.external_product_id=='2500324385:101428349_ST')
    assert beef.offers[0].member_only and beef.offers[0].max_quantity==2
    assert beef.offers[0].price==119 and beef.package_quantity==800
    pizza=next(p for p in parsed.products if p.external_product_id=='2500317459:group')
    assert pizza.offers[0].price==79 and pizza.offers[0].quantity==2
    assert pizza.source_fields['purchase_terms']['variant_selection']=='required'
    assert pizza.gtin is None and pizza.source_fields['source_variant_id'] is None and pizza.package_quantity is None


@pytest.mark.parametrize('condition',[
    {'threshold':200},{'conditionLabel':'Handla andra varor för 200 kr'},
    {'description':'Endast fredag'}, {'description':'Pant tillkommer'},
    {'textLabelGenerated':'Köp 2 betala för 1'}, {'discountPrice':15},
    {'redeemLimit':2,'promotionRedeemLimit':3,'redeemLimitLabel':'Max 2 köp'},
])
def test_hemkop_unsupported_conditions_never_become_ordinary_discounts(condition):
    from grocery_data.tests.test_hemkop_physical_offers import source
    doc,store=source(); payload=doc.json_payload()
    payload['results'][0]['potentialPromotions'][0].update(condition)
    parsed=hemkop_parse(RawBatch(chain='hemkop',documents=(doc.model_copy(update={'payload':json.dumps(payload).encode()}),)),['raw:mutation'],store)
    assert not parsed.products and parsed.failures


def test_explicit_loose_source_statement_required_not_inferred_from_absent_pack():
    _, store, raw = retained('ica')
    documents = []
    def mark(value):
        if isinstance(value, dict):
            if str(value.get('id')) == '5004121679':
                value['details']['customerInformation'] += '. Lösvikt.'
            for child in value.values():
                mark(child)
        elif isinstance(value, list):
            for child in value:
                mark(child)
    for doc in raw.documents:
        payload = doc.json_payload()
        mark(payload)  # Synthetic explicit statement; not claimed as real apple evidence.
        documents.append(doc.model_copy(update={'payload': json.dumps(payload).encode()}))
    batch = raw.model_copy(update={'documents': tuple(documents)})
    parsed = IcaParser().parse_catalog(batch, ['raw:loose-test'] * len(documents), store)
    apples = next(p for p in parsed.products if p.external_product_id == '5004121679')
    assert apples.source_fields['purchase_terms']['purchase_form'] == 'loose_weight'
    assert not row_blockers(apples)


def test_explicit_mixing_statement_binds_only_identified_source_children():
    existing, store, raw = retained('coop')
    eligible_groups = {p.source_fields['source_group_id'] for p in existing.products if (p.offers[0].quantity or 1) > 1}
    payload = raw.documents[0].json_payload()
    groups = payload['structured_offers']['data']['sortingGroups']
    parent = next(p for g in groups for p in g['offers']
                  if p['id'] in eligible_groups and len(p.get('clusterInteriorOffers', [])) > 1
                  and p['priceInformation'].get('quantity', 0) > 1
                  and p['priceInformation'].get('unit') == 'st')
    for group in groups:
        for row in group['offers']:
            if row['id'] == parent['id']:
                row['content']['description'] += ' Välj och blanda.'  # Synthetic control only.
    batch = raw.model_copy(update={'documents': (raw.documents[0].model_copy(
        update={'payload': json.dumps(payload).encode()}),)})
    parsed = CoopParser().parse_catalog(batch, ['raw:mixing-test'], store)
    approved, _ = qualify_rows(parsed, store=store, observed_at=batch.documents[0].fetched_at)
    children = [p for p in approved.products if p.source_fields['source_group_id'] == parent['id']]
    assert len(children) > 1
    eligible = {f"{v['id']}:{v['externalId']}" for v in parent['clusterInteriorOffers']}
    for p in children:
        terms = PurchaseTerms.model_validate(p.source_fields['purchase_terms'])
        assert terms.mixing_allowed and set(terms.eligible_variant_ids) == eligible
        assert p.external_product_id in eligible
