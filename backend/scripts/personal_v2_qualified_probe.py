"""Frozen real-catalog R4/R5 acceptance; outputs only synthetic plans/public facts."""

import argparse
import hashlib
import json
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import (
    complete_identity_facts,
    project_raw_facts,
)
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", default="reports/private/gaps-price-fixture.json")
    parser.add_argument("--facts", default="reports/private/qualified-facts.json")
    parser.add_argument("--output", default="reports/personal-v2-qualified/frozen.json")
    args = parser.parse_args()
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        Path(args.prices).read_bytes()
    ).restore()
    raw = json.loads(Path(args.facts).read_bytes())
    assert raw["universe_id"] == prepared.universe.universe_id
    before = {tuple(k): ProductFacts(**v) for k, v in raw["facts"]}
    mapped = {}
    for p in prepared.universe.products:
        key = (p.store_id, p.product_id)
        if key in before:
            f = before[key]
            mapped[key] = project_raw_facts(
                raw["raw"][p.product_id],
                chain=p.chain,
                product_id=p.product_id,
                snapshot_id=f.source_snapshot_id,
                source_reference=f.source,
                observed_at=p.source_provenance.source_observed_at.isoformat(),
            )
    after = complete_identity_facts(prepared, mapped)
    inventory = {
        "id": None,
        "revision": 0,
        "profile": None,
        "items": [],
        "reservations": {},
        "events": {},
    }
    settings = Settings(price_provider="mock")

    def planner(spec, facts):
        return PersonalPlanner(
            PlanRequest(
                recipes=0,
                diversity_mode="cheapest",
                max_stores=2,
                memberships={},
                personal=PersonalPlanning(**spec),
            ),
            settings,
            prepared,
            inventory,
            facts=facts,
            now=prepared.universe.built_at,
        )

    base = planner(
        {
            "meals": [
                MealSettings(meal_type=t, count=1, servings=4)
                for t in ("dinner", "breakfast", "snack")
            ]
        },
        {},
    )
    reachable = set()
    recipes = []
    for meal in base.spec.meals:
        for recipe in base._candidates(meal):
            recipes.append((meal.meal_type, recipe.name))
            for ingredient in base.service.normalizer.normalize_and_aggregate([recipe]):
                reachable.update(
                    i
                    for i, _ in base.resolve(
                        ingredient.canonical_name,
                        ingredient.required_quantity,
                        ingredient.unit,
                        profile=base.spec.profile,
                    )
                )

    def coverage(facts):
        result = Counter(products=len(reachable))
        for i in reachable:
            p = prepared.universe.products[i]
            f = facts.get((p.store_id, p.product_id))
            if f:
                result.update(
                    ingredients=bool(f.ingredients),
                    organic=f.organic is True,
                    animal_known=f.animal is not None,
                    nutrition_complete={"kcal", "protein_g", "carbs_g", "fat_g"}
                    <= f.nutrition.keys(),
                    nutrition_as_sold=bool(f.nutrition_basis)
                    and f.nutrition_preparation == "as_sold"
                    and {"kcal", "protein_g", "carbs_g", "fat_g"} <= f.nutrition.keys(),
                )
        return dict(result)

    cases = {
        "A": {"meals": [MealSettings(count=1, servings=2)], "organic_percent": 25},
        "B": {
            "meals": [MealSettings(meal_type="breakfast", count=1, servings=2)],
            "organic_animals": True,
        },
        "C": {
            "meals": [
                MealSettings(
                    meal_type="breakfast",
                    count=1,
                    servings=2,
                    limits=PortionLimits(
                        min_protein_g=15,
                        min_carbs_g=30,
                        max_carbs_g=90,
                        min_fat_g=5,
                        max_fat_g=30,
                        max_kcal=600,
                    ),
                )
            ]
        },
        "D": {
            "meals": [
                MealSettings(
                    meal_type="breakfast",
                    count=1,
                    servings=2,
                    limits=PortionLimits(min_weight_g=250, max_weight_g=600),
                )
            ]
        },
        "E": {
            "meals": [
                MealSettings(
                    meal_type="breakfast",
                    count=1,
                    servings=2,
                    limits=PortionLimits(
                        min_protein_g=15,
                        min_carbs_g=30,
                        max_carbs_g=90,
                        min_fat_g=5,
                        max_fat_g=30,
                        max_kcal=600,
                    ),
                )
            ],
            "organic_percent": 30,
        },
    }
    result = {
        "price_version": prepared.universe.universe_id,
        "price_sha256": raw["price_sha256"],
        "facts_before": "retained-catalog-facts-v1:export:"
        + hashlib.sha256(Path(args.facts).read_bytes()).hexdigest(),
        "facts_after": after.version,
        "coverage_before": coverage(before),
        "coverage_after": coverage(after),
        "recipe_counts": dict(Counter(t for t, _ in recipes)),
        "live_provider_requests": 0,
        "product_detail_fetches": 0,
        "cases": {},
        "reused_pool_fields": [],
    }
    for i in sorted(reachable):
        product = prepared.universe.products[i]
        key = (product.store_id, product.product_id)
        original, new = before.get(key), after.get(key)
        if not new:
            continue
        gained = []
        if new.ingredients and not (original and original.ingredients):
            gained.append("ingredients")
        if new.organic is True and not (original and original.organic is True):
            gained.append("organic")
        if new.nutrition and not (original and original.nutrition):
            gained.append("nutrition")
        if gained:
            result["reused_pool_fields"].append(
                {
                    "product_id": product.product_id,
                    "name": product.name,
                    "chain": product.chain,
                    "gtin": product.gtin,
                    "fields": gained,
                    "provenance": new.field_sources,
                }
            )
    for name, spec in cases.items():
        start = time.perf_counter()
        p = planner(spec, after)
        try:
            plan = p.create()
            case = {"status": "PASS", "plan": plan.model_dump(mode="json")}
        except ValueError as exc:
            case = {"status": getattr(exc, "code", "SEARCH_BLOCKED"), "message": str(exc)}
            case["recipe_gaps"] = []
            from app.services.personal_nutrition import calculation_basis, requested_nutrients
            from app.services.recipe_candidate_generator import (
                DeterministicRecipeCandidateGenerator,
            )

            for meal in p.spec.meals:
                for recipe in DeterministicRecipeCandidateGenerator().generate_for_meal_type(
                    p.view.economic_pool, meal.meal_type, servings=meal.servings
                ):
                    needs = []
                    requested = requested_nutrients(meal.limits)
                    for ingredient in p.service.normalizer.normalize_and_aggregate([recipe]):
                        try:
                            candidates = p.resolve(
                                ingredient.canonical_name,
                                ingredient.required_quantity,
                                ingredient.unit,
                                profile=p.spec.profile,
                                organic_animals=p.spec.organic_animals or meal.organic_animals,
                            )
                            qualified = [
                                c
                                for i, c in candidates
                                if not requested
                                or (
                                    (f := p.source_facts(prepared.universe.products[i]))
                                    and f.nutrition_basis
                                    and f.nutrition_unit == ingredient.unit
                                    and f.nutrition_preparation == "as_sold"
                                    and requested <= f.nutrition.keys()
                                )
                            ]
                            needs.append(
                                {
                                    "ingredient": ingredient.canonical_name,
                                    "unit": ingredient.unit,
                                    "qualified_products": len(qualified),
                                    "missing": []
                                    if qualified
                                    else sorted(requested) + ["correct_unit_and_preparation_basis"],
                                }
                            )
                        except ValueError as error:
                            needs.append(
                                {
                                    "ingredient": ingredient.canonical_name,
                                    "qualified_products": 0,
                                    "missing": [str(error)],
                                }
                            )
                    missing = []
                    if meal.limits.min_weight_g is not None or meal.limits.max_weight_g is not None:
                        missing.append("cooked_edible_weight_and_yield")
                    if requested:
                        try:
                            calculation_basis(recipe)
                        except ValueError as error:
                            missing.append(str(error))
                    case["recipe_gaps"].append(
                        {
                            "recipe": recipe.name,
                            "needs": needs,
                            "covered_needs": sum(bool(n["qualified_products"]) for n in needs),
                            "total_needs": len(needs),
                            "missing_recipe_fields": missing,
                        }
                    )
        case.update(
            settings=p.request.model_dump(mode="json"),
            seconds=round(time.perf_counter() - start, 3),
        )
        result["cases"][name] = case
        print(
            json.dumps(
                {
                    "case": name,
                    "status": case["status"],
                    "cost": case.get("plan", {}).get("optimized_basket", {}).get("total"),
                    "message": case.get("message"),
                    "seconds": case["seconds"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}, ensure_ascii=False))


if __name__ == "__main__":
    with patch(
        "socket.socket.connect",
        side_effect=AssertionError("No network allowed in frozen consumer planning"),
    ):
        main()
