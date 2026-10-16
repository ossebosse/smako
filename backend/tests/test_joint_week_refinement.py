"""Joint constraints, real frozen checkout, and price-first surplus ranking."""
from collections import Counter
from decimal import Decimal

import pytest
from app.config import Settings
from app.models.personal import MealSettings, PantryItem
from app.services.personal_planner import PersonalPlanner
from app.services.stable_candidate_pool import VariantSearchEvidence
from app.services.week_refinement import qualified_joint_proposals, surplus_key, surplus_summary

from backend.tests.test_incremental_library_search import options, run
from backend.tests.test_personal_planning_v2 import (
    NOW,
    key_for,
    prepared,
    product,
    recipe,
    request,
    state,
)


def proposals(groups, anchor):
    return qualified_joint_proposals(groups, anchor, {})


def test_joint_distribution_repair_can_succeed_without_a_single_valid_swap():
    seed, grown = options("AB"), options("ABCD")
    seed = [[seed[0][0]], [seed[1][1]]]
    grown = [[grown[0][0], grown[0][2]], [grown[1][1], grown[1][3]]]
    valid = {("A", "B"), ("C", "D")}
    trace, seen = [], []
    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        seen.append(names)
        return 5 if names == ("C", "D") else 20
    chosen, cost = run([(1, seed), (2, grown)], evaluate=evaluate,
        accepts=lambda slots, final: not final or tuple(s.recipe.name for s in slots) in valid,
        joint_proposals=proposals, search_trace=trace)
    assert cost == 5 and tuple(s.recipe.name for s in chosen) == ("C", "D")
    assert ("A", "D") not in seen and ("C", "B") not in seen
    assert next(r for r in trace if r["library_phase"] == "joint_refinement")["improvements"] == 1


def test_surplus_objective_does_not_change_original_search_or_choose_a_more_expensive_menu():
    seen, original_seen = [], []
    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        seen.append((names, final))
        return (11, 0) if "C" in names else (10, 1) if "B" in names else (10, 8)
    kwargs = {"evaluate": evaluate, "retention_score": lambda slots, result: result[0],
              "score": lambda slots, result: result[0], "accepts": lambda slots, final: True}
    from app.services.menu_optimizer import MenuOptimizer
    base = MenuOptimizer().optimize_library_slots([(1, options("ABC"))], **kwargs)
    original_seen[:] = seen
    seen.clear()
    refined = MenuOptimizer().optimize_library_slots([(1, options("ABC"))],
        refinement_score=lambda slots, result: result, **kwargs)
    assert seen == original_seen  # no extra checkout and unchanged baseline path
    assert base[1] == (10, 8) and refined[1] == (10, 1)


def test_new_pair_budget_is_separate_and_preserves_existing_pairs():
    trace = []
    run([(1, options("A", days=5)), (2, options("ABCDEFGHIJKLM", days=5))],
        evaluate=lambda slots, final: sum(ord(s.recipe.name) for s in slots),
        joint_proposals=proposals, search_trace=trace)
    old = next(r for r in trace if r["library_phase"] == "paired_refinement")
    new = next(r for r in trace if r["library_phase"] == "joint_refinement")
    assert old["proposals"] == 128
    assert new["proposals"] <= 256 and new["evaluations_executed"] <= 32
    from app.services.complete_recipes import completed_search_outcome
    summary = completed_search_outcome({"search": trace})
    recorded = summary["search_budget"]["joint_refinement"][0]
    assert recorded["evaluations_executed"] == new["evaluations_executed"]
    assert recorded["evaluation_limit"] == 32 and not summary["global_optimum_proven"]


def test_future_recipes_enter_bounded_deterministic_joint_shortlists():
    from app.services.recipe_candidate_validator import recipe_id

    groups = options([f"Future{i}" for i in range(300)], days=5)
    evidence = {(s.meal_type, recipe_id(s.recipe)): VariantSearchEvidence(300-i, (), frozenset())
                for i, s in enumerate(groups[0])}
    anchor = [row[0] for row in groups]
    pairs = qualified_joint_proposals(groups, anchor, evidence)
    assert len(pairs) == 256 and pairs == qualified_joint_proposals(groups, anchor, evidence)
    selected = [set() for _ in groups]
    for left, right, first, second in pairs:
        selected[left].add(first.recipe.name)
        selected[right].add(second.recipe.name)
    assert all(len(names) <= 8 for names in selected)
    assert "Future299" in set().union(*selected)
    assert all(len(row) == 300 for row in groups)


@pytest.mark.parametrize("blocked", ["constraints", "checkout", "more_expensive"])
def test_unsuccessful_joint_proposals_preserve_complete_incumbent(blocked):
    def evaluate(slots, *, final):
        if any(s.recipe.name == "B" for s in slots):
            if blocked == "checkout":
                raise ValueError("Synthetic unqualified purchase")
            return 30
        return 10
    chosen, cost = run([(1, options("A")), (2, options("AB"))], evaluate=evaluate,
        accepts=lambda slots, final: blocked != "constraints" or all(s.recipe.name == "A" for s in slots),
        joint_proposals=proposals)
    assert cost == 10 and all(s.recipe.name == "A" for s in chosen)


@pytest.mark.parametrize(("store_cap", "second_store"), [(1, "coop"), (2, "coop"), (1, "willys"), (2, "willys")])
def test_joint_week_uses_actual_packs_pantry_and_shared_promotion(store_cap, second_store):
    from app.models.recipe import RecipeIngredient
    from app.services.menu_optimizer import MenuOptimizer
    from app.services.recipe_candidate_validator import recipe_id

    from backend.tests.test_promotion_groups import group
    promotion = group(eligible_product_ids=("pasta", "bröd"), required_packages=2, amount=10)
    p = prepared(product("ris", 1000, "g", 30), product("kyckling", 500, "g", 30),
                 product("pasta", 500, "g", 12, promotion_groups=(promotion,)),
                 product("bröd", 500, "g", 12, store=second_store,
                         promotion_groups=(promotion,) if second_store == "coop" else ()))
    req = request(meals=[MealSettings(count=2, servings=1)],
                  slots=[row[0].model_copy(update={"recipe": None}) for row in options("A")])
    req.max_stores = store_cap
    pantry = state([PantryItem(name="pasta", quantity=200, unit="g", product_key=key_for(p, "pasta"))])
    subject = PersonalPlanner(req, Settings(price_provider="mock"), p, pantry, now=NOW)
    slots = options("ABCD")
    for index, name, quantity in ((0, "ris", 600), (1, "kyckling", 300), (2, "pasta", 600), (3, "bröd", 500)):
        r = recipe("ABCD"[index], ingredients=[RecipeIngredient(name=name, quantity=quantity, unit="g")])
        for day in range(2):
            slots[day][index] = slots[day][index].model_copy(update={"recipe": r})
    seed, full = [[slots[0][0]], [slots[1][1]]], [[slots[0][0], slots[0][2]], [slots[1][1], slots[1][3]]]
    # Explicit synthetic distribution labels: one of each category. Both
    # individual replacements break it; C+D repairs it. Checkout is unmocked.
    categories = {"A": "one", "B": "two", "C": "two", "D": "one"}
    evidence = {}
    for row in full:
        for s in row:
            result = subject.basket([s], final=False)
            evidence[(s.meal_type, recipe_id(s.recipe))] = VariantSearchEvidence(
                result["basket"].total, (), frozenset((i.store_id, i.product_id)
                for store in result["basket"].stores for i in store.items))
    chosen, result = MenuOptimizer().optimize_library_slots([(1, seed), (2, full)],
        evaluate=lambda slots, final: subject.basket(slots, final=final),
        accepts=lambda slots, final: not final or Counter(categories[s.recipe.name] for s in slots) == {"one": 1, "two": 1},
        score=lambda slots, r: r["basket"].total, retention_score=lambda slots, r: r["basket"].total,
        refinement_score=lambda slots, r: (r["basket"].total, surplus_key(r["basket"])),
        joint_proposals=lambda groups, anchor: qualified_joint_proposals(groups, anchor, evidence))
    if second_store != "coop":
        assert [s.recipe.name for s in chosen] == (["A", "B"] if store_cap == 1 else ["C", "D"])
        assert result["basket"].total == (60 if store_cap == 1 else 24)
        assert result["basket"].store_count <= store_cap and result["audit"].passed
        return
    assert [s.recipe.name for s in chosen] == ["C", "D"]
    assert result["basket"].total == 10 and result["audit"].passed
    assert result["allocations"][0]["quantity"] == 200
    rows = [i for store in result["basket"].stores for i in store.items]
    assert sum(i.packages_needed for i in rows) == 2 and all(i.group_applications for i in rows)
    assert surplus_summary(result["basket"])["unused_purchase_value"] == 1
    assert subject.basket(chosen, final=True)["audit"].passed


def test_surplus_keeps_dimensions_separate_and_cannot_discount_the_checkout():
    from app.models.personal import ExtraNeed

    from backend.tests.test_personal_planning_v2 import run as plan
    p = prepared(product("ris", 1000, "g", 20), product("mjölk", 1000, "ml", 10))
    result = plan(p, request(extras=[ExtraNeed(query="ris", quantity=500, unit="g", confirmed=True),
                                   ExtraNeed(query="mjölk", quantity=750, unit="ml", confirmed=True)]))
    summary = surplus_summary(result.optimized_basket)
    assert summary["unused_quantities"] == {"g": 500, "ml": 250}
    assert summary["unused_purchase_value"] == 12.5
    assert summary["unused_package_equivalents"] == .75
    assert result.optimized_basket.total == 30 and not summary["deducted_from_checkout"]
    unknown = result.optimized_basket.model_copy(deep=True)
    unknown.stores[0].items[0] = unknown.stores[0].items[0].model_copy(update={"quantity_confidence": "unknown"})
    assert surplus_summary(unknown)["unused_purchase_value"] is None
    assert surplus_key(unknown) > surplus_key(result.optimized_basket)


def test_explicit_larger_purchase_mode_does_not_apply_surplus_penalty():
    subject = PersonalPlanner(request(surplus_mode="allow_larger"), Settings(price_provider="mock"),
                              prepared(product("ris", 1000, "g", 20)), state(), now=NOW)
    result = subject.basket([], final=True)
    assert subject._week_purchase_key(result["basket"]) == (Decimal(0), ())


@pytest.mark.parametrize(("inclusion", "total", "unused_value"), [("additional", 54, 7.5), ("included", 30, 1.5)])
def test_surplus_excludes_deposit_and_preserves_estimate_status(inclusion, total, unused_value):
    from datetime import date
    from types import SimpleNamespace

    from app.models.ingredient import NormalizedIngredient
    from app.models.product import ProductCandidate
    from app.services.basket_calculator import BasketCalculator
    from app.services.user_pricing import price_candidate_for_context

    from backend.tests.test_verified_offer_deposit import offer
    from grocery_data.app.domain.promotion_pricing import UserPricingContext

    p = product("läsk", 6000, "ml", None, effective_price=15, sale_price=None,
                gtin="7350086160659", offers=[offer(inclusion)])
    candidate = price_candidate_for_context(ProductCandidate.from_product(p, 1),
        UserPricingContext(), on_date=date(2026, 9, 19))
    item = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="läsk", required_quantity=9000, unit="ml"), candidate)
    basket = SimpleNamespace(stores=[SimpleNamespace(items=[item])])
    assert item.total_price == total and item.deposit_total == 24
    assert surplus_summary(basket)["unused_purchase_value"] == unused_value
    basket.stores[0].items = [item.model_copy(update={"quantity_confidence": "estimated"})]
    assert surplus_summary(basket)["quantity_status"] == "ESTIMATED"
