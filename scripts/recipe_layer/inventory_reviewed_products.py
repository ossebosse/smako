"""Share source loading and ingredient resolution across the reviewed subset.

No menu search, nutrient approval, collection or publication. Every decision
uses the ordinary planner's product/form/quantity/source/date/policy gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.models import PlanRequest
from app.services.meal_library_content import encoded, identity
from app.services.meal_prepared_artifacts import method_signature
from app.services.official_product_facts import shell_egg_quantity_proofs
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import current_recipes


def inventory(args):
    started = time.perf_counter()
    clock = datetime.fromisoformat(args.clock)
    if clock.utcoffset() is None:
        raise ValueError("Explicit timezone required")
    prepared = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    raw = json.loads(args.facts.read_bytes())
    facts = FactsCollection({tuple(key): ProductFacts(**value) for key, value in raw["facts"]})
    facts.version = raw["facts_version"]
    del raw
    shell_egg_quantity_proofs(prepared.universe.products, facts)
    loaded_seconds = time.perf_counter() - started
    request = PlanRequest.model_validate({"recipes": 1, "max_stores": 2,
        "purchase_planning_mode": "exact", "recipe_preferences": {"mode": "complete"},
        "personal": {"allow_nutrition_estimates": True, "use_pantry": False, "meals": [
            {"meal_type": meal, "count": 1, "servings": 4 if meal == "dinner" else 1,
             "recipe_choices": {"min_ingredients": 1, "max_ingredients": 40}, "limits": {}}
            for meal in ("dinner", "breakfast", "snack")]}})
    planner = PersonalPlanner(request, Settings(price_provider="mock", complete_recipes_enabled=True),
        prepared, {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=facts, now=clock)
    initialized_seconds = time.perf_counter() - started
    pack_ids = args.pack_id or ["recipe-intake-reviewed-20261025"]
    recipes = [r for r in current_recipes() if r.design.content_source and r.design.content_source.pack_id in pack_ids]
    shared, results = {}, []
    for recipe in recipes:
        meal = planner.meals[recipe.design.meal_types[0]]
        profile = planner._merged_profile(meal)
        inputs = []
        for ingredient in recipe.ingredients:
            key = (ingredient.canonical_name, ingredient.form, ingredient.unit,
                   ingredient.quantity, tuple(ingredient.product_requirements or ()))
            if key not in shared:
                decision = {"identity": key[0] + "|" + key[1], "quantity": key[3], "unit": key[2],
                            "requirements": list(key[4]), "recipes": []}
                try:
                    candidates = planner.resolve(key[0], key[3], key[2], profile=profile,
                                                 organic_animals=False, recipe=recipe)
                    examples = []
                    for position, candidate in candidates[:3]:
                        product = prepared.universe.products[position]
                        fact = planner.source_facts(product)
                        examples.append({"store_id": product.store_id, "product_id": product.product_id,
                            "name": product.name, "package_quantity": candidate.package_quantity,
                            "package_unit": candidate.package_unit, "usable_quantity": candidate.usable_quantity,
                            "usable_unit": candidate.usable_unit, "source_snapshot_id": product.source_provenance.source_snapshot_id,
                            "facts_present": fact is not None, "nutrition_unit": fact.nutrition_unit if fact else None,
                            "nutrition_preparation": fact.nutrition_preparation if fact else None,
                            "ingredients_complete": fact.ingredients_complete if fact else False,
                            "allergens_checked": list(fact.allergens_checked) if fact else [],
                            "organic": fact.organic if fact else None, "animal": fact.animal if fact else None,
                            "conflicts": list(fact.conflicts) if fact else []})
                    decision.update(status="resolved_product_input", candidate_count=len(candidates), examples=examples)
                except ValueError as exc:
                    decision.update(status="blocked_product_input", candidate_count=0, reason=str(exc),
                                    code=getattr(exc, "code", None), stage=getattr(exc, "stage", None))
                shared[key] = decision
            decision = shared[key]
            decision["recipes"].append(identity(recipe))
            inputs.append({"identity": decision["identity"], "quantity": key[3], "unit": key[2],
                           "requirements": list(key[4]), "status": decision["status"]})
        results.append({"id": identity(recipe), "inputs": inputs,
                        "status": "all_product_inputs_resolved" if all(i["status"] == "resolved_product_input" for i in inputs)
                        else "blocked_product_input", "nutrition_allergen_organic_qualification": "not_performed"})
    report = {"schema_version": "smako-reviewed-input-inventory-v1", "clock": args.clock,
        "runtime_commit": args.runtime_commit, "runtime_app_tree": args.runtime_tree,
        "method_signature": method_signature(),
        "scope": "Explicit historical source replay; shared product input resolution, not weekly or nutritional qualification",
        "universe_sha256": hashlib.sha256(args.universe.read_bytes()).hexdigest(),
        "facts_sha256": hashlib.sha256(args.facts.read_bytes()).hexdigest(),
        "universe_id": prepared.universe.universe_id, "facts_version": facts.version,
        "products": len(prepared.universe.products), "fact_rows": len(facts),
        "conditions": request.model_dump(mode="json"), "recipes": results, "shared_inputs": list(shared.values()),
        "source_loading_seconds": loaded_seconds, "initialized_seconds": initialized_seconds,
        "wall_seconds": time.perf_counter() - started}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded(report))
    probes = []
    for requested in args.probe_id:
        recipe = next(r for r in recipes if identity(r) == requested)
        meal = recipe.design.meal_types[0]
        slot = {"id": meal + "-1", "day": 1, "meal_type": meal, "recipe": recipe.model_dump(mode="json")}
        probe_request = PlanRequest.model_validate({"recipes": 1 if meal == "dinner" else 0, "max_stores": 2,
            "purchase_planning_mode": "exact", "recipe_preferences": {"mode": "complete"},
            "personal": {"allow_nutrition_estimates": True, "use_pantry": False, "slots": [slot],
                "meals": [{"meal_type": meal, "count": 1, "servings": recipe.servings,
                           "recipe_choices": {"min_ingredients": 1, "max_ingredients": 40}, "limits": {}}]}})
        row = {"id": requested, "scope": "Pinned one-meal functional replay; no HTTP/UI latency or global optimum",
               "conditions": probe_request.model_dump(mode="json")}
        probe_started = time.perf_counter()
        try:
            from app.services.plan_store import PlanStore

            plan = PersonalPlanner(probe_request, Settings(price_provider="mock", complete_recipes_enabled=True),
                prepared, {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=facts, now=clock).create()
            checkout = plan.personal.checks.get("checkout_audit")
            if not isinstance(checkout, dict) or checkout.get("passed") is not True:
                raise ValueError("Checkout audit did not pass")
            store = PlanStore(args.plan_store)
            # Each independent probe has a fresh private store scope. Reusing
            # a prior probe's owner with revision=0 would correctly be rejected.
            owner = hashlib.sha256(("isolated-functional-probe:" + requested + ":" + str(uuid4())).encode()).hexdigest()
            saved = store.create(probe_request, plan, owner_actor_hash=owner)
            loaded = store.get_owned(saved.plan_id, owner_actor_hash=owner)
            if loaded.plan.model_dump(mode="json") != saved.plan.model_dump(mode="json"):
                raise ValueError("Saved plan changed on readback")
            row.update(status="saved_and_read_back", total=plan.optimized_basket.total,
                       response_sha256=hashlib.sha256(encoded(loaded.plan.model_dump(mode="json"))).hexdigest(),
                       audit=plan.personal.checks.get("checkout_audit"),
                       meal_nutrition=plan.personal.checks.get("nutrition"))
        except ValueError as exc:
            row.update(status="blocked", reason=str(exc), code=getattr(exc, "code", None), stage=getattr(exc, "stage", None))
        row["wall_seconds"] = time.perf_counter() - probe_started
        probes.append(row)
        report["functional_probes"] = probes
        report["wall_seconds"] = time.perf_counter() - started
        args.output.write_bytes(encoded(report))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded(report))
    print(json.dumps({"recipes": len(results), "shared_inputs": len(shared),
                      "all_product_inputs_resolved": sum(r["status"] == "all_product_inputs_resolved" for r in results),
                      "wall_seconds": report["wall_seconds"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--clock", required=True)
    parser.add_argument("--runtime-commit")
    parser.add_argument("--runtime-tree")
    parser.add_argument("--pack-id", action="append")
    parser.add_argument("--probe-id", action="append", default=[])
    parser.add_argument("--plan-store", type=Path, default=Path(".local/recipes/intake-probes.sqlite3"))
    parser.add_argument("--output", type=Path, required=True)
    inventory(parser.parse_args())
