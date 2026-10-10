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


@pytest.mark.parametrize('code,city,postal', [('1281', 'Lund', '22350'), ('1280', 'Malmö', '21120')])
async def test_municipal_transport_rechecks_official_inventory_and_opt_in(tmp_path, monkeypatch, code, city, postal):
    from grocery_data.app.connectors.hemkop import HemkopConnector
    from grocery_data.app.connectors.hemkop.client import HemkopSourcePolicyError
    from grocery_data.app.services.area_membership import approved_municipal_stores
    from grocery_data.app.services.municipal_rollout import (
        add_municipality,
        hemkop_policy,
        municipal_environment,
        refresh_scopes,
    )

    fixtures = Path(__file__).parent / 'fixtures'
    raw = RawBatch.model_validate_json(gzip.decompress((fixtures / 'hemkop-municipal-register-20260928.json.gz').read_bytes()))
    boundary = json.loads(gzip.decompress((fixtures / 'willys-municipality-20260922.json.gz').read_bytes()))['boundary-' + code]
    inventory = build_inventory(GeographicArea(city=city, mode='municipality', municipality_code=code),
        raw, ['saved-national-register'], boundary, parser=HemkopParser())
    monkeypatch.setenv('MUNICIPAL_COLLECTION_SCOPE_PATH', str(tmp_path / 'registry.json'))
    monkeypatch.setenv('GROCERY_DATABASE_URL', 'sqlite:///' + (tmp_path / 'grocery.sqlite').as_posix())
    monkeypatch.setenv('HEMKOP_MUNICIPAL_ROOT', str(tmp_path / 'hemkop'))
    monkeypatch.setenv('HEMKOP_MUNICIPAL_OFFERS_ENABLED', 'true')
    monkeypatch.setenv('HEMKOP_STORE_EXTERNAL_IDS', '4123,4224')  # Legacy Lund transport list.
    monkeypatch.setenv('REFRESH_CITY', 'Lund')
    monkeypatch.setenv('REFRESH_MUNICIPALITY_CODE', '1281')
    monkeypatch.setenv('REFRESH_POSTAL_CODE', '22350')
    monkeypatch.setenv('PRICE_UNIVERSE_CACHE_ROOT', str(tmp_path / 'price-universes'))
    add_municipality(code, postal, persist=True)
    write(tmp_path / 'hemkop' / code / 'source-state.json', {'inventory': inventory})
    scope = next(s for s in refresh_scopes() if s['municipality_code'] == code)
    expected = {k for k, s in approved_municipal_stores(inventory).items() if s.online_shopping}
    with municipal_environment(scope):
        policy = hemkop_policy(city, HemkopOperatorCrawlPolicy.from_environment())
        assert policy.allowed_store_ids == expected
        for identity in sorted(expected):
            connector = HemkopConnector.for_exact_full_collection(identity, policy=policy)
            try:
                assert connector.client.allowed_store_ids == {identity}
            finally:
                await connector.aclose()
        # A stale/injected planning object cannot expand fresh transport authority.
        injected = HemkopOperatorCrawlPolicy(True, frozenset({'9999', *expected}))
        with pytest.raises(HemkopSourcePolicyError):
            HemkopConnector.for_exact_full_collection('9999', policy=injected)
        with monkeypatch.context() as selected:
            identity = min(expected)
            selected.setenv('MUNICIPAL_HEMKOP_DUE_STORE_IDS', identity + ',9999')
            assert hemkop_policy(city, policy).allowed_store_ids == {identity}
            other = next(i for i in expected if i != identity)
            with pytest.raises(HemkopSourcePolicyError):
                HemkopConnector.for_exact_full_collection(other, policy=policy)
            selected.setenv('MUNICIPAL_HEMKOP_DUE_STORE_IDS', '')
            with pytest.raises(HemkopSourcePolicyError):
                HemkopConnector.for_exact_full_collection(identity, policy=policy)
        monkeypatch.setenv('HEMKOP_ALLOW_FULL_CRAWL', 'false')
        with pytest.raises(HemkopSourcePolicyError):
            HemkopConnector.for_exact_full_collection(min(expected), policy=policy)
        monkeypatch.setenv('HEMKOP_ALLOW_FULL_CRAWL', 'true')
        from grocery_data.app.services import operations_diagnostics
        with monkeypatch.context() as guard:
            guard.setattr(operations_diagnostics, 'schema_holds', lambda root: {'hemkop': sorted(expected)})
            with pytest.raises(HemkopSourcePolicyError):
                HemkopConnector.for_exact_full_collection(min(expected), policy=policy)
        with monkeypatch.context() as guard:
            guard.setenv('MUNICIPAL_REFRESH_SCOPE', '1480')
            with pytest.raises(ValueError, match='municipality'):
                HemkopConnector.for_exact_full_collection(min(expected), policy=policy)
        write(tmp_path / 'hemkop' / code / 'source-state.json', {})
        with pytest.raises(ValueError, match='inventory'):
            HemkopConnector.for_exact_full_collection(min(expected), policy=policy)


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
