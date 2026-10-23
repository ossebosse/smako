"""Cheap per-recipe proxy (sum of each row's cheapest quote) against qualified single paid.

proxy_probe.py <data-dir> <case> <out.json>
"""
import json
import socket
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models.personal import MealSlot
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import current_recipe_generations

from backend.scripts.planner_acceptance_matrix import matrix_request

data, case, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
manifest = json.loads((data / "matrix-inputs.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((data / "combined-prices.json").read_bytes()).restore()
raw = json.loads((data / "combined-facts.json").read_bytes())
facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
request = matrix_request(json.loads((data / "combined-request.json").read_bytes()), case)
settings = replace(Settings(complete_recipes_enabled=True, price_provider="own"), library_substitution_slot_limit=16)
planner = PersonalPlanner(request, settings, prepared, {"revision": 0, "items": [], "reservations": {}, "events": {}},
                          facts=facts, now=datetime.fromisoformat(manifest["now"]))
with patch.object(socket.socket, "connect", side_effect=AssertionError("net")):
    plan = planner.create()
    from app.services.meal_library_content import identity
    generations = current_recipe_generations(planner.library_generation)
    recipes = {}
    for meal in planner.meals.values():
        from app.services.recipe_library import meal_candidates
        for recipe in meal_candidates(meal, request.recipe_preferences, include_supplement=planner.include_content_pack,
                                      generation=planner.library_generation):
            key = (meal.meal_type, planner._recipe_id(recipe))
            if key in planner.variant_search_evidence:
                recipes[key] = (meal, recipe)
    rows, started = [], time.perf_counter()
    for (meal_type, rid), (meal, recipe) in recipes.items():
        cleaned = planner.clean_recipe(recipe, meal)
        slot = MealSlot(id=f"{meal_type}-1", day=1, meal_type=meal_type, recipe=cleaned)
        proxy = 0.0
        for need in planner._need_rows([slot]):
            if need["quantity"] <= 0:
                continue
            resolved = planner.resolve_choices(
                need["name"], need["quantity"], need["unit"], product_key=need["product_key"],
                alternatives=need.get("alternatives", ()), properties=need["properties"], profile=need["profile"],
                organic_animals=need["organic_animals"], food=need["food"],
                campaign_choice=need.get("campaign_choice", False), purchase_units=need.get("purchase_units", False),
                recipe=cleaned)
            from app.models.ingredient import NormalizedIngredient
            ing = NormalizedIngredient(canonical_name=need["name"], required_quantity=need["quantity"], unit=need["unit"])
            quotes = planner.optimizer._candidate_quotes(ing, tuple(c for _i, c in resolved))
            proxy += float(min((q.total_price for q in quotes), default=0))
        ev = planner.variant_search_evidence[(meal_type, rid)]
        rows.append({"meal_type": meal_type, "id": rid, "generation": generations.get(identity(recipe)),
                     "paid": float(ev.paid), "proxy": proxy})
    proxy_seconds = time.perf_counter() - started
chosen = {planner._recipe_id(s.recipe) for s in plan.personal.slots if s.recipe}
by_gen = {}
for r in rows:
    by_gen.setdefault((r["meal_type"], r["generation"]), []).append(r)
ranks = []
for g in by_gen.values():
    g.sort(key=lambda r: r["proxy"])
    ranks += [(k, len(g)) for k, r in enumerate(g) if r["id"] in chosen]
import statistics

ratio = [r["proxy"] / r["paid"] for r in rows if r["paid"]]
summary = {"final": plan.optimized_basket.total, "recipes": len(rows), "proxy_seconds": round(proxy_seconds, 1),
           "proxy_over_paid_min": min(ratio), "proxy_over_paid_median": statistics.median(ratio),
           "chosen_rank_in_generation_by_proxy": ranks}
out.write_text(json.dumps({"summary": summary, "rows": rows}), encoding="utf-8")
print(json.dumps(summary))
