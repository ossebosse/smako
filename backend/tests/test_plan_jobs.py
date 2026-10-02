"""Async transport contracts; injected work is not public acceptance evidence."""
import asyncio
from threading import Event

import pytest
from app.api import plan as api
from app.config import Settings
from app.main import app
from fastapi import HTTPException
from fastapi.testclient import TestClient


def test_async_plan_returns_before_work_finishes_and_preserves_failure(monkeypatch, tmp_path):
    from app import main

    settings = Settings(price_provider='mock', plan_store_path=tmp_path/'plans.sqlite3')
    monkeypatch.setattr(api, 'get_settings', lambda: settings)
    monkeypatch.setattr(main, 'get_settings', lambda: settings)
    release = Event()
    started = Event()
    calls = []

    async def slow(request, *_):
        calls.append(request)
        started.set()
        await asyncio.to_thread(release.wait, 1)
        raise HTTPException(503, 'unavailable', headers={'X-Error-Code': 'price_universe_unusable'})

    monkeypatch.setattr(api, '_run_admitted_plan', slow)
    try:
        with TestClient(app) as client:
            response = client.post('/api/plans', headers={'Prefer': 'respond-async'}, json={
                'recipes': 5, 'servings': 2, 'max_stores': 3, 'purchase_planning_mode': 'exact',
            })
            assert response.status_code == 202
            assert started.wait(2)
            status_url = response.json()['status_url']
            assert status_url.startswith('/api/plan-jobs/')
            assert client.get(status_url).status_code == 202
            duplicate = client.post('/api/plans', headers={'Prefer': 'respond-async'}, json={
                'recipes': 5, 'servings': 2, 'max_stores': 3, 'purchase_planning_mode': 'exact',
            })
            assert duplicate.json()['status_url'] == status_url
            assert len(calls) == 1
            # A different owner cannot poll or receive the result.
            forbidden = client.get(status_url, headers={'X-Anonymous-Session-ID': 'another-isolated-session-12345'})
            assert forbidden.status_code == 404
            release.set()
            import time
            for _ in range(100):
                final = client.get(status_url)
                if final.status_code != 202:
                    break
                time.sleep(.01)
            assert final.status_code == 503
            assert final.headers['x-error-code'] == 'price_universe_unusable'
            assert calls[0].servings == 2 and calls[0].max_stores == 3
            assert calls[0].purchase_planning_mode == 'exact'
    finally:
        release.set()


@pytest.mark.asyncio
async def test_jobs_are_bounded_owned_and_completed_transport_expires(monkeypatch):
    from app.services import plan_jobs

    now = [100.0]
    monkeypatch.setattr(plan_jobs, 'monotonic', lambda: now[0])
    jobs = plan_jobs.PlanJobs(max_pending=1, max_retained=2, retention=10)
    release = asyncio.Event()

    async def work():
        await release.wait()
        return 'saved-result'

    first = jobs.start('owner', 'input-key', 'request-1', work)
    assert jobs.start('owner', 'input-key', 'request-2', work) is first
    assert jobs.get(first.job_id, 'stranger') is None
    with pytest.raises(plan_jobs.PlanJobsFull):
        jobs.start('stranger', 'other-key', 'request-3', work)
    now[0] = 200
    assert jobs.get(first.job_id, 'owner') is first  # Pending work is never evicted.
    release.set()
    assert await first.task == 'saved-result'
    await asyncio.sleep(0)
    now[0] = 211
    assert jobs.get(first.job_id, 'owner') is None
    await jobs.close()
