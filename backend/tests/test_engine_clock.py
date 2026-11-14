"""The planning time limit starts when the engine starts (owner decision 2026-11-14).

Waiting in the admission queue does not use the planner's 60 seconds; the
work after admission still has exactly its own limit.
"""
import asyncio
from types import SimpleNamespace

import pytest
from app.api.plan import _pending_plan_job, _with_current_deadline
from app.services import plan_jobs
from app.services.personal_policy import PolicyConflict
from app.services.planner_admission import PlannerAdmissionController

CURRENT = SimpleNamespace(library_search_policy="smako-current-library-v2")


async def _queued_request(seconds, work_seconds):
    admission = PlannerAdmissionController(max_concurrent=1, max_queued=4)
    release = asyncio.Event()

    async def leader_work():
        await release.wait()
        return "leader"

    async def own_work():
        await asyncio.sleep(work_seconds)
        plan_jobs.check_cancelled()
        return "planned"

    leader = asyncio.create_task(admission.run("leader", leader_work))
    await asyncio.sleep(0.01)
    queued = asyncio.create_task(_with_current_deadline(CURRENT, lambda: admission.run("queued", own_work), seconds=seconds))
    await asyncio.sleep(seconds + 1.0)  # Longer than the whole limit, all of it in the queue.
    release.set()
    await leader
    return await queued


@pytest.mark.asyncio
async def test_time_in_the_queue_does_not_count():
    assert await _queued_request(1.5, 0.05) == "planned"


@pytest.mark.asyncio
async def test_engine_work_still_has_its_limit():
    with pytest.raises(PolicyConflict) as error:
        await _queued_request(1.0, 1.6)
    assert error.value.code == "SEARCH_INCOMPLETE"


@pytest.mark.asyncio
async def test_job_status_reports_engine_time_after_admission():
    jobs = plan_jobs.PlanJobs(max_pending=2)
    admission = PlannerAdmissionController(max_concurrent=1, max_queued=2)
    started, finish = asyncio.Event(), asyncio.Event()

    async def engine():
        started.set()
        await finish.wait()
        return "saved"

    job = jobs.start("owner", "key", "request", lambda: _with_current_deadline(CURRENT, lambda: admission.run("k", engine), seconds=60))
    assert _pending_plan_job(job).body and job.engine is None
    await started.wait()
    await asyncio.sleep(0.05)
    import json
    engine_info = json.loads(_pending_plan_job(job).body)["engine"]
    assert 0 < engine_info["elapsed_seconds"] < 5 and 55 < engine_info["limit_seconds"] <= 60
    finish.set()
    assert await job.task == "saved"
