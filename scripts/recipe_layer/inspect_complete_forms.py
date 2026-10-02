"""Read-only ingredient qualification evidence from the frozen public universe."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import TasteProfile
from app.models.recipe_preferences import RecipePreferences
from app.services.complete_recipes import product_form_compatible
from app.services.personal_planner import PersonalPlanner
from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_search import ProductSearchRequest
from app.services.recipe_library import candidates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ingredients', nargs='+', default=['bönor', 'kidneybönor', 'kikärtor', 'linser', 'kapris', 'oliver', 'tortillas', 'salt', 'gurka', 'citronjuice', 'limejuice', 'jordnötssmör'])
    parser.add_argument('--report', default='ingredient-forms')
    args = parser.parse_args()
    if not args.report.replace('-', '').replace('_', '').isalnum():
        parser.error('report must be a simple directory name')
    prepared = PreparedPriceUniverseArtifact.model_validate_json(Path('/inputs/universe.json').read_bytes()).restore()
    clock = datetime.fromisoformat(json.loads(Path('/inputs/freeze.json').read_text())['frozen_at_utc'])
    request = PlanRequest(max_stores=2, purchase_planning_mode='estimated', recipe_preferences={'mode': 'complete'},
        personal={'allow_nutrition_estimates': True, 'meals': [{'count': 1, 'servings': 2}]})
    planner = PersonalPlanner(request, Settings(price_provider='mock', complete_recipes_enabled=True), prepared,
        {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=load_retained_facts(prepared), now=clock)
    library = candidates(RecipePreferences(mode='complete'), 2)
    report = {}
    for name in args.ingredients:
        recipe = next(r for r in library if any(i.canonical_name == name for i in r.ingredients))
        ingredient = next(i for i in recipe.ingredients if i.canonical_name == name)
        try:
            resolved = planner.resolve(name, ingredient.quantity, ingredient.unit, profile=TasteProfile(), recipe=recipe)
            resolved_ids = {i for i, _ in resolved}
            error = None
        except ValueError as exc:
            resolved_ids, error = set(), str(exc)
        keys, _, _ = planner.index.retrieve(ProductSearchRequest(query=name))
        rows = []
        for i in dict.fromkeys(i for key in keys for i in planner.index.groups[key]):
            product = prepared.universe.products[i]
            fact = planner.source_facts(product)
            from app.services.official_product_facts import project_usable_quantity
            projected = project_usable_quantity(product, fact, allow_estimates=True, required_unit=ingredient.unit)
            evidence = planner.nutrition_evidence(product, name, ingredient.unit, {'kcal', 'protein_g', 'fat_g', 'carbs_g'}, recipe)
            rows.append({'name': product.name, 'brand': product.brand, 'gtin': product.gtin,
                'product_id': product.product_id, 'store_id': product.store_id,
                'price': product.price, 'semantic_confidence': str(product.semantic_confidence),
                'source_unit': product.usable_unit, 'projected_unit': projected.usable_unit,
                'source_quantity': product.usable_quantity, 'projected_quantity': projected.usable_quantity,
                'form_pass': product_form_compatible(recipe, name, projected, fact),
                'resolved': i in resolved_ids, 'nutrition_pass': bool(evidence),
                'facts': None if fact is None else {'ingredients': fact.ingredients, 'complete': fact.ingredients_complete,
                    'nutrition': fact.nutrition, 'nutrition_unit': fact.nutrition_unit,
                    'nutrition_preparation': fact.nutrition_preparation, 'quantity_sources': fact.field_sources.get('usable_quantity'),
                    'conflicts': fact.conflicts, 'source': fact.source}})
        report[name] = {'ingredient': ingredient.model_dump(mode='json'), 'error': error, 'products': rows}
        print(json.dumps({'ingredient': name, 'error': error, 'total': len(rows),
                          'forms': sum(r['form_pass'] for r in rows), 'resolved': len(resolved_ids),
                          'nutrition': sum(r['resolved'] and r['nutrition_pass'] for r in rows)}, ensure_ascii=False), flush=True)
    target = Path('/results') / args.report
    target.mkdir(exist_ok=True)
    (target / 'inspection.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
