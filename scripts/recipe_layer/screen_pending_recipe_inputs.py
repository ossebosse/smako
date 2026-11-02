"""Find hidden product blockers in known inputs of still-unapproved drafts.

Unknown vocabulary entries remain blocked. A diagnostic subset is never a
recipe approval, import pack or complete shopping-basket qualification.
"""
import argparse
import copy
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.meal_library_content import encoded, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes
from coverage_reference import file_sha, load_reference, planner_for


def pending_entries(queue):
    pending = []
    allowed = {'pending_qualified_input', 'pending_register_or_authoring',
               'blocked', 'native_compatible_not_approved'}
    for row in queue['variants']:
        if row['status'] == 'imported_reviewed_version':
            continue
        if row['status'] not in allowed:
            raise ValueError('Unknown queue decision: ' + row['status'])
        pending.append(row)
    return pending


def known_input_probe(original, vocabulary):
    """Preserve exact amounts/units/requirements; explicitly list omitted inputs."""
    row = copy.deepcopy(original)
    unknown, components, uses = set(), [], []
    for component in row['components']:
        kept = []
        for item in component['ingredients']:
            key = canonicalize_ingredient_name(item['name']) + '|' + item['form']
            if key not in vocabulary:
                unknown.add(key)
            else:
                kept.append(item)
                uses.append(key)
        if kept:
            components.append({**component, 'ingredients': kept})
    if not components:
        return None, sorted(unknown)
    row.update(base_id='smako-diagnostic-' + row['base_id'], components=components,
               name='DIAGNOSTIK – EJ RECEPT: ' + row['name'],
               steps=[{'text': 'Endast inköpsdiagnostik av kända ingrediensrader. Inte ett recept eller en tillagningsinstruktion.',
                       'uses': sorted(set(uses)), 'minutes': 1}],
               notes='Synthetic known-input subset; never approve, serve or import this diagnostic object.')
    row.pop('unmeasured_processes', None)
    document = {'schema_version': 'smako-recipe-authoring-v1',
                'pack_id': 'diagnostic-only-not-for-import', 'recipes': [row]}
    pack, _ = standardize(document, vocabulary, reviewed_at='2026-11-02')
    checked = validate_pack_bytes(encoded(pack))
    if checked['rejections']:
        raise ValueError(str(checked['rejections']))
    return checked['recipes'][0], sorted(unknown)


def screen(original, vocabulary, planner):
    recipe, unknown = known_input_probe(original, vocabulary)
    result = {'unknown_identities': unknown, 'recipe_approved': False,
              'basket_checked': False, 'input_blocks': [], 'known_input_count': 0}
    if recipe is None:
        return {**result, 'status': 'no_known_inputs'}
    result['known_input_count'] = len(recipe.ingredients)
    meal = planner.meals[recipe.design.meal_types[0]]
    for item in recipe.ingredients:
        try:
            planner.resolve(item.canonical_name, item.quantity, item.unit,
                            profile=planner._merged_profile(meal), organic_animals=False, recipe=recipe)
        except ValueError as exc:
            result['input_blocks'].append({'identity': item.canonical_name + '|' + item.form,
                                           'unit': item.unit, 'quantity': item.quantity,
                                           'code': getattr(exc, 'code', None), 'reason': str(exc)})
    result['status'] = 'known_inputs_blocked' if result['input_blocks'] else 'known_inputs_resolved_only'
    return result


def summarize(report):
    known, combined = defaultdict(set), defaultdict(set)
    for row in report['variants']:
        for key in row.get('unknown_identities', []):
            combined[key].add(row['source_id'])
        for block in row['input_blocks']:
            known[block['identity']].add(row['source_id'])
            combined[block['identity']].add(row['source_id'])
    for key, groups in [('ranked_known_input_blocks', known), ('ranked_combined_blocks', combined)]:
        report[key] = sorted(
            [{'identity': identity, 'variants': len(ids), 'source_ids': sorted(ids)} for identity, ids in groups.items()],
            key=lambda row: (-row['variants'], row['identity']))
    report['status'] = dict(Counter(r['status'] for r in report['variants']))
    return report


def main(args):
    queue = json.loads(args.queue.read_bytes())
    source = args.source.resolve()
    originals = {}
    for entry in queue['source_files']:
        path = (source / entry['path']).resolve()
        if not path.is_relative_to(source) or file_sha(path) != entry['sha256']:
            raise ValueError('Changed source file: ' + entry['path'])
        for row in json.loads(path.read_bytes())['recipes']:
            key = ':'.join(row.get(k, default) for k, default in
                           [('base_id', ''), ('version', '1.0.0'), ('variant_id', 'base')])
            if key in originals:
                raise ValueError('Duplicate source identity: ' + key)
            originals[key] = row
    pending = pending_entries(queue)
    os.environ['RECIPE_PREPARATION_CACHE_ROOT'] = str(args.output.parent / 'preparation')
    prepared, facts, _refs, _issued, scope = load_reference(args)
    vocabulary = library_vocabulary(current_recipes())
    report = {'schema_version': 'smako-pending-known-input-screen-v1', 'scope': scope,
              'queue_sha256': file_sha(args.queue), 'mode': 'estimated',
              'recipe_approved': False, 'basket_checked': False,
              'note': 'Only known input rows were checked. Unknown identities and authoring defects remain. No import or complete-basket claim.',
              'variants': []}
    planner = planner_for('estimated', prepared, facts, scope)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for index, entry in enumerate(pending, 1):
        row = originals[entry['source_id']]
        try:
            result = screen(row, vocabulary, planner)
        except ValueError as exc:
            result = {'status': 'screen_error', 'reason': str(exc), 'recipe_approved': False,
                      'basket_checked': False, 'input_blocks': []}
        report['variants'].append({'source_id': entry['source_id'], 'source_file': entry['source_file'],
                                   'source_recipe_sha256': hashlib.sha256(encoded(row)).hexdigest(), **result})
        args.output.write_bytes(encoded(report))
        if index % 20 == 0:
            print(index, dict(Counter(r['status'] for r in report['variants'])), flush=True)
    summarize(report)
    args.output.write_bytes(encoded(report))
    print(report['status'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--queue', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('backend/app/data/recipes/incoming/authoring-1000-20261101'))
    parser.add_argument('--universe', type=Path, required=True)
    parser.add_argument('--facts', type=Path, required=True)
    parser.add_argument('--clock', required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
