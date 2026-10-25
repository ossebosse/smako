"""Process-local reuse of pure product resolution between planner requests.

``PersonalPlanner.resolve`` turns one ingredient need into its qualified,
priced product candidates. Its request-local cache key covers the ingredient,
unit, profile, organic/food flags and recipe forms. Everything else it reads is
fixed per *scope*: the exact prepared price universe object and fact content
version, the request's usable stores, purchase mode, pricing date, membership
and coupon identity, and settings. Two requests with the same scope and key
compute the same candidates, the same failure and the same traced product
events, so a later request may reuse them instead of recomputing.

Only successes and diagnostics-free failures are shared, exactly what the
planner already caches within one request. Entries are immutable by
convention (the planner already shares candidate objects between baskets).
The scope holds a weak reference to the prepared universe and verifies object
identity on reuse. Retired universes are not kept alive by this cache; their
entries are discarded when the last owner releases them. Production fact
versions are computed from every fact by ``FactsCollection``; injected facts
must honor the same immutable content-version contract.

Nothing here is a price, approval or plan: every basket, nutrition check and
checkout audit still runs per request. Disable with
``SMAKO_PLANNER_SHARED_RESOLUTION=0``.
"""
from __future__ import annotations

import os
import sys
import threading
import weakref
from collections import OrderedDict

SCOPE_LIMIT = 4
ENTRY_LIMIT = 32768


def enabled() -> bool:
    return os.getenv("SMAKO_PLANNER_SHARED_RESOLUTION", "1") != "0"


class _Scope:
    __slots__ = ("entries", "keep", "stats")

    def __init__(self, keep, expired):
        self.entries: OrderedDict = OrderedDict()
        self.keep = weakref.ref(keep, expired)
        self.stats = {"hits": 0, "misses": 0, "stores": 0, "evictions": 0}


class SharedResolution:
    def __init__(self, *, scope_limit=SCOPE_LIMIT, entry_limit=ENTRY_LIMIT):
        self.scope_limit, self.entry_limit = scope_limit, entry_limit
        self._scopes: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def scope(self, key, keep):
        def expired(reference):
            with self._lock:
                current = self._scopes.get(key)
                if current is not None and current.keep is reference:
                    del self._scopes[key]

        with self._lock:
            scope = self._scopes.get(key)
            if scope is None or scope.keep() is not keep:
                if len(self._scopes) >= self.scope_limit:
                    self._scopes.popitem(last=False)
                scope = self._scopes[key] = _Scope(keep, expired)
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


class CheckoutArithmeticCache:
    """Bounded memo of integer arithmetic, containing no quotes or menus.

    A key contains every exact (rank, cents, winning-store bits) operand and
    its subset-position mask, count and lane width for ONE ingredient. The
    result is numeric columns and position masks. Source qualification and quoting run
    BEFORE this boundary; current quotes and independent checkout audit run
    AFTER it. Equal integers have equal arithmetic even after a price/fact
    replacement. No source identity, date, eligibility or approval is inferred.
    Only the optimizer's proven exact-integer path may use this cache. Decimal
    fallback, coupled promotions and custom checkout retain their own paths.
    """

    def __init__(self, *, max_entries=512, max_bytes=8 * 1024 * 1024):
        if max_entries < 1 or max_bytes < 1:
            raise ValueError("Checkout arithmetic cache bounds must be positive")
        self.max_entries, self.max_bytes = max_entries, max_bytes
        self._entries = OrderedDict()
        self._lock = threading.Lock()
        self.clear()

    def get(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._hits += 1
            return entry[0]

    def put(self, key, value):
        # These trees contain only tuples/ints/None. Count repeated references
        # again conservatively; neither source models nor search state survive.
        def size(item):
            return sys.getsizeof(item) + (sum(size(v) for v in item) if isinstance(item, tuple) else 0)

        weight = size(key) + size(value) + 128
        if weight > min(self.max_bytes, 64 * 1024):
            return
        with self._lock:
            previous = self._entries.pop(key, None)
            if previous is not None:
                self._bytes -= previous[1]
            while self._entries and (len(self._entries) >= self.max_entries or self._bytes + weight > self.max_bytes):
                _, (_, released) = self._entries.popitem(last=False)
                self._bytes -= released
            self._entries[key] = (value, weight)
            self._bytes += weight

    def clear(self):
        with self._lock:
            self._entries.clear()
            self._bytes = self._hits = self._misses = 0

    def stats(self):
        with self._lock:
            return {"entries": len(self._entries), "bytes": self._bytes, "hits": self._hits, "misses": self._misses}


CHECKOUT_ARITHMETIC = CheckoutArithmeticCache()


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
