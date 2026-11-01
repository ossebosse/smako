"""Probe explicit packs against a frozen reference; never import or approve them."""
import argparse
import json
import os
import time
from collections import Counter
from pathlib import Path

from app.models.personal import MealSlot
from app.services.meal_library_content import encoded, identity, validate_pack_bytes
from app.services.plan_jobs import PlanningDeadlineExceeded, planning_deadline
from coverage_reference import file_sha, load_reference, planner_for


def main(args):
    os.environ['RECIPE_PREPARATION_CACHE_ROOT'] = str(args.output.parent / 'preparation')
    checked = validate_pack_bytes(args.pack.read_bytes())
    if checked['rejections']:
        raise ValueError(checked['rejections'])
    recipes = checked['recipes']
    if args.exclude_review:
        excluded = {r[k] for r in json.loads(args.exclude_review.read_bytes())['recipes']
                    for k in ('source_id', 'runtime_id')}
        recipes = [r for r in recipes if identity(r) not in excluded]
    prepared, facts, _refs, _issued, scope = load_reference(args)
    report = {'scope': scope, 'pack_sha256': file_sha(args.pack), 'input_only': args.input_only,
              'native_recipes': len(recipes), 'deadline_seconds': args.variant_seconds, 'modes': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    print('Loaded frozen reference:', len(prepared.universe.products), 'products;', len(recipes), 'recipes', flush=True)
    for mode in ('exact', 'estimated'):
        planner = planner_for(mode, prepared, facts, scope)
        report['modes'][mode] = {'recipes': []}
        for n, recipe in enumerate(recipes):
            start = time.perf_counter()
            meal = planner.meals[recipe.design.meal_types[0]]
            blocked = []
            for item in recipe.ingredients:
                try:
                    planner.resolve(item.canonical_name, item.quantity, item.unit,
                                    profile=planner._merged_profile(meal), organic_animals=False, recipe=recipe)
                except ValueError as exc:
                    blocked.append({'identity': item.canonical_name + '|' + item.form,
                                    'reason': str(exc), 'code': getattr(exc, 'code', None)})
            record = {'id': identity(recipe), 'name': recipe.name, 'input_blocks': blocked}
            if blocked:
                record['status'] = 'data_blocked'
            elif args.input_only:
                record['status'] = 'inputs_resolved_not_checked_out'
            else:
                try:
                    clean = planner.clean_recipe(recipe, meal)
                    with planning_deadline(args.variant_seconds):
                        result = planner.basket([MealSlot(id='probe-1', day=1,
                            meal_type=recipe.design.meal_types[0], recipe=clean)], final=True)
                    assert result['audit'].passed and result['basket'].store_count <= planner.request.max_stores
                    record.update(status='verified', audit=result['audit'].model_dump(mode='json'),
                                  basket=result['basket'].model_dump(mode='json'))
                except PlanningDeadlineExceeded:
                    record.update(status='search_incomplete')
                except ValueError as exc:
                    record.update(status='checkout_blocked', reason=str(exc), code=getattr(exc, 'code', None))
            record['seconds'] = round(time.perf_counter() - start, 4)
            report['modes'][mode]['recipes'].append(record)
            args.output.write_bytes(encoded(report))
            if n % 20 == 0:
                print(mode, n + 1, dict(Counter(r['status'] for r in report['modes'][mode]['recipes'])), flush=True)
        print(mode, dict(Counter(r['status'] for r in report['modes'][mode]['recipes'])), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', type=Path, required=True)
    parser.add_argument('--universe', type=Path, required=True)
    parser.add_argument('--facts', type=Path, required=True)
    parser.add_argument('--clock', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exclude-review', type=Path)
    parser.add_argument('--input-only', action='store_true')
    parser.add_argument('--variant-seconds', type=float, default=20)
    main(parser.parse_args())
