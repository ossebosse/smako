"""Process-local admission control for CPU-heavy consumer planning.

The deterministic planner deliberately keeps a number of immutable-universe
caches in one process.  Letting several request-cold searches enter those
caches concurrently is both slower (the work is CPU bound) and can acquire
the nested cache locks in different phases.  This controller admits a small,
configured number of distinct jobs while coalescing identical in-flight
requests.  It does not alter any planner input or economic result.
"""

from __future__ import annotations

import asyncio
import gc
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from time import perf_counter
from typing import TypeVar

Result = TypeVar("Result")
memory_cleanup_seconds: ContextVar[float] = ContextVar("planner_memory_cleanup_seconds", default=0.0)


class PlannerAdmissionOverloaded(RuntimeError):
    """Raised before work starts when the bounded distinct-job queue is full."""


class PlannerAdmissionBusy(RuntimeError):
    """Optional background work must yield to admitted consumer work."""


@dataclass(frozen=True, slots=True)
class PlannerAdmissionStats:
    active: int
    queued: int
    in_flight_keys: int
    admitted: int
    coalesced: int
    rejected: int
    peak_active: int
    peak_queued: int


@dataclass(frozen=True, slots=True)
class _Outcome[Result]:
    value: Result | None = None
    error: BaseException | None = None


class PlannerAdmissionController:
    """Bound and single-flight deterministic plan builds in one ASGI process.

    ``max_queued`` counts distinct request keys waiting for a worker. Exact
    duplicates share the leader result and therefore consume neither an extra
    worker nor an extra queue slot. The caller-provided key must contain the
    complete pricing/request identity, including memberships and universe ID.
    """

    def __init__(self, *, max_concurrent: int = 1, max_queued: int = 12) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least one")
        if max_queued < 0:
            raise ValueError("max_queued must not be negative")
        self.max_concurrent = max_concurrent
        self.max_queued = max_queued
        self._capacity = asyncio.Semaphore(max_concurrent)
        self._state_lock = asyncio.Lock()
        self._in_flight: dict[str, asyncio.Future[_Outcome[object]]] = {}
        self._active = 0
        self._queued = 0
        self._admitted = 0
        self._coalesced = 0
        self._rejected = 0
        self._peak_active = 0
        self._peak_queued = 0

    async def run(
        self,
        key: str,
        factory: Callable[[], Awaitable[Result]],
        *,
        only_if_idle: bool = False,
    ) -> Result:
        """Run one request, coalescing an identical in-flight computation."""

        normalized_key = key.strip()
        if not normalized_key:
            raise ValueError("planner admission key must not be blank")

        leader = False
        async with self._state_lock:
            if only_if_idle and self._in_flight:
                raise PlannerAdmissionBusy('consumer planning has priority')
            existing = self._in_flight.get(normalized_key)
            if existing is not None:
                self._coalesced += 1
                outcome_future = existing
            else:
                # Active jobs and queued jobs are both retained in _in_flight.
                # Bound only distinct work; duplicate followers are cheap and
                # remain protected by the public endpoint rate limiter.
                admitted_limit = self.max_concurrent + self.max_queued
                if len(self._in_flight) >= admitted_limit:
                    self._rejected += 1
                    raise PlannerAdmissionOverloaded(
                        "planner admission queue is full"
                    )
                outcome_future = asyncio.get_running_loop().create_future()
                self._in_flight[normalized_key] = outcome_future
                self._queued += 1
                self._admitted += 1
                self._peak_queued = max(self._peak_queued, self._queued)
                leader = True

        if not leader:
            # A cancelled client must not cancel the shared leader result.
            outcome = await asyncio.shield(outcome_future)
            if outcome.error is not None:
                raise outcome.error
            return outcome.value  # type: ignore[return-value]

        acquired = False
        cleanup_token = None
        try:
            await self._capacity.acquire()
            acquired = True
            async with self._state_lock:
                self._queued -= 1
                self._active += 1
                self._peak_active = max(self._peak_active, self._active)

            # Completed searches can leave cyclic garbage in Python's oldest
            # generation even after their bounded caches go out of scope.
            # Collect between admitted builds, before allocating another search.
            # This neither evicts live facts nor changes candidates or budgets.
            cleanup_started = perf_counter()
            await asyncio.to_thread(gc.collect)
            cleanup_token = memory_cleanup_seconds.set(perf_counter() - cleanup_started)

            try:
                value = await factory()
            except BaseException as exc:
                outcome = _Outcome[Result](error=exc)
                if not outcome_future.done():
                    outcome_future.set_result(outcome)  # type: ignore[arg-type]
                raise
            else:
                outcome = _Outcome(value=value)
                if not outcome_future.done():
                    outcome_future.set_result(outcome)  # type: ignore[arg-type]
                return value
        except BaseException as exc:
            # Cancellation may happen while the leader is still queued, before
            # the inner factory exception boundary can publish an outcome.
            if not outcome_future.done():
                outcome_future.set_result(_Outcome(error=exc))
            raise
        finally:
            if cleanup_token is not None:
                memory_cleanup_seconds.reset(cleanup_token)
            async with self._state_lock:
                if acquired:
                    self._active -= 1
                else:
                    self._queued -= 1
                self._in_flight.pop(normalized_key, None)
            if acquired:
                self._capacity.release()

    async def stats(self) -> PlannerAdmissionStats:
        async with self._state_lock:
            return PlannerAdmissionStats(
                active=self._active,
                queued=self._queued,
                in_flight_keys=len(self._in_flight),
                admitted=self._admitted,
                coalesced=self._coalesced,
                rejected=self._rejected,
                peak_active=self._peak_active,
                peak_queued=self._peak_queued,
            )


__all__ = [
    "PlannerAdmissionController",
    "PlannerAdmissionOverloaded",
    "PlannerAdmissionStats",
]
