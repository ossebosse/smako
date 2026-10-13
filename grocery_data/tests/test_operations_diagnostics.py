import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from grocery_data.app.services import operations_diagnostics as ops


@pytest.fixture
def context(tmp_path, monkeypatch):
    database = tmp_path/'grocery.sqlite'
    universe = tmp_path/'price_universes'
    raw = tmp_path/'raw'
    (universe/'active').mkdir(parents=True)
    raw.mkdir()
    root = tmp_path/'reports/operations'
    root.mkdir(parents=True)
    env = {'GROCERY_DATABASE_URL': 'sqlite:///'+database.as_posix(),
           'PRICE_UNIVERSE_CACHE_ROOT': str(universe), 'GROCERY_RAW_SNAPSHOT_ROOT': str(raw),
           'PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS': 'context:willys:test', 'BUILD_ID': 'reviewed-test'}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    with sqlite3.connect(database) as db:
        db.executescript('''
        CREATE TABLE catalog_snapshots(id TEXT PRIMARY KEY,chain TEXT,scope_key TEXT,
        coverage TEXT,state TEXT,is_active INT,collector_run_id TEXT,parser_version TEXT,
        connector_version TEXT,metrics TEXT,rejection_reason TEXT,created_at TEXT,rejected_at TEXT,promoted_at TEXT);
        CREATE TABLE raw_snapshots(id TEXT PRIMARY KEY,catalog_snapshot_id TEXT,kind TEXT,store_external_id TEXT,
        payload_location TEXT,payload_hash TEXT,fetched_at TEXT,page_number INT);
        CREATE TABLE source_products(catalog_snapshot_id TEXT,chain TEXT,store_external_id TEXT,fetched_at TEXT);
        ''')
    return SimpleNamespace(database=database, universe=universe, raw=raw, root=root, env=env)


def snapshot(c, sid, state='rejected', metrics=None, chain='hemkop'):
    with sqlite3.connect(c.database) as db:
        db.execute('INSERT INTO catalog_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                   (sid, chain, 'lund:'+chain+':4123', 'full_online_catalog', state, int(state=='promoted'),
                    'run-'+sid, 'parser-old', 'connector-v1', json.dumps(metrics or {}),
                    'ConnectorFetchError', '2026-10-08T12:00:00+00:00',
                    '2026-10-08T12:01:00+00:00' if state=='rejected' else None,
                    '2026-10-08T12:02:00+00:00' if state=='promoted' else None))


def raw(c, sid, payload, name='raw.json', kind='store_context'):
    data=json.dumps(payload).encode()
    (c.raw/name).write_bytes(data)
    with sqlite3.connect(c.database) as db:
        db.execute('INSERT INTO raw_snapshots VALUES (?,?,?,?,?,?,?,?)',
                   (sid+name, sid, kind, '4123', name, hashlib.sha256(data).hexdigest(),
                    '2026-10-08T12:00:00+00:00', 0))


def test_schema_deduplicates_runs_not_ticks_and_marks_source_recovery(context):
    c=context
    metrics={'effective_schema_diff': {'added': ['4123:store_context:$[].hasPickingBaseStore']}}
    snapshot(c, 'one', metrics=metrics)
    raw(c, 'one', {'storeId':'4123', 'hasPickingBaseStore': False})
    first=ops.record_incidents(c.env)
    item=next(iter(first['incidents'].values()))
    assert item['code']=='SOURCE_SCHEMA_CHANGED'
    assert item['reproduction']['fields'][0]['value'] is False
    assert ops.record_incidents(c.env)['incidents'][item['incident_id']]['occurrences']==1
    snapshot(c, 'two', metrics=metrics)
    raw(c, 'two', {'storeId':'4123', 'hasPickingBaseStore': False}, name='two.json')
    assert ops.record_incidents(c.env)['incidents'][item['incident_id']]['occurrences']==2
    snapshot(c, 'three', state='promoted')
    assert ops.record_incidents(c.env)['incidents'][item['incident_id']]['status']=='source_recovered'


def test_unfinished_older_job_does_not_hide_new_failure(context):
    snapshot(context, 'pending', state='fetched')
    snapshot(context, 'failed', metrics={'run_metrics': {'http_error_count':1}})
    index=ops.record_incidents(context.env)
    assert index['pending']==['pending']
    assert next(iter(index['incidents'].values()))['code']=='SOURCE_TRANSPORT_FAILED'
    with sqlite3.connect(context.database) as db:
        db.execute("UPDATE catalog_snapshots SET state='rejected' WHERE id='pending'")
    assert ops.record_incidents(context.env)['pending']==[]


def test_raw_corruption_and_path_escape_fail_closed(context):
    snapshot(context, 'one')
    raw(context, 'one', {'storeId':'4123'})
    (context.raw/'raw.json').write_text('{}')
    with pytest.raises(ValueError, match='raw_hash_mismatch'):
        ops.reproduce(context.database, context.raw, 'one')
    with sqlite3.connect(context.database) as db:
        db.execute("UPDATE raw_snapshots SET payload_location='../grocery.sqlite'")
    with pytest.raises(ValueError, match='raw_reference_outside_root'):
        ops.reproduce(context.database, context.raw, 'one')


@pytest.mark.parametrize('metrics,code,step', [
    ({'run_metrics': {'rate_limit_count':1}}, 'SOURCE_RATE_LIMITED', 'transport'),
    ({'catalog_completion': {'x': {'complete':False,'conflicting_duplicates':1}}}, 'SOURCE_COMMERCIAL_CONFLICT', 'collection'),
    ({'catalog_completion': {'x': {'complete':False}}}, 'SOURCE_INCOMPLETE', 'collection'),
])
def test_failure_stages(metrics, code, step):
    assert ops.classify(metrics, 'ConnectorFetchError')[:2]==(code,step)


def test_imported_is_not_loaded_or_receipted_and_status_is_readonly(context, monkeypatch):
    c=context
    snapshot(c, 'new', state='promoted', chain='willys', metrics={'source_artifact': {'sha256':'digest'}})
    with sqlite3.connect(c.database) as db:
        db.execute('INSERT INTO source_products VALUES (?,?,?,?)', ('new','willys','4123','2026-10-08T12:00:00+00:00'))
    (c.root/'demand-refresh.json').write_text(json.dumps({'base_scope':[{'store_id':'context:willys:test',
        'chain':'willys','source_provenance':{'provider_store_id':'4123'}}], 'retry_at':'2026-10-10T12:00:00+00:00'}))
    (c.universe/'active/city-lund.json').write_text(json.dumps({'universe_id':'disk-old','snapshot_ids':['old']}))
    monkeypatch.setattr(ops,'request_json',lambda url:{'http_status':503,'body':{'universe_id':'loaded-old','snapshot_ids':['old']}})
    before=c.database.read_bytes()
    result=ops.status(c.env,now=datetime(2026,10,8,14,tzinfo=UTC))
    item=result['required_contexts'][0]
    assert item['qualified'] and not item['loaded'] and not item['published']
    assert item['source_artifact_sha256']=='digest' and item['receipt']=='unknown_until_relay_read'
    assert item['freshness_risk'] and item['publication_overdue']
    assert result['external_price_requests']==0 and c.database.read_bytes()==before


def test_unreachable_app_and_missing_index_never_green(context, monkeypatch):
    monkeypatch.setattr(ops.urllib.request,'urlopen',lambda *a,**k: (_ for _ in ()).throw(OSError('private token must not leak')))
    value=ops.status(context.env)
    assert value['ready']['status']=='unknown'
    assert value['unknown_required_contexts']==['context:willys:test']
    assert 'private token' not in json.dumps(value)


def test_municipal_status_uses_own_journal_catalog_and_serving_scope(context, monkeypatch):
    from urllib.parse import parse_qs, urlsplit

    c = context
    snapshot(c, 'malmo-new', state='promoted', chain='willys')
    with sqlite3.connect(c.database) as db:
        db.execute('INSERT INTO source_products VALUES (?,?,?,?)',
                   ('malmo-new', 'willys', 'malmo-store', '2026-10-08T12:00:00+00:00'))
    municipal = c.root / 'municipalities/1280/demand-refresh.json'
    municipal.parent.mkdir(parents=True)
    municipal.write_text(json.dumps({'base_scope': [{'store_id': 'context:willys:malmo',
        'chain': 'willys', 'source_provenance': {'provider_store_id': 'malmo-store'}}]}))
    (c.root / 'demand-refresh.json').write_text(json.dumps({'base_scope': [
        {'store_id': 'context:willys:lund', 'chain': 'willys'}]}))
    (c.universe / 'active/city-malmö.json').write_text(json.dumps(
        {'universe_id': 'malmo-disk', 'snapshot_ids': ['malmo-new']}))
    env = c.env | {'REFRESH_CITY': 'Malmö', 'REFRESH_POSTAL_CODE': '21120',
                   'DEMAND_REFRESH_STATE_PATH': str(municipal),
                   'PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS': ''}
    requests = []

    def request(url):
        path, query = urlsplit(url).path, parse_qs(urlsplit(url).query)
        requests.append((path, query))
        if path == '/ready' and query == {'postal_code': ['21120']}:
            return {'http_status': 503, 'body': {'status': 'not_ready'}}
        if path == '/api/price-universe/status' and query == {'city': ['Malmö']}:
            return {'http_status': 200, 'body': {'universe_id': 'malmo-old', 'snapshot_ids': ['old']}}
        return {'http_status': 200, 'body': {'universe_id': 'lund-ready', 'snapshot_ids': ['malmo-new']}}

    monkeypatch.setattr(ops, 'request_json', request)
    result = ops.status(env, now=datetime(2026, 10, 8, 14, tzinfo=UTC))
    assert result['disk_manifest'] == 'malmo-disk'
    assert result['loaded_manifest'] == 'malmo-old'
    assert result['ready']['http_status'] == 503
    assert len(result['required_contexts']) == 1
    row = result['required_contexts'][0]
    assert row['context_id'] == 'context:willys:malmo'
    assert row['published'] and not row['loaded']
    assert requests == [('/ready', {'postal_code': ['21120']}),
                        ('/api/price-universe/status', {'city': ['Malmö']})]


@pytest.mark.parametrize('source_case', ['approved', 'missing', 'wrong_store', 'wrong_snapshot', 'unreadable'])
def test_citygross_status_follows_verified_municipal_database(context, monkeypatch, source_case):
    from grocery_data.app.services import citygross_municipal_job

    c = context
    snapshot(c, 'municipal-cg', state='promoted', chain='citygross')
    with sqlite3.connect(c.database) as db:
        db.execute('INSERT INTO source_products VALUES (?,?,?,?)',
                   ('municipal-cg', 'citygross', '3211', '2026-10-08T12:00:00+00:00'))
    external = c.database.with_name('municipal-own.sqlite')
    external.write_bytes(c.database.read_bytes())
    with sqlite3.connect(c.database) as db:
        db.execute('DELETE FROM source_products')
        db.execute('DELETE FROM catalog_snapshots')
    source = {'database': external, 'store_ids': ['3211'], 'snapshot_ids': ['municipal-cg']}
    if source_case == 'wrong_store':
        source['store_ids'] = ['other-store']
    if source_case == 'wrong_snapshot':
        source['snapshot_ids'] = ['not-approved']
    if source_case == 'unreadable':
        source['database'] = c.database.with_name('missing.sqlite')
    monkeypatch.setattr(citygross_municipal_job, 'source_inputs', lambda **kwargs: {
        'citygross_municipal_enabled': True,
        'citygross_sources': [] if source_case == 'missing' else [source]})
    (c.root/'demand-refresh.json').write_text(json.dumps({'base_scope': [{
        'store_id': 'context:citygross:malmo', 'chain': 'citygross',
        'source_provenance': {'provider_store_id': '3211'}}]}))
    (c.universe/'active/city-malmö.json').write_text(json.dumps({
        'universe_id': 'current', 'snapshot_ids': ['municipal-cg']}))
    monkeypatch.setattr(ops, 'request_json', lambda url: {'http_status': 200,
        'body': {'universe_id': 'current', 'snapshot_ids': ['municipal-cg']}})
    before = (c.database.read_bytes(), external.read_bytes())
    result = ops.status(c.env | {'REFRESH_CITY': 'Malmö',
                                'PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS': ''},
                        now=datetime(2026, 10, 8, 14, tzinfo=UTC))
    item = result['required_contexts'][0]
    if source_case == 'approved':
        assert item['qualified'] and item['published'] and item['loaded']
        assert item['snapshot_id'] == 'municipal-cg' and item['freshness'] == 'FRESH'
        assert item['serving_source']['snapshot_id'] == 'municipal-cg'
    else:
        assert not item['qualified'] and item['stage'] == 'unknown'
    assert before == (c.database.read_bytes(), external.read_bytes())
    assert result['external_price_requests'] == 0


def test_pipeline_recovery_cannot_close_other_municipality(context, monkeypatch):
    value = {'checked_at': '2026-10-08T14:00:00+00:00', 'storage': {'adequate': True},
             'ready': {'http_status': 200}, 'disk_manifest': 'lund-ready',
             'loaded_manifest': 'lund-ready', 'unknown_required_contexts': [],
             'required_contexts': [{'context_id': 'lund', 'incident_ids': [],
                                    'loaded': True, 'freshness': 'FRESH'}]}
    monkeypatch.setattr(ops, 'status', lambda _: value)
    path = context.root / 'pipeline-incidents.json'
    path.write_text(json.dumps({'incidents': {
        'lund': {'scope': 'Lund', 'status': 'open'},
        'malmo': {'scope': 'Malmö', 'status': 'open'},
        'unknown': {'status': 'open'}}}))
    ops.record_indicators(context.env)
    rows = json.loads(path.read_text())['incidents']
    assert rows['lund']['status'] == 'recovered'
    assert rows['malmo']['status'] == rows['unknown']['status'] == 'open'
    assert 'verified_manifest' not in rows['malmo']


def test_disk_margin_warning(context, monkeypatch):
    monkeypatch.setattr(ops.shutil,'disk_usage',lambda _: SimpleNamespace(free=1))
    monkeypatch.setattr(ops,'request_json',lambda _: {'status':'unknown'})
    assert ops.status(context.env)['storage']['adequate'] is False


def test_changed_incident_repair_is_rejected_before_source_work(context, monkeypatch):
    from contextlib import nullcontext

    from deploy.scripts import run_daily_refresh as runner
    from grocery_data import ops as cli

    monkeypatch.setattr(runner,'_operations_lock',lambda: nullcontext())
    args=SimpleNamespace(incident_id='missing',signature='old',runtime='reviewed-test',action='retry',apply=True)
    with pytest.raises(ValueError,match='incident_identity_changed_or_missing'):
        cli.repair(args)


def test_index_size_bound_preserves_previous_file(context, monkeypatch):
    snapshot(context,'one')
    ops.record_incidents(context.env)
    path=context.root/'source-incidents.json'
    before=path.read_bytes()
    monkeypatch.setattr(ops,'MAX_INDEX_BYTES',10)
    with pytest.raises(ValueError,match='incident_index_size_exceeded'):
        ops.record_incidents(context.env)
    assert path.read_bytes()==before


def test_indicator_repetitions_and_recovery_are_transitions(context, monkeypatch):
    value={'checked_at':'2026-10-08T14:00:00+00:00','storage':{'adequate':False},'ready':{},
           'required_contexts':[], 'unknown_required_contexts':[]}
    monkeypatch.setattr(ops,'status',lambda _: value)
    for _ in range(3):
        ops.record_indicators(context.env)
    path=context.root/'drift-indicators.json'
    assert json.loads(path.read_text())['indicators']['storage_capacity']['occurrences']==1
    value['storage']['adequate']=True
    ops.record_indicators(context.env)
    assert not json.loads(path.read_text())['indicators']['storage_capacity']['active']
    value['storage']['adequate']=False
    ops.record_indicators(context.env)
    assert json.loads(path.read_text())['indicators']['storage_capacity']['occurrences']==2


def test_identical_schema_cannot_trigger_recrawl(context, monkeypatch):
    from contextlib import nullcontext

    from deploy.scripts import run_daily_refresh as runner
    from grocery_data import ops as cli

    snapshot(context,'one',metrics={'effective_schema_diff':{'added':['newPriceScope']}})
    index=ops.record_incidents(context.env)
    item=next(iter(index['incidents'].values()))
    monkeypatch.setattr(runner,'_operations_lock',lambda: nullcontext())
    monkeypatch.setattr(cli,'status',lambda: {'storage':{'adequate':True},'required_contexts':[]})
    args=SimpleNamespace(incident_id=item['incident_id'],signature=item['signature'],runtime='reviewed-test',action='retry',apply=True)
    with pytest.raises(ValueError,match='code_review_required_no_identical_schema_recrawl'):
        cli.repair(args)
    assert not (context.root/'incident-repairs.json').exists()


def test_unavailable_local_relay_is_unknown(tmp_path):
    import importlib.util

    spec=importlib.util.spec_from_file_location('smako_ops_local', Path(__file__).resolve().parents[2]/'scripts/smako_ops.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result=module.relay_status(tmp_path/'does-not-exist',tmp_path/'no-shell')
    assert result['status']=='unknown'


def test_schema_hold_clears_only_on_recovery(context):
    snapshot(context,'one',metrics={'effective_schema_diff':{'added':['newPriceScope']}})
    ops.record_incidents(context.env)
    assert set(ops.schema_holds(context.root))=={'hemkop'}
    snapshot(context,'two',state='promoted')
    ops.record_incidents(context.env)
    assert ops.schema_holds(context.root)=={}


def test_offer_schema_failure_does_not_hold_online_base(context):
    snapshot(context,'physical',metrics={'effective_schema_diff':{'added':['offerContract']}})
    with sqlite3.connect(context.database) as db:
        db.execute("UPDATE catalog_snapshots SET coverage='offers_only'")
    ops.record_incidents(context.env)
    assert ops.schema_holds(context.root)=={}


def test_pipeline_error_keeps_stack_without_message_or_locals(context):
    try:
        raise TypeError('private credential must never be copied')
    except TypeError as exc:
        key=ops.record_pipeline_failure('price_universe_build',exc,scope='Lund')
    value=json.loads((context.root/'pipeline-incidents.json').read_text())['incidents'][key]
    assert value['error_type']=='TypeError' and value['frames']
    assert 'private credential' not in json.dumps(value)


def test_publish_refuses_incomplete_federation_and_duplicate_action(context, monkeypatch):
    from contextlib import nullcontext

    from deploy.scripts import run_daily_refresh as runner
    from grocery_data import ops as cli

    try:
        raise TypeError('builder failed')
    except TypeError as exc:
        key=ops.record_pipeline_failure('price_universe_build',exc,scope='Lund')
    incident=json.loads((context.root/'pipeline-incidents.json').read_text())['incidents'][key]
    args=SimpleNamespace(incident_id=key,signature=incident['signature'],runtime='reviewed-test',action='publish',apply=True)
    monkeypatch.setattr(runner,'_operations_lock',lambda: nullcontext())
    report={'storage':{'adequate':True},'required_contexts':[{'qualified':False,'chain':'hemkop'}],
            'unknown_required_contexts':[],'disk_manifest':'old'}
    monkeypatch.setattr(cli,'status',lambda: report)
    with pytest.raises(ValueError,match='mandatory_sources_not_qualified_and_fresh'):
        cli.repair(args)
    report['required_contexts'][0].update(qualified=True,freshness='FRESH')
    attempt=f'{key}:old:publish:reviewed-test'
    (context.root/'incident-repairs.json').write_text(json.dumps({'attempts':{attempt:{'status':'complete'}}}))
    with pytest.raises(ValueError,match='repair_already_attempted'):
        cli.repair(args)


def test_source_package_refuses_unrelated_or_ambiguous_base():
    import importlib.util

    spec=importlib.util.spec_from_file_location('source_packager', Path(__file__).resolve().parents[2]/'scripts/build_source_patch.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.transplant(b'old\n',b'old\n',b'new\n')==b'new\n'
    assert module.transplant(None,None,b'new\n')==b'new\n'
    with pytest.raises(ValueError,match='missing or ambiguous'):
        module.transplant(b'unrelated\n',b'old\n',b'new\n')
    with pytest.raises(ValueError,match='missing or ambiguous'):
        module.transplant(b'old\nold\n',b'old\n',b'new\n')


def test_busy_operation_does_not_write_incident_index(context, monkeypatch):
    from deploy.scripts import run_daily_refresh as runner

    monkeypatch.setenv('REFRESH_RUNNER_STATUS_PATH',str(context.root/'runner.json'))
    def must_not_run():
        pytest.fail('busy response must not write an index without a lease')
    monkeypatch.setattr(ops,'record_incidents',must_not_run)
    runner._write_status({'status':'degraded','runtime_reload':{'reason':'operation_lock_held'}})
    assert not (context.root/'source-incidents.json').exists()


def test_commercial_incident_identity_uses_actual_product_and_terms(context):
    metrics={'catalog_completion':{'4123':{'complete':False,'conflicting_duplicates':1}}}
    for sid, product in [('first','A'),('repeat','A'),('different','B')]:
        snapshot(context,sid,metrics=metrics)
        for n, offers in enumerate([[],[{'id':'member','price':12}]]):
            raw(context,sid,{'results':[{'code':product,'potentialPromotions':offers}]},name=f'{sid}-{n}.json',kind='catalog_page')
    items=ops.record_incidents(context.env)['incidents']
    assert len(items)==2
    assert sorted(i['occurrences'] for i in items.values())==[1,2]
    legacy={'schema':'source-incidents-v1','watermark':0,'incidents':{}}
    (context.root/'source-incidents.json').write_text(json.dumps(legacy))
    assert ops.record_incidents(context.env)['schema']=='source-incidents-v2'
    assert json.loads((context.root/'source-incidents-v1.json').read_text())==legacy
