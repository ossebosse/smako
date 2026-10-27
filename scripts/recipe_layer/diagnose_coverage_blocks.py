"""Bounded explanations for remaining real-product and full-basket failures."""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.models.personal import MealSlot
from app.services.ingredient_normalizer import _search_text
from app.services.plan_jobs import planning_deadline
from coverage_reference import load_reference, planner_for


def main(args):
    prepared, facts, _references, recipes, scope = load_reference(args)
    coverage = json.loads(args.coverage.read_bytes())
    assert coverage['scope'] == scope
    planner = planner_for('estimated', prepared, facts, scope)
    output = {'scope': scope, 'groups': {}, 'basket_failures': []}
    for name in args.group:
        recipe = next(r for r in recipes if any(i.canonical_name == name for i in r.ingredients))
        ingredient = next(i for i in recipe.ingredients if i.canonical_name == name)
        watched = [p for p in prepared.universe.products if _search_text(name) in _search_text(p.name)]
        planner.product_trace.products = {(p.store_id, p.product_id): {
            'name': p.name, 'store_id': p.store_id, 'product_id': p.product_id, 'contexts': {}}
            for p in watched}
        try:
            candidates = planner.resolve(name, ingredient.quantity, ingredient.unit,
                profile=planner._merged_profile(planner.meals[recipe.design.meal_types[0]]), recipe=recipe)
            outcome = {'resolved': len(candidates)}
        except ValueError as error:
            outcome = {'reason': str(error), 'code': getattr(error, 'code', None)}
        rows = []
        for p in watched:
            f = planner.source_facts(p)
            rows.append({'product': p.model_dump(mode='json'), 'facts': asdict(f) if f else None,
                         'trace': planner.product_trace.products[(p.store_id, p.product_id)]})
        output['groups'][name] = {'outcome': outcome, 'products': rows}
    exact = planner_for('exact', prepared, facts, scope)
    for index, row in enumerate(coverage['variants']):
        if row['modes']['exact']['basket'] != 'checkout_blocked':
            continue
        recipe = recipes[index]
        slot = MealSlot(id=recipe.design.meal_types[0] + '-1', day=1,
                        meal_type=recipe.design.meal_types[0], recipe=recipe)
        result = {'current_id': row['current_id'], 'ingredients': [i.model_dump(mode='json') for i in recipe.ingredients]}
        for cap in [2, 3]:
            exact.request = exact.request.model_copy(update={'max_stores': cap})
            try:
                with planning_deadline(3):
                    basket = exact.basket([slot], final=True)
                result[str(cap)] = {'passed': basket['audit'].passed, 'total': basket['basket'].total,
                                    'stores': [s.store_id for s in basket['basket'].stores]}
            except ValueError as error:
                result[str(cap)] = {'reason': str(error), 'stage': getattr(error, 'stage', None)}
        output['basket_failures'].append(result)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print({name: row['outcome'] for name, row in output['groups'].items()}, flush=True)
    print(output['basket_failures'], flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'coverage', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    p.add_argument('--group', action='append', default=[])
    main(p.parse_args())
