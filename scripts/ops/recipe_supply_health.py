"""Read-only recipe supply check for every active PriceUniverse.

Run inside the app container (it has the code, prices and facts):

    ssh smako 'sudo -n docker exec -i smako-app-1 nice -n 19 python - --json' < scripts/ops/recipe_supply_health.py

For each distinct authored ingredient group (name, input form, unit and
product requirements) it asks the ordinary planner resolver, in the
estimated purchase mode with every store of the universe allowed, whether
anything is buyable. Groups with no candidate block every recipe variant
that uses them. Nothing is written; no network, no plans, no user data.
"""
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

for path in ("/srv/app/backend", "/srv/app"):
    if path not in sys.path:
        sys.path.insert(0, path)

ACTIVE = Path("/srv/app/var/price_universes/active")


def request(stores):
    from app.models import PlanRequest
    return PlanRequest.model_validate({
        "recipes": 1, "max_stores": 2, "allowed_store_ids": sorted(stores),
        "purchase_planning_mode": "estimated", "recipe_preferences": {"mode": "complete"},
        "personal": {"allow_nutrition_estimates": True, "use_pantry": False,
                     "meals": [{"meal_type": m, "count": 1, "servings": 4 if m == "dinner" else 1,
                                "recipe_choices": {"min_ingredients": 1, "max_ingredients": 40}, "limits": {}}
                               for m in ("dinner", "breakfast", "snack")]}})


def check(manifest_path, recipes):
    from app.config import Settings
    from app.services.official_product_facts import shell_egg_quantity_proofs
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_source_facts import load_retained_facts
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
    from app.services.recipe_library import _scaled

    started = time.monotonic()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    prepared = PreparedPriceUniverseArtifact.from_file(manifest_path.parent.parent / manifest["artifact_file"]).restore()
    facts = load_retained_facts(prepared)
    shell_egg_quantity_proofs(prepared.universe.products, facts)
    stores = {p.store_id for p in prepared.universe.products}
    planner = PersonalPlanner(request(stores), Settings(price_provider="mock", complete_recipes_enabled=True),
                              prepared, {"revision": 0, "items": [], "reservations": {}, "events": {}},
                              facts=facts, now=datetime.now(UTC))
    groups = {}
    for recipe in recipes:
        scaled = _scaled(recipe, {"dinner": 4, "breakfast": 1, "snack": 1}[recipe.design.meal_types[0]])
        for item in planner.service.normalizer.normalize_and_aggregate([scaled]):
            source = next(i for i in scaled.ingredients if i.canonical_name == item.canonical_name)
            key = (item.canonical_name, source.form, item.unit, tuple(source.product_requirements or ()))
            groups.setdefault(key, {"example": (scaled, item), "variants": set(), "bases": set()})
            groups[key]["variants"].add(f"{recipe.design.base_id}:{recipe.design.variant_id}")
            groups[key]["bases"].add(recipe.design.base_id)
    blocked = []
    for key, group in groups.items():
        recipe, item = group["example"]
        meal = planner.meals[recipe.design.meal_types[0]]
        try:
            found = planner.resolve(item.canonical_name, item.required_quantity, item.unit,
                                    profile=planner._merged_profile(meal), organic_animals=False, recipe=recipe)
            if found:
                continue
        except ValueError:
            pass
        blocked.append({"ingredient": key[0], "form": key[1], "unit": key[2], "requirements": list(key[3]),
                        "variants": len(group["variants"]), "dishes": len(group["bases"]),
                        "example_dish": recipe.name})
    blocked_variants = set().union(*(groups[(b["ingredient"], b["form"], b["unit"], tuple(b["requirements"]))]["variants"]
                                     for b in blocked)) if blocked else set()
    blocked.sort(key=lambda b: (-b["variants"], b["ingredient"]))
    return {"city": manifest.get("city"), "universe_id": manifest.get("universe_id"),
            "built_at": manifest.get("built_at"), "products": len(prepared.universe.products),
            "ingredient_groups": len(groups), "blocked_groups": len(blocked),
            "blocked_variants": len(blocked_variants), "active_variants": len(recipes),
            "blocked": blocked, "seconds": round(time.monotonic() - started, 1)}


def main():
    from app.services.recipe_library import current_recipes
    recipes = current_recipes()
    report = {"schema": "smako-recipe-supply-health-v1", "checked_at": datetime.now(UTC).isoformat(),
              "build_id": __import__("os").environ.get("BUILD_ID"), "universes": []}
    for path in sorted(ACTIVE.glob("city-*.json")):
        report["universes"].append(check(path, recipes))
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
