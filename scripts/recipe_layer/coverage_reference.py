"""Frozen coverage reference shared by resumable input and basket checks."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.services.meal_library_content import identity
from app.services.meal_prepared_artifacts import method_signature
from app.services.official_product_facts import shell_egg_quantity_proofs
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import current_recipes

MINT_REVIEW = Path('docs/reviews/recipe-four-staples-20261027/recipe-review.json')


def reviewed_recipe_transition(scope, compared_scope, variants):
    """Allow only the recorded manifest transition and complete successor set.

    This changes comparison identities, never old checkout receipts or outcomes.
    Unknown recipe/manifest drift still fails closed.
    """
    review = json.loads(MINT_REVIEW.read_bytes())
    if (scope['manifest_sha256'] != review['before_manifest_file_sha256']
            or compared_scope['manifest_sha256'] != review['after_manifest_file_sha256']):
        raise ValueError('Changed coverage comparison scope: unreviewed manifest transition')
    before = [r['current_id'] for r in variants]
    replacements = {r['previous_id']: r['runtime_id'] for r in review['corrected']}
    after = [replacements.get(r, r) for r in before]
    if (digest(before) != scope['recipe_ids_sha256']
            or digest(after) != compared_scope['recipe_ids_sha256']
            or not set(replacements) <= set(before)
            or len(set(after)) != len(after)):
        raise ValueError('Changed coverage comparison scope: unreviewed recipe transition')
    return after


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def prior_input_report(report, *, compared_scope=None):
    """Read either the original input inventory or a complete coverage report.

    Facts/method may deliberately change between phases. The original IDs,
    price universe, clock, stores, portions and purchase scope must not drift.
    Issued recipe corrections require the explicit manifest/successor proof.
    """
    if report.get('schema') == 'smako-recipe-coverage-v1':
        scope, variants = report['scope'], report['variants']
        recipe_ids = [r['current_id'] for r in variants]
        if compared_scope is not None:
            for key in ('universe_sha256', 'clock', 'store_ids', 'max_stores',
                        'servings', 'pantry', 'imported_reference_ids_sha256',
                        'conditions'):
                if scope[key] != compared_scope[key]:
                    raise ValueError('Changed coverage comparison scope: '+key)
            if any(scope[key] != compared_scope[key] for key in ('recipe_ids_sha256', 'manifest_sha256')):
                recipe_ids = reviewed_recipe_transition(scope, compared_scope, variants)
        report = {'imported_reference_ids': [r['original_id'] for r in variants],
                  'recipe_ids': recipe_ids,
                  'universe_sha256': scope['universe_sha256'],
                  'facts_sha256': scope['facts_sha256'], 'clock': scope['clock'],
                  'modes': {mode: {'resolved_indices': [i for i, row in enumerate(variants)
                               if row['modes'][mode]['inputs'] == 'resolved']}
                            for mode in ('exact', 'estimated')}}
    if (compared_scope is not None
            and (report['universe_sha256'] != compared_scope['universe_sha256']
                 or report['clock'] != compared_scope['clock'])):
        raise ValueError('Changed original price universe or clock')
    return report


def imported_recipes():
    source = json.loads(Path('docs/reviews/recipe-integration-all-20261026/all-recipes.json').read_bytes())
    replacements = {}
    for file, key in [('recipe-quality-and-planning-20261026/recipe-review.json', 'recipes'),
                      ('week-search-and-cache-20261026/recipe-review.json', 'corrected'),
                      ('recipe-four-staples-20261027/recipe-review.json', 'corrected')]:
        for row in json.loads((Path('docs/reviews') / file).read_bytes())[key]:
            replacements[row['previous_id']] = row['runtime_id']
    active = {identity(r): r for r in current_recipes()}
    references, recipes = [], []
    for row in source['recipes']:
        key = row['runtime_id']
        references.append(key)
        seen = set()
        while key in replacements:
            if key in seen:
                raise ValueError('Cyclic recipe replacement')
            seen.add(key)
            key = replacements[key]
        recipes.append(active[key])
    assert len(recipes) == len(set(references)) == len({identity(r) for r in recipes}) == 2200
    return references, recipes


def request_for(mode, store_ids):
    return PlanRequest.model_validate({'recipes': 1, 'max_stores': 2,
        'allowed_store_ids': sorted(store_ids), 'purchase_planning_mode': mode,
        'recipe_preferences': {'mode': 'complete'}, 'personal': {
            'allow_nutrition_estimates': True, 'use_pantry': False,
            'meals': [{'meal_type': m, 'count': 1, 'servings': 4 if m == 'dinner' else 1,
                       'recipe_choices': {'min_ingredients': 1, 'max_ingredients': 40}, 'limits': {}}
                      for m in ['dinner', 'breakfast', 'snack']]}})


def load_reference(args):
    prepared = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    raw = json.loads(args.facts.read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw['facts']})
    facts.version = raw['facts_version']
    del raw
    shell_egg_quantity_proofs(prepared.universe.products, facts)
    references, recipes = imported_recipes()
    stores = sorted({p.store_id for p in prepared.universe.products})
    scope = {'name': 'Malmö retained combined-prices 2026-10-23 / imported-2200-v1',
             'universe_sha256': file_sha(args.universe), 'facts_sha256': file_sha(args.facts),
             'facts_version': facts.version, 'clock': args.clock, 'store_ids': stores,
             'method_signature': method_signature(), 'max_stores': 2,
             'servings': {'dinner': 4, 'breakfast': 1, 'snack': 1}, 'pantry': False,
             'imported_reference_ids_sha256': digest(references),
             'recipe_ids_sha256': digest([identity(r) for r in recipes]),
             'manifest_sha256': file_sha('backend/app/data/recipes/library-manifest.json'),
             'conditions': {m: request_for(m, stores).model_dump(mode='json') for m in ['exact', 'estimated']}}
    return prepared, facts, references, recipes, scope


def planner_for(mode, prepared, facts, scope):
    return PersonalPlanner(PlanRequest.model_validate(scope['conditions'][mode]),
        Settings(price_provider='mock', complete_recipes_enabled=True), prepared,
        {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts,
        now=datetime.fromisoformat(scope['clock']))
