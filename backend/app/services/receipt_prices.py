"""Store prices and items members' receipts taught Smako, usable at once.

Owner decisions 2026-11-24 (member_rewards.py): a scanned receipt line may
teach Smako a store's own price for a product it has, or that a store sells a
product Smako only knew from another store. Both reach planning on the next
request, without rebuilding the shared price data:

* a store price is applied in the request-local pricing step
  (``user_pricing.price_candidate_for_context``). A lower price is a campaign
  "according to receipts", dated while it is temporary; a higher price
  replaces the ordinary price only once it is persistent.
* a new item whose barcode Smako knows from another store is planned in the
  receipt's store as a copy of that product (``store_copies``), so its
  declaration, size and allergen checks are the other store's product's.
  An item whose barcode Smako has never seen is not planned here.

The rows are read from the plan database at most every REFRESH_SECONDS per
process and only again when ``member_store_items_version`` changes; caches
carry ``version()`` through the price universe's freshness identity.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from datetime import date, timedelta

from app.models import OfferKind, OfferMetadata

REFRESH_SECONDS = 2.0
_LOCK = threading.Lock()
_STATE: dict = {"checked": -1e9, "path": None, "version": 0, "prices": {}, "items": {}}


def gtin_key(value) -> str | None:
    digits = "".join(c for c in str(value or "") if c.isdigit()).lstrip("0")
    return digits or None


def _path():
    try:
        from app.config import get_settings

        return get_settings().plan_store_path
    except (ImportError, AttributeError, ValueError):  # no settings in this process: nothing learned
        return None


def _rows(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as db:
        db.row_factory = sqlite3.Row
        found = db.execute("SELECT version FROM member_store_items_version WHERE id=1").fetchone()
        version = found["version"] if found else 0
        if version == _STATE["version"] and _STATE["path"] == path:
            return version, None
        return version, db.execute("""SELECT store_key, store_ids, gtin, kind, name, price, last_seen, persistent_since
                                      FROM member_store_items""").fetchall()


def _state():
    path = _path()
    now = time.monotonic()
    with _LOCK:
        if path is None:
            _STATE.update(path=None, version=0, prices={}, items={})
            return _STATE
        if _STATE["path"] == path and now - _STATE["checked"] < REFRESH_SECONDS:
            return _STATE
        _STATE["checked"] = now
        try:
            version, rows = _rows(path)
        except sqlite3.Error:  # no database or no receipt tables yet
            _STATE.update(path=path, version=0, prices={}, items={})
            return _STATE
        if rows is None:
            return _STATE
        import json

        from app.services.planning_rules import load

        rules = load()
        prices, items = {}, {}
        for row in rows:
            key = gtin_key(row["gtin"])
            if key is None:
                continue
            last = date.fromisoformat(row["last_seen"])
            entry = {"name": row["name"], "price": float(row["price"]), "last_seen": last, "store": row["store_key"],
                     "persistent": bool(row["persistent_since"]),
                     "forget_after": last + timedelta(days=rules.receipt_item_forget_days),
                     "temporary_until": last + timedelta(days=rules.receipt_item_temporary_days)}
            for context in json.loads(row["store_ids"]):
                if row["kind"] == "price":
                    prices[(context, key)] = entry
                else:
                    items.setdefault(key, {})[context] = entry
        _STATE.update(path=path, version=version, prices=prices, items=items)
        return _STATE


def version() -> int:
    """Changes whenever receipts teach Smako something; 0 when nothing is learned."""
    return int(_state()["version"] or 0)


def has_items() -> bool:
    """Whether any store is known from receipts to sell a barcode it lacks in Smako's data."""
    return bool(_state()["items"])


def _usable(entry, on_date):
    """(usable, temporary) on the purchase day."""
    if on_date > entry["forget_after"] or on_date < entry["last_seen"]:
        return False, False
    if entry["persistent"]:
        return True, False
    return on_date <= entry["temporary_until"], True


def _offer(entry, temporary):
    seen = f"{entry['last_seen'].day}/{entry['last_seen'].month}"
    return OfferMetadata(
        kind=OfferKind.CAMPAIGN,
        description=(f"Tillfälligt pris enligt kvitto {seen}, brukar bara gälla några dagar" if temporary
                     else f"Butikens pris enligt kvitton, senast {seen}"),
        price=entry["price"],
        source_confidence="member_receipt",
        valid_from=entry["last_seen"],
        valid_to=entry["temporary_until"] if temporary else None,
    )


def apply_store_price(candidate, on_date: date):
    """The candidate with the store's price from receipts, if Smako has learned one."""
    key = gtin_key(getattr(candidate, "gtin", None))
    if key is None:
        return candidate
    state = _state()
    if not state["prices"]:
        return candidate
    entry = state["prices"].get((candidate.store_id, key))
    if entry is None or getattr(candidate, "sale_model", None) in {"sold_by_weight", "variable_weight_package"}:
        return candidate
    usable, temporary = _usable(entry, on_date)
    if not usable:
        return candidate
    ordinary = candidate.price
    if ordinary is not None and entry["price"] >= ordinary:
        if temporary or abs(entry["price"] - ordinary) < 0.005:
            return candidate
        # Confirmed by two members: the store's ordinary price is higher than Smako's source.
        # Its offers still apply; the source's own current price does not.
        return candidate.model_copy(update={"price": entry["price"], "effective_price": entry["price"],
                                            "sale_price": None,
                                            "offers": [o for o in candidate.offers if o.price < entry["price"]]})
    return candidate.model_copy(update={"offers": [*candidate.offers, _offer(entry, temporary)]})


def store_copies(candidate, allowed_store_ids, stores, on_date: date):
    """Copies of a product for stores whose receipts show they sell it (same barcode)."""
    key = gtin_key(getattr(candidate, "gtin", None))
    if key is None:
        return []
    state = _state()
    contexts = state["items"].get(key) if state["items"] else None
    if not contexts:
        return []
    by_id = {s.store_id: s for s in stores}
    copies, seen_stores = [], set()
    for context, entry in contexts.items():
        store = by_id.get(context)
        if context == candidate.store_id or context not in allowed_store_ids or store is None:
            continue
        if entry["store"] in seen_stores:  # one copy per store, even with several price contexts
            continue
        usable, temporary = _usable(entry, on_date)
        if not usable:
            continue
        seen_stores.add(entry["store"])
        provenance = candidate.source_provenance
        if provenance is not None:
            from datetime import UTC, datetime
            from datetime import time as day_start

            provenance = provenance.model_copy(update={
                "source_provider": "member_receipt", "source_channel": "receipt",
                "source_snapshot_id": f"receipt:{state['version']}:{key}",
                "source_observed_at": datetime.combine(entry["last_seen"], day_start(12), UTC),
                "chain": getattr(store, "chain", None) or provenance.chain, "store_id": context,
                "store_name": store.name, "provider_store_id": None, "price_context": None,
                "price_context_evidence": None, "fallback_used": False})
        copies.append(candidate.model_copy(update={
            "source_provenance": provenance,
            "store_id": context, "store_name": store.name, "chain": getattr(store, "chain", None) or candidate.chain,
            # The other store's offers and member prices are not this store's.
            "price": None if temporary else entry["price"], "effective_price": entry["price"], "member_price": None,
            "offers": [_offer(entry, temporary)] if temporary else [], "promotion_groups": (),
            "selected_price_contract_id": None,
        }))
    return copies


def reset_for_tests():
    with _LOCK:
        _STATE.update(checked=-1e9, path=None, version=0, prices={}, items={})
