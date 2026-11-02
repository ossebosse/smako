"""Issue three immutable Pindi chole successors with scalable cooking-water text."""
import argparse
import copy
import json
from pathlib import Path

from admit_expansion_round2_20261101 import OUTPUT, REPORT, sha
from app.services.meal_library_content import encoded, identity, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes
from correct_round2_portion_text import admit, corrected_text

PACK = OUTPUT / 'standardized-pindi-portion-corrections.json'
REVIEW = REPORT / 'pindi-portion-corrections.json'
RECEIPT = REPORT / 'import-pindi-portion-corrections.json'
QUALIFICATION = REPORT / 'qualification-pindi-portion-corrections.json'
REASON = 'Ersatt före main av granskad 1.0.2: blötläggningsvattnets uttryckliga dos skalar med portionerna. Tidigare bytes och råvarumängder bevaras.'


def build():
    if RECEIPT.exists():
        raise ValueError('Pindi portion corrections are already issued')
    active = {identity(r): r for r in current_recipes()}
    vocabulary = library_vocabulary(current_recipes())
    source = OUTPUT / 'authoring-stage43.json'
    document = json.loads(source.read_bytes())
    authors, native, records = [], [], []
    for original in document['recipes']:
        old_id = ':'.join(original[k] for k in ('base_id', 'version', 'variant_id'))
        previous = active[old_id]
        row = copy.deepcopy(original)
        row['version'] = '1.0.2'
        for step in row['steps']:
            step['text'] = corrected_text(step['text'])
        row['notes'] += ' Blötläggningsvattnets text är granskad för portionsskalning; inga råvarumängder ändras.'
        pack, _ = standardize({**document, 'pack_id': 'round2-pindi-portion-corrections', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-02')
        checked = validate_pack_bytes(encoded(pack))
        assert not checked['rejections'], checked['rejections']
        successor, = checked['recipes']
        assert previous.ingredients == successor.ingredients
        authors.append(row)
        native.extend(pack['recipes'])
        records.append({'previous_id': old_id, 'previous_content_sha256': previous.design.content_sha256,
            'runtime_id': identity(successor), 'content_sha256': successor.design.content_sha256,
            'previous_authoring_file': source.name, 'previous_authoring_sha256': sha(source.read_bytes()),
            'changes': ['Express cold soaking water as scalable ml vatten (kallt); all food identities, amounts, units and product requirements unchanged.'],
            'servings_multiple': None, 'cooking_test': 'not_cooked'})
    assert len(records) == 3
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': 'round2-pindi-portion-corrections', 'recipes': native})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections']
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    PACK.write_bytes(raw)
    (OUTPUT / 'authoring-pindi-portion-corrections.json').write_bytes(encoded({
        'schema_version': 'smako-recipe-authoring-v1', 'pack_id': 'round2-pindi-portion-corrections', 'recipes': authors}))
    REVIEW.write_bytes(encoded({'pack_sha256': sha(raw), 'recipes': records,
        'scope': 'Three newly issued Pindi chole variants only; no baseline recipe changes.'}))
    print({'pindi_portion_successors': len(records)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import-reviewed', action='store_true')
    parser.add_argument('--qualifying-report', type=Path)
    args = parser.parse_args()
    if args.import_reviewed or args.qualifying_report:
        admit(args.qualifying_report, pack=PACK, review_path=REVIEW, receipt_path=RECEIPT,
              reason=REASON, qualification_path=QUALIFICATION)
    else:
        build()
