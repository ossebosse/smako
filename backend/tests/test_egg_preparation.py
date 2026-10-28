"""Joint edible input and measured physical outputs must remain distinct."""

from copy import deepcopy
from dataclasses import replace

import pytest
from app.config import Settings
from app.models.personal import EggSeparation, PantryItem, PersonalMutation, PreparedOrigin
from app.services.egg_preparation import METHOD, OPERAND, component, edible_input
from app.services.official_product_facts import shell_egg_quantity_proofs
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.personal_store import PersonalConflict, write_state
from app.services.recipe_library import current_recipes

from backend.tests.test_personal_booked_revisions import OWNER, setup_plan
from backend.tests.test_personal_planning_v2 import NOW, key_for, prepared, product, request, state


def issued(name="äggula"):
    return next(r for r in current_recipes() if component(r, name))


def egg_planner():
    p = prepared(product("Ägg M", 6, "st", 20))
    raw = p.universe.products[0]
    fact = ProductFacts(source="fixture", source_product_id=raw.product_id, source_snapshot_id="v2-frozen",
        ingredients=("ÄGG",), ingredients_complete=True, animal=True, organic=False)
    facts = shell_egg_quantity_proofs(p.universe.products, {(raw.store_id, raw.product_id): fact})
    req = request(allow_nutrition_estimates=True).model_copy(update={"purchase_planning_mode": "estimated"})
    planner = PersonalPlanner(req, Settings(price_provider="mock"), p, state(), facts=facts, now=NOW)
    return planner, raw


def test_only_issued_explicit_raw_method_resolves_whole_egg_and_uses_component_nutrients():
    planner, raw = egg_planner()
    recipe = issued()
    candidates = planner.resolve("äggula", 30, "g", recipe=recipe, profile=planner.spec.profile)
    assert candidates and candidates[0][1].usable_unit == "g"
    assert candidates[0][1].usable_quantity == 6 * 51  # Existing M-class edible proof.
    evidence = planner.nutrition_evidence(raw, "äggula", "g", {"protein_g"}, recipe)
    assert evidence.nutrition["protein_g"] == 15.63
    assert evidence.evidence_kind == "reviewed_raw_component_population_estimate"
    planner.spec.allow_nutrition_estimates = False
    assert planner.nutrition_evidence(raw, "äggula", "g", {"protein_g"}, recipe) is None
    planner.request = planner.request.model_copy(update={"purchase_planning_mode": "exact"})
    with pytest.raises(PolicyConflict, match="uppskattningsläge"):
        planner.resolve("äggula", 30, "g", recipe=recipe)
    edited = recipe.model_copy(update={"instructions": ["Fake preparation", *recipe.instructions]})
    with pytest.raises(ValueError):
        planner.resolve("äggula", 30, "g", recipe=edited)


@pytest.mark.parametrize("yolk,white,whole,expected", [(30, 60, 0, 90), (30, 0, 0, 90), (0, 60, 40, 130), (30, 100, 20, 170)])
def test_shared_input_uses_max_then_adds_whole_demand(yolk, white, whole, expected):
    assert edible_input(yolk, white, whole) == expected


def test_grouping_allocates_raw_stock_once_and_exposes_coproduct_surplus():
    planner, _ = egg_planner()
    key = key_for(planner.prepared, "Ägg M")
    planner.items = [{**PantryItem(name="ägg", quantity=50, unit="g", product_key=key).model_dump(), "available": 50}]
    available = {planner.items[0]["id"]: 50}
    rows = [{"name": name, "unallocated_quantity": q, "unit": "g", "source": source,
             "demand_key": source, **({"preparation": METHOD} if name != "ägg" else {})}
            for name, q, source in [("äggula", 30, "y"), ("äggvita", 40, "w"), ("ägg", 20, "e")]]
    groups = [{"name": "äggula", "quantity": 90, "positions": {0}, "demand_keys": ["y", "w", "e"]}]
    allocations = []
    result = planner._prepare_groups(groups, rows, allocations, available)
    assert groups[0]["quantity"] == 60  # 20 whole + (90 separation - 50 stock).
    assert result[0]["estimated_surplus_g"] == {"äggula": 0, "äggvita": 20}
    assert sum(r["quantity"] for r in allocations) == 50
    assert allocations[0]["kind"] == "preparation_input" and available[planner.items[0]["id"]] == 0


def measured_plan(tmp_path):
    _p, plans, private, saved, stock = setup_plan(tmp_path)
    # Isolate the existing inventory transaction with a saved preparation quote.
    # Resolver qualification is tested above; this fixture does not assert milk
    # is egg or add any product fact to the shared universe.
    stock["items"] = [PantryItem(id="egg-lot", name="ägg", quantity=300, unit="g", product_key="a" * 32).model_dump()]
    stock["reservations"][saved.plan_id] = [{"item_id": "egg-lot", "quantity": 90, "unit": "g", "name": "ägg",
        "source": "prep", "demand_key": "prep", "kind": "preparation_input", "method": METHOD, "product_key": "a" * 32}]
    demands = [{"source": "yolk-meal", "name": "äggula", "quantity": 30, "original_quantity": 30, "unit": "g", "demand_key": "y", "preparation": METHOD},
               {"source": "white-meal", "name": "äggvita", "quantity": 60, "original_quantity": 60, "unit": "g", "demand_key": "w", "preparation": METHOD}]
    prep = {"id": "prep", "method": METHOD, "input_allocations": stock["reservations"][saved.plan_id], "outputs": demands}
    saved = saved.model_copy(update={"plan": saved.plan.model_copy(update={
        "personal": saved.plan.personal.model_copy(update={"remaining_demands": demands, "needs": [], "allocations": [], "preparations": [prep]}),
        "optimized_basket": saved.plan.optimized_basket.model_copy(update={"stores": [], "total": 0}),
    })})
    with plans._connect() as conn:
        stock = write_state(conn, OWNER, stock, stock["revision"])
    return private, saved, stock


def batch(yolk=30, white=60, input_g=90):
    return EggSeparation(method=METHOD, inputs={"egg-lot": input_g}, yolk_g=yolk, white_g=white)


def test_measured_prepare_partial_consume_release_conserve_inventory_and_retry(tmp_path):
    private, saved, stock = measured_plan(tmp_path)
    result = private.inventory_action(OWNER, saved, "prepare", stock["revision"], operation_id="prepare-0001", preparation=batch())
    assert sum(i["quantity"] for i in result["items"]) == 300
    outputs = [i for i in result["items"] if i.get("prepared_origin")]
    assert {i["name"]: i["quantity"] for i in outputs} == {"äggula": 30, "äggvita": 60}
    assert all(i["product_key"] is None for i in outputs)
    assert private.inventory_action(OWNER, saved, "prepare", stock["revision"], operation_id="prepare-0001", preparation=batch()) == result
    with pytest.raises(PersonalConflict, match="annat innehåll"):
        private.inventory_action(OWNER, saved, "prepare", result["revision"], operation_id="prepare-0001", preparation=batch(20, 60))
    consumed = private.inventory_action(OWNER, saved, "consume", result["revision"], operation_id="consume-half", consume_fraction=.5)
    assert sum(i["quantity"] for i in consumed["items"]) == 255
    assert sum(r["quantity"] for r in consumed["ledger"][-1]["rows"]) == 45
    released = private.inventory_action(OWNER, saved, "release", consumed["revision"])
    assert released["items"] == consumed["items"] and saved.plan_id not in released["reservations"]


def test_short_yield_is_recorded_truthfully_and_blocks_consumption(tmp_path):
    private, saved, stock = measured_plan(tmp_path)
    with pytest.raises(PersonalConflict, match="Separera"):
        private.inventory_action(OWNER, saved, "consume", stock["revision"])
    result = private.inventory_action(OWNER, saved, "prepare", stock["revision"], operation_id="prepare-short", preparation=batch(20, 60))
    assert result["ledger"][-1]["preparation"]["loss_g"] == 10
    assert sum(i["quantity"] for i in result["items"]) == 290
    with pytest.raises(PersonalConflict, match="täcker inte"):
        private.inventory_action(OWNER, saved, "consume", result["revision"])
    assert private.read(OWNER) == result


def test_binary_float_roundoff_never_becomes_a_negative_recorded_loss(tmp_path):
    private, saved, stock = measured_plan(tmp_path)
    result = private.inventory_action(OWNER, saved, "prepare", stock["revision"],
        operation_id="prepare-decimals", preparation=batch(.1, .2, .3))
    assert result["ledger"][-1]["preparation"]["loss_g"] == 0


def test_preparation_conservation_stale_stock_and_other_plan_reservations(tmp_path):
    with pytest.raises(ValueError):
        batch(31, 60)
    with pytest.raises(ValueError):
        PersonalMutation(action="prepare", revision=1, pantry_revision=0, preparation=batch())
    private, saved, stock = measured_plan(tmp_path)
    changed = deepcopy(stock)
    changed["reservations"]["other-plan"] = [{"item_id": "egg-lot", "quantity": 250}]
    with private.plans._connect() as conn:
        changed = write_state(conn, OWNER, changed, stock["revision"])
    with pytest.raises(PersonalConflict, match="disponibelt"):
        private.inventory_action(OWNER, saved, "prepare", changed["revision"], operation_id="prepare-0001", preparation=batch())
    assert private.read(OWNER) == changed


def test_source_conflict_and_plain_shell_identity_are_not_bypassed():
    planner, raw = egg_planner()
    key = (raw.store_id, raw.product_id)
    planner.facts[key] = replace(planner.facts[key], conflicts=("unknown_quantity_conflict",))
    with pytest.raises(PolicyConflict):
        planner.resolve("äggula", 30, "g", recipe=issued(), profile=planner.spec.profile)
    assert OPERAND in next(i for i in issued().ingredients if i.canonical_name == "äggula").product_requirements


def test_prepared_lot_keeps_component_identity_and_requires_current_qualified_origin():
    planner, _ = egg_planner()
    candidates = planner.resolve("äggula", 30, "g", recipe=issued(), profile=planner.spec.profile)
    key = planner.product_keys[0]
    raw = PantryItem(name="ägg", quantity=100, unit="g", product_key=key)
    yolk = PantryItem(name="äggula", quantity=30, unit="g", form="raw_edible",
        prepared_origin=PreparedOrigin(method=METHOD, product_key=key, operation_id="prepare-test-1"))
    planner.items = [i.model_dump() for i in (raw, yolk)]
    available = {raw.id: 100, yolk.id: 30}
    row = {"name": "äggula", "quantity": 30, "unit": "g", "use_pantry": True, "source": "dinner",
        "demand_key": "y", "preparation": METHOD, "profile": planner.spec.profile, "organic_animals": False,
        "properties": [], "product_key": None, "input_form": "raw_edible", "nutrients": ["protein_g"]}
    remaining, allocated = planner._allocate(row, candidates, available)
    assert remaining == 0 and [a["item_id"] for a in allocated] == [yolk.id]
    assert available[raw.id] == 100
    assert allocated[0]["product_key"] is None and allocated[0]["prepared_origin"]["product_key"] == key
    for changed in ({"preparation": "unknown"}, {"name": "ägg", "preparation": None}):
        planner.items = [yolk.model_dump()]
        remaining, allocated = planner._allocate({**row, **changed}, candidates, {yolk.id: 30})
        assert remaining == 30 and allocated == []
    assert planner._allocate(row, [], {yolk.id: 30}) == (30, [])


def test_prepared_lineage_cannot_be_forged_by_pantry_edit(tmp_path):
    private, saved, stock = measured_plan(tmp_path)
    result = private.inventory_action(OWNER, saved, "prepare", stock["revision"], operation_id="prepare-test-1", preparation=batch())
    items = [PantryItem.model_validate(i) for i in result["items"]]
    prepared = next(i for i in items if i.prepared_origin)
    prepared.prepared_origin = prepared.prepared_origin.model_copy(update={"product_key": "b" * 32})
    with pytest.raises(PersonalConflict, match="ursprung"):
        private.update_pantry(OWNER, result["revision"], items)
    assert private.read(OWNER) == result


def test_repeated_purchase_compares_measured_payload(tmp_path):
    _p, _plans, private, saved, stock = setup_plan(tmp_path)
    with pytest.raises(PersonalConflict, match="annat innehåll"):
        private.inventory_action(OWNER, saved, "purchase", stock["revision"], measured_purchase_quantities={"changed": 999})
    assert private.read(OWNER) == stock


def test_surplus_signal_includes_unused_component_without_crediting_checkout():
    from types import SimpleNamespace

    from app.services.week_refinement import surplus_key, surplus_summary

    item = SimpleNamespace(ingredient="eggs", merchandise_total=20, purchased_usable_quantity=300,
        waste_quantity=210, quantity_confidence="exact", purchase_units=None, packages_needed=1, unit="g")
    basket = SimpleNamespace(stores=[SimpleNamespace(items=[item])], total=20)
    preparation = {"purchase_key": "eggs", "purchase_input_quantity_g": 90, "input_quantity_g": 90,
                   "estimated_surplus_g": {"äggula": 0, "äggvita": 60}}
    before = surplus_summary(basket)
    after = surplus_summary(basket, preparations=[preparation])
    assert before["unused_quantities"] == {"g": 210}
    assert after["unused_quantities"] == {"g": 270}
    assert after["unused_purchase_value"] == 18 and after["preparation_unused_purchase_value"] == 4
    assert after["quantity_status"] == "ESTIMATED" and not after["deducted_from_checkout"] and basket.total == 20
    assert surplus_key(basket, preparations=[preparation]) > surplus_key(basket)


def test_separation_time_participates_in_the_existing_meal_filters():
    from app.models.personal import MealSettings
    from app.models.recipe_preferences import RecipePreferences
    from app.services.recipe_library import matches_meal

    recipe = issued()
    assert recipe.design.steps[0].duration_minutes == 3
    meal = MealSettings(meal_type=recipe.design.meal_types[0], count=1, servings=recipe.servings,
        recipe_choices={"max_active_minutes": recipe.design.active_minutes - 1})
    assert not matches_meal(recipe, meal, RecipePreferences(mode="complete"))
