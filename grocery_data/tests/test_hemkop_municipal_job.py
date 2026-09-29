import gzip
import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from grocery_data.app.connectors.hemkop import HemkopOperatorCrawlPolicy
from grocery_data.app.connectors.hemkop.parser import HemkopParser
from grocery_data.app.connectors.willys.municipality_inventory import build_inventory
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.services.hemkop_context_collection import HemkopMultiContextCollectionPlanner
from grocery_data.app.services.hemkop_municipal_job import persist_official_inventory, write
from grocery_data.app.storage import create_database_engine, create_schema


@pytest.mark.parametrize('code,city,expected', [('1281','Lund',{'4517','4224','4123'}),
                                            ('1280','Malmö',{'4212','4114','4247','4199'})])
def test_official_register_drives_catalog_selection_independently_of_predefined_contexts(tmp_path, monkeypatch, code, city, expected):
    fixtures = Path(__file__).parent/'fixtures'
    raw = RawBatch.model_validate_json(gzip.decompress((fixtures/'hemkop-municipal-register-20260928.json.gz').read_bytes()))
    boundary = json.loads(gzip.decompress((fixtures/'willys-municipality-20260922.json.gz').read_bytes()))['boundary-' + code]
    inventory = build_inventory(GeographicArea(city=city,mode='municipality',municipality_code=code),
        raw,['saved-national-register'],boundary,parser=HemkopParser())
    inside = {r['store']['external_id'] for r in inventory['stores'] if r['geographic_evidence']['status']=='inside'}
    assert inside == expected
    assert len(inventory['stores']) == inventory['registry_rows'] == 205
    database = tmp_path/'grocery.sqlite'; root = tmp_path/'municipal'
    engine = create_database_engine('sqlite:///' + database.as_posix()); create_schema(engine)
    monkeypatch.setenv('GROCERY_DATABASE_URL','sqlite:///' + database.as_posix())
    monkeypatch.setenv('HEMKOP_MUNICIPAL_ROOT',str(root))
    monkeypatch.setenv('HEMKOP_MUNICIPAL_OFFERS_ENABLED','true')
    monkeypatch.setenv('REFRESH_MUNICIPALITY_CODE',code)
    write(root/code/'source-state.json',{'inventory':inventory})
    persist_official_inventory(inventory,database)
    online = {r['store']['external_id'] for r in inventory['stores'] if r['store']['external_id'] in inside and r['store']['online_shopping']}
    policy = HemkopOperatorCrawlPolicy(allow_full_crawl=True,allowed_store_ids=frozenset(online))
    with Session(engine) as session:
        result = HemkopMultiContextCollectionPlanner(session).plan(city,policy=policy)
        assert {t.store_external_id for t in result.targets} == online
        assert not any(t.store_external_id=='4517' for t in result.targets)
    engine.dispose()


async def test_access_stop_does_not_continue_with_another_store(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from grocery_data.app.connectors.hemkop import HemkopConnector, physical_offers
    from grocery_data.app.connectors.hemkop.client import HemkopRateLimitStop
    from grocery_data.app.domain import RawFetch
    from grocery_data.app.services.hemkop_municipal_job import run_source_job

    fixtures = Path(__file__).parent/'fixtures'
    raw = RawBatch.model_validate_json(gzip.decompress((fixtures/'hemkop-municipal-register-20260928.json.gz').read_bytes()))
    boundary = json.loads(gzip.decompress((fixtures/'willys-municipality-20260922.json.gz').read_bytes()))['boundary-1281']
    database = tmp_path/'grocery.sqlite'; root = tmp_path/'municipal'
    engine = create_database_engine('sqlite:///' + database.as_posix()); create_schema(engine);engine.dispose()
    env = {'GROCERY_DATABASE_URL':'sqlite:///' + database.as_posix(), 'HEMKOP_MUNICIPAL_ROOT':str(root),
        'HEMKOP_MUNICIPAL_OFFERS_ENABLED':'true','REFRESH_MUNICIPALITY_CODE':'1281'}
    write(root/'1281/boundary.json',boundary)
    connector = HemkopConnector.for_bounded_discovery()
    async def stores(area): return raw
    monkeypatch.setattr(connector,'fetch_stores',stores)
    monkeypatch.setattr(HemkopConnector,'for_bounded_discovery',lambda:connector)
    calls=[]
    async def blocked(client,store):
        calls.append(store.external_id)
        error = RawFetch(chain='hemkop',kind='rate_limit',method='GET',url='https://www.hemkop.se/search/campaigns/offline',
            fetched_at=datetime.now(UTC),http_status=429,connector_version='hemkop-v1',payload=b'{"reason":"rate_limited"}')
        raise HemkopRateLimitStop('fixture rate limit',error,retry_after=300,retry_after_raw='300')
    monkeypatch.setattr(physical_offers,'fetch',blocked)
    result=await run_source_job(city='Lund',environment=env)
    assert len(calls)==1
    assert sum(r['status']=='not_requested_after_access_stop' for r in result['outcomes'].values())==2
    assert not result['approved_store_ids']
