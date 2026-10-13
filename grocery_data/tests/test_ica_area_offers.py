"""Synthetic protocol fixtures: no network and no retailer price assertions."""
import json
from datetime import UTC, datetime

import httpx
import pytest

from grocery_data.app.connectors.ica.client import IcaClient
from grocery_data.app.connectors.ica.models import sanitized_initial_data_payload
from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import Chain, GeographicArea, RawBatch, RawFetch, SourceStore
from grocery_data.app.services.ica_area_offers import (
    area_membership,
    coverage_drift,
    inventory_counts,
)


def store(city="Lund", postal="22476"):
    return SourceStore(chain="ica", external_id="1004598", name="Fixture",
                       address="Fixturegatan 1", city=city, postal_code=postal,
                       coverage="offers_only", raw_reference="fixture",
                       source_fields={"store_id": "15172"})


def offer(**updates):
    return {"id": "fixture-offer", "details": {"name": "Mjölk", "packageInformation": "1000 ml"},
            "validFrom": "2026-09-18", "validTo": "2026-09-20", "traits": [],
            "parsedMechanics": {"benefitType": "FIXED", "quantity": 2,
                                "value1": "2 för", "value2": "30"},
            "stores": [{"BMSStoreId": "15172", "storeInd": True}], **updates}


def parse(row):
    raw = RawFetch(chain=Chain.ICA, kind="offers_page", method="GET", url="https://www.ica.se/",
                   http_status=200, content_type="application/json", connector_version="fixture",
                   payload=json.dumps({"offers": {"weeklyOffers": [row]}}).encode(),
                   fetched_at=datetime(2026, 9, 16, tzinfo=UTC))
    return IcaParser().parse_catalog(RawBatch(chain=Chain.ICA, documents=(raw,)), ["fixture"], store())


def test_area_is_verified_address_locality_not_shopper_postcode_or_result_name():
    area = GeographicArea(city="Lund", postal_codes=("22350",))
    assert area_membership(store(), area)[0] == "inside"
    assert area_membership(store("Södra Sandby"), area)[0] == "outside"
    assert area_membership(store().model_copy(update={"address": None}), area)[0] == "unknown"
    assert area_membership(store("Malmö"), GeographicArea(city="Malmö"))[0] == "inside"


@pytest.mark.parametrize("city,slug", [("Lund", "lund"), ("Malmö", "malmo"), ("Uppsala", "uppsala")])
async def test_parameterized_full_locator_follows_observed_pagination(city, slug):
    calls = []
    def response(req):
        calls.append(str(req.url))
        page = len(calls)
        card = {"accountNumber": str(page), "storeName": f"Fixture {page}",
                "address": {"city": city, "street": "Fixture 1"}}
        data = {"resultStore": {"totalNrOfStores": 2, "storeCards": [card]}}
        html = '<script>window.__INITIAL_DATA__ = ' + json.dumps(data) + ';</script>'
        if page == 1:
            html += f'<a rel="next" href="https://www.ica.se/butiker/{slug}/?page=2">Next</a>'
        return httpx.Response(200, content=html.encode())
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        client = IcaClient(client=http, requests_per_second=10000)
        batch = await client.fetch_physical_stores(GeographicArea(city=city))
        stores = IcaParser().parse_physical_stores(batch, ["a", "b"], GeographicArea(city=city),
                                                 include_outside=True)
    assert calls[0] == f"https://www.ica.se/butiker/{slug}/"
    assert len(stores) == 2 and inventory_counts(batch, stores)["complete"]
    assert not inventory_counts(batch, stores[:1])["complete"]


def test_public_projection_preserves_store_page_conditions_and_excludes_runtime():
    data = {"offers": {"weeklyOffers": [offer(restriction="Max 1 köp/hushåll")]},
            "user": {"cookie": "NEVER_RETAIN"}}
    result = sanitized_initial_data_payload(json.dumps(data).encode(), kind="offers_page")
    assert b"NEVER_RETAIN" not in result
    assert json.loads(result)["offers"]["weeklyOffers"][0]["validFrom"] == "2026-09-18"


@pytest.mark.parametrize("traits", [[], ["Stammis"]])
def test_start_end_multibuy_and_cap_survive(traits):
    result = parse(offer(traits=traits, restriction="Max 1 köp/hushåll"))
    assert not result.failures
    product = result.products[0]
    price = product.offers[0]
    assert price.quantity == 2 and price.price == 30 and price.max_quantity == 1
    assert price.member_only == bool(traits)
    assert price.valid_from.isoformat() == "2026-09-18"
    assert product.regular_price is None
    assert product.sale_price is None and product.sale_unit == "st"


@pytest.mark.parametrize("change", [
    {"condition": "Personligt erbjudande"}, {"restriction": "Endast fredag"},
    {"restriction": "Aktivera kupong"}, {"restriction": "+ pant"},
    {"validFrom": "not-a-date"}, {"validFrom": "2026-09-21"},
    {"stores": [{"BMSStoreId": "2786"}]},
    {"stores": [{"BMSStoreId": "15172", "storeInd": False}]},
])
def test_uncertain_or_foreign_conditions_are_quarantined(change):
    result = parse(offer(**change))
    assert not result.products and len(result.failures) == 1


def test_multiple_gtin_variants_are_never_fanned_out():
    result = parse(offer(eans=[{"id": "7300206787006"}, {"id": "7310860007259"}]))
    assert len(result.products) == 1 and result.products[0].gtin is None


def test_inventory_drift_keeps_losses_and_source_changes_visible():
    before = {"stores": [{"ica_account_id": "1", "collection_status": "success", "offers_url": "old"},
                         {"ica_account_id": "2"}]}
    after = {"stores": [{"ica_account_id": "1", "collection_status": "error", "offers_url": "new"},
                        {"ica_account_id": "3"}]}
    assert coverage_drift(before, after) == {"new_stores": ["3"], "not_seen_stores": ["2"],
        "changed_sources": ["1"], "collection_regressions": ["1"],
        "coverage_regressions": {"own_active": [], "price_universe_products": [], "planning_qualified_products": []}}
    before['stores'][0]['own_active'] = 10
    after['stores'][0]['own_active'] = 0
    before['stores'][0]['planning_qualified_products'] = 3
    after['stores'][0]['planning_qualified_products'] = None
    drift = coverage_drift(before, after)
    assert drift['coverage_regressions']['own_active'] == ['1']
    assert drift['coverage_regressions']['planning_qualified_products'] == []  # unknown is not zero


def test_full_official_map_projection_completes_paginated_visible_cards():
    data = {"resultStore": {"totalNrOfStores": 3, "storeCards": [
        {"accountNumber": "1", "storeName": "Visible", "highlightUrls": {"offers": "/offers/1"}}]},
        "SlimStores": {"slimStores": [
            {"accountNumber": str(i), "storeName": "Map", "bhsUrl": f"/butiker/{i}",
             "address": {"street": "Fixture 1", "city": "Malmö"},
             "geoPosition": {"latitude": 55.6, "longitude": 13.0}} for i in range(1, 4)]}}
    result = json.loads(sanitized_initial_data_payload(json.dumps(data).encode(), kind="stores_page"))
    cards = result["resultStore"]["storeCards"]
    assert len(cards) == 3
    assert cards[0]["storeName"] == "Visible" and cards[0]["bhsUrl"] == "/butiker/1"
    assert cards[2]["address"]["coordinates"]["latitude"] == 55.6
    assert result["resultStore"]["renderedCardCount"] == 1


@pytest.mark.parametrize("conflict", [False, True])
def test_repeated_campaign_keeps_evidence_and_conflicts_are_quarantined(conflict):
    rows = [offer(), offer(restriction="Max 1 köp/hushåll") if conflict else offer()]
    documents = tuple(RawFetch(chain=Chain.ICA, kind="offers_page", method="GET",
        url=f"https://www.ica.se/fixture/{i}", http_status=200, content_type="application/json",
        connector_version="fixture", fetched_at=datetime(2026, 9, 16, tzinfo=UTC),
        payload=json.dumps({"offers": {"weeklyOffers": [row]}}).encode())
        for i, row in enumerate(rows))
    result = IcaParser().parse_catalog(RawBatch(chain=Chain.ICA, documents=documents), ["a", "b"], store())
    if conflict:
        assert len(result.failures) == 2 and not result.products
    else:
        assert len(result.products) == 1 and not result.failures
        assert result.products[0].source_fields["source_evidence"] == ["a#weeklyOffers/0", "b#weeklyOffers/0"]


def test_deposit_in_mechanic_suffix_is_not_silently_lost():
    row = offer()
    row["parsedMechanics"]["value4"] = "+ pant"
    assert parse(row).failures


async def test_failed_discovery_retains_prior_stores_in_denominator(tmp_path):
    from grocery_data.app.connectors.base import ConnectorFetchError
    from grocery_data.app.services.ica_area_offers import collect_area_offers, offer_store_proposal
    class Failed:
        async def fetch_physical_stores(self, area):
            raise ConnectorFetchError('fixture failure', partial_batch=RawBatch(chain='ica', documents=()))
        parser = IcaParser()
        async def aclose(self):
            pass
    previous = {'stores':[{'ica_account_id':'fixture', 'area_membership':'inside',
        'area_reason':'official_address_locality_matches_existing_area', 'offers_url':'old',
        'flyer_links':['old-flyer'], 'last_success_at':'2026-09-16T00:00:00Z'}]}
    report = await collect_area_offers(GeographicArea(city='Lund'),tmp_path/'attempt',
                                      connector=Failed(),previous=previous)
    assert len(report['stores'])==1 and report['coverage']['in_area_denominator']==1
    assert not report['inventory']['complete'] and not offer_store_proposal(report)['inventory_approved']
    assert report['stores'][0]['collection_status'].startswith('unknown_')


def test_public_reader_empty_spread_slots_are_not_missing_document_pages():
    from grocery_data.app.services.ica_area_offers import source_page_inventory
    empty = {'files': [], 'elements': []}
    published = {'files': [{'role':'high','uri':'page_1_main.jpg'}], 'elements': []}
    result = source_page_inventory([empty, published, published, empty])
    assert result['source_spread_slots']==4 and result['expected_document_pages']==2
    assert not result['missing_content_slots']
    result = source_page_inventory([empty, published, empty, published, empty])
    assert result['expected_document_pages']==3 and result['missing_content_slots']==[2]
    assert source_page_inventory([{},published,empty])['missing_content_slots']==[0]


async def test_retained_store_page_offer_link_does_not_refetch_undue_prices(tmp_path):
    from types import SimpleNamespace

    from grocery_data.app.services.ica_area_offers import collect_area_offers
    official = store().model_copy(update={'source_fields': {'store_id':'15172',
        'official_store_url':'https://www.ica.se/butiker/fixture-1004598/'}})
    class Connector:
        parser = SimpleNamespace(parse_physical_stores=lambda *args, **kwargs: [official])
        async def fetch_physical_stores(self, area):
            return RawBatch(chain='ica',documents=(RawFetch(chain='ica',kind='physical_stores',method='GET',
                url='https://www.ica.se/butiker/lund/',http_status=200,content_type='application/json',
                connector_version='fixture',payload=b'{}',fetched_at=datetime(2026,9,28,10,tzinfo=UTC)),))
        async def aclose(self): pass
    previous = {'area': GeographicArea(city='Lund').model_dump(mode='json'), 'stores': [{
        'ica_account_id':'1004598', 'area_membership':'inside', 'name':'Fixture',
        'address':official.address,'postal_code':official.postal_code,'locality':official.city,
        'official_store_url':official.source_fields['official_store_url'],
        'offers_url':'https://www.ica.se/erbjudanden/fixture-1004598/',
        'last_success_at':'2026-09-28T09:00:00Z','row_approved_own':7,
        'collection_status':'success'}]}
    report = await collect_area_offers(GeographicArea(city='Lund'),tmp_path/'attempt',
        connector=Connector(),previous=previous,only_store_ids=set(),collect_flyers=False,discover_flyers=False)
    row=report['stores'][0]
    assert row['collection_status']=='not_due_retained' and row['row_approved_own']==7
    assert row['store']['source_fields']['offers_url']==previous['stores'][0]['offers_url']
    assert row['last_success_at']=='2026-09-28T09:00:00Z'

@pytest.mark.parametrize('identity', ['1003660', '1004598', 'future-municipality-store'])
def test_same_official_offer_page_with_product_details_is_one_integration(identity):
    from grocery_data.app.connectors.ica.public_material import public_links, store_offer_url
    page = f'https://www.ica.se/erbjudanden/fixture-{identity}/'
    payload = f'<a href="{page}">Alla erbjudanden</a><a href="{page}?id=5004133830&amp;action=details">Visa erbjudande</a>'.encode()
    links = public_links(payload)['offers_links']
    assert len(links) == 2
    assert store_offer_url(links, identity) == page
    assert store_offer_url(links, 'different') is None
    assert store_offer_url(links + [f'https://www.ica.se/erbjudanden/conflicting-{identity}/'], identity) is None
    assert store_offer_url([page.replace('www.ica.se', 'unverified.example')], identity) is None
    assert store_offer_url([page.replace('https:', 'http:')], identity) is None
