"""One serial, source-bound before/after inventory of corrected intake content."""
import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.services import product_semantics
from app.services.meal_library_content import ROOT, encoded, identity
from app.services.official_product_facts import shell_egg_quantity_proofs
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import current_recipes


def main(args):
    start = time.perf_counter()
    prepared = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    raw = json.loads(args.facts.read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
    facts.version = raw["facts_version"]
    del raw
    shell_egg_quantity_proofs(prepared.universe.products, facts)
    original = json.loads((ROOT.parents[3] / "docs/reviews/recipe-integration-all-20261026/all-recipes.json").read_bytes())
    amended = json.loads((ROOT.parents[3] / "docs/reviews/recipe-quality-and-planning-20261026/recipe-review.json").read_bytes())
    replace = {r["previous_id"]: r["runtime_id"] for r in amended["recipes"]}
    by_id = {identity(r): r for r in current_recipes()}
    recipes = [by_id[replace.get(r["runtime_id"], r["runtime_id"])] for r in original["recipes"]]
    reused = json.loads(args.reuse.read_bytes()) if args.reuse else None
    result = {"scope": "Corrected current 2200 intake variants; individual inputs, not joint basket/nutrition approval",
              "universe_sha256": hashlib.sha256(args.universe.read_bytes()).hexdigest(),
              "facts_sha256": hashlib.sha256(args.facts.read_bytes()).hexdigest(),
              "facts_version": facts.version, "clock": args.clock,
              "source_loading_seconds": time.perf_counter() - start,
              "modes": json.loads(args.retain.read_bytes())["modes"] if args.retain else {}}
    settings = Settings(price_provider="mock", complete_recipes_enabled=True)
    if reused:
        assert reused['universe_sha256'] == result['universe_sha256']
        assert reused['facts_sha256'] == result['facts_sha256']
        result['reused_non_corn_evidence_sha256'] = hashlib.sha256(args.reuse.read_bytes()).hexdigest()
    print({'source_loading_seconds': result['source_loading_seconds']}, flush=True)
    for mode in args.mode or ("exact", "estimated"):
        request = PlanRequest.model_validate({"recipes": 1, "max_stores": 2, "purchase_planning_mode": mode,
            "recipe_preferences": {"mode": "complete"}, "personal": {"allow_nutrition_estimates": True,
            "use_pantry": False, "meals": [{"meal_type": m, "count": 1, "servings": 4 if m == "dinner" else 1,
                "recipe_choices": {"min_ingredients": 1, "max_ingredients": 40}, "limits": {}}
                for m in ("dinner", "breakfast", "snack")]}})
        pantry = {"revision": 0, "items": [], "reservations": {}, "events": {}}
        planner = None if reused else PersonalPlanner(request, settings, prepared, pantry, facts=facts, now=datetime.fromisoformat(args.clock))
        shared, rows = {}, []
        prior = {(v['identity'].split('|')[0], v['identity'].split('|')[1], v['unit'], v['quantity'], tuple(v['requirements'])): v
                 for v in reused['modes'][mode]['shared_inputs']} if reused else {}

        def resolve(i, recipe, subject):
            profile = subject._merged_profile(subject.meals[recipe.design.meal_types[0]])
            try:
                candidates = subject.resolve(i.canonical_name, i.quantity, i.unit, profile=profile,
                                             organic_animals=False, recipe=recipe)
                return {"status": "resolved", "candidate_count": len(candidates), "examples": [
                    {"store_id": prepared.universe.products[n].store_id, "product_id": prepared.universe.products[n].product_id,
                     "name": prepared.universe.products[n].name, "source_snapshot_id": prepared.universe.products[n].source_provenance.source_snapshot_id,
                     "usable_quantity": c.usable_quantity, "unit": c.usable_unit} for n, c in candidates[:3]]}
            except ValueError as exc:
                return {"status": "blocked", "reason": str(exc), "code": getattr(exc, "code", None)}

        # Baseline differs ONLY by removing the new frozen-kernel label rule.
        # Use a separate request-owned planner/cache before measuring current.
        rule = product_semantics._frozen_corn_identity
        before_corn = {}
        product_semantics._frozen_corn_identity = lambda name, category: None
        try:
            for r in recipes:
                for i in r.ingredients:
                    key = (i.canonical_name, i.form, i.unit, i.quantity, tuple(i.product_requirements or ()))
                    if i.canonical_name == "majs" and key not in before_corn:
                        before_corn[key] = prior[key] if reused else resolve(i, r, planner)
        finally:
            product_semantics._frozen_corn_identity = rule
        planner = PersonalPlanner(request, settings, prepared, pantry, facts=facts, now=datetime.fromisoformat(args.clock))
        for r in recipes:
            keys = []
            for i in r.ingredients:
                key = (i.canonical_name, i.form, i.unit, i.quantity, tuple(i.product_requirements or ()))
                if key not in shared:
                    shared[key] = {"identity": i.canonical_name + "|" + i.form, "quantity": i.quantity,
                        "unit": i.unit, "requirements": list(i.product_requirements or ()), "recipes": [], **({k: v for k, v in prior[key].items() if k not in ("recipes",)} if reused and i.canonical_name != "majs" else resolve(i, r, planner))}
                shared[key]["recipes"].append(identity(r))
                keys.append(key)
            before = all((before_corn.get(k) or shared[k])["status"] == "resolved" for k in keys)
            after = all(shared[k]["status"] == "resolved" for k in keys)
            rows.append({"id": identity(r), "before_all_inputs_resolved": before, "all_inputs_resolved": after})
        result["modes"][mode] = {"conditions": request.model_dump(mode="json"),
            "before_resolved": sum(r["before_all_inputs_resolved"] for r in rows),
            "after_resolved": sum(r["all_inputs_resolved"] for r in rows),
            "newly_resolved": [r["id"] for r in rows if r["all_inputs_resolved"] and not r["before_all_inputs_resolved"]],
            "recipes": rows, "shared_inputs": list(shared.values()),
            "blocked_scopes_by_identity": dict(Counter(r["identity"] for r in shared.values() if r["status"] == "blocked"))}
        args.output.write_bytes(encoded(result))
    result["wall_seconds"] = time.perf_counter() - start
    args.output.write_bytes(encoded(result))
    print({m: {k: r[k] for k in ("before_resolved", "after_resolved")} for m, r in result["modes"].items()})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--universe", type=Path, required=True)
    p.add_argument("--facts", type=Path, required=True)
    p.add_argument("--clock", required=True)
    p.add_argument("--reuse", type=Path)
    p.add_argument("--retain", type=Path)
    p.add_argument("--mode", action="append", choices=["exact", "estimated"])
    p.add_argument("--output", type=Path, required=True)
    main(p.parse_args())
