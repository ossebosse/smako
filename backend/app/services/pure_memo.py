"""A bounded memo for pure functions whose hits take no lock.

``functools.lru_cache`` locks on every call when Python runs without the GIL,
so threads calling the same hot function (ingredient names are canonicalized
hundreds of thousands of times per plan) take turns. Here a hit is a plain
dict read; only a miss writes, and the oldest entry is dropped when full
(first in, first out instead of least recently used: the answer is the same,
only which entry is recomputed later can differ). For pure functions of
hashable positional arguments, exactly like ``lru_cache(maxsize=n)``, with
``cache_info``, ``cache_clear`` and ``__wrapped__``. Its counters are
statistics: without the GIL two threads may count one hit as one.
"""
from __future__ import annotations

import functools
from collections import namedtuple
from collections.abc import Callable

CacheInfo = namedtuple("CacheInfo", ["hits", "misses", "maxsize", "currsize"])
_MISSING = object()


def pure_memo(maxsize: int) -> Callable[[Callable], Callable]:
    if maxsize < 1:
        raise ValueError("maxsize must be at least one")

    def decorate(function: Callable) -> Callable:
        values: dict = {}
        counts = [0, 0]

        @functools.wraps(function)
        def memo(*args):
            value = values.get(args, _MISSING)
            if value is not _MISSING:
                counts[0] += 1
                return value
            counts[1] += 1
            value = function(*args)  # an exception is not cached, as with lru_cache
            while len(values) >= maxsize:
                try:
                    values.pop(next(iter(values)), None)
                except (StopIteration, RuntimeError):  # emptied or changed meanwhile
                    break
            values[args] = value
            return value

        def cache_info() -> CacheInfo:
            return CacheInfo(counts[0], counts[1], maxsize, len(values))

        def cache_clear() -> None:
            values.clear()
            counts[0] = counts[1] = 0

        memo.cache_info = cache_info
        memo.cache_clear = cache_clear
        return memo

    return decorate
