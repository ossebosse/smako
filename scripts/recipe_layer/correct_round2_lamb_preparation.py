"""Bind long braises to lamb leg and include source-supported frozen preparation."""
import argparse
import copy
import json
from pathlib import Path

from admit_expansion_round2_20261101 import OUTPUT, REPORT, mark_process, rename_ingredient, sha
from app.services.meal_library_content import encoded, identity, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes
from correct_round2_portion_text import admit

PACK = OUTPUT / 'standardized-lamb-corrections.json'
REVIEW = REPORT / 'lamb-corrections.json'
RECEIPT = REPORT / 'import-lamb-corrections.json'
QUALIFICATION = REPORT / 'qualification-lamb-corrections.json'
REASON = 'Ersatt före main av granskad 1.0.2: benfri lammstek, kylupptining och okänd putsförlust. Tidigare bytes bevaras.'


def build():
    if RECEIPT.exists():
        raise ValueError('Lamb correction stage is already issued and immutable')
    active = {identity(r): r for r in current_recipes()}
    vocabulary = library_vocabulary(current_recipes())
    authors, recipes, records = [], [], []
    for stage in (25, 26, 27):
        path = OUTPUT / f'authoring-stage{stage}.json'
        for original in json.loads(path.read_bytes())['recipes']:
            previous_id = ':'.join(original[k] for k in ('base_id', 'version', 'variant_id'))
            previous = active[previous_id]
            row = copy.deepcopy(original)
            rename_ingredient(row, 'lammkött', 'benfri lammstek')
            row['primary'] = 'benfri lammstek'
            row['name'] += ' – med benfri lammstek och planerad kylupptining'
            for component in row['components']:
                for item in component['ingredients']:
                    if item['name'] == 'benfri lammstek':
                        item.update(form='as_sold', label='Benfri lammstek, inköpt vikt före eventuell putsning')
            row['notes'] = 'Granskad version med benfri lammstek. Den ursprungliga dosen i gram används nu som inköpt vikt före eventuell putsning, en ny kulinarisk dos utan påstående om samma ätliga mängd. Bara stek stöds, inte lammytterfilé, rostbiff, färs eller benbärande kött. Planerad tid inkluderar 24 timmars kylupptining; redan kylförvarat kött kan tillagas direkt. Följ alltid förpackningens förvaring och användningstid. All upptiningsvätska genomkokas i grytan; putsförlust och serverad näring är okända. Övriga uttalade krydd-, kött- och matlagningsvinsanpassningar i föregående granskning gäller. Inte provlagad.'
            first = row['steps'][0]
            first['text'] = first['text'].replace('Väg benfritt lamm efter eventuell putsning. ', '')
            first['text'] = first['text'].replace('Väg benfritt lammkött utan grova senor och skär det', 'Skär lammsteken')
            first['text'] = first['text'].replace('Putsa bort grova senor vid behov, väg därefter angiven rå ätlig mängd benfritt lamm och skär', 'Skär lammsteken')
            first['text'] = 'Kontrollera att köttet är helt tinat. Vänd köttet med vätskan i kärlet och väg den angivna mängden som kött tillsammans med tillhörande upptiningsvätska, före putsning. Förvara överblivet kött enligt förpackningen. Spara den uppvägda delens vätska kallt i en separat skål. Putsa endast bort eventuella grova senor från den uppvägda mängden; väg inte upp extra kött efter putsningen. ' + first['text']
            mark_process(row, 1, ['benfri lammstek'], 'trim_before_cooking', 'Inköpt benfri stek vägs före eventuell putsning. Andelen senor och näringsförlusten är inte uppmätta; inget utbyte antas.')
            # Add raw thaw liquid only after browning so it is fully cooked,
            # without converting the tsigariasto method to a water-filled stew.
            browned = 2 if stage == 25 else 3 if stage == 26 else (2 if row['variant_id'] == 'simple' else 3)
            row['steps'][browned - 1]['text'] += ' Häll därefter i all sparad upptiningsvätska och koka upp ordentligt innan den långa tillagningen fortsätter.'
            row['steps'][browned - 1]['uses'] = list(dict.fromkeys([*row['steps'][browned - 1]['uses'], 'benfri lammstek']))
            row['steps'][browned - 1]['minutes'] += 2
            row['steps'] = [
                {'text': 'Om den inköpta benfria lammsteken är fryst, lägg förpackningen i ett täckt läckagesäkert kärl i kylskåp. Den behöver inte delas i fryst tillstånd. Behåll vätskan med köttet; receptmängden vägs efter upptiningen och före putsning.', 'uses': ['benfri lammstek'], 'minutes': 2},
                {'text': 'Tina fryst kött helt i kylskåp enligt förpackningen. Planera 24 timmar och förläng vid behov tills ingen iskärna återstår. Redan kylförvarat kött behöver ingen upptining och går direkt vidare; förvaring får inte överskrida förpackningens anvisning.', 'uses': ['benfri lammstek'], 'minutes': 1440, 'passive': True},
                *row['steps']]
            for process in row['unmeasured_processes']:
                process['step'] += 2
            for n, step in enumerate(row['steps']):
                step['after'] = [n] if n else []
            row['version'] = '1.0.2'
            pack, _ = standardize({'schema_version': 'smako-recipe-authoring-v1',
                'pack_id': 'round2-lamb-corrections', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-02')
            authors.append(row)
            recipes.extend(pack['recipes'])
            records.append({'previous_id': previous_id, 'previous_content_sha256': previous.design.content_sha256,
                'runtime_id': ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')),
                'previous_authoring_file': path.name, 'previous_authoring_sha256': sha(path.read_bytes()),
                'changes': ['Explicit reviewed boneless-leg source identity replaces broad edible lamb; same numeric grams are a new pre-trim purchased dose, not equivalent yield.',
                    'Add 24-hour refrigerated thaw planning, retain and boil all thaw liquid, record unknown trim loss and enforce meat restrictions.'],
                'servings_multiple': None, 'cooking_test': 'not_cooked'})
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': 'round2-lamb-corrections', 'recipes': recipes})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    assert len(records) == 9
    PACK.write_bytes(raw)
    (OUTPUT / 'authoring-lamb-corrections.json').write_bytes(encoded({
        'schema_version': 'smako-recipe-authoring-v1', 'pack_id': 'round2-lamb-corrections', 'recipes': authors}))
    REVIEW.write_bytes(encoded({'pack_sha256': sha(raw), 'recipes': records,
        'scope': 'Only nine newly issued lamb variants, no baseline recipe changes.'}))
    print({'corrected_lamb_versions': len(records)})


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
