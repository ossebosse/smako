"""Private packaged ordinary runner + private HTTP app, never a production write."""
import hashlib
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path('/work/lifecycle')
PROD = Path('/srv/app/var')


def save(name, data):
    (ROOT / (name + '.json')).write_text(json.dumps(data, default=str, ensure_ascii=False, indent=2))


def configure():
    os.environ.update(APP_ENV='development', PUBLIC_BASE_URL='http://127.0.0.1:8000',
        SECRET_KEY=secrets.token_hex(32), BETA_ADMIN_TOKEN=secrets.token_hex(32),
        PLAN_STORE_PATH=str(ROOT/'plans.sqlite'), GROCERY_DATABASE_URL='sqlite+pysqlite:///'+str(ROOT/'grocery.sqlite'),
        GROCERY_RAW_SNAPSHOT_ROOT=str(ROOT/'raw'), PRICE_UNIVERSE_CACHE_ROOT=str(ROOT/'price-universes'),
        PRICE_UNIVERSE_PREWARM_ENABLED='false', INTERNAL_APP_BASE_URL='http://127.0.0.1:8000',
        REFRESH_CITY='Lund', REFRESH_POSTAL_CODE='22350', REFRESH_REPORT_DIR=str(ROOT/'reports'),
        REFRESH_RUNNER_STATUS_PATH=str(ROOT/'runner-status.json'), DEMAND_REFRESH_STATE_PATH=str(ROOT/'demand.json'),
        DEMAND_REFRESH_ENABLED='true', COOP_MUNICIPAL_OFFERS_ROOT=str(ROOT/'municipal'),
        COOP_MUNICIPAL_OFFERS_ENABLED='true', COOP_MUNICIPALITY_CODE='1281',
        COOP_MUNICIPAL_INVENTORY='/evaluation/inventory.json', COOP_XTRA_OFFERS_ENABLED='false',
        ICA_AREA_OFFER_CANDIDATES_ENABLED='false', ICA_STRUCTURED_OFFERS_ENABLED='false',
        ICA_FLYER_PAID_ENABLED='false', ICA_FLYER_VISUAL_COMMAND_JSON='')


def copy_active(source, target):
    target.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((source/'active/city-lund.json').read_bytes())
    artifact = source/manifest['artifact_file']
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == manifest['artifact_sha256']
    destination = target/manifest['artifact_file']
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, destination)
    (target/'active').mkdir(exist_ok=True)
    shutil.copyfile(source/'active/city-lund.json', target/'active/city-lund.json')


def initialize():
    ROOT.mkdir(exist_ok=False)
    configure()
    shutil.copyfile('/work/base-final/frozen-base.sqlite', ROOT/'grocery.sqlite')
    copy_active(PROD/'price_universes', ROOT/'price-universes')
    copy_active(PROD/'price_universes/external-provider-cache', ROOT/'price-universes/external-provider-cache')
    save('initial', {'at': datetime.now(UTC).isoformat(), 'production_manifest_sha256': hashlib.sha256((PROD/'price_universes/active/city-lund.json').read_bytes()).hexdigest()})


def run(mode):
    if mode == 'initialize':
        initialize()
        print('private durable full source and manifests initialized')
        return
    configure()
    if mode == 'prepare-raw':
        target_root = ROOT/'raw'
        source_root = PROD/'raw_snapshots'
        files, size = 0, 0
        with sqlite3.connect(f'file:{ROOT / "grocery.sqlite"}?mode=ro', uri=True) as db:
            rows = db.execute("""SELECT DISTINCT r.payload_location, r.payload_hash FROM raw_snapshots r
                JOIN catalog_snapshots cs ON cs.id=r.catalog_snapshot_id WHERE cs.is_active=1""").fetchall()
        for location, expected in rows:
            source = (source_root/location).resolve()
            target = (target_root/location).resolve()
            assert source.is_relative_to(source_root) and target.is_relative_to(target_root)
            data = source.read_bytes()
            assert hashlib.sha256(data).hexdigest() == expected
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                assert target.read_bytes() == data
            else:
                target.write_bytes(data)
            files += 1
            size += len(data)
        save('retained-raw-base', {'files': files, 'bytes': size, 'source_observations_unchanged': True})
        print(json.dumps({'files': files, 'bytes': size}))
        return
    if mode == 'cycle-xtra':
        os.environ['COOP_XTRA_OFFERS_ENABLED'] = 'true'
    from deploy.scripts import run_daily_refresh as runner
    from grocery_data.app.services.coop_offer_job import source_plan, read, write, configuration, location
    from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path
    if mode in {'cycle-fetch-failure', 'cycle-recovery', 'cycle-withdrawal', 'cycle-final-recovery'}:
        root, config = configuration()
        with RefreshRunLock(production_refresh_lock_path(ROOT/'grocery.sqlite', ROOT/'price-universes')):
            path = location(root, config)
            state = read(path)
            selected = next(r for r in state['selection']['stores'] if r['selected'] and r['concept'] != 'X:-tra')
            selected['next_fetch_at'] = datetime.now(UTC).isoformat()
            write(path, state)
            save(mode+'-injection', {'forced_due_store_id': selected['store_id'], 'observation_times_modified': False,
                 'failure_injected': mode == 'cycle-fetch-failure', 'recovery': 'actual official transport'})
    if mode == 'cycle-withdrawal':
        os.environ['TEST_COOP_WITHDRAWAL'] = 'true'
    if mode == 'cycle-expiry':
        root, config = configuration()
        state = read(location(root, config))
        last = max(w['valid_to'] for refs in state['approved'].values() for ref in refs for w in ref.get('windows', []) if w.get('valid_to'))
        day = datetime.fromisoformat(last) + timedelta(days=1)
        os.environ['TEST_COOP_EXPIRY_DATE'] = day.isoformat()
        save(mode+'-injection', {'clock_scope':'Coop provider purchase day only; base freshness uses actual clock', 'purchase_day':day.isoformat(), 'source_observations_modified':False})
    if mode == 'cycle-c':
        # Remove initialization inputs; root/config and source pointer are sufficient.
        for key in ['COOP_MUNICIPAL_OFFERS_ENABLED','COOP_MUNICIPALITY_CODE','COOP_MUNICIPAL_INVENTORY','COOP_XTRA_OFFERS_ENABLED']:
            os.environ.pop(key, None)
    import httpx
    import uvicorn
    from app import main as application
    started = time.perf_counter()
    before = (PROD/'price_universes/active/city-lund.json').read_bytes()
    server = uvicorn.Server(uvicorn.Config(application.app, host='127.0.0.1', port=8000, log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic()+180
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError('private application startup failed')
        time.sleep(.1)
    result = {'mode': mode, 'started_at': datetime.now(UTC).isoformat(), 'clock': 'actual', 'code_mounts': False}
    original_run = subprocess.run
    def quiet_child(command, **kwargs):
        if '-m' in command and 'grocery_data' in command:
            if mode in {'cycle-fetch-failure', 'cycle-withdrawal', 'cycle-expiry'}:
                command = [command[0], '/evaluation/fault_child.py', *command[3:]]
            kwargs['stdout'] = subprocess.DEVNULL
            kwargs['stderr'] = subprocess.DEVNULL
        return original_run(command, **kwargs)
    subprocess.run = quiet_child
    try:
        result['before'] = source_plan()
        if mode in {'cycle-b','cycle-base','cycle-fetch-failure','cycle-recovery','cycle-reload-failure','cycle-reload-recovery','cycle-xtra','cycle-xtra-off','cycle-withdrawal','cycle-final-recovery','cycle-final-plan','cycle-expiry'}:
            # Existing ordinary wrapper, exact base-only request; Coop remains not due.
            command = runner.build_refresh_command()+['--chain','citygross']
            if mode != 'cycle-base':
                command.append('--no-external-refresh')
            if mode == 'cycle-reload-failure':
                def fail_reload():
                    raise runner.RuntimeReloadUnavailable('injected private test')
                runner._reload_runtime = fail_reload
            with RefreshRunLock(production_refresh_lock_path(ROOT/'grocery.sqlite', ROOT/'price-universes')) as lock:
                result['exit_code'] = runner._run_locked(lock, started_at=datetime.now(UTC), command=command)
        elif mode != 'plan':
            result['exit_code'] = runner.main()
        result['after'] = source_plan()
        from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
        store = PreparedUniverseArtifactStore(ROOT/'price-universes')
        artifact = store.resolve_active_artifact('Lund', verify_hash=True)
        from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
        prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact.read_bytes()).restore()
        offers = [p for p in prepared.universe.products if p.chain == 'coop' and p.coverage == 'offers_only']
        result.update(universe_id=prepared.universe.universe_id, coop_products=len(offers),
            coop_rows=[p.model_dump(mode='json') for p in offers], artifact=str(artifact),
            oldest_price_age_hours=prepared.status(now=datetime.now(UTC)).oldest_price_age_hours)
        with httpx.Client(base_url='http://127.0.0.1:8000', timeout=240) as client:
            result['health'] = client.get('/health').status_code
            result['ready'] = client.get('/ready').status_code
            if mode in {'cycle-b','cycle-base','cycle-final-plan','plan'}:
                request = json.loads(Path('/evaluation/request.json').read_bytes())
                from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator
                from app.models.recipe import Recipe
                frozen = json.loads(Path('/evaluation/request-recipes.json').read_bytes())
                traced = []
                for method in ['generate_for_meal_type','generate_reference_candidates']:
                    def recipes(self,*args,_method=method,**kwargs):
                        entry = frozen[len(traced)]
                        assert entry['method'] == _method
                        traced.append(entry)
                        return [Recipe.model_validate(r) for r in entry['recipes']]
                    setattr(DeterministicRecipeCandidateGenerator, method, recipes)
                audits = []
                from app.services.personal_planner import PersonalPlanner
                original = PersonalPlanner.basket
                def basket(self,*a,**kw):
                    value = original(self,*a,**kw)
                    audits.append(value['audit'].passed)
                    return value
                PersonalPlanner.basket = basket
                client.get('/api/personal/state').raise_for_status()
                start = time.perf_counter()
                response = client.post('/api/plans', json=request)
                result['planning'] = {'status': response.status_code, 'seconds': time.perf_counter()-start, 'audits': audits}
                if response.status_code == 201:
                    saved = response.json()
                    readback = client.get('/api/plans/'+saved['plan_id'])
                    result['planning'].update(saved_equals_readback=readback.json()['plan']==saved['plan'],
                        cost=saved['plan']['optimized_basket']['total'], plan=saved['plan'])
                else:
                    result['planning']['error'] = response.json()
        assert before == (PROD/'price_universes/active/city-lund.json').read_bytes()
        result['production_unchanged'] = True
    finally:
        subprocess.run = original_run
        server.should_exit = True
        thread.join(timeout=20)
        result['seconds'] = time.perf_counter()-started
        save(mode, result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'before','after','coop_rows','planning'}}, default=str), flush=True)
    if 'planning' in result:
        print(json.dumps({**{k:v for k,v in result['planning'].items() if k not in {'plan','audits'}},
                          'audit_count': len(result['planning']['audits']),
                          'all_audits_pass': all(result['planning']['audits'])}, default=str))

