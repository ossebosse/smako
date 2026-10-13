"""Interrupted traversal, fair turns, admission and loading-only regressions."""
import asyncio
import gzip
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from grocery_data.app.connectors.willys.connector import WillysConnector
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.services.catalog_checkpoint import CatalogCheckpoints, CollectionWindowEnded
from grocery_data.app.services.municipal_capacity import FIELDS, capacity_report
from grocery_data.app.services.municipal_scheduling import order_work, record_attempt
from grocery_data.app.services.source_artifact import verify_source_artifact
from grocery_data.tests.test_source_artifact import artifact


def setup_checkpoint(tmp_path):
    verified = verify_source_artifact(artifact(tmp_path))
    discovery = RawBatch(chain='willys', documents=tuple(d for d in verified.documents if d.kind == 'stores'))
    connector = WillysConnector()
    stores = connector.parse_stores(discovery, ['test:registry'], GeographicArea(city='Lund'))
    batches = {s.external_id: RawBatch(chain='willys',
        documents=tuple(d for d in verified.documents if d.store_external_id == s.external_id),
        catalog_completion=verified.completion[s.external_id]) for s in stores}
    def checkpoint(**kwargs):
        return CatalogCheckpoints(tmp_path / 'checkpoints', area=GeographicArea(city='Lund'),
            boundary=None, parser_version=connector.parser_version, **kwargs)
    asyncio.run(connector.aclose())
    return discovery, stores, batches, checkpoint


def test_resume_complete_store_after_peer_interrupt_preserves_observations(tmp_path):
    discovery, stores, batches, checkpoint = setup_checkpoint(tmp_path)
    calls = []
    async def fetch(store):
        calls.append(store.external_id)
        return batches[store.external_id]
    first = checkpoint()
    original = asyncio.run(first.fetch(stores[0], discovery, fetch))
    # A new process starts with an empty object after the first store completed.
    second = checkpoint()
    resumed = asyncio.run(second.fetch(stores[0], discovery, fetch))
    asyncio.run(second.fetch(stores[1], discovery, fetch))
    assert calls == [s.external_id for s in stores]
    assert resumed.documents == original.documents
    assert second.reused_requests == len(original.documents)
    assert resumed.transport.request_count == 0


@pytest.mark.parametrize('damage', ['hash', 'truncated', 'parser', 'expired'])
def test_bad_or_expired_checkpoint_is_never_reused(tmp_path, damage):
    discovery, stores, batches, checkpoint = setup_checkpoint(tmp_path)
    calls = []
    async def fetch(store):
        calls.append(store.external_id)
        return batches[store.external_id]
    first = checkpoint()
    asyncio.run(first.fetch(stores[0], discovery, fetch))
    path = first._path(stores[0])
    second = checkpoint()
    if damage == 'hash':
        saved = json.loads(gzip.decompress(path.read_bytes()))
        saved['sha256'] = '0' * 64
        path.write_bytes(gzip.compress(json.dumps(saved).encode()))
    elif damage == 'truncated':
        path.write_bytes(path.read_bytes()[:10])
    elif damage == 'parser':
        second.parser_version = 'changed'
    else:
        second.now = lambda: datetime.now(UTC) + timedelta(hours=25)
    if damage == 'expired':
        # New fetch is also old in this fixture; qualification still refuses it.
        with pytest.raises(ValueError, match='window'):
            asyncio.run(second.fetch(stores[0], discovery, fetch))
    else:
        asyncio.run(second.fetch(stores[0], discovery, fetch))
    assert len(calls) == 2 and second.reused_requests == 0


def test_window_defers_unstarted_store_and_partial_is_not_checkpointed(tmp_path):
    discovery, stores, batches, checkpoint = setup_checkpoint(tmp_path)
    async def forbidden(store):
        raise AssertionError('network request after window ended')
    cache = checkpoint(deadline=0)
    with pytest.raises(CollectionWindowEnded):
        asyncio.run(cache.fetch(stores[0], discovery, forbidden))
    assert cache.deferred and not list(cache.root.glob('*.gz'))
    async def partial(store):
        return batches[store.external_id].model_copy(update={'documents': batches[store.external_id].documents[:-1]})
    with pytest.raises(ValueError):
        asyncio.run(checkpoint().fetch(stores[0], discovery, partial))
    assert not list(cache.root.glob('*.gz'))


@pytest.mark.parametrize('code', ['1281', '1280'])
def test_municipal_resume_revalidates_geometry_and_complete_artifact(tmp_path, monkeypatch, code):
    from grocery_data.app.services.source_artifact import write_source_artifact
    from grocery_data.tests.test_willys_municipality import municipal_artifact

    verified = verify_source_artifact(municipal_artifact(tmp_path, monkeypatch, code))
    manifest = verified.manifest
    discovery = RawBatch(chain='willys', documents=tuple(d for d in verified.documents if d.kind == 'stores'))
    connector = WillysConnector(municipality_boundary=manifest.municipality_boundary)
    stores = connector.parse_stores(discovery, ['test:registry'], manifest.source_scope.geographic_area)
    stores.sort(key=lambda store: store.external_id)
    now = manifest.observed_to + timedelta(minutes=3)
    def checkpoint(boundary):
        return CatalogCheckpoints(tmp_path / 'municipal-cache', area=manifest.source_scope.geographic_area,
            boundary=boundary, parser_version=connector.parser_version, now=lambda: now)
    calls = []
    async def fetch(store):
        calls.append(store.external_id)
        return RawBatch(chain='willys', documents=tuple(d for d in verified.documents if d.store_external_id == store.external_id),
                        catalog_completion=verified.completion[store.external_id])
    first = checkpoint(manifest.municipality_boundary)
    for store in stores:
        asyncio.run(first.fetch(store, discovery, fetch))
    # A fresh boundary fetch with identical geometry must not invalidate the cache.
    second = checkpoint({**manifest.municipality_boundary, 'observed_at': now.isoformat()})
    docs = list(discovery.documents)
    for store in stores:
        docs.extend(asyncio.run(second.fetch(store, discovery, fetch)).documents)
    assert len(calls) == len(stores)
    assert tuple(docs) == verified.documents
    output = tmp_path / 'resumed.smako-source'
    write_source_artifact(manifest, tuple(docs), output)
    assert verify_source_artifact(output, now=now).manifest.observed_from == manifest.observed_from
    asyncio.run(connector.aclose())


def test_deadline_order_and_failed_scope_cannot_starve_waiting_peer():
    now = datetime.now(UTC)
    items = [{'municipality_code': '1281', 'deadline': (now + timedelta(hours=10)).isoformat()},
             {'municipality_code': '1280', 'deadline': (now + timedelta(hours=1)).isoformat()}]
    state = {}
    assert order_work(items, state, now=now)[0]['municipality_code'] == '1280'
    state['jobs']['1281']['waiting_since'] = (now - timedelta(hours=26)).isoformat()
    record_attempt(state, '1280', started=now, seconds=20, result=1)
    items[1]['deadline'] = (now - timedelta(days=2)).isoformat()
    assert order_work(items, state, now=now)[0]['municipality_code'] == '1281'


def evidence():
    return {**dict.fromkeys(FIELDS, 100), 'municipality_code': '1480', 'postal_code': '41110',
            'sources': ['willys'], 'pilot_complete': True, 'measured_at': datetime.now(UTC).isoformat(),
            'available_memory_bytes': 1000, 'available_cycle_seconds': 1000}


@pytest.mark.parametrize('failure', ['missing', 'disk', 'memory', 'cycle', 'scope', 'expired', 'nan'])
def test_admission_rejects_unknown_or_insufficient_capacity(failure):
    item = evidence()
    disk = 10**10
    if failure == 'missing': item.pop('backup_bytes')
    if failure == 'disk': disk = 1
    if failure == 'memory': item['available_memory_bytes'] = 1
    if failure == 'cycle': item['existing_cycle_seconds'] = 2000
    if failure == 'scope': item['municipality_code'] = '1280'
    if failure == 'expired': item['measured_at'] = (datetime.now(UTC) - timedelta(days=8)).isoformat()
    if failure == 'nan': item['peak_memory_bytes'] = float('nan')
    report = capacity_report(item, municipality='1480', postal_code='41110', sources=['willys'], free_bytes=disk)
    assert report['status'] == 'BLOCKED' and report['reasons']


def test_measured_admission_includes_restore_and_backup():
    report = capacity_report(evidence(), municipality='1480', postal_code='41110',
                             sources=['willys'], free_bytes=10**10)
    assert report['status'] == 'PASS'
    assert report['required_bytes'] == 875 + 512 * 1024**2


@pytest.mark.parametrize('loaded', [True, False])
def test_reload_retry_uses_exact_manifest_without_collection_or_build(tmp_path, monkeypatch, loaded):
    from deploy.scripts import run_daily_refresh as runner

    path = tmp_path / 'state.json'
    now = datetime.now(UTC)
    state = {'pending_runtime': {'universe_id': 'universe:malmo', 'fingerprint': 'same'}}
    plan = {'state': state, 'state_path': str(path), 'work_due': False, 'due_sources': [],
            'reasons': [], 'source_fingerprint': 'same'}
    manifest = SimpleNamespace(universe_id='universe:malmo', oldest_base_observed_at=now,
                               oldest_observed_at=now)
    monkeypatch.setenv('REFRESH_CITY', 'Malmö')
    monkeypatch.setattr(runner, 'demand_refresh_plan', lambda **k: plan)
    monkeypatch.setattr(runner, '_artifact_store', lambda: SimpleNamespace(read_active=lambda city: manifest,
                        resolve_active_artifact=lambda *a, **k: path))
    def reload():
        if not loaded: raise runner.RuntimeReloadUnavailable('test')
        return {'new_price_universe_id': manifest.universe_id}
    monkeypatch.setattr(runner, '_reload_runtime', reload)
    monkeypatch.setattr(runner, '_confirm_loaded_runtime', lambda value: None)
    monkeypatch.setattr(runner, '_run_locked', lambda *a, **k: pytest.fail('unnecessary rebuild'))
    statuses = []
    monkeypatch.setattr(runner, '_write_status', statuses.append)
    assert runner._run_demand_locked(object(), started_at=now) == (0 if loaded else 2)
    assert ('pending_runtime' in json.loads(path.read_bytes())) is not loaded
    assert statuses[-1]['build_reused']


def test_local_overview_joins_receipts_to_exact_municipality(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sys
    from pathlib import Path

    spec = importlib.util.spec_from_file_location('municipal_ops_test', Path(__file__).resolve().parents[2] / 'scripts/smako_ops.py')
    smako_ops = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smako_ops)

    report = {'municipalities': [
        {'municipality_code': code, 'operations': {'required_contexts': [
            {'source_artifact_sha256': code, 'loaded': code == '1281'}]}}
        for code in ('1281', '1280')]}
    monkeypatch.setattr(sys, 'argv', ['smako_ops.py', '--workspace', str(tmp_path / 'municipality-1281'), 'municipalities'])
    monkeypatch.setattr(smako_ops.subprocess, 'run', lambda *a, **k:
        SimpleNamespace(stdout=json.dumps(report), returncode=0))
    visited = []
    def local(root, pwsh):
        visited.append(root.name)
        return {'qualified': {'sha256': root.name.removeprefix('municipality-')}, 'pending_delivery': True}
    monkeypatch.setattr(smako_ops, 'relay_status', local)
    assert smako_ops.main() == 0
    rows = json.loads(capsys.readouterr().out)['municipalities']
    assert visited == ['municipality-1281', 'municipality-1280']
    assert [r['windows']['delivery_stage'] for r in rows] == ['imported_waiting_receipt', 'imported_waiting_publication']

@pytest.mark.parametrize('municipality,city', [('1281','Lund'), ('1280','Malmö'), ('1480','Göteborg')])
def test_pending_loaded_scope_is_acknowledged_without_reload(tmp_path, monkeypatch, municipality, city):
    from deploy.scripts import run_daily_refresh as runner
    path = tmp_path / (municipality + '.json')
    now = datetime.now(UTC)
    identity = 'universe:' + municipality
    state = {'pending_runtime': {'universe_id': identity, 'fingerprint': 'same'}}
    plan = {'state': state, 'state_path': str(path), 'work_due': False, 'due_sources': [],
            'reasons': [], 'source_fingerprint': 'same'}
    manifest = SimpleNamespace(universe_id=identity, oldest_base_observed_at=now, oldest_observed_at=now)
    monkeypatch.setenv('REFRESH_CITY', city)
    monkeypatch.setattr(runner, 'demand_refresh_plan', lambda **k: plan)
    monkeypatch.setattr(runner, '_artifact_store', lambda: SimpleNamespace(read_active=lambda c: manifest,
        resolve_active_artifact=lambda *a, **k: path))
    monkeypatch.setattr(runner, '_reload_runtime', lambda: pytest.fail('must preserve existing caches'))
    def confirm(value):
        assert value == identity
        return {'new_price_universe_id': identity, 'changed': False}
    monkeypatch.setattr(runner, '_confirm_loaded_runtime', confirm)
    monkeypatch.setattr(runner, '_run_locked', lambda *a, **k: pytest.fail('unnecessary collection'))
    monkeypatch.setattr(runner, '_write_status', lambda value: None)
    assert runner._run_demand_locked(object(), started_at=now) == 0
    assert 'pending_runtime' not in json.loads(path.read_bytes())


@pytest.mark.parametrize('code,city', [('1281', 'Lund'), ('1280', 'Malmö'), ('1480', 'Göteborg')])
def test_lost_municipal_receipt_is_acknowledged_without_recollection(tmp_path, monkeypatch, code, city):
    from deploy.scripts import run_daily_refresh as runner
    from grocery_data.app.services import coop_offer_job as coop

    now = datetime.now(UTC)
    monkeypatch.setenv('REFRESH_CITY', city)
    monkeypatch.setenv('COOP_MUNICIPAL_OFFERS_ROOT', str(tmp_path / 'coop'))
    monkeypatch.setenv('COOP_MUNICIPAL_OFFERS_ENABLED', 'true')
    monkeypatch.setenv('COOP_MUNICIPALITY_CODE', code)
    monkeypatch.setenv('COOP_MUNICIPAL_BUILD_CITY', city)
    root, cfg = coop.configuration()
    source_path = coop.location(root, cfg)
    failed_store = {'store_id': 'test-store', 'selected': True, 'concept': 'Coop',
                    'failed_attempts': 14, 'status': 'failed', 'last_success': None,
                    'next_fetch_at': (now + timedelta(hours=6)).isoformat()}
    source = {'selection': {'stores': [failed_store],
                           'next_inventory_check': (now + timedelta(days=1)).isoformat()}}
    coop.write(source_path, source)
    fingerprint = coop.source_plan(now=now)['fingerprint']
    identity = 'universe:' + code
    source.update(built={'universe_id': identity, 'fingerprint': fingerprint},
                  publication={'status': 'publication_or_reload_pending',
                               'retry_at': (now - timedelta(minutes=1)).isoformat()})
    coop.write(source_path, source)
    scoped = coop.source_plan(now=now)
    assert scoped['publication_due'] and not scoped['inventory_due'] and not scoped['due_store_ids']
    path = tmp_path / 'runner.json'
    state = {'pending_runtime': {'universe_id': identity, 'fingerprint': 'same'}}
    plan = {'state': state, 'state_path': str(path), 'work_due': True, 'due_sources': [],
            'reasons': ['coop_municipal_work_due'], 'source_fingerprint': 'same', 'coop_municipal': scoped}
    monkeypatch.setattr(runner, 'demand_refresh_plan', lambda **kwargs: plan)
    manifest = SimpleNamespace(universe_id=identity, oldest_base_observed_at=now, oldest_observed_at=now)
    monkeypatch.setattr(runner, '_artifact_store', lambda: SimpleNamespace(
        read_active=lambda city: manifest, resolve_active_artifact=lambda *args, **kwargs: path))
    monkeypatch.setattr(runner, '_confirm_loaded_runtime', lambda expected: {'new_price_universe_id': expected})
    monkeypatch.setattr(runner, '_reload_runtime', lambda: pytest.fail('already loaded'))
    monkeypatch.setattr(runner, '_run_locked', lambda *args, **kwargs: pytest.fail('unnecessary source/build work'))
    monkeypatch.setattr(runner, '_write_status', lambda value: None)
    assert runner._run_demand_locked(object(), started_at=now) == 0
    assert 'pending_runtime' not in json.loads(path.read_bytes())
    after = coop.read(source_path)
    assert after['publication']['status'] == 'reloaded'
    assert after['publication']['reloaded_fingerprint'] == fingerprint
    assert after['selection']['stores'] == [failed_store]
    assert not coop.source_plan(now=now)['work_due']


@pytest.mark.parametrize('reason,extra', [
    ('campaign_transition', {}), ('source_promotion_pending_publication', {}),
    ('ica_source_due', {}), ('hemkop_municipal_work_due', {}),
    ('coop_municipal_work_due', {'due_store_ids': ['3833']}),
    ('coop_municipal_work_due', {'inventory_due': True}),
    ('coop_municipal_work_due', {'publication_due': False}),
])
def test_publication_retry_never_suppresses_real_source_work(reason, extra):
    from deploy.scripts.run_daily_refresh import _runtime_publication_only
    plan = {'reasons': [reason], 'coop_municipal': {'publication_due': True,
            'due_store_ids': [], 'inventory_due': False, **extra}}
    assert not _runtime_publication_only(plan)
