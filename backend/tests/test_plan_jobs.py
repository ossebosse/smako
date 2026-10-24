"""Async transport contracts; injected work is not public acceptance evidence."""
import asyncio
from threading import Event

import pytest
from app.api import plan as api
from app.config import Settings
from app.main import app
from fastapi import HTTPException
from fastapi.testclient import TestClient


@pytest.mark.parametrize("kind,status,code", [("policy",422,"RECIPE_CHOICES_CONFLICT"),
                                             ("revision",409,"REVISION_CONFLICT")])
def test_retained_domain_failure_keeps_direct_http_contract(monkeypatch,tmp_path,kind,status,code):
    import time

    from app import main
    from app.services.personal_policy import PolicyConflict
    from app.services.personal_store import PersonalConflict

    settings=Settings(price_provider="mock",plan_store_path=tmp_path/"plans.sqlite3")
    monkeypatch.setattr(api,"get_settings",lambda:settings)
    monkeypatch.setattr(main,"get_settings",lambda:settings)
    calls=[]
    async def blocked(*args):
        calls.append(True)
        if kind=="policy":
            raise PolicyConflict("Omöjligt måltidsval",code=code,diagnostics={"bounded":True})
        raise PersonalConflict("Senaste revision är bevarad")
    monkeypatch.setattr(api,"_run_admitted_plan",blocked)
    with TestClient(app,raise_server_exceptions=False) as client:
        accepted=client.post("/api/plans",headers={"Prefer":"respond-async","X-Request-ID":"domain-"+kind},json={"recipes":3,"servings":2})
        assert accepted.status_code==202
        url=accepted.json()["status_url"]
        for _ in range(100):
            result=client.get(url)
            if result.status_code!=202:break
            time.sleep(.01)
        assert result.status_code==status
        assert result.json()["code"]==code
        assert result.headers["cache-control"]=="private, no-store"
        assert result.headers["x-plan-request-id"]=="domain-"+kind
        assert len(calls)==1
        for _ in range(3):
            again=client.get(url)
            assert again.status_code==status and again.json()==result.json()
        assert client.delete(url).status_code == 409
        assert client.get(url,headers={"X-Anonymous-Session-ID":"separate-domain-reader-12345"}).status_code==404


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
            response = client.post('/api/plans', headers={'Prefer': 'respond-async', 'X-Request-ID': 'lost-response-1'}, json={
                'recipes': 3, 'servings': 2, 'max_stores': 3, 'purchase_planning_mode': 'exact',
            })
            assert response.status_code == 202
            assert started.wait(2)
            status_url = response.json()['status_url']
            assert status_url.startswith('/api/plan-jobs/')
            assert client.get(status_url).status_code == 202
            recovery = client.get('/api/plan-job-requests/lost-response-1')
            assert recovery.status_code == 202 and recovery.json()['status_url'] == status_url
            assert client.get('/api/plan-job-requests/lost-response-1', headers={
                'X-Anonymous-Session-ID': 'another-isolated-session-12345'}).status_code == 404
            assert client.get('/api/plan-job-requests/missing').status_code == 404
            duplicate = client.post('/api/plans', headers={'Prefer': 'respond-async'}, json={
                'recipes': 3, 'servings': 2, 'max_stores': 3, 'purchase_planning_mode': 'exact',
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
            for _ in range(3):
                again = client.get(status_url)
                assert again.status_code == 503 and again.json() == final.json()
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
    assert jobs.by_request('request-2', 'owner') is first
    assert jobs.by_request('request-2', 'stranger') is None
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
    assert jobs.by_request('request-2', 'owner') is None
    assert plan_jobs.PlanJobs(max_pending=1).by_request('request-1', 'owner') is None
    await jobs.close()


@pytest.mark.asyncio
async def test_retained_failure_releases_planner_locals_without_losing_error():
    import gc
    import weakref

    from app.services.plan_jobs import PlanJobs

    class PlannerState:
        pass

    references = []

    async def work():
        state = PlannerState()
        references.append(weakref.ref(state))
        try:
            raise ValueError('original data gap')
        except ValueError as cause:
            raise HTTPException(422, {'code': 'DATA_BLOCKED', 'missing': ['edible_g']},
                                headers={'X-Error-Code': 'DATA_BLOCKED'}) from cause

    jobs = PlanJobs(max_pending=1)
    job = jobs.start('owner', 'key', 'request', work)
    while not job.task.done():
        await asyncio.sleep(0)
    await asyncio.sleep(0)  # Completion callback releases finished frames.
    gc.collect()
    assert references and all(reference() is None for reference in references)
    error = job.task.exception()
    assert isinstance(error, HTTPException)
    assert error.status_code == 422
    assert error.detail == {'code': 'DATA_BLOCKED', 'missing': ['edible_g']}
    assert error.headers == {'X-Error-Code': 'DATA_BLOCKED'}
    assert str(error.__cause__) == 'original data gap'
    assert error.__traceback__ is not None  # Location evidence remains available.
    assert jobs.get(job.job_id, 'stranger') is None
    assert jobs.get(job.job_id, 'owner') is job
    await jobs.close()


def test_owned_cancellation_stops_worker_before_the_next_unit_and_reports_real_progress(monkeypatch, tmp_path):
    import time

    from app import main
    from app.services.plan_jobs import check_cancelled, report_stage

    settings = Settings(price_provider="mock", plan_store_path=tmp_path / "cancel.sqlite")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    started, release, stopped = Event(), Event(), Event()
    calls = []

    def work():
        try:
            report_stage("library_preparation", completed=7, total=11, unit="publications")
            calls.append("bounded unit")
            started.set()
            assert release.wait(5)
            check_cancelled()
            calls.append("must not execute or save")
        finally:
            stopped.set()

    async def admitted(*args):
        return await api._run_personal_thread(work)

    monkeypatch.setattr(api, "_run_admitted_plan", admitted)
    try:
        with TestClient(app) as client:
            accepted = client.post("/api/plans", headers={"Prefer": "respond-async"},
                                   json={"recipes": 3, "servings": 2})
            url = accepted.json()["status_url"]
            assert started.wait(2)
            progress = client.get(url).json()
            assert progress["stage"] == "library_preparation"
            assert progress["progress"] == {"completed": 7, "total": 11, "unit": "publications"}
            assert client.delete(url, headers={"X-Anonymous-Session-ID": "other-cancellation-owner-12345"}).status_code == 404
            assert not stopped.is_set()
            cancelling = client.delete(url)
            assert cancelling.status_code == 202 and cancelling.json()["status"] == "cancelling"
            assert cancelling.headers["cache-control"] == "private, no-store"
            assert not stopped.is_set()  # No false assertion that the running unit was interrupted.
            release.set()
            assert stopped.wait(2)
            for _ in range(100):
                if client.get(url).status_code == 404:
                    break
                time.sleep(.01)
            else:
                pytest.fail("The worker did not finish cancellation")
            assert client.delete(url).json()["status"] == "cancelled"
            assert calls == ["bounded unit"]
    finally:
        release.set()


@pytest.mark.parametrize("completed,total,unit", [(2,1,"recipes"),(-1,3,"publications"),
                                                  (True,1,"recipes"),(1,None,"recipes"),(1,3,"percent")])
def test_progress_cannot_claim_unmeasured_or_invalid_work(completed,total,unit):
    from app.services.plan_jobs import report_stage

    with pytest.raises(ValueError):
        report_stage("candidate_qualification", completed=completed, total=total, unit=unit)


@pytest.mark.asyncio
async def test_retained_cancelled_job_releases_the_cooperative_worker_state():
    import gc
    import weakref

    from app.services.plan_jobs import PlanJobs, check_cancelled

    class PlannerState:
        pass

    references = []
    started, release = Event(), Event()

    def work():
        state = PlannerState()
        references.append(weakref.ref(state))
        started.set()
        assert release.wait(5)
        check_cancelled()

    jobs = PlanJobs(max_pending=1)
    job = jobs.start("owner", "key", "request", lambda: api._run_personal_thread(work))
    try:
        while not started.is_set():
            await asyncio.sleep(.001)
        job.task.cancel()
        await asyncio.sleep(0)
    finally:
        release.set()
    while not job.task.done():
        await asyncio.sleep(.001)
    await asyncio.sleep(0)  # Completion callback runs before retention is inspected.
    gc.collect()
    assert job.task.cancelled() and job.stage == "cancelled"
    assert all(reference() is None for reference in references)
    with pytest.raises(asyncio.CancelledError):
        await job.task
    await jobs.close()
