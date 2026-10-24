"""Bounded, owner-scoped async transport around the existing saved planner.

This does not schedule source work or replace planner admission. Completed plans
are persisted by the existing PlanStore; only short-lived transport state lives
here. A process restart expires unfinished jobs rather than replaying writes.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Event
from time import monotonic
from uuid import uuid4

from app.models import SavedPlan

_stage_reporter: ContextVar = ContextVar("plan_stage_reporter", default=None)
job_reference: ContextVar = ContextVar("plan_job_reference", default=None)
_work_cancellation: ContextVar = ContextVar("plan_work_cancellation", default=None)
logger = logging.getLogger(__name__)


@contextmanager
def cancellable_work():
    """Share one thread-safe stop request with this worker's copied context."""
    stop = Event()
    token = _work_cancellation.set(stop)
    try:
        yield stop
    finally:
        _work_cancellation.reset(token)


def check_cancelled():
    stop = _work_cancellation.get()
    if stop is not None and stop.is_set():
        raise asyncio.CancelledError()


def report_stage(stage: str, *, completed=None, total=None, unit=None):
    check_cancelled()
    progress = None
    if completed is not None or total is not None or unit is not None:
        if (type(completed) is not int or type(total) is not int
                or not 0 <= completed <= total or unit not in {"recipes", "publications"}):
            raise ValueError("Progress requires actual completed/total work units")
        progress = {"completed": completed, "total": total, "unit": unit}
    reporter = _stage_reporter.get()
    if reporter:
        reporter(stage, progress)


class PlanJobsFull(RuntimeError):
    pass


def _release_exception_frames(error: BaseException | None) -> None:
    """Keep pollable error evidence without retaining finished planner locals.

    A Task retains its exception for the transport retention period. Chained
    tracebacks otherwise retain the complete planner, facts and search caches.
    Clearing completed frames preserves exception type, public fields, cause
    chain and traceback locations; it never changes the user-visible failure.
    """
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        traceback.clear_frames(current.__traceback__)
        pending.extend((current.__cause__, current.__context__))
        if isinstance(current, BaseExceptionGroup):
            pending.extend(current.exceptions)


@dataclass
class PlanJob:
    job_id: str
    owner: str
    key: str
    request_id: str
    task: asyncio.Task[SavedPlan]
    completed_at: float | None = None
    status: tuple[str, dict | None] = ("queued", None)

    @property
    def stage(self):
        return self.status[0]


class PlanJobs:
    def __init__(self, *, max_pending: int, max_retained: int = 64, retention: float = 900):
        self.max_pending = max_pending
        self.max_retained = max_retained
        self.retention = retention
        self.jobs: dict[str, PlanJob] = {}
        self.requests: dict[tuple[str, str], str] = {}

    def _prune(self):
        cutoff = monotonic() - self.retention
        self.jobs = {key: job for key, job in self.jobs.items()
                     if job.completed_at is None or job.completed_at > cutoff}
        self.requests = {key: value for key, value in self.requests.items() if value in self.jobs}

    def start(self, owner: str, key: str, request_id: str,
              work: Callable[[], Awaitable[SavedPlan]]) -> PlanJob:
        self._prune()
        # Bound recovery aliases as well as retained tasks. Never store an owner
        # or request capability in public diagnostics.
        if len(self.requests) >= 4096:
            del self.requests[next(iter(self.requests))]
        for job in self.jobs.values():
            if (job.owner == owner and job.key == key
                    and (not job.task.done() or (not job.task.cancelled() and job.task.exception() is None))):
                self.requests[owner, request_id] = job.job_id
                logger.info("plan_job reused job=%s request=%s stage=%s", job.job_id, request_id, job.stage)
                return job
        if sum(not job.task.done() for job in self.jobs.values()) >= self.max_pending:
            raise PlanJobsFull()
        if len(self.jobs) >= self.max_retained:
            completed = [job for job in self.jobs.values() if job.task.done()]
            if not completed:
                raise PlanJobsFull()
            oldest = min(completed, key=lambda job: job.completed_at or 0)
            del self.jobs[oldest.job_id]
        async def run():
            token = _stage_reporter.set(lambda stage, progress: setattr(job, "status", (stage, progress)))
            reference_token = job_reference.set({"job_id": job.job_id, "request_id": job.request_id})
            try:
                return await work()
            finally:
                job_reference.reset(reference_token)
                _stage_reporter.reset(token)

        job = PlanJob(uuid4().hex, owner, key, request_id, asyncio.create_task(run()))
        self.jobs[job.job_id] = job
        self.requests[owner, request_id] = job.job_id
        logger.info("plan_job accepted job=%s request=%s", job.job_id, request_id)

        def finished(task):
            job.completed_at = monotonic()
            if task.cancelled():
                job.status = ("cancelled", None)
                # Cooperative cancellation crosses the thread with a traceback
                # too. A retained cancelled Task otherwise keeps that entire
                # planner alive even though no browser will read its result.
                try:
                    task.exception()
                except asyncio.CancelledError as error:
                    _release_exception_frames(error)
            # Retrieve exceptions even when a browser never polls again. The
            # existing API exception handlers render them on an owned poll.
            if not task.cancelled():
                _release_exception_frames(task.exception())
            logger.info("plan_job completed job=%s request=%s outcome=%s", job.job_id, job.request_id,
                        "cancelled" if task.cancelled() else "failed" if task.exception() else "saved")

        job.task.add_done_callback(finished)
        return job

    def get(self, job_id: str, owner: str) -> PlanJob | None:
        self._prune()
        job = self.jobs.get(job_id)
        return job if job is not None and job.owner == owner else None

    def by_request(self, request_id: str, owner: str) -> PlanJob | None:
        self._prune()
        return self.get(self.requests.get((owner, request_id), ""), owner)

    async def close(self):
        tasks = [job.task for job in self.jobs.values() if not job.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
