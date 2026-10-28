"""Private state in the existing plan database; all writes use its transaction.

No email identity, credentials, price universe write or telemetry belongs here.
The random record ID is also the existing erasure ledger's restore target.
"""

from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from math import isfinite
from uuid import uuid4

from app.models.personal import EggSeparation, PantryItem, PreparedOrigin, TasteProfile

SCHEMA = """
CREATE TABLE IF NOT EXISTS personal_private_state (
    id TEXT PRIMARY KEY,
    owner_actor_hash TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL,
    payload TEXT NOT NULL
);
"""


class PersonalConflict(ValueError):
    pass


def demand_key(row):
    """A slot's consumed ingredient remains consumed across recipe revisions."""
    from app.services.ingredient_normalizer import canonicalize_ingredient_name

    return sha256(
        json.dumps(
            [
                row["source"],
                canonicalize_ingredient_name(row["name"]),
                row["unit"],
                row.get("product_key"),
                sorted(row.get("properties", [])),
                *([sorted(row["alternatives"])] if row.get("alternatives") else []),
                *(["purchase_units"] if row.get("purchase_units") else []),
            ],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def consumed_demands(state, plan_id):
    return [
        row
        for event in state.get("ledger", [])
        if event["plan_id"] == plan_id and event["action"] == "consume"
        for row in event["rows"]
    ]


def event_recorded(state, plan_id, revision, action, operation_id=None):
    return any(
        e["plan_id"] == plan_id
        and e["action"] == action
        and e["operation_id"] == (operation_id or f"{action}:{revision}")
        for e in state.get("ledger", [])
    )


def revision_purchased(state, plan_id, revision):
    return any(
        e["plan_id"] == plan_id and e["revision"] == revision and e["action"] == "purchase"
        for e in state.get("ledger", [])
    )


def read_state(connection, owner):
    row = connection.execute(
        "SELECT * FROM personal_private_state WHERE owner_actor_hash = ?", (owner,)
    ).fetchone()
    if row is None:
        return {
            "id": None,
            "revision": 0,
            "profile": None,
            "items": [],
            "reservations": {},
            "events": {},
        }
    return {"id": row["id"], "revision": row["revision"], **json.loads(row["payload"])}


def write_state(connection, owner, state, expected):
    current = read_state(connection, owner)
    if current["revision"] != expected:
        raise PersonalConflict(
            "Skafferiet eller reservationerna ändrades. Läs om och beräkna igen."
        )
    state = deepcopy(state)
    identity = current["id"] or uuid4().hex
    state.pop("id", None)
    state.pop("revision", None)
    connection.execute(
        """INSERT INTO personal_private_state(id, owner_actor_hash, revision, payload)
        VALUES (?, ?, ?, ?) ON CONFLICT(owner_actor_hash)
        DO UPDATE SET revision=excluded.revision, payload=excluded.payload""",
        (identity, owner, expected + 1, json.dumps(state, ensure_ascii=False)),
    )
    return {"id": identity, "revision": expected + 1, **state}


def available_items(state, *, plan_id=None):
    reserved = defaultdict(float)
    for identity, rows in state["reservations"].items():
        if identity != plan_id:
            for row in rows:
                reserved[row["item_id"]] += row["quantity"]
    result = []
    for raw in state["items"]:
        item = PantryItem.model_validate(raw)
        result.append(
            {
                **item.model_dump(),
                "reserved": reserved[item.id],
                "available": max(0, item.quantity - reserved[item.id]),
            }
        )
    return result


def reserve_plan(connection, owner, plan_id, result):
    state = read_state(connection, owner)
    if state["revision"] != result.pantry_revision:
        raise PersonalConflict("Skafferiet ändrades under beräkningen. Senaste plan är bevarad.")
    available = {i["id"]: i for i in available_items(state, plan_id=plan_id)}
    allocated = defaultdict(float)
    for row in result.allocations:
        allocated[row["item_id"]] += row["quantity"]
    for identity, quantity in allocated.items():
        item = available.get(identity)
        if not item or item["unusable"] or quantity > item["available"] + 1e-8:
            raise PersonalConflict("Reservationen ryms inte i disponibelt skafferi.")
    state["reservations"][plan_id] = result.allocations
    write_state(connection, owner, state, state["revision"])


class PersonalStore:
    def __init__(self, plan_store):
        self.plans = plan_store

    def read(self, owner):
        self.plans._validate_owner_actor_hash(owner)
        with self.plans._connect() as connection:
            return read_state(connection, owner)

    def update_pantry(self, owner, revision, items):
        if len({i.id for i in items}) != len(items):
            raise PersonalConflict("Skafferivarornas ID måste vara unika.")
        with self.plans._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = read_state(connection, owner)
            reserved = defaultdict(float)
            for rows in state["reservations"].values():
                for row in rows:
                    reserved[row["item_id"]] += row["quantity"]
            old = {i["id"]: i for i in state["items"]}
            new = {i.id: i for i in items}
            for item in items:
                if item.prepared_origin and item.prepared_origin.model_dump() != old.get(item.id, {}).get("prepared_origin"):
                    raise PersonalConflict("Beredningsursprung skapas endast av bokförd uppmätt beredning.")
                if old.get(item.id, {}).get("prepared_origin") and (
                    not item.prepared_origin or any(getattr(item, k) != old[item.id][k]
                                                   for k in ("name", "unit", "product_key", "form", "food"))
                ):
                    raise PersonalConflict("Beredningsursprung och utfallsidentitet får inte skrivas om.")
            for identity, quantity in reserved.items():
                item = new.get(identity)
                if quantity and (
                    not item
                    or item.unusable
                    or item.quantity < quantity
                    or any(
                        getattr(item, k) != old[identity][k]
                        for k in ("name", "unit", "product_key", "food")
                    )
                ):
                    raise PersonalConflict(
                        "Varan är reserverad. Frigör berörd plan innan ändringen."
                    )
            state["items"] = [i.model_dump() for i in items]
            return write_state(connection, owner, state, revision)

    def update_profile(self, owner, revision, profile: TasteProfile):
        with self.plans._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = read_state(connection, owner)
            state["profile"] = profile.model_dump()
            return write_state(connection, owner, state, revision)

    def update_shopping(self, owner, revision, items):
        """Owner-bound draft and bounded frequently chosen rows; never books stock."""
        self.plans._validate_owner_actor_hash(owner)
        rows = [item.model_dump() for item in items]

        def identity(row):
            return sha256(json.dumps({k: v for k, v in row.items() if k != "id"},
                                     sort_keys=True, ensure_ascii=False).encode()).hexdigest()

        with self.plans._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = read_state(connection, owner)
            # Repeated identical writes do not inflate frequencies or reservations.
            if "shopping_items" in state and state["shopping_items"] == rows:
                return state
            prior = {identity(row) for row in state.get("shopping_items", [])}
            common = {row["key"]: row for row in state.get("shopping_common", [])}
            now = datetime.now(UTC).isoformat()
            for row in rows:
                key = identity(row)
                if key in prior:
                    continue
                previous = common.get(key, {})
                common[key] = {"key": key, "item": row, "count": min(previous.get("count", 0) + 1, 1000000),
                               "last_used": now}
                prior.add(key)
            state["shopping_items"] = rows
            state["shopping_common"] = sorted(common.values(),
                key=lambda row: (row["count"], row["last_used"], row["key"]), reverse=True)[:50]
            return write_state(connection, owner, state, revision)

    def inventory_action(
        self, owner, saved, action, pantry_revision, *, operation_id=None, consume_fraction=1, measured_purchase_quantities=None,
        preparation=None,
    ):
        if preparation is not None:
            preparation = EggSeparation.model_validate(preparation)
        if (action == "prepare") != (preparation is not None) or (action == "prepare" and not operation_id):
            raise PersonalConflict("Beredning kräver ett unikt ID och uppmätt insats/utfall.")
        payload = {"measured_purchase_quantities": measured_purchase_quantities or {},
                   "preparation": preparation.model_dump(mode="json") if preparation else None}
        with self.plans._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = read_state(connection, owner)
            self._upgrade_ledger(connection, owner, state, saved)
            event = state["events"].get(saved.plan_id, {})
            # Check semantic idempotency BEFORE revision: even a double click using
            # the previous revision is acknowledged without booking any quantity twice.
            if event_recorded(state, saved.plan_id, saved.revision, action, operation_id):
                prior = next(
                    e
                    for e in state["ledger"]
                    if e["plan_id"] == saved.plan_id
                    and e["action"] == action
                    and e["operation_id"] == (operation_id or f"{action}:{saved.revision}")
                )
                if (
                    prior["revision"] != saved.revision
                    or prior.get("fraction", 1) != consume_fraction
                    or ("payload" in prior and prior["payload"] != payload)
                ):
                    raise PersonalConflict("Åtgärds-ID har redan använts med annat innehåll.")
                return state
            latest = connection.execute(
                "SELECT MAX(revision) FROM consumer_plan_revisions WHERE plan_id = ?",
                (saved.plan_id,),
            ).fetchone()[0]
            if latest != saved.revision:
                raise PersonalConflict("Planen ändrades. Läs senaste revisionen före bokföring.")
            if action == "release":
                state["reservations"].pop(saved.plan_id, None)
                booked = []
            elif action == "purchase":
                if revision_purchased(state, saved.plan_id, saved.revision):
                    raise PersonalConflict(
                        "Revisionens inköp är redan bokfört. Räkna om före nästa köp."
                    )
                rows = list(state["reservations"].get(saved.plan_id, []))
                if saved.plan.personal.allocations and not rows:
                    raise PersonalConflict("Planen är frigjord. Beräkna om innan inköp.")
                booked = []
                demands = self._remaining_purchase_demands(saved, rows)
                for group in saved.plan.optimized_basket.stores:
                    for item in group.items:
                        identity = uuid4().hex
                        need = next(
                            n for n in saved.plan.personal.needs if n["key"] == item.ingredient
                        )
                        item_key = need.get("selected_product_key")
                        if item.purchase_units:
                            raise PersonalConflict("Verifiera innehållets verkliga mängd före bokföring i skafferiet. Köpförpackningar är inte ätbara stycken.")
                        if item.conditional_variant_choice:
                            raise PersonalConflict('Välj den faktiskt köpta produktvarianten före bokföring i skafferiet.')
                        quantity = item.purchased_usable_quantity
                        if item.quantity_confidence == 'estimated' or need.get("preparation") or item.unit != item.purchased_unit:
                            quantity = (measured_purchase_quantities or {}).get(item.store_id + '|' + item.product_id + '|' + item.ingredient)
                            if quantity is None or not isfinite(quantity) or quantity < item.required_quantity:
                                raise PersonalConflict('Ange verklig användbar inköpsmängd som täcker behovet; annars räkna om planen.')
                        if quantity is None:
                            raise PersonalConflict(
                                "Verklig inköpt mängd behöver verifieras före bokföring."
                            )
                        state["items"].append(
                            PantryItem(
                                id=identity,
                                name=need["name"],
                                quantity=quantity,
                                unit=item.unit,
                                product_key=item_key,
                                food=need["food"],
                            ).model_dump()
                        )
                        booked.append(
                            {
                                "item_id": identity,
                                "name": need["name"],
                                "quantity": quantity,
                                "unit": item.unit,
                                "product_key": item_key,
                                "checkout": item.model_dump(mode="json"),
                            }
                        )
                        remaining = item.required_quantity
                        for demand in demands:
                            if demand.get("preparation"):
                                continue
                            if (
                                demand["source"] not in need["sources"]
                                or demand["unit"] != item.unit
                            ):
                                continue
                            # Each normalized group names precisely the compatible demands.
                            if demand.get("purchase_key") != need["key"]:
                                continue
                            used = min(remaining, demand["quantity"])
                            if used <= 0:
                                continue
                            rows.append(
                                {
                                    "item_id": identity,
                                    "quantity": used,
                                    "unit": item.unit,
                                    "name": need["name"],
                                    "source": demand["source"],
                                    "demand_key": demand["demand_key"],
                                }
                            )
                            remaining -= used
                            demand["quantity"] -= used
                        if need.get("preparation"):
                            prep = need["preparation"]
                            used = prep["purchase_input_quantity_g"]
                            if abs(remaining - used) > 1e-7:
                                raise PersonalConflict("Beredningsinsatsen stämmer inte med inköpet.")
                            if used > 1e-8:
                                rows.append({"item_id": identity, "quantity": used, "unit": "g", "name": "ägg",
                                    "source": prep["id"], "demand_key": prep["id"], "kind": "preparation_input",
                                    "method": prep["method"], "product_key": item_key})
                            remaining -= used
                        if remaining > 1e-7:
                            raise PersonalConflict(
                                "Inköpet saknar verifierad koppling till planens behov."
                            )
                state["reservations"][saved.plan_id] = rows
            elif action == "prepare":
                booked, preparation_record = self._prepare_eggs(state, saved, preparation, operation_id)
            elif action == "consume":
                if any(g.items for g in saved.plan.optimized_basket.stores) and not revision_purchased(
                    state, saved.plan_id, saved.revision
                ):
                    raise PersonalConflict("Bekräfta verkligt inköp före planens förbrukning.")
                rows = state["reservations"].get(saved.plan_id)
                if rows is None:
                    raise PersonalConflict("Planens reservation är frigjord. Beräkna om först.")
                if any(r.get("kind") == "preparation_input" for r in rows):
                    raise PersonalConflict("Separera och bokför uppmätt gula/vita före förbrukning.")
                for demand in self._unconsumed_component_demands(state, saved):
                    reserved = sum(r["quantity"] for r in rows if r.get("demand_key") == demand["demand_key"])
                    if reserved + 1e-7 < demand["quantity"]:
                        raise PersonalConflict("Uppmätt beredningsutfall täcker inte återstående behov. Räkna om eller komplettera.")
                amounts = defaultdict(float)
                booked = []
                for row in rows:
                    used = row["quantity"] * consume_fraction
                    amounts[row["item_id"]] += used
                    booked.append({**row, "quantity": used})
                    row["quantity"] -= used
                for item in state["items"]:
                    if amounts[item["id"]] > item["quantity"] + 1e-8:
                        raise PersonalConflict("Lagret räcker inte för bekräftad förbrukning.")
                    item["quantity"] = max(0, item["quantity"] - amounts[item["id"]])
                state["reservations"][saved.plan_id] = [r for r in rows if r["quantity"] > 1e-8]
            else:
                raise ValueError("Okänd lageråtgärd.")
            if action != "release":
                state["events"][saved.plan_id] = {**event, action: True}
            state.setdefault("ledger", []).append(
                {
                    "plan_id": saved.plan_id,
                    "revision": saved.revision,
                    "action": action,
                    "operation_id": operation_id or f"{action}:{saved.revision}",
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "rows": booked,
                    "fraction": consume_fraction,
                    "payload": payload,
                    **({"preparation": preparation_record} if action == "prepare" else {}),
                    "total": saved.plan.optimized_basket.total if action == "purchase" else None,
                }
            )
            return write_state(connection, owner, state, pantry_revision)

    @staticmethod
    def _unconsumed_component_demands(state, saved):
        consumed = defaultdict(float)
        for row in consumed_demands(state, saved.plan_id):
            consumed[row["demand_key"]] += row["quantity"]
        return [{**r, "quantity": max(0, r.get("original_quantity", r["quantity"]) - consumed[r["demand_key"]])}
                for r in saved.plan.personal.remaining_demands if r.get("preparation")]

    @staticmethod
    def _prepare_eggs(state, saved, preparation, operation_id):
        from app.services.egg_preparation import METHOD

        if not saved.plan.personal.preparations:
            raise PersonalConflict("Planen saknar granskad äggberedning.")
        rows = state["reservations"].get(saved.plan_id)
        if rows is None:
            raise PersonalConflict("Planens reservation är frigjord. Räkna om först.")
        inputs = []
        available = {i["id"]: i for i in available_items(state, plan_id=saved.plan_id)}
        allowed = {a["product_key"] for p in saved.plan.personal.preparations for a in p["input_allocations"]}
        allowed.update(n["selected_product_key"] for n in saved.plan.personal.needs if n.get("preparation"))
        for identity, quantity in preparation.inputs.items():
            item = available.get(identity)
            protected = sum(r["quantity"] for r in rows if r["item_id"] == identity and r.get("kind") != "preparation_input")
            if (not item or item["unusable"] or item["unit"] != "g" or item.get("prepared_origin")
                    or not item.get("product_key") or item["product_key"] not in allowed
                    or quantity > item["available"] - protected + 1e-7):
                raise PersonalConflict("Ägginsatsen saknar kvalificerat disponibelt parti eller är reserverad för annat behov.")
            inputs.append({"item_id": identity, "quantity": quantity, "unit": "g", "product_key": item["product_key"]})
        keys = {r["product_key"] for r in inputs}
        if len(keys) != 1:
            raise PersonalConflict("Separera olika produktidentiteter i egna uppmätta beredningsomgångar.")
        product_key = next(iter(keys))
        compatible_demands = set()
        for planned in saved.plan.personal.preparations:
            source_keys = {a["product_key"] for a in planned["input_allocations"]}
            source_keys.update(n["selected_product_key"] for n in saved.plan.personal.needs
                               if n.get("preparation", {}).get("id") == planned["id"])
            if product_key in source_keys:
                compatible_demands.update(r["demand_key"] for r in planned["outputs"])
        # Book physical reality even for a short yield. Readiness below remains
        # blocked until measured component stock covers the original demands.
        for item in state["items"]:
            if item["id"] in preparation.inputs:
                item["quantity"] = max(0, item["quantity"] - preparation.inputs[item["id"]])
        state["reservations"][saved.plan_id] = rows = [r for r in rows if not (
            r.get("kind") == "preparation_input" and r.get("product_key") == product_key)]
        demands = PersonalStore._unconsumed_component_demands(state, saved)
        booked = []
        for name, quantity in (("äggula", preparation.yolk_g), ("äggvita", preparation.white_g)):
            if quantity <= 0:
                continue
            item = PantryItem(name=name, quantity=quantity, unit="g", form="raw_edible",
                prepared_origin=PreparedOrigin(method=METHOD, product_key=next(iter(keys)), operation_id=operation_id))
            state["items"].append(item.model_dump())
            booked.append({"item_id": item.id, "name": name, "quantity": quantity, "unit": "g",
                           "prepared_origin": item.prepared_origin.model_dump()})
            remaining = quantity
            for demand in demands:
                if demand["name"] != name or demand["demand_key"] not in compatible_demands:
                    continue
                already = sum(r["quantity"] for r in rows if r.get("demand_key") == demand["demand_key"])
                used = min(remaining, max(0, demand["quantity"] - already))
                if used > 1e-8:
                    rows.append({"item_id": item.id, "name": name, "quantity": used, "unit": "g",
                        "source": demand["source"], "demand_key": demand["demand_key"],
                        "prepared_origin": item.prepared_origin.model_dump()})
                    remaining -= used
        return booked, {"method": METHOD, "inputs": inputs, "outputs": booked,
                        "loss_g": max(0, sum(preparation.inputs.values()) - preparation.yolk_g - preparation.white_g)}

    @staticmethod
    def _remaining_purchase_demands(saved, allocations):
        demands = deepcopy(saved.plan.personal.remaining_demands)
        if not demands:
            # Old plans predate structured allocation keys. Reconstruct only their
            # explicit remaining purchase needs, without changing stock or history.
            for need in saved.plan.personal.needs:
                source = need["sources"][0]
                row = {
                    "source": source,
                    "name": need["name"],
                    "unit": need["unit"],
                    "quantity": need["quantity"],
                    "purchase_key": need["key"],
                }
                row["demand_key"] = demand_key(row)
                demands.append(row)
            return demands
        reserved = defaultdict(float)
        for row in allocations:
            reserved[row.get("demand_key")] += row["quantity"]
        for row in demands:
            row["quantity"] = max(0, row["quantity"] - reserved[row["demand_key"]])
        return demands

    @staticmethod
    def _upgrade_ledger(connection, owner, state, saved):
        """Preserve old boolean events with their immutable original revision quote.

        The previous release prohibited edits after booking. It is consequently
        safe to associate an unconverted event with the last pre-upgrade revision.
        No physical quantities are added or removed by this conversion.
        """
        ledger = state.setdefault("ledger", [])
        # Upgrade old reservation attribution before recording any consumption.
        # Existing plan allocations identify the original pantry lots; remaining
        # reserved lots were created by the old purchase transaction.
        original_ids = {r["item_id"] for r in saved.plan.personal.allocations}
        reservations = state["reservations"].get(saved.plan_id, [])
        if any("demand_key" not in r for r in reservations):
            from app.services.ingredient_normalizer import (
                IngredientNormalizer,
                canonicalize_ingredient_name,
            )

            demands = []
            for slot in saved.plan.personal.slots:
                if slot.recipe:
                    for ingredient in IngredientNormalizer().normalize_and_aggregate([slot.recipe]):
                        row = {
                            "source": slot.id,
                            "name": ingredient.canonical_name,
                            "unit": ingredient.unit,
                            "quantity": ingredient.required_quantity,
                        }
                        demands.append({**row, "demand_key": demand_key(row)})
            for extra in saved.request.personal.extras:
                row = {**extra.model_dump(), "source": extra.id, "name": extra.query}
                demands.append({**row, "demand_key": demand_key(row)})
            upgraded = []
            for reservation in reservations:
                remaining = reservation["quantity"]
                for demand in demands:
                    if (
                        demand["unit"] != reservation["unit"]
                        or (reservation.get("source") and reservation["source"] != demand["source"])
                        or canonicalize_ingredient_name(reservation["name"])
                        != canonicalize_ingredient_name(demand["name"])
                    ):
                        continue
                    used = min(remaining, demand["quantity"])
                    if used > 0:
                        upgraded.append(
                            {
                                **reservation,
                                "quantity": used,
                                "source": demand["source"],
                                "demand_key": demand["demand_key"],
                            }
                        )
                        remaining -= used
                        demand["quantity"] -= used
                if remaining > 1e-7:
                    raise PersonalConflict(
                        "Äldre reservation saknar entydig behovskoppling. Frigör och räkna om planen."
                    )
            state["reservations"][saved.plan_id] = upgraded
        old = state["events"].get(saved.plan_id, {})
        for action in ("purchase", "consume"):
            if not old.get(action) or any(
                e["plan_id"] == saved.plan_id and e["action"] == action for e in ledger
            ):
                continue
            if action == "purchase":
                rows = [
                    {
                        "checkout": i.model_dump(mode="json"),
                        "quantity": i.purchased_usable_quantity,
                        "unit": i.unit,
                        "name": i.product_name,
                    }
                    for g in saved.plan.optimized_basket.stores
                    for i in g.items
                ]
                lots = {r["item_id"] for r in reservations} - original_ids
                state.setdefault("legacy_purchase_lots", {})[saved.plan_id] = sorted(lots)
            else:
                from app.services.ingredient_normalizer import IngredientNormalizer

                rows = []
                for slot in saved.plan.personal.slots:
                    if slot.recipe:
                        for ingredient in IngredientNormalizer().normalize_and_aggregate(
                            [slot.recipe]
                        ):
                            row = {
                                "source": slot.id,
                                "name": ingredient.canonical_name,
                                "unit": ingredient.unit,
                                "quantity": ingredient.required_quantity,
                            }
                            rows.append({**row, "demand_key": demand_key(row)})
                for extra in saved.request.personal.extras:
                    row = {**extra.model_dump(), "source": extra.id, "name": extra.query}
                    rows.append({**row, "demand_key": demand_key(row)})
            ledger.append(
                {
                    "plan_id": saved.plan_id,
                    "revision": saved.revision,
                    "action": action,
                    "operation_id": f"{action}:{saved.revision}",
                    "recorded_at": None,
                    "legacy_time_unknown": True,
                    "rows": rows,
                    "total": saved.plan.optimized_basket.total if action == "purchase" else None,
                }
            )

    def prepare_revision(self, owner, saved):
        """Persist legacy bookkeeping conversion before a new revision can exist."""
        with self.plans._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = read_state(connection, owner)
            before = deepcopy(state)
            self._upgrade_ledger(connection, owner, state, saved)
            # An empty ledger alone is not a meaningful migration.
            if state.get("ledger") and state != before:
                return write_state(connection, owner, state, state["revision"])
            return state
