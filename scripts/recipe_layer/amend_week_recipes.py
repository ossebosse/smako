"""Issue bounded skewer/rye corrections while retaining every published byte."""
import argparse
import copy

from amend_frozen_recipes import fruit_preparation
from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    library_signature,
    load_entries,
    manifest_entries,
    pack_diff,
    read_json,
    revoke_recipe,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

REPORT = ROOT.parents[3] / 'docs/reviews/week-search-and-cache-20261026'
OUTPUT = ROOT / 'reviewed-week-20261026'
SKEWERS = {'smako-thai-chicken-pineapple-skewers': 'ananas', 'smako-thai-paneer-mango-skewers': 'mango'}
RYE = 'smako-swedish-creamed-cabbage-chickpeas'


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
    for directory in ['reviewed-all-20261026', 'reviewed-frozen-20261026']:
        for p in sorted((ROOT / directory).glob('*/authoring.json')):
            for row in read_json(p)['recipes']:
                rid = row['base_id'] + ':' + row['version'] + ':' + row['variant_id']
                if rid in active:
                    authoring[rid] = row
    rows, corrected, unchanged, author_rows = [], [], [], []
    for rid, runtime in active.items():
        if not runtime.design:
            continue
        base = runtime.design.base_id
        replacement = any('frysta skalade' in s.text and 'direkt i den varma pannan' in s.text for s in runtime.design.steps)
        if replacement and base not in SKEWERS:
            unchanged.append({'runtime_id': rid, 'content_sha256': runtime.design.content_sha256, 'disposition': 'verified_direct_frozen_pan_process'})
        if base not in SKEWERS and base != RYE:
            continue
        row = copy.deepcopy(authoring[rid])
        if base in SKEWERS:
            name = SKEWERS[base]
            old = fruit_preparation(name, 'frozen_direct_heat')
            assert sum(old in s['text'] for s in row['steps']) == 1
            for step in row['steps']:
                step['text'] = step['text'].replace(old, fruit_preparation(name, 'thaw_before_threading'))
            row['version'] = '1.0.3'
            reason = 'Coherent thaw, cut, thread and oven process; no frozen-pan instruction after thaw.'
        else:
            for c in row['components']:
                for i in c['ingredients']:
                    if i['name'] == 'bröd':
                        i.update(label='Rågbröd i skivor, vikt som såld', requirements=['pack:rye_bread'])
                        c['name'] = 'Rostat rågbröd till servering'
            for step in row['steps']:
                if step['text'].startswith('Värm bröd kort'):
                    step['text'] = 'Rosta rågbrödsskivorna i torr stekpanna på båda sidor tills ytan är torr och lätt gyllenbrun. Håll varmt fram till servering.'
            row['version'] = '1.0.1'
            reason = 'Title, bread declaration requirement and toasting instruction all require rye bread, never generic pita.'
        row['notes'] += ' Innehållsrättning 2026-10-26: ' + reason
        vocabulary = library_vocabulary([runtime])
        if base == RYE:
            vocabulary['bröd|as_sold'] = ('g', ['pack:rye_bread'])
        author_rows.append(copy.deepcopy(row))
        pack, authored = standardize({'schema_version':'smako-recipe-authoring-v1','pack_id':'recipe-week-review-20261026','recipes':[row]}, vocabulary, reviewed_at='2026-10-26')
        rows.extend(pack['recipes'])
        corrected.append({'previous_id':rid, 'before_content_sha256':runtime.design.content_sha256, 'runtime_id':base+':'+row['version']+':'+row['variant_id'], 'reason':reason, 'before':{k:getattr(runtime.design,k) for k in ['active_minutes','waiting_minutes','total_minutes']}, 'author':authored})
    assert len(corrected) == 9 and len(unchanged) == 12
    # Authoring is preserved separately from standardized output for review.
    for row in rows:
        assert row['design']['version'] in {'1.0.1','1.0.3'}
    (OUTPUT/'authoring.json').write_bytes(encoded({'schema_version':'smako-recipe-authoring-v1','pack_id':'recipe-week-review-20261026','recipes':author_rows}))
    source = {'schema_version':'smako-meal-pack-v1','pack_id':'recipe-week-review-20261026','recipes':rows}
    path = OUTPUT / 'standardized.json'
    path.write_bytes(encoded(source))
    checked = validate_pack_bytes(path.read_bytes())
    assert not checked['rejections'], checked['rejections']
    (REPORT/'validate.json').write_bytes(encoded({k:v for k,v in checked.items() if k!='recipes'}))
    (REPORT/'diff.json').write_bytes(encoded(pack_diff(checked)))
    for record,r in zip(corrected,checked['recipes'],strict=True):
        record.update(content_sha256=r.design.content_sha256,after={k:getattr(r.design,k) for k in ['active_minutes','waiting_minutes','total_minutes']})
        assert record['before'] == record['after']
    if not do_import:
        print({'validated_corrections':9,'unchanged_direct_pan_variants':12})
        return
    (REPORT/'import.json').write_bytes(encoded(import_pack(path)))
    (REPORT/'revocations.json').write_bytes(encoded([revoke_recipe(r['previous_id'],r['reason']) for r in corrected]))
    report_path.write_bytes(encoded({'schema':'smako-week-recipe-review-v1','corrected':corrected,'verified_unchanged':unchanged,'manifest_sha256':library_signature()}))
    print({'issued':len(corrected),'unchanged_direct_pan_variants':len(unchanged)})


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import',dest='do_import',action='store_true')
    main(parser.parse_args().do_import)
