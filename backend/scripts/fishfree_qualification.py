"""Ingredient-level qualification evidence on the unchanged historical price artifact."""

import argparse
import json
from contextlib import nullcontext
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSlot, TasteProfile
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import check_product
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator
from app.services.recipe_profile import RecipeProfileBuilder

from backend.scripts.personal_v2_cost_audit import inputs
from backend.scripts.personal_v2_dinners_probe import fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", action="store_true")
    args = parser.parse_args()
    with (
        patch("app.services.reviewed_ingredients.enrich_ingredients", side_effect=lambda p, f: f)
        if args.before
        else nullcontext()
    ):
        prepared, facts = fixture()
    _, cases = inputs()
    request = PlanRequest.model_validate(cases["no_fish"]["request"])
    planner = PersonalPlanner(
        request,
        Settings(price_provider="mock"),
        prepared,
        {"revision": 0, "items": [], "reservations": {}, "events": {}},
        facts=facts,
        now=prepared.universe.built_at,
    )
    output = {
        "price_version": prepared.universe.universe_id,
        "facts_version": facts.version,
        "recipes": [],
    }
    for recipe in DeterministicRecipeCandidateGenerator().generate_reference_candidates():
        row = {
            "name": recipe.name,
            "profile": str(RecipeProfileBuilder().build(recipe)),
            "ingredients": [],
        }
        for ingredient in recipe.ingredients:
            try:
                resolved = planner.resolve(
                    ingredient.name, ingredient.quantity, ingredient.unit, profile=TasteProfile()
                )
                values = []
                for position, _ in resolved:
                    product = prepared.universe.products[position]
                    fact = planner.source_facts(product)
                    evidence = planner.nutrition_evidence(
                        product, ingredient.name, ingredient.unit, {"protein_g", "kcal"}, recipe
                    )
                    try:
                        check_product(product, request.personal.profile, fact)
                        policy = {"status": "PASS"}
                    except ValueError as error:
                        policy = {"status": getattr(error, "code", "ERROR"), "reason": str(error)}
                    values.append(
                        {
                            "name": product.name,
                            "chain": product.chain,
                            "product_id": product.product_id,
                            "quantity": product.package_quantity,
                            "unit": product.package_unit,
                            "ingredients": fact.ingredients if fact else [],
                            "sources": fact.field_sources if fact else {},
                            "conflicts": fact.conflicts if fact else [],
                            "ingredient_policy": policy,
                            "nutrition": evidence.nutrition if evidence else None,
                        }
                    )
                row["ingredients"].append({"name": ingredient.name, "products": values})
            except ValueError as error:
                row["ingredients"].append({"name": ingredient.name, "error": str(error)})
        try:
            structure = planner.service._nutrition_for(request).validate_recipes([recipe])
            row["structural_meal_check"] = asdict(structure)
            if not structure.is_valid:
                raise ValueError(str(structure.results[0].violations))
            result = planner.basket(
                [MealSlot(id="dinner-1", day=1, meal_type="dinner", recipe=recipe)]
            )
            row.update(qualified=True, cost=result["basket"].total, checks=result["checks"])
        except ValueError as error:
            row.update(qualified=False, error=str(error))
        output["recipes"].append(row)
        print(
            json.dumps(
                {"recipe": recipe.name, "qualified": row["qualified"], "error": row.get("error")},
                ensure_ascii=False,
            ),
            flush=True,
        )
    filename = "before-qualification.json" if args.before else "qualification.json"
    Path("reports/fishfree-20260913", filename).write_text(
        json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8"
    )
    raw = json.loads(Path("reports/private/qualified-facts.json").read_bytes())["raw"]
    print("Chicken alternatives:")
    seen = set()
    for product in prepared.universe.products:
        if (
            product.chain == "willys"
            and "kycklingfil" in product.name.casefold()
            and product.product_id in raw
            and product.package_unit == "g"
        ):
            code = raw[product.product_id]["code"]
            if code not in seen:
                print(code, product.name, product.brand, product.package_quantity)
                seen.add(code)


if __name__ == "__main__":
    main()
