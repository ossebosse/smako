"""Process-local reuse of pure product resolution between planner requests.

``PersonalPlanner.resolve`` turns one ingredient need into its qualified,
priced product candidates. Its request-local cache key covers the ingredient,
unit, profile, organic/food flags and recipe forms. Everything else it reads is
fixed per *scope*: the exact prepared price universe and fact collection
objects, the request's usable stores, purchase mode, pricing date, membership
and coupon identity, and settings. Two requests with the same scope and key
compute the same candidates, the same failure and the same traced product
events, so a later request may reuse them instead of recomputing.

Only successes and diagnostics-free failures are shared, exactly what the
planner already caches within one request. Entries are immutable by
convention (the planner already shares candidate objects between baskets).
The scope holds strong references to the universe and facts objects, so an
``id()`` in the key can never be reused by a different object while cached.

Nothing here is a price, approval or plan: every basket, nutrition check and
checkout audit still runs per request. Disable with
``SMAKO_PLANNER_SHARED_RESOLUTION=0``.
"""
from __future__ import annotations

import os
import threading
from collections import OrderedDict

SCOPE_LIMIT = 4
ENTRY_LIMIT = 32768


def enabled() -> bool:
    return os.getenv("SMAKO_PLANNER_SHARED_RESOLUTION", "1") != "0"


class _Scope:
    __slots__ = ("entries", "keep", "stats")

    def __init__(self, keep):
        self.entries: OrderedDict = OrderedDict()
        self.keep = keep  # strong references: ids in the scope key stay unique
        self.stats = {"hits": 0, "misses": 0, "stores": 0, "evictions": 0}


class SharedResolution:
    def __init__(self, *, scope_limit=SCOPE_LIMIT, entry_limit=ENTRY_LIMIT):
        self.scope_limit, self.entry_limit = scope_limit, entry_limit
        self._scopes: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def scope(self, key, keep):
        with self._lock:
            scope = self._scopes.get(key)
            if scope is None:
                if len(self._scopes) >= self.scope_limit:
                    self._scopes.popitem(last=False)
                scope = self._scopes[key] = _Scope(keep)
            else:
                self._scopes.move_to_end(key)
            return scope

    def get(self, scope, key):
        with self._lock:
            entry = scope.entries.get(key)
            if entry is None:
                scope.stats["misses"] += 1
                return None
            scope.entries.move_to_end(key)
            scope.stats["hits"] += 1
            return entry

    def put(self, scope, key, entry):
        with self._lock:
            if key not in scope.entries and len(scope.entries) >= self.entry_limit:
                scope.entries.popitem(last=False)
                scope.stats["evictions"] += 1
            scope.entries[key] = entry
            scope.stats["stores"] += 1

    def clear(self):
        with self._lock:
            self._scopes.clear()

    def stats(self):
        with self._lock:
            return [dict(s.stats, entries=len(s.entries)) for s in self._scopes.values()]


SHARED_RESOLUTION = SharedResolution()


def planner_scope(planner):
    """The scope of everything ``resolve`` reads besides its own cache key."""
    if not enabled():
        return None
    view = planner.view
    key = (
        id(planner.prepared), planner.prepared.universe.universe_id,
        planner.facts_version,  # content hash of every fact (facts_version)
        view.cache_identity,  # usable/stale contexts, selection and Stockholm date
        frozenset(s.store_id for s in view.stores), frozenset(planner.store_ids),
        planner.user.cache_identity, planner.pricing_date.isoformat(),
        planner.request.purchase_planning_mode, planner.complete,
        repr(planner.settings),
    )
    return SHARED_RESOLUTION.scope(key, planner.prepared)
