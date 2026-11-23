"""Full ICA store catalogs from Primat, fetched a slice per day.

Owner decision 2026-11-23: every ICA store that Primat carries with its full
catalog in Smako's cities, fetched within the free plan (20 000 rows a day,
200 rows a call, 60 calls a minute) by spreading one full round over several
days.

Each daily step:

1. reads the remaining quota from ``/me`` and the stores from ``/stores``
   (neither counts against rows),
2. once a day, reads the stores' current campaigns (``/prices?offers=1``),
3. continues the full catalog cursor (``/prices``) over all stores together,
   saving the cursor after every page so the next day continues where this
   one stopped,
4. looks up package size once per food product (``/batch``), because catalog
   rows carry no amount or unit.

Rows are kept in a local SQLite file with the time each row was fetched.
A finished round removes rows that the round no longer returned.  Nothing here
touches the grocery database, the price universes or the planner.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PAGE_ROWS = 200
BATCH_LOOKUPS = 100
SECONDS_BETWEEN_CALLS = 1.1
MAX_STORES_PER_CALL = 15

# Top-level ICA categories (the chain's own names) whose products are food.
FOOD_CATEGORIES = frozenset(
    {
        "Skafferi",
        "Mejeri & Ost",
        "Glass, Godis & Snacks",
        "Dryck",
        "Kött, Chark & Fågel",
        "Bröd & Kakor",
        "Färdigmat & Såser",
        "Fryst",
        "Frukt & Grönt",
        "Fisk & Skaldjur",
        "Vegetariskt",
        "Jul",
        "Butikens egna varor",
    }
)


def default_catalog_path() -> Path:
    """``PRIMAT_ICA_CATALOG_DB`` or ``<data root>/primat-ica-catalog/catalog.sqlite``."""

    configured = os.getenv("PRIMAT_ICA_CATALOG_DB", "").strip()
    if configured:
        return Path(configured)
    return Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).parent / "primat-ica-catalog" / "catalog.sqlite"


def is_food_category(category: str | None) -> bool:
    parts = [part.strip() for part in (category or "").split(" > ")]
    if not parts or not parts[0]:
        return False
    if parts[0] in FOOD_CATEGORIES:
        return True
    # Baby food sits under "Barn"; nappies and clothes do not.
    return parts[0] == "Barn" and any("mat" in part.casefold() for part in parts[1:])


def _now() -> datetime:
    return datetime.now(tz=UTC)


class QuotaExhausted(RuntimeError):
    """Primat refused further rows today (HTTP 429)."""


class CatalogStore:
    """Small SQLite store owned by the catalog job alone."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS stores(
                store_id TEXT PRIMARY KEY, name TEXT, city TEXT, tier TEXT, seen_at TEXT);
            CREATE TABLE IF NOT EXISTS rows(
                store_id TEXT NOT NULL, product_id TEXT NOT NULL, category TEXT,
                row_json TEXT NOT NULL, changed_at TEXT, fetched_at TEXT NOT NULL,
                PRIMARY KEY(store_id, product_id));
            CREATE TABLE IF NOT EXISTS meta(
                chain TEXT NOT NULL, product_id TEXT NOT NULL,
                product_json TEXT, fetched_at TEXT NOT NULL,
                PRIMARY KEY(chain, product_id));
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS runs(
                started_at TEXT, finished_at TEXT, rows_used INTEGER, report_json TEXT);
            """
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, value: str | None) -> None:
        if value is None:
            self.db.execute("DELETE FROM state WHERE key=?", (key,))
        else:
            self.db.execute(
                "INSERT INTO state(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def save_stores(self, stores: Sequence[dict[str, Any]], seen_at: datetime) -> None:
        for store in stores:
            self.db.execute(
                "INSERT INTO stores(store_id, name, city, tier, seen_at) VALUES(?,?,?,?,?) "
                "ON CONFLICT(store_id) DO UPDATE SET name=excluded.name, city=excluded.city, "
                "tier=excluded.tier, seen_at=excluded.seen_at",
                (
                    store_key(store),
                    store.get("name"),
                    store.get("city"),
                    store.get("tier"),
                    seen_at.isoformat(),
                ),
            )

    def upsert_rows(self, rows: Iterable[dict[str, Any]], fetched_at: datetime) -> int:
        count = 0
        for row in rows:
            key = (f"{row.get('chain')}:{row.get('store_id')}", str(row.get("product_id") or ""))
            if not row.get("chain") or not row.get("store_id") or not key[1]:
                continue
            self.db.execute(
                "INSERT INTO rows(store_id, product_id, category, row_json, changed_at, fetched_at) "
                "VALUES(?,?,?,?,?,?) ON CONFLICT(store_id, product_id) DO UPDATE SET "
                "category=excluded.category, row_json=excluded.row_json, "
                "changed_at=excluded.changed_at, fetched_at=excluded.fetched_at",
                (
                    key[0],
                    key[1],
                    row.get("category"),
                    json.dumps(row, ensure_ascii=False, sort_keys=True),
                    row.get("changed_at"),
                    fetched_at.isoformat(),
                ),
            )
            count += 1
        return count

    def drop_rows_not_seen_since(self, store_ids: Sequence[str], since: datetime) -> int:
        marks = ",".join("?" for _ in store_ids)
        cursor = self.db.execute(
            f"DELETE FROM rows WHERE store_id IN ({marks}) AND fetched_at < ?",
            (*store_ids, since.isoformat()),
        )
        return cursor.rowcount

    def products_lacking_meta(self, limit: int) -> list[tuple[str, str, str]]:
        """Food products without package details: (chain, native store id, product id)."""

        found: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        query = self.db.execute(
            "SELECT r.store_id, r.product_id, r.category FROM rows r "
            "LEFT JOIN meta m ON m.chain = substr(r.store_id, 1, instr(r.store_id, ':') - 1) "
            "AND m.product_id = r.product_id WHERE m.product_id IS NULL "
            "ORDER BY r.product_id, r.store_id"
        )
        for store_id, product_id, category in query:
            chain, native = store_id.split(":", 1)
            if (chain, product_id) in seen or not is_food_category(category):
                continue
            seen.add((chain, product_id))
            found.append((chain, native, product_id))
            if len(found) >= limit:
                break
        return found

    def save_meta(
        self, chain: str, product_id: str, product: dict[str, Any] | None, fetched_at: datetime
    ) -> None:
        self.db.execute(
            "INSERT INTO meta(chain, product_id, product_json, fetched_at) VALUES(?,?,?,?) "
            "ON CONFLICT(chain, product_id) DO UPDATE SET product_json=excluded.product_json, "
            "fetched_at=excluded.fetched_at",
            (
                chain,
                product_id,
                None if product is None else json.dumps(product, ensure_ascii=False, sort_keys=True),
                fetched_at.isoformat(),
            ),
        )

    def commit(self) -> None:
        self.db.commit()

    def counts(self) -> dict[str, Any]:
        per_store = dict(self.db.execute("SELECT store_id, count(*) FROM rows GROUP BY store_id"))
        meta = self.db.execute(
            "SELECT count(*), sum(product_json IS NOT NULL) FROM meta"
        ).fetchone()
        return {
            "rows_per_store": per_store,
            "meta_products": int(meta[0] or 0),
            "meta_with_package": int(meta[1] or 0),
        }


def store_key(store: dict[str, Any]) -> str:
    return f"{store.get('chain')}:{store.get('store_id')}"


Fetch = Callable[..., Awaitable[dict[str, Any]]]


@dataclass
class StepReport:
    started_at: str
    stores: list[str] = field(default_factory=list)
    quota_rows_per_day: int | None = None
    quota_used_before: int | None = None
    budget_rows: int = 0
    rows_used: int = 0
    offer_rows: int = 0
    catalog_rows: int = 0
    catalog_pages: int = 0
    meta_lookups: int = 0
    meta_found: int = 0
    round_completed: bool = False
    rows_removed: int = 0
    stopped: str = "budget"
    calls: int = 0

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


async def run_catalog_step(
    store: CatalogStore,
    fetch: Fetch,
    *,
    cities: Sequence[str],
    max_rows: int,
    reserve_rows: int = 500,
    offers: bool = True,
    now: Callable[[], datetime] = _now,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> StepReport:
    """Fetch one day's slice. ``fetch(method, path, params=None, json=None)``."""

    started = now()
    report = StepReport(started_at=started.isoformat())
    calls = 0

    async def call(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        if calls:
            await sleep(SECONDS_BETWEEN_CALLS)  # Primat: 60 calls a minute
        calls += 1
        report.calls = calls
        return await fetch(method, path, **kwargs)

    me = await call("GET", "/me")
    plan = me.get("plan") or {}
    per_day = int(plan.get("rows_per_day") or 0)
    used = int(plan.get("rows_returned_today") or 0)
    report.quota_rows_per_day, report.quota_used_before = per_day, used
    budget = max(0, min(max_rows, per_day - used - reserve_rows))
    report.budget_rows = budget
    page_rows = min(PAGE_ROWS, int(plan.get("max_rows_per_call") or PAGE_ROWS))

    listing = await call("GET", "/stores")
    rows = listing if isinstance(listing, list) else listing.get("stores") or listing.get("data") or []
    wanted = {city.casefold() for city in cities}
    selected = sorted(
        (
            row
            for row in rows
            if isinstance(row, dict)
            and row.get("chain") == "ica"
            and row.get("tier") == "full"
            and str(row.get("city") or "").casefold() in wanted
        ),
        key=store_key,
    )[:MAX_STORES_PER_CALL]
    report.stores = [store_key(row) for row in selected]
    store.save_stores(selected, started)
    store.commit()
    if not selected:
        report.stopped = "no_full_ica_stores"
        return report
    native = ",".join(report.stores)

    def remaining() -> int:
        return budget - report.rows_used

    try:
        # 1. Campaigns once a day: they change more often than a round takes.
        today = started.date().isoformat()
        if offers and store.get("offers_day") != today:
            cursor = store.get("offers_cursor")
            if cursor is None:
                store.put("offers_pass_started_at", now().isoformat())
            while remaining() >= page_rows:
                params: dict[str, Any] = {"stores": native, "limit": page_rows, "offers": 1}
                if cursor:
                    params["cursor"] = cursor
                page = await call("GET", "/prices", params=params)
                data = [row for row in page.get("data") or [] if isinstance(row, dict)]
                report.rows_used += len(data)
                report.offer_rows += store.upsert_rows(data, now())
                cursor = page.get("next_cursor") or None
                store.put("offers_cursor", cursor)
                if cursor is None:
                    store.put("offers_day", today)
                    # Rows with an offer that this pass did not return have
                    # lost it; catalog_products drops such stale offers.
                    store.put("offers_pass_completed_from", store.get("offers_pass_started_at"))
                store.commit()
                if cursor is None:
                    break

        # 2. Package details for food first found earlier, then 3. the catalog.
        while remaining() > 0:
            wanted_meta = store.products_lacking_meta(min(BATCH_LOOKUPS, remaining()))
            if wanted_meta:
                answer = await call(
                    "POST",
                    "/batch",
                    json={
                        "lookups": [
                            {"chain": chain, "store_id": native_id, "product_id": product_id}
                            for chain, native_id, product_id in wanted_meta
                        ]
                    },
                )
                found: dict[tuple[str, str], dict[str, Any]] = {}
                returned = 0
                for item in answer.get("data") or []:
                    for product in (item or {}).get("results") or []:
                        returned += 1
                        if isinstance(product, dict) and product.get("product_id"):
                            found.setdefault(
                                (str(product.get("chain")), str(product.get("product_id"))),
                                product,
                            )
                report.rows_used += max(returned, 1)
                fetched = now()
                for chain, _native_id, product_id in wanted_meta:
                    store.save_meta(chain, product_id, found.get((chain, product_id)), fetched)
                report.meta_lookups += len(wanted_meta)
                report.meta_found += sum(
                    (chain, product_id) in found for chain, _native_id, product_id in wanted_meta
                )
                store.commit()
            if remaining() < page_rows:
                break

            scope = native
            if store.get("catalog_scope") != scope:
                # New or removed store: start a fresh round over the new scope.
                store.put("catalog_scope", scope)
                store.put("catalog_cursor", None)
                store.put("round_started_at", None)
            if store.get("round_started_at") is None:
                store.put("round_started_at", now().isoformat())
            params = {"stores": native, "limit": page_rows}
            cursor = store.get("catalog_cursor")
            if cursor:
                params["cursor"] = cursor
            page = await call("GET", "/prices", params=params)
            data = [row for row in page.get("data") or [] if isinstance(row, dict)]
            report.rows_used += len(data)
            report.catalog_rows += store.upsert_rows(data, now())
            report.catalog_pages += 1
            cursor = page.get("next_cursor") or None
            store.put("catalog_cursor", cursor)
            if cursor is None:
                round_started = datetime.fromisoformat(str(store.get("round_started_at")))
                report.rows_removed += store.drop_rows_not_seen_since(report.stores, round_started)
                store.put("round_completed_at", now().isoformat())
                store.put("round_started_at", None)
                report.round_completed = True
            store.commit()
    except QuotaExhausted:
        report.stopped = "quota_exhausted"
        store.commit()
    return report


def catalog_products(
    store: CatalogStore,
    *,
    store_ids: Sequence[str],
    not_before: datetime,
) -> list[tuple[dict[str, Any], datetime]]:
    """Merged rows ready for the Primat product parser, with their fetch time.

    Only food rows with known package details and fetched at or after
    ``not_before`` are returned.  The comparison price is scaled to this
    store's own price, since package details may come from another store.
    """

    marks = ",".join("?" for _ in store_ids)
    query = store.db.execute(
        f"SELECT r.row_json, r.fetched_at, m.product_json FROM rows r "
        f"JOIN meta m ON m.chain = substr(r.store_id, 1, instr(r.store_id, ':') - 1) "
        f"AND m.product_id = r.product_id "
        f"WHERE r.store_id IN ({marks}) AND m.product_json IS NOT NULL AND r.fetched_at >= ? "
        f"ORDER BY r.store_id, r.product_id",
        (*store_ids, not_before.isoformat()),
    )
    offers_from = store.get("offers_pass_completed_from")
    merged: list[tuple[dict[str, Any], datetime]] = []
    for row_json, fetched_at, product_json in query:
        row = json.loads(row_json)
        if not is_food_category(row.get("category")):
            continue
        if row.get("offer_price") is not None and offers_from and fetched_at < offers_from:
            # The latest complete offer pass no longer listed this campaign.
            for key in _OFFER_FIELDS:
                row[key] = None
        meta = json.loads(product_json)
        merged.append((merge_row(row, meta), datetime.fromisoformat(fetched_at)))
    return merged


_OFFER_FIELDS = ("offer_price", "offer_label", "offer_valid_until")


def catalog_ready(store: CatalogStore, *, store_ids: Sequence[str], min_products: int) -> bool:
    """True once a full round has finished and every store has usable food rows."""

    if store.get("round_completed_at") is None:
        return False
    for store_id in store_ids:
        count = store.db.execute(
            "SELECT count(*) FROM rows r JOIN meta m ON m.chain = "
            "substr(r.store_id, 1, instr(r.store_id, ':') - 1) AND m.product_id = r.product_id "
            "WHERE r.store_id = ? AND m.product_json IS NOT NULL",
            (store_id,),
        ).fetchone()[0]
        if count < min_products:
            return False
    return True


def merge_row(row: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    """A catalog price row with the product's package details added."""

    out = dict(row)
    for key in ("amount", "unit", "package", "sold_by_weight"):
        if meta.get(key) is not None:
            out[key] = meta[key]
    if out.get("brand") is None and meta.get("brand") is not None:
        out["brand"] = meta["brand"]
    prices = meta.get("prices") if isinstance(meta.get("prices"), dict) else {}
    comparison = prices.get("comparison") if isinstance(prices.get("comparison"), dict) else {}
    try:
        ratio = float(comparison["price"]) / float(prices["regular"])
        own = float(row["price"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        ratio = own = None  # type: ignore[assignment]
    if ratio and own and comparison.get("unit"):
        out["comparison"] = {"price": round(own * ratio, 2), "unit": comparison["unit"]}
    return out


__all__ = [
    "CatalogStore",
    "FOOD_CATEGORIES",
    "QuotaExhausted",
    "StepReport",
    "catalog_products",
    "catalog_ready",
    "default_catalog_path",
    "is_food_category",
    "merge_row",
    "run_catalog_step",
]
