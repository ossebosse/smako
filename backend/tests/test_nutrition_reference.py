"""Frozen official reference subset and combined consumer contracts."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from app.models import NormalizedIngredient
from app.models.personal import MealSettings, MealSlot, PantryItem, PortionLimits
from app.services.nutrition_reference import (
    COOKED,
    MAPPINGS,
    macro_values,
    product_reference,
    reference_data,
    reference_evidence,
    validate_pantry_reference,
)
from app.services.personal_nutrition import calculation_basis
from app.services.personal_policy import PolicyConflict
from app.services.product_matcher import ProductMatcher
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator

from backend.tests.test_personal_planning_v2 import prepared, product, request, run, state
from backend.tests.test_personal_qualified_facts import facts


def dinner():
    return DeterministicRecipeCandidateGenerator().generate_reference_candidates(servings=4)[0]


def dinner_request(**kwargs):
    return request(
        slots=[MealSlot(id="d", day=1, meal_type="dinner", recipe=dinner())],
        meals=[
            MealSettings(count=1, servings=4, limits=PortionLimits(min_protein_g=20, max_kcal=800))
        ],
        **kwargs,
    )


def products():
    return prepared(
        product("Kycklingbröstfilé", 1000, "g", 80),
        product("Långkornigt Ris", 1000, "g", 20),
        product("Morötter", 1000, "g", 10),
    )


def test_all_reviewed_references_have_sourced_units_and_not_product_identities():
    with patch("socket.socket.connect", side_effect=AssertionError("offline")):
        data = reference_data()
        assert len(MAPPINGS) == 65  # 46 retained plus 19 explicitly imported recipe-layer foods.
        for identity in MAPPINGS:
            f = reference_evidence(identity)
            assert set(f.nutrition) == {"kcal", "protein_g", "fat_g", "carbs_g"}
            assert f.source_product_id == f"slv:{identity}"
            assert "organic" not in vars(f) and "allergens_checked" not in vars(f)
        assert data["license"].endswith("/by/4.0/deed.sv")


@pytest.mark.parametrize("change", ["unit", "basis", "missing", "nan", "duplicate", "bool"])
def test_unknown_or_conflicting_macros_never_become_zero(change):
    rows = deepcopy(reference_data()["foods"]["2481"]["nutrients"])
    target = next(r for r in rows if r["namn"] == "Protein")
    if change == "unit":
        target["enhet"] = "mg"
    if change == "basis":
        target["viktGram"] = 1
    if change == "missing":
        rows.remove(target)
    if change == "nan":
        target["varde"] = float("nan")
    if change == "bool":
        target["varde"] = False
    if change == "duplicate":
        rows.append(target)
    with pytest.raises(ValueError):
        macro_values(rows)


@pytest.mark.parametrize(
    "name,unit,reference",
    [
        ("kokt ris", "g", "slv:2481:dry"),
        ("ris", "ml", "slv:2481:dry"),
        ("ris", "g", "slv:2481:cooked"),
        ("mjölk", "g", "slv:123:ready"),
        ("avrunna kikärtor", "g", "slv:881:dry"),
    ],
)
def test_wrong_form_units_or_important_variant_rejected(name, unit, reference):
    with pytest.raises(ValueError):
        validate_pantry_reference(name, unit, reference)


def test_cooked_reference_uses_documented_batch_not_water_factor_or_second_yield():
    data = reference_data()
    entry = data["preparations"][str(COOKED[2481])]
    source = macro_values(entry["nutrients"])
    expected = source["kcal"] * sum(i["viktEfterTillagning"] for i in entry["ingredients"]) / 85
    actual = reference_evidence(2481, cooked=True)
    assert actual.nutrition["kcal"] == pytest.approx(expected)
    assert actual.nutrition["kcal"] != pytest.approx(source["kcal"] * 17.2)
    assert reference_evidence(3815, cooked=True) is None  # Already drained: no second cook.
    assert reference_evidence(845, cooked=True) is None  # No invented pasta yield.


def test_unrequested_nutrients_do_not_block_complete_selected_declaration():
    p = product("Kycklingbröstfilé", 1000, "g", 80)
    declaration = facts(
        p,
        nutrition={"protein_g": 23, "kcal": 110},
        nutrition_unit="g",
        nutrition_basis="per 100 g",
        nutrition_preparation="as_sold",
    )
    evidence = reference_evidence(1173, cooked=True, declaration=declaration)
    assert set(evidence.nutrition) == {"protein_g", "kcal"}
    assert evidence.nutrition["protein_g"] > 0
    result = run(
        products(),
        dinner_request(allow_nutrition_estimates=True),
        facts={(p.store_id, p.product_id): declaration},
    )
    assert result.personal.checks["nutrition"][0]["status"] == "ESTIMATED"


def test_explicit_mode_required_and_unsupported_recipe_edit_stays_blocked():
    with pytest.raises(PolicyConflict):
        run(products(), dinner_request(), facts={})
    assert not dinner_request().personal.allow_nutrition_estimates
    with pytest.raises(PolicyConflict):
        calculation_basis(
            dinner().model_copy(update={"instructions": ["Stek i lite olja."]}),
            allow_estimates=True,
        )


def test_combined_pantry_packages_and_estimate_without_stock_mutation():
    inventory = state(
        [
            PantryItem(
                id="rice", name="ris", quantity=500, unit="g", nutrition_reference="slv:2481:dry"
            )
        ]
    )
    before = deepcopy(inventory)
    with patch("socket.socket.connect", side_effect=AssertionError("offline")):
        plan = run(products(), dinner_request(allow_nutrition_estimates=True), inventory, facts={})
    assert inventory == before
    assert plan.optimized_basket.total == 90  # One whole chicken and carrot pack; no rice purchase.
    check = plan.personal.checks["nutrition"][0]
    assert check["status"] == "ESTIMATED"
    expected = sum(
        reference_evidence(n, cooked=True).nutrition["protein_g"] * q / 100
        for n, q in [(1173, 150), (2481, 80), (289, 150)]
    )
    assert check["values"]["protein_g"] == pytest.approx(expected)
    assert sum(a["quantity"] for a in plan.personal.allocations) == 320
    assert {s["origin"] for s in check["sources"]} == {"purchase", "pantry"}
    assert plan.personal.checks["organic_cost_percent"] == 0
    assert plan.personal.checks["allergy"] == "NOT_REQUESTED"


def test_generic_pantry_requires_own_confirmation_even_with_mode_enabled():
    inventory = state([PantryItem(name="ris", quantity=500, unit="g")])
    with pytest.raises(PolicyConflict, match="bekräftat"):
        run(products(), dinner_request(allow_nutrition_estimates=True), inventory, facts={})


def test_estimates_do_not_relax_allergy_or_eco():
    from app.models.personal import TasteProfile

    for kwargs in (
        {"organic_percent": 25},
        {"organic_animals": True},
        {"profile": TasteProfile(allergies=["jordnötter"])},
    ):
        with pytest.raises(PolicyConflict):
            run(products(), dinner_request(allow_nutrition_estimates=True, **kwargs), facts={})


def test_conflicting_declarations_and_special_variants_not_replaced():
    p = product("Kycklingbröstfilé", 1000, "g", 80)
    assert product_reference(p, "kyckling", facts(p, conflicts=("nutrition.protein_g",))) is None
    for name, need in [
        ("Pinklaxfilé Solrosolja", "lax"),
        ("Poésie Torsk", "fisk"),
        ("Basmatiris", "ris"),
        ("Kycklinglårfilé", "kyckling"),
    ]:
        assert product_reference(product(name, 500, "g", 20), need, None) is None
    for name, need, unit in [
        ("Blåmögelost Organic blue Eko", "ost", "g"),
        ("Getmjölk", "mjölk", "ml"),
    ]:
        assert not ProductMatcher().match(
            NormalizedIngredient(canonical_name=need, required_quantity=100, unit=unit),
            [product(name, 500, unit, 20)],
        )


def test_mapping_content_is_part_of_cache_version(monkeypatch):
    first = reference_data()["content_version"]
    monkeypatch.setitem(MAPPINGS, 2481, ("ris", "changed-form"))
    reference_data.cache_clear()
    try:
        assert reference_data()["content_version"] != first
    finally:
        monkeypatch.undo()
        reference_data.cache_clear()


def test_reference_version_is_independent_of_json_line_endings(tmp_path, monkeypatch):
    from app.services import nutrition_reference as module

    first = reference_data()["content_version"]
    path = tmp_path / "reference.json"
    path.write_bytes(module.PATH.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    (tmp_path / "slv-20260925.json").write_bytes(module.PATH.with_name("slv-20260925.json").read_bytes())
    (tmp_path / "slv-20260926.json").write_bytes(module.PATH.with_name("slv-20260926.json").read_bytes())
    (tmp_path / "slv-20261002.json").write_bytes(module.PATH.with_name("slv-20261002.json").read_bytes())
    (tmp_path / "slv-20261002-celery.json").write_bytes(module.PATH.with_name("slv-20261002-celery.json").read_bytes())
    (tmp_path / "slv-20261002-beetroot.json").write_bytes(module.PATH.with_name("slv-20261002-beetroot.json").read_bytes())
    monkeypatch.setattr(module, "PATH", path)
    reference_data.cache_clear()
    try:
        assert reference_data()["content_version"] == first
    finally:
        reference_data.cache_clear()


def test_personal_preset_survives_saved_request_roundtrip_without_null_relaxation():
    from app.models import PlanRequest
    from app.services.meal_plan_optimizer import MealPlanService
    from app.services.personal_planner import personal_policy_request

    fresh = PlanRequest(recipes=5, diversity_mode="balanced")
    restored = PlanRequest.model_validate_json(fresh.model_dump_json())
    for req in (fresh, restored):
        actual = MealPlanService._diversity_policy_for(
            personal_policy_request(req, 5), req.diversity_mode
        )
        assert actual.max_same_cooking_method_meals == 2
        assert actual.max_same_dish_form_meals == 2
        assert actual.max_pairwise_culinary_similarity == 0.85
    explicit = PlanRequest(recipes=5, diversity_mode="balanced", max_same_cooking_method_meals=1)
    assert (
        MealPlanService._diversity_policy_for(
            personal_policy_request(explicit, 5), explicit.diversity_mode
        ).max_same_cooking_method_meals
        == 1
    )
    assert "max_same_cooking_method_meals" in restored.model_fields_set


def test_explicit_extra_stays_additional_and_package_surplus_is_not_eaten():
    from app.models.personal import ExtraNeed

    inventory = state(
        [PantryItem(name="ris", quantity=500, unit="g", nutrition_reference="slv:2481:dry")]
    )
    req = dinner_request(
        allow_nutrition_estimates=True,
        extras=[ExtraNeed(query="ris", quantity=100, unit="g", confirmed=True)],
    )
    plan = run(products(), req, inventory, facts={})
    assert plan.optimized_basket.total == 110
    rice = next(
        i
        for store in plan.optimized_basket.stores
        for i in store.items
        if i.product_name == "Långkornigt Ris"
    )
    assert rice.required_quantity == 100 and rice.purchased_usable_quantity == 1000
    check = plan.personal.checks["nutrition"][0]
    assert sum(s["quantity"] for s in check["sources"] if s["ingredient"] == "ris") == 320


def test_estimated_purchase_replay_history_and_consumption_are_immutable(tmp_path):
    from app.services.personal_store import PersonalStore
    from app.services.plan_store import PlanStore

    owner = "f" * 64
    plans = PlanStore(tmp_path / "plans.sqlite")
    private = PersonalStore(plans)
    req = dinner_request(allow_nutrition_estimates=True)
    saved = plans.create(req, run(products(), req, facts={}), owner_actor_hash=owner)
    initial = private.read(owner)
    assert initial["items"] == []
    bought = private.inventory_action(owner, saved, "purchase", initial["revision"])
    assert private.inventory_action(owner, saved, "purchase", initial["revision"]) == bought
    history = deepcopy(bought["ledger"])
    revised = req.model_copy(deep=True)
    revised.personal.pantry_revision = bought["revision"]
    recomputed = run(products(), revised, bought, plan_id=saved.plan_id, facts={})
    assert recomputed.optimized_basket.total == 0
    new = plans.append(
        plan_id=saved.plan_id,
        request=revised,
        response=recomputed,
        operation="recipe_replaced",
        expected_parent=1,
        owner_actor_hash=owner,
    )
    assert private.read(owner)["ledger"] == history
    assert plans.get_owned(saved.plan_id, owner_actor_hash=owner, revision=1) == saved
    stock = private.read(owner)
    consumed = private.inventory_action(owner, new, "consume", stock["revision"])
    assert private.inventory_action(owner, new, "consume", stock["revision"]) == consumed
    assert consumed["ledger"][0] == history[0]
    assert sum(i["quantity"] for i in consumed["items"]) == 1480  # 3000 bought minus 600+320+600.
