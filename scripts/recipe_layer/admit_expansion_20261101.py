"""Issue the explicitly reviewed first expansion families; preserve ZIP originals."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

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
OUTPUT = ROOT / 'reviewed-expansion-20261101'
REPORT = Path('docs/reviews/recipe-unblock-20261101')
BASES = {
    'smako-greek-fasolakia-ladera': 'Frysta gröna bönor och potatis långsjuds i tomat och olivolja; skild från snabbstekta bönrätter.',
    'smako-italian-pasta-pesto-genovese': 'Rå färsk basilikapesto med pinjenötter, parmesan och olivolja; inte en generell basilikapasta.',
    'smako-italian-bagna-cauda': 'Varm sardell- och vitlöksdipp med råa/kokta grönsaker och bröd; mjölken kokas in och hela såsen serveras.',
    'smako-italian-passatelli-buljong': 'Pressade strängar av ströbröd, parmesan och ägg i grönsakssoppa; inte pasta eller fyllda degknyten.',
    'smako-italian-testaroli-basilika': 'Gräddade mjölpannkakor skärs till romber, mjukas i hett vatten och vänds med basilikasås; annan metod än pasta.',
    'smako-greek-fasolada': 'Vit bönsoppa med selleri/tomat och avslutande olivolja; inte ribollitas kål och inarbetade bröd.',
    'smako-greek-kleftiko-lamm': 'Lamm och potatis ångbakas länge i slutet paket och bryns sedan öppet; grytstycke är uttryckligt.',
    'smako-greek-sofrito-korfu': 'Mjölvända tunna nötskivor bräseras i vitlöksvinäger och persilja; färdigskivad produkt har explicit hantering.',
    'smako-italian-lasagne-bolognese': 'Torra lasagneplattor varvas med långkokt ragù och separat béchamel; ingen tidigare sådan bas.',
    'smako-italian-pasta-puttanesca': 'Tomatsås med avrunna sardeller, kapris och oliver; skild från befintliga sardinpastor.',
    'smako-italian-pasta-sarde-fankal': 'Siciliansk fänkåls-/russin-/pinjenötssås med sardiner; skild från bibliotekets tomatbaserade sardinpasta.',
    'smako-swedish-plommonspackad-flaskkarre': 'Benfri karré späckas med katrinplommon, långsteks och serveras med hela skyn och potatis.',
    'smako-swedish-bruna-bonor-flask': 'Torra bruna bönor blötläggs och kokas mjuka före sirap/ättika; fläskets fett serveras uttryckligen.',
    'smako-mexican-mazapan-cacahuate': 'Rostade osaltade jordnötter och florsocker pressas utan tillagning; inte marsipan, nötkräm eller bakad kaka.',
    'smako-greek-boureki-hania': 'Tunna zucchini-/potatislager med ricotta och feta; ingen pajdeg, äggstanning eller bönfyllning.',
    'smako-greek-alevropita': 'Tunn mjölk-/mjöl-/äggsmet i het oljad form med feta; skild från fyllda filo- och potatispajer.',
    'smako-swedish-drommar': 'Små vaniljkakor med hjorthornssalt; explicit precisionsvåg, genomgräddning och kall servering.',
}
SECOND_STAGE = {'smako-greek-fasolakia-ladera', 'smako-italian-pasta-pesto-genovese',
    'smako-italian-bagna-cauda', 'smako-italian-passatelli-buljong', 'smako-italian-testaroli-basilika'}
THIRD_STAGE = {
    'smako-greek-youvarlakia-avgolemono': 'Ris sväller inne i färsbullar som sjuds i soppan; tempererad ägg-citronredning. Skild från kyckling-/kronärtskocksavgolemono.',
    'smako-greek-tomatokeftedes': 'Tomat inklusive saft bildar mjölsmeten till tunna pannstekta fritters, med uppmätt stekolja; inte ett frityrbad.',
    'smako-mexican-pan-de-elote': 'Mixad kokt majs och sötad kondenserad mjölk bildar äggsatt kaka utan vetemjöl; inte majsgröt eller pannkaka.',
    'smako-indian-chicken-cafreal': 'Kyckling marineras i koriander-vinägerpasta som sedan kokas helt med köttet; skild från tomat- och yoghurtcurryer.',
    'smako-thai-pad-woon-sen': 'Blötlagda glasnudlar wokas i två omgångar med ägg och strimlade grönsaker; skild från risnudel- och äggnudelrätter.',
    'smako-swedish-kanelbullar': 'Jäst vetedeg rullas med separat kanel-smörfyllning och jäser igen; skild från kakor och friterad jästdeg.',
    'smako-mexican-capirotada': 'Bröd lagras med ost/russin och absorberar kanel-muscovadolag vid ugnsbakning; ingen äggstanning.',
    'smako-mexican-conchas': 'Söt jästbulle med separat mönstrat kakdegsskal; skild från sirapsindränkt baba och friterade bullar.',
    'smako-thai-ma-hor': 'Klibbig fläsk-jordnötsfyllning läggs på ananas; skild från äggnätspaket. Fryst ananas får uttrycklig upptining och all saft används.',
    'smako-indian-thalipeeth-rostade-mjol': 'Torrrostade kikärts-/vetemjöl blir utplattade lökbröd, inte pannkakssmet; mjölanpassningen är synlig i namnet.',
    'smako-indian-gajar-halwa': 'Riven morot sjuds länge med mjölk till kompakt morotsmassa; skild från mjölkfudge.',
    'smako-indian-akki-rotti': 'Oskållad rismjölsdeg med lök trycks ut i kall panna och steks; skild från bibliotekets skållade, utkavlade risbröd.',
    'smako-swedish-kolbulle': 'Mjöl-vattensmet utan ägg/mjölk steks med fläsk och sparat fett i fyra omgångar; skild från raggmunk och äggakaka.',
    'smako-swedish-havreflarn': 'Tunn havre-smörsmet flyter ut till spröda kakor; hallonen i tillbehöret kokas och kyls uttryckligen.',
    'smako-thai-khai-yat-sai': 'Sammanhängande genomstekt tunn omelett viks runt varm fläsk-tomatfyllning; inte bibliotekets glesa äggnät.',
}
BASES.update(THIRD_STAGE)
FOURTH_STAGE = {
    'smako-swedish-wallenbergare': 'Kall emulsion av kalvfärs, äggula och grädde paneras tunt; skild från vanliga färsbiffar. Granskad äggseparering, hela steksmöret och kokta lingon.',
    'smako-swedish-biff-greta': 'Snabbstekt mört nötkött binds i senap-äggula; skild från separat ägg till pytt. Separering och äggblandningens genomhettning är uttryckliga.',
    'smako-swedish-aggakaka': 'Ägg-mjölksmet får först tjockna i panna, vänds hel och bakas färdig; skild från kolbulle/raggmunk. Kokta lingon ersätter den råa bärhanteringen.',
    'smako-swedish-mandelmusslor': 'Tunnt pressade mandelmördegsskal fylls efter avsvalning; skild från gräddad mandelkrämspaj. Frysta hallon kokas till synligt angiven kompott.',
    'smako-italian-spaghetti-assassina': 'Rå spaghetti bryns och absorberar tomatbuljong i pannan; skild från kokt pasta med tomatsås. Specifik pastaform och färsk basilika krävs.',
}
BASES.update(FOURTH_STAGE)
FIFTH_STAGE = {
    'smako-swedish-flygande-jacob': 'Kyckling-banan-gräddgratäng med jordnötter och egen tomatpuré-chilisås; skild från vanliga kycklinggratänger. Kycklingen ugnsbakas med all sky kvar.',
    'smako-swedish-stuvade-makaroner': 'Gammaldags makaroner sjuds direkt i mjölken till stuvning; skild från kokt pasta med separat mjölksås. Gurksalladens dressing serveras.',
    'smako-mexican-molletes': 'Öppet rostat bröd med tjock mosad svartbönskräm och gratinerad ost; skild från skinktoast. Koriandern genomhettas i bönkrämen.',
    'smako-greek-bourdeto': 'Fisk sjuds i långsam lök-paprikasås utan tomat; skild från tomatfiskgryta. Upptining och all fisksaft ingår uttryckligen.',
}
BASES.update(FIFTH_STAGE)


def prepend_steps(row, steps):
    for step in row['steps']:
        step['after'] = [n + len(steps) for n in step.get('after', [])] or [len(steps)]
    row['steps'][:0] = steps


def correct(row, vocabulary):
    changes = []
    base = row['base_id']
    if base in FIFTH_STAGE:
        if base.endswith('flygande-jacob'):
            row['steps'][0]['text'] = 'Sätt ugnen på 200 °C över-/undervärme. Skär kycklingen i jämnstora bitar och lägg i gratängformen med gratängens salt och 50 ml vatten. Täck formen med lock eller folie.'
            row['steps'][1]['text'] = 'Ugnsbaka kycklingen cirka 25 minuter till minst 74 °C i de tjockaste bitarna. Ta av locket och behåll all sky i samma form till gratängen; inget avkok hälls bort.'
            row['steps'][1]['minutes'] = 25
            changes.append('Bake chicken in its gratin dish with all salt and juices retained; replace discarded poaching liquid and increase this passive step from 12 to 25 minutes.')
        if base.endswith('stuvade-makaroner'):
            for c in row['components']:
                for item in c['ingredients']:
                    if item['name'] == 'pasta':
                        item['requirements'] = ['pack:stewing_macaroni']
            for step in row['steps']:
                step['text'] = step['text'].replace('Rör ner makaroner och salt', 'Rör ner gammaldags idealmakaroner och salt')
                step['text'] = step['text'].replace('den avrunna dillgurkan', 'dillgurksalladen med hela sin dressing, serverad i separata skålar')
                if step['text'].startswith('Skär falukorven'):
                    step['text'] += ' Fördela även steksmöret mellan portionerna.'
            changes.append('Require reviewed long-cooking macaroni shape; serve the cucumber dressing and frying butter instead of inventing discarded fractions.')
        if base.endswith('molletes') and row['variant_id'] == 'extended':
            for step in row['steps']:
                if step['text'].startswith('Sätt ugnen'):
                    step['text'] += ' Rör ner den frysta hackade koriandern i bönkrämen och genomhetta enligt förpackningen.'
                    step['uses'].append('koriander')
                    step['minutes'] += 2
                if step['text'].startswith('Finhacka tomaten'):
                    step['text'] = step['text'].replace('tomaten, löken och koriandern', 'tomaten och löken')
                    step['uses'].remove('koriander')
            changes.append('Explicitly move frozen coriander into the heated bean spread; the tomato-onion salsa stays fresh.')
        if base.endswith('bourdeto'):
            for step in row['steps']:
                step['text'] = step['text'].replace('Torka fisken och kontrollera att inga ben finns kvar.',
                    'Använd upptinad benfri fiskfilé och kontrollera att inga ben finns kvar. Spara all upptiningssaft till såsen.')
                step['text'] = step['text'].replace('häll i 400 ml vatten.', 'häll i 400 ml vatten samt all upptiningssaft från fisken.')
                if 'upptiningssaft från fisken' in step['text']:
                    step['uses'].append('fisk')
                step['text'] = step['text'].replace('med 1500 ml vatten och potatisdelens salt', 'med 1500 ml vatten utan salt')
                if step['text'].startswith('Skala potatisen'):
                    step['uses'].remove('salt')
                if step['text'].startswith('Servera huvudrätten'):
                    step['text'] = 'Fördela potatisdelens salt över den kokta potatisen. ' + step['text']
                    step['uses'].extend(['potatis','salt'])
            prepend_steps(row, [
                {'text': 'Väg upp den frysta benfria fiskfilén. Lägg i ett täckt kärl i kylskåp och behåll all vätska.',
                 'uses':['fisk'],'minutes':1,'after':[]},
                {'text': 'Tina fisken helt i kylskåp enligt förpackningen. Planera 12 timmar och förläng vid behov tills ingen iskärna återstår. All upptiningssaft ska hettas upp i såsen.',
                 'uses':['fisk'],'minutes':720,'passive':True,'after':[1]}])
            changes.append('Explicit frozen-fish thaw with all juice cooked in the sauce; potato salt added after cooking so no salt-absorption fraction is assumed.')
    if base in FOURTH_STAGE:
        names = {i['name'] for c in row['components'] for i in c['ingredients']}
        if 'äggula' in names:
            from app.services.egg_preparation import OPERAND

            for component in row['components']:
                for item in component['ingredients']:
                    if item['name'] == 'äggula':
                        item['requirements'] = list(dict.fromkeys([*vocabulary['äggula|raw_edible'][1], OPERAND]))
            prepend_steps(row, [{'text': 'Knäck rena hönsägg och separera gula och vita utan tillsatser. Väg den råa gulan utan skal till receptets angivna gram. Inköpets utbytesförhållande är en populationsuppskattning; komplettera vid för litet faktiskt utbyte och bokför uppmätt insats, gula och vita. Oanvänd vita är en separat rest. Håll delarna kylda och följ förpackningens hantering; ingen hållbarhet är fastställd här.',
                'uses': ['äggula'], 'minutes': 3, 'after': []}])
            changes.append('Reuse reviewed egg-separation operand, three active minutes and measured separate leftovers; never assume exact yield.')
        if 'lingon' in names:
            for step in row['steps']:
                step['text'] = step['text'].replace('Rör ihop lingon och socker i en skål.', '')
                step['text'] = step['text'].replace('Rör ihop lingon och socker.', '')
                step['text'] = step['text'].replace(' och låt lingonen tina om de är frysta', '')
                step['text'] = step['text'].replace(' och lingonen tina vid behov', '')
                step['text'] = step['text'].replace('Följ eventuella upphettningskrav på bärförpackningen.', '')
                step['text'] = step['text'].replace('Följ bärförpackningens eventuella upphettningsanvisning.', '')
                step['text'] = step['text'].replace('rårörda lingon', 'kokta sockrade lingon')
            prepend_steps(row, [
                {'text': 'Lägg frysta lingon och allt bärsocker i en kastrull med 20 ml vatten. Koka upp under omrörning och koka minst en minut, eller längre enligt förpackningen. Behåll alla bär och all saft; detta tillbehör är kokta sockrade lingon.',
                 'uses': ['lingon', 'strösocker'], 'minutes': 5, 'after': []},
                {'text': 'Häll lingonen i en grund skål och låt svalna cirka 20 minuter. Ställ sedan kallt tills maten serveras.',
                 'uses': ['lingon'], 'minutes': 20, 'passive': True, 'after': [1]}])
            changes.append('Replace ambiguous twenty-minute berry thaw with explicit cooking and cooling of all frozen lingonberries and juice; label the cooked accompaniment.')
        if base.endswith('wallenbergare'):
            for step in row['steps']:
                step['text'] = step['text'].replace('Följ eventuella upphettningskrav på bärförpackningen.', '')
                if step['text'].startswith('Bryn biffarna'):
                    step['text'] += ' Häll med allt steksmör i ugnsformen och servera det till biffarna och purén.'
            changes.append('Serve all frying butter and pan juices with the patties and purée.')
        if base.endswith('biff-greta') and 'rödbeta' in names:
            for step in row['steps']:
                step['text'] = step['text'].replace('Tvätta rödbetorna och lägg dem', 'Skala och tvätta rödbetorna, väg den ätliga mängden och lägg dem')
                step['text'] = step['text'].replace('skala och tärna rödbetorna', 'tärna de redan skalade rödbetorna')
            changes.append('Weigh edible raw beetroot after peeling, not gross unpeeled weight followed by unmodelled skin loss.')
        if base.endswith('mandelmusslor'):
            for step in row['steps']:
                step['text'] = step['text'].replace('Skölj och torka hallonen. ', '')
                step['text'] = step['text'].replace('grädde och hallon', 'grädde och den kalla hallonkompotten')
            prepend_steps(row, [
                {'text': 'Koka de uppvägda frysta hallonen med 10 ml vatten under omrörning minst en minut. Behåll all frukt och saft som kompott.',
                 'uses': ['hallon'], 'minutes': 4, 'after': []},
                {'text': 'Häll kompotten i en grund skål, låt svalna 15 minuter och kyl sedan tills den är helt kall innan skalen fylls.',
                 'uses': ['hallon'], 'minutes': 15, 'passive': True, 'after': [1]}])
            row['name'] = row['name'].replace('grädde och bär', 'grädde och hallonkompott')
            changes.append('Frozen raspberries are boiled with all juice retained, cooled and served as explicitly named compote.')
        if base.endswith('spaghetti-assassina'):
            for component in row['components']:
                for item in component['ingredients']:
                    if item['name'] in {'pasta', 'basilika'}:
                        item['requirements'] = ['pack:spaghetti' if item['name'] == 'pasta' else 'pack:basil']
            changes.append('Require spaghetti shape and fresh basil; ordinary identity and product gates still apply.')
    if base.endswith('ma-hor'):
        prepend_steps(row, [
            {'text': 'Lägg de uppvägda frysta ananasbitarna i en täckt skål i kylskåp. Spara all saft i skålen.',
             'uses': ['ananas'], 'minutes': 1, 'after': []},
            {'text': 'Tina ananasen helt i kylskåp enligt förpackningen. Planera 12 timmar; förläng vid behov tills ingen iskärna återstår.',
             'uses': ['ananas'], 'minutes': 720, 'passive': True, 'after': [1]}])
        for step in row['steps']:
            step['text'] = step['text'].replace('Skär ananasen i sex tjocka munsbitar med plan yta.',
                'Forma de tinade ananasbitarna till sex munsbitar med stabil plan yta; fördela alla bitar och småbitar mellan dem.')
            step['text'] = step['text'].replace('med 20 ml vatten.', 'med 20 ml vatten och all upptiningssaft från ananasen.')
            if step['text'].startswith('Stek fläskfärsen'):
                step['uses'].append('ananas')
            if 'Blanda i jordnötter och koriander' in step['text']:
                step['text'] += ' Fryst hackad koriander läggs i direkt och värms i hela fyllningen enligt förpackningen innan den tas från värmen.'
                step['minutes'] += 2
        changes.append('Frozen edible pineapple: active setup plus 12-hour refrigerated thaw; all juice cooks into the filling. Frozen coriander is heated before serving.')
    if base.endswith('chicken-cafreal'):
        row['steps'][0]['text'] += ' Fryst hackad koriander kan mixas direkt; hela pastan hettas senare upp med kycklingen.'
        changes.append('Explicit handling of the reviewed frozen coriander in the fully heated marinade.')
    if base.endswith('pad-woon-sen'):
        row['steps'][0]['text'] = 'Låt glasnudlarna ligga i vatten cirka 10 minuter eller enligt paketet tills de är böjliga men inte mosiga.'
        prepend_steps(row, [{'text': 'Lägg glasnudlarna i en skål och häll på 1500 ml vatten.',
                            'uses': ['glasnudlar'], 'minutes': 1, 'after': []}])
        changes.append('Separate one active setup minute from the preserved ten-minute noodle soak.')
    if base.endswith(('pasta-pesto-genovese', 'testaroli-basilika')):
        for part in row['components']:
            for item in part['ingredients']:
                if item['name'] == 'basilika':
                    item['requirements'] = list(dict.fromkeys([*item.get('requirements', []), 'pack:basil']))
        changes.append('Require fresh basil for the unheated sauce; frozen basil is not silently substituted.')
    for step in row['steps']:
        text = step['text']
        if base.endswith('sofrito-korfu') and text.startswith('Skär nötinnanlåret'):
            step['text'] = text.replace('Skär nötinnanlåret i 5–7 mm tjocka skivor tvärs fibrerna.',
                'Använd färdigskivad lövbiff av nötinnanlår. Dela endast mycket stora skivor så att de ryms i grytan; skivorna ska inte skäras tjockare.')
            changes.append('Use the reviewed sliced inner-round product, not a fictional whole cut.')
        if base.endswith('lasagne-bolognese'):
            step['text'] = step['text'].replace('finriven parmesan', 'färdigriven parmesan')
        if base.endswith('passatelli-buljong') and text.startswith('Finriv parmesan'):
            step['text'] = text.replace('Finriv parmesan', 'Mixa den färdigrivna parmesanen finare')
            step['minutes'] += 1
            changes.append('Finely grind reviewed grated Parmesan for the dough; add one active minute.')
        if base.endswith('pasta-pesto-genovese'):
            step['text'] = step['text'].replace('finriven parmesan', 'färdigriven parmesan')
        if base.endswith('testaroli-basilika'):
            step['text'] = step['text'].replace('Riv och rör ner parmesan', 'Rör ner färdigriven parmesan')
        if base.endswith('bruna-bonor-flask') and text.startswith('Servera bönstuvningen'):
            step['text'] += ' Fördela även allt stekfett över bönorna och fläsket; inget stekfett räknas som bortkastat.'
            changes.append('Serve retained pork frying fat; no invented loss fraction.')
        if base.endswith('pasta-puttanesca') and text.startswith('Hacka vitlök och sardeller'):
            step['text'] = 'Låt sardellerna rinna av och väg fiskfiléerna utan burkens fria olja till angiven mängd. ' + text
            changes.append('Explicitly weigh drained sardells; 43 g drained per reviewed 80 g package.')
        if base.endswith('pasta-sarde-fankal') and text.startswith('Hacka sardeller'):
            step['text'] = 'Låt sardellerna rinna av och väg dem utan burkens fria olja. ' + text
            changes.append('Explicit drained sardell handling.')
    if base.endswith('alevropita'):
        for step in row['steps']:
            step['after'] = [n + 1 for n in step.get('after', [])] or [1]
        row['steps'][0]['text'] = 'Låt ugnen och den oljade formen bli ordentligt varma vid 220 °C, cirka 15 minuter.'
        row['steps'].insert(0, {'text': 'Sätt ugnen på 220 °C. Häll hälften av olivoljan i metallformen och ställ in den.',
            'uses': ['olivolja'], 'minutes': 2, 'after': []})
        changes.append('Two active setup minutes added before preserved 15-minute oven preheat.')
    row['version'] = '1.0.1'
    row['notes'] = row.get('notes', '') + ' Innehållsgranskad 2026-11-01 med produktform och mängdenhet; inte provlagad. Alla ursprungliga receptmängder bevarade.'
    return changes


def main(do_import=False):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    vocabulary = library_vocabulary(current_recipes())
    authors, recipes, records = [], [], []
    for path in sorted(SOURCE.glob('*/source/paket/*.json')):
        doc = json.loads(path.read_bytes())
        for original in doc.get('recipes', []):
            if original['base_id'] not in BASES:
                continue
            row = copy.deepcopy(original)
            changes = correct(row, vocabulary)
            pack, _ = standardize({**doc, 'pack_id': 'reviewed-expansion-20261101', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-01')
            checked = validate_pack_bytes(encoded(pack))
            assert not checked['rejections'], checked['rejections']
            recipe = checked['recipes'][0]
            authors.append(row)
            recipes.extend(pack['recipes'])
            records.append({'source_id': ':'.join(original[k] for k in ('base_id','version','variant_id')),
                'source_file': path.relative_to(SOURCE).as_posix(), 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'runtime_id': identity(recipe), 'content_sha256': recipe.design.content_sha256,
                'content_review': BASES[row['base_id']], 'changes': changes, 'amounts_preserved': True,
                'cooking_test': 'not_cooked'})
    assert {r['base_id'] for r in authors} == BASES.keys()
    (OUTPUT / 'authoring.json').write_bytes(encoded({'schema_version':'smako-recipe-authoring-v1',
        'pack_id':'reviewed-expansion-20261101','recipes':authors}))
    target = OUTPUT / 'standardized.json'
    issued = []
    for stage in (1, 2, 3, 4, 5):
        selected = [r for r in recipes if (5 if r['design']['base_id'] in FIFTH_STAGE else
                    4 if r['design']['base_id'] in FOURTH_STAGE else
                    3 if r['design']['base_id'] in THIRD_STAGE else
                    2 if r['design']['base_id'] in SECOND_STAGE else 1) == stage]
        path = OUTPUT / f'standardized-stage{stage}.json'
        path.write_bytes(encoded({'schema_version':'smako-meal-pack-v1','pack_id':'reviewed-expansion-20261101','recipes':selected}))
        checked = validate_pack_bytes(path.read_bytes())
        assert not checked['rejections'], checked['rejections']
        issued.extend(checked['recipes'])
    actual = {identity(r):r for r in issued}
    for record in records:
        record['content_sha256'] = actual[record['runtime_id']].design.content_sha256
    target.write_bytes(encoded({'schema_version':'smako-meal-pack-v1','pack_id':'reviewed-expansion-20261101',
        'recipes':[r.model_dump(mode='json') for r in issued]}))
    report = {'reviewed_variants':len(records),'reviewed_bases':len(BASES),'recipes':records}
    (REPORT / 'recipe-review.json').write_bytes(encoded(report))
    if do_import:
        before = (ROOT / 'library-manifest.json').read_bytes()
        checked = validate_pack_bytes(target.read_bytes())
        diff = pack_diff(checked)
        assert {r['status'] for r in diff} <= {'unchanged', 'new_recipe'}, diff
        pending = {r['id'] for r in diff if r['status'] == 'new_recipe'}
        if not pending:
            print({'variants':len(records),'bases':len(BASES),'already_imported':True})
            return
        result = import_pack(target, accepted_ids=pending)
        after = (ROOT / 'library-manifest.json').read_bytes()
        assert import_pack(target, accepted_ids=pending)['published_file'] == result['published_file']
        assert (ROOT / 'library-manifest.json').read_bytes() == after
        (REPORT / 'import.json').write_bytes(encoded({'before_manifest_sha256':hashlib.sha256(before).hexdigest(),
            'after_manifest_sha256':hashlib.sha256(after).hexdigest(),'idempotent_reimport':True,'result':result}))
    print({'variants':len(records),'bases':len(BASES),'imported':do_import})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--import', dest='do_import', action='store_true')
    main(parser.parse_args().do_import)
