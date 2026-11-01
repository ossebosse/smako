"""Issue explicit portion-text successors; preserve every previous source byte."""
import argparse
import copy
import json
import re
from pathlib import Path

from admit_expansion_round2_20261101 import OUTPUT, REPORT, sha
from app.services.diet_policy import recipe_contains_fish
from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    load_entries,
    manifest_entries,
    pack_diff,
    revoke_recipe,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

PACK = OUTPUT / 'standardized-portion-corrections.json'
REVIEW = REPORT / 'portion-corrections.json'
RECEIPT = REPORT / 'import-portion-corrections.json'
REASON = 'Ersatt före main av granskad 1.0.2: portionsskalning, satsstorlek eller fiskmetadata. Tidigare bytes bevaras.'


def corrected_text(text):
    # These are explicitly reviewed process-water phrases in this delivery.
    # Temperature words, times and package weights are not scalable amounts.
    text = re.sub(r'(\d+(?:[,.]\d+)?) ml (ljummet|hett|kokande|kallt|nytt kallt|sjudande) vatten',
                  r'\1 ml vatten (\2)', text)
    text = re.sub(r'(\d+(?:[,.]\d+)?) ml (?:stärkelserikt |sparat )?kokvatten\b',
                  r'\1 ml vatten från pastakoket', text)
    text = re.sub(r'(\d+(?:[,.]\d+)?) ml av (?:det sparade )?kokvattnet',
                  r'\1 ml vatten från pastakoket', text)
    text = text.replace('80 ml av det ljumma, inte kokande, kokvattnet',
                        '80 ml vatten från pastakoket, ljummet och inte kokande,')
    text = text.replace('500 ml om det behövs för att täcka', '500 ml vatten om det behövs för att täcka')
    text = text.replace('100 ml så grynen inte bränner', '100 ml vatten så grynen inte bränner')
    text = text.replace('400 ml av läggens kokspad', '400 ml vatten från läggkoket, alltså köttets kokspad')
    text = text.replace('Dela laxen i fyra jämntjocka bitar', 'Dela laxen i jämntjocka portionsbitar')
    text = text.replace('i fyra grunda värmetåliga kärl', 'i tillräckligt många grunda värmetåliga kärl')
    text = text.replace('väg 158 g utan fri lag, motsvarande två deklarerade 79 g-mängder',
                        'väg den angivna avrunna mängden utan fri lag')
    text = text.replace('Öppna de två corned beef-konserverna och finfördela hela innehållet inklusive fett och gelé.',
        'Öppna så många corned beef-konserver som inköpslistan anger. Finfördela kött, fett och gelé jämnt och väg den angivna mängden av blandningen; ingen del av den uppvägda produkten ska hällas bort.')
    return text


def build():
    if RECEIPT.exists():
        raise ValueError('Portion correction stage is already issued and immutable')
    active = {identity(r): r for r in current_recipes()}
    vocabulary = library_vocabulary(current_recipes())
    authors, recipes, records = [], [], []
    for path in sorted(OUTPUT.glob('authoring-stage*.json')):
        for original in json.loads(path.read_bytes())['recipes']:
            previous_id = ':'.join(original[k] for k in ('base_id', 'version', 'variant_id'))
            previous = active[previous_id]
            row = copy.deepcopy(original)
            for step in row['steps']:
                step['text'] = corrected_text(step['text'])
            for component in row['components']:
                for ingredient in component['ingredients']:
                    if ingredient['name'] == 'surdegsfralla':
                        ingredient['label'] = 'Färdigbakad svensk surdegsfralla, vägd mängd'
                    if ingredient['name'] == 'corned beef på burk':
                        ingredient['label'] = 'Färdigkokt corned beef, vägd mängd av hela produkten'
            if row['base_id'] in {'smako-indian-murgh-musallam', 'smako-swedish-flasklagg-rotmos'}:
                row['servings_multiple'] = 4
                row['steps'][0]['text'] = 'Denna rätt tillagas i hela satser om 4 portioner, alltså för 4, 8 eller 12 portioner. Vid fler satser används flera hela stycken av samma storlek. ' + row['steps'][0]['text']
            fish_changed = recipe_contains_fish(previous) != previous.design.fish
            if row == original and not fish_changed:
                continue
            row['version'] = '1.0.2'
            row['notes'] = row.get('notes', '') + ' Separat portionsgranskning: vattenmängder följer portionsantalet och livsmedel vägs enligt ingredienslistan. Inte provlagad.'
            pack, _ = standardize({'schema_version': 'smako-recipe-authoring-v1',
                'pack_id': 'round2-portion-corrections', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-02')
            checked = validate_pack_bytes(encoded(pack))
            assert not checked['rejections'], checked['rejections']
            successor = checked['recipes'][0]
            assert [i.model_dump() for i in previous.ingredients] == [i.model_dump() for i in successor.ingredients], previous_id
            authors.append(row)
            recipes.extend(pack['recipes'])
            records.append({'previous_id': previous_id, 'previous_content_sha256': previous.design.content_sha256,
                'runtime_id': identity(successor), 'content_sha256': successor.design.content_sha256,
                'previous_authoring_file': path.name, 'previous_authoring_sha256': sha(path.read_bytes()),
                'changes': ['Explicit reviewed process-water spelling and dose-neutral instructions/labels.',
                            'No ingredient quantity, unit, food identity or product requirements changed.'],
                'servings_multiple': row.get('servings_multiple'), 'fish_metadata_corrected': fish_changed,
                'cooking_test': 'not_cooked'})
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': 'round2-portion-corrections', 'recipes': recipes})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    PACK.write_bytes(raw)
    (OUTPUT / 'authoring-portion-corrections.json').write_bytes(encoded({
        'schema_version': 'smako-recipe-authoring-v1', 'pack_id': 'round2-portion-corrections', 'recipes': authors}))
    REVIEW.write_bytes(encoded({'pack_sha256': sha(raw), 'recipes': records,
        'scope': 'Correct successors of this review round only; no baseline recipe version changes.'}))
    print({'corrected_versions': len(records), 'batch_limited': sum(bool(r['servings_multiple']) for r in records),
           'fish_metadata_corrected': sum(r['fish_metadata_corrected'] for r in records)})


def admit(probe_path=None):
    raw = PACK.read_bytes()
    review = json.loads(REVIEW.read_bytes())
    assert sha(raw) == review['pack_sha256']
    checked = validate_pack_bytes(raw)
    assert not checked['rejections']
    expected = {r['runtime_id']: r['content_sha256'] for r in review['recipes']}
    assert {identity(r): r.design.content_sha256 for r in checked['recipes']} == expected
    if probe_path:
        probe = json.loads(probe_path.read_bytes())
        assert probe['pack_sha256'] == sha(raw) and not probe['input_only']
        rows = probe['modes']['estimated']['recipes']
        assert {r['id'] for r in rows} == expected.keys() and len(rows) == len(expected)
        assert all(r['status'] == 'verified' and r['audit']['passed'] for r in rows)
        receipt = json.loads(RECEIPT.read_bytes())
        receipt.update(basket_status='verified_estimated', qualification_sha256=sha(probe_path.read_bytes()))
        RECEIPT.write_bytes(encoded(receipt))
        (REPORT / 'qualification-portion-corrections.json').write_bytes(probe_path.read_bytes())
        print({'qualified': len(rows)})
        return
    if RECEIPT.exists():
        raise ValueError('Correction stage is already issued')
    assert {r['status'] for r in pack_diff(checked)} == {'new_version'}
    manifest = manifest_entries()
    old = {identity(r): r.design.content_sha256 for r in load_entries(manifest['current'] + manifest['history'])}
    assert all(old[r['previous_id']] == r['previous_content_sha256'] for r in review['recipes'])
    before = (ROOT / 'library-manifest.json').read_bytes()
    result = import_pack(PACK, accepted_ids=set(expected))
    for record in review['recipes']:
        revoke_recipe(record['previous_id'], REASON)
    after = (ROOT / 'library-manifest.json').read_bytes()
    assert import_pack(PACK, accepted_ids=set(expected))['published_file'] == result['published_file']
    assert (ROOT / 'library-manifest.json').read_bytes() == after
    RECEIPT.write_bytes(encoded({'before_manifest_sha256': sha(before), 'after_manifest_sha256': sha(after),
        'pack_sha256': sha(raw), 'basket_status': 'pending_local_qualification', 'idempotent_reimport': True,
        'new_revocations': {r['previous_id']: REASON for r in review['recipes']}, 'result': result}))
    print({'issued_successors': len(expected), 'withdrawn_previous_versions': len(review['recipes'])})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-reviewed', action='store_true')
    parser.add_argument('--qualifying-report', type=Path)
    args = parser.parse_args()
    if args.qualifying_report:
        admit(args.qualifying_report)
    elif args.import_reviewed:
        admit()
    else:
        build()
