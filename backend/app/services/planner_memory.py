"""Return unused allocator pages at bounded planner phase boundaries.

No live cache, candidate, certificate or owner state is evicted here. Collection
reclaims unreachable Python cycles. On glibc, malloc_trim additionally returns
whole unused heap pages to the OS; unsupported runtimes retain ordinary GC.
"""
from __future__ import annotations

import ctypes
import gc
import sys
from functools import lru_cache

from app.services.performance_trace import increment_performance_counter


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


def release_idle_memory():
    collected = gc.collect()
    function = _allocator_trim()
    released = bool(function(0)) if function is not None else None
    increment_performance_counter("planner_memory_reclamation_calls")
    increment_performance_counter("planner_unreachable_objects_collected", collected)
    increment_performance_counter("planner_allocator_trim_available", function is not None)
    increment_performance_counter("planner_allocator_trim_released", released is True)
    return {"collected": collected, "allocator_supported": function is not None,
            "allocator_released": released}
