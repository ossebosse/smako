"""Reconcile selected frozen products with eight newly issued recipe methods."""
import argparse
import copy
import json
from pathlib import Path

from admit_expansion_round2_20261101 import OUTPUT, REPORT, insert_step, mark_process, sha
from app.services.meal_library_content import encoded, identity, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes
from correct_round2_portion_text import admit

PACK = OUTPUT / 'standardized-selected-product-corrections.json'
REVIEW = REPORT / 'selected-product-corrections.json'
RECEIPT = REPORT / 'import-selected-product-corrections.json'
QUALIFICATION = REPORT / 'qualification-selected-product-corrections.json'
REASON = 'Ersatt före main efter korggranskning: faktisk fryst produkt, genomhettning, upptining eller uttrycklig avrinning. Tidigare bytes bevaras.'
BASES = {'smako-italian-spaghetti-aglio-olio', 'smako-mexican-sopa-de-lima', 'smako-greek-melitzanosalata'}


def build():
    if RECEIPT.exists():
        raise ValueError('Selected-product corrections are already issued and immutable')
    active = {identity(r): r for r in current_recipes()}
    vocabulary = library_vocabulary(current_recipes())
    authors, recipes, records = [], [], []
    seen = set()
    for path in sorted(OUTPUT.glob('authoring-*.json')):
        if path.name == 'authoring-selected-product-corrections.json':
            continue
        for original in json.loads(path.read_bytes())['recipes']:
            previous_id = ':'.join(original[k] for k in ('base_id', 'version', 'variant_id'))
            if original['base_id'] not in BASES or previous_id not in active:
                continue
            assert previous_id not in seen
            seen.add(previous_id)
            previous = active[previous_id]
            row = copy.deepcopy(original)
            if row['base_id'].endswith('spaghetti-aglio-olio'):
                row['name'] += ' – med hackad vitlök och genomhettad persilja'
                for n, step in enumerate(row['steps'], 1):
                    if step['text'].startswith('Skär broccolin'):
                        step['text'] = 'Använd frysta broccolibuketter direkt från frysen, eller ansa färsk broccoli, skala den ätliga stjälken och väg angiven rå ätlig mängd. Dela färska buketter och stjälk i små bitar. Koka upp 800 ml vatten och sjud broccolin cirka sex minuter eller längre enligt förpackningen tills den är mjuk. Lägg i de redan kokta avrunna bönorna de sista två minuterna. Häll av. Blanda med tillbehörets citronjuice, salt och olivolja och håll varmt.'
                        step['minutes'] = max(step['minutes'], 10)
                        mark_process(row, n, ['broccoli', 'bönor'], 'drain_after_cooking', 'Kokvatten från broccoli och bönor hälls bort. Kvarvarande näring och färdig vikt är inte uppmätta.')
                    if step['text'].startswith('Skiva vitlöken'):
                        step['text'] = 'Använd uppvägd fryst hackad vitlök direkt från frysen, eller skala, väg och finhacka färsk vitlök. Väg upp fryst hackad persilja eller ansad finhackad färsk persilja. Koka upp 3000 ml vatten utan tillsatt salt i en stor kastrull.'
                    if step['text'].startswith('Koka pastan'):
                        mark_process(row, n, ['pasta'], 'drain_after_cooking', 'Pasta kokas och hälls av; bara angiven del kokvatten återförs. Stärkelse- och näringsförlust i kasserat vatten är inte uppmätt.')
                    if step['text'].startswith('Lägg pastans olivolja'):
                        step['text'] = 'Lägg pastans olivolja, den hackade vitlöken och chiliflakes i en kall stor panna. Värm långsamt på medellåg värme under omrörning tills eventuell is tinat och vätskan avdunstat. Fortsätt försiktigt tills vitlöken doftar och är ljust gyllene, inte brun; följ längre genomhettningstid på förpackningen vid behov.'
                        step['minutes'] = max(step['minutes'], 7)
                    if step['text'].startswith('Häll försiktigt 100 ml'):
                        step['text'] = step['text'].replace('Rör ner pastakomponentens salt. Lägg i spaghettin', 'Rör ner pastakomponentens salt och all uppvägd persilja. Sjud under omrörning minst tre minuter eller längre enligt förpackningen. Lägg sedan i spaghettin')
                        step['text'] = step['text'].replace('Vänd ner persiljan och servera genast', 'Servera genast')
                        step['minutes'] += 3
                changes = ['Explicit chopped fresh/frozen garlic and frozen parsley; parsley cooks in the emulsion before pasta is added.',
                           'Frozen broccoli cooks from frozen; pasta/side draining has unknown retention, not assumed full nutrient retention.']
            elif row['base_id'].endswith('melitzanosalata'):
                row['name'] += ' – med genomhettad vitlök'
                for step in row['steps']:
                    if 'Riv vitlöken fint' in step['text']:
                        step['text'] = step['text'].replace('Riv vitlöken fint och blanda med citronjuice, salt och återstående olivolja.',
                            'Väg upp fryst hackad vitlök, eller skala, väg och riv färsk vitlök. Sjud vitlöken med 20 ml vatten under omrörning minst tre minuter eller längre enligt förpackningen. Blanda hela vitlöksblandningen med auberginen, citronjuice, salt och återstående olivolja. Vitlöken är mildare än rå vitlök i denna uttryckliga version.')
                        step['minutes'] += 4
                changes = ['Explicit cooked garlic alternative accepts the selected frozen chopped product; all garlic liquid is retained and the mixture then chills.']
            else:
                for n, step in enumerate(row['steps'], 1):
                    if step['text'].startswith('Sjud under lock cirka 22'):
                        step['text'] = 'Sjud under lock cirka 22 minuter; buljongen ska inte stormkoka.'
                        insert_step(row, n + 1, {'text': 'Mät minst 74 °C mitt i kycklingens tjockaste bit. Fortsätt sjuda och kontrollera igen om den inte är genomlagad. Förpackningens längre tillagningstid gäller om sådan anges.', 'uses': ['kyckling'], 'minutes': 2})
                        break
                for step in row['steps']:
                    if step['text'].startswith('Tillsätt oregano'):
                        step['text'] = step['text'].replace('Lägg ner kycklingen', 'Tillsätt all upptiningsvätska och lägg ner den helt tinade kycklingen')
                row['steps'] = [
                    {'text': 'Om kycklingen är fryst, lägg den i ett täckt läckagesäkert kärl i kylskåp. Håll den skild från sallad och andra ätklara livsmedel. Behåll upptiningsvätskan för genomkokning i soppan.', 'uses': ['kyckling'], 'minutes': 2},
                    {'text': 'Tina fryst kyckling helt i kylskåp enligt förpackningen. Planera 24 timmar och förläng tills ingen iskärna återstår. Redan kylförvarad kyckling går direkt vidare; följ förpackningens användningstid.', 'uses': ['kyckling'], 'minutes': 1440, 'passive': True},
                    *row['steps']]
                for process in row.get('unmeasured_processes', []):
                    process['step'] += 2
                changes = ['Include planned refrigerated thaw for the selected frozen chicken, boil all thaw liquid in the soup and count the 74 C check as active work.']
            for n, step in enumerate(row['steps']):
                step['after'] = [n] if n else []
            major, minor, patch = map(int, row['version'].split('.'))
            row['version'] = f'{major}.{minor}.{patch + 1}'
            row['notes'] += ' Separat granskning mot faktiskt valda produkter: fryst form och genomhettning/upptining följer stegen. Väntetid är planerad, inte provlagd; råvarumängderna är oförändrade.'
            pack, _ = standardize({'schema_version': 'smako-recipe-authoring-v1',
                'pack_id': 'round2-selected-product-corrections', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-02')
            checked = validate_pack_bytes(encoded(pack))
            assert not checked['rejections'], checked['rejections']
            assert previous.ingredients == checked['recipes'][0].ingredients
            authors.append(row)
            recipes.extend(pack['recipes'])
            records.append({'previous_id': previous_id, 'previous_content_sha256': previous.design.content_sha256,
                'runtime_id': ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')),
                'previous_authoring_file': path.name, 'previous_authoring_sha256': sha(path.read_bytes()),
                'changes': changes, 'servings_multiple': None, 'cooking_test': 'not_cooked'})
    assert len(records) == 8
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': 'round2-selected-product-corrections', 'recipes': recipes})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    PACK.write_bytes(raw)
    (OUTPUT / 'authoring-selected-product-corrections.json').write_bytes(encoded({
        'schema_version': 'smako-recipe-authoring-v1', 'pack_id': 'round2-selected-product-corrections', 'recipes': authors}))
    REVIEW.write_bytes(encoded({'pack_sha256': sha(raw), 'recipes': records,
        'scope': 'Eight newly issued variants only; no baseline versions change.'}))
    print({'selected_product_successors': len(records)})


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
