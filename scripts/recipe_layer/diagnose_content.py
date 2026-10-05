"""Offline first-stop and independent-ingredient evidence through the real planner.

The extra ingredient passes are diagnostic only: they do not replace a failed
whole recipe, edit candidates, lower targets or supply any source facts.
"""
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSlot
from app.models.recipe_preferences import RecipePreferences
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import merged_profile
from app.services.personal_source_facts import facts_version, load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import candidates


def main():
    label = sys.argv[1]
    output = Path('/results') / label
    output.mkdir(parents=True, exist_ok=False)
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        Path('/inputs/universe.json').read_bytes()).restore()
    facts = load_retained_facts(prepared)
    clock = datetime.fromisoformat(json.loads(Path('/inputs/freeze.json').read_text())['frozen_at_utc'])
    recipes = [r for r in candidates(RecipePreferences(mode='complete'), 2)
               if r.design.content_source]
    report = {'facts_version': facts_version(facts), 'clock': clock.isoformat(),
              'universe_id': prepared.universe.universe_id, 'modes': {}}
    products = {}
    for mode in ('exact', 'estimated'):
        request = PlanRequest(recipes=0, max_stores=2, purchase_planning_mode=mode,
            recipe_preferences={'mode': 'complete'}, personal={'allow_nutrition_estimates': True,
            'meals': [{'count': 1, 'servings': 2, 'limits': {'min_protein_g': 0,
                'min_carbs_g': 0, 'min_fat_g': 0, 'max_kcal': 4000}}]})
        planner = PersonalPlanner(request, Settings(price_provider='own', complete_recipes_enabled=True),
            prepared, {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts, now=clock)
        # Widen only observability. Candidate retrieval, policy and prices stay
        # unchanged. The normal trace caps otherwise omit many catalog items.
        for product in prepared.universe.products:
            planner.product_trace.products.setdefault((product.store_id, product.product_id),
                {'indexes': {}, 'contexts': {}, 'selected': False})
        events = []

        def observe(product, recipe, ingredient, stage, outcome, reason, planner=planner, events=events, **evidence):
            key = product.store_id + '/' + product.product_id
            if key not in products:
                fact = planner.source_facts(product)
                products[key] = {'product': product.model_dump(mode='json'),
                                 'fact': asdict(fact) if fact else None}
            events.append({'product_ref': key, 'stage': stage, 'outcome': outcome,
                           'reason': reason, **evidence})

        planner.product_trace.event = observe
        mode_rows = report['modes'][mode] = []
        for recipe in recipes:
            row = {'proposal_id': recipe.design.content_source.proposal_id,
                   'base_id': recipe.design.base_id, 'version': recipe.design.version,
                   'variant_id': recipe.design.variant_id, 'cuisine': recipe.design.cuisines,
                   'family': recipe.design.family, 'name': recipe.name, 'ingredients': []}
            slot = MealSlot(id='dinner-1', day=1, meal_type='dinner', recipe=recipe)
            try:
                result = planner.basket([slot])
                row['qualification'] = {'status': 'qualified', 'basket': result['basket'].model_dump(mode='json'),
                    'checks': result['checks'], 'audit': result['audit'].model_dump(mode='json')}
            except ValueError as exc:
                row['qualification'] = {'status': 'stopped', 'first_stop': str(exc),
                    'code': getattr(exc, 'code', None), 'stage': getattr(exc, 'stage', None)}
            # Examine each other ingredient independently, without claiming the
            # original recipe passed its earlier first stop.
            sources = {canonicalize_ingredient_name(i.name): i for i in recipe.ingredients}
            meal = planner.meals['dinner']
            for ingredient in planner.service.normalizer.normalize_and_aggregate([recipe]):
                source = sources[ingredient.canonical_name]
                need = {'name': ingredient.canonical_name, 'quantity': ingredient.required_quantity,
                    'unit': ingredient.unit, 'input_form': source.form,
                    'product_requirements': source.product_requirements, 'product_key': None, 'properties': [],
                    'profile': merged_profile(planner.spec.profile, meal.profile),
                    'organic_animals': planner.spec.organic_animals or meal.organic_animals, 'food': True}
                events.clear()
                record = {k: need.get(k) for k in ('name', 'quantity', 'unit', 'input_form', 'product_requirements')}
                try:
                    resolved = planner.resolve(need['name'], need['quantity'], need['unit'],
                        product_key=need['product_key'], properties=need['properties'], profile=need['profile'],
                        organic_animals=need['organic_animals'], food=need['food'], recipe=recipe)
                    nutrition = []
                    for i, _ in resolved:
                        product = prepared.universe.products[i]
                        fact = planner.nutrition_evidence(product, need['name'], need['unit'],
                            {'protein_g', 'carbs_g', 'fat_g', 'kcal'}, recipe)
                        nutrition.append({'product_ref': product.store_id + '/' + product.product_id,
                            'status': 'qualified' if fact and {'protein_g', 'carbs_g', 'fat_g', 'kcal'} <= fact.nutrition.keys()
                                      and fact.nutrition_unit == need['unit'] and fact.nutrition_preparation == 'as_sold'
                                      else 'missing_or_incompatible',
                            'evidence': asdict(fact) if fact else None})
                    record.update(status='purchase_candidates', nutrition=nutrition)
                except ValueError as exc:
                    record.update(status='stopped', reason=str(exc), code=getattr(exc, 'code', None))
                record['candidate_events'] = list(events)
                row['ingredients'].append(record)
            mode_rows.append(row)
            print(mode, row['proposal_id'], row['qualification']['status'], flush=True)
        (output / 'recipes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        (output / 'products.json').write_text(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
