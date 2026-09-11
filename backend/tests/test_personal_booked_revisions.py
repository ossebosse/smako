"""Booked purchases are facts; revisions change only future needs/reservations."""

from copy import deepcopy

import pytest
from app.models.personal import MealSettings, MealSlot
from app.models.recipe import RecipeIngredient
from app.services.personal_store import PersonalConflict, PersonalStore, available_items
from app.services.plan_store import PlanStore

from backend.tests.test_personal_planning_v2 import prepared, product, recipe, request, run

OWNER = "c" * 64


def milk_rice(milk, rice):
    return recipe(
        ingredients=[
            RecipeIngredient(name="mjölk", quantity=milk, unit="ml"),
            RecipeIngredient(name="ris", quantity=rice, unit="g"),
        ]
    )


def setup_plan(tmp_path):
    p = prepared(product("mjölk", 1000, "ml", 20), product("ris", 500, "g", 15))
    plans = PlanStore(tmp_path / "plans.sqlite")
    private = PersonalStore(plans)
    req = request(
        slots=[MealSlot(id="dinner", day=1, meal_type="dinner", recipe=milk_rice(2000, 1000))],
        meals=[MealSettings(count=1, servings=1)],
    )
    saved = plans.create(req, run(p, req), owner_actor_hash=OWNER)
    stock = private.read(OWNER)
    stock = private.inventory_action(OWNER, saved, "purchase", stock["revision"])
    return p, plans, private, saved, stock


def revise(p, plans, private, saved, food, mutation_key=None):
    stock = private.read(OWNER)
    req = saved.request.model_copy(deep=True)
    req.personal.pantry_revision = stock["revision"]
    req.personal.slots[0].recipe = food
    result = run(p, req, stock, plan_id=saved.plan_id)
    new = plans.append(
        plan_id=saved.plan_id,
        request=req,
        response=result,
        operation="recipe_replaced",
        expected_parent=saved.revision,
        owner_actor_hash=OWNER,
        mutation_key=mutation_key,
    )
    return new


def test_edit_purchased_milk_rice_preserves_price_and_only_buys_topup(tmp_path):
    p, plans, private, saved, stock = setup_plan(tmp_path)
    history = deepcopy(stock["ledger"])
    assert history[0]["total"] == 70
    new = revise(p, plans, private, saved, milk_rice(1000, 1200), "change-1")
    assert new.revision == 2 and new.plan.optimized_basket.total == 15
    item = new.plan.optimized_basket.stores[0].items[0]
    assert item.product_name == "ris" and item.required_quantity == 200
    assert item.purchased_usable_quantity == 500
    updated = private.read(OWNER)
    assert updated["ledger"] == history
    assert sum(i["available"] for i in available_items(updated) if i["unit"] == "ml") == 1000
    assert plans.get_owned(saved.plan_id, owner_actor_hash=OWNER, revision=1) == saved
    topped = private.inventory_action(OWNER, new, "purchase", updated["revision"])
    assert [e["total"] for e in topped["ledger"]] == [70, 15]
    assert private.inventory_action(OWNER, new, "purchase", updated["revision"]) == topped
    assert topped["ledger"][0] == history[0]
    third = revise(p, plans, private, new, milk_rice(1000, 1200))
    assert third.plan.optimized_basket.total == 0
    assert sum(i["quantity"] for i in topped["items"] if i["unit"] == "g") == 1500


def test_partial_consume_remove_restore_and_two_tabs(tmp_path):
    p, plans, private, saved, stock = setup_plan(tmp_path)
    consumed = private.inventory_action(
        OWNER, saved, "consume", stock["revision"], operation_id="partial-1", consume_fraction=0.25
    )
    assert sum(r["quantity"] for r in consumed["ledger"][-1]["rows"] if r["unit"] == "ml") == 500
    assert (
        private.inventory_action(
            OWNER, saved, "consume", 0, operation_id="partial-1", consume_fraction=0.25
        )
        == consumed
    )
    with pytest.raises(PersonalConflict):
        private.inventory_action(
            OWNER, saved, "consume", 0, operation_id="partial-1", consume_fraction=0.5
        )
    edited = revise(p, plans, private, saved, milk_rice(1000, 1200))
    assert edited.plan.optimized_basket.total == 15
    assert sum(a["quantity"] for a in edited.plan.personal.allocations if a["unit"] == "ml") == 500
    with pytest.raises(PersonalConflict):
        revise(p, plans, private, saved, milk_rice(1500, 1000))
    removed = revise(p, plans, private, edited, None)
    assert removed.plan.optimized_basket.total == 0
    assert private.read(OWNER)["reservations"][saved.plan_id] == []
    restored = revise(p, plans, private, removed, milk_rice(2000, 1000))
    assert restored.revision == 4 and restored.plan.optimized_basket.total == 0
    assert (
        sum(a["quantity"] for a in restored.plan.personal.allocations if a["unit"] == "ml") == 1500
    )
    assert private.read(OWNER)["ledger"] == consumed["ledger"]


def test_same_mutation_is_atomically_idempotent(tmp_path):
    p, plans, private, saved, _stock = setup_plan(tmp_path)
    new = revise(p, plans, private, saved, milk_rice(1000, 1200), "same-request")
    replay = revise(p, plans, private, saved, milk_rice(1000, 1200), "same-request")
    assert replay == new and plans.get_owned(saved.plan_id, owner_actor_hash=OWNER).revision == 2


def test_generator_replaces_booked_recipe_twice_preserving_history(tmp_path, monkeypatch):
    from app.config import Settings
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_personal_planning_v2 import NOW

    p, plans, private, saved, stock = setup_plan(tmp_path)
    for title, amount in (("Nytt recept ett", 1200), ("Nytt recept två", 1400)):
        replacement = milk_rice(1000, amount).model_copy(update={"name": title})
        monkeypatch.setattr(PersonalPlanner, "_candidates", lambda self, meal, r=replacement: [r])
        req = saved.request.model_copy(deep=True)
        req.personal.slots = saved.plan.personal.slots
        req.personal.pantry_revision = private.read(OWNER)["revision"]
        result = PersonalPlanner(req, Settings(price_provider="mock"), p, private.read(OWNER), plan_id=saved.plan_id, now=NOW).create(replace_slot="dinner")
        assert result.recipes[0].name == title
        saved = plans.append(plan_id=saved.plan_id, request=req, response=result, operation="recipe_replaced", expected_parent=saved.revision, owner_actor_hash=OWNER)
        assert private.read(OWNER)["ledger"] == stock["ledger"]
        assert private.read(OWNER)["items"] == stock["items"]
    assert saved.revision == 3 and saved.plan.optimized_basket.total == 15


def test_concurrent_tabs_have_one_winner_and_no_inventory_change(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    p, plans, private, saved, stock = setup_plan(tmp_path)
    barrier = Barrier(2)

    def tab(milk):
        req = saved.request.model_copy(deep=True)
        req.personal.pantry_revision = stock["revision"]
        req.personal.slots[0].recipe = milk_rice(milk, 1200)
        result = run(p, req, stock, plan_id=saved.plan_id)
        barrier.wait()
        try:
            plans.append(
                plan_id=saved.plan_id,
                request=req,
                response=result,
                operation="recipe_replaced",
                expected_parent=1,
                owner_actor_hash=OWNER,
            )
            return "saved"
        except PersonalConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(tab, (1000, 1500))) == ["conflict", "saved"]
    assert private.read(OWNER)["items"] == stock["items"]
    assert private.read(OWNER)["ledger"] == stock["ledger"]


def test_legacy_boolean_history_upgrades_without_changing_inventory(tmp_path):
    from app.services.personal_store import write_state

    p, plans, private, saved, stock = setup_plan(tmp_path)
    legacy = deepcopy(stock)
    legacy.pop("ledger")
    for row in legacy["reservations"][saved.plan_id]:
        row.pop("demand_key")
        row.pop("source")
    with plans._connect() as conn:
        write_state(conn, OWNER, legacy, stock["revision"])
    upgraded = private.prepare_revision(OWNER, saved)
    assert upgraded["items"] == stock["items"]
    assert upgraded["ledger"][0]["legacy_time_unknown"]
    assert upgraded["ledger"][0]["total"] == 70
    new = revise(p, plans, private, saved, milk_rice(1000, 1200))
    assert new.plan.optimized_basket.total == 15
    assert private.read(OWNER)["items"] == stock["items"]


def test_purchase_operation_id_cannot_book_revision_again(tmp_path):
    p, plans, private, saved, _stock = setup_plan(tmp_path)
    new = revise(p, plans, private, saved, milk_rice(1000, 1200))
    stock = private.read(OWNER)
    booked = private.inventory_action(
        OWNER, new, "purchase", stock["revision"], operation_id="purchase-custom"
    )
    assert (
        private.inventory_action(OWNER, new, "purchase", 0, operation_id="purchase-custom")
        == booked
    )
    with pytest.raises(PersonalConflict):
        private.inventory_action(
            OWNER, new, "purchase", booked["revision"], operation_id="another-purchase"
        )
    consumed = private.inventory_action(OWNER, new, "consume", booked["revision"])
    assert len(consumed["ledger"]) == 3


def test_old_backup_erasure_suppresses_ledger_and_all_revisions(tmp_path):
    import sqlite3

    from deploy.scripts.privacy_erasure_ledger import SuppressionDirective, _apply_plan_directives

    p, plans, private, saved, _stock = setup_plan(tmp_path)
    revise(p, plans, private, saved, milk_rice(1000, 1200), "private-mutation")
    stock = private.read(OWNER)
    target = tmp_path / "restored.sqlite"
    with sqlite3.connect(plans.path) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    plans.erase_owned(owner_actor_hash=OWNER)
    directives = tuple(
        SuppressionDirective(
            id=f"erase-{i}",
            created_at="2026-09-11T00:00:00Z",
            target_kind=kind,
            target_record_id=identity,
        )
        for i, (kind, identity) in enumerate(
            (("private_state", stock["id"]), ("saved_plan", saved.plan_id))
        )
    )
    _apply_plan_directives(target, directives)
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT COUNT(*) FROM personal_private_state").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM consumer_plan_revisions").fetchone()[0] == 0
