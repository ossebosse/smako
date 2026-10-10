import json
import sqlite3
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from deploy.scripts import run_daily_refresh as runner
from deploy.scripts.start_cron import scheduled_jobs


def test_no_due_tick_restart_base_deadline_and_new_source_promotion(tmp_path,monkeypatch):
    now=datetime(2026,9,20,8,tzinfo=UTC)
    db=tmp_path/'base.sqlite'
    with sqlite3.connect(db) as c:
        c.executescript("CREATE TABLE catalog_snapshots(id,state,is_active,coverage,promoted_at); CREATE TABLE source_products(catalog_snapshot_id,chain,store_external_id,fetched_at);")
        c.execute("INSERT INTO catalog_snapshots VALUES ('base-1','promoted',1,'full_catalog',?)",(now.isoformat(),))
        c.execute("INSERT INTO source_products VALUES ('base-1','hemkop','verified',?)",(now.isoformat(),))
    artifact=tmp_path/'artifact.json'
    artifact.write_text(json.dumps({'stores':[{'store_id':'context:verified','chain':'hemkop',
        'source_provenance':{'source_provider':'own','source_channel':'catalog','provider_store_id':'verified'}}]}))
    class Store:
        def __init__(self,*a):pass
        def read_active(self,*a):return SimpleNamespace(universe_id='universe-old')
        def resolve_active_artifact(self,*a,**k):return artifact
    monkeypatch.setattr(runner,'PreparedUniverseArtifactStore',Store)
    env={'PRICE_UNIVERSE_CACHE_ROOT':str(tmp_path/'pu'),'GROCERY_DATABASE_URL':'sqlite:///'+db.as_posix(),
         'DEMAND_REFRESH_STATE_PATH':str(tmp_path/'state.json'),'PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS':'context:verified'}
    plan=runner.demand_refresh_plan(now=now,environment=env)
    assert plan['work_due'] and not plan['due_sources']
    state=plan['state']|{'published_sources':plan['source_fingerprint'],'last_success_at':now.isoformat()}
    (tmp_path/'state.json').write_text(json.dumps(state))
    idle=runner.demand_refresh_plan(now=now+timedelta(hours=34),environment=env)
    assert not idle['work_due'] and idle['external_price_requests']==0
    due=runner.demand_refresh_plan(now=now+timedelta(hours=35),environment=env)
    assert due['work_due'] and due['due_sources']==['hemkop']
    assert datetime.fromisoformat(due['sources']['hemkop']['hard_stop_at']) == now+timedelta(hours=48)
    from grocery_data.app.services import operations_diagnostics

    with monkeypatch.context() as scoped:
        scoped.setattr(operations_diagnostics,'schema_holds',lambda root:{'hemkop':['verified']})
        partial=runner.demand_refresh_plan(now=now+timedelta(hours=35),environment=env|{'HEMKOP_STORE_EXTERNAL_IDS':'verified,other'})
        assert partial['due_sources']==['hemkop']
        assert partial['source_context_overrides']=={'HEMKOP_STORE_EXTERNAL_IDS':'other'}
        blocked=runner.demand_refresh_plan(now=now+timedelta(hours=35),environment=env|{'HEMKOP_STORE_EXTERNAL_IDS':'verified'})
        assert not blocked['due_sources'] and not blocked['source_context_overrides']
    # Campaign coalescing must not falsely advertise a local relay fetch.
    with sqlite3.connect(db) as c:
        c.execute("UPDATE source_products SET chain='willys'")
    payload=json.loads(artifact.read_bytes());payload['stores'][0]['chain']='willys'
    artifact.write_text(json.dumps(payload));(tmp_path/'state.json').unlink()
    source=tmp_path/'offers/lund';source.mkdir(parents=True)
    (source/'structured-source.json').write_text(json.dumps({'next_inventory_at':(now+timedelta(days=3)).isoformat(),
        'store_schedule':{'official':{'next_fetch_at':(now+timedelta(hours=25)).isoformat()}}}))
    local_env=env|{'WILLYS_COLLECTION_LOCATION':'LOCAL_RELAY','ICA_STRUCTURED_OFFERS_ROOT':str(tmp_path/'offers')}
    local=runner.demand_refresh_plan(now=now,environment=local_env)
    assert datetime.fromisoformat(local['sources']['willys']['next_fetch_at'])==now+timedelta(hours=35)
    assert local['sources']['willys']['reason']=='local_relay_35h_deadline'
    # Restore the independent full-source failure/restart scenario.
    with sqlite3.connect(db) as c:c.execute("UPDATE source_products SET chain='hemkop'")
    payload['stores'][0]['chain']='hemkop';artifact.write_text(json.dumps(payload))
    # Failure retry is durable, without changing the original observation.
    state['source_retries']={'hemkop':{'snapshots':['base-1'],'retry_at':(now+timedelta(hours=36)).isoformat()}}
    (tmp_path/'state.json').write_text(json.dumps(state))
    assert not runner.demand_refresh_plan(now=now+timedelta(hours=35,minutes=30),environment=env)['work_due']
    assert runner.demand_refresh_plan(now=now+timedelta(hours=36),environment=env)['work_due']
    with sqlite3.connect(db) as c:
        c.execute("UPDATE catalog_snapshots SET id='base-2'")
        c.execute("UPDATE source_products SET catalog_snapshot_id='base-2',fetched_at=?",((now+timedelta(hours=36)).isoformat(),))
    fresh=runner.demand_refresh_plan(now=now+timedelta(hours=36),environment=env)
    assert fresh['work_due'] and not fresh['due_sources']
    assert fresh['reasons']==['source_promotion_pending_publication']


def test_campaign_tick_replaces_full_daily_and_retry_but_retains_backup(monkeypatch):
    monkeypatch.setenv('DEMAND_REFRESH_ENABLED','true')
    assert scheduled_jobs()==(('DAILY_BACKUP_CRON','backup_sqlite.py'),('DEMAND_REFRESH_CRON','run_daily_refresh.py'))


def test_municipal_catalogs_missing_from_first_artifact_remain_scheduled(tmp_path, monkeypatch):
    import gzip
    from pathlib import Path

    from grocery_data.app.connectors.hemkop.parser import HemkopParser
    from grocery_data.app.connectors.willys.municipality_inventory import build_inventory
    from grocery_data.app.domain import GeographicArea, RawBatch
    from grocery_data.app.services import operations_diagnostics
    from grocery_data.app.services.hemkop_municipal_job import write
    from grocery_data.app.services.municipal_rollout import (
        add_municipality,
        refresh_scopes,
        scoped_environment,
    )

    now = datetime(2026, 10, 10, 20, tzinfo=UTC)
    database = tmp_path / 'base.sqlite'
    with sqlite3.connect(database) as db:
        db.executescript('CREATE TABLE catalog_snapshots(id,state,is_active,coverage,promoted_at); '
                         'CREATE TABLE source_products(catalog_snapshot_id,chain,store_external_id,fetched_at);')
        db.execute("INSERT INTO catalog_snapshots VALUES ('coop-1','promoted',1,'full_catalog',?)", (now.isoformat(),))
        db.execute("INSERT INTO source_products VALUES ('coop-1','coop','730400',?)", (now.isoformat(),))
    env = {'MUNICIPAL_COLLECTION_SCOPE_PATH': str(tmp_path / 'registry.json'),
           'PRICE_UNIVERSE_CACHE_ROOT': str(tmp_path / 'pu'),
           'GROCERY_DATABASE_URL': 'sqlite:///' + database.as_posix(),
           'HEMKOP_MUNICIPAL_ROOT': str(tmp_path / 'hemkop'),
           'REFRESH_CITY': 'Lund', 'REFRESH_MUNICIPALITY_CODE': '1281', 'REFRESH_POSTAL_CODE': '22350'}
    add_municipality('1280', '21120', environment=env, persist=True)
    scope = next(s for s in refresh_scopes(env) if s['municipality_code'] == '1280')
    env = scoped_environment(scope, env)
    fixtures = Path(__file__).resolve().parents[2] / 'grocery_data/tests/fixtures'
    raw = RawBatch.model_validate_json(gzip.decompress((fixtures / 'hemkop-municipal-register-20260928.json.gz').read_bytes()))
    boundary = json.loads(gzip.decompress((fixtures / 'willys-municipality-20260922.json.gz').read_bytes()))['boundary-1280']
    inventory = build_inventory(GeographicArea(city='Malmö', mode='municipality', municipality_code='1280'),
        raw, ['saved-national-register'], boundary, parser=HemkopParser())
    write(tmp_path / 'hemkop/1280/source-state.json', {'inventory': inventory,
        'next_inventory_at': (now + timedelta(days=3)).isoformat(), 'store_schedule': {}})
    artifact = tmp_path / 'artifact.json'
    artifact.write_text(json.dumps({'stores': [{'store_id': 'context:coop', 'chain': 'coop',
        'source_provenance': {'source_provider': 'own', 'source_channel': 'catalog', 'provider_store_id': '730400'}}]}))

    class Store:
        def __init__(self, *args): pass
        def read_active(self, *args): return SimpleNamespace(universe_id='first-malmo')
        def resolve_active_artifact(self, *args, **kwargs): return artifact

    monkeypatch.setattr(runner, 'PreparedUniverseArtifactStore', Store)
    plan = runner.demand_refresh_plan(now=now, environment=env)
    expected = {'4114', '4199', '4212', '4247'}
    assert plan['due_sources'] == ['hemkop']
    assert set(plan['pending_catalog_contexts']) == {'own:hemkop:' + identity for identity in expected}
    assert len(plan['state']['base_scope']) == 1  # No fabricated priced stores.
    assert plan['sources']['hemkop']['missing']
    write(Path(env['DEMAND_REFRESH_STATE_PATH']), plan['state'])
    # Restart still sees the missing online catalogs, including Limhamn in Malmö.
    assert runner.demand_refresh_plan(now=now, environment=env)['due_sources'] == ['hemkop']
    with monkeypatch.context() as guard:
        guard.setattr(operations_diagnostics, 'schema_holds', lambda root: {'hemkop': sorted(expected)})
        assert not runner.demand_refresh_plan(now=now, environment=env)['due_sources']
    with sqlite3.connect(database) as db:
        for identity in expected:
            db.execute("INSERT INTO catalog_snapshots VALUES (?,'promoted',1,'full_catalog',?)", ('hemkop-' + identity, now.isoformat()))
            db.execute("INSERT INTO source_products VALUES (?,'hemkop',?,?)", ('hemkop-' + identity, identity, now.isoformat()))
    fresh = runner.demand_refresh_plan(now=now, environment=env)
    assert not fresh['due_sources']
    assert datetime.fromisoformat(fresh['sources']['hemkop']['hard_stop_at']) == now + timedelta(hours=48)
