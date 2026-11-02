"""Review nine pending variants with explicit ingredients and preparation."""
import argparse
import copy
import json
from pathlib import Path

from admit_expansion_round2_20261101 import (
    amount_changes,
    check_process_water,
    mark_process,
    rename_ingredient,
    sha,
)
from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    pack_diff,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

SOURCE = ROOT / 'incoming/authoring-1000-20261101'
OUTPUT = ROOT / 'reviewed-expansion-round4-20261102'
REPORT = Path('docs/reviews/recipe-unblock-round4-20261102')
STAGES = {
    1: {'smako-greek-magiritsa-lammlever-agg-citron': 'Lever, ris och sallad kokas i soppa med tempererad äggcitron. Uttrycklig ungnötsleverversion med okänd puts- och förvällningsförlust, skild från stekt lever och kycklingavgolemono. Carolina Doriti tillåter nötlever: https://cookout.skai.gr/articles/magiritsa-the-traditional-greek-easter-soup .'},
    2: {'smako-italian-pastiera-napoletana-matvete': 'Mördeg omsluter ricotta, ägg och hela kokta vetekorn; skild från slät ostkaka och gröt. Apelsinblomsvatten mäts i ml. Kanderat apelsinskal är uttryckligt alternativ till citron i utökad version, med stöd hos receptförfattaren: https://www.giallozafferano.com/recipes/pastiera-napoletana-Neapolitan-ricotta-cheese-Easter-pie.html .'},
    3: {
        'smako-italian-focaccia-formaggio-recco-stil': 'Två mycket tunna ojästa degark omsluter mjuk ost; skild från jäst focaccia, pizza och ricottapaj med ägg. Synlig treostversion med ricotta, färskost och mozzarella enligt alternativet i https://www.ica.se/recept/focaccia-di-recco-729881/ . Egen dosering, ingen stracchinoidentitet eller IGP-attest.',
        'smako-greek-bouyiourdi-feta-paprika': 'Utökad medlem av redan antagen familj med smältande gruyère ovanpå feta, tomat och paprika. Inte en ny grundrätt. Författarens alternativ stöds av https://bwydbydbywyd.blogspot.com/2017/03/bouyiourdi.html .'},
}
SELECTED = {3: {'smako-greek-bouyiourdi-feta-paprika': {'extended'}}}


def step(text, uses, minutes, passive=False):
    return {'text': text, 'uses': uses, 'minutes': minutes, 'passive': passive}


def correct(row):
    base, variant = row['base_id'], row['variant_id']
    if 'magiritsa' in base:
        rename_ingredient(row, 'lammlever', 'ungnötslever')
        row['primary'] = 'ungnötslever'
        row['name'] = row['name'].replace('lammlever', 'ungnötslever')
        for c in row['components']:
            for i in c['ingredients']:
                if i['name'] == 'ungnötslever':
                    i.update(form='as_sold', label='Ungnötslever, inköpt vikt före putsning')
        original_steps = copy.deepcopy(row['steps'])
        herbs = ['dill'] + (['persilja'] if variant != 'simple' else [])
        row['steps'] = [
            step('Väg levern före putsning. Ta bort grova hinnor och blodkärl och skär i stora bitar. Koka upp 1800 ml vatten, lägg ner levern och förväll fem minuter. Häll bort spadet; ingen förlustandel antas. Diska redskap som rört rå lever.', ['ungnötslever'], 10),
            step('Låt levern svalna på en ren tallrik så att den går att hantera.', ['ungnötslever'], 10, True),
            {**original_steps[1], 'text': original_steps[1]['text'].replace('Låt leverbitarna svalna på en ren tallrik tills de kan hanteras. ', '') + ' Väg grönsaker efter ansning. Färska eller frysta hackade örter ska tillsättas i det senare koksteget; behåll all vätska från frysta örter.'},
            original_steps[2],
            step('Sjud under lock på låg värme cirka tolv minuter.', ['ungnötslever', 'ris'], 12, True),
            step('Rör längs botten och kontrollera vätskan. Späd vid behov med 100 ml vatten.', ['ungnötslever', 'ris'], 2),
            step('Sjud ytterligare cirka tretton minuter tills riset är mjukt.', ['ungnötslever', 'ris'], 13, True),
            step('Kontrollera minst 72 °C i flera leverbitar. Tillsätt all dill' + (' och persilja' if variant != 'simple' else '') + ' med eventuell upptiningsvätska och koka under omrörning minst tre minuter, eller längre enligt örtproduktens anvisning. Förläng tills ris och grönsaker är mjuka.', ['ungnötslever', 'ris', *herbs], 5),
            {**original_steps[4], 'text': 'Väg upp äggen utan skal och vispa med citronjuicen. Ta grytan från värmen. Vispa ner hett soppspad lite i taget i äggen och rör sedan tillbaka hela redningen i grytan.'},
            step('Värm under ständig omrörning på låg värme till 75 °C utan att stormkoka. Fördela hela soppan jämnt mellan valt antal portioner.' + (' Servera allt uppvägt bröd, inklusive ätlig skorpa, vid sidan.' if variant != 'simple' else ''), ['ägg', 'citronjuice'] + (['bröd'] if variant != 'simple' else []), 5),
        ]
        mark_process(row, 1, ['ungnötslever'], 'trim_before_cooking', 'Inköpt vikt före borttagning av hinnor och blodkärl; utbytet är inte mätt.')
        mark_process(row, 1, ['ungnötslever'], 'drain_after_cooking', 'Förvällningsspadet hälls bort. Näringsöverföring och slutlig vikt är okända.')
        changes = ['480 g purchased young-beef liver replaces 480 g edible lamb liver as an explicit newly authored input, not a yield conversion. Record trimming and discarded broth; heat frozen herbs and preserve active temperature checks and scalable serving text.']
    elif 'pastiera' in base:
        if variant == 'extended':
            rename_ingredient(row, 'kanderat citronskal', 'kanderade apelsinskal')
            row['name'] = row['name'].replace('utökad', 'med kanderat apelsinskal och vanilj')
            row['steps'][5]['text'] = row['steps'][5]['text'].replace('finhackat kanderat citronskal', 'finhackade kanderade apelsinskal')
        row['steps'][0]['text'] += ' Äggmängder avser uppvispat ägg vägt utan skal; väg degens och fyllningens mängder separat.'
        row['steps'][4]['text'] = 'Bred ut veteblandningen tunt i en ren skål och låt svalna till högst 25 °C före äggblandningen. Planera tjugo minuter och förläng vid behov.'
        row['steps'][5]['text'] = 'Kontrollera att veteblandningen är högst 25 °C. Mät apelsinblomsvattnet med graderat millilitermått. ' + row['steps'][5]['text']
        row['steps'][5]['minutes'] += 2
        row['steps'][6]['text'] = 'Sätt ugnen på 175 °C över-/undervärme. Använd en låg pajform cirka tio centimeter per vald portion, eller flera former med motsvarande sammanlagd bottenyta och samma låga fyllningsdjup. Klä med bakpapper. Kavla tre fjärdedelar av degen mellan papper och klä botten och kanten. Fördela fyllningen. Skär resterande deg i remsor och lägg glest korsvis ovanpå. Använd all deg, även kantbitar.'
        row['steps'][7]['text'] = 'Grädda cirka trettio minuter tills mördegen är gyllene och fyllningen stannat. Behåll samma låga fyllningsdjup vid större sats och använd fler formar eller omgångar.'
        row['steps'].insert(8, step('Kontrollera minst 72 °C i mitten av varje paj. Förläng gräddningen vid behov och kontrollera igen. Ta ut formarna.', ['ägg', 'ricotta'], 3))
        row['steps'][-1]['text'] = 'Låt svalna i formarna cirka tjugofem minuter före servering. Fördela hela satsen jämnt mellan valt antal portioner. Kyl snabbt i grunda behållare och förvara vid 4 °C om pajerna ska sparas.'
        mark_process(row, 3, ['matvete'], 'drain_after_cooking', 'Kokvatten från vetet hälls bort; förlust av stärkelse och slutlig serverad vikt är inte mätta.')
        changes = ['Bind orange-blossom water in ml to reviewed existing products. Extended variant uses 10 g candied orange peel, not a citrus identity alias. Retain wheat grains, record drained cooking loss, weigh shelled egg, check cooled filling and baked egg actively, scale pan area and portions.']
    elif 'focaccia-formaggio' in base:
        row['name'] = row['name'].replace('hembakad i Recco-stil', 'Recco-inspirerad med ricotta, färskost och mozzarella')
        row['primary'] = 'ricotta, färskost och mozzarella'
        row['flavor'] = ['tre ostar', 'olivolja']
        component = row['components'][0]
        component['name'] = 'Två tunna degark med tre ostar'
        old = next(i for i in component['ingredients'] if i['name'] == 'stracchino')
        index = component['ingredients'].index(old)
        component['ingredients'][index:index+1] = [
            {**old, 'name': name, 'label': label, 'form': form, 'quantity': quantity}
            for name, label, form, quantity in [('ricotta', 'Ricotta', 'as_sold', 140),
                ('färskost', 'Naturell färskost', 'as_sold', 130),
                ('mozzarella', 'Mozzarella, vägd avrunnen', 'preserved_drained', 130)]]
        for s in row['steps']:
            s['uses'] = [x for x in s['uses'] if x != 'stracchino']
        row['steps'][2]['uses'] += ['ricotta', 'färskost', 'mozzarella']
        row['steps'][2]['text'] = 'Värm ugnen till 250 °C med plåten i. Låt mozzarellan rinna av och väg den angivna avrunna mängden. Riv eller finfördela den och blanda med hela ricottan och färskosten; ingen ostvätska från dessa två produkter hälls bort. Dela degen i två lika delar. Kavla mellan bakpapper och dra till mycket tunna ark, cirka en millimeter. Använd motsvarande plåtyta vid större sats, eventuellt flera plåtar. Fördela ostblandningen på det undre arket, täck med det andra och förslut kanterna. Gör små ångöppningar och pensla med återstående brödolja. Använd allt degmaterial. Välj bakpapper godkänt för 250 °C eller lätt oljad metallplåt med olja från receptets mängd.'
        row['steps'][2]['minutes'] += 5
        row['steps'][3]['text'] = 'Grädda på het plåt cirka fjorton minuter tills degen fått bruna blåsor och osten bubblar. Håll samma tunna deg och fyllningsdjup i större satser; grädda i flera omgångar vid behov.'
        row['steps'].insert(4, step('Lyft försiktigt ett hörn och kontrollera att botten är gräddad; förläng vid behov. Ta ut plåten.', ['vetemjöl', 'ricotta', 'färskost', 'mozzarella'], 3))
        row['steps'][-1]['text'] = 'Väg tomaten efter ansning och skär den. Blanda salladens råvaror med dess olja och balsamvinäger. Skär brödet i portionsbitar och servera hela brödet och salladen jämnt fördelat mellan valt antal portioner.'
        if variant != 'simple':
            row['steps'][-1]['text'] += ' Skölj rucolan enligt förpackningen, låt ytvatten rinna av och använd hela uppvägda blad inklusive ätliga stjälkar. Väg gurkan efter ansning och skär den.'
        if variant == 'extended':
            salad = next(c for c in row['components'] if c['id'] == 'sallad')
            basil = next(i for i in salad['ingredients'] if i['name'] == 'basilika')
            salad['ingredients'].remove(basil)
            component['ingredients'].append(basil)
            row['steps'][2]['uses'].append('basilika')
            row['steps'][2]['text'] += ' Blanda all färsk eller fryst hackad basilika i ostfyllningen före gräddningen; behåll dess vätska.'
            row['steps'][4]['text'] += ' Kontrollera att hela ostfyllningen med basilikan är genomhet och når minst 75 °C, samt följ örtproduktens anvisning.'
            row['steps'][4]['uses'].append('basilika')
            row['steps'][-1]['uses'].remove('basilika')
            row['steps'][-1]['text'] += ' Väg bönorna avrunna och rödlöken skalad. Skiva löken tunt och vänd ner båda i salladen.'
        changes = ['Explicit three-cheese version: 140 g ricotta, 130 g plain cream cheese and 130 g drained mozzarella replace 400 g stracchino. New authored quantities, no identity alias. Scale thin dough area; keep all dough and oil; heat frozen basil in filling and use reviewed rucola whole leaves.']
    elif 'bouyiourdi' in base:
        rename_ingredient(row, 'kasseri', 'gruyère')
        row['name'] = row['name'].replace('utökad', 'med gruyère och bröd')
        row['steps'][0]['text'] = 'Väg gruyèren som inköpt bit före putsning. Skär bort eventuell oätlig kant och riv resten; inget bestämt utbyte antas. ' + row['steps'][0]['text'].replace('grovriven kasseri', 'den rivna gruyèren') + ' Väg tomat och paprika efter ansning. Anpassa formens yta till portionerna och behåll samma låga lager.'
        row['steps'][0]['minutes'] += 2
        row['steps'][-1]['text'] = 'Kontrollera att grönsakerna är mjuka och förläng gräddningen vid behov. Skär allt uppvägt bröd inklusive ätlig skorpa i bitar. Fördela hela formen och brödet jämnt mellan valt antal mellanmålsportioner.'
        mark_process(row, 1, ['gruyère'], 'trim_before_cooking', 'Inköpt ostvikt före eventuell oätlig kant; ingen andel eller serverad näring antas.')
        changes = ['Explicit gruyere alternative: 20 g purchased cheese before optional rind removal, no kasseri alias or assumed rind yield. Scale dish area and bread servings.']
    else:
        raise ValueError('No reviewed correction: ' + base)
    for n, s in enumerate(row['steps']):
        s['after'] = [n] if n else []
    row['version'] = '1.0.1'
    row['notes'] = 'Innehållsgranskad 2026-11-02; inte provlagad. Egen receptanpassning med råvaruformer, inköpsmängder, portionsskalning och okända processförluster enligt granskningsrapporten. Ägg anges utan skal; grönsaker vägs ansade där formen är raw_edible.'
    return changes


def build(stage):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    if (REPORT / f'import-stage{stage}.json').exists():
        raise ValueError('Issued stages are immutable; create a successor')
    vocabulary = library_vocabulary(current_recipes())
    authors, native, records = [], [], []
    for path in sorted(SOURCE.glob('*/source/paket/*.json')):
        doc = json.loads(path.read_bytes())
        for original in doc['recipes']:
            base = original['base_id']
            if base not in STAGES[stage]:
                continue
            selected = SELECTED.get(stage, {}).get(base)
            if selected is not None and original['variant_id'] not in selected:
                continue
            row = copy.deepcopy(original)
            changes = correct(row)
            pack, _ = standardize({**doc, 'pack_id': f'reviewed-expansion-round4-stage{stage}', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-02')
            authors.append(row)
            native.extend(pack['recipes'])
            records.append({'source_id': ':'.join(original[k] for k in ('base_id', 'version', 'variant_id')),
                'source_file': path.relative_to(SOURCE).as_posix(), 'source_sha256': sha(path.read_bytes()),
                'runtime_id': ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')),
                'content_review': STAGES[stage][base], 'changes': changes,
                'amount_changes': amount_changes(original, row), 'cooking_test': 'not_cooked'})
    assert {r['base_id'] for r in authors} == STAGES[stage].keys()
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': f'reviewed-expansion-round4-stage{stage}', 'recipes': native})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    check_process_water(checked['recipes'])
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    (OUTPUT / f'standardized-stage{stage}.json').write_bytes(raw)
    (OUTPUT / f'authoring-stage{stage}.json').write_bytes(encoded({'schema_version': 'smako-recipe-authoring-v1', 'pack_id': f'reviewed-expansion-round4-stage{stage}', 'recipes': authors}))
    (REPORT / f'recipe-review-stage{stage}.json').write_bytes(encoded({'reviewed_bases': len(STAGES[stage]), 'reviewed_variants': len(records), 'pack_sha256': sha(raw), 'recipes': records}))
    print({'stage': stage, 'variants': len(records)}, flush=True)


def admit(stage, qualification=None):
    target = OUTPUT / f'standardized-stage{stage}.json'
    raw = target.read_bytes()
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    expected = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
    assert review['pack_sha256'] == sha(raw)
    assert {r['runtime_id']: r['content_sha256'] for r in review['recipes']} == expected
    receipt_path = REPORT / f'import-stage{stage}.json'
    if qualification:
        probe = json.loads(qualification.read_bytes())
        rows = probe['modes']['estimated']['recipes']
        assert probe['pack_sha256'] == sha(raw) and not probe['input_only']
        assert len(rows) == len(expected) and {r['id'] for r in rows} == expected.keys()
        assert all(r['status'] == 'verified' and r['audit']['passed'] for r in rows)
        receipt = json.loads(receipt_path.read_bytes())
        assert receipt['pack_sha256'] == sha(raw)
        assert probe['scope']['manifest_sha256'] == receipt['after_manifest_sha256']
        receipt.update(qualification_sha256=sha(qualification.read_bytes()), basket_status='verified_estimated')
        receipt_path.write_bytes(encoded(receipt))
        (REPORT / f'qualification-stage{stage}.json').write_bytes(qualification.read_bytes())
        print({'stage': stage, 'qualified': len(expected)}, flush=True)
        return
    diff = pack_diff(checked)
    assert {r['status'] for r in diff} <= {'new_recipe', 'new_variant'}, diff
    assert {r['id'] for r in diff} == expected.keys()
    before = (ROOT / 'library-manifest.json').read_bytes()
    result = import_pack(target, accepted_ids=set(expected))
    after = (ROOT / 'library-manifest.json').read_bytes()
    assert import_pack(target, accepted_ids=set(expected))['published_file'] == result['published_file']
    assert (ROOT / 'library-manifest.json').read_bytes() == after
    receipt_path.write_bytes(encoded({'before_manifest_sha256': sha(before), 'after_manifest_sha256': sha(after),
        'pack_sha256': sha(raw), 'basket_status': 'pending_local_qualification', 'idempotent_reimport': True, 'result': result}))
    print({'stage': stage, 'imported': len(expected)}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=int, choices=STAGES, required=True)
    parser.add_argument('--import-reviewed', action='store_true')
    parser.add_argument('--qualifying-report', type=Path)
    args = parser.parse_args()
    if args.qualifying_report or args.import_reviewed:
        admit(args.stage, args.qualifying_report)
    else:
        build(args.stage)
