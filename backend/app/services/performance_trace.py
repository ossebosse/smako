"""Request-local, deterministic performance instrumentation for meal planning.

The helpers in this module are deliberately no-ops unless a trace is active.
They can therefore live on hot paths without creating process-global metrics or
allowing data from concurrent requests to leak into each other.  ``ContextVar``
state is copied into ``asyncio.to_thread`` workers, which lets one trace cover
the async provider boundary and the synchronous search/checkout code.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from time import perf_counter_ns, process_time_ns


@dataclass(frozen=True, slots=True)
class PerformanceSnapshot:
    """Serializable snapshot of one completed or in-progress trace."""

    timings_ms: dict[str, float]
    span_statistics: dict[str, dict[str, int | float]]
    operation_counters: dict[str, int]
    depth_counters: dict[str, dict[str, int]]


@dataclass(slots=True)
class PerformanceTrace:
    """Thread-safe accumulator scoped to one plan/profile operation."""

    _timings_ns: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _cpu_ns: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _calls: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _max_ns: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _counters: Counter[str] = field(default_factory=Counter, init=False, repr=False)
    _depths: dict[int, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter), init=False, repr=False
    )
    _lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def add_timing_ns(
        self,
        name: str,
        elapsed_ns: int,
        *,
        cpu_ns: int = 0,
    ) -> None:
        if elapsed_ns < 0 or cpu_ns < 0:
            raise ValueError("elapsed_ns and cpu_ns cannot be negative")
        normalized = _metric_name(name)
        with self._lock:
            self._timings_ns[normalized] += elapsed_ns
            self._cpu_ns[normalized] += cpu_ns
            self._calls[normalized] += 1
            self._max_ns[normalized] = max(self._max_ns[normalized], elapsed_ns)

    def increment(self, name: str, amount: int = 1) -> None:
        if amount < 0:
            raise ValueError("counter increments cannot be negative")
        normalized = _metric_name(name)
        with self._lock:
            self._counters[normalized] += amount

    def record_depth(self, depth: int, values: Mapping[str, int]) -> None:
        if depth < 1:
            raise ValueError("depth must be at least one")
        normalized: dict[str, int] = {}
        for name, value in values.items():
            if value < 0:
                raise ValueError("depth counters cannot be negative")
            normalized[_metric_name(name)] = value
        with self._lock:
            self._depths[depth].update(normalized)

    def snapshot(self) -> PerformanceSnapshot:
        with self._lock:
            timings = {
                name: round(elapsed_ns / 1_000_000, 3)
                for name, elapsed_ns in sorted(self._timings_ns.items())
            }
            span_statistics = {
                name: {
                    "calls": self._calls[name],
                    "wall_ms": round(elapsed_ns / 1_000_000, 3),
                    "cpu_ms": round(self._cpu_ns[name] / 1_000_000, 3),
                    "average_ms": round(
                        elapsed_ns / self._calls[name] / 1_000_000,
                        3,
                    ),
                    "max_ms": round(self._max_ns[name] / 1_000_000, 3),
                }
                for name, elapsed_ns in sorted(self._timings_ns.items())
            }
            counters = dict(sorted(self._counters.items()))
            depths = {
                str(depth): dict(sorted(values.items()))
                for depth, values in sorted(self._depths.items())
            }
        return PerformanceSnapshot(
            timings_ms=timings,
            span_statistics=span_statistics,
            operation_counters=counters,
            depth_counters=depths,
        )


_ACTIVE_TRACE: ContextVar[PerformanceTrace | None] = ContextVar(
    "meal_plan_performance_trace", default=None
)


def _metric_name(value: str) -> str:
    normalized = value.casefold().strip().replace("-", " ").replace("/", " ")
    normalized = "_".join(normalized.split())
    if not normalized or not all(character.isalnum() or character == "_" for character in normalized):
        raise ValueError(f"invalid performance metric name: {value!r}")
    return normalized


def current_performance_trace() -> PerformanceTrace | None:
    """Return the active request trace, if instrumentation was enabled."""

    return _ACTIVE_TRACE.get()


@contextmanager
def activate_performance_trace(
    trace: PerformanceTrace | None = None,
) -> Iterator[PerformanceTrace]:
    """Activate an isolated trace and restore the previous context on exit."""

    active = trace or PerformanceTrace()
    token = _ACTIVE_TRACE.set(active)
    try:
        yield active
    finally:
        _ACTIVE_TRACE.reset(token)


@asynccontextmanager
async def activate_performance_trace_async(
    trace: PerformanceTrace | None = None,
) -> AsyncIterator[PerformanceTrace]:
    """Async spelling of :func:`activate_performance_trace`."""

    with activate_performance_trace(trace) as active:
        yield active


@contextmanager
def performance_span(name: str) -> Iterator[None]:
    """Accumulate elapsed wall time under ``name`` when a trace is active."""

    trace = current_performance_trace()
    if trace is None:
        yield
        return
    started = perf_counter_ns()
    cpu_started = process_time_ns()
    try:
        yield
    finally:
        trace.add_timing_ns(
            name,
            perf_counter_ns() - started,
            cpu_ns=process_time_ns() - cpu_started,
        )


def increment_performance_counter(name: str, amount: int = 1) -> None:
    trace = current_performance_trace()
    if trace is not None:
        trace.increment(name, amount)


def record_performance_depth(depth: int, **values: int) -> None:
    trace = current_performance_trace()
    if trace is not None:
        trace.record_depth(depth, values)


def record_performance_seconds(name: str, seconds: float) -> None:
    if seconds < 0:
        raise ValueError("seconds cannot be negative")
    trace = current_performance_trace()
    if trace is not None:
        trace.add_timing_ns(name, round(seconds * 1_000_000_000))


def traced_plan_call[**P, R](
    function: Callable[P, Awaitable[R]],
) -> Callable[P, Awaitable[R]]:
    """Ensure an async plan entry point has a fresh trace.

    An explicitly activated outer trace (used by the deterministic profiler)
    wins. Ordinary API calls receive a new trace which is reset after the
    response has been built, including exceptional exits.
    """

    @wraps(function)
    async def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        if current_performance_trace() is not None:
            return await function(*args, **kwargs)
        async with activate_performance_trace_async():
            return await function(*args, **kwargs)

    return wrapped


__all__ = [
    "PerformanceSnapshot",
    "PerformanceTrace",
    "activate_performance_trace",
    "activate_performance_trace_async",
    "current_performance_trace",
    "increment_performance_counter",
    "performance_span",
    "record_performance_depth",
    "record_performance_seconds",
    "traced_plan_call",
]
