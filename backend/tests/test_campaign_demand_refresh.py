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
