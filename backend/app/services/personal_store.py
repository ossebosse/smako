"""Private state in the existing plan database; all writes use its transaction.

No email identity, credentials, price universe write or telemetry belongs here.
The random record ID is also the existing erasure ledger's restore target.
"""

from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from uuid import uuid4

from app.models.personal import PantryItem, TasteProfile

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
    if plan_id in state["events"]:
        raise PersonalConflict("Bekräftat inköp är bokfört. Skapa en ny plan för nya behov.")
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

    def inventory_action(self, owner, saved, action, pantry_revision):
        with self.plans._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            state = read_state(connection, owner)
            event = state["events"].get(saved.plan_id, {})
            # Check semantic idempotency BEFORE revision: even a double click using
            # the previous revision is acknowledged without booking any quantity twice.
            if event.get(action):
                return state
            latest = connection.execute(
                "SELECT MAX(revision) FROM consumer_plan_revisions WHERE plan_id = ?",
                (saved.plan_id,),
            ).fetchone()[0]
            if latest != saved.revision:
                raise PersonalConflict("Planen ändrades. Läs senaste revisionen före bokföring.")
            if action == "release":
                state["reservations"].pop(saved.plan_id, None)
            elif action == "purchase":
                if event.get("consume"):
                    raise PersonalConflict("Planens förbrukning är redan bokförd.")
                rows = list(state["reservations"].get(saved.plan_id, []))
                if saved.plan.personal.allocations and not rows:
                    raise PersonalConflict("Planen är frigjord. Beräkna om innan inköp.")
                for group in saved.plan.optimized_basket.stores:
                    for item in group.items:
                        identity = uuid4().hex
                        need = next(
                            n for n in saved.plan.personal.needs if n["key"] == item.ingredient
                        )
                        item_key = need.get("selected_product_key")
                        quantity = item.purchased_usable_quantity
                        if quantity is None or item.unit != item.purchased_unit:
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
                        rows.append(
                            {
                                "item_id": identity,
                                "quantity": item.required_quantity,
                                "unit": item.unit,
                                "name": need["name"],
                            }
                        )
                state["reservations"][saved.plan_id] = rows
            elif action == "consume":
                if saved.plan.optimized_basket.total and not event.get("purchase"):
                    raise PersonalConflict("Bekräfta verkligt inköp före planens förbrukning.")
                rows = state["reservations"].get(saved.plan_id)
                if rows is None:
                    raise PersonalConflict("Planens reservation är frigjord. Beräkna om först.")
                amounts = defaultdict(float)
                for row in rows:
                    amounts[row["item_id"]] += row["quantity"]
                for item in state["items"]:
                    if amounts[item["id"]] > item["quantity"] + 1e-8:
                        raise PersonalConflict("Lagret räcker inte för bekräftad förbrukning.")
                    item["quantity"] = max(0, item["quantity"] - amounts[item["id"]])
                state["reservations"].pop(saved.plan_id, None)
            else:
                raise ValueError("Okänd lageråtgärd.")
            if action != "release":
                state["events"][saved.plan_id] = {**event, action: True}
            return write_state(connection, owner, state, pantry_revision)
