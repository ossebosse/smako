from datetime import UTC, datetime, timedelta

import pytest

from deploy.scripts.start_cron import _validate_display_schedule
from grocery_data.app.services.campaign_refresh_policy import (
    STOCKHOLM,
    base_fetch_due,
    campaign_schedule,
    collection_slots,
    scheduled_source_times,
)
from grocery_data.app.services.freshness import next_scheduled_refresh

ENV = {'PRICE_COLLECTION_CADENCE': 'mon_thu'}


def local(day, hour=3, minute=17):
    return datetime.fromisoformat(f'{day}T{hour:02}:{minute:02}:00').replace(tzinfo=STOCKHOLM)


@pytest.mark.parametrize('start,end,hours', [
    ('2026-10-22', '2026-10-26', 97),
    ('2027-03-25', '2027-03-29', 95),
    ('2026-10-26', '2026-10-29', 72),
])
def test_civil_time_slots_across_dst(start, end, hours):
    previous, following = collection_slots(local(start))
    assert previous == local(start)
    assert following == local(end)
    assert (following - previous).total_seconds() == hours * 3600


def test_base_sources_wait_for_each_collection_night_without_changing_observation():
    observed = local('2026-10-26', 4)
    monday = observed.isoformat()
    for now in [local('2026-10-27', 8), local('2026-10-28', 23), local('2026-10-29', 3, 16)]:
        assert base_fetch_due(observed, now=now, campaign_at=now, environment=ENV) == local('2026-10-29')
        assert base_fetch_due(None, now=now, environment=ENV) == local('2026-10-29')
    now = local('2026-10-29')
    assert base_fetch_due(observed, now=now, environment=ENV) == now
    assert base_fetch_due(now + timedelta(minutes=1), now=now + timedelta(minutes=2), environment=ENV) == local('2026-11-02')
    assert observed.isoformat() == monday
    # A failed night has bounded recovery; no daytime fetch loop.
    assert base_fetch_due(observed, now=local('2026-10-29', 6, 17), environment=ENV) == local('2026-11-02')


def test_campaign_boundaries_stay_local_while_network_waits(monkeypatch):
    monkeypatch.setenv('PRICE_COLLECTION_CADENCE', 'mon_thu')
    now = local('2026-10-26', 4)
    windows = [{'valid_from': '2026-10-26', 'valid_to': '2026-10-27'}]
    result = campaign_schedule(windows, now=now)
    assert datetime.fromisoformat(result['next_fetch_at']) == local('2026-10-29')
    assert datetime.fromisoformat(result['next_transition_at']) == local('2026-10-28', 0, 0)
    assert windows[0]['valid_to'] == '2026-10-27'
    result = campaign_schedule([], now=local('2026-10-28', 12), failed_attempts=4)
    assert datetime.fromisoformat(result['next_fetch_at']) == local('2026-10-29')


def test_legacy_offer_timers_migrate_and_backoff_is_preserved():
    rows = [{'last_success': local('2026-10-26', 4).isoformat(),
             'next_fetch_at': local('2026-10-27', 15).isoformat()}]
    now = local('2026-10-28', 12)
    inventory = scheduled_source_times(rows, state={}, now=now, environment=ENV)
    assert inventory == local('2026-10-29')
    assert datetime.fromisoformat(rows[0]['next_fetch_at']) == inventory
    now = local('2026-10-29')
    rows[0].update(failed_attempts=1, next_fetch_at=(now + timedelta(minutes=15)).isoformat())
    scheduled_source_times(rows, state={}, now=now, environment=ENV)
    assert datetime.fromisoformat(rows[0]['next_fetch_at']) == now + timedelta(minutes=15)


def test_cron_and_admin_projection_agree():
    display = '03:17 Europe/Stockholm Mon,Thu'
    _validate_display_schedule('17 03 * * 1,4', display, name='DAILY_REFRESH_SCHEDULE')
    with pytest.raises(ValueError):
        _validate_display_schedule('17 03 * * *', display, name='DAILY_REFRESH_SCHEDULE')
    assert next_scheduled_refresh(display, now=local('2026-10-29', 4)) == local('2026-11-02').astimezone(UTC)


@pytest.mark.parametrize('name', ['coop_offer_job', 'willys_flyer_job',
                                  'citygross_municipal_job', 'lidl_municipal_job'])
def test_every_municipal_offer_plan_uses_the_same_nights(name, monkeypatch, tmp_path):
    from importlib import import_module

    module = import_module('grocery_data.app.services.' + name)
    config = {'enabled': True, 'xtra_enabled': True, 'municipality_code': '1281', 'city': 'Lund'}
    row = {'store_id': 'verified', 'selected': True, 'concept': 'Coop',
           'last_success': local('2026-10-26', 4).isoformat(),
           'next_fetch_at': local('2026-10-27', 15).isoformat()}
    state = {'selection': {'stores': [row], 'next_inventory_check': local('2026-10-28').isoformat()},
             'inventory_status': {'checked_at': local('2026-10-26', 4).isoformat()}}
    monkeypatch.setattr(module, 'configuration', lambda *args: (tmp_path, config))
    monkeypatch.setattr(module, 'read', lambda *args: state)
    midweek = module.source_plan(environment=ENV, now=local('2026-10-28', 12))
    assert not midweek['due_store_ids'] and not midweek['inventory_due']
    thursday = module.source_plan(environment=ENV, now=local('2026-10-29'))
    assert thursday['due_store_ids'] == ['verified'] and thursday['inventory_due']
    assert row['last_success'] == local('2026-10-26', 4).isoformat()


def test_ica_job_cannot_fetch_outside_collection_night(monkeypatch, tmp_path):
    import asyncio

    from grocery_data.app.domain import GeographicArea
    from grocery_data.app.services import ica_offer_job

    monkeypatch.setenv('PRICE_COLLECTION_CADENCE', 'mon_thu')
    monkeypatch.setattr(ica_offer_job, 'source_location',
                        lambda *args, **kwargs: (GeographicArea(city='Lund'), tmp_path))

    async def forbidden(*args, **kwargs):
        raise AssertionError('No retailer request allowed on Wednesday')

    result = asyncio.run(ica_offer_job.run_structured_offer_job(
        city='Lund', root=tmp_path, now=local('2026-10-28', 12), collect=forbidden))
    assert result['status'] == 'not_due' and result['network_requests'] == 0


def test_primat_is_planned_before_ica_enters_the_active_artifact(monkeypatch, tmp_path):
    import json
    import sqlite3
    from types import SimpleNamespace

    from app.services import production_primat_refresh

    from deploy.scripts import run_daily_refresh as runner

    db = tmp_path / 'source.sqlite'
    with sqlite3.connect(db) as connection:
        connection.executescript('CREATE TABLE catalog_snapshots(id,state,is_active,coverage,promoted_at); '
                                 'CREATE TABLE source_products(catalog_snapshot_id,chain,store_external_id,fetched_at);')
        connection.execute("INSERT INTO catalog_snapshots VALUES ('one','promoted',1,'full_catalog',?)",
                           (local('2026-10-26', 4).isoformat(),))
        connection.execute("INSERT INTO source_products VALUES ('one','hemkop','verified',?)",
                           (local('2026-10-26', 4).isoformat(),))
    artifact = tmp_path / 'artifact.json'
    artifact.write_text(json.dumps({'stores': [{'store_id': 'context:verified', 'chain': 'hemkop',
        'source_provenance': {'source_provider': 'own', 'source_channel': 'catalog', 'provider_store_id': 'verified'}}]}))

    class Store:
        def __init__(self, *args): pass
        def read_active(self, *args): return SimpleNamespace(universe_id='own-only')
        def resolve_active_artifact(self, *args, **kwargs): return artifact

    monkeypatch.setattr(runner, 'PreparedUniverseArtifactStore', Store)
    monkeypatch.setattr(production_primat_refresh, 'plan_city_primat_refresh',
                        lambda *args: {'contexts': ['verified-ica']})
    env = ENV | {'PRICE_UNIVERSE_CACHE_ROOT': str(tmp_path / 'pu'),
                 'GROCERY_DATABASE_URL': 'sqlite:///' + db.as_posix(),
                 'DEMAND_REFRESH_STATE_PATH': str(tmp_path / 'state.json'),
                 'ICA_PRIMAT_BASE_ENABLED': 'true'}
    waiting = runner.demand_refresh_plan(now=local('2026-10-28', 12), environment=env)
    assert 'primat' in waiting['sources'] and not waiting['due_sources']
    due = runner.demand_refresh_plan(now=local('2026-10-29'), environment=env)
    assert set(due['due_sources']) == {'primat', 'hemkop'}
    monkeypatch.setattr(production_primat_refresh, 'plan_city_primat_refresh',
                        lambda *args: {'contexts': []})
    assert 'primat' not in runner.demand_refresh_plan(now=local('2026-10-29'), environment=env)['sources']


def test_hemkop_empty_scope_waits_without_inventory_or_network(monkeypatch, tmp_path):
    import asyncio

    from grocery_data.app.domain import GeographicArea
    from grocery_data.app.services import hemkop_municipal_job

    area = GeographicArea(city='Lund', mode='municipality', municipality_code='1281')
    monkeypatch.setenv('PRICE_COLLECTION_CADENCE', 'mon_thu')
    monkeypatch.setattr(hemkop_municipal_job, 'configuration',
                        lambda *args, **kwargs: (area, tmp_path, True))
    result = asyncio.run(hemkop_municipal_job.run_source_job(now=local('2026-10-28', 12)))
    assert result['status'] == 'not_due' and result['external_price_requests'] == 0
