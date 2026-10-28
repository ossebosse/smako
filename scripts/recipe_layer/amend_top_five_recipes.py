"""Issue reviewed existing-store alternatives without altering historical recipes."""
import argparse
import copy
import re
from collections import Counter

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

REPORT = ROOT.parents[3] / 'docs/reviews/top-five-ingredients-20261028'
OUTPUT = ROOT / 'reviewed-top-five-20261028'
PACK = 'top-five-review-20261028'
FOODS = {
    'pärlkorn': ('kornris', 'dry', 'g', 'kornris'),
    'masa harina': ('förkokt vitt majsmjöl', 'dry', 'g', 'precooked_white_maize'),
    'tamarindpasta': ('tamarindkoncentrat', 'as_sold', 'ml', 'tamarind_concentrate'),
    'citrongräs': ('citrongräs', 'as_sold', 'g', 'whole_lemongrass'),
    'klibbigt ris': ('sushiris', 'dry', 'g', 'sushi_rice'),
}
REASON = (
    'Granskade alternativ i befintliga butikskontexter 2026-10-28. '
    'Nya uttryckliga råvaror och beredningar; inga identitetsalias, mass-/volymomräkningar '
    'eller garanterade ätliga utbyten. Originalversionen bevaras. '
    'Mängder, smakbalans och tider i anpassningen är författaruppskattningar; inte provlagat. '
    'Se docs/reviews/top-five-ingredients-20261028/cooking-review.json.'
)


def requirement(old):
    return 'pack:intake_all_shape_top5_' + FOODS[old][3]


def step(text, minutes, uses, passive=False):
    return {'text': text, 'minutes': minutes, 'uses': uses, 'passive': passive}


def rewrite_steps(row, replacements):
    """Replace step groups and remap every original dependency, including deletions."""
    result, mapping = [], {}
    for old_index, original in enumerate(row['steps']):
        dependencies = sorted({n for d in original.get('after', []) for n in mapping[d]})
        replacement = replacements.get(old_index, [copy.deepcopy(original)])
        for new in replacement:
            new = copy.deepcopy(new)
            new['after'] = dependencies
            result.append(new)
            dependencies = [len(result)]
        mapping[old_index + 1] = dependencies
    row['steps'] = result


def rename_text(text, old, new):
    # Keep Swedish sentence capitalization; longer inflected forms first.
    pairs = {
        'tamarindpasta': [('tamarindpastan', 'tamarindkoncentratet'), ('tamarindpasta', new)],
        'pärlkorn': [('pärlkornet', 'kornriset'), ('pärlkorn', new),
                    ('korngrynskomponenten', 'kornriskomponenten'),
                    ('korngrynen', 'kornriset'), ('korngryn', new)],
        'klibbigt ris': [('ångat klibbigt ris', 'kokt rundkornigt ris'),
                        ('ångade klibbiga riset', 'kokta rundkorniga riset'),
                        ('ångat kokosris', 'kokosris av sushiris'),
                        ('klibbigt ris', 'rundkornigt ris')],
    }.get(old, [(old, new)])
    for before, after in pairs:
        text = re.sub(re.escape(before),
                      lambda m, after=after: after.capitalize() if m[0][0].isupper() else after,
                      text, flags=re.IGNORECASE)
    return text.replace('kornrisss', 'kornriss').replace('Kornrisss', 'Kornriss')


def rename(row, old):
    new = FOODS[old][0]
    for key in ('name', 'side', 'primary', 'flavor'):
        if isinstance(row[key], list):
            row[key] = [rename_text(value, old, new) for value in row[key]]
        else:
            row[key] = new if row[key] == old else rename_text(row[key], old, new)
    for component in row['components']:
        component['name'] = rename_text(component['name'], old, new)
    for s in row['steps']:
        s['text'] = rename_text(s['text'], old, new)
        s['uses'] = [new if u == old else u for u in s['uses']]


def adapt_rice(row):
    starts = [i for i, s in enumerate(row['steps']) if 'klibbigt ris' in s['uses']
              and 'blötlägg' in s['text'] and 'blötläggningsvatten' not in s['text']]
    finishes = [i for i, s in enumerate(row['steps']) if 'klibbigt ris' in s['uses']
                and ('Ånga under lock' in s['text'] or 'Ånga' in s['text'] and 'Häll av' in s['text'])]
    assert len(starts) == len(finishes) == 1, row['base_id']
    a, b = starts[0], finishes[0]
    assert row['steps'][a + 1]['passive'] and row['steps'][b + 1]['passive']
    salted = 'salt' in row['steps'][b]['uses']
    uses = ['klibbigt ris', *(['salt'] if salted else [])]
    rewrite_steps(row, {
        a: [step('Väg upp torrt sushiris och mät även dess torra volym i ett mått; notera volymen. '
                 'Skölj riset och låt rinna av i sil. Förvara täckt i kylskåp fram till koksteget. '
                 'Denna version använder rundkornigt sushiris och kräver ingen lång blötläggning.',
                 3, ['klibbigt ris'])], a + 1: [],
        b: [step('Lägg det sköljda sushiriset i en kastrull med lock. Mät upp lika stor volym kallt '
                 'vatten som den tidigare uppmätta TORRA risvolymen. '
                 + ('Tillsätt riskomponentens salt. ' if salted else '')
                 + 'Koka upp och sänk till låg värme.', 4, uses),
            step('Sjud sushiriset under lock cirka 15 minuter tills vattnet absorberats och kornen '
                 'är mjuka utan hård kärna. Följ den valda förpackningens anvisning om den skiljer sig.',
                 15, uses, True),
            step('Ta kastrullen från värmen och låt riset vila under lock cirka tio minuter. '
                 'Lossa försiktigt med en sked. Använd därefter i följande moment och håll varmt '
                 'under lock fram till serveringen. Vilan är en författaruppskattning.',
                 10, uses, True)], b + 1: [],
    })
    row['equipment'] = [x for x in row['equipment'] if x not in {
        'Ånginsats', 'Finmaskig ånginsats', 'Ren silduk', 'Ren tunn kökshandduk'}]
    row['equipment'] = list(dict.fromkeys([*row['equipment'], 'Kastrull med lock', 'Sil']))


def adapt_lemongrass(row):
    # The specified amount is whole purchased stalks, not a claimed tender-core yield.
    i = next(i for i, s in enumerate(row['steps']) if 'citrongräs' in s['uses'])
    row['steps'][i]['text'] = (
        'Väg citrongräset helt före ansning enligt ingredienslistans inköpsvikt. '
        'Skölj och ta bort torra ytterblad, hård rotände och grov överdel. '
        'Använd den mjuka ljusa kärna som faktiskt återstår från den uppvägda råvaran; '
        'finhacka mycket tunt så att inga sega strån följer med maten. '
        'Det finns inget bestämt gramkrav på kärnan i denna version. '
        + row['steps'][i]['text'])
    row['steps'][i]['minutes'] += 3


def adapt_maize(row):
    base, steps = row['base_id'], row['steps']
    flour = next(i for c in row['components'] for i in c['ingredients'] if i['name'] == 'masa harina')
    water = {55: 85, 65: 100, 250: 375, 360: 540}[flour['quantity']]
    mix = next(i for i, s in enumerate(steps) if 'masa harina' in s['text'])
    steps[mix]['text'] = re.sub(r'\d+ ml vatten', f'{water} ml vatten', steps[mix]['text'], count=1)
    steps[mix]['text'] = steps[mix]['text'].replace(
        'Ingen vanlig majsstärkelse får ersätta masa harina.',
        'Använd förkokt vitt majsmjöl för denna version. Majsstärkelse fungerar inte som degbas.')
    steps[mix]['text'] = 'Använd förkokt vitt majsmjöl avsett för formbar majsdeg. ' + steps[mix]['text']
    if base.endswith('breakfast-steamed-corn-breakfast-parcel'):
        steps[mix]['text'] = steps[mix]['text'].replace(
            'till en mjuk smet. Bred ut',
            'till en mjuk formbar deg. Låt svälla fem minuter innan du formar den. Bred ut')
        steps[mix]['minutes'] += 5
    elif base.endswith('breakfast-stuffed-masa-breakfast-cakes'):
        steps[mix]['text'] += ' Låt degen svälla fem minuter innan den formas.'
        steps[mix]['minutes'] += 5
        steps[1]['text'] = ('Platta degen till runda ofyllda kakor, högst en centimeter tjocka. '
                            'Spara bönor och ost som fyllning till efter stekningen.')
        steps[1]['uses'] = ['masa harina']
        steps[2]['text'] += (' Dela en kaka och kontrollera att mitten saknar torr mjölig kärna; '
                             'fortsätt på låg värme vid behov. Skär sedan en ficka i sidan på varje '
                             'varm kaka, fyll med bönor och ost och servera direkt.')
        steps[2]['uses'] = list(dict.fromkeys([*steps[2]['uses'], 'svarta bönor', 'ost']))
        steps[2]['minutes'] += 3
    elif base.endswith('chicken-broth-unfilled-masa-dumplings'):
        steps[mix]['text'] = steps[mix]['text'].replace('fyra per portion', 'åtta per portion')
        cook = next(s for s in steps if 'Lägg majsdegsklimparna direkt i buljongen' in s['text'])
        cook['text'] = (
            'Låt buljongen nå lugn kokning. Lägg de små majsdegsklimparna försiktigt i buljongen. '
            'Låt dem först sätta sig utan omrörning; rör sedan varsamt så att de inte fastnar. '
            'Sjud cirka 18 minuter. Dela en klimp och fortsätt vid behov tills mitten är genomvarm '
            'och saknar torr mjölig kärna. Servera klimpar och buljong tillsammans. '
            'Tid och mindre klimpstorlek är författarens anpassning till förkokt majsmjöl.')
    elif base == 'smako-intake-masa-cake':
        target = next(s for s in steps if s['text'].startswith('Forma majsdegen till'))
        target['text'] = target['text'].replace('tjocka runda kakor', 'runda kakor högst en centimeter tjocka')
        target['text'] += ' Dela en kaka: mitten ska sakna torr mjölig kärna; sänk värmen och fortsätt vid behov.'
    elif base == 'smako-intake-masa-pocket':
        # P.A.N.'s filled dough supports folding. This remains a separately authored pan-baked version.
        target = next(s for s in steps if s['text'].startswith('Platta ut majsdegen'))
        target['text'] = target['text'].replace('runda plattor', 'runda plattor högst en halv centimeter tjocka')
        target['text'] += ' Fukta kanterna lätt och laga sprickor innan stekning.'
    elif base != 'smako-mexican-bean-tamale-parcels':
        raise AssertionError(base)
    steps[mix]['text'] += (' Den angivna vattenmängden är en startmängd för denna anpassning. '
                          'Kontrollera efter vilan att degen är sammanhängande och formbar; '
                          'arbeta vid behov in lite vatten i taget om den spricker.')
    row['name'] = row['name'].replace(' – ', ' (förkokt majsmjöl) – ', 1)


def adapt_barley(row):
    steps, base = row['steps'], row['base_id']
    separate = next((i for i, s in enumerate(steps) if s['text'].startswith('Korngryn: Skölj pärlkorn.')), None)
    if separate is not None:
        i = separate
        steps[i]['text'] = ('Kornris: Koka upp 2000 ml vatten med riskomponentens salt. '
                             'Lägg i det torra kornriset. Spara riskomponentens olja till efter avrinningen.')
        steps[i + 1].update(text='Koka kornriset i rikligt med vatten 13–15 minuter tills kornen är mjuka. '
                                'Det ska finnas kokvatten kvar att hälla av.', minutes=15)
        steps[i + 2].update(text='Häll av kornriset i durkslag. Vänd ner riskomponentens olja. '
                                'Använd i följande steg eller servera som tillbehör.', minutes=2, passive=False)
    elif base == 'smako-greek-feta-onion-shells-barley':
        steps[1]['text'] = 'Koka upp 2000 ml vatten och lägg i det torra kornriset.'
        steps[1]['minutes'] = 4
        steps[2].update(text='Koka kornriset 13–15 minuter tills kornen är mjuka.', minutes=15)
        steps[3]['text'] = 'Häll av kornriset noggrant i durkslag. ' + steps[3]['text']
        steps[3]['minutes'] += 2
    else:
        i = next(i for i, s in enumerate(steps) if s['text'].startswith('Rör ner pärlkorn,'))
        old = steps[i]
        text = old['text'].replace('Rör ner pärlkorn, ', 'Rör ner ')
        broth = base == 'smako-greek-chicken-barley-mushroom-broth'
        if not broth:
            text = re.sub(r'\d+ ml vatten', '250 ml vatten', text)
        old['text'] = text
        old['uses'] = [u for u in old['uses'] if u != 'pärlkorn']
        if base in {'smako-italian-barley-mushroom-whitebean-risotto',
                    'smako-italian-mackerel-tomato-barley-pan'}:
            steps[i + 1]['minutes'] = 15
            steps[i + 1]['text'] = steps[i + 1]['text'].replace('35 minuter', '15 minuter')
        steps[i + 1]['text'] = steps[i + 1]['text'].replace('Korngrynen ska vara helt mjuka och rätten', 'Rätten')
        steps[i + 1]['text'] += (' Kontrollera att det finns vätska i botten och späd med lite vatten vid behov. '
                                  'Vänd till sist ner allt separat kokt och avrunnet kornris och värm igenom.')
        # Prepare grain before handling raw meat, never interrupt partial meat cooking.
        grain_steps = [
            step('Koka upp 2000 ml vatten i en separat kastrull och lägg i det torra kornriset.',
                 4, ['pärlkorn']),
            step('Koka kornriset i rikligt med vatten 13–15 minuter tills kornen är mjuka.',
                 15, ['pärlkorn'], True),
            step('Häll av kornriset i durkslag och håll varmt under lock på mycket låg värme '
                 'till grytans avslutande moment. Rör vid behov ner lite vatten så att det inte fastnar.',
                 2, ['pärlkorn'])]
        for n, s in enumerate(grain_steps):
            s['after'] = [n] if n else []
        for s in row['steps']:
            s['after'] = [n + 3 for n in s.get('after', [])] or [3]
        row['steps'] = [*grain_steps, *row['steps']]
    row['equipment'] = list(dict.fromkeys([*row['equipment'], 'Kastrull', 'Durkslag']))


def adapt(original):
    row = copy.deepcopy(original)
    groups = sorted({i['name'] for c in row['components'] for i in c['ingredients']} & FOODS.keys())
    if 'klibbigt ris' in groups:
        adapt_rice(row)
    if 'citrongräs' in groups:
        adapt_lemongrass(row)
    if 'masa harina' in groups:
        adapt_maize(row)
    if 'pärlkorn' in groups:
        adapt_barley(row)
    if 'tamarindpasta' in groups:
        i = next(i for i, s in enumerate(row['steps']) if 'tamarindpasta' in s['uses'])
        row['steps'][i]['text'] = (
            'Mät upp tamarindkoncentratet i volym enligt ingredienslistan. '
            + row['steps'][i]['text'])
    for component in row['components']:
        for item in component['ingredients']:
            old = item['name']
            if old not in groups:
                continue
            name, form, unit, _ = FOODS[old]
            item.update(name=name, form=form, unit=unit, requirements=[requirement(old)])
            if old == 'tamarindpasta':
                # An authored seasoning dose, never a density or concentration conversion.
                item['quantity'] = 5 * row['servings']
                item['label'] = 'Tamarindkoncentrat CHS, uppmätt volym; ny receptdos'
            elif old == 'citrongräs':
                item['quantity'] = 12.5 * row['servings']
                item['label'] = 'Hela citrongrässtjälkar, inköpsvikt före ansning'
            else:
                item['label'] = name.capitalize() + ', torr vikt'
    for old in groups:
        rename(row, old)
    version = row['version'].split('.')
    row['version'] = '.'.join([*version[:-1], str(int(version[-1]) + 1)])
    row['notes'] += ' ' + REASON + ' Ändrade grupper: ' + ', '.join(groups) + '.'
    return row, groups


def main(do_import=False):
    REPORT.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    review = REPORT / 'recipe-review.json'
    if review.exists():
        manifest = manifest_entries()
        issued = {identity(r): r for r in load_entries([*manifest['current'], *manifest['history']], ROOT)}
        prior = read_json(review)
        assert all(issued[r['runtime_id']].design.content_sha256 == r['content_sha256'] for r in prior['corrected'])
        print({'already_issued': len(prior['corrected']), 'no_bytes_rewritten': True})
        return
    active = {identity(r): r for r in current_recipes()
              if any(i.canonical_name in FOODS for i in r.ingredients)}
    assert len(active) == 192, len(active)
    originals = {}
    for path in ROOT.rglob('authoring.json'):
        if OUTPUT in path.parents:
            continue
        for row in read_json(path)['recipes']:
            rid = ':'.join(row[k] for k in ('base_id', 'version', 'variant_id'))
            if rid in active:
                assert rid not in originals
                originals[rid] = row
    assert originals.keys() == active.keys()
    authors, rows, corrected, readiness = [], [], [], []
    for rid, original in sorted(originals.items()):
        row, groups = adapt(original)
        vocabulary = library_vocabulary([active[rid]])
        for old in groups:
            name, form, unit, _ = FOODS[old]
            vocabulary[f'{name}|{form}'] = (unit, [requirement(old)])
        authors.append(copy.deepcopy(row))
        pack, checks = standardize({'schema_version': 'smako-recipe-authoring-v1',
            'pack_id': PACK, 'recipes': [row]}, vocabulary, reviewed_at='2026-10-28')
        readiness.extend(checks)
        rows.extend(pack['recipes'])
        corrected.append({'previous_id': rid, 'runtime_id': ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')),
                          'groups': groups, 'before_content_sha256': active[rid].design.content_sha256, 'reason': REASON})
    (OUTPUT / 'authoring.json').write_bytes(encoded({'schema_version': 'smako-recipe-authoring-v1',
                                                   'pack_id': PACK, 'recipes': authors}))
    path = OUTPUT / 'standardized.json'
    path.write_bytes(encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': PACK, 'recipes': rows}))
    checked = validate_pack_bytes(path.read_bytes())
    assert not checked['rejections'], checked['rejections']
    (REPORT / 'validate.json').write_bytes(encoded({k: v for k, v in checked.items() if k != 'recipes'}))
    (REPORT / 'diff.json').write_bytes(encoded(pack_diff(checked)))
    (REPORT / 'readiness.json').write_bytes(encoded(readiness))
    for record, recipe in zip(corrected, checked['recipes'], strict=True):
        record['content_sha256'] = recipe.design.content_sha256
        old = active[record['previous_id']]
        assert set(re.findall(r'\d+ °C', ' '.join(old.instructions))) <= set(
            re.findall(r'\d+ °C', ' '.join(recipe.instructions)))
        assert len(old.ingredients) == len(recipe.ingredients)
        for before, after in zip(old.ingredients, recipe.ingredients, strict=True):
            if before.canonical_name not in FOODS:
                assert before == after, (record['previous_id'], before.canonical_name)
            else:
                name, form, unit, _ = FOODS[before.canonical_name]
                assert (after.canonical_name, after.form, after.unit) == (name, form, unit)
                assert after.product_requirements == (requirement(before.canonical_name),)
                if before.canonical_name not in {'tamarindpasta', 'citrongräs'}:
                    assert after.quantity == before.quantity
        assert old.design.ingredient_count == recipe.design.ingredient_count
        assert (old.design.vegetarian, old.design.fish) == (recipe.design.vegetarian, recipe.design.fish)
    counts = dict(Counter(g for r in corrected for g in r['groups']))
    assert counts == {'tamarindpasta': 93, 'masa harina': 31, 'citrongräs': 27, 'pärlkorn': 27, 'klibbigt ris': 20}
    if not do_import:
        print({'validated': len(corrected), 'groups': counts})
        return
    manifest_path = ROOT / 'library-manifest.json'
    before_manifest = file_sha(manifest_path)
    (REPORT / 'import.json').write_bytes(encoded(import_pack(path)))
    (REPORT / 'revocations.json').write_bytes(encoded([revoke_recipe(r['previous_id'], r['reason']) for r in corrected]))
    review.write_bytes(encoded({'schema': 'smako-top-five-recipe-review-v1', 'corrected': corrected,
        'group_counts': counts, 'before_manifest_file_sha256': before_manifest,
        'after_manifest_file_sha256': file_sha(manifest_path)}))
    print({'issued': len(corrected), 'original_bytes_preserved': True, 'groups': counts})


def repair_dumpling():
    """Retain the withdrawn intermediate and correct its variant-specific step offset."""
    review_path = REPORT / 'recipe-review.json'
    review = read_json(review_path)
    if review.get('internal_revisions'):
        print({'already_corrected': review['internal_revisions']})
        return
    record = next(r for r in review['corrected'] if r['previous_id'].startswith(
        'smako-mexican-chicken-broth-unfilled-masa-dumplings:') and r['previous_id'].endswith(':extended'))
    current = {identity(r): r for r in current_recipes()}
    intermediate = current[record['runtime_id']]
    original = next(row for path in ROOT.rglob('authoring.json') if OUTPUT not in path.parents
                    for row in read_json(path)['recipes']
                    if ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')) == record['previous_id'])
    row, groups = adapt(original)
    version = intermediate.design.version.split('.')
    row['version'] = '.'.join([*version[:-1], str(int(version[-1]) + 1)])
    reason = ('Variant-specific step-offset correction before integration: retain frozen coriander preparation, '
              'restore the complete chicken broth step and its 74 °C check, and adapt only dough shaping '
              'and dumpling cooking. The intermediate issued bytes are preserved but withdrawn.')
    row['notes'] += ' ' + reason
    vocab = library_vocabulary([intermediate])
    for old in groups:
        name, form, unit, _ = FOODS[old]
        vocab[f'{name}|{form}'] = (unit, [requirement(old)])
    authored = {'schema_version': 'smako-recipe-authoring-v1', 'pack_id': PACK + '-correction-01', 'recipes': [row]}
    pack, readiness = standardize(authored, vocab, reviewed_at='2026-10-28')
    destination = OUTPUT / 'correction-01'
    destination.mkdir(exist_ok=True)
    (destination / 'authoring.json').write_bytes(encoded(authored))
    path = destination / 'standardized.json'
    path.write_bytes(encoded(pack))
    validated = validate_pack_bytes(path.read_bytes())
    assert not validated['rejections'] and not readiness[0]['warnings']
    corrected = validated['recipes'][0]
    assert corrected.ingredients == intermediate.ingredients
    assert any('74 °C' in s for s in corrected.instructions)
    imported = import_pack(path)
    withdrawn = revoke_recipe(identity(intermediate), reason)
    revision = {'previous_id': identity(intermediate), 'runtime_id': identity(corrected),
                'before_content_sha256': intermediate.design.content_sha256,
                'content_sha256': corrected.design.content_sha256, 'reason': reason}
    (REPORT / 'internal-correction.json').write_bytes(encoded({
        'revision': revision, 'import': imported, 'revocation': withdrawn, 'readiness': readiness}))
    record.update(runtime_id=identity(corrected), content_sha256=corrected.design.content_sha256)
    review['internal_revisions'] = [revision]
    review['after_manifest_file_sha256'] = file_sha(ROOT / 'library-manifest.json')
    review_path.write_bytes(encoded(review))
    print(revision)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import', dest='do_import', action='store_true')
    parser.add_argument('--repair-dumpling', action='store_true')
    args = parser.parse_args()
    repair_dumpling() if args.repair_dumpling else main(args.do_import)
