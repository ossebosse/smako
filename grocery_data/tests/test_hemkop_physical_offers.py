import json
from datetime import UTC, datetime

import pytest

from grocery_data.app.connectors.hemkop.physical_offers import PARSER, POLICY, URL, page_rows, parse
from grocery_data.app.domain import RawBatch, RawFetch, SourceStore
from grocery_data.app.services.offer_rows import qualify_rows


def source():
    promotion = {'code': 'fixture-campaign', 'mainProductCode': 'fixture-product_ST',
        'productCodes': ['fixture-product_ST'], 'qualifyingCount': 1, 'realMixAndMatch': False,
        'promotionType': 'MixMatchPricePromotion', 'campaignType': 'GENERAL', 'price': 20,
        'startDate': '28/09-2026', 'endDate': '04/10-2026', 'weightVolume': '500g',
        'validUntil': int(datetime(2026,10,4,21,59,59,tzinfo=UTC).timestamp()*1000)}
    row = {'name': 'Fixture pasta', 'manufacturer': 'Fixture', 'displayVolume': '500g',
        'priceUnit': 'kr/st', 'potentialPromotions': [promotion]}
    payload = {'results': [row], 'pagination': {'currentPage': 0, 'pageSize': 30,
        'numberOfPages': 1, 'totalNumberOfResults': 1}}
    document = RawFetch(chain='hemkop', store_external_id='fixture-store', method='GET',
        kind='physical_offers', url=URL, query={'q':'fixture-store','size':'30','page':'0'},
        page_number=0, http_status=200, content_type='application/json',
        fetched_at=datetime(2026,9,28,9,tzinfo=UTC), connector_version='hemkop-v1',
        payload=json.dumps(payload).encode())
    store = SourceStore(chain='hemkop', external_id='fixture-store', name='Fixture',
        city='Dalby', address='Fixture 1', postal_code='24750', coverage='offers_only', raw_reference='fixture-register',
        price_context_type='physical_store', source_fields={'offer_policy': POLICY,
            'official_store_url':'https://www.hemkop.se/butik/fixture-store'})
    return document, store


def test_singleton_physical_campaign_preserves_channel_package_dates_and_observation():
    doc, store = source()
    parsed = parse(RawBatch(chain='hemkop', documents=(doc,)), ['fixture-source'], store)
    approved, evidence = qualify_rows(parsed, store=store, observed_at=doc.fetched_at)
    assert not evidence['shared_blockers'] and len(approved.products) == 1
    p = approved.products[0]
    assert p.gtin is None and p.sale_price is None and p.regular_price is None
    assert p.source_fields['source_variant_id'] == 'fixture-product_ST'
    assert p.package_quantity == 500 and p.offers[0].price == 20
    assert p.offers[0].source_payload['campaign_evidence']['observed_current_at'] == doc.fetched_at.isoformat().replace('+00:00','Z')


@pytest.mark.parametrize('change', [{'query':{'q':'wrong','size':'30'}}, {'store_external_id':'wrong'},
    {'url':'https://www.hemkop.se/search/campaigns/online'}, {'http_status':403}, {'chain':'willys'}])
def test_wrong_store_or_source_is_a_shared_failure(change):
    doc, store = source()
    with pytest.raises(ValueError): page_rows(doc.model_copy(update=change), store.external_id)


@pytest.mark.parametrize('change', [{'productCodes':None}, {'productCodes':['one','two']},
    {'realMixAndMatch':True}, {'qualifyingCount':2}, {'campaignType':'PERSONAL_SEGMENTED'},
    {'conditionLabel':'Handla andra varor för 200 kr'}, {'redeemLimitLabel':'Max 2 köp'},
    {'weightVolume':'600g'}])
def test_unproven_variants_and_unsupported_conditions_stay_quarantined(change):
    doc, store = source(); payload = doc.json_payload()
    payload['results'][0]['potentialPromotions'][0].update(change)
    parsed = parse(RawBatch(chain='hemkop', documents=(doc.model_copy(update={'payload':json.dumps(payload).encode()}),)), ['fixture'], store)
    assert not parsed.products and len(parsed.failures) == 1
    assert parsed.failures[0].parser_version == PARSER


def test_new_business_field_blocks_the_document_not_just_one_row():
    doc, store = source(); payload = doc.json_payload()
    payload['results'][0]['potentialPromotions'][0]['newPurchaseRestriction'] = 'unknown'
    with pytest.raises(ValueError, match='schema changed'):
        page_rows(doc.model_copy(update={'payload':json.dumps(payload).encode()}), store.external_id)


def test_actual_saved_dalby_edition_is_replayed_without_image_identity_or_ordinary_price():
    import gzip
    from pathlib import Path
    fixture = json.loads(gzip.decompress((Path(__file__).parent/'fixtures/hemkop-physical-20260928.json.gz').read_bytes()))
    raw = RawBatch.model_validate(fixture['batch']); store = SourceStore.model_validate(fixture['store'])
    parsed = parse(raw, [f'real-page-{i}' for i in range(len(raw.documents))], store)
    assert len(parsed.products) == 48 and len(parsed.failures) == 25
    assert sum(p.source_fields['purchase_terms']['variant_selection']=='resolved' for p in parsed.products)==22
    for product in parsed.products:
        assert product.gtin is None and product.regular_price is None and product.sale_price is None
        p = product.offers[0].source_payload['hemkop_physical_campaign']
        terms = product.source_fields['purchase_terms']
        if terms['variant_selection']=='resolved':
            assert p['productCodes'] == [product.source_fields['source_variant_id']]
        else:
            assert tuple(p['productCodes']) == tuple(terms['eligible_variant_ids'])
            assert product.source_fields['source_variant_id'] is None and product.package_quantity is None
        assert product.fetched_at in {d.fetched_at for d in raw.documents}


def test_synthetic_new_edition_with_reused_campaign_id_needs_new_approval():
    doc, store = source()
    def qualify(document):
        parsed = parse(RawBatch(chain='hemkop', documents=(document,)), ['fixture-source'], store)
        return qualify_rows(parsed, store=store, observed_at=document.fetched_at)
    old, old_evidence = qualify(doc)
    payload = doc.json_payload()
    promo = payload['results'][0]['potentialPromotions'][0]
    promo.update(price=25,startDate='05/10-2026',endDate='11/10-2026',
        validUntil=int(datetime(2026,10,11,21,59,59,tzinfo=UTC).timestamp()*1000))
    changed = doc.model_copy(update={'payload':json.dumps(payload).encode(),
        'fetched_at':datetime(2026,10,5,9,tzinfo=UTC)})
    new, new_evidence = qualify(changed)
    assert old_evidence['accepted_ids'] == new_evidence['accepted_ids']
    assert old_evidence['evidence_sha256'] != new_evidence['evidence_sha256']
    assert old.products[0].source_fields['source_sha256'] != new.products[0].source_fields['source_sha256']
    assert old.products[0].offers[0].price == 20 and new.products[0].offers[0].price == 25
    assert new.products[0].fetched_at == changed.fetched_at
