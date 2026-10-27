"""Current 2,200-variant input coverage through the existing inventory resolver.

Run only through budgeted_check. Individual ingredient resolution is not a
shared basket, nutrition/allergen/organic approval, or a saved personal plan.
"""
import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.services.ingredient_normalizer import _search_text
from app.services.meal_library_content import encoded, identity
from app.services.meal_prepared_artifacts import method_signature
from app.services.official_product_facts import shell_egg_quantity_proofs
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import current_recipes
from coverage_reference import imported_recipes


def main(args):
    started = time.perf_counter()
    prepared = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    raw = json.loads(args.facts.read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw['facts']})
    facts.version = raw['facts_version']
    del raw
    shell_egg_quantity_proofs(prepared.universe.products, facts)
    active = {identity(r): r for r in current_recipes()}
    references, recipes = imported_recipes()
    assert len(recipes) == len({identity(r) for r in recipes}) == 2200
    report = {'scope': 'Same individual-input definition as preceding quality inventory; current 2200 imported variants, not joint basket/nutrition approval',
        'universe_sha256': hashlib.sha256(args.universe.read_bytes()).hexdigest(),
        'facts_sha256': hashlib.sha256(args.facts.read_bytes()).hexdigest(), 'clock': args.clock,
        'facts_version': facts.version, 'method_signature': method_signature(),
        'manifest_sha256': hashlib.sha256(Path('backend/app/data/recipes/library-manifest.json').read_bytes()).hexdigest(),
        'source_loading_seconds': time.perf_counter()-started,
        'current_variants': len(active), 'imported_variants': 2200, 'other_original_variants_not_inventoried': len(active)-2200,
        'imported_reference_ids': references, 'recipe_ids': [identity(r) for r in recipes], 'modes': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.research:
        groups = {'limejuice': ['limejuice', 'lime juice', 'pressad lime'], 'ingefära': ['ingefära'],
                  'salladslök': ['salladslök'], 'mynta': ['mynta'], 'purjolök': ['purjolök'], 'kokosflingor': ['kokos riven', 'riven kokos', 'kokosflingor']}
        research = {name: [] for name in groups}
        for p in prepared.universe.products:
            label = _search_text(p.name)
            for group, terms in groups.items():
                if not any(_search_text(t) in label for t in terms):
                    continue
                f = facts.get((p.store_id, p.product_id))
                valid = bool(f and f.source and p.source_provenance and f.source_product_id == p.product_id
                    and f.source_snapshot_id == p.source_provenance.source_snapshot_id)
                research[group].append({'product': p.model_dump(mode='json'),
                    'facts': f.__dict__ if valid and hasattr(f, '__dict__') else None,
                    'exact_facts': valid})
        # ProductFacts is a dataclass, including slots on supported runtimes.
        from dataclasses import asdict
        for rows in research.values():
            for row in rows:
                p = row['product'];f = facts.get((p['store_id'], p['product_id']))
                row['facts'] = asdict(f) if row['exact_facts'] else None
        args.research.write_bytes(encoded({'universe_sha256': report['universe_sha256'], 'facts_sha256': report['facts_sha256'], 'groups': research}))
    print({'source_loading_seconds': report['source_loading_seconds']}, flush=True)
    for mode in ['exact', 'estimated']:
        request = PlanRequest.model_validate({'recipes': 1, 'max_stores': 2, 'purchase_planning_mode': mode,
            'recipe_preferences': {'mode': 'complete'}, 'personal': {'allow_nutrition_estimates': True,
            'use_pantry': False, 'meals': [{'meal_type': m, 'count': 1, 'servings': 4 if m == 'dinner' else 1,
                'recipe_choices': {'min_ingredients': 1, 'max_ingredients': 40}, 'limits': {}}
                for m in ['dinner', 'breakfast', 'snack']]}})
        planner = PersonalPlanner(request, Settings(price_provider='mock', complete_recipes_enabled=True), prepared,
            {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts, now=datetime.fromisoformat(args.clock))
        shared = {};resolved = [];blocked = Counter()
        for index, recipe in enumerate(recipes):
            keys = []
            for ingredient in recipe.ingredients:
                key = (ingredient.canonical_name, ingredient.form, ingredient.unit, ingredient.quantity, tuple(ingredient.product_requirements or ()))
                keys.append(key)
                if key not in shared:
                    row = {'identity': key[0]+'|'+key[1], 'unit': key[2], 'quantity': key[3], 'requirements': list(key[4]), 'recipe_indices': []}
                    try:
                        candidates = planner.resolve(ingredient.canonical_name, ingredient.quantity, ingredient.unit,
                            profile=planner._merged_profile(planner.meals[recipe.design.meal_types[0]]), organic_animals=False, recipe=recipe)
                        row.update(status='resolved', candidate_count=len(candidates), examples=[{
                            'store_id': prepared.universe.products[n].store_id, 'product_id': prepared.universe.products[n].product_id,
                            'name': prepared.universe.products[n].name, 'source_snapshot_id': prepared.universe.products[n].source_provenance.source_snapshot_id,
                            'usable_quantity': c.usable_quantity, 'unit': c.usable_unit} for n,c in candidates[:3]])
                    except ValueError as error:
                        row.update(status='blocked', reason=str(error), code=getattr(error, 'code', None))
                    shared[key] = row
                shared[key]['recipe_indices'].append(index)
            if all(shared[key]['status']=='resolved' for key in keys):
                resolved.append(index)
            else:
                blocked.update({shared[key]['identity'] for key in keys if shared[key]['status']=='blocked'})
        report['modes'][mode] = {'conditions': request.model_dump(mode='json'), 'resolved_indices': resolved,
            'resolved': len(resolved), 'shared_inputs': list(shared.values()), 'blocked_variants_by_identity': dict(blocked)}
        args.output.write_bytes(encoded(report))
        print({'mode': mode, 'resolved': len(resolved), 'elapsed_seconds': time.perf_counter()-started}, flush=True)
    report['wall_seconds'] = time.perf_counter()-started
    assert report['method_signature'] == method_signature()
    args.output.write_bytes(encoded(report))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    p.add_argument('--research', type=Path)
    main(p.parse_args())
