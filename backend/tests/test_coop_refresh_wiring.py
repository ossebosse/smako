"""Ordinary entrypoint forwarding and publication acknowledgement boundaries."""
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from grocery_data.app.services import coop_offer_job as job


async def test_every_ordinary_build_reads_durable_optional_sources(tmp_path, monkeypatch):
    from app.services import production_price_universe_build as builder

    from grocery_data import __main__ as cli
    source = tmp_path / "base.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE complete_base(id)")
        db.execute("INSERT INTO complete_base VALUES ('preserved')")
    seen = []
    async def build(database, *args, **kwargs):
        with closing(sqlite3.connect(database)) as db:
            assert db.execute("SELECT id FROM complete_base").fetchone()[0] == "preserved"
        seen.append(kwargs)
        return {"price_universe_id": "built", "snapshot_ids": []}
    monkeypatch.setattr(builder, "build_city_price_universe", build)
    expected = {"coop_offer_sources": [{"database": "approved-own", "inventory": {"municipality_code": "1281"}}]}
    monkeypatch.setattr(job, "source_inputs", lambda **k: expected)
    monkeypatch.setattr(job, "record_build", lambda **k: None)
    for _ in range(2):
        await cli._build_production_price_universe(database=source, city="Lund", postal_code="22350",
            external_cache=None, output=tmp_path / "candidate.json", max_price_age_hours=48)
    assert seen == [expected, expected]


@pytest.mark.parametrize("failure", ["reload_rejected", "reload_unavailable", "publication_failed", "success"])
def test_ordinary_locked_wrapper_records_actual_reload(tmp_path, monkeypatch, failure):
    from backend.tests.test_production_deployment import (
        _configure_refresh_runner,
        _FakeArtifactStore,
    )
    from deploy.scripts import run_daily_refresh as runner
    from grocery_data.app.services.prepared_universe_activation import (
        ActivePreparedUniverseManifest,
    )

    now = datetime.now(UTC)
    store = _FakeArtifactStore()
    previous = ActivePreparedUniverseManifest(city='Lund', scope_id='city:lund', universe_id='base',
        built_at=now, activated_at=now, oldest_observed_at=now, snapshot_ids=('source',), product_count=1,
        canonical_index_count=1, artifact_file='artifacts/'+'a'*64+'.json', artifact_sha256='a'*64, artifact_bytes=100).model_dump_json().encode()
    store.active = previous
    statuses = _configure_refresh_runner(monkeypatch, store, tmp_path)
    monkeypatch.delenv('DEMAND_REFRESH_ENABLED', raising=False)
    monkeypatch.setenv('COOP_MUNICIPAL_OFFERS_ENABLED', 'true')
    monkeypatch.setenv('COOP_MUNICIPALITY_CODE', '1281')
    monkeypatch.setenv('COOP_MUNICIPAL_OFFERS_ROOT', str(tmp_path/'sources'))
    root, config = job.configuration()
    path = job.location(root, config)
    job.write(path, {'selection': {'stores': [], 'next_inventory_check': (now+timedelta(days=3)).isoformat()}})
    job.record_build(city='Lund', result={'price_universe_id': 'new', 'snapshot_ids': ['snapshot']})
    monkeypatch.setattr(runner, '_active_disk_universe_id', lambda *a, **kw: 'new' if store.active == b'promoted-manifest' else 'base')
    if failure == 'publication_failed':
        monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=1))
    def reload():
        if failure == 'reload_rejected':
            raise runner.RuntimeReloadRejected('injected')
        if failure == 'reload_unavailable':
            raise runner.RuntimeReloadUnavailable('injected')
        return {'old_price_universe_id': 'base', 'new_price_universe_id': 'new', 'changed': True}
    monkeypatch.setattr(runner, '_reload_runtime', reload)
    code = runner.main()
    record = job.read(path)['publication']
    assert bool(record.get('last_reload_at')) == (failure == 'success')
    assert code == {'success': 0, 'publication_failed': 1, 'reload_rejected': 1, 'reload_unavailable': 2}[failure]
    if failure in {'publication_failed', 'reload_rejected'}:
        assert store.active == previous
        assert not record.get('last_published_at')
    if failure == 'reload_unavailable':
        assert record['last_published_at'] and not record.get('last_reload_at')
    assert statuses[-1]['exit_code'] == code


def test_invalid_optional_configuration_cannot_stop_base(tmp_path):
    env = {'COOP_MUNICIPAL_OFFERS_ENABLED': 'true', 'COOP_MUNICIPALITY_CODE': 'not-a-code',
           'COOP_MUNICIPAL_OFFERS_ROOT': str(tmp_path)}
    assert not job.source_plan(environment=env)['work_due']
    assert job.source_inputs(city='Lund', environment=env)['coop_offer_source_errors'][0]['status'] == 'optional_configuration_error'
