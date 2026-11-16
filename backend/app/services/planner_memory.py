"""Return unused allocator pages at bounded planner phase boundaries.

No live cache, candidate, certificate or owner state is evicted here. Collection
reclaims unreachable Python cycles. On glibc, malloc_trim additionally returns
whole unused heap pages to the OS; unsupported runtimes retain ordinary GC.
"""
from __future__ import annotations

import ctypes
import gc
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache
from threading import Lock

from app.services.performance_trace import increment_performance_counter


@dataclass
class _AdmissionCleanup:
    available: bool = True
    lock: object = field(default_factory=Lock)


_admission_cleanup: ContextVar[_AdmissionCleanup | None] = ContextVar(
    "planner_admission_cleanup", default=None)


@contextmanager
def admission_cleanup_scope():
    """One startup collection may reuse the admission's completed full GC.

    The caller must have completed collection before entering. A mutable,
    locked credit is shared with worker-thread context copies, but never with
    another admitted job. Failure/cancellation restores the previous context.
    """
    token = _admission_cleanup.set(_AdmissionCleanup())
    try:
        yield
    finally:
        _admission_cleanup.reset(token)


def consume_admission_cleanup() -> bool:
    credit = _admission_cleanup.get()
    if credit is None:
        return False
    with credit.lock:
        if not credit.available:
            return False
        credit.available = False
    increment_performance_counter("planner_full_collections_coordinated")
    return True


@lru_cache(maxsize=1)
def _allocator_trim():
    if not sys.platform.startswith("linux"):
        return None
    try:
        function = ctypes.CDLL(None).malloc_trim
    except (AttributeError, OSError):
        return None
    function.argtypes = (ctypes.c_size_t,)
    function.restype = ctypes.c_int
    return function


def release_idle_memory(*, generation=2):
    collected = gc.collect(generation)
    function = _allocator_trim()
    released = bool(function(0)) if function is not None else None
    increment_performance_counter("planner_memory_reclamation_calls")
    increment_performance_counter(f"planner_memory_reclamation_generation_{generation}")
    increment_performance_counter("planner_unreachable_objects_collected", collected)
    increment_performance_counter("planner_allocator_trim_available", function is not None)
    increment_performance_counter("planner_allocator_trim_released", released is True)
    return {"collected": collected, "generation": generation, "allocator_supported": function is not None,
            "allocator_released": released}


def reclaim_and_freeze():
    """Full collection after a planning job, then freeze the survivors.

    Runs once the job's result is out (planner_admission), so nobody waits for
    it. Freezing moves the long-lived shared state (price universes, shared
    caches) out of the collector's scans, so the next job's collections only
    look at its own objects; a full collection with that state took about 7 s
    per job on beta. Unfreezing first lets this collection reclaim anything
    that became cyclic garbage since the last freeze, so nothing is kept for
    longer than one job. Objects freed by reference counting are freed as
    before, frozen or not.
    """
    gc.unfreeze()
    collected = gc.collect()
    function = _allocator_trim()
    if function is not None:
        function(0)
    gc.freeze()
    increment_performance_counter("planner_post_job_reclamations")
    increment_performance_counter("planner_unreachable_objects_collected", collected)
    return collected
