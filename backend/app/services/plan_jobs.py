"""Bounded, owner-scoped async transport around the existing saved planner.

This does not schedule source work or replace planner admission. Completed plans
are persisted by the existing PlanStore; only short-lived transport state lives
here. A process restart expires unfinished jobs rather than replaying writes.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from app.models import SavedPlan


class PlanJobsFull(RuntimeError):
    pass


@dataclass
class PlanJob:
    job_id: str
    owner: str
    key: str
    request_id: str
    task: asyncio.Task[SavedPlan]
    completed_at: float | None = None


class PlanJobs:
    def __init__(self, *, max_pending: int, max_retained: int = 64, retention: float = 900):
        self.max_pending = max_pending
        self.max_retained = max_retained
        self.retention = retention
        self.jobs: dict[str, PlanJob] = {}

    def _prune(self):
        cutoff = monotonic() - self.retention
        self.jobs = {key: job for key, job in self.jobs.items()
                     if job.completed_at is None or job.completed_at > cutoff}

    def start(self, owner: str, key: str, request_id: str,
              work: Callable[[], Awaitable[SavedPlan]]) -> PlanJob:
        self._prune()
        for job in self.jobs.values():
            if job.owner == owner and job.key == key and not job.task.done():
                return job
        if sum(not job.task.done() for job in self.jobs.values()) >= self.max_pending:
            raise PlanJobsFull()
        if len(self.jobs) >= self.max_retained:
            completed = [job for job in self.jobs.values() if job.task.done()]
            if not completed:
                raise PlanJobsFull()
            oldest = min(completed, key=lambda job: job.completed_at or 0)
            del self.jobs[oldest.job_id]
        job = PlanJob(uuid4().hex, owner, key, request_id, asyncio.create_task(work()))
        self.jobs[job.job_id] = job

        def finished(task):
            job.completed_at = monotonic()
            # Retrieve exceptions even when a browser never polls again. The
            # existing API exception handlers render them on an owned poll.
            if not task.cancelled():
                task.exception()

        job.task.add_done_callback(finished)
        return job

    def get(self, job_id: str, owner: str) -> PlanJob | None:
        self._prune()
        job = self.jobs.get(job_id)
        return job if job is not None and job.owner == owner else None

    async def close(self):
        tasks = [job.task for job in self.jobs.values() if not job.task.done()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
