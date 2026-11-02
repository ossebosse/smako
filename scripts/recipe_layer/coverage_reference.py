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
EGG_REVIEW = Path('docs/reviews/egg-preparation-20261028/recipe-review.json')
MINT_LEAF_REVIEW = Path('docs/reviews/mint-leaf-preparation-20261028/recipe-review.json')
CORN_REVIEW = Path('docs/reviews/whole-corn-20261028/recipe-review.json')
TOP_FIVE_REVIEW = Path('docs/reviews/top-five-ingredients-20261028/recipe-review.json')
EXPANSION_REVIEW = Path('docs/reviews/recipe-unblock-20261101/library-transition.json')
ROUND2_REVIEW = Path('docs/reviews/recipe-unblock-round2-20261101/library-transition.json')


def checked_additive_transition(review):
    """Append disjoint recipes; reviewed successors may retire only new versions."""
    from app.services.meal_library_content import (
        ROOT,
        encoded,
        identity,
        load_entries,
        validate_pack_bytes,
    )

    before, after = review['before_manifest'], review['after_manifest']
    expected = {**before, 'current': before['current'] + review['added_entries']}
    revoked = review.get('new_revocations', {})
    corrections = review.get('superseded_new_versions', [])
    rejected = review.get('rejected_new_versions', [])
    if revoked:
        expected['revocations'] = {**before.get('revocations', {}), **revoked}
    if (after != expected or review['corrected']
            or hashlib.sha256(encoded(before)).hexdigest() != review['before_manifest_file_sha256']
            or hashlib.sha256(encoded(after)).hexdigest() != review['after_manifest_file_sha256']):
        raise ValueError('Changed coverage comparison scope: unreviewed additive manifest')
    old = {identity(r) for r in load_entries(before['current'] + before['history'])}
    added = {identity(r): r.design.content_sha256 for r in load_entries(review['added_entries'])}
    declared = {r['runtime_id']: r['content_sha256'] for r in review['added']}
    if not added or old.intersection(added) or added != declared or len(declared) != len(review['added']):
        raise ValueError('Changed coverage comparison scope: unreviewed additive recipes')
    correction_ids = [r['previous_id'] for r in corrections]
    successors = [r['runtime_id'] for r in corrections]
    rejected_ids = [r['runtime_id'] for r in rejected]
    if (set(revoked) != set(correction_ids) | set(rejected_ids)
            or len(set(rejected_ids)) != len(rejected_ids)
            or set(rejected_ids).intersection(correction_ids + successors)
            or len(set(correction_ids)) != len(correction_ids)
            or len(set(successors)) != len(successors) or set(revoked).intersection(old)):
        raise ValueError('Changed coverage comparison scope: unreviewed new-version revocations')
    for row in rejected:
        key = row['runtime_id']
        if (key not in added or added[key] != row['content_sha256']
                or not row.get('reason') or revoked.get(key) != row['reason']):
            raise ValueError('Changed coverage comparison scope: unreviewed rejected new version')
        proof_path = Path(row['qualification_path'])
        if proof_path.parent != ROUND2_REVIEW.parent:
            raise ValueError('Changed coverage comparison scope: unreviewed rejection proof path')
        proof_raw = proof_path.read_bytes()
        proof = json.loads(proof_raw)
        pack_path = Path(row['standardized_pack_path'])
        if pack_path.is_absolute() or pack_path.parent.resolve() != ROOT / 'reviewed-expansion-round2-20261101':
            raise ValueError('Changed coverage comparison scope: unreviewed rejected pack path')
        pack_raw = pack_path.read_bytes()
        checked = validate_pack_bytes(pack_raw)
        candidates = [r for r in checked['recipes'] if identity(r) == key]
        rows = [r for r in proof['modes']['estimated']['recipes'] if r['id'] == key]
        if (hashlib.sha256(proof_raw).hexdigest() != row['qualification_sha256']
                or proof['input_only'] or checked['rejections'] or len(candidates) != 1
                or candidates[0].design.content_sha256 != added[key]
                or proof['pack_sha256'] != hashlib.sha256(pack_raw).hexdigest()
                or proof['pack_sha256'] != row['pack_sha256']
                or len(rows) != 1 or rows[0]['status'] != 'data_blocked'
                or not rows[0].get('input_blocks')
                or any(b['code'] != 'DATA_BLOCKED' for b in rows[0]['input_blocks'])):
            raise ValueError('Changed coverage comparison scope: unreviewed rejection proof')
    for row in corrections:
        previous_id, successor_id = row['previous_id'], row['runtime_id']
        previous_parts, successor_parts = previous_id.split(':'), successor_id.split(':')
        if (not revoked[previous_id] or previous_id not in added or successor_id not in added
                or added[previous_id] != row['previous_content_sha256']
                or added[successor_id] != row['content_sha256']
                or len(previous_parts) != 3 or len(successor_parts) != 3
                or previous_parts[::2] != successor_parts[::2]
                or tuple(map(int, successor_parts[1].split('.'))) <= tuple(map(int, previous_parts[1].split('.')))):
            raise ValueError('Changed coverage comparison scope: unreviewed new-version revocations')
    # Successive corrections may retire an intermediate newly issued version.
    # Same-base/variant, strictly increasing versions above preclude cycles;
    # every retired node must have exactly one hash-bound reviewed successor.
    edges = {r['previous_id']: r['runtime_id'] for r in corrections}
    for origin in edges:
        latest = origin
        visited = set()
        while latest in edges:
            if latest in visited:
                raise ValueError('Changed coverage comparison scope: unreviewed new-version revocations')
            visited.add(latest)
            latest = edges[latest]
        if latest in revoked or latest not in added:
            raise ValueError('Changed coverage comparison scope: unreviewed new-version revocations')
    return review


def reviewed_recipe_transition(scope, compared_scope, variants):
    """Follow only recorded manifest edges and complete successor sets.

    This changes comparison identities, never old checkout receipts or outcomes.
    Unknown recipe/manifest drift still fails closed.
    """
    before = [r['current_id'] for r in variants]
    if digest(before) != scope['recipe_ids_sha256'] or len(set(before)) != len(before):
        raise ValueError('Changed coverage comparison scope: unreviewed recipe transition')
    paths = (MINT_REVIEW, EGG_REVIEW, MINT_LEAF_REVIEW, CORN_REVIEW, TOP_FIVE_REVIEW, EXPANSION_REVIEW, ROUND2_REVIEW)
    reviews = [(path, json.loads(path.read_bytes())) for path in paths if path.exists()]
    pending = [(scope['manifest_sha256'], before)]
    visited = set()
    while pending:
        manifest, ids = pending.pop(0)
        if (manifest, tuple(ids)) in visited:
            continue
        visited.add((manifest, tuple(ids)))
        if manifest == compared_scope['manifest_sha256']:
            if digest(ids) != compared_scope['recipe_ids_sha256']:
                raise ValueError('Changed coverage comparison scope: unreviewed recipe transition')
            return ids
        for path, review in reviews:
            if manifest != review['before_manifest_file_sha256']:
                continue
            if path in {EXPANSION_REVIEW, ROUND2_REVIEW}:
                checked_additive_transition(review)
            replacements = {r['previous_id']: r['runtime_id'] for r in review['corrected']}
            after = [replacements.get(r, r) for r in ids]
            if not set(replacements) <= set(ids) or len(set(after)) != len(after):
                raise ValueError('Changed coverage comparison scope: unreviewed recipe transition')
            pending.append((review['after_manifest_file_sha256'], after))
    raise ValueError('Changed coverage comparison scope: unreviewed manifest transition')


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
                      ('recipe-four-staples-20261027/recipe-review.json', 'corrected'),
                      ('egg-preparation-20261028/recipe-review.json', 'corrected'),
                      ('mint-leaf-preparation-20261028/recipe-review.json', 'corrected'),
                      ('whole-corn-20261028/recipe-review.json', 'corrected'),
                      ('top-five-ingredients-20261028/recipe-review.json', 'corrected')]:
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
