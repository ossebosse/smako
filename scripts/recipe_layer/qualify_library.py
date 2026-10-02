"""First actual stop per authored recipe on frozen public sources, normal engine."""
import dataclasses
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSlot
from app.models.recipe_preferences import RecipePreferences
from app.services.performance_trace import activate_performance_trace
from app.services.personal_planner import PersonalPlanner
from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import candidates, validate_library


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'qualification'
    mode = sys.argv[2] if len(sys.argv) > 2 else 'estimated'
    root = Path('/results') / label
    root.mkdir(parents=True, exist_ok=True)
    prepared = PreparedPriceUniverseArtifact.model_validate_json(Path('/inputs/universe.json').read_bytes()).restore()
    clock = datetime.fromisoformat(json.loads(Path('/inputs/freeze.json').read_text())['frozen_at_utc'])
    started = time.perf_counter()
    facts = load_retained_facts(prepared)
    fact_seconds = time.perf_counter() - started
    request = PlanRequest(recipes=0, max_stores=2, diversity_mode='cheapest', purchase_planning_mode=mode,
        recipe_preferences={'mode': 'complete'}, personal={'allow_nutrition_estimates': True,
        'meals': [{'count': 1, 'servings': 2, 'limits': {'min_protein_g': 0, 'min_carbs_g': 0, 'min_fat_g': 0, 'max_kcal': 4000}}]})
    planner = PersonalPlanner(request, Settings(price_provider='mock', complete_recipes_enabled=True), prepared,
        {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts, now=clock)
    report = {'library': validate_library(), 'fact_seconds': fact_seconds, 'mode': mode, 'recipes': [],
              'stage': json.loads(Path('/evaluation/stage.json').read_text())}
    for recipe in candidates(RecipePreferences(mode='complete'), servings=2):
        record = {'id': recipe.design.base_id, 'variant': recipe.design.variant_id, 'name': recipe.name,
                  'cuisine': recipe.design.cuisines[0], 'ingredients': recipe.design.ingredient_count}
        started = time.perf_counter()
        with activate_performance_trace() as trace:
            try:
                clean = planner.clean_recipe(recipe, planner.meals['dinner'])
                slot = MealSlot(id='dinner-1', day=1, meal_type='dinner', recipe=clean)
                result = planner.basket([slot])
                record.update(status='qualified', result_keys=list(result),
                              basket=result['basket'].model_dump(mode='json'))
                record['checks'] = result.get('checks')
                record['audit'] = result.get('audit')
            except ValueError as exc:
                record.update(status='stopped', reason=str(exc), stage=getattr(exc, 'stage', None), code=getattr(exc, 'code', None))
        record['seconds'] = time.perf_counter() - started
        record['trace'] = dataclasses.asdict(trace.snapshot())
        report['recipes'].append(record)
        (root / 'qualification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
        print(json.dumps({k: v for k, v in record.items() if k not in {'basket', 'trace', 'nutrition'}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
