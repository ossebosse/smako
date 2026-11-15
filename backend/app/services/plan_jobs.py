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
from dataclasses import dataclass, field
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


_planning_deadline: ContextVar = ContextVar("planning_deadline", default=None)


@dataclass
class _DeadlineClock:
    """Shared by the nested deadlines of one request.

    Owner decision 2026-11-14: the planning time limit counts from when the
    engine starts (admission), not from when the request arrived. Time spent
    waiting in the admission queue is credited back to every enclosing
    deadline and to the asyncio timers guarding them.
    """
    credit: float = 0.0
    timers: list = field(default_factory=list)
    paused: dict = field(default_factory=dict)


_deadline_clock: ContextVar = ContextVar("deadline_clock", default=None)
_engine_reporter: ContextVar = ContextVar("engine_reporter", default=None)


def _credit() -> float:
    clock = _deadline_clock.get()
    return clock.credit if clock is not None else 0.0


class PlanningDeadlineExceeded(RuntimeError):
    """Must escape pricing/beam ValueError retries before HTTP translation."""


@contextmanager
def planning_deadline(seconds):
    clock_token = None
    if _deadline_clock.get() is None:
        clock_token = _deadline_clock.set(_DeadlineClock())
    previous = _planning_deadline.get()
    # Stored without the queue credit; check_cancelled adds it back.
    limit = monotonic() - _credit() + seconds if seconds is not None else previous
    if previous is not None and limit is not None:
        limit = min(previous, limit)
    token = _planning_deadline.set(limit)
    try:
        yield
    finally:
        _planning_deadline.reset(token)
        if clock_token is not None:
            _deadline_clock.reset(clock_token)


def register_deadline_timer(timer):
    """Let queue time credited later also move this asyncio timeout."""
    clock = _deadline_clock.get()
    if clock is not None:
        clock.timers.append(timer)


def unregister_deadline_timer(timer):
    clock = _deadline_clock.get()
    if clock is not None and timer in clock.timers:
        clock.timers.remove(timer)


def pause_engine_clock():
    """Called when the request starts waiting for the planner: stop its timers."""
    clock = _deadline_clock.get()
    if clock is None:
        return
    for timer in clock.timers:
        when = timer.when()
        if when is None or timer.expired() or timer in clock.paused:
            continue
        try:
            timer.reschedule(None)
        except RuntimeError:
            continue
        clock.paused[timer] = when


def start_engine_clock(queued_seconds: float):
    """Called when the planner is admitted: the time limit starts now."""
    clock = _deadline_clock.get()
    if clock is not None and clock.paused and not (queued_seconds > 0 and _planning_deadline.get() is not None):
        for timer, when in list(clock.paused.items()):
            try:
                timer.reschedule(when)
            except RuntimeError:
                pass
        clock.paused.clear()
    if clock is not None and queued_seconds > 0 and _planning_deadline.get() is not None:
        clock.credit += queued_seconds
        for timer in list(clock.timers):
            when = clock.paused.pop(timer, None) or timer.when()
            if when is None or timer.expired():
                continue
            try:
                timer.reschedule(when + queued_seconds)
            except RuntimeError:  # Already left; nothing to move.
                pass
    reporter = _engine_reporter.get()
    if reporter:
        reporter(remaining_planning_seconds())


def check_cancelled():
    deadline = _planning_deadline.get()
    if deadline is not None and monotonic() >= deadline + _credit():
        raise PlanningDeadlineExceeded("The complete planning deadline expired")
    stop = _work_cancellation.get()
    if stop is not None and stop.is_set():
        raise asyncio.CancelledError()


def remaining_planning_seconds():
    deadline = _planning_deadline.get()
    return None if deadline is None else max(0.0, deadline + _credit() - monotonic())


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
    # (monotonic start, seconds the engine may use), set when admitted.
    engine: tuple[float, float | None] | None = None

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
            engine_token = _engine_reporter.set(lambda limit: setattr(job, "engine", (monotonic(), limit)))
            reference_token = job_reference.set({"job_id": job.job_id, "request_id": job.request_id})
            try:
                return await work()
            finally:
                job_reference.reset(reference_token)
                _engine_reporter.reset(engine_token)
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
