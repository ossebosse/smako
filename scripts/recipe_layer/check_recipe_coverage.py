"""Serial, resumable 2,200-variant input/checkout coverage. Use budgeted_check.

Each receipt binds the complete price/facts, method, recipe and request scope.
Successful baskets use PersonalPlanner.basket(final=True), including the usual
package calculation, pricing and final audit. Timeout is incomplete search.
"""
import argparse
import json
import time
from collections import Counter
from pathlib import Path

from app.models.personal import MealSlot
from app.services.meal_library_content import identity
from app.services.plan_jobs import PlanningDeadlineExceeded, planning_deadline
from coverage_reference import digest, file_sha, load_reference, planner_for, prior_input_report


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.next')
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n', encoding='utf-8')
    temporary.replace(path)


def input_key(ingredient, meal_type):
    return (ingredient.canonical_name, ingredient.form, ingredient.unit,
            ingredient.quantity, tuple(ingredient.product_requirements or ()), meal_type)


def input_result(planner, recipe, ingredient):
    try:
        candidates = planner.resolve(ingredient.canonical_name, ingredient.quantity, ingredient.unit,
            profile=planner._merged_profile(planner.meals[recipe.design.meal_types[0]]),
            organic_animals=False, recipe=recipe)
        return {'status': 'resolved', 'candidate_count': len(candidates), 'candidate_refs': [
            {'store_id': c.store_id, 'product_id': c.product_id, 'usable_quantity': c.usable_quantity,
             'usable_unit': c.usable_unit, 'quantity_confidence': str(c.quantity_confidence),
             'source_snapshot_id': planner.prepared.universe.products[n].source_provenance.source_snapshot_id}
            for n, c in candidates[:3]]}
    except ValueError as error:
        return {'status': 'data_blocked', 'reason': str(error), 'code': getattr(error, 'code', None)}


def receipt_key(scope, recipe, mode, checker_sha):
    return digest({'scope': scope, 'recipe': recipe.model_dump(mode='json'), 'mode': mode,
                   'checker_sha256': checker_sha})


def read_receipt(path, expected):
    try:
        row = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if row.get('dependencies') != expected:
        return None
    if row.get('status') == 'verified':
        # An edited/truncated receipt cannot retain a successful status.
        evidence = row.get('evidence', {})
        if digest(evidence) != row.get('evidence_sha256') or not evidence.get('audit', {}).get('passed'):
            return None
    return row


def check_basket(planner, recipe, seconds):
    meal = recipe.design.meal_types[0]
    slot = MealSlot(id=meal + '-1', day=1, meal_type=meal, recipe=recipe)
    started = time.perf_counter()
    try:
        with planning_deadline(seconds):
            result = planner.basket([slot], final=True)
        evidence = {'basket': result['basket'].model_dump(mode='json'),
                    'audit': result['audit'].model_dump(mode='json'), 'checks': result['checks'],
                    'remaining_demands': result['remaining_demands']}
        assert evidence['audit']['passed'] and result['basket'].store_count <= 2
        return {'status': 'verified', 'evidence': evidence, 'evidence_sha256': digest(evidence)}
    except PlanningDeadlineExceeded:
        return {'status': 'search_incomplete', 'reason': 'per-variant cooperative deadline; no impossibility claim'}
    except ValueError as error:
        return {'status': 'checkout_blocked', 'reason': str(error), 'stage': getattr(error, 'stage', None),
                'code': getattr(error, 'code', None)}
    finally:
        planner._coverage_last_seconds = time.perf_counter() - started


def main(args):
    started = time.perf_counter()
    prepared, facts, references, recipes, scope = load_reference(args)
    checker_sha = digest([file_sha(__file__), file_sha(Path(__file__).with_name('coverage_reference.py'))])
    report = {'schema': 'smako-recipe-coverage-v1', 'scope': scope,
              'checker_sha256': checker_sha, 'denominator': 2200,
              'variants': [{'original_id': original, 'current_id': identity(recipe), 'modes': {}}
                           for original, recipe in zip(references, recipes, strict=True)], 'modes': {}}
    before = prior_input_report(json.loads(args.before.read_bytes()), compared_scope=scope)
    assert before['imported_reference_ids'] == references
    assert before['recipe_ids'] == [identity(r) for r in recipes]
    assert before['universe_sha256'] == scope['universe_sha256'] and before['clock'] == scope['clock']
    print({'loaded_seconds': time.perf_counter() - started, 'scope': digest(scope)}, flush=True)
    for mode in ['exact', 'estimated']:
        planner = planner_for(mode, prepared, facts, scope)
        shared = {}
        for index, recipe in enumerate(recipes):
            keys = []
            for ingredient in recipe.ingredients:
                key = input_key(ingredient, recipe.design.meal_types[0])
                keys.append(key)
                if key not in shared:
                    shared[key] = {'name': key[0], 'form': key[1], 'unit': key[2], 'quantity': key[3],
                                   'requirements': list(key[4]), **input_result(planner, recipe, ingredient)}
            blocked = sorted({digest(shared[key]) for key in keys if shared[key]['status'] != 'resolved'})
            row = report['variants'][index]['modes'][mode] = {
                'inputs': 'data_blocked' if blocked else 'resolved', 'blocking_scope_ids': blocked,
                'basket': 'data_blocked' if blocked else 'not_checked', 'receipt': None}
            expected = receipt_key(scope, recipe, mode, checker_sha)
            path = args.checkpoints / mode / (digest(references[index]) + '.json')
            prior = read_receipt(path, expected)
            if prior and (prior['status'] != 'search_incomplete' or not args.retry_incomplete):
                row.update(basket=prior['status'], receipt=path.as_posix())
            elif not blocked and args.baskets and time.perf_counter() - started < args.work_seconds:
                receipt = {'original_id': references[index], 'current_id': identity(recipe),
                           'mode': mode, 'dependencies': expected,
                           **check_basket(planner, recipe, args.variant_seconds)}
                receipt['wall_seconds'] = planner._coverage_last_seconds
                atomic_json(path, receipt)
                row.update(basket=receipt['status'], receipt=path.as_posix())
            row['next_action'] = ('supply_reviewed_source_facts_for_blocking_scopes' if blocked
                                  else 'none' if row['basket'] == 'verified' else 'resume_bounded_checkout')
            if index % 100 == 0:
                atomic_json(args.output, report)
                print({'mode': mode, 'index': index, 'seconds': round(time.perf_counter() - started, 2)}, flush=True)
        resolved = {i for i, row in enumerate(report['variants']) if row['modes'][mode]['inputs'] == 'resolved'}
        old = set(before['modes'][mode]['resolved_indices'])
        report['modes'][mode] = {'resolved': len(resolved), 'before_resolved': len(old),
            'newly_resolved_indices': sorted(resolved - old), 'lost_indices': sorted(old - resolved),
            'basket_status': dict(Counter(row['modes'][mode]['basket'] for row in report['variants'])),
            'input_scopes': {digest(row): row for row in shared.values()}}
        atomic_json(args.output, report)
        del planner
    report['wall_seconds'] = time.perf_counter() - started
    atomic_json(args.output, report)
    print({m: {k: v for k, v in r.items() if k != 'input_scopes' and not isinstance(v, list)}
           for m, r in report['modes'].items()}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'output', 'checkpoints', 'before']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    p.add_argument('--baskets', action='store_true')
    p.add_argument('--retry-incomplete', action='store_true')
    p.add_argument('--work-seconds', type=float, default=240)
    p.add_argument('--variant-seconds', type=float, default=1)
    main(p.parse_args())
