"""Separate general trimmed mint from explicitly leaf-only authored recipes.

Preserve issued bytes and quantities. Only the reviewed 91 generic raw-edible
definitions receive a new version; leaf-only recipes keep their original gate.
"""
import argparse
import copy

from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    load_entries,
    manifest_entries,
    pack_diff,
    read_json,
    revoke_recipe,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes
from coverage_reference import file_sha

REPORT = ROOT.parents[3] / 'docs/reviews/recipe-four-staples-20261027'
OUTPUT = ROOT / 'reviewed-mint-20261027'
REQUIREMENT = 'pack:intake_all_shape_trimmed_mint'
PREPARATION = ('Skölj myntan och ta bort skadade delar och grova stjälkar. '
               'Väg blad och mjuka stjälkar efter ansning till receptets angivna myntavikt. ')


def main(do_import=False):
    REPORT.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report_path = REPORT / 'recipe-review.json'
    if report_path.exists():
        prior = read_json(report_path)
        manifest = manifest_entries()
        issued = {identity(r): r for r in load_entries([*manifest['current'], *manifest['history']], ROOT)}
        assert all(issued[r['runtime_id']].design.content_sha256 == r['content_sha256'] for r in prior['corrected'])
        print({'already_issued': len(prior['corrected']), 'no_bytes_rewritten': True})
        return
    active = {identity(r): r for r in current_recipes()}
    authoring = {}
    for directory in ('reviewed-all-20261026', 'reviewed-frozen-20261026', 'reviewed-week-20261026'):
        for path in sorted((ROOT / directory).rglob('authoring.json')):
            for row in read_json(path)['recipes']:
                rid = row['base_id'] + ':' + row['version'] + ':' + row['variant_id']
                if rid in active:
                    authoring[rid] = row
    rows, corrected, untouched, authors = [], [], [], []
    for rid, original in sorted(authoring.items()):
        mint = [i for c in original['components'] for i in c['ingredients'] if i['name'] == 'mynta']
        if not mint:
            continue
        runtime = active[rid]
        if any(i['label'] != 'Mynta, rå ätlig vikt' for i in mint):
            untouched.append({'runtime_id': rid, 'content_sha256': runtime.design.content_sha256,
                              'reason': 'Explicit leaf-only definition retains its stricter quantity gate.'})
            continue
        assert not any('plocka' in s['text'].lower() or 'myntablad' in s['text'].lower()
                       for s in original['steps'] if 'mynta' in s['uses'])
        row = copy.deepcopy(original)
        for component in row['components']:
            for ingredient in component['ingredients']:
                if ingredient['name'] == 'mynta':
                    assert ingredient['unit'] == 'g' and ingredient['form'] == 'raw_edible'
                    ingredient.update(label='Färsk mynta, blad och mjuka stjälkar, ansad rå ätlig vikt',
                                      requirements=[REQUIREMENT])
        step = next(s for s in row['steps'] if 'mynta' in s['uses'])
        assert not step.get('passive', False)
        step['text'] = PREPARATION + step['text']
        # Give the explicit rinse/trim/weigh instruction its own active minute;
        # do not claim an unchanged time estimate for a newly explicit process.
        step['minutes'] += 1
        parts = row['version'].split('.')
        row['version'] = '.'.join([*parts[:-1], str(int(parts[-1]) + 1)])
        reason = ('Original generic raw-edible mint was collapsed into a leaf-only registry. '
                  'Clarify trimmed leaves and tender stems, preserving edible grams; '
                  'population yield is available only with estimated-quantity consent.')
        row['notes'] += ' Innehållsrättning 2026-10-27: ' + reason
        vocabulary = library_vocabulary([runtime])
        vocabulary['mynta|raw_edible'] = ('g', [REQUIREMENT])
        authors.append(copy.deepcopy(row))
        pack, _ = standardize({'schema_version': 'smako-recipe-authoring-v1',
            'pack_id': 'recipe-mint-review-20261027', 'recipes': [row]}, vocabulary, reviewed_at='2026-10-27')
        rows.extend(pack['recipes'])
        corrected.append({'previous_id': rid, 'before_content_sha256': runtime.design.content_sha256,
            'runtime_id': row['base_id'] + ':' + row['version'] + ':' + row['variant_id'], 'reason': reason,
            'before': {k: getattr(runtime.design, k) for k in ('active_minutes', 'waiting_minutes', 'total_minutes')}})
    assert len(corrected) == 91 and len(untouched) == 40
    (OUTPUT / 'authoring.json').write_bytes(encoded({'schema_version': 'smako-recipe-authoring-v1',
        'pack_id': 'recipe-mint-review-20261027', 'recipes': authors}))
    path = OUTPUT / 'standardized.json'
    path.write_bytes(encoded({'schema_version': 'smako-meal-pack-v1',
        'pack_id': 'recipe-mint-review-20261027', 'recipes': rows}))
    checked = validate_pack_bytes(path.read_bytes())
    assert not checked['rejections'], checked['rejections']
    (REPORT / 'validate.json').write_bytes(encoded({k: v for k, v in checked.items() if k != 'recipes'}))
    (REPORT / 'diff.json').write_bytes(encoded(pack_diff(checked)))
    for record, recipe in zip(corrected, checked['recipes'], strict=True):
        record.update(content_sha256=recipe.design.content_sha256,
                      after={k: getattr(recipe.design, k) for k in record['before']})
        old = active[record['previous_id']]
        assert len(old.ingredients) == len(recipe.ingredients)
        for before, after in zip(old.ingredients, recipe.ingredients, strict=True):
            if before.canonical_name == 'mynta':
                assert (before.quantity, before.unit, before.form) == (after.quantity, after.unit, after.form)
            else:
                assert before == after
        assert record['after']['active_minutes'] == record['before']['active_minutes'] + 1
        assert record['after']['waiting_minutes'] == record['before']['waiting_minutes']
    if not do_import:
        print({'validated_corrections': len(corrected), 'leaf_only_unchanged': len(untouched)})
        return
    manifest_path = ROOT / 'library-manifest.json'
    before_manifest = file_sha(manifest_path)
    (REPORT / 'import.json').write_bytes(encoded(import_pack(path)))
    (REPORT / 'revocations.json').write_bytes(encoded([revoke_recipe(r['previous_id'], r['reason']) for r in corrected]))
    report_path.write_bytes(encoded({'schema': 'smako-mint-recipe-review-v1', 'corrected': corrected,
        'verified_unchanged': untouched, 'before_manifest_file_sha256': before_manifest,
        'after_manifest_file_sha256': file_sha(manifest_path)}))
    print({'issued': len(corrected), 'leaf_only_unchanged': len(untouched)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import', dest='do_import', action='store_true')
    main(parser.parse_args().do_import)
