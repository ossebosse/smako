"""Issue a Vada pav successor with purchased date mass before pit removal."""
import argparse
import copy
import json
from pathlib import Path

from admit_expansion_round2_20261101 import OUTPUT, REPORT, mark_process, sha
from app.services.meal_library_content import encoded, identity, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes
from correct_round2_portion_text import admit

PACK = OUTPUT / 'standardized-date-basis-corrections.json'
REVIEW = REPORT / 'date-basis-corrections.json'
RECEIPT = REPORT / 'import-date-basis-corrections.json'
QUALIFICATION = REPORT / 'qualification-date-basis-corrections.json'
REASON = 'Ersatt före main av 1.0.2: 60 g dadlar avser inköpt vikt med kärnor, före urkärning med okänd förlust. Ingen ätlig vikt eller kärnandel antas.'


def build():
    if RECEIPT.exists():
        raise ValueError('Date correction already issued')
    active = {identity(r): r for r in current_recipes()}
    vocabulary = library_vocabulary(current_recipes())
    source = OUTPUT / 'authoring-stage59.json'
    document = json.loads(source.read_bytes())
    original, = document['recipes']
    old_id = ':'.join(original[k] for k in ('base_id', 'version', 'variant_id'))
    previous = active[old_id]
    row = copy.deepcopy(original)
    row['version'] = '1.0.2'
    row['name'] += ' och dadelchutney'
    for component in row['components']:
        for item in component['ingredients']:
            if item['name'] == 'dadlar':
                item['label'] = 'Dadlar, inköpt vikt med kärnor före urkärning'
    index = next(n for n, s in enumerate(row['steps'], 1) if s['text'].startswith('Kontrollera att dadlarna'))
    row['steps'][index - 1]['text'] = row['steps'][index - 1]['text'].replace(
        'Kontrollera att dadlarna är urkärnade och väg den ätliga mängden utan kärnor.',
        'Väg dadlarna med kärnor till den angivna inköpta mängden. Ta ur och kasta samtliga kärnor; fyll inte på extra dadlar. Använd allt kvarvarande fruktkött.')
    mark_process(row, index, ['dadlar'], 'trim_before_cooking',
                 'Inköpt dadelvikt inkluderar kärnor. Kärnornas andel och kvarvarande ätlig vikt är okända; ingen gramomräkning görs.')
    row['notes'] += ' Korggranskning visar Fontana färska ekologiska dadlar 400 g med kärnor, artikel 27096/GTIN 7316150270969. De 60 g avser nu inköpt vikt före urkärning, inte 60 g fruktkött; inget extra köps efter putsning. Källa: https://www.fontana.se/produkt/farska-dadlar-ekologiska/ . Okänd kärnförlust kräver samma begränsning för serverad vikt/näring som övriga V3-förluster.'
    pack, _ = standardize({**document, 'pack_id': 'round2-date-basis-corrections', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-02')
    raw = encoded(pack)
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    successor, = checked['recipes']
    before = [(i.canonical_name, i.form, i.quantity, i.unit, i.product_requirements) for i in previous.ingredients]
    after = [(i.canonical_name, i.form, i.quantity, i.unit, i.product_requirements) for i in successor.ingredients]
    assert before == after
    record = {'previous_id': old_id, 'previous_content_sha256': previous.design.content_sha256,
              'runtime_id': identity(successor), 'content_sha256': successor.design.content_sha256,
              'previous_authoring_file': source.name, 'previous_authoring_sha256': sha(source.read_bytes()),
              'changes': ['Same 60 g as-sold purchased dates, now explicitly weighed before removing pits with unknown loss. No edible yield or density. Source Fontana 27096 identifies fresh Mazafati dates with a pit; same exact purchase requirements and all other food doses retained.'],
              'servings_multiple': None, 'cooking_test': 'not_cooked'}
    PACK.write_bytes(raw)
    (OUTPUT / 'authoring-date-basis-corrections.json').write_bytes(encoded({
        'schema_version': 'smako-recipe-authoring-v1', 'pack_id': 'round2-date-basis-corrections', 'recipes': [row]}))
    REVIEW.write_bytes(encoded({'pack_sha256': sha(raw), 'recipes': [record],
                               'scope': 'Only newly issued stage59 Vada pav extended; original reference recipes unchanged.'}))
    print({'date_basis_successors': 1})


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
