"""Adversarial search proposals over synthetic prices, never market acceptance.

Only the wider planner's search proposal is replaced. Narrow search, authored
recipe validation, product/quantity/nutrition qualification, pantry allocation,
whole-package checkout and final audit all use their ordinary implementations.
"""
from copy import deepcopy
from datetime import date

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, PantryItem, PersonalPlanning, TasteProfile
from app.models.product import OfferMetadata
from app.models.recipe_preferences import RecipePreferences
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.recipe_library import candidates

from backend.tests.test_personal_planning_v2 import NOW, key_for, prepared, product, state


def fixture():
    preferences = RecipePreferences(mode="complete", cuisines=["greek"], min_ingredients=13,
        max_ingredients=13, max_minutes=50, adaptation="approved", min_protein_g=30)
    authored = candidates(preferences, 2)
    base = next(r for r in authored if r.design.base_id == "smako-greek-keftedes" and r.design.variant_id == "base")
    # The reviewed protein variation uses 420 g beef, versus 340 g in the base.
    # A real 400 g pack boundary makes its checkout more expensive without
    # changing either recipe, inventing quantities or bypassing the optimizer.
    packs = {"nötfärs": (400, 45), "potatis": (400, 12), "ströbröd": (400, 18),
        "vitlök": (100, 15), "oregano": (10, 17), "spiskummin": (35, 23),
        "rapsolja": (500, 25), "citronjuice": (200, 15), "yoghurt naturell": (500, 25),
        "gurka": (350, 15), "tomat": (500, 25), "rödlök": (500, 15),
        "persilja": (30, 17), "salt": (500, 10)}
    products, facts = [], {}
    for ingredient in base.ingredients:
        quantity, price = packs[ingredient.name]
        offers = ([OfferMetadata(kind="member", description="Synthetic Coop member test offer",
            price=39.90, eligibility="member", membership_program="COOP_MEMBER",
            valid_from=date(2026, 9, 8), valid_to=date(2026, 9, 15))]
            if ingredient.name == "nötfärs" else [])
        item = product(ingredient.name, quantity, ingredient.unit, price, offers=offers).model_copy(update={
            "category": "Kryddor" if ingredient.form == "dry" else "Frukt & grönt" if ingredient.form == "raw_edible" else "Mat",
            "name": "Grekisk Yoghurt Naturell 10%" if ingredient.name == "yoghurt naturell"
                else "Spiskummin Malen" if ingredient.name == "spiskummin" else ingredient.name,
        })
        products.append(item)
        protein = {"nötfärs": 20, "yoghurt naturell": 5, "ströbröd": 10,
                   "rapsolja": 0, "salt": 0}.get(ingredient.name, 1.5)
        facts[(item.store_id, item.product_id)] = ProductFacts(
            source="synthetic_test_declaration", source_product_id=item.product_id,
            source_snapshot_id="v2-frozen", ingredients=(item.name,), ingredients_complete=True,
            nutrition={"protein_g": protein}, nutrition_unit=item.usable_unit,
            nutrition_basis="Synthetic declaration per 100 input units, not authentic source evidence")
    universe = prepared(*products)
    pantry = state([PantryItem(name="potatis", quantity=100, unit="g", form="raw_edible",
                              product_key=key_for(universe, "potatis"))])
    pantry["id"] = "first-private-test-owner"
    request = PlanRequest(recipes=1, servings=2, diversity_mode="cheapest", max_stores=1,
        memberships={"coop": True}, recipe_preferences=preferences,
        personal=PersonalPlanning(allow_nutrition_estimates=True,
            profile=TasteProfile(likes=["potatis"]), meals=[MealSettings(count=1, servings=2)]))
    return request, universe, facts, pantry


def planner(request, universe, facts, pantry):
    return PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe,
                           pantry, facts=facts, now=NOW)


@pytest.mark.parametrize("budget_stop", [False, True])
def test_content_expansion_retains_real_revalidated_checkout(monkeypatch, budget_stop):
    request, universe, facts, pantry = fixture()
    baseline = PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe,
        pantry, facts=facts, now=NOW, include_content_pack=False).create()
    expanded = planner(request, universe, facts, pantry)
    original_candidates = expanded._candidates

    def expanded_pool(meal):
        rows = original_candidates(meal)
        # Simulate the expansion marker. Only this search is adversarial; the
        # old pool, real quantities, source qualification and audit stay real.
        expanded._supplement_qualified = True
        expanded._expanded_cohort_qualified = True
        return rows

    def proposal(options, *, evaluate, accepts, **kwargs):
        if budget_stop:
            raise PolicyConflict("Synthetic expanded search budget stop", code="SEARCH_BLOCKED")
        chosen = [next(s for s in options[0] if s.recipe.design.variant_id == "protein")]
        assert accepts(chosen, final=True)
        return chosen, evaluate(chosen, final=True)

    monkeypatch.setattr(expanded, "_candidates", expanded_pool)
    monkeypatch.setattr(expanded.service.menu_optimizer, "optimize_slots", proposal)
    result = expanded.create()
    assert result.optimized_basket.stores == baseline.optimized_basket.stores
    assert result.optimized_basket.total == baseline.optimized_basket.total
    assert result.personal.allocations == baseline.personal.allocations
    assert result.personal.checks["scope_comparison"]["selected_scope"]["library"] == "before_content_pack"
    assert result.personal.checks["checkout_audit"]["passed"]


@pytest.mark.parametrize("expansion", ["exact_to_estimated", "one_to_two_stores"])
@pytest.mark.parametrize("wide_result", ["more_expensive", "budget_stop"])
def test_complete_cheapest_keeps_audited_narrow_incumbent_under_wider_request(monkeypatch, tmp_path, expansion, wide_result):
    from app.services.personal_store import PersonalStore
    from app.services.plan_store import PlanStore

    request, universe, facts, pantry = fixture()
    store = PlanStore(tmp_path / "plans.sqlite3")
    private = PersonalStore(store)
    pantry = private.update_pantry("a" * 64, 0, [PantryItem.model_validate(i) for i in pantry["items"]])
    request.personal.pantry_revision = pantry["revision"]
    narrower = planner(request, universe, facts, pantry).create()
    assert narrower.recipes[0].design.variant_id == "base"
    assert narrower.personal.checks["checkout_audit"]["passed"]
    assert any(item.applied_offer and item.membership_program == "COOP_MEMBER"
               for store in narrower.optimized_basket.stores for item in store.items)

    wider_request = request.model_copy(deep=True)
    if expansion == "exact_to_estimated":
        wider_request.purchase_planning_mode = "estimated"
    else:
        wider_request.max_stores = 2
    request_before, pantry_before = wider_request.model_dump(mode="json"), deepcopy(pantry)
    wider = planner(wider_request, universe, facts, pantry)
    observed = []

    def adversarial_proposal(options, *, evaluate, accepts, **kwargs):
        # This is the sole mocked seam: force a valid but suboptimal proposal,
        # or stop the wider search. All nested narrow planners remain real.
        observed.append(wide_result)
        wider.diagnostics.search.append({"depth": 1, "synthetic_wide_proposal": True, "beam_pruned": 9})
        if wide_result == "budget_stop":
            raise PolicyConflict("Synthetic wider-search budget exhausted", code="SEARCH_BLOCKED")
        chosen = [next(slot for slot in options[0] if slot.recipe.design.variant_id == "protein")]
        assert accepts(chosen, final=True)
        evaluated = evaluate(chosen, final=True)
        # Complete menus compared inside the search are no longer audited; the
        # chosen menu is audited by the final recompute (checked below).
        assert evaluated["audit"] is None and wider._defer_search_audit
        assert evaluated["basket"].total > narrower.optimized_basket.total
        return chosen, evaluated

    monkeypatch.setattr(wider.service.menu_optimizer, "optimize_slots", adversarial_proposal)
    retained = wider.create()
    assert observed == [wide_result]
    assert retained.recipes == narrower.recipes
    assert retained.optimized_basket.total == narrower.optimized_basket.total
    assert retained.optimized_basket.stores == narrower.optimized_basket.stores
    assert retained.optimized_basket.max_stores == wider_request.max_stores
    assert retained.personal.checks["purchase_planning_mode"] == wider_request.purchase_planning_mode
    assert retained.personal.checks["scope_comparison"]["retained_valid_incumbents"] >= 1
    assert retained.personal.checks["checkout_audit"]["passed"]

    # Independently run the actual final basket path under the TARGET request.
    # This proves the retained food, products, pantry allocation, source protein,
    # package cost and audit are still valid with those target choices.
    target_check = wider.basket(retained.personal.slots, final=True)
    assert target_check["audit"].passed
    assert target_check["basket"].total == retained.optimized_basket.total
    assert target_check["basket"].store_count <= wider_request.max_stores
    assert target_check["allocations"] == retained.personal.allocations
    assert target_check["checks"]["nutrition"][0]["values"]["protein_g"] >= 30
    assert target_check["checks"]["purchase_planning_mode"] == wider_request.purchase_planning_mode
    assert wider_request.model_dump(mode="json") == request_before
    assert pantry == pantry_before
    comparison = retained.personal.checks["scope_comparison"]
    assert comparison["exact_checkout_and_private_allocations_preserved"]
    assert comparison["target_audit_passed"]
    assert any(s.get("synthetic_wide_proposal") for s in comparison["expanded_search_diagnostics"]["search"])
    assert not any(s.get("synthetic_wide_proposal") for s in retained.personal.checks["planning_diagnostics"]["search"])
    assert retained.personal.checks["search_outcome"]["diagnostics_scope"] == "selected_narrow_search"
    assert retained.personal.checks["search_outcome"]["expanded_search_budget"]["distinct_week_proposals_pruned"] >= 9
    if wide_result == "budget_stop":
        assert comparison["expanded_search_error"]["code"] == "SEARCH_BLOCKED"
        assert retained.personal.checks["search_outcome"]["status"] == "VALID_SOLUTION"

    # The saved request stays the actual target request, without injected
    # product locks. Its cache identity agrees with a fresh ordinary target run.
    ordinary_target = planner(wider_request, universe, facts, pantry).create(_compare_scopes=False)
    assert retained.personal.cache_identity == ordinary_target.personal.cache_identity
    saved = store.create(wider_request, retained, owner_actor_hash="a" * 64)
    reopened = PlanStore(tmp_path / "plans.sqlite3").get_owned(saved.plan_id, owner_actor_hash="a" * 64)
    assert reopened.request.model_dump(mode="json") == request_before
    assert not reopened.request.personal.product_locks
    assert reopened.plan.optimized_basket == retained.optimized_basket
    assert reopened.plan.personal == retained.personal


def test_complete_incumbents_do_not_cross_private_stock_or_changed_food_choices():
    request, universe, facts, first_pantry = fixture()
    request.purchase_planning_mode = "estimated"
    first = planner(request, universe, facts, first_pantry).create()
    second_pantry = state()
    second_pantry["id"] = "second-private-test-owner"
    second = planner(request, universe, facts, second_pantry).create()
    assert first.personal.allocations and not second.personal.allocations
    assert second.optimized_basket.total > first.optimized_basket.total
    assert first.personal.cache_identity != second.personal.cache_identity
    changed = request.model_copy(deep=True)
    changed.personal.profile.exclusions = ["nötfärs"]
    with pytest.raises(PolicyConflict):
        planner(changed, universe, facts, second_pantry).create()
    changed = request.model_copy(deep=True)
    changed.recipe_preferences = changed.recipe_preferences.model_copy(update={"min_protein_g": 300})
    with pytest.raises(PolicyConflict) as failure:
        planner(changed, universe, facts, second_pantry).create()
    assert failure.value.code == "NUTRITION_TARGET_NOT_MET"


@pytest.mark.parametrize("changed", ["membership", "private_stock", "checkout_amount"])
def test_retained_checkout_still_runs_real_authorization_allocation_and_audit(changed):
    request, universe, facts, pantry = fixture()
    candidate = planner(request, universe, facts, pantry).create()
    if changed == "membership":
        request.memberships = {}
        request.membership_programs = []
        request.use_member_prices = False
    elif changed == "private_stock":
        pantry = state()
        pantry["id"] = "another-private-test-owner"
    else:
        candidate = candidate.model_copy(update={"optimized_basket": candidate.optimized_basket.model_copy(
            update={"total": candidate.optimized_basket.total - 1})})
    target = planner(request, universe, facts, pantry)
    with pytest.raises(PolicyConflict):
        target.basket(candidate.personal.slots, final=True, _retained=candidate)
