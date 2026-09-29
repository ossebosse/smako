import json
from datetime import UTC, datetime, timedelta

import pytest

from grocery_data.app.domain import GeographicArea
from grocery_data.app.services.area_membership import collection_area
from grocery_data.app.services.ica_offer_job import (
    run_structured_offer_job,
    structured_source_inputs,
)
from grocery_data.tests.test_municipality_area import stores


def test_explicit_scope_survives_restart_and_does_not_cross_municipalities(tmp_path):
    env = {'MUNICIPAL_COLLECTION_SCOPE_PATH': str(tmp_path / 'scope.json'), 'REFRESH_MUNICIPALITY_CODE': '1281'}
    assert collection_area('Lund', environment=env, persist=True).municipality_code == '1281'
    with pytest.raises(ValueError, match='does not match'):
        collection_area('Malmö', environment=env)
    env.pop('REFRESH_MUNICIPALITY_CODE')
    assert collection_area('Lund', environment=env).municipality_code == '1281'
    assert collection_area('Malmö', environment=env).mode == 'locality'
    env['REFRESH_MUNICIPALITY_CODE'] = '1280'
    assert collection_area('Malmö', environment=env, persist=True).municipality_code == '1280'
    env.pop('REFRESH_MUNICIPALITY_CODE')
    assert collection_area('Lund', environment=env).municipality_code == '1281'


async def test_ica_optional_rows_use_verified_municipality_without_claiming_complete_inventory(tmp_path, monkeypatch):
    monkeypatch.setenv('MUNICIPAL_COLLECTION_SCOPE_PATH', str(tmp_path / 'scope.json'))
    monkeypatch.setenv('REFRESH_MUNICIPALITY_CODE', '1281')
    now = datetime(2026, 9, 28, 9, tzinfo=UTC)
    called = []
    async def collect(area, output, **kwargs):
        called.append(area)
        return {'area': area.model_dump(mode='json'),
            'inventory': {'complete': True, 'municipality_complete': False},
            'stores': [{'store': s.model_dump(mode='json'), 'ica_account_id': s.external_id,
                'area_membership': 'inside', 'area_reason': 'verified_address_municipality_matches',
                'collection_status': 'success', 'last_success_at': now.isoformat(),
                'campaign_windows': [{'valid_to': '2026-10-04'}],
                'row_approved_result': {'published': True, 'acceptance': {'shared_blockers': []}}}
                for s in stores('1281')]}
    first = await run_structured_offer_job(city='Lund', root=tmp_path / 'ica', now=now, collect=collect)
    assert not first['inventory_approved']
    inputs = structured_source_inputs(city='Lund', root=tmp_path / 'ica')
    assert {'Genarp', 'Veberöd', 'Södra Sandby'} <= {s.city for s in inputs['ica_municipal_stores'].values()}
    monkeypatch.delenv('REFRESH_MUNICIPALITY_CODE')
    again = await run_structured_offer_job(city='Lund', root=tmp_path / 'ica', now=now+timedelta(hours=1), collect=collect)
    assert len(called) == 1 and called[0] == GeographicArea(city='Lund', mode='municipality', municipality_code='1281')
    assert again['status'] == 'not_due' and again['database'] == first['database']
    assert again['observed_at'] == first['observed_at']
    pointer = tmp_path / 'ica/1281/structured-source.json'
    changed = json.loads(pointer.read_bytes())
    changed['coverage']['area']['municipality_code'] = '1280'
    pointer.write_text(json.dumps(changed), encoding='utf-8')
    assert structured_source_inputs(city='Lund', root=tmp_path / 'ica') == {}


async def test_failed_inventory_preserves_approved_municipal_source_and_age(tmp_path, monkeypatch):
    monkeypatch.setenv('MUNICIPAL_COLLECTION_SCOPE_PATH', str(tmp_path / 'scope.json'))
    monkeypatch.setenv('REFRESH_MUNICIPALITY_CODE', '1281')
    now = datetime(2026, 9, 28, 9, tzinfo=UTC)
    async def collect(area, output, **kwargs):
        return {'area': area.model_dump(mode='json'), 'inventory': {'complete': True},
            'stores': [{'store': s.model_dump(mode='json'), 'ica_account_id': s.external_id,
                'area_membership': 'inside', 'collection_status': 'success',
                'last_success_at': now.isoformat(), 'campaign_windows': [{'valid_to': '2026-10-04'}],
                'row_approved_result': {'published': True, 'acceptance': {'shared_blockers': []}}}
                for s in stores('1281')]}
    root = tmp_path / 'ica'
    first = await run_structured_offer_job(city='Lund', root=root, now=now, collect=collect)
    async def failed(area, output, **kwargs):
        return {'inventory_error': 'ConnectionError', 'inventory': {'complete': False}, 'stores': []}
    later = now + timedelta(minutes=10)
    result = await run_structured_offer_job(city='Lund', root=root, now=later, force=True, collect=failed)
    assert result['status'] == 'inventory_failed_lkg_retained'
    after = json.loads((root / '1281/structured-source.json').read_bytes())
    for key in ['database', 'coverage', 'observed_at', 'ica_offer_store_ids']:
        assert after[key] == first[key]
    assert after['next_inventory_at'] == (later + timedelta(minutes=30)).isoformat()
    assert structured_source_inputs(city='Lund', root=root)['ica_offer_store_ids']
    assert (await run_structured_offer_job(city='Lund', root=root, now=later, collect=failed))['status'] == 'not_due'
