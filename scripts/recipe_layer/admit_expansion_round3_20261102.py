"""Review bounded continuation batches; require full basket receipts before delivery."""
import argparse
import copy
import json
from pathlib import Path

from admit_expansion_round2_20261101 import (
    amount_changes,
    check_process_water,
    mark_process,
    prepend_thaw,
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
OUTPUT = ROOT / 'reviewed-expansion-round3-20261102'
REPORT = Path('docs/reviews/recipe-unblock-round3-20261102')
STAGES = {
    1: {
        'smako-greek-kolokithopita-sot-pumpapaj': 'Söt kokt pumpafyllning omsluts av frasiga filolager. Skild från salt spenat-fetafilo, pumpabåt med äggstanning och sirapsdränkt sönderriven portokalopita.',
        'smako-swedish-angamat-sommargronsaker': 'Bitar av sommargrönsaker i mjölkredd soppa med hela kokspadet; skild från mixad blomkålssoppa, rotmos och mjölksoppa med pasta.',
        'smako-swedish-fiskpudding-ris-mjolk': 'Förkokt vit fisk vänds i mjölkkokt ris och ägg och bakas till skivbar pudding. Skild från fiskfärsbollar, ångad kokoscurrykräm och fiskgratäng med potatismos.',
        'smako-greek-bouyiourdi-feta-paprika': 'Fetaskiva bakas direkt i tomat, paprika och chili, med separat bröd. Skild från rostat bröd med kall feta, bakade ägg i fetatomat och tirokafteris mixade dipp.',
        'smako-italian-frittata-scammaro-aggfri': 'Kokt spaghetti binds utan ägg till en pannstekt kaka med två fasta skorpor och sardell-olivröra. Skild från äggfrittatans ersättare, lös vitlökspasta och råstekt spaghetti assassina.',
        'smako-italian-jota-triestina-surkal-bonor': 'Surkål kokas separat från potatis tills potatisen mjuknat; bönor och potatis mosas delvis i sitt spad före sammanföring. Skild från slät kålsoppa, färsk kålsallad och tomatbaserad minestrone.',
    },
    2: {
        'smako-italian-pallotte-cacio-uova': 'Bröd, lagrad fårhårdost och ägg formas till bollar som bryns och efterkokas i tomatsås. Skild från pressade ströbrödspassatelli i buljong, brödgnocchi och bakade mannagrynskuber.',
    },
    3: {
        'smako-greek-kolokithopita-sot-pumpapaj': 'Samma nya pumpafamilj som steg 1, med valnötter, russin och synligt kanderat apelsinskal. Ingen ytterligare grundrätt räknas. Angela Nicolettous pumpapaj använder sötat apelsinskal: https://www.sbs.com.au/language/greek/en/podcast-episode/sweet-pumpkin-pie-with-ricotta/g5xzo5yrq . Ny dos är egen författarbedömning, inte en färskt-kanderat-faktor.',
        'smako-mexican-coyotas-piloncillo': 'Tunn dubbel smördegskaka utan laminering omsluter torr brun sockerfyllning; skild från jäst concha med sprött tak, mjölkkrämsfylld pasticciotto och öppen smulpaj. Uttrycklig muscovadoversion med stöd för brunt socker och smör hos receptförfattaren: https://www.maricruzavalos.com/coyotas/ .',
    },
}
SELECTED = {1: {'smako-greek-bouyiourdi-feta-paprika': {'simple'},
                'smako-greek-kolokithopita-sot-pumpapaj': {'simple'}},
            3: {'smako-greek-kolokithopita-sot-pumpapaj': {'extended'}}}


def correct(row):
    base, variant = row['base_id'], row['variant_id']
    changes = []
    if base.endswith('kolokithopita-sot-pumpapaj'):
        row['steps'][0]['text'] = 'Skala och kärna ur pumpan, väg den angivna råa ätliga mängden och skär smått. Lägg i kastrull med 35 ml vatten och lock.'
        row['steps'][1]['text'] = 'Sjud under lock cirka tolv minuter tills pumpan kan mosas med en gaffel.'
        row['steps'][2]['text'] += ' Koka bort kvarvarande fritt vatten under omrörning; inget pumpaspad hälls bort.'
        row['steps'][2]['minutes'] += 3
        row['steps'][3]['text'] = 'Bred ut fyllningen tunt och låt svalna femton minuter. Sätt därefter på ugnen i nästa arbetssteg.'
        row['steps'][4]['text'] = 'Sätt ugnen på 190 °C över-/undervärme. ' + row['steps'][4]['text']
        row['steps'][-1]['text'] = 'Låt svalna tio minuter före servering. Vid större sats används flera formar med samma fyllningsdjup. Fördela hela pajen eller pajerna jämnt över det valda portionsantalet.'
        changes.append('Weigh peeled/seeded raw pumpkin; evaporate rather than discard liquid. Count reduction as active work; scale portions without a fixed one-person serving claim.')
        if variant == 'extended':
            rename_ingredient(row, 'apelsinskal', 'kanderade apelsinskal')
            for component in row['components']:
                for item in component['ingredients']:
                    if item['name'] == 'kanderade apelsinskal':
                        item.update(quantity=5, form='as_sold', label='Kanderade apelsinskal, ny dos')
            row['name'] += ' – med kanderat apelsinskal'
            row['steps'][2]['text'] = row['steps'][2]['text'].replace('finrivet apelsinskal', 'finhackade kanderade apelsinskal')
            changes.append('Replace unsupported 1 g fresh zest with a new explicit 5 g candied-orange-peel dose. The original 10 g sugar remains; candied peel is sweeter and is not a raw-zest identity or conversion.')
    elif base.endswith('angamat-sommargronsaker'):
        row['steps'][0]['text'] = 'Ansa grönsakerna och väg rå ätlig mängd efter skalning och putsning. ' + row['steps'][0]['text']
        if variant != 'simple':
            row['steps'][3]['text'] = row['steps'][3]['text'].replace('Sjud försiktigt', 'Tillsätt all färsk eller fryst hackad persilja. Sjud försiktigt')
            row['steps'][3]['uses'].append('persilja')
            row['steps'][4]['text'] = row['steps'][4]['text'].replace(' och hackad persilja', '')
            row['steps'][4]['uses'].remove('persilja')
        if variant == 'extended':
            row['steps'][1]['minutes'] = 16
        row['steps'][3]['text'] += ' Frysta grönsaker och örter ska vara genomhettade; följ längre tillagning på förpackningen om den kräver det. Allt spad behålls.'
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('fyra portioner', 'det valda portionsantalet')
        changes.append('Heat frozen parsley in the soup; retain all cooking liquid. Extended variant records its actual 10+6 active cooking minutes. Serving text follows selected portions.')
    elif base.endswith('fiskpudding-ris-mjolk'):
        row['steps'][2]['text'] = 'Använd helt tinad benfri vit fisk. Kontrollera efter kvarvarande ben och ta bort eventuella sådana. Koka upp 700 ml vatten med all upptiningssaft. Sänk värmen, lägg i fisken och sjud cirka åtta minuter till minst 63 °C i tjockaste delen. Lyft upp fisken och flika den. Kokspadet hälls bort; förlusten är okänd.'
        mark_process(row, 3, ['fisk'], 'drain_after_cooking', 'Fiskens kokspad kasseras; ingen överförings- eller utbytesandel antas.')
        row['steps'][3]['text'] = 'Bred ut risgröt och fisk i två rena grunda skålar, ställ skålarna i kallt vattenbad och låt svalna cirka tjugo minuter. Byt badvatten vid behov; badvattnet ingår inte i maten.'
        row['steps'][4]['text'] = 'Kontrollera att gröt och fisk svalnat till högst 25 °C; kyl vidare vid behov. Sätt ugnen på 190 °C. Knäck äggen, vispa ihop och väg angiven mängd utan skal. ' + row['steps'][4]['text']
        row['steps'][4]['minutes'] += 3
        row['steps'][5]['text'] = 'Baka cirka trettiofem minuter tills puddingen stannat. Kontrollera därefter temperaturen i nästa aktiva arbetssteg. Håll högst fyra centimeters djup även med fler portioner; använd flera formar vid behov.'
        row['steps'][6]['text'] = 'Kontrollera minst 72 °C mitt i varje puddingform och förläng gräddningen vid behov. ' + row['steps'][6]['text']
        row['steps'][6]['minutes'] += 2
        if variant != 'simple':
            row['steps'][6]['text'] = 'Kontrollera minst 72 °C mitt i varje puddingform och förläng vid behov. Koka ärtor och all färsk eller fryst hackad dill i 500 ml vatten minst fem minuter eller längre enligt förpackningen. Häll av noga och vänd ner ärtkomponentens smör, salt och citronjuice. All smörsås serveras.'
            row['steps'][6]['minutes'] += 2
        mark_process(row, 7, ['ärtor'] + (['dill'] if variant != 'simple' else []), 'drain_after_cooking', 'Ärtornas kokvatten kasseras; eventuell dill följer samma okända överföring.')
        if variant == 'extended':
            row['steps'][7]['text'] = 'Väg gurka och urkärnat äpple som rå ätlig mängd och tärna. Använd färsk sköljd gräslök och hacka, eller värm fryst gräslök med 15 ml vatten minst tre minuter enligt förpackningen och låt svalna kort. Vänd all gräslök och dess vätska med gurka, äpple och salladens citronjuice.'
            row['steps'][7]['minutes'] = 10
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('skär i fyra portioner', 'fördela över det valda portionsantalet')
        prepend_thaw(row, 'fisk', 720, 'All upptiningssaft kokas i fiskens pocheringsvatten; det kokspadet kasseras sedan med okänd förlust.')
        for process in row['unmeasured_processes']:
            process['step'] += 2
        changes.append('Plan frozen white-fish thaw; record discarded fish and pea/herb broth as unknown losses. Cool before egg mixing, weigh shelled eggs, actively check baked center, heat frozen herbs and preserve scalable portions.')
    elif base.endswith('bouyiourdi-feta-paprika'):
        row['steps'][0]['text'] = 'Väg paprika efter urkärning och feta utan fri lag. ' + row['steps'][0]['text']
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('Hela formen och brödet är en mellanmålsportion.', 'Fördela all mat och all sky jämnt över det valda portionsantalet; använd flera små formar vid större sats.')
        changes.append('Explicit edible pepper and drained free feta liquid; all oven juices served, multiple shallow forms when scaling.')
    elif base.endswith('frittata-scammaro-aggfri'):
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('med saltet', 'utan salt')
        row['steps'][0]['text'] = 'Väg oliver, kapris och sardeller efter avrinning. ' + row['steps'][0]['text']
        row['steps'][0]['uses'].remove('salt')
        row['steps'][1]['text'] = row['steps'][1]['text'].replace('Spara 150 ml av pastans kokvatten', 'Spara 50 ml vatten från pastakoket')
        mark_process(row, 2, ['spaghetti'], 'drain_after_cooking', 'Stärkelsehaltigt pastavatten kasseras utom den uttryckligen sparade dosen; okänd förlust.')
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('50 ml av det sparade stärkelsevattnet', '50 ml vatten från den sparade dosen pastavatten')
        row['steps'][2]['text'] += ' Rör ner hela den angivna mängden salt i pastan; kokvattnet var osaltat. All persilja är färsk eller fryst hackad och genomhettas under stekningen.' if variant != 'simple' else ' Rör ner hela den angivna mängden salt i pastan; kokvattnet var osaltat.'
        row['steps'][2]['uses'].append('salt')
        row['steps'][3]['text'] += ' Vid annan satsstorlek anpassas pannans yta så kakan är omkring två centimeter tjock; använd flera pannor eller stekomgångar vid större sats. Förläng då den aktiva tiden för extra omgångar.'
        row['steps'][4]['text'] += ' Skrapa med all olja och allt stekfett vid vändningen och serveringen; inget stekfett hälls bort.'
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('Dela i fyra', 'Dela efter det valda portionsantalet')
        changes.append('Retain the same salt dose in the served pasta rather than discarded water; unknown starch loss. Exactly one saved 50 ml portion is scaled, all pan oil retained, pan area follows cake thickness.')
    elif base.endswith('jota-triestina-surkal-bonor'):
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skala och tärna potatisen.', 'Skala potatisen, väg den råa ätliga mängden och tärna.')
        row['steps'][1]['text'] += ' Bönmängden vägs efter avrinning, innan den blandas med potatisen.'
        row['steps'][2]['text'] = 'Väg surkålen efter avrinning. ' + row['steps'][2]['text']
        row['steps'][3]['text'] = 'Sjud surkålen under lock cirka tjugofem minuter tills den är mjuk. Potatisen hålls varm separat; blanda först i nästa arbetssteg.'
        row['steps'][4]['text'] = 'Kontrollera att potatisen är helt mjuk. Häll surkål och allt dess kokspad i den varma bön- och potatisgrytan. ' + row['steps'][4]['text']
        row['steps'][4]['minutes'] += 2
        if variant != 'simple':
            mark_process(row, 5, ['lagerblad'], 'remove_after_infusion', 'Lagerbladen plockas bort före servering; överförd mängd och förlust är okända.')
        if variant == 'extended':
            row['steps'][4]['text'] = row['steps'][4]['text'].replace('Hacka och vänd ner persiljan.', 'Tillsätt all färsk eller fryst hackad persilja före sjudningen och genomhetta minst tre minuter eller längre enligt förpackningen.')
        changes.append('Weigh drained kraut/beans and peeled potato; keep potato separate from acid until soft. Count combining as active work; record removed bay leaves as unknown loss and cook frozen parsley.')
    elif base.endswith('pallotte-cacio-uova'):
        rename_ingredient(row, 'pecorino romano', 'lagrad pecorino')
        row['name'] += ' – med lagrad pecorino'
        row['steps'][0]['text'] = 'Väg hela mängden lagrad pecorino före putsning av eventuell oätlig ostkant, putsa och riv återstoden; fyll inte på ny ost för kanten. Smula färdigbakat bröd med hela dess ätliga skorpa. Knäck ägg, vispa ihop och väg den angivna mängden utan skal. Blanda ost, bröd och ägg' + (' samt färsk eller fryst hackad persilja' if variant != 'simple' else '') + ' till formbar massa. Tillsätt inget extra salt i bollarna.'
        mark_process(row, 1, ['lagrad pecorino'], 'trim_before_cooking', 'Inköpt ostvikt inkluderar eventuell kant; bortputsad mängd är okänd.')
        row['steps'][4]['text'] += ' Efter bryningen lossas allt stekfett med 30 ml vatten och hälls i tomatsåsen; allt fett serveras.'
        row['steps'][5]['text'] += ' Kontrollera flera bollar, även från sista stekomgången.'
        if variant != 'simple':
            row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('Riv basilikan och vänd ner den i tomatsåsen.', 'Tillsätt all färsk eller fryst hackad basilika i tomatsåsen. Sjud minst tre minuter eller längre enligt förpackningen.')
            row['steps'][-1]['minutes'] += 3
        changes.append('Explicit aged-pecorino adaptation at 140 g purchased weight, not a Romano identity alias. Record rind trim, retain frying fat, weigh shelled egg and cook frozen basil. Bread includes its edible crust.')
    elif base.endswith('coyotas-piloncillo'):
        rename_ingredient(row, 'piloncillo', 'mörkt muscovadosocker')
        row['primary'] = 'mörkt muscovadosocker'
        row['name'] = row['name'].replace('piloncillokakor', 'muscovadokakor')
        for component in row['components']:
            if component['id'] == 'fill':
                component['name'] = 'Muscovadofyllning'
            for item in component['ingredients']:
                if item['name'] == 'mörkt muscovadosocker':
                    item['form'] = 'dry'
        row['steps'][2]['text'] = 'Smula sönder alla klumpar i det mörka muscovadosockret och blanda med fyllningens vetemjöl' + (', finhackade valnötter och kanel' if variant == 'extended' else '') + '. Tillsätt inget vatten till fyllningen; den ska vara smulig utan fri vätska före gräddning.'
        row['steps'][3]['text'] = 'Sätt ugnen på 190 °C över-/undervärme. Dela degen i två lika delar per vald portion och kavla varje del mellan bakpapper till en tunn rundel, cirka tio centimeter. Fördela fyllningen jämnt på hälften av rundlarna med fri kant. Använd totalt 2 ml vatten för att fukta kanterna, lägg på lockrundlarna och förslut noga med gaffel. Stick två små ånghål per kaka. Håll kakornas storlek vid större sats; använd fler plåtar eller omgångar.'
        row['steps'][4]['text'] = 'Grädda på bakpapper cirka tjugo minuter tills båda degskivorna är genomgräddade och ytan gyllene. Kontrollera undersidan i nästa aktiva steg; förläng vid behov.'
        row['steps'][-1]['text'] = 'Kontrollera att även undersidan är gräddad och förläng vid behov. Flytta försiktigt kakorna till galler med bakspade. Fördela eventuell utläckt fyllning på samma kakor; fyllningen är mycket het direkt ur ugnen.'
        row['steps'][-1].update(passive=False, minutes=3)
        row['steps'].append({'text': 'Låt svalna minst femton minuter på galler. Servera en kaka per vald portion.', 'uses': ['mörkt muscovadosocker'], 'minutes': 15, 'passive': True, 'after': [6]})
        changes.append('Use the explicit brown-sugar alternative as 18 g dark muscovado per portion, not a piloncillo alias. Preserve walnut/cinnamon differences; scale number of cookies, total sealing water and serve all filling.')
    else:
        raise ValueError('No reviewed correction: ' + base)
    row['version'] = '1.0.1'
    row['notes'] = row.get('notes', '') + ' Innehållsgranskad 2026-11-02; inte provlagad. Produktformer, mängder och avvikelser är dokumenterade i granskningsrapporten.'
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
            pack, _ = standardize({**doc, 'pack_id': f'reviewed-expansion-round3-stage{stage}', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-02')
            authors.append(row)
            native.extend(pack['recipes'])
            records.append({'source_id': ':'.join(original[k] for k in ('base_id', 'version', 'variant_id')),
                'source_file': path.relative_to(SOURCE).as_posix(), 'source_sha256': sha(path.read_bytes()),
                'runtime_id': ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')),
                'content_review': STAGES[stage][base], 'changes': changes,
                'amount_changes': amount_changes(original, row), 'cooking_test': 'not_cooked'})
    assert {r['base_id'] for r in authors} == STAGES[stage].keys()
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': f'reviewed-expansion-round3-stage{stage}', 'recipes': native})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    check_process_water(checked['recipes'])
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    (OUTPUT / f'standardized-stage{stage}.json').write_bytes(raw)
    (OUTPUT / f'authoring-stage{stage}.json').write_bytes(encoded({'schema_version': 'smako-recipe-authoring-v1', 'pack_id': f'reviewed-expansion-round3-stage{stage}', 'recipes': authors}))
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
