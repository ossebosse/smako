"""Retained real flyer text plus explicitly injected adverse cases."""
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors.willys.flyer_client import FlyerClient
from grocery_data.app.connectors.willys.flyer_inventory import (
    approved_flyer_stores,
    build_inventory,
)
from grocery_data.app.connectors.willys.flyer_offers import WillysFlyerConnector, document_review
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.services import willys_flyer_job as job
from grocery_data.app.services.offer_rows import row_blockers

ROOT = Path(__file__).parents[2] / 'reports/willys-flyers-20260923'


@pytest.mark.parametrize('status', [401, 403, 429])
async def test_access_stop_is_not_repeated_for_later_stores(status):
    client = FlyerClient()
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(status)))
    try:
        with pytest.raises(ValueError, match=f'HTTP {status}'):
            await client.request('GET', 'https://reklamblad.willys.se/willys/2863/')
        with pytest.raises(ValueError, match='not retried'):
            await client.request('GET', 'https://reklamblad.willys.se/willys/2843/')
        assert client.requests == 1
    finally:
        await client.aclose()


def inventory(code='1281'):
    return json.loads((ROOT / f'inventory-{code}/inventory.json').read_bytes())


@pytest.fixture(scope='module')
def examples():
    result = {}
    for identity, code in [('2863', '1281'), ('2352', '1280')]:
        inv = inventory(code)
        store = approved_flyer_stores(inv)[identity]
        raw = RawBatch.model_validate_json((ROOT / f'live-{identity}.json').read_bytes())
        connector = WillysFlyerConnector(store=store, inventory=inv, raw=raw)
        parsed = connector.parse_catalog(raw, ['listing', 'document'], store)
        result[identity] = (store, raw, connector, parsed)
    return result


@pytest.mark.parametrize('code,expected', [('1281', {'2863'}), ('1280', {'2843','2851','2870','2865','2879','2352'})])
def test_official_inventory_selects_offline_flyers_without_changing_online(code, expected):
    inv = inventory(code)
    approved = approved_flyer_stores(inv)
    assert set(approved) == expected
    assert all(s.online_shopping is False and s.price_context_type.value == 'physical_store' for s in approved.values())
    assert inv['unresolved_registry_rows']  # original national unknown remains visible
    assert all(not r['collection_selected'] for r in inv['stores'] if r['online_collection_selected'])
    inv['selected_store_ids'].append('invented-neighbor')
    with pytest.raises(ValueError):
        approved_flyer_stores(inv)


def test_missing_coordinates_or_official_link_remain_visible():
    inv = inventory()
    raw = RawBatch.model_validate(inv['registry'])
    rows = raw.documents[0].json_payload()
    target = next(r for r in rows if r.get('storeId') == '2863')
    target['geoPoint'] = {}
    target['address'].update(latitude=None, longitude=None)
    changed = raw.model_copy(update={'documents': (raw.documents[0].model_copy(update={'payload':json.dumps(rows).encode()}),)})
    rebuilt = build_inventory(GeographicArea.model_validate(inv['area']), changed.model_dump(mode='json'), inv['boundary'])
    selected = next(r for r in rebuilt['stores'] if r['store']['external_id']=='2863')
    assert selected['geographic_evidence']['status']=='unknown' and not selected['collection_selected']


def test_all_reviewed_rows_no_example_count_cap_and_no_invented_facts(examples):
    for identity, expected in [('2863',21),('2352',61)]:
        _, raw, connector, parsed = examples[identity]
        assert len(parsed.products)==expected
        assert len(connector.row_acceptance['advertisement_decisions']) == (34 if identity=='2863' else 112)
        assert all(p.gtin is p.regular_price is p.sale_price is p.member_price is None for p in parsed.products)
        assert all(p.fetched_at==min(d.fetched_at for d in raw.documents) for p in parsed.products)
        assert all(not row_blockers(p) for p in parsed.products)
        assert any('variant' in f.error_message for f in parsed.failures)
        assert any('deposit' in f.error_message for f in parsed.failures)
        assert sum(f.error_message=='duplicate_advertisement' for f in parsed.failures)==1


@pytest.mark.parametrize('field,value', [('package_quantity',999),('gtin','7311071330525'),('name','different variant')])
def test_changed_product_does_not_inherit_text_review(examples,field,value):
    p=examples['2863'][3].products[0]
    assert row_blockers(p.model_copy(update={field:value}))


def test_shorter_days_member_multibuy_and_household_group_remain_explicit(examples):
    products=examples['2352'][3].products
    ice=next(p for p in products if 'Djungelmix' in p.name)
    assert ice.offers[0].valid_to.isoformat()=='2026-09-23'
    assert ice.offers[0].member_only and ice.offers[0].max_quantity==3
    tomatoes=[p for p in products if 'tomater' in p.name]
    assert len(tomatoes)==2
    assert tomatoes[0].offers[0].source_payload['price_contract_id']==tomatoes[1].offers[0].source_payload['price_contract_id']
    assert tomatoes[0].offers[0].quantity==3 and tomatoes[0].offers[0].max_quantity==5


def test_new_campaign_or_wrong_store_cannot_inherit_review(examples):
    store,raw,_,_=examples['2863']
    other=examples['2352'][0]
    with pytest.raises(ValueError,match='binding'):
        document_review(raw,other)
    listing=raw.documents[0]
    payload=listing.json_payload();payload['publication_url']='https://cdn.ipaper.io/iPaper/Papers/new/'
    changed=raw.model_copy(update={'documents':(listing.model_copy(update={'payload':json.dumps(payload).encode()}),raw.documents[1])})
    with pytest.raises(ValueError,match='mismatch'):
        document_review(changed,store)


def test_failure_backoff_preserves_success_age_and_durable_selection(tmp_path):
    inv=inventory(); now=datetime(2026,9,23,21,0,tzinfo=UTC)
    observed=now-timedelta(hours=2)
    state=job.update_selection(inv,{'2863':{'status':'success','observed_at':observed.isoformat(),
        'windows':[{'valid_from':'2026-09-21','valid_to':'2026-09-27'}]}},now=now)
    failed=job.update_selection(inv,{'2863':{'status':'failed'}},previous=state,now=now)
    row=next(r for r in failed['stores'] if r['selected'])
    assert row['last_success']==observed.isoformat() and row['failed_attempts']==1
    assert datetime.fromisoformat(row['next_fetch_at'])>now
    env={'WILLYS_FLYER_ROOT':str(tmp_path),'WILLYS_FLYER_ENABLED':'true','WILLYS_FLYER_MUNICIPALITY_CODE':'1281'}
    root,config=job.configuration(env);job.write(root/'config.json',config)
    assert job.configuration({'WILLYS_FLYER_ROOT':str(tmp_path)})[1]==config
    with pytest.raises(ValueError):
        job.configuration({**env,'REFRESH_CITY':'Malmö'})
