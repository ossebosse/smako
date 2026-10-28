"""Issue explicit frozen whole-cob recipes with count, never average cob mass."""
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

REPORT = ROOT.parents[3] / 'docs/reviews/whole-corn-20261028'
OUTPUT = ROOT / 'reviewed-whole-corn-20261028'
BASE = 'smako-mexican-snack-whole-charred-corn'
REQUIREMENT = 'pack:intake_all_shape_frozen_whole_corn_count'


def main(do_import=False):
    REPORT.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    report_path = REPORT / 'recipe-review.json'
    if report_path.exists():
        manifest = manifest_entries()
        issued = {identity(r): r for r in load_entries([*manifest['current'], *manifest['history']], ROOT)}
        prior = read_json(report_path)
        assert all(issued[r['runtime_id']].design.content_sha256 == r['content_sha256'] for r in prior['corrected'])
        print({'already_issued': len(prior['corrected']), 'no_bytes_rewritten': True})
        return
    active = {identity(r): r for r in current_recipes() if r.design.base_id == BASE}
    assert len(active) == 2
    originals = {}
    for relative in ('reviewed-all-20261026/batch-05/authoring.json',
                     'reviewed-frozen-20261026/batch-01/authoring.json'):
        for row in read_json(ROOT / relative)['recipes']:
            rid = ':'.join(row[k] for k in ('base_id', 'version', 'variant_id'))
            if rid in active:
                originals[rid] = row
    assert originals.keys() == active.keys()
    authors, rows, corrected = [], [], []
    reason = ('Explicit frozen whole-cob adaptation: one whole blanched frozen cob per serving '
              'replaces the previous 180-g raw whole-cob specification. Exact manufacturer pack count '
              'does not establish individual or edible mass. Original recipe bytes remain in history. '
              'Heating time is an author estimate with a doneness check; not cooking-tested.')
    for rid, original in sorted(originals.items()):
        row = copy.deepcopy(original)
        runtime = active[rid]
        for component in row['components']:
            for ingredient in component['ingredients']:
                if ingredient['name'] == 'majskolv':
                    assert ingredient['quantity'] == 180 and ingredient['unit'] == 'g'
                    ingredient.update(quantity=1, unit='st',
                        label='Hel fryst förvälld majskolv, antal inklusive oätlig mittkolv',
                        requirements=[REQUIREMENT])
        first = next(s for s in row['steps'] if s['text'].startswith('Använd en skalad hel rå majskolv;'))
        first['text'] = ('Ta fram angivet antal hela frysta förvällda majskolvar. Antalet avser hela kolvar '
                         'inklusive oätlig mittkolv; ingen gramvikt per kolv antas. '
                         'Koka upp 1000 ml vatten och lägg i kolvarna direkt från frysen.')
        heat = next(s for s in row['steps'] if s['text'].startswith('Sjud cirka tio minuter'))
        heat['text'] = ('Sjud cirka tio minuter tills kolvarna är genomvarma och kornen mjuka; '
                        'kontrollera att ingen fryst kärna finns kvar och fortsätt vid behov enligt förpackningen. '
                        'Lyft upp och torka ytan med rent kökspapper. Tiden är en författaruppskattning.')
        for step in row['steps']:
            step['text'] = step['text'].replace('Majskärnan äts inte.', 'Den hårda mittkolven äts inte.')
        parts = row['version'].split('.')
        row['version'] = '.'.join([*parts[:-1], str(int(parts[-1]) + 1)])
        row['notes'] += ' Granskad fryst kolvberedning 2026-10-28: ' + reason
        vocabulary = library_vocabulary([runtime])
        vocabulary['majskolv|as_sold'] = ('st', [REQUIREMENT])
        authors.append(copy.deepcopy(row))
        pack, _ = standardize({'schema_version':'smako-recipe-authoring-v1',
            'pack_id':'whole-corn-review-20261028','recipes':[row]}, vocabulary, reviewed_at='2026-10-28')
        rows.extend(pack['recipes'])
        corrected.append({'previous_id':rid,'runtime_id':':'.join(row[k] for k in ('base_id','version','variant_id')),
            'before_content_sha256':runtime.design.content_sha256,'reason':reason})
    (OUTPUT/'authoring.json').write_bytes(encoded({'schema_version':'smako-recipe-authoring-v1',
        'pack_id':'whole-corn-review-20261028','recipes':authors}))
    path = OUTPUT/'standardized.json'
    path.write_bytes(encoded({'schema_version':'smako-meal-pack-v1','pack_id':'whole-corn-review-20261028','recipes':rows}))
    checked = validate_pack_bytes(path.read_bytes())
    assert not checked['rejections'], checked['rejections']
    (REPORT/'validate.json').write_bytes(encoded({k:v for k,v in checked.items() if k != 'recipes'}))
    (REPORT/'diff.json').write_bytes(encoded(pack_diff(checked)))
    for record, recipe in zip(corrected, checked['recipes'], strict=True):
        record['content_sha256'] = recipe.design.content_sha256
        old = active[record['previous_id']]
        assert len(old.ingredients) == len(recipe.ingredients)
        for before, after in zip(old.ingredients, recipe.ingredients, strict=True):
            if before.canonical_name == 'majskolv':
                assert (after.quantity, after.unit, after.form) == (1, 'st', 'as_sold')
            else:
                assert before == after
    if not do_import:
        print({'validated_corrections':len(corrected)})
        return
    manifest_path = ROOT/'library-manifest.json'
    before_manifest = file_sha(manifest_path)
    (REPORT/'import.json').write_bytes(encoded(import_pack(path)))
    (REPORT/'revocations.json').write_bytes(encoded([revoke_recipe(r['previous_id'], r['reason']) for r in corrected]))
    report_path.write_bytes(encoded({'schema':'smako-whole-corn-recipe-review-v1','corrected':corrected,
        'before_manifest_file_sha256':before_manifest,'after_manifest_file_sha256':file_sha(manifest_path)}))
    print({'issued':len(corrected),'original_bytes_preserved':True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import', dest='do_import', action='store_true')
    main(parser.parse_args().do_import)
