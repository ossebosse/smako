"""Explain retained candidates at each real food/form/unit/source gate."""
import dataclasses
import json
import sys
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import TasteProfile
from app.models.recipe_preferences import RecipePreferences
from app.services.complete_recipes import product_form_compatible
from app.services.official_product_facts import project_usable_quantity
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_search import ProductSearchRequest
from app.services.product_semantics import evaluate_product_semantics
from app.services.recipe_library import candidates
from replay import install_clock

clock = install_clock()
prepared = PreparedPriceUniverseArtifact.model_validate_json(Path('/inputs/universe.json').read_bytes()).restore()
request = PlanRequest(recipes=1, max_stores=2, purchase_planning_mode='estimated',
                      allow_nutrition_estimates=True, recipe_preferences={'mode': 'complete'})
planner = PersonalPlanner(request, Settings(price_provider='own', complete_recipes_enabled=True), prepared,
    {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, now=clock)
library = candidates(RecipePreferences(mode='complete'), servings=2)
report = {}
for name in sys.argv[1:] or ['bönor', 'kidneybönor', 'tortillas', 'salt', 'gurka', 'citronjuice', 'linser']:
    recipe = next(r for r in library if any(i.name == name for i in r.ingredients))
    ingredient = next(i for i in recipe.ingredients if i.name == name)
    keys, _, _ = planner.index.retrieve(ProductSearchRequest(query=name))
    rows = []
    for i in dict.fromkeys(i for key in keys for i in planner.index.groups[key]):
        p = prepared.universe.products[i]
        fact = planner.source_facts(p)
        projected = project_usable_quantity(p, fact, allow_estimates=True, required_unit=ingredient.unit)
        form_ok = product_form_compatible(recipe, name, projected, fact)
        semantic = evaluate_product_semantics(name, projected)
        nutrition = planner.nutrition_evidence(projected, name, ingredient.unit,
                    {'kcal', 'protein_g', 'carbs_g', 'fat_g'}, recipe) if form_ok and semantic.compatible else None
        rows.append({'product': p.model_dump(mode='json'), 'projected_quantity': projected.usable_quantity,
            'projected_unit': projected.usable_unit, 'facts': dataclasses.asdict(fact) if fact else None,
            'form_ok': form_ok, 'semantic': dataclasses.asdict(semantic),
            'nutrition': dataclasses.asdict(nutrition) if nutrition else None})
    try:
        resolved = planner.resolve(name, ingredient.quantity, ingredient.unit, profile=TasteProfile(), recipe=recipe)
        resolution = [c.product_name for _, c in resolved]
    except ValueError as exc:
        resolution = str(exc)
    report[name] = {'recipe': recipe.name, 'requirement': ingredient.model_dump(mode='json'),
                    'resolution': resolution, 'candidates': rows}
    print(json.dumps({'name': name, 'resolution': resolution, 'count': len(rows),
                      'form_pass': sum(r['form_ok'] for r in rows), 'nutrition_pass': sum(bool(r['nutrition']) for r in rows)}, ensure_ascii=False), flush=True)
Path('/results/form-diagnostics.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str))
