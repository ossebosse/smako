"""Build reviewed stages, register locally, then require basket proofs before merge."""
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
OUTPUT = ROOT / 'reviewed-expansion-round2-20261101'
REPORT = Path('docs/reviews/recipe-unblock-round2-20261101')
STAGES = {
    1: {
        'smako-greek-horiatiki': 'Råa grovskurna grönsaker med stora fetaskivor och separat bröd; inte panzanellas inarbetade bröd eller bakade grönsaker.',
        'smako-greek-tahinopita': 'Tunn jästdeg fylls med tahini, tvinnas och plattas till spiral; skild från smörfyllda kanelbullar och smulpaj.',
        'smako-italian-gnocchi-di-susine': 'Plommon innesluts i potatisdeg, sjuds och vänds i smörsmulor; inte plommonkaka eller ugnsbakad äggsmet.',
        'smako-swedish-semla': 'Kardemummabulle fylls efter gräddning med mandelkräm och vispad grädde; inte conchas kakdegsskal eller babas indränkning.',
        'smako-indian-chana-madra': 'Kikärtor tillagas i varsamt uppvärmd yoghurtsås med ghee; inte tomatmasala eller kall raita till annan huvudrätt.',
        'smako-indian-khichu': 'Rismjöl skållas till mjuk skedbar massa och ångas i skål; inte utbakade risbröd eller separata ångade risbullar.',
        'smako-swedish-stompa': 'Bikarbonat- och fildeg med råg kavlas till tunna bröd i torr panna; skild från ugnsbakad filmjölkslimpa.',
    },
    2: {
        'smako-indian-doi-maach': 'Först brynt fisk sjuds varsamt i tempererad lök-yoghurtsås; skild från tomatfiskgryta, kokosfisk och kall raita.',
        'smako-mexican-pescado-zarandeado': 'Adobopasta kokas separat och bryns på fisk i het ugn; uttrycklig hemanpassning, skild från pocherad fisk eller stekt fisk i tacos.',
        'smako-mexican-tacos-de-canasta': 'Mjuka majstacos med separata potatis- och bönfyllningar penslas med chiliolja och ångvilar tätt inpackade; skild från frasiga flautas/tostadas.',
        'smako-mexican-chilorio': 'Rivet långkokt fläsk steks torrt i ancho-vinägerpasta; skild från saftiga citruskokta carnitas och kött i buljong.',
        'smako-italian-spaghetti-aglio-olio': 'Kokt spaghetti vänds i vitlöksolja emulgerad med pastavatten; skild från råstekt spaghetti assassina eller pasta blandad med bönsås.',
    },
    3: {
        'smako-italian-panforte': 'Tät nöt-honungskaka med kanderat apelsinskal, ingen äggvispning eller jäst. Skild från rulltårta, nötmaräng och kanderat skal som eget godis.',
        'smako-swedish-bryta-filmjolk': 'Hårt tunnbröd bryts direkt i fil och mjuknar kort; skild från gröt, müsli och ugnsbakat bröd.',
        'smako-italian-schiacciata-uva': 'Druvor bakas både mellan två jästdegslager och ovanpå; skild från tahinifylld spiral och paj med frukt på botten.',
        'smako-mexican-enfrijoladas': 'Mjuka majstortillas doppas och viks i slät svartbönsås. Skild från tjocka fyllda majskakor, frasiga flautas och korgtacos med separat fyllning.',
    },
    4: {
        'smako-greek-fanouropita': 'Äggfri oljebaserad apelsin-russinkaka; skild från friterad skållad churro, filokaka och jäst fruktbröd.',
        'smako-greek-halvas-simigdalenios': 'Mannagryn rostas i olja, skållas med sirap och formas kallt; skild från bakad grynkaka och mjölkkokt kräm i filopaket.',
        'smako-greek-portokalopita': 'Torkad sönderriven filodeg binds med yoghurt och ägg, bakas och dränks med apelsinsirap; skild från grynig mannagrynskaka.',
        'smako-italian-budino-riso-toscana': 'Mjölkkokt ris och ägg bakas i eget mördegsskal; skild från jäst concha, fruktsmet/clafoutis och skiktad citronpudding.',
        'smako-mexican-camotes-poblanos': 'Sötpotatismos kokas med socker till formbar mjuk konfekt och kyls; skild från fruktgranita, knäck och kanderat skal.',
        'smako-italian-ricciarelli-siena': 'Ovispad mandel-äggvitedeg vilar åtta timmar och bakas till mjuka ovala kakor; skild från vispade mandelmarängskal med kräm.',
    },
    5: {
        'smako-swedish-isterband-dillpotatis': 'Syrad grynkorv serveras med mjölkstuvad tärnad potatis och rödbetor; skild från Lindströms rödbetsfärsbiffar, rårakor och mjölklimpar.',
        'smako-greek-kollyva-veteskal': 'Kokta hela matvetekorn kyls och blandas med nötter och frukt; uttrycklig frukostanpassning, skild från rostad havregranola och fylld bakad frukt.',
    },
    6: {
        'smako-swedish-porterstek': 'Hel nötstek bräseras i porter, koncentrerad vinbärssaft och soja; spadet blir gräddsås. Skild från plommonspäckad fläskkarré och pressat stekt fläsk.',
        'smako-italian-zuppa-imperiale': 'Mannagryn, ägg, smör och parmesan bakas till platta, skärs i kuber och värms i buljong. Skild från ströbrödsbaserade pressade passatelli.',
        'smako-italian-pizzoccheri': 'Handskurna boveteband samkokas med potatis och kål, varvas med ost och vitlökssmör. Skild från mjölklimpar, stekt potatis och stuvad potatis.',
    },
    7: {
        'smako-greek-revithada': 'Torra kikärtor och lök bakas sex timmar under tätt lock och avslutas med citron. Skild från tomatkokt fasolada och kalla kikärtssallader.',
        'smako-italian-pasta-alla-genovese': 'Nötkött och stor mängd lök långkokas till reducerad löksås för pasta. Skild från tomatragu, linssoppa och pressade passatelli.',
        'smako-greek-tirokafteri': 'Rostad skalad paprika mosas med feta och chili till dipp; skild från grov rå sallad och ugnsbakad fetapaj.',
        'smako-greek-melitzanosalata': 'Aubergine rostas mjuk, skalas och hackas till kall citron-vitlöksröra; skild från fyllda auberginebåtar och rullar.',
    },
    8: {
        'smako-thai-pa-tong-ko': 'Luftig osötad jästdeg paras till dubbla remsor och friteras, med varm sojadryck. Skild från fyllda runda jästmunkar.',
        'smako-mexican-bunuelos-de-viento': 'Tunn ägg-mjölksmet fastnar på rosettjärn och friteras till ihåliga spröda mönster; skild från spritsad skållad churrodeg.',
        'smako-indian-mangalore-buns': 'Banan-yoghurtdeg utan jäst vilar åtta timmar och friteras som tjocka puffade rundlar. Skild från stekt bananmos, ångad risdeg och jästa remsor.',
        'smako-greek-loukoumades': 'Lös jästsmet skedas till små friterade bollar och vänds i honung; skild från kesoplättar och fasta fyllda munkar.',
        'smako-indian-gulab-jamun': 'Mjölkpulverdeg formas till släta bollar, friteras vid lägre temperatur och drar i kardemummasirap. Skild från mjölbaserade churros och honungsjästbollar.',
    },
    9: {
        'smako-swedish-bohuslansk-aggost': 'Mjölk, fil och ägg värmekoaguleras, silas och varvas med socker; skild från bakad karamelläggkräm och gräddtårta.',
        'smako-indian-shrikhand': 'Yoghurt silas kall åtta timmar och vispas med socker och kardemumma; skild från långreducerad varm mjölkkräm och kokt ostkonfekt.',
        'smako-indian-chhena-poda': 'Nysyrad och silad mjölkost knådas med mannagryn och bakas till karamelliserad kaka; skild från pannkokt sandesh och morotshalwa.',
        'smako-italian-torta-pasqualina': 'Oljedeg omsluter ricotta och gröna blad med hela ägg i gropar, som bakas inne i pajen; skild från öppen tomatpaj och fyllda crespelle.',
    },
    10: {
        'smako-indian-phirni': 'Rått blötlagt ris mals fint och sjuds i mjölk till kyld kräm; skild från risgrynsgröt med hela gryn och bakad rispudding.',
        'smako-thai-hor-mok-pla': 'Fiskbitar och mald fisk binds med ägg och kokosmjölk och ångas i skålar ovanpå kål; skild från rinnande fisksås till nudlar och puffad omelett.',
        'smako-thai-kluai-buat-chi': 'Bananbitar sjuds varsamt i saltad söt kokosmjölk; skild från klibbigt ris med mango, kokosäggkräm och friterad banan.',
        'smako-italian-pasticciotto-leccese': 'Ett slutet mördegsskal omsluter förkokt äggkräm; uttrycklig smöranpassning, skild från öppna smördegsformar och staplade millefoglie.',
        'smako-mexican-sopa-de-lima': 'Klar kycklingsoppa med lime och frasiga stekta tortillastrimlor; skild från tjock bönsås runt mjuka tortillas och kycklingtinga på bröd.',
    },
    11: {
        'smako-thai-kai-palo': 'Hårdkokta hela ägg och fläskkarré bräseras i karamell, soja och Five Spice; skild från wokat äggris, friterad omelett i soppa och basilikatofu.',
    },
    12: {
        'smako-indian-dal-baati': 'Fasta ofyllda fullkornsbrödbollar bakas, bryts och smöras till linsgryta; skild från råa degbitar som kokas direkt i dal och fyllda stekta bröd.',
        'smako-mexican-salpicon-de-res': 'Långkokt högrev rivs, kyls och vänds i rå grönsakssallad med lime; skild från kycklingtinga på bröd och kall räkcocktail.',
        'smako-swedish-inkokt-lax': 'Lax sjuds i söt-syrlig dillag, kyls i lagen och lyfts ur före servering; skild från ugnsbakad lax, gratäng och varm laxsoppa.',
    },
    13: {
        'smako-indian-murgh-musallam': 'Hel marinerad kyckling fylls med ris och kokt ägg och bakas täckt; skild från benfria nötpanerade bitar, cafreal och risgryta.',
        'smako-italian-coda-vaccinara': 'Oxsvans på ben långkokas och benas ur i selleri-tomatsås; skild från bönsoppa, lammragù med polenta och löksås till pasta.',
        'smako-swedish-flasklagg-rotmos': 'Rimmad lägg långkokas och serveras med rotmos som späds med en del av kokspadet; skild från stekt fläsk med bruna bönor och späckad karré.',
    },
}
STAGES[14] = {
    'smako-italian-pasta-amatriciana': 'Guancialefett bär en reducerad tomatsås som avslutas med fårhårdost; skild från olja-vitlöksemulsion, sardell-olivsås och råstekt tomatspaghetti.',
    'smako-italian-pasta-cacio-pepe': 'Fårhårdost emulgeras utanför värmen med stärkelsevatten och rostad peppar; skild från gräddsås, äggbaserad carbonara och vitlöksolja.',
    'smako-mexican-torta-ahogada': 'Fläskfylld surdegsfralla dränks i varm lös tomatsalsa strax före servering. Uttrycklig svensk brödanpassning, skild från majsskålar och mjuka bönsåstortillas.',
}
SELECTED_VARIANTS = {
    14: {'smako-mexican-torta-ahogada': {'simple', 'standard'}},
    8: {'smako-indian-gulab-jamun': {'simple'}},
    9: {'smako-italian-torta-pasqualina': {'simple'}},
    10: {name: {'simple'} for name in ('smako-indian-phirni', 'smako-thai-hor-mok-pla',
                                      'smako-thai-kluai-buat-chi', 'smako-italian-pasticciotto-leccese')},
    12: {'smako-indian-dal-baati': {'simple'}},
}
STAGES[15] = {
    'smako-swedish-janssons-frestelse': 'Råstrimlad potatis varvas med lök och kryddad skarpsill och bakas länge med grädde. Skild från potatispuré, stekt köttpanna och gratänger med färdigkokt potatis.',
    'smako-swedish-gubbrora-ansjovis': 'Hårdkokta ägg och kryddad skarpsill tärnas till kall röra på knäckebröd; skild från matjessill med potatis, varm kycklingfyllning och bakad linspaté.',
}
STAGES[16] = {
    'smako-mexican-carlota-limon': 'Kyld lime-mjölkkräm varvas med mariekex som mjuknar utan gräddning; skild från fruktsorbet, grynpudding och gräddad paj.',
    'smako-swedish-blodpalt': 'Rå potatis och nötblod binds med råg/vetemjöl runt fläskfyllning och sjuds som palt; skild från äggpannkaka, kolbulle och rökt korv.',
}
STAGES[17] = {
    'smako-indian-gulab-jamun': STAGES[8]['smako-indian-gulab-jamun'],
    'smako-indian-phirni': STAGES[10]['smako-indian-phirni'],
    'smako-mexican-carne-en-su-jugo': 'Tunt nötkött avger sitt eget spad i en grön tomatillobuljong, med krispigt fläsk och bönor. Uttrycklig såsanpassning, skild från tjock chili, rivet långkokt fläsk och kall köttsallad.',
}
SELECTED_VARIANTS[17] = {name: {'extended'} for name in ('smako-indian-gulab-jamun', 'smako-indian-phirni')}
STAGES[18] = {
    'smako-italian-fegato-veneziana-flasklever': 'Tunna leverstrimlor steks till mjuk riklig lök, vinägersky och polenta. Uttrycklig ungnötsleverversion, skild från fintärnat förkokt fläsk/lever i indisk kryddsås.',
    'smako-swedish-korvkaka': 'Rå lever finfördelas och bakas med mjölkkokta korngryn, russin och ägg till skivbar kaka. Skild från äggakaka, blodpalt och lös korngryta.',
}
STAGES[19] = {
    'smako-mexican-manchamanteles': 'Kyckling sjuds i mixad röd ancho-tomatsås med ananas och stekt mogen kokbanan; frukten ingår i själva molen. Skild från cashewkyckling och fyllda tomater.',
}
STAGES[20] = {
    'smako-mexican-arroz-tumbada': 'Soppigt tomatris tillagas i samma spad som vit fisk, råa räkor och musselkött. Skild från risotto, torr paella och separat ris till fisksoppa.',
}
SELECTED_VARIANTS[20] = {'smako-mexican-arroz-tumbada': {'simple'}}
STAGES[21] = {
    'smako-swedish-sillsallad': 'Kall potatis-rödbets-äppelsallad med ätklar inläggningssill och saltgurka; skild från ägg-ansjovisröra på bröd och matjessill med separata tillbehör.',
}
STAGES[22] = {
    'smako-swedish-lapskojs': 'Finfördelat saltat nötkött arbetas in i grovt potatismos; uttrycklig konservversion, skild från skivat kött med mos, stekt biffpanna och rimmad lägg med rotmos.',
}
STAGES[23] = {'smako-italian-torta-pasqualina': STAGES[9]['smako-italian-torta-pasqualina']}
SELECTED_VARIANTS[23] = {'smako-italian-torta-pasqualina': {'standard', 'extended'}}
STAGES[24] = {
    'smako-mexican-frijoles-puercos': 'Kokta bönor mosas och steks med rå kryddad korvfärs, hela dess fett och smält ost till tjock röra med tortilla. Svensk färsk chorizo anges öppet; skild från frijol con puerco med hela bönor i buljong och enfrijoladas släta bönsås runt vikta tortillas.',
}
STAGES[25] = {
    'smako-indian-rogan-josh': 'Lamm bräseras i yoghurt med fänkålsfrö och torkad ingefära utan tomat. Öppet namngiven paprika-cayenneanpassning; skild från tomatmasala, palak och sötsyrlig vinägerbaserad vindaloo. Ainsley Harriotts egen rogan josh visar paprika/cayenne som kulinarisk väg: https://www.ainsley-harriott.com/recipe/lamb-rogan-josh/ . Dos och övrigt innehåll är separat granskade, inte hämtade som en kopia av det receptet.',
}
STAGES[26] = {
    'smako-greek-patatato-amorgos': 'Tomat-kanelbräserat lamm där potatisen tillsätts senare och binder själva spadet. Skild från tätt paketbakat kleftiko, lökdominerad stifado med separat korn och italiensk ragu med separat polenta. Lammversionen stöds av grekiska turistmyndighetens beskrivning: https://www.visitgreece.gr/el/experiences/architecture/local-architecture/amorgos-gastronomy . Det ursprungliga getutkastet bevaras.',
}
STAGES[27] = {
    'smako-greek-tsigariasto-get': 'Brynning följd av mycket låg tillagning i köttets eget lilla spad, med bröd till. Ingen tomat- eller potatisgryta och inget paketbakat kleftiko. Den kreten­siska restaurangens lammversion dokumenteras i https://www.gastronomos.gr/syntagh/tsigariasto/50594/ ; här är benfritt lamm och vin/lök/citron i tilläggsvarianterna uttryckliga anpassningar, inte en kopia av deras recept.',
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def insert_step(row, index, step):
    """Insert a one-based step while preserving the original dependency graph."""
    for later in row['steps'][index - 1:]:
        later['after'] = [n + 1 if n >= index else n for n in later.get('after', [])]
    for process in row.get('unmeasured_processes', []):
        if process['step'] >= index:
            process['step'] += 1
    row['steps'].insert(index - 1, step)


def rename_ingredient(row, old, new):
    for component in row['components']:
        for item in component['ingredients']:
            if item['name'] == old:
                item.update(name=new, label=new)
                item.pop('requirements', None)
    for step in row['steps']:
        step['uses'] = [new if n == old else n for n in step['uses']]


def prepend_thaw(row, name, minutes, purpose):
    from admit_expansion_20261101 import prepend_steps

    prepend_steps(row, [
        {'text': f'Väg upp fryst {name} i ett täckt kärl i kylskåp. Behåll all vätska.', 'uses': [name], 'minutes': 1, 'after': []},
        {'text': f'Tina helt i kylskåp enligt förpackningen. Planera {minutes} minuter och förläng vid behov tills ingen iskärna återstår. {purpose}', 'uses': [name], 'minutes': minutes, 'passive': True, 'after': [1]},
    ])


def mark_process(row, index, ingredients, operation, description):
    step = row['steps'][index - 1]
    step['uses'] = list(dict.fromkeys([*step['uses'], *ingredients]))
    row.setdefault('unmeasured_processes', []).append({
        'step': index, 'ingredients': ingredients, 'operation': operation, 'description': description})


def correct(row, vocabulary):
    base, changes = row['base_id'], []
    if base.endswith(('patatato-amorgos', 'tsigariasto-get')):
        rename_ingredient(row, 'getkött', 'lammkött')
        row['primary'] = 'lammkött'
        row['name'] = row['name'].replace('getkött', 'lammkött')
        row['notes'] = 'Granskad version med benfritt lamm i stället för get. Rå ätlig köttmängd anges efter eventuell putsning; ingen benandel eller kokförlust har antagits. Inte provlagad; tider är författaruppskattningar och mörheten avgör faktisk koktid.'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'lammkött':
                    item['label'] = 'Benfritt lammkött för långkok, rå ätlig vikt'
        for step in row['steps']:
            step['text'] = step['text'].replace('getköttet', 'lammköttet')
        first = row['steps'][0]
        first['text'] = first['text'].replace('Putsa lammköttet vid behov och skär', 'Putsa bort grova senor vid behov, väg därefter angiven rå ätlig mängd benfritt lamm och skär')
        if base.endswith('patatato-amorgos'):
            first['text'] = first['text'].replace('Skär lammköttet', 'Väg benfritt lamm efter eventuell putsning. Skär lammköttet').replace('Hacka löken.', 'Skala och väg löken, hacka den.').replace('Tärna morot och selleri grovt.', 'Ansa och väg rå ätlig morot och selleri, tärna grovt.')
            if row['variant_id'] == 'extended':
                rename_ingredient(row, 'rödvin', 'rött matlagningsvin')
                row['name'] += ' – med rött matlagningsvin'
                row['steps'][2]['text'] = row['steps'][2]['text'].replace('rödvinet', 'det röda matlagningsvinet')
                row['steps'][6]['text'] = 'Ta upp lagerbladen. Rör ner den uppvägda frysta hackade persiljan och låt den koka med minst tre minuter eller längre enligt förpackningen.'
                row['steps'][6]['minutes'] = 4
            old = copy.deepcopy(row['steps'])
            row['steps'] = old[:3]
            for turn in range(5):
                row['steps'].append({'text': 'Sjud försiktigt under tätt lock 20 minuter.', 'uses': ['lammkött'], 'minutes': 20, 'passive': True})
                row['steps'].append({'text': 'Rör om från botten och kontrollera att grytan inte kokar torr. Tillsätt vid behov 100 ml vatten. Efter sista omgången ska köttet börja bli mört; fortsätt annars sjuda med regelbundna kontroller innan potatisen tillsätts.', 'uses': ['lammkött'], 'minutes': 1})
            potato = old[4]
            potato['text'] = potato['text'].replace('Skala potatisen och skär', 'Skala potatisen, väg den råa ätliga mängden och skär')
            row['steps'].extend([potato,
                {'text': 'Sjud försiktigt med locket på glänt 15 minuter.', 'uses': ['potatis', 'lammkött'], 'minutes': 15, 'passive': True},
                {'text': 'Vänd försiktigt från botten utan att mosa potatisen. Kontrollera vätskan och tillsätt vid behov 50 ml vatten.', 'uses': ['potatis', 'lammkött'], 'minutes': 1},
                {'text': 'Sjud ytterligare cirka 15 minuter.', 'uses': ['potatis', 'lammkött'], 'minutes': 15, 'passive': True},
                {'text': 'Kontrollera att potatisen är helt mjuk och köttet delar sig med gaffel. Förläng vid behov. Behåll all olja och allt spad som tjocknat av potatisens stärkelse.', 'uses': ['potatis', 'lammkött', 'olivolja'], 'minutes': 2}])
            if row['variant_id'] != 'simple':
                row['steps'].append(old[6])
                mark_process(row, len(row['steps']), ['lagerblad'], 'remove_after_infusion', 'Lagerblad kokar med och tas bort före servering. Kvarvarande näring i såsen och bladens avgivning är inte uppmätta.')
            row['steps'].extend([
                {'text': 'Ta grytan från värmen och lägg på lock.', 'uses': ['potatis', 'lammkött'], 'minutes': 1},
                {'text': 'Låt grytan vila fem minuter av värmen.', 'uses': ['potatis', 'lammkött'], 'minutes': 5, 'passive': True},
                {'text': 'Fördela kött, potatis och hela såsen mellan portionerna.', 'uses': ['potatis', 'lammkött'], 'minutes': 2}])
        else:
            if row['variant_id'] != 'simple':
                rename_ingredient(row, 'vitt vin', 'vitt matlagningsvin')
                row['name'] += ' – med vitt matlagningsvin'
                row['notes'] += ' Lök, vin, oregano och citron är uttryckliga tillägg till fåingredienstekniken.'
                row['steps'][1]['text'] = row['steps'][1]['text'].replace('Skiva löken och hacka vitlöken.', 'Skala och väg lök och vitlök, skiva löken och hacka vitlöken.').replace('vinet', 'det vita matlagningsvinet')
            index = next(n for n, s in enumerate(row['steps']) if s.get('passive'))
            periods = []
            for turn in range(6):
                periods.extend([
                    {'text': 'Låt köttet tillagas under tätt lock på mycket låg värme i 20 minuter.', 'uses': ['lammkött'], 'minutes': 20, 'passive': True},
                    {'text': 'Vänd köttet och kontrollera bottnen. Sänk värmen om det steker torrt; tillsätt endast vid behov 30 ml vatten så det inte bränner. Köttet ska tillagas i lite eget spad, inte täckas av vatten.', 'uses': ['lammkött'], 'minutes': 1}])
            periods.append({'text': 'Kontrollera att köttet är genomlagat och mycket mört. Förläng tillagningen vid behov med fortsatt tillsyn. Servera allt fett och det koncentrerade spadet.', 'uses': ['lammkött', 'olivolja'], 'minutes': 2})
            row['steps'][index:index + 1] = periods
            row['steps'][-1]['text'] += ' Väg den angivna brödmängden och behåll hela salladens saft om sallad ingår.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit boneless lamb version at the original edible gram dose, with meat named in the title and weighed after trimming. It is not a goat identity alias or a bone/cooking-yield conversion. Preserve the distinct patatato potato-in-tomato method or tsigariasto low-liquid method. Separate periodic checks and serving from passive time; retain all meat fat/gravy. Any wine becomes explicitly named reviewed cooking wine; no claim of complete alcohol evaporation.')
    if base.endswith('rogan-josh'):
        rename_ingredient(row, 'kashmirichilipulver', 'paprikapulver')
        row['name'] += ' – med paprika och cayenne'
        row['flavor'] = ['paprika', 'cayenne', 'fänkålsfrö', 'torkad ingefära']
        row['notes'] = 'Granskad vardagsanpassning av rogan josh med lamm, yoghurt, fänkålsfrö och torkad ingefära, utan tomat. Ny dos 8 g paprikapulver och 0,6 g cayenne ersätter 10 g kashmirichili utan påstående om samma hetta, smak eller färg. Rapsolja används i stället för senapsolja/ghee och ratanjot utelämnas. Inte provlagad; tiderna är uppskattningar.'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'paprikapulver':
                    item.update(quantity=8, label='Malt paprikapulver, inte rökt paprika')
                elif item['name'] == 'lammkött':
                    item.update(label='Benfritt lammkött för gryta, rå ätlig vikt')
                elif item['name'] in {'kardemumma', 'kryddnejlika', 'kanel'}:
                    item['label'] = 'Mald ' + item['name']
            if component['id'] == 'lamm':
                component['ingredients'].append({'name': 'cayennepeppar', 'form': 'dry', 'quantity': 0.6, 'unit': 'g', 'role': 'flavour', 'label': 'Malen cayennepeppar'})
        for step in row['steps']:
            if 'paprikapulver' in step['uses']:
                step['uses'].append('cayennepeppar')
            step['text'] = step['text'].replace('kashmirichili', 'paprikapulver och cayennepeppar')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skär lammköttet', 'Väg benfritt lammkött utan grova senor och skär det')
        row['steps'][0]['text'] += ' De eventuella övriga kryddorna används malda och stannar i såsen.'
        original = copy.deepcopy(row['steps'])
        row['steps'] = original[:2] + [
            {'text': 'Häll i 500 ml vatten och koka upp under omrörning. Sänk till svag sjudning och lägg på lock.', 'uses': ['lammkött', 'yoghurt naturell'], 'minutes': 3},
            {'text': 'Sjud försiktigt under lock 30 minuter.', 'uses': ['lammkött'], 'minutes': 30, 'passive': True},
            {'text': 'Rör i grytan och kontrollera att bottnen inte bränner. Tillsätt vid behov 100 ml vatten.', 'uses': ['lammkött', 'yoghurt naturell'], 'minutes': 1},
            {'text': 'Sjud ytterligare 30 minuter under lock.', 'uses': ['lammkött'], 'minutes': 30, 'passive': True},
            {'text': 'Rör igen och kontrollera vätskan. Tillsätt vid behov 100 ml vatten.', 'uses': ['lammkött', 'yoghurt naturell'], 'minutes': 1},
            {'text': 'Sjud ytterligare cirka 40 minuter under lock.', 'uses': ['lammkött'], 'minutes': 40, 'passive': True},
            {'text': 'Kontrollera att lammet är helt genomlagat och så mört att det delar sig lätt med gaffel. Förläng sjudningen vid behov och kontrollera regelbundet vätskan. Behåll allt fett och all sås.', 'uses': ['lammkött'], 'minutes': 2},
            {**original[3], 'text': original[3]['text'].replace('Skölj riset i sil. ', '')},
            {'text': 'Sjud riset under lock cirka 18 minuter eller längre enligt förpackningen, tills kornen är mjuka och vattnet absorberats.', 'uses': ['ris'], 'minutes': 18, 'passive': True},
            {'text': 'Kontrollera riset och ta från värmen. Om det fortfarande är hårt, tillsätt 50 ml vatten och fortsätt sjuda före vilan.', 'uses': ['ris'], 'minutes': 1},
            {'text': 'Låt riset vila fem minuter under lock.', 'uses': ['ris'], 'minutes': 5, 'passive': True},
            *original[5:]]
        for step in row['steps']:
            if step['text'].startswith('Riv gurkan'):
                step['text'] = 'Riv den uppvägda gurkan grovt och behåll all vätska. Hacka de uppvägda färska myntabladen och blanda gurka, all gurksaft och mynta med raitans yoghurt, citronjuice och salt. Raitan blir lösare än med pressad gurka. Ställ i kylskåp vid 4 °C till servering och servera hela mängden.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New visible paprika/cayenne recipe: 8 g paprika and 0.6 g cayenne replace 10 g Kashmiri chili without sensory equivalence. Keep boneless edible lamb, yoghurt, fennel and dried ginger; no tomato is added. Separate active liquid/softness/rice checks from 100-minute simmering and rice rest. All fat, ground spices and cucumber juice are retained; no invented cooking yield.')
    if base.endswith('frijoles-puercos'):
        rename_ingredient(row, 'mexikansk färsk chorizo', 'färsk chorizokorv')
        row['name'] += ' – med svensk färsk chorizo'
        row['primary'] = 'bönor och färsk chorizokorv'
        row['notes'] = row.get('notes', '').replace('AI-författat receptutkast, inte provlagat och ännu inte import-/produktgranskat av Smako. ', 'Granskad receptanpassning, inte provlagad. ')
        row['notes'] = row.get('notes', '').replace('Rå mexikansk chorizo är nödvändig identitet, inte spansk lufttorkad korv.',
            'Denna granskade version använder uttryckligen svensk rå färsk chorizo med fläsk och nöt; den är inte märkt som mexikansk korv.')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'färsk chorizokorv':
                    item.update(form='as_sold', quantity=35, label='Svensk rå färsk chorizokorv, vägd med fjälster')
        index = next(n for n, s in enumerate(row['steps'], 1) if 'färsk chorizokorv' in s['uses'])
        insert_step(row, index, {'text': 'Väg den råa färska chorizokorven före borttagning av fjälstret. Skär upp fjälstret, skrapa ur all korvfärs och kasta fjälstret. Använd separat skärbräda; tvätta händer och redskap efter rå korv.',
            'uses': ['färsk chorizokorv'], 'minutes': 3, 'after': [index - 1] if index > 1 else []})
        row['steps'][index]['after'] = [index]
        mark_process(row, index, ['färsk chorizokorv'], 'trim_before_cooking',
            'Fjälstret tas bort efter att hela råa korven vägts. Mängden och näringsförlusten är inte uppmätta; ingen ren köttandel antas.')
        row['steps'][index + 1]['text'] += ' Häll inte bort något stekfett; hela korvfärsen och allt fett blandas med bönorna.'
        row['steps'][-1]['text'] += ' Följ även tortillaförpackningens uppvärmningsanvisning.'
        changes.append('Explicit Swedish raw fresh chorizo alternative with pork and beef, not a Mexican identity alias. New gross dose 35 g before casing removal replaces 30 g raw casing-free mince without yield equivalence. Casing loss is unknown; all cooking fat enters the beans. Keep raw handling, 72 C centre check and separate salsa utensils.')
    if base.endswith('sillsallad'):
        rename_ingredient(row, 'inläggningssill', 'ätklar inläggningssill')
        rename_ingredient(row, 'ättiksgurka', 'saltgurka')
        rename_ingredient(row, 'kokta ägg', 'ägg')
        row['primary'] = 'ätklar inläggningssill'
        row['method'] = 'pot'
        row['name'] += ' – med ätklar sill och saltgurka'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'saltgurka':
                    item.update(quantity=80, label='Saltgurka, vägd efter avrinning')
                if item['name'] == 'ätklar inläggningssill':
                    item['label'] = 'Ätklar 5-minuterssill, vägd efter avrinning'
                if item['name'] == 'ägg':
                    item.update(quantity=4, unit='st', form='as_sold', label='Råa hela hönsägg med skal, räknade före kokning')
                if item['name'] == 'dill':
                    item['requirements'] = ['frozen']
        row['steps'] = [
            {'text': 'Skala rödbetorna råa och väg därefter den angivna ätliga mängden. Dela stora betor. Koka upp med 1200 ml vatten i en kastrull.', 'uses': ['rödbeta'], 'minutes': 7},
            {'text': 'Sjud under lock cirka 40 minuter tills rödbetorna är helt mjuka.', 'uses': ['rödbeta'], 'minutes': 40, 'passive': True},
            {'text': 'Kontrollera rödbetorna med sticka, förläng kokningen vid behov. Häll av kokvattnet och skär betorna i mindre bitar på ren skärbräda. Bred ut i en grund skål och ställ i kylskåp.', 'uses': ['rödbeta'], 'minutes': 5},
            {'text': 'Skala potatisen, väg den råa ätliga mängden och dela jämnt. Koka upp med 1200 ml vatten.', 'uses': ['potatis'], 'minutes': 6},
            {'text': 'Sjud cirka 18 minuter tills potatisen är precis mjuk, inte sönderkokt.', 'uses': ['potatis'], 'minutes': 18, 'passive': True},
            {'text': 'Kontrollera potatisen, förläng kokningen vid behov. Häll av, skär i bitar och bred ut i en grund ren skål. Ställ i kylskåp.', 'uses': ['potatis'], 'minutes': 4},
        ]
        mark_process(row, 3, ['rödbeta'], 'drain_after_cooking', 'Rödbetornas kokvatten hälls bort; kvarvarande näring och färdig vikt är inte uppmätta.')
        mark_process(row, 6, ['potatis'], 'drain_after_cooking', 'Potatisens kokvatten hälls bort; kvarvarande näring och färdig vikt är inte uppmätta.')
        if row['variant_id'] != 'simple':
            row['steps'].extend([
                {'text': 'Lägg de hela råa äggen i en kastrull med kallt vatten så de täcks. Koka upp.', 'uses': ['ägg'], 'minutes': 5},
                {'text': 'Sjud äggen tolv minuter tills både gula och vita är fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
                {'text': 'Häll av kokvattnet och lägg äggen i kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
                {'text': 'Låt äggen svalna fem minuter i det kalla vattnet.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
                {'text': 'Skala äggen, skölj bort skalrester och dela med rena redskap. Ställ i kylskåp på en ren tallrik.', 'uses': ['ägg'], 'minutes': 4},
            ])
            mark_process(row, 11, ['ägg'], 'peel_after_cooking', 'Fyra råa hela ägg kokas och skalas. Ingen styckvikt, skalandel eller kokt vikt antas.')
        if row['variant_id'] == 'extended':
            row['steps'].append({'text': 'Koka den frysta hackade dillen med 15 ml vatten under omrörning minst tre minuter eller längre enligt förpackningen. Häll hela mängden med vätskan i en liten ren skål och ställ i kylskåp.', 'uses': ['dill'], 'minutes': 4})
        chill = ['rödbeta', 'potatis'] + (['ägg'] if row['variant_id'] != 'simple' else []) + (['dill'] if row['variant_id'] == 'extended' else [])
        row['steps'].extend([
            {'text': 'Kyl alla tillagade ingredienser i de grunda kärlen tills de är högst 8 °C, uppskattningsvis 60 minuter. Kylskåpet bör hålla 4 °C. Förläng vid behov; blanda aldrig varm potatis, rödbeta, ägg eller dill med fisken.', 'uses': chill, 'minutes': 60, 'passive': True},
            {'text': 'Kontrollera att sillen är märkt ätklar 5-minuterssill; rå salt sill som kräver egen behandling får inte användas. Låt sill och saltgurka rinna av utan att skölja. Väg därefter de angivna avrunna mängderna och skär smått. Kärna ur äpplet och skala rödlöken, väg rå ätlig mängd och tärna.', 'uses': ['ätklar inläggningssill', 'saltgurka', 'äpple', 'rödlök'], 'minutes': 10},
        ])
        salad_names = [i['name'] for i in row['components'][0]['ingredients']]
        sauce = 'crème fraiche och peppar' + (' samt senap' if row['variant_id'] != 'simple' else '') + (' och vinäger samt hela den kalla dillblandningen med vätskan' if row['variant_id'] == 'extended' else '')
        row['steps'].extend([
            {'text': 'Rör ihop ' + sauce + '. Vänd varsamt med kall potatis, rödbeta, sill, saltgurka, äpple och rödlök. Tillsätt inget extra salt. Täck skålen och ställ i kylskåp.', 'uses': salad_names, 'minutes': 5},
            {'text': 'Låt salladen stå i kylskåp 30 minuter så smakerna förenas.', 'uses': ['ätklar inläggningssill'], 'minutes': 30, 'passive': True},
            {'text': 'Fördela den kalla sillsalladen i fyra portioner och servera direkt från kylskåp.' + (' Servera de kalla kokta äggen och knäckebrödet till.' if row['variant_id'] != 'simple' else ''), 'uses': ['ätklar inläggningssill'] + (['ägg', 'knäckebröd'] if row['variant_id'] != 'simple' else []), 'minutes': 3},
        ])
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Bind only ready-treated Abba herring at the unchanged 400 g declared drained dose. Explicit salt-pickle alternative: 80 g saltgurka replaces 120 g ättiksgurka, no equivalence. Source comparison quantities are already drained. Weigh beet/potato after raw peeling, separate active draining/cold-chain checks, and retain unknown cooking losses. Standard/extended use four raw shell eggs instead of 180 g cooked eggs, with explicit boiling and peeling. Frozen dill is cooked and chilled with all liquid.')
    if base.endswith('lapskojs'):
        rename_ingredient(row, 'rimmad oxbringa', 'corned beef på burk')
        row['primary'] = 'corned beef på burk'
        row['name'] = row['name'].replace('rimmad oxbringa', 'corned beef på burk')
        row['components'][0]['name'] = 'Färdigkokt nötkött och mjuk lök'
        row['notes'] = 'Granskad konservversion av lapskojs. Inte provlagad; tider är författaruppskattningar. Ny dos 680 g färdigkokt corned beef ersätter 700 g rå rimmad bringa utan påstådd utbytesekvivalens. Hela konservinnehållet används. Standard har snabbsyrad rödbeta för direkt konsumtion, utökad även varm kålsida.'
        for item in row['components'][0]['ingredients']:
            if item['name'] == 'corned beef på burk':
                item.update(quantity=680, label='Färdigkokt corned beef, två hela 340 g-konserver')
        original = copy.deepcopy(row['steps'])
        row['steps'] = []
        if row['variant_id'] != 'simple':
            row['steps'].extend([
                {'text': 'Skala rödbetan, väg rå ätlig mängd och tärna. Koka upp med 700 ml vatten.', 'uses': ['rödbeta'], 'minutes': 6},
                {'text': 'Sjud cirka 25 minuter tills rödbetan är mjuk.', 'uses': ['rödbeta'], 'minutes': 25, 'passive': True},
                {'text': 'Kontrollera rödbetan och förläng vid behov. Häll av kokvattnet och vänd betorna med all vinäger, socker och senap. Ställ åt sidan till serveringen; detta är ett tillbehör för direkt konsumtion, ingen hållbarhetsvaliderad inläggning.', 'uses': ['rödbeta', 'äppelcidervinäger', 'strösocker', 'senap'], 'minutes': 3},
            ])
            mark_process(row, 3, ['rödbeta'], 'drain_after_cooking', 'Rödbetans kokvatten hälls bort; kvarvarande näring och färdig vikt är inte uppmätta.')
        row['steps'].extend([
            {'text': 'Skala potatisen och löken, väg därefter de råa ätliga mängderna. Dela potatisen och finhacka löken. Koka upp tillsammans i 1600 ml vatten.', 'uses': ['potatis', 'gul lök'], 'minutes': 8},
            {'text': 'Sjud cirka 20 minuter tills potatis och lök är helt mjuka.', 'uses': ['potatis', 'gul lök'], 'minutes': 20, 'passive': True},
            {'text': 'Kontrollera med sticka och förläng kokningen vid behov. Häll av potatis och lök genom ett finmaskigt durkslag så all lök behålls. Lägg tillbaka i kastrullen.', 'uses': ['potatis', 'gul lök'], 'minutes': 2},
        ])
        mark_process(row, len(row['steps']), ['potatis', 'gul lök'], 'drain_after_cooking', 'Potatisens och lökens kokvatten hälls bort. Kvarvarande näring och tillagad portionsvikt är inte uppmätta.')
        if row['variant_id'] == 'extended':
            side = next(s for s in original if s['text'].startswith('Strimla vitkål'))
            side['text'] = 'Ansa vitkål och purjolök, skala moroten och väg rå ätlig mängd. ' + side['text'] + ' Behåll allt smör och all grönsakssaft till serveringen.'
            row['steps'].append(side)
        row['steps'].extend([
            {'text': 'Öppna de två corned beef-konserverna och finfördela hela innehållet inklusive fett och gelé. Värm mjölken med mosets smör. Stöt potatis och lök grovt och arbeta ner hela mjölkblandningen och allt kött. Späd vid behov med 85 ml hett vatten. Tillsätt inget extra salt.', 'uses': ['corned beef på burk', 'gul lök', 'potatis', 'smör', 'mjölk'], 'minutes': 10},
            {'text': 'Värm under ständig omrörning tills hela moset är genomhett, minst fem minuter och längre vid behov. Köttet ska vara finfördelat och inarbetat i moset. Fördela på fyra portioner.' + (' Servera med rödbetorna och all deras dressing.' if row['variant_id'] != 'simple' else '') + (' Servera den varma kålsidan med all smörsky.' if row['variant_id'] == 'extended' else ''), 'uses': [i['name'] for c in row['components'] for i in c['ingredients']], 'minutes': 6},
        ])
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit canned-corned-beef lapskojs: new 680 g whole prepared product (two 340 g cans) replaces 700 g raw cured brisket, not a cooking-yield conversion. Remove the unnecessary 150-minute raw-meat braise. Cook onion with potato, retain all canned fat/jelly and milk/butter. Weigh roots after raw peeling; discarded cooking water has unknown retention. Separate beet draining/dressing and potato inspection from passive simmering.')
    if base.endswith('manchamanteles'):
        rename_ingredient(row, 'matbanan', 'kokbanan med skal')
        row['name'] += ' – med uppvägd hel mogen kokbanan'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'kokbanan med skal':
                    item.update(form='as_sold', quantity=600, label='Mogen gul/svartfläckig kokbanan, inköpt vikt med skal')
                if item['name'] == 'anchochili':
                    item['label'] = 'Mald anchochili'
        row['steps'][0].update(text='Utgå från redan mogen kokbanan med gul till svartfläckig skal och eftergivligt fruktkött. Grön hård kokbanan måste mogna före matlagningen; mognadstid ingår inte i receptets tillagningstid. Rör den uppvägda malda anchochilin med 250 ml hett vatten; ingen hel chili ska rostas eller rensas.', minutes=2)
        row['steps'][1].update(text='Låt den malda chilin dra i vattnet fem minuter; hela blandningen ska användas.', minutes=5)
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('den mjuka chilin', 'den uppblötta malda chilin').replace('det sparade chilivattnet', 'allt chilivatten')
        row['steps'][5].update(text='Sjud kycklingen under lock i elva minuter.', minutes=11)
        insert_step(row, 7, {'text': 'Rör i molesåsen och kontrollera att bottnen inte bränner. Tillsätt vid behov 50 ml vatten.', 'uses': ['kyckling', 'tomat'], 'minutes': 1})
        insert_step(row, 8, {'text': 'Sjud ytterligare elva minuter under lock.', 'uses': ['kyckling'], 'minutes': 11, 'passive': True})
        insert_step(row, 9, {'text': 'Kontrollera minst 74 °C mitt i de tjockaste kycklingbitarna. Fortsätt sjuda om de inte är genomlagade.', 'uses': ['kyckling'], 'minutes': 2})
        fruit_step = row['steps'][9]
        fruit_step['text'] = 'Väg kokbananen med skal till den nya angivna bruttomängden, skala och skiva allt fruktkött. Stek försiktigt i återstående olja tills skivorna är gyllene med mjuk mitt. Använd den uppvägda frysta ananasen i nästa steg; ingen saft ska hällas bort.'
        if row['variant_id'] == 'extended':
            fruit_step['text'] += ' Skala och kärna ur äpplet, väg den råa ätliga mängden och tärna.'
        mark_process(row, 10, ['kokbanan med skal'], 'trim_before_cooking', 'Kokbanan vägs med skal före skalning. Skalets andel och kvarvarande ätliga vikt är inte uppmätta; inget portionsutbyte antas.')
        row['steps'][10]['text'] = row['steps'][10]['text'].replace('ananas', 'fryst ananas med all saft').replace('sjud 6 minuter', 'sjud under omrörning minst tio minuter eller längre enligt förpackningen tills frukten är helt genomhet').replace('matbananen', 'kokbananen')
        row['steps'][10]['text'] += ' Skrapa även ner all stekolja från bananpannan i grytan.'
        row['steps'][10]['minutes'] = 13
        for step in row['steps']:
            if step['text'].startswith('Sjud riset'):
                step['text'] = 'Sjud riset under lock cirka 18 minuter eller längre enligt förpackningen tills det är mjukt och vattnet absorberats.'
            if step['text'].startswith('Ta riset från'):
                step['text'] = 'Låt riset vila under lock fem minuter efter att det tagits från värmen.'
        rice_rest = next(n for n, s in enumerate(row['steps'], 1) if s['text'].startswith('Låt riset vila'))
        insert_step(row, rice_rest, {'text': 'Kontrollera riset och ta det från värmen när det är mjukt. Tillsätt annars 50 ml vatten och fortsätt sjuda före vilan.', 'uses': ['ris'], 'minutes': 1})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New dose 600 g ripe whole plantain weighed with peel replaces 300 g edible flesh; no yield equivalence. Ripeness is a manual precondition, not proved by catalogue or included in cook time. Use the reviewed ground ancho at unchanged 24 g and retain all hydration water. Frozen pineapple cooks in the mole with all juice; all frying oil is retained. Separate simmering inspection and temperature/rice checks from passive time.')
    if base.endswith('arroz-tumbada'):
        rename_ingredient(row, 'råa räkor', 'råa skalade vannameiräkor')
        rename_ingredient(row, 'musslor', 'blåmusselkött utan skal')
        row['name'] += ' – med fryst musselkött utan skal'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'råa skalade vannameiräkor':
                    item.update(form='as_sold', label='Rå skalad vannameiräka, deklarerad produktvikt')
                if item['name'] == 'blåmusselkött utan skal':
                    item.update(quantity=200, label='Fryst blåmusselkött utan skal')
        row['steps'][0]['text'] = 'Använd tinad benfri vit fisk, råa skalade vannameiräkor och musselkött utan skal; inga levande musslor ingår. Behåll all upptiningsvätska och koka den i rätten. Kontrollera fisken efter kvarvarande ben och skär i bitar. Skala löken, väg ätlig mängd och hacka lök och tomat.'
        row['steps'][2].update(text='Sjud riset försiktigt i cirka tolv minuter; det ska fortfarande omges av rikligt med spad.', minutes=12, passive=True)
        insert_step(row, 3, {'text': 'Häll i 1400 ml vatten och all upptiningsvätska. Koka upp ordentligt under omrörning.', 'uses': ['ris', 'fisk', 'råa skalade vannameiräkor', 'blåmusselkött utan skal'], 'minutes': 3})
        row['steps'][4]['text'] = 'Lägg i musselköttet och fisken och sjud försiktigt fem minuter. Tillsätt de råa skalade räkorna och sjud ytterligare tre till fem minuter, eller längre enligt skaldjursförpackningarna. Kontrollera att räkorna är ogenomskinliga i mitten, fisken når minst 63 °C och musselköttet är genomhett. Riset ska vara mjukt men inte sönderkokt. Allt spad behålls.'
        row['notes'] = row.get('notes', '').replace('Musslor har vikt med skal; ätligt utbyte är inte uppskattat.', 'Ny version använder uttryckligen musselkött utan skal, inte levande musslor.')
        row['steps'] = [
            {'text': 'Väg upp råa skalade vannameiräkor, fryst fisk och fryst musselkött i separata täckta kärl. Ställ i kylskåp.', 'uses': ['råa skalade vannameiräkor', 'fisk', 'blåmusselkött utan skal'], 'minutes': 2},
            {'text': 'Tina helt i kylskåp enligt förpackningarna. Planera tolv timmar och förläng vid behov tills inga iskärnor finns kvar. Behåll all vätska för genomkokning i risgrytan.', 'uses': ['råa skalade vannameiräkor', 'fisk', 'blåmusselkött utan skal'], 'minutes': 720, 'passive': True},
            *row['steps']]
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit shell-free version: new 200 g frozen mussel meat replaces 600 g live shell-on mussels, not a shell-yield conversion. Raw peeled Miramar shrimp use the unchanged 250 g declared product mass including its added water/salt, not 100 percent pure flesh. Thaw all seafood under refrigeration, boil all thaw liquid and retain all broth. Separate water addition/boiling from passive rice simmer.')
    if base in STAGES[18]:
        rename_ingredient(row, 'fläsklever', 'ungnötslever')
        row['primary'] = 'ungnötslever'
        row['name'] = row['name'].replace('fläsklever', 'ungnötslever')
        if base.endswith('korvkaka'):
            row['name'] += ' – med ungnötslever'
        row['notes'] = row.get('notes', '').replace('fläsklever i stället för kalvlever', 'ungnötslever i stället för kalvlever').replace('Grislever serveras inte rosa', 'Levern serveras genomlagad')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ungnötslever':
                    item.update(form='as_sold', label='Rå ungnötslever, vägd före putsning')
        for step in row['steps']:
            step['text'] = step['text'].replace('fläsklevern', 'ungnötslevern')
        if base.endswith('fegato-veneziana-flasklever'):
            row['steps'][2].update(text='Sjud polentan försiktigt i cirka 25 minuter eller längre enligt förpackningen. Rör regelbundet och skrapa bottnen; tiden räknas som aktiv tillsyn.', passive=False)
            for n, step in enumerate(row['steps'], 1):
                if step['text'].startswith('Putsa'):
                    step['text'] = 'Väg leverbiten före putsning. ' + step['text']
                    mark_process(row, n, ['ungnötslever'], 'trim_before_cooking', 'Grova hinnor och kärl putsas bort från inköpt levervikt; den kvarvarande råa och färdiga vikten är inte uppmätt.')
                if step['text'].startswith('Lägg tillbaka lök'):
                    step['text'] += ' Låt den frysta hackade persiljan koka med minst tre minuter eller längre enligt förpackningen.'
                    step['uses'].append('persilja')
                if step['text'].startswith('Hacka persilja'):
                    step['text'] = step['text'].replace('Hacka persilja och vänd ner med svartpeppar.', 'Vänd ner svartpeppar; persiljan är redan genomkokt i skyn.')
                    step['text'] += ' Servera allt smör, all sky och eventuell salladsdressing.'
            changes.append('Explicit young-beef-liver substitution at 600 g purchased pre-trim mass, not an equivalence to 600 g edible pork liver. Unknown trimming yield; frozen parsley cooks in the gravy and all butter/juice/dressing is served. Polenta stirring counts as active work.')
        else:
            row['steps'][1].update(text='Sjud korngrynen under lock i 17 minuter.', minutes=17)
            insert_step(row, 3, {'text': 'Rör om och kontrollera vattnet. Tillsätt vid behov 100 ml så grynen inte bränner.', 'uses': ['korngryn'], 'minutes': 1})
            insert_step(row, 4, {'text': 'Sjud ytterligare 18 minuter, eller längre tills korngrynen är mjuka. Allt kvarvarande vatten ska gå med i gröten.', 'uses': ['korngryn'], 'minutes': 18, 'passive': True})
            row['steps'][5].update(text='Låt gröten svalna 20 minuter tills den är ljummen och inte börjar tillaga äggen när smeten blandas.', minutes=20)
            insert_step(row, 6, {'text': 'Bred gröten i en vid skål och sätt ugnen på 190 °C över-/undervärme.', 'uses': ['korngryn', 'mjölk'], 'minutes': 2})
            mix = row['steps'][7]
            mix['text'] = mix['text'].replace('Putsa levern', 'Väg ungnötslevern före putsning. Putsa levern').replace('med ägg,', 'med råa ägg knäckta och vägda utan skal,')
            mark_process(row, 8, ['ungnötslever'], 'trim_before_cooking', 'Leverhinnor och kärl avlägsnas från bruttovikten. Kvarvarande ätlig vikt och näringsutbyte är inte uppmätta.')
            row['steps'][8].update(text='Baka kakan mitt i ugnen i cirka 50 minuter.', minutes=50)
            insert_step(row, 9, {'text': 'Klä formen med bakplåtspapper, häll i hela massan och sätt in formen i ugnen.', 'uses': ['ungnötslever', 'korngryn', 'ägg'], 'minutes': 2})
            insert_step(row, 11, {'text': 'Mät minst 75 °C i mitten. Om det är svalare, fortsätt grädda tills temperaturen nåtts. Kakan ska vara genomstannad utan rå levermassa.', 'uses': ['ungnötslever', 'ägg'], 'minutes': 2})
            insert_step(row, 12, {'text': 'Låt kakan stå kvar i ugnen minst tre minuter efter att mitten nått 75 °C.', 'uses': ['ungnötslever', 'ägg'], 'minutes': 3, 'passive': True})
            insert_step(row, 13, {'text': 'Ta ut formen och ställ på värmetåligt underlag.', 'uses': ['ungnötslever'], 'minutes': 1})
            for step in row['steps']:
                if step['text'].startswith('Mosa lingonen'):
                    step['text'] = 'Koka de uppvägda frysta lingonen med sockret minst en minut eller längre enligt förpackningen, under omrörning. Mosa lätt; behåll all bärsaft och servera kompotten ljummen.'
                if step['text'].startswith('Strimla kålen'):
                    step['text'] = 'Ansa kålen och kärna ur äpplet. Väg de råa ätliga mängderna, strimla och vänd med all vinäger. Servera även råkostens saft.'
            changes.append('Explicit young-beef-liver substitution at 400 g purchased pre-trim mass with unknown trimming yield. Keep raw egg weighed without shells. Separate gryn inspection, cooling setup/oven heating, pan loading and centre-temperature checks from passive periods. Frozen lingonberries become a cooked compote; all milk, butter, berry juice and dressing are served.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith(('gulab-jamun', 'phirni')) and row['variant_id'] == 'extended':
        rename_ingredient(row, 'pistagenötter', 'rostade saltade pistaschkärnor')
        row['name'] += ' – med rostade saltade pistaschkärnor'
        for step in row['steps']:
            step['text'] = step['text'].replace('Hacka pistagenötterna', 'Hacka de uppvägda redan skalade, rostade och saltade pistaschkärnorna')
        changes.append('Explicit salted roasted shelled pistachio garnish at the unchanged 10 g dose. This is not an alias for raw unsalted pistachios or nuts weighed with shells. The separate manufacturer kernel page and exact retailer article/65 g package are reviewed.')
    if base.endswith('carne-en-su-jugo'):
        rename_ingredient(row, 'tomatillo', 'salsa verde av tomatillo')
        row['name'] += ' – med färdig tomatillosalsa'
        for component in row['components']:
            component['ingredients'] = [i for i in component['ingredients'] if i['name'] != 'salt']
            for item in component['ingredients']:
                if item['name'] == 'salsa verde av tomatillo':
                    item.update(form='as_sold', quantity=250, role='sauce', label='Färdig Salsa Verde av tomatillo, Clemente Jacques')
                elif item['name'] == 'limejuice':
                    item['quantity'] = 20
                elif item['name'] == 'sojasås':
                    item['quantity'] = 5
        for step in row['steps']:
            step['uses'] = [name for name in step['uses'] if name != 'salt']
        row['steps'][0]['text'] = 'Skär nötinnanlår i mycket tunna skivor tvärs fibrerna och därefter i små rutor. Tärna det rimmade fläsket. Skala lök och vitlök, väg den råa ätliga mängden och hacka. Väg upp den färdiga tomatillosalsan; den innehåller redan kryddor, soja, syra och salt.'
        row['steps'][2]['text'] = 'Mixa den uppvägda färdiga tomatillosalsan med gul lök, vitlök, limejuice, svartpeppar och 500 ml vatten. Häll i köttgrytan och koka upp. Tillsätt inget extra salt.'
        if row['variant_id'] != 'simple':
            row['steps'][2]['text'] += ' Mixa även ner den frysta hackade koriandern, chiliflakes och den lilla angivna mängden soja; koriandern genomkokas sedan med grytan.'
        row['steps'][4]['text'] = 'Skölj de redan kokta bönorna, låt rinna av och väg den angivna avrunna mängden. Värm i grytan fem minuter under omrörning. Kontrollera att köttet är mört och genomhettat; förläng kokningen vid behov. Såväl fläsk som färdig salsa och eventuell soja ger sälta; tillsätt inget extra salt.'
        row['steps'][-1]['text'] += ' Servera allt köttspad och allt utsmält fläskfett i grytan.'
        if row['variant_id'] == 'extended':
            row['steps'][5]['text'] = 'Använd de tinade avokadobitarna med all saft. Ansa rädisor och salladslök, väg de råa ätliga mängderna och skiva. Lägg på ett fat med avokadon.'
            prepend_thaw(row, 'avokado', 120, 'Behåll all avokadosaft och servera med grytan.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New prepared-salsa adaptation: 250 g Salsa Verde replaces 400 g raw tomatillo; not an edible-yield conversion. Omit 3 g added salt, reduce lime from 35 to 20 ml and optional soy from 15 to 5 ml because the salsa is already salted/acidified/seasoned. Use 500 ml process water instead of 650. Retain all meat juice/fat, weigh drained beans, cook frozen coriander and explicitly thaw frozen avocado with all juice.')
    if base.endswith('carlota-limon'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'evaporerad mjölk':
                    item.update(quantity=45, unit='g', label='Osötad evaporerad mjölk, vägd i gram')
        row['name'] += ' – med uppvägd osötad evaporerad mjölk'
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Vispa kondenserad och evaporerad mjölk', 'Väg den sötade kondenserade mjölken och den osötade evaporerade mjölken separat. Vispa båda')
        row['steps'][2]['text'] = 'Låt portionsglaset stå i kylskåp minst fyra timmar vid cirka 4 °C så kexen mjuknar och krämen sätter sig.'
        insert_step(row, 3, {'text': 'Täck portionsglaset och ställ direkt i kylskåp.', 'uses': ['kondenserad mjölk', 'evaporerad mjölk', 'mariekex'], 'minutes': 1, 'after': [2]})
        row['steps'].append({'text': 'Servera hela den lilla portionen direkt från kylen.', 'uses': ['mariekex'], 'minutes': 1, 'after': [len(row['steps'])]})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        if row['variant_id'] == 'extended':
            row['steps'][1]['text'] = row['steps'][1]['text'].replace('små mangotärningar mellan lagren', 'helt tinade mangobitar och all mangosaft mellan lagren')
            prepend_thaw(row, 'mango', 120, 'Behåll alla bitar och all saft till desserten.')
        changes.append('New authored dose 45 g unsweetened evaporated milk replaces 40 ml, not a density conversion. Keep sweetened condensed milk as a separate unchanged input. Frozen mango thaws with all juice; active covering/refrigeration and serving are separated from four-hour chilling.')
    if base.endswith('blodpalt'):
        row['steps'][0].update(text='Mät upp det helt tinade kalla nötblodet i ml och ställ tillbaka det i kylen. Tärna det rimmade fläsket smått. Skala potatisen, väg den angivna råa ätliga mängden och finriv. Pressa ur lös vätska genom en ren handduk till en skål.', minutes=10)
        insert_step(row, 2, {'text': 'Låt potatisvätskan stå orörd två minuter så stärkelsen sjunker.', 'uses': ['potatis'], 'minutes': 2, 'passive': True, 'after': [1]})
        insert_step(row, 3, {'text': 'Häll försiktigt bort den fria potatisvätskan men skrapa tillbaka all sedimenterad stärkelse till potatisen.', 'uses': ['potatis'], 'minutes': 1, 'after': [2]})
        mark_process(row, 3, ['potatis'], 'drain_before_cooking', 'Rå potatis pressas och fri vätska hälls bort medan sedimenterad stärkelse återförs. Kvarhållen vätska/näring har inget uppmätt utbyte.')
        row['steps'][6].update(text='Sjud paltarna försiktigt cirka 45 minuter. De ska ligga fritt i en stor gryta eller två grytor utan att klämmas ihop.', minutes=45, passive=True)
        insert_step(row, 7, {'text': 'Lägg paltarna försiktigt i det sjudande vattnet och lossa dem från botten med hålslev.', 'uses': ['potatis', 'nötblod', 'rimmat fläsk'], 'minutes': 3, 'after': [6]})
        insert_step(row, 9, {'text': 'Kontrollera minst 75 °C mitt i en palt, även i fläskfyllningen. Degens mitt ska sakna rå mjölrand; fortsätt sjuda om det behövs.', 'uses': ['nötblod', 'rimmat fläsk', 'rågmjöl', 'vetemjöl'], 'minutes': 2, 'after': [8]})
        row['steps'][-1]['text'] += ' Allt eventuellt löksmör och all lingonvätska serveras. Kokvattnet används inte.'
        mark_process(row, len(row['steps']), ['potatis', 'nötblod', 'salt'], 'drain_after_cooking', 'Palt lyfts ur saltat kokvatten. Kvarhållen mängd salt och näring är okänd; inget kokutbyte antas.')
        for step in row['steps']:
            if step['text'].startswith('Värm lingonen'):
                step['text'] = step['text'].replace('Värm lingonen', 'Värm de uppvägda frysta lingonen').replace('en minut', 'minst en minut eller längre enligt förpackningen')
            if step['text'].startswith('Strimla kålen'):
                step['text'] = 'Ansa kålen och kärna ur äpplet, väg sedan de råa ätliga mängderna. Strimla och vänd med all vinäger. Servera även saften.'
        row['steps'] = [
            {'text': 'Flytta förpackningen med fryst nötblod till ett läckagesäkert kärl i kylskåpet.', 'uses': ['nötblod'], 'minutes': 1},
            {'text': 'Tina nötblodet helt i kylskåp enligt förpackningen. Planera tolv timmar och förläng vid behov. Håll det kallt och använd inom förpackningens anvisade tid; det ska inte användas rått.', 'uses': ['nötblod'], 'minutes': 720, 'passive': True},
            *row['steps']]
        for process in row['unmeasured_processes']:
            process['step'] += 2
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Retain the authored 250 ml raw food-grade frozen bovine blood without mass/density conversion. Explicit fridge thaw, peeled raw potato weighing, separate starch sedimentation/pouring, palt loading and 75 C centre checks. Both squeezed potato liquid and salted cooking-water losses remain unmeasured; all lingon juice and optional butter are served.')
    if base.endswith('janssons-frestelse'):
        rename_ingredient(row, 'svensk ansjovis med spad', 'svensk ansjovis')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'svensk ansjovis':
                    item.update(quantity=158, form='preserved_drained', label='Svensk ansjovisfilé, avrunnen utan extra spad')
        row['name'] += ' – med avrunnen ansjovis utan extra spad'
        row['steps'][0]['text'] = 'Sätt ugnen på 175 °C över-/undervärme. Skala potatisen och väg den angivna råa ätliga mängden. Skär i cirka 3 mm tunna strimlor utan att skölja bort stärkelsen. Skala och skiva den uppvägda löken. Låt ansjovisfiléerna rinna av och väg 158 g utan fri lag, motsvarande två deklarerade 79 g-mängder; dela grovt. Spadet används inte i denna version.'
        row['steps'][2]['text'] = row['steps'][2]['text'].replace(' samt allt ansjovisspad', '').replace('fisken och spadet är salta', 'fisken är salt')
        row['steps'][3].update(text='Grädda gratängen i nedre delen av ugnen i 60 minuter.', minutes=60)
        insert_step(row, 5, {'text': 'Kontrollera gratängens yta och täck löst med folie om den blivit mörk.', 'uses': ['potatis'], 'minutes': 2, 'after': [4]})
        insert_step(row, 6, {'text': 'Grädda ytterligare 40 minuter. Vätskan ska bindas till en krämig sås.', 'uses': ['potatis', 'grädde'], 'minutes': 40, 'passive': True, 'after': [5]})
        insert_step(row, 7, {'text': 'Kontrollera med sticka att samtliga potatislager är helt mjuka; förläng annars gräddningen. Ta ut formen.', 'uses': ['potatis'], 'minutes': 1, 'after': [6]})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
            if step['text'].startswith('Strimla grönkålen'):
                step['text'] = 'Lägg den uppvägda frysta hackade grönkålen direkt i pannan med tillbehörets smör och 60 ml vatten. Genomhetta under omrörning minst tio minuter eller längre enligt förpackningen. Låt vattnet koka in; servera all kål och allt smör.'
            if step['text'].startswith('Skala och riv rödbetan'):
                step['text'] = 'Skala rödbetan och kärna ur äpplet, väg därefter respektive råa ätliga mängd. Riv rödbetan och skär äpplet i tunna stavar. Vänd med all vinäger och servera hela salladen med saften.'
        changes.append('New visible drained-anchovy version: 158 g declared drained sprat replaces 220 g fish-plus-brine. Extra brine is omitted without inventing an equivalence or nutrient yield. Source already declares drained 79 g, so purchasing must not apply another drained fraction. Weigh peeled potato, use frozen kale explicitly, count oven inspection separately and retain all butter/cream/dressing.')
    if base.endswith('gubbrora-ansjovis'):
        rename_ingredient(row, 'kokta ägg', 'ägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ägg':
                    item.update(quantity=2, unit='st', form='as_sold', label='Hela råa ägg med skal, räknade före kokning')
                if item['name'] == 'dill':
                    item['requirements'] = ['frozen']
        row['method'] = 'pot'
        row['name'] += ' – med nykokta och kylda ägg'
        herbs = ['dill'] + (['gräslök'] if row['variant_id'] == 'extended' else [])
        prefix = [
            {'text': 'Lägg de hela råa äggen i en kastrull med kallt vatten så de täcks. Koka upp.', 'uses': ['ägg'], 'minutes': 5},
            {'text': 'Sjud äggen tolv minuter så vitan och gulan blir fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
            {'text': 'Häll av kokvattnet och lägg äggen i kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Låt äggen svalna i det kalla vattnet fem minuter.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Skala äggen, skölj bort eventuella skalrester och tärna dem med rena redskap. Lägg på en ren tallrik i kylskåp.', 'uses': ['ägg'], 'minutes': 4},
            {'text': 'Koka de frysta hackade örterna med 15 ml vatten under omrörning minst tre minuter eller längre enligt förpackningen. Häll hela mängden i en ren liten skål och ställ i kylskåp.', 'uses': herbs, 'minutes': 4},
            {'text': 'Låt ägg och örter kallna helt i kylskåp, uppskattningsvis 30 minuter. Förläng tills båda är högst 8 °C innan de blandas med den kalla röran.', 'uses': ['ägg', *herbs], 'minutes': 30, 'passive': True},
        ]
        row['steps'][0].update(text='Låt ansjovisfiléerna rinna av utan att skölja, väg den angivna avrunna mängden och hacka fint.', uses=['svensk ansjovis'], minutes=2)
        row['steps'][1]['text'] = 'Finhacka den skalade uppvägda rödlöken. Rör ihop med crème fraiche och hela den kalla örtblandningen med vätskan.' + (' Rör också i senapen.' if row['variant_id'] == 'extended' else '') + ' Vänd ner de kalla tärnade äggen och ansjovisen. Inget extra salt ingår.'
        row['steps'] = prefix + row['steps']
        mark_process(row, 5, ['ägg'], 'peel_after_cooking', 'Två råa hela ägg kokas och skalas. Ingen rå eller kokt styckvikt eller skalandel antas.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New dose two raw shell eggs replaces 80 g ready-boiled egg; no equivalence is claimed. The hot cooking and subsequent cold chain are explicit, with counted peeling/cooling. Frozen herbs are cooked, cooled and retained with all liquid. Declared drained sprat remains 25 g; no gross-weight or sardell alias.')
    if base.endswith(('pasta-amatriciana', 'pasta-cacio-pepe')):
        rename_ingredient(row, 'pecorino romano', 'lagrad pecorino')
        row['name'] += ' – med lagrad pecorino'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'lagrad pecorino':
                    item.update(quantity=75 if base.endswith('amatriciana') else 150,
                                label='Lagrad pecorino i bit, vägd före ansning')
        insert_step(row, 1, {'text': 'Väg ostbiten före ansning. Skär bort eventuell hård ytkant och finriv all återstående ost. Här används lagrad pecorino av fårmjölk; osten är inte verifierad som Pecorino Romano.',
                            'uses': ['lagrad pecorino'], 'minutes': 5, 'after': []})
        mark_process(row, 1, ['lagrad pecorino'], 'trim_before_cooking', 'Inköpt ostbit vägs före eventuell bortskärning av ytkant. Kvarvarande mängd och dess näring är inte uppmätta.')
        for index, step in enumerate(row['steps'], 1):
            if index == 1:
                continue
            step['text'] = step['text'].replace('Finriv pecorino.', 'Använd den redan finrivna lagrade pecorinon.').replace('Riv pecorinon mycket fint i en rymlig värmetålig skål.', 'Lägg den redan finrivna lagrade pecorinon i en rymlig värmetålig skål.')
            if ('häll' in step['text'].lower() and ('kokvatten' in step['text'] or 'kokvattnet' in step['text'])
                    and ('häll sedan av' in step['text'] or 'hälls av' in step['text'])):
                mark_process(row, index, ['pasta', 'salt'], 'drain_after_cooking', 'En del saltat stärkelsevatten sparas till såsen och resten hälls bort. Saltets och stärkelsens kvarhållna mängd är okänd.')
                step['passive'] = False
            if step['text'].startswith('Tärna guanciale'):
                step['text'] += ' Behåll allt utsmält fett i såsen.'
            if step['text'].startswith('Rör ner chiliflakes'):
                step['passive'] = False
                step['text'] += ' Rör regelbundet under sjudningen.'
            if 'Hacka persilja' in step['text']:
                step.update(text='Väg de redan kokta vita bönorna efter sköljning och avrinning. Koka fryst hackad persilja med 20 ml vatten under omrörning i minst tre minuter eller längre enligt förpackningen. Vänd hela mängden med bönorna, citronjuice och bönkomponentens olivolja och servera ljummet.', minutes=8)
                row['name'] += ' och ljumma persiljebönor'
            step['after'] = [index - 1]
        changes.append('Explicit aged-sheep-cheese alternative, not a Romano identity alias. New gross doses 75 g (amatriciana) / 150 g (cacio e pepe) replace 65 / 140 g, without edible-yield equivalence. Trimmed rind and discarded salted pasta water carry unknown retention. Count grating, draining and regular stirring as active work; frozen parsley is cooked in the visible warm side.')
    if base.endswith('torta-ahogada'):
        rename_ingredient(row, 'surdegsfralla med hård skorpa', 'surdegsfralla')
        row['name'] += ' – med svensk surdegsfralla'
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'surdegsfralla':
                    item.update(quantity=320, label='Färdigbakade svenska surdegsfrallor, 4 × 80 g')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Koka upp, skumma och sänk värmen.', 'Koka upp och sänk värmen; skumma inte bort något.')
        row['steps'][1].update(text='Sjud köttet under lock i 55 minuter.', minutes=55, passive=True)
        insert_step(row, 3, {'text': 'Vänd köttbitarna och kontrollera spadet. Tillsätt 100 ml vatten om det behövs så grytan inte kokar torr.', 'uses': ['fläskkarré'], 'minutes': 2, 'after': [2]})
        insert_step(row, 4, {'text': 'Sjud ytterligare 55 minuter under lock. Köttet ska bli helt genomlagat och mycket mört.', 'uses': ['fläskkarré'], 'minutes': 55, 'passive': True, 'after': [3]})
        row['steps'][4]['text'] = 'Kontrollera att köttet är minst 72 °C och faller isär lätt; förläng annars sjudningen. Lyft upp och dra i fibrer. Kokspadet används inte i denna version. Bryn allt kött i köttets rapsolja under omrörning i tio minuter; behåll oljan och köttsaften i fyllningen.'
        row['steps'][4]['minutes'] = 15
        mark_process(row, 5, ['fläskkarré', 'salt'], 'drain_after_cooking', 'Saltat kokspad blir över och serveras inte. Köttets kvarhållna vätska, salt och näring är okända.')
        index = len(row['steps'])
        insert_step(row, index, {'text': 'Sätt ugnen på 200 °C och lägg de färdigbakade surdegsfrallorna på galler. Brödet är en svensk anpassning, inte traditionellt birote. Använd inte rå deg eller ogräddat fryst bakeoffbröd.', 'uses': ['surdegsfralla'], 'minutes': 2, 'after': [index - 1]})
        insert_step(row, index + 1, {'text': 'Låt ugnen bli varm, cirka tio minuter.', 'uses': [], 'minutes': 10, 'passive': True, 'after': [index]})
        insert_step(row, index + 2, {'text': 'Sätt in frallorna i ugnen.', 'uses': ['surdegsfralla'], 'minutes': 1, 'after': [index + 1]})
        insert_step(row, index + 3, {'text': 'Värm frallorna fem minuter tills ytan är frasig; de är redan färdigbakade.', 'uses': ['surdegsfralla'], 'minutes': 5, 'passive': True, 'after': [index + 2]})
        row['steps'][-1]['text'] = 'Ta ut brödet. ' + row['steps'][-1]['text'] + ' Fördela även all eventuell limejuice från löken över fyllningen.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Explicit Swedish baked sourdough roll instead of unverified hard-crust birote. New bread dose 320 g (four declared 80 g rolls) replaces 400 g, no conversion. Discarded salted pork broth has unknown retention. Separate mid-simmer inspection and bread reheating steps; keep frying oil and pickle juice in the served filling.')
    if base.endswith('murgh-musallam'):
        rename_ingredient(row, 'kokta ägg', 'ägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ägg':
                    item.update(quantity=4, unit='st', form='as_sold', label='Råa hela hönsägg med skal, räknade före kokning')
                if item['name'] == 'hel kyckling':
                    item.update(quantity=1350, label='Hel rå kyckling, bruttovikt inklusive ben och skinn')
        row['name'] += ' – med hel rå kyckling och nykokta ägg'
        row['steps'][0]['text'] = 'Välj en hel rå kyckling nära ingredienslistans bruttovikt. Butikens vikt är uppskattad; kontrollera faktisk vikt och kostnad. ' + row['steps'][0]['text'] + ' Diska råkycklingredskap och tvätta händerna.'
        row['steps'][0]['minutes'] += 3
        row['steps'][1]['text'] = 'Täck och marinera i kylskåp i två timmar.'
        for step in row['steps']:
            step['text'] = step['text'].replace('de redan kokta äggen', 'de nykokta skalade äggen')
            step['text'] = step['text'].replace('russin och koriander', 'russin och fryst hackad koriander; hela fyllningen ska genomhettas')
        row['steps'][-2:-1] = [
            {'text': 'Ugnstillaga fågeln täckt vid 175 °C i cirka 85 minuter.', 'uses': ['hel kyckling', 'ägg', 'ris'], 'minutes': 85, 'passive': True},
            {'text': 'Ta försiktigt av locket; skydda händerna mot ånga.', 'uses': ['hel kyckling'], 'minutes': 1},
            {'text': 'Fortsätt ugnstillagningen utan lock cirka 25 minuter för färg.', 'uses': ['hel kyckling'], 'minutes': 25, 'passive': True},
            {'text': 'Mät innerst i låret utan benkontakt och mitt i fyllningen, även eventuell separat fyllningsform. Samtliga ska nå minst 74 °C. Förläng tillagningen om någon mätpunkt är kallare.', 'uses': ['hel kyckling', 'ägg', 'ris'], 'minutes': 2},
        ]
        row['steps'][-1].update(text='Låt fågeln vila 15 minuter.', minutes=15, passive=True)
        row['steps'].append({'text': 'Ta bort snöret, lyft ur fyllningen och lossa allt ätligt kött och skinn från benen. Kontrollera små ben. Fördela kött, skinn, all fyllning och allt genomkokt spad eller sås mellan portionerna; benen serveras inte.', 'uses': ['hel kyckling', 'ägg', 'ris'], 'minutes': 10})
        eggs = [
            {'text': 'Lägg det angivna antalet råa hela ägg i en kastrull med 1000 ml vatten och koka upp försiktigt.', 'uses': ['ägg'], 'minutes': 5},
            {'text': 'Sjud äggen tolv minuter från uppkok tills vita och gula blir helt fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
            {'text': 'Häll av det heta vattnet och tillsätt 1000 ml kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Låt svalna fem minuter så att äggen går att skala.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Skala äggen och kasta skalen. Kontrollera fasta gulor och vitor; alla kokta ägg används utan antagen gramvikt.', 'uses': ['ägg'], 'minutes': 4},
        ]
        row['steps'][2:2] = eggs
        mark_process(row, 7, ['ägg'], 'peel_after_cooking', 'Ägg köps och doseras som antal före kokning. Skalen avlägsnas och ingen rå eller kokt styckvikt antas.')
        mark_process(row, len(row['steps']), ['hel kyckling'], 'remove_bones_after_cooking', 'Kycklingens inköpta bruttovikt innehåller ben. Allt ätligt kött, skinn och sky serveras; benens andel och tillagat utbyte är okända.')
        changes.append('Visible new dose: 1350 g whole raw chicken replaces 1600 g, and four raw shell eggs replace 120 g ready-cooked egg. Neither is a yield conversion. Whole source package mass stays estimated; bone/shell losses remain unknown. Count cleanup, egg cooking/peeling, lid removal, temperature checks and carving separately from waiting. Both bird and stuffing must reach 74 C.')
    if base.endswith('coda-vaccinara'):
        if row['variant_id'] != 'simple':
            rename_ingredient(row, 'vitt vin', 'vitt matlagningsvin')
            row['name'] += ' – med vitt matlagningsvin'
            row['steps'][2]['text'] = row['steps'][2]['text'].replace('vitt vin', 'vitt matlagningsvin')
        periods = []
        for turn in range(6):
            periods.append({'text': 'Sjud oxsvansen under lock på låg värme i 30 minuter.', 'uses': ['oxsvans med ben'], 'minutes': 30, 'passive': True})
            if turn < 5:
                periods.append({'text': 'Kontrollera vätskan och rör varsamt. Tillsätt vid behov 150 ml vatten så att bottnen inte kokar torr.', 'uses': ['oxsvans med ben'], 'minutes': 1})
        periods[-1]['text'] += ' Efter totalt cirka 180 minuter ska köttet börja lossna från benen; förläng om det fortfarande är segt.'
        row['steps'][3:4] = periods
        for index, step in enumerate(row['steps'], 1):
            if step['text'].startswith('Sjud utan heltäckande'):
                step['passive'] = False
            if step['text'].startswith('Ta upp köttbitarna'):
                mark_process(row, index, ['oxsvans med ben'], 'remove_bones_after_cooking', 'Oxsvans köps med ben som bruttovikt. Ben avlägsnas efter långkok; ingen ätlig andel eller tillagad vikt antas.')
        changes.append('Keep whole source oxtail mass including bones and its estimated variable-weight purchase; do not infer edible yield. Explicit bone removal carries unknown served nutrition. Standard/extended use visibly named cooking wine. Schedule five liquid checks during three hours and count the final regularly stirred reduction as active work.')
    if base.endswith('flasklagg-rotmos'):
        rename_ingredient(row, 'rimmat fläsklägg med ben', 'rimmat fläsklägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'rimmat fläsklägg':
                    item.update(quantity=1500, label='Rå rimmad fläsklägg, bruttovikt före borttagning av eventuella ben och seg svål')
        row['name'] += ' – med rå rimmad lägg'
        row['steps'][0]['text'] = 'Använd rå rimmad fläsklägg, med eller utan ben, nära den angivna vikten före putsning. Kontrollera faktisk vikt och kostnad. ' + row['steps'][0]['text']
        row['steps'][1:2] = [
            {'text': 'Sjud läggen försiktigt under lock i 60 minuter.', 'uses': ['rimmat fläsklägg'], 'minutes': 60, 'passive': True},
            {'text': 'Kontrollera vätskan och vänd läggen. Fyll vid behov på med 300 ml vatten.', 'uses': ['rimmat fläsklägg'], 'minutes': 1},
            {'text': 'Sjud ytterligare 60 minuter.', 'uses': ['rimmat fläsklägg'], 'minutes': 60, 'passive': True},
            {'text': 'Kontrollera och vänd igen; fyll vid behov på med 300 ml vatten.', 'uses': ['rimmat fläsklägg'], 'minutes': 1},
            {'text': 'Sjud ytterligare omkring 60 minuter, tills köttet är mycket mört och lätt delas med gaffel, eller lossnar från ben om ben ingår. Förläng vid behov.', 'uses': ['rimmat fläsklägg'], 'minutes': 60, 'passive': True},
        ]
        for step in row['steps']:
            step['text'] = step['text'].replace('Skala och tärna kålrot, morot och potatis.', 'Skala kålrot, morot och potatis, väg de råa ätliga mängderna och tärna.')
            step['text'] = step['text'].replace('avlägsna ben och seg svål', 'avlägsna eventuella ben och seg svål')
            if step['text'].startswith('Koka rotfrukterna'):
                step['text'] = 'Koka rotfrukterna mjuka cirka 30 minuter.'
        index = next(n for n, step in enumerate(row['steps'], 1) if step['text'].startswith('Koka rotfrukterna'))
        insert_step(row, index + 1, {'text': 'Häll av rotfrukterna och spara kokvätskan separat till spädning av moset.', 'uses': ['kålrot', 'morot', 'potatis'], 'minutes': 2})
        for index, step in enumerate(row['steps'], 1):
            if 'Ta upp lagerbladen' in step['text']:
                mark_process(row, index, ['lagerblad'], 'remove_after_infusion', 'Lagerblad kokar med och tas upp. Överföring till kokspadet är inte uppmätt.')
            if step['text'].startswith('Mosa rotfrukterna'):
                mark_process(row, index, ['rimmat fläsklägg'], 'remove_bones_after_cooking', 'Eventuella ben och seg svål tas bort från köttet. Förpackningens bruttovikt omvandlas inte till en påhittad ätlig vikt.')
        mark_process(row, len(row['steps']), ['rimmat fläsklägg', 'kålrot', 'morot', 'potatis', 'kryddpeppar'], 'drain_after_cooking', 'Endast kokspad som faktiskt används till moset serveras. Resterande lag och rotfruktsvatten är processrester med okänd salt- och näringsfördelning.')
        changes.append('New culinary dose 1500 g gross raw cured hock replaces 2200 g bone-in hock. Moab makes bone-in and boneless hock; the source label does not establish which, so the recipe explicitly handles either and removes any bones/tough skin. No bone or nutrient yield is inferred. Preserve salted broth use/discard and bay removal as unknown losses; count checks and draining as active work.')
    if base in STAGES[13]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith('dal-baati'):
        row['name'] += ' – med röda linser och smör'
        row['steps'][3:4] = [
            {'text': 'Baka brödbollarna i 20 minuter.', 'uses': ['grahamsmjöl', 'vetemjöl', 'smör'], 'minutes': 20, 'passive': True},
            {'text': 'Vänd brödbollarna försiktigt på plåten.', 'uses': ['grahamsmjöl', 'vetemjöl', 'smör'], 'minutes': 1},
            {'text': 'Baka ytterligare 20 minuter, totalt omkring 40 minuter. Bröden ska ha rostad yta och vara genomgräddade utan rå mjöldeg i mitten; förläng vid behov.', 'uses': ['grahamsmjöl', 'vetemjöl', 'smör'], 'minutes': 20, 'passive': True},
        ]
        simmer = next(step for step in row['steps'] if step['text'].startswith('Sjud 25 minuter'))
        simmer.update(passive=False, text='Sjud dalen cirka 25 minuter och rör regelbundet så att den inte fastnar. Linserna ska vara helt mjuka. Tillsätt 150 ml vatten om blandningen blir för fast; all dal och vätska serveras.')
        changes.append('Keep the explicit simple red-lentil and butter adaptation; do not alias chana dal or urad. Count bread turning and regular dal stirring as active work. All butter and dal are retained.')
    if base.endswith('salpicon-de-res'):
        rename_ingredient(row, 'nötkött', 'högrev')
        row['name'] += ' – med långkokt högrev'
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('nötköttet', 'den benfria högreven')
        row['steps'][1:2] = [
            {'text': 'Sjud högreven under lock på låg värme i 75 minuter.', 'uses': ['högrev'], 'minutes': 75, 'passive': True},
            {'text': 'Kontrollera vätskan och vänd köttbitarna. Tillsätt vid behov 200 ml vatten så att grytan inte kokar torr.', 'uses': ['högrev'], 'minutes': 1},
            {'text': 'Sjud ytterligare cirka 75 minuter, totalt 150 minuter. Köttet ska gå lätt att dra isär med två gafflar; förläng om det är segt.', 'uses': ['högrev'], 'minutes': 75, 'passive': True},
        ]
        pull = row['steps'][4]
        pull['text'] = pull['text'].replace('Bred ut i ett rent grunt kärl.', 'Bred ut i ett rent grunt kärl; kvarvarande kokspad serveras inte.')
        if row['variant_id'] != 'simple':
            pull['text'] = pull['text'].replace('Bred ut', 'Koka den frysta hackade koriandern med 20 ml vatten i en liten kastrull minst tre minuter eller längre enligt förpackningen. Blanda all koriander och vätska med det varma köttet. Bred ut')
            pull['minutes'] += 4
            pull['uses'].append('koriander')
        mark_process(row, 5, ['högrev', 'salt'], 'drain_after_cooking', 'Köttet lyfts ur saltat kokspad som inte serveras. Saltöverföring, vätskeutbyte och näringsförluster är inte uppmätta.')
        row['steps'][5]['text'] = 'Kyl köttet i vattenbad 15 minuter. Badvattnet ska inte komma i maten.'
        row['steps'][5]['minutes'] = 15
        insert_step(row, 7, {'text': 'Täck kärlet och flytta det till kylskåp vid 4 °C.', 'uses': ['högrev'], 'minutes': 1})
        insert_step(row, 8, {'text': 'Kyl ytterligare cirka 45 minuter tills köttet är högst 8 °C; förläng vid behov. Låt det inte stå på köksbänken.', 'uses': ['högrev'], 'minutes': 45, 'passive': True})
        for step in row['steps']:
            if step['text'].startswith('Skär avokado'):
                step['text'] = step['text'].replace('Skär avokado och rädisa i små bitar.', 'Använd de tinade avokadobitarna med all saft och skär rädisan smått.').replace('och koriander i salladen', 'i salladen; koriandern är redan kokt och kyld med köttet')
            if step['text'].startswith('Koka fryst majs'):
                step['text'] += ' Väg bönorna efter avrinning och kontrollera att majsen är helt kall före blandning.'
                mark_process(row, row['steps'].index(step) + 1, ['majs'], 'drain_after_cooking', 'Majsens kokvatten hälls bort; vätske- och näringsförlusten är inte uppmätt.')
        if row['variant_id'] != 'simple':
            prepend_thaw(row, 'avokado', 120, 'Använd hela mängden och all saft i salladen.')
            for process in row['unmeasured_processes']:
                process['step'] += 2
        changes.append('Specify reviewed boneless chuck for shreddable beef, with a visible title. Keep discarded salted broth under unknown loss; separate simmer inspection and fridge transfer from passive waiting. Frozen coriander cooks before chilling with the beef; frozen avocado thaws with all juice. Extended corn draining is also unmeasured.')
    if base.endswith('inkokt-lax'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] in {'lax', 'dill'}:
                    item['requirements'] = list(dict.fromkeys([*vocabulary[f"{item['name']}|{item['form']}"][1], 'frozen']))
        row['steps'][0]['text'] = 'Använd upptinad benfri och skinnfri lax. Häll all upptiningssaft i lagen och koka upp den ordentligt före fisken. Använd fryst hackad dill direkt i lagen. ' + row['steps'][0]['text']
        row['steps'][1]['text'] = 'Sjud laxen mycket försiktigt cirka tolv minuter. Mitten av den tjockaste biten ska nå minst 63 °C; förläng vid behov. Syra ersätter inte tillagning.'
        insert_step(row, 2, {'text': 'Lägg försiktigt laxen i den heta lagen och sänk värmen.', 'uses': ['lax'], 'minutes': 1})
        transfer = row['steps'][3]
        transfer['text'] = transfer['text'].replace('Byt till nytt kallt badvatten när det blir varmt.', '')
        row['steps'][4:5] = [
            {'text': 'Låt de grunda kärlen kylas i det kalla vattenbadet i 15 minuter.', 'uses': ['lax'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera temperaturen och byt badvattnet mot 4000 ml nytt kallt vatten.', 'uses': ['lax'], 'minutes': 2},
            {'text': 'Låt kylas ytterligare 15 minuter i vattenbadet.', 'uses': ['lax'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera att portionerna inte längre är varma. Täck och flytta till kylskåp vid 4 °C; fortsätt aktiv kylning om de fortfarande är varma.', 'uses': ['lax'], 'minutes': 2},
        ]
        for step in row['steps']:
            if step['text'].startswith('Skala potatisen'):
                step['text'] = step['text'].replace('och skär den', 'och väg den angivna råa ätliga mängden. Skär den')
            if step['text'].startswith('Sjud potatisen'):
                step['text'] = 'Sjud potatisen omkring 20 minuter tills en sticka går lätt igenom.'
        index = next(n for n, step in enumerate(row['steps'], 1) if step['text'].startswith('Hacka såsens dill'))
        insert_step(row, index, {'text': 'Häll av potatisens saltade kokvatten och håll potatisen varm över 60 °C under lock.', 'uses': ['potatis', 'salt'], 'minutes': 2})
        mark_process(row, index, ['potatis', 'salt'], 'drain_after_cooking', 'Saltat potatisvatten hälls bort. Upptag av salt och förlust till vattnet är inte uppmätta.')
        index += 1
        row['steps'][index - 1]['text'] = row['steps'][index - 1]['text'].replace('Hacka såsens dill och rör ihop', 'Rör ihop den helt kalla kokta dillen och all dillvätska')
        insert_step(row, index, {'text': 'Koka såsens frysta hackade dill med 20 ml vatten minst tre minuter eller längre enligt förpackningen. Häll hela mängden i en ren grund skål och ställ i kylskåp.', 'uses': ['dill'], 'minutes': 4})
        insert_step(row, index + 1, {'text': 'Låt dillen och all vätska kallna helt i kylskåp, uppskattningsvis 30 minuter; förläng om den ännu är varm.', 'uses': ['dill'], 'minutes': 30, 'passive': True})
        broth = ['lax', 'gul lök', 'dill', 'ättiksprit 12 procent', 'strösocker', 'salt']
        if row['variant_id'] != 'simple':
            broth += ['morot', 'lagerblad']
            mark_process(row, 4, ['lagerblad'], 'remove_after_infusion', 'Lagerblad plockas bort efter sjudningen; överföringen till lagen är inte uppmätt.')
        mark_process(row, len(row['steps']), broth, 'drain_after_cooking', 'Fisken lyfts ur inläggningslagen före servering. Lagen är processvätska med okänd överföring av salt, socker och övrig näring.')
        prepend_thaw(row, 'lax', 720, 'Koka all upptiningssaft i lagen före fisken.')
        for process in row['unmeasured_processes']:
            process['step'] += 2
        changes.append('Require frozen salmon/dill explicitly, thaw salmon and boil its juice in the discarded poaching liquid. Keep actual discarded sweet-sour brine, bay removal and salted potato water under unknown-loss metadata. Frozen sauce dill cooks and chills before mixing. Active loading, bath-water changes, fridge transfer and draining are separately scheduled.')
    if base in STAGES[12]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith('phirni'):
        row['steps'][1]['text'] = 'Blötlägg riset 30 minuter.'
        row['steps'][2]['text'] = 'Häll bort blötläggningsvattnet. ' + row['steps'][2]['text']
        row['steps'][2]['minutes'] += 1
        row['steps'][6]['text'] = 'Låt skålen svalna 15 minuter i det kalla vattenbadet.'
        row['steps'][7]['text'] = 'Kyl cirka 90 minuter tills puddingen är helt kall och har satt sig.'
        insert_step(row, 7, {'text': 'Ställ skålen i ett kallt vattenbad med 500 ml vatten utan att vatten går i puddingen.', 'uses': ['mjölk', 'ris'], 'minutes': 1})
        insert_step(row, 9, {'text': 'Flytta skålen till kylskåp; låt den inte stå kvar på köksbänken.', 'uses': ['mjölk', 'ris'], 'minutes': 1})
        row['steps'].append({'text': 'Servera hela den kalla portionsskålen.', 'uses': ['mjölk', 'ris'], 'minutes': 1})
        changes.append('Preserve raw-ground-rice method and all cooked cream. Count draining, water-bath setup, fridge transfer and serving as active work rather than hiding them inside passive cooling.')
    if base.endswith('hor-mok-pla'):
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('Kontrollera att fisken är benfri.', 'Använd den upptinade benfria fisken och behåll all upptiningssaft i fiskmassan. Knäck ägg och väg den råa mängden utan skal.')
        row['steps'][3:4] = [
            {'text': 'Ställ skålarna stadigt i ånginsatsen och lägg på locket.', 'uses': ['fisk', 'ägg'], 'minutes': 2},
            {'text': 'Ånga under lock i 15 minuter.', 'uses': ['fisk', 'ägg'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera vattnet under insatsen. Fyll vid behov på med 300 ml kokande vatten utan att hälla i maten. Lägg tillbaka locket.', 'uses': [], 'minutes': 1},
            {'text': 'Ånga ytterligare 15 minuter, totalt cirka 30 minuter.', 'uses': ['fisk', 'ägg'], 'minutes': 15, 'passive': True},
            {'text': 'Kontrollera att krämen stannat och att mitten av samtliga skålar nått minst 72 °C. Förläng ångningen vid behov; servera aldrig rå fisk-äggkräm.', 'uses': ['fisk', 'ägg'], 'minutes': 2},
        ]
        mark_process(row, 3, ['vitkål'], 'drain_after_cooking', 'Kålen ångas och får rinna av före fyllning. Vätske- och näringsförlusten är inte uppmätt.')
        prepend_thaw(row, 'fisk', 720, 'Blanda all upptiningssaft i fiskmassan; hela massan ska genomhettas till minst 72 °C.')
        row['unmeasured_processes'][0]['step'] += 2
        changes.append('Explicit frozen-fish thaw, all juice cooked in the custard, and shell-free raw egg weight. Mark steamed-cabbage draining as unknown loss. Schedule steamer loading, water inspection and final temperature checks as active work.')
    if base.endswith('kluai-buat-chi'):
        row['steps'][1]['text'] = row['steps'][1]['text'].replace('Dela bananen', 'Skala bananen, väg den angivna ätliga mängden och dela den')
        row['steps'][2].update(text='Låt svalna lite före servering.', passive=True)
        row['steps'].append({'text': 'Servera alla bananbitar och hela kokosmjölksåsen ljumma.', 'uses': ['banan', 'kokosmjölk'], 'minutes': 1})
        changes.append('Weigh peeled edible banana, keep all coconut sauce, and separate passive cooling from serving.')
    if base.endswith('pasticciotto-leccese'):
        row['name'] += ' – mördeg med smör'
        row['steps'][3]['text'] = 'Kyl krämen i kylskåp cirka 35 minuter tills den är helt kall och inte smälter smöret vid fyllning.'
        insert_step(row, 4, {'text': 'Bred krämen i en ren grund skål och täck direkt mot ytan före kylningen.', 'uses': ['mjölk', 'äggula', 'majsstärkelse'], 'minutes': 2})
        row['steps'][-1]['text'] = 'Låt bakverket svalna på galler 20 minuter; fyllningen kan annars bränna.'
        row['steps'].append({'text': 'Lossa försiktigt formen och servera hela bakverket ljummet.', 'uses': ['vetemjöl', 'äggula'], 'minutes': 1})
        insert_step(row, 1, {'text': 'Knäck rena hönsägg och separera gula och vita utan tillsatser. Väg rå äggula utan skal separat till deg och kräm. Oanvänd vita och gula är separata rester; komplettera inköpet om det faktiska utbytet är mindre än uppskattningen.', 'uses': ['äggula'], 'minutes': 3})
        changes.append('Use the existing reviewed egg-separation method with explicitly weighed raw yolks, no fixed yolk count or exact yield. Preserve the authored butter shortcrust adaptation and separate cream transfer/unmoulding from cooling.')
    if base.endswith('sopa-de-lima'):
        mark_process(row, 4, ['rapsolja', 'majstortillas'], 'deep_fry_and_drain', 'Tortillastrimlor steks och lyfts upp på galler; kvarvarande olja serveras inte. Upptagen oljemängd är okänd, medan hela insatsen måste köpas.')
        if row['variant_id'] != 'simple':
            row['name'] += ' – med lime och grapefrukt'
            row['steps'][4]['text'] = row['steps'][4]['text'].replace('Finhacka det helt hinnfria grapefruktköttet', 'Skala grapefrukten och ta bort hinnorna. Väg den angivna ätliga mängden och finhacka den')
            row['steps'][4]['minutes'] += 3
        if row['variant_id'] == 'extended':
            row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('Tärna avokadon.', 'Använd de tinade avokadobitarna med all saft.')
            prepend_thaw(row, 'avokado', 120, 'Använd hela mängden i soppan vid servering.')
            row['unmeasured_processes'][0]['step'] += 2
        changes.append('Keep the source-authored real oil input and discarded pan remainder with unknown uptake. Standard/extended visibly name the lime-grapefruit adaptation and weigh peeled flesh; extended frozen avocado is thawed with all juice.')
    if base in STAGES[10]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith('bohuslansk-aggost'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'filmjölk':
                    item.update(quantity=42, unit='g', label='Filmjölk, uppvägd i gram')
                if item['name'] == 'jordgubbar':
                    item['label'] = 'Frysta ansade jordgubbar, hela mängden och saften används'
        row['name'] = row['name'].replace('färska bär', 'tinade bär')
        row['steps'][0]['text'] = 'Knäck ägg och väg den råa mängden utan skal. Väg filmjölken i gram. ' + row['steps'][0]['text']
        row['steps'][0]['minutes'] += 2
        row['steps'][3].update(text='Klä en liten sil eller äggostform med ren silduk över en skål. Lyft över ostmassan med hålslev och varva med sockret. Vasslen är en separat processrest med okänt näringsinnehåll.', minutes=2)
        insert_step(row, 5, {'text': 'Låt rinna av tio minuter tills den värsta hettan gått ur.', 'uses': ['mjölk', 'filmjölk', 'ägg', 'strösocker'], 'minutes': 10, 'passive': True})
        for step in row['steps']:
            step['text'] = step['text'].replace('Skölj och dela jordgubbarna.', 'Dela de tinade jordgubbarna och servera all saft till.')
            step['text'] = step['text'].replace('Vispa den kalla grädden', 'Vispa den kalla vispgrädden')
        mark_process(row, 4, ['mjölk', 'filmjölk', 'ägg', 'strösocker'], 'strain_whey', 'Ostmassan skiljs från vasslen och fortsätter rinna av i kylskåp. Ätligt utbyte och näringsfördelning är inte uppmätta.')
        prepend_thaw(row, 'jordgubbar', 120, 'Servera hela bärmängden och all saft till äggosten.')
        # prepend_steps adjusts dependencies but not the new process metadata.
        row['unmeasured_processes'][0]['step'] += 2
        changes.append('New culinary dose 42 g filmjölk replaces 40 ml without a density conversion. Frozen berries are thawed with all juice and named visibly. Raw egg is weighed shell-free. Whey separation remains explicit and unmeasured; two active transfer minutes are separated from ten passive draining minutes.')
    if base.endswith('shrikhand'):
        mark_process(row, 2, ['yoghurt naturell'], 'strain_whey', 'Yoghurtens vassle silas bort under åtta timmar i kylskåp. Serverad vikt och näringsfördelning är inte uppmätta.')
        if row['variant_id'] == 'extended':
            row['steps'][2].update(text='Värm mjölken försiktigt i en liten kastrull, rör ner saffran och ta från värmen.', minutes=2)
            insert_step(row, 4, {'text': 'Låt saffransmjölken dra och svalna tio minuter.', 'uses': ['mjölk', 'saffran'], 'minutes': 10, 'passive': True})
            for step in row['steps']:
                step['text'] = step['text'].replace('Skär mangon i små bitar', 'Använd de tinade mangobitarna med all saft')
            prepend_thaw(row, 'mango', 120, 'Behåll all saft till krämen.')
            row['unmeasured_processes'][0]['step'] += 2
        changes.append('Keep chilled whey draining without assumed yield or nutrient retention. Extended frozen mango is explicitly thawed with all juice; saffron heating and ten-minute cooling are scheduled separately.')
    if base.endswith('chhena-poda'):
        row['steps'][1]['text'] = 'Låt ostmassan rinna av cirka 15 minuter. Pressa inte torrt; den ska vara fuktig och gå att knåda. Vassle som inte används är en separat processrest.'
        row['steps'][2]['text'] = 'Låt ostmassan svalna tio minuter tills den går att hantera.'
        row['steps'][4]['text'] = 'Låt massan vila 15 minuter så att mannagrynen sväller.'
        row['steps'][6]['text'] = 'Låt kakan svalna i formen 30 minuter.'
        insert_step(row, 2, {'text': 'Klä en sil med ren silduk över en skål och häll försiktigt i ostmassan och vasslen.', 'uses': ['mjölk', 'citronjuice'], 'minutes': 2})
        insert_step(row, 5, {'text': 'Värm ugnen till 185 °C och klä en liten form med bakplåtspapper. Smält det uppmätta smöret försiktigt.', 'uses': ['smör'], 'minutes': 3})
        insert_step(row, 8, {'text': 'Fördela hela massan i formen och jämna till ytan.', 'uses': ['mjölk', 'mannagryn'], 'minutes': 2})
        row['steps'].append({'text': 'Lossa hela den lilla kakan och servera. Förvara inte fuktig färskostkaka i varm ugn efter servering.', 'uses': ['mjölk', 'mannagryn'], 'minutes': 2})
        mark_process(row, 3, ['mjölk', 'citronjuice'], 'strain_whey', 'Mjölk och citron delas i ostmassa och vassle. Bara angiven liten del vassle får återföras; kvarvarande processrest och näringsfördelning är inte uppmätta.')
        changes.append('Keep actual milk curdling and whey separation with unknown yield. Separate active pouring, oven/form preparation, butter melting, filling and unmoulding from passive draining, cooling and baking.')
    if base.endswith('torta-pasqualina'):
        if row['variant_id'] != 'simple':
            for component in row['components']:
                component['ingredients'] = [i for i in component['ingredients'] if i['name'] != 'mangold']
                for item in component['ingredients']:
                    if item['name'] == 'spenat':
                        item['quantity'] = 600
            for step in row['steps']:
                step['uses'] = list(dict.fromkeys('spenat' if n == 'mangold' else n for n in step['uses']))
                step['text'] = step['text'].replace(' Skär mangolden och tillsätt den, stjälkar först och blad sist.', '')
            row['name'] += ' – med spenat, mejram och muskot'
            changes.append('Explicit spinach-only pasqualina: 600 g frozen spinach replaces the mixed 400 g spinach/200 g chard proposal, as a new culinary input dose, not a fresh/frozen or drained-yield conversion. Standard retains marjoram/nutmeg and extended retains its tomato-basil side; neither duplicates the simpler variant.')
        inputs = ['spenat']
        mark_process(row, 3, inputs, 'drain_after_cooking', 'Uppvärmda bladgrönsaker pressas ur före fyllningen. Vätskemängd och näringsförlust är inte uppmätta; hela inköpta insatsen bevaras.')
        row['steps'][4]['text'] = 'Låt grönsaksblandningen svalna på ett fat cirka 15 minuter.'
        row['steps'][5]['text'] = 'Värm ugnen till 185 °C. ' + row['steps'][5]['text'].replace('finriven parmesan', 'den färdigrivna parmesanen')
        row['steps'][5]['minutes'] += 1
        if row['variant_id'] == 'extended':
            row['name'] += ' – med ljummen tomat-basilikasallad'
            row['steps'][-1]['text'] = 'Tärna tomaterna. Koka hälften med den frysta hackade basilikan under omrörning minst tre minuter eller längre enligt förpackningen. Blanda med resten av tomaterna, salladens vinäger och olja. Skär pajen i fyra delar och servera hela den ljumma salladen med all saft till.'
            row['steps'][-1]['minutes'] = 9
        if row['variant_id'] != 'simple':
            row['notes'] = row.get('notes', '').replace('AI-författat receptutkast. Inte provlagat och ännu inte import- eller produktgranskat av Smako.', 'Granskad spenatversion, inte provlagad.')
            row['steps'][3]['text'] += ' Bred ut blandningen på ett fat inför avsvalningen.'
            row['steps'][7]['text'] = 'Baka på nedre falsen cirka 45 minuter.'
            insert_step(row, 9, {'text': 'Kontrollera att skalet är gyllene, botten gräddad och ägghålen har stelnad vita och minst 72 °C i mitten. Förläng gräddningen vid behov; ta därefter ut formen.', 'uses': ['ägg', 'vetemjöl', 'spenat'], 'minutes': 2})
            changes.append('Count the oven doneness/temperature check and pan removal as active work before the passive twelve-minute rest.')
        changes.append('Retain real spinach/chard draining as unmeasured loss. Use weighed raw shell-free eggs and already grated parmesan. Separate oven preparation; extended frozen basil cooks in a visibly warm salad.')
    if base.endswith('nicuatole-majspudding'):
        row['steps'][0].update(text='Vispa masa harina med mjölk, socker, vanilj och salt i en liten tjockbottnad kastrull tills inga torra klumpar finns.', minutes=1)
        insert_step(row, 2, {'text': 'Låt blandningen stå fem minuter.', 'uses': ['masa harina', 'mjölk'], 'minutes': 5, 'passive': True})
        row['steps'][3].update(text='Skölj en skål på minst 250 ml med kallt vatten och skaka ur. Packa hela den heta massan i skålen och jämna till.', minutes=2)
        insert_step(row, 5, {'text': 'Låt svalna cirka 15 minuter före kylningen.', 'uses': ['masa harina', 'mjölk'], 'minutes': 15, 'passive': True})
        if row['variant_id'] == 'extended':
            for step in row['steps']:
                step['text'] = step['text'].replace('Tärna den skalade mangon', 'Använd de tinade mangobitarna med all saft')
            prepend_thaw(row, 'mango', 120, 'Behåll hela mängden och all saft till puddingen.')
        changes.append('Keep the explicit masa-harina adaptation with full retained inputs. Use a bowl large enough for all pudding; separate five-minute hydration and fifteen-minute cooling from active work. Extended mango is explicitly frozen and thawed.')
    if base in STAGES[9]:
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
    if base.endswith(('pa-tong-ko', 'bunuelos-de-viento', 'mangalore-buns', 'loukoumades', 'gulab-jamun')):
        if base.endswith('gulab-jamun'):
            row['steps'][5].update(text='Låt bollarna dra i den ljumma sirapen i 30 minuter.', minutes=30)
            insert_step(row, 6, {'text': 'Lyft bollarna med hålslev, låt överskottsoljan rinna av på papper och lägg dem i den ljumma sirapen. Återstående frityrolja serveras inte.', 'uses': ['rapsolja', 'mjölkpulver', 'strösocker'], 'minutes': 2, 'after': [5]})
            row['steps'][6]['after'] = [6]
            insert_step(row, 8, {'text': 'Vänd bollarna försiktigt i sirapen.', 'uses': ['mjölkpulver', 'strösocker'], 'minutes': 1, 'after': [7]})
            insert_step(row, 9, {'text': 'Låt dra ytterligare 30 minuter, totalt 60 minuter.', 'uses': ['mjölkpulver', 'strösocker'], 'minutes': 30, 'passive': True, 'after': [8]})
            for n, step in enumerate(row['steps']):
                step['after'] = [n] if n else []
        if base.endswith('loukoumades'):
            row['steps'][0]['text'] = row['steps'][0]['text'].replace('fingervarmt, cirka 35 °C', 'tempererat enligt torrjästens förpackningsanvisning')
            row['steps'][2]['text'] = 'Smörj två torra teskedar med några droppar av den uppmätta oljan innan den värms. Värm resten till 170 °C i en stadig kastrull där mängden bildar ett grunt bad. Välj kärl efter portionsmängden och fyll aldrig mer än till en tredjedel. Håll ett torrt lock nära och lämna inte oljan obevakad.'
            row['steps'][3]['text'] = row['steps'][3]['text'].replace('Smörj två torra teskedar med lite av den angivna oljan innan den hettas upp. ', '')
        if base.endswith('mangalore-buns'):
            row['steps'][0]['text'] = row['steps'][0]['text'].replace('Mosa bananen', 'Skala bananen, väg den angivna ätliga mängden och mosa')
        if base.endswith('bunuelos-de-viento'):
            row['steps'][0]['text'] = row['steps'][0]['text'].replace('Vispa mjöl, uppvägt ägg', 'Knäck ägg och väg den angivna råa ätliga mängden utan skal; oanvänt ägg är separat rest. Vispa mjöl, uppvägt ägg')
        for step in row['steps']:
            step['text'] = step['text'].replace('mer än halva kastrullen', 'mer än en tredjedel av kastrullen').replace('mer än halvfullt', 'mer än fyllt till en tredjedel')
        draining = [n for n, step in enumerate(row['steps'], 1)
                    if any(term in step['text'] for term in ('rinna av', 'droppa av'))]
        assert draining, f'Missing explicit oil-draining step: {base}'
        index = draining[0]
        mark_process(row, index, ['rapsolja'], 'deep_fry_and_drain', 'Hela uppmätta oljemängden är en inköpt processinsats. Överskottsolja rinner av och serveras inte. Oljans upptag och slutlig näring är okända.')
        changes.append('Keep the original frying quantities and classic method, explicitly mark unknown oil uptake, and do not treat process oil as served food. Preserve fryer temperature, batch/doneness checks and at-most-one-third fill. Active transfer/turning and yeast preparation are clarified where needed.')
    if base.endswith('revithada'):
        row['steps'][1]['text'] = 'Blötlägg kikärtorna 12 timmar i kylskåp. Blötläggningsvattnet hälls bort i nästa aktiva steg.'
        # The two inspections are real work, separately scheduled between
        # passive periods rather than hidden in a six-hour passive step.
        old = row['steps'][3]
        row['steps'][3:4] = [
            {**old, 'text': 'Baka den täckta grytan två timmar vid 150 °C.', 'minutes': 120},
            {'text': 'Kontrollera vätskan och tillsätt 150 ml vatten om kikärtorna annars blir torra. Lägg tillbaka det täta locket.', 'uses': ['kikärtor'], 'minutes': 1},
            {**old, 'text': 'Baka ytterligare två timmar under tätt lock.', 'minutes': 120},
            {'text': 'Kontrollera vätskan igen; tillsätt vid behov 150 ml vatten och lägg tillbaka locket.', 'uses': ['kikärtor'], 'minutes': 1},
            {**old, 'text': 'Baka ytterligare två timmar, totalt omkring sex timmar. Kikärtorna ska vara helt mjuka och kunna mosas lätt; förläng tiden om det behövs.', 'minutes': 120},
        ]
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        if row['variant_id'] != 'simple':
            mark_process(row, len(row['steps']), ['lagerblad'], 'remove_after_infusion', 'Lagerblad kokar med och plockas sedan bort. Överföring till spadet är inte uppmätt; ingen noll- eller fullretention antas.')
        changes.append('Keep the authored bay leaf and its removal in standard/extended. Explicit unmeasured-process contract makes served nutrition unknown. Count two active liquid inspections during the original six-hour bake.')
    if base.endswith('pasta-alla-genovese'):
        if row['variant_id'] != 'simple':
            rename_ingredient(row, 'vitt vin', 'vitt matlagningsvin')
            row['name'] += ' – med vitt matlagningsvin'
        for step in row['steps']:
            step['text'] = step['text'].replace('Häll i vinet', 'Häll i det vita matlagningsvinet')
            step['text'] = step['text'].replace('riv parmesan över', 'fördela den färdigrivna parmesanen över')
            step['text'] = step['text'].replace('Häll av, hacka persiljan och vänd bönorna', 'Låt fryst hackad persilja koka med bönorna de sista två minuterna. Häll av och vänd bönorna')
        simmer = row['steps'][3]
        periods = []
        for turn in range(6):
            periods.append({**simmer, 'text': 'Sjud på låg värme under lock i 30 minuter.', 'minutes': 30})
            if turn < 5:
                periods.append({'text': 'Rör om och kontrollera att bottnen inte kokar torr. Tillsätt vid behov 50 ml vatten och lägg tillbaka locket.', 'uses': ['högrev', 'gul lök'], 'minutes': 1})
        row['steps'][3:4] = periods
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        for index, step in enumerate(row['steps'], 1):
            if 'Ta upp lagerbladet' in step['text']:
                mark_process(row, index, ['lagerblad'], 'remove_after_infusion', 'Lagerblad plockas bort efter långkok; överföring till såsen är inte uppmätt.')
            if step['text'].startswith('Koka upp 2500 ml vatten'):
                mark_process(row, index, ['pasta', 'salt'], 'drain_after_cooking', 'Saltat pastavatten hälls delvis bort och en mindre del används i såsen. Upptag av salt och förlust till vattnet är okända.')
        changes.append('Keep original salt and bay-leaf procedures with explicit unknown retention. Standard/extended explicitly use 100 ml cooking wine, at the manufacturer-recommended same cooking volume; grated parmesan and cooked frozen parsley. Five active stirring/liquid checks are scheduled between six half-hour simmering periods.')
    if base.endswith('tirokafteri'):
        row['steps'][0]['text'] = 'Värm ugnen till 230 °C över-/undervärme. Kärna ur paprikan, väg angiven rå ätlig mängd med skal och lägg med skalsidan upp i en liten ugnsform.'
        row['steps'][1]['text'] = 'Rosta 20 minuter eller tills skalet fått mörka blåsor.'
        row['steps'][1]['minutes'] = 20
        insert_step(row, 3, {'text': 'Lägg den varma paprikan i en skål och täck.', 'uses': ['paprika'], 'minutes': 1, 'after': [2]})
        insert_step(row, 4, {'text': 'Låt svalna tio minuter så att skalet lossnar.', 'uses': ['paprika'], 'minutes': 10, 'passive': True, 'after': [3]})
        row['steps'][4]['after'] = [4]
        mark_process(row, 5, ['paprika'], 'peel_after_cooking', 'Paprikan vägs rå efter urkärning men före rostning och skalning. Borttaget skal och eventuell vätska är okänt utbyte.')
        changes.append('Preserve roasted-and-peeled pepper method. Raw input is explicitly weighed before roasting/peeling; lost peel and juice are not assigned an invented yield. Active transfer and passive cooling are separate.')
    if base.endswith('melitzanosalata'):
        row['name'] += ' – rostad med skal, sedan skalad'
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'aubergine':
                    item['label'] = 'Aubergine med skal, rå ätlig vikt efter att fästet tagits bort'
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skär den redan skalade auberginen i tjocka skivor.', 'Ta bort auberginens fäste, väg angiven rå mängd med skal och dela i längsgående kvartar. Skalet tas bort efter rostningen.')
        row['steps'][2]['text'] = 'Låt grönsakerna rinna av över skålen och svalna 15 minuter. Pressa inte ur fruktköttet. Vätskan serveras inte.'
        insert_step(row, 3, {'text': 'Flytta de rostade grönsakerna till ett durkslag över en skål.', 'uses': ['aubergine'] + (['paprika'] if row['variant_id']=='extended' else []), 'minutes': 1, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][4]['text'] = row['steps'][4]['text'].replace('Hacka auberginen', 'Dra bort aubergineskalet och hacka fruktköttet')
        row['steps'][4]['minutes'] += 3
        if row['variant_id'] == 'extended':
            row['steps'][4]['text'] = row['steps'][4]['text'].replace('Finhacka rödlök, persilja och rostad paprika', 'Värm fryst hackad persilja med 20 ml vatten i en liten kastrull under omrörning minst två minuter eller längre enligt förpackningen. Behåll hela denna vätska. Finhacka rödlök och rostad paprika')
            row['steps'][4]['text'] += ' Blanda också ner all uppvärmd persilja med vätskan.'
            row['steps'][4]['minutes'] += 3
        mark_process(row, 4, ['aubergine', 'olivolja'] + (['paprika'] if row['variant_id']=='extended' else []), 'drain_after_cooking', 'Vätska från rostade grönsaker med olja rinner av. Ingen kvarhållen andel är uppmätt.')
        mark_process(row, 5, ['aubergine'], 'peel_after_cooking', 'Ny tydlig rå insats med skal före rostning. Skalet tas bort efteråt; 250 g är inte en påstådd motsvarighet till 250 g skalat fruktkött.')
        row['steps'][1].update(text='Rosta grönsakerna i 15 minuter utan att ytan blir svart.', minutes=15)
        insert_step(row, 3, {'text': 'Vänd grönsakerna med tång.', 'uses': ['aubergine'] + (['paprika'] if row['variant_id']=='extended' else []), 'minutes': 1, 'after': [2]})
        insert_step(row, 4, {'text': 'Rosta ytterligare cirka 20 minuter tills auberginen är helt mjuk och brynt men inte svart. Förläng tiden om den fortfarande är fast.', 'uses': ['aubergine'], 'minutes': 20, 'passive': True, 'after': [3]})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Visible roast-in-skin version, using the same numerical 250 g as a new gross edible input with skin, not peeled-flesh equivalence. Peel and roast juice are removed after cooking under the unknown-loss contract. No edible yield/density invented.')
    if base.endswith('porterstek'):
        for step in row['steps']:
            step['text'] = step['text'].replace('Krossa enbären lätt', 'Mal enbären mycket fint i kryddkvarn')
            step['text'] = step['text'].replace('Ta bort enbären. ', 'Behåll de finmalda enbären i såsen. ')
            step['text'] = step['text'].replace('Skala potatisen och dela stora exemplar jämnt.', 'Skala potatisen, väg den angivna råa ätliga mängden och dela stora exemplar jämnt.')
            if 'och potatisdelens salt' in step['text']:
                step['text'] = step['text'].replace('och potatisdelens salt', 'utan tillsatt salt')
                step['uses'].remove('salt')
            if step['text'].startswith('Vispa mjölet'):
                step['text'] = step['text'].replace('Vispa ner i spadet', 'Vispa ner i spadet tillsammans med hela saltmängden från potatiskomponenten')
                step['uses'].append('salt')
            if step['text'].startswith('Koka ner spadet'):
                step['text'] = step['text'].replace('Rör ner grädden', 'Rör ner hela saltmängden från potatiskomponenten och grädden')
                step['uses'].append('salt')
        simmer = row['steps'][1]
        simmer['text'] = simmer['text'].replace('Sjud under tätt lock cirka två timmar. Vänd steken efter en timme.', 'Sjud vidare under tätt lock cirka en timme till, totalt ungefär två timmar.')
        simmer['minutes'] = 60
        insert_step(row, 2, {'text': 'Sjud under tätt lock på låg värme i en timme.', 'uses': ['nötstek'], 'minutes': 60, 'passive': True, 'after': [1]})
        insert_step(row, 3, {'text': 'Vänd steken varsamt vid halvtidskontrollen och lägg på locket igen.', 'uses': ['nötstek'], 'minutes': 1, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][-1]['text'] += ' Fördela hela såsen och all köttsaft från skärbrädan mellan portionerna.'
        if row['variant_id'] != 'simple':
            row['equipment'].append('kryddkvarn')
        changes.append('Use declared concentrated blackcurrant cordial; never the diluted nutrition as concentrate. Grind and retain juniper, retain all sauce and board juices, move unchanged potato salt to sauce, and count the simmering turn as active work.')
    if base.endswith('zuppa-imperiale'):
        rename_ingredient(row, 'grönsaksbuljong', 'grönsaksfond')
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'grönsaksfond':
                    item.update(quantity=35, unit='ml', label='Flytande koncentrerad grönsaksfond')
        row['name'] += ' – med flytande grönsaksfond'
        for step in row['steps']:
            step['text'] = step['text'].replace('Riv parmesanen.', 'Väg upp den färdigrivna parmesanen.')
            step['text'] = step['text'].replace('inte har rå äggsmet i mitten', 'når minst 72 °C i mitten utan rå äggsmet')
            step['text'] = step['text'].replace('buljongpulvret', 'den flytande koncentrerade grönsaksfonden')
            step['text'] = step['text'].replace('Hacka persiljan och rör ner den.', 'Rör ner fryst hackad persilja och låt koka med minst två minuter eller längre enligt förpackningen.')
        changes.append('Visible new dose 35 ml liquid concentrated vegetable stock replaces 12 g powder; the original process water is retained and no equivalence/density is asserted. Use grated parmesan and cook frozen parsley; explicit egg doneness.')
    if base.endswith('pizzoccheri'):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'salvia':
                    item.update(form='dry', quantity=1, label='Torkad smulad salvia')
                if c['id'] == 'kok' and item['name'] == 'salt':
                    item['quantity'] = 2
        if row['variant_id'] != 'simple':
            row['name'] += ' – med torkad salvia'
        for step in row['steps']:
            step['text'] = step['text'].replace('Skala potatis och tärna', 'Skala potatisen, väg angiven rå ätlig mängd och tärna')
            if 'med kokkomponentens salt' in step['text']:
                step['text'] = step['text'].replace('med kokkomponentens salt', 'utan tillsatt salt')
                step['uses'].remove('salt')
            step['text'] = step['text'].replace('tillsammans med salviabladen', 'tillsammans med torkad smulad salvia')
            step['text'] = step['text'].replace('och finriv parmesan', 'och väg upp färdigriven parmesan')
            if step['text'].startswith('Lyft pasta'):
                step['text'] = step['text'].replace('och svartpeppar', ', hela kokkomponentens salt och svartpeppar')
                step['uses'].append('salt')
                step['text'] += ' Skrapa med allt smör och all ost till serveringen.'
            if step['text'].startswith('Skala rödbeta'):
                step['text'] = 'Skala rödbetan och kärna ur äpplet, väg de angivna ätliga mängderna och grovriv. Vänd med äppelcidervinäger och ställ svalt; hela salladen och dressingen serveras separat från pastan.'
        changes.append('Visible dried-sage adaptation: 1 g instead of 5 g fresh leaves, no fresh/dry yield. Replace 6 g discarded cooking-water salt with a new 2 g dose on drained pasta; dough salt unchanged. Ready-grated parmesan, all butter/cheese and salad dressing served.')
    if base.endswith('kai-palo'):
        rename_ingredient(row, 'kokta ägg', 'ägg')
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'ägg':
                    item.update(quantity=8, unit='st', form='as_sold', label='Hela råa hönsägg med skal, räknade före kokning')
        for step in row['steps']:
            step['text'] = step['text'].replace('hacka koriander grovt', 'väg upp fryst hackad koriander')
            step['text'] = step['text'].replace('tills mycket mört.', 'tills mycket mört och minst 72 °C i mitten.')
            step['text'] = step['text'].replace('Lägg den stekta tofun i grytan.', 'Lägg den stekta tofun i grytan tillsammans med all olja från pannan.')
            if step['text'].startswith('Skala och skiva morot'):
                step['text'] = 'Skala morot och ingefära och väg de råa ätliga mängderna. Dela och skölj pak choi. Koka upp 150 ml vatten med grönsakernas salt och ingefära, lägg i morot och sjud under lock fem minuter. Tillsätt pak choi och sjud ytterligare minst tre minuter tills allt är genomhett och mjukt. Servera med hela grönsaksspadet.'
            step['text'] = step['text'].replace('lite spad och ris', 'hela kryddspadet och ris')
        row['steps'][2:3] = [
            {'text': 'Lägg köttet i kryddspadet och koka upp försiktigt.', 'uses': ['fläskkarré'], 'minutes': 3},
            {'text': 'Sjud under lock på låg värme i 50 minuter.', 'uses': ['fläskkarré'], 'minutes': 50, 'passive': True},
            {'text': 'Rör om och kontrollera vätskan. Tillsätt vid behov 150 ml vatten så att köttet inte kokar torrt.', 'uses': ['fläskkarré'], 'minutes': 1},
            {'text': 'Sjud ytterligare 50 minuter, tills köttet är mycket mört och minst 72 °C i mitten.', 'uses': ['fläskkarré'], 'minutes': 50, 'passive': True},
        ]
        index = next(n for n, step in enumerate(row['steps'], 1) if 'färdigkokta skalade äggen' in step['text'])
        egg_steps = [
            {'text': 'Lägg de räknade hela råa äggen i en separat kastrull med 1000 ml vatten, eller ytterligare 500 ml om det behövs för att täcka. Koka upp försiktigt.', 'uses': ['ägg'], 'minutes': 5},
            {'text': 'Sjud äggen tolv minuter från uppkok så att både vita och gula blir helt fasta.', 'uses': ['ägg'], 'minutes': 12, 'passive': True},
            {'text': 'Häll försiktigt bort det heta kokvattnet och kyl äggen med 1000 ml kallt vatten.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Låt äggen svalna i det kalla vattnet fem minuter så att de går att skala.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Skala äggen och kassera skalen. Använd samtliga kokta ägg; ingen färdig gramvikt är förutsatt. Kontrollera att både vita och gula är fasta.', 'uses': ['ägg'], 'minutes': 6},
            {'text': 'Lägg ner de nykokta skalade äggen hela i grytan och värm till svag sjudning.', 'uses': ['ägg'], 'minutes': 2},
            {'text': 'Sjud mycket försiktigt i fem minuter.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Vänd äggen varsamt så att kryddspadet kommer åt runtom.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Sjud ytterligare fem minuter.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
            {'text': 'Vänd äggen försiktigt igen.', 'uses': ['ägg'], 'minutes': 1},
            {'text': 'Sjud de sista fem minuterna, totalt 15 minuter i kryddspadet.', 'uses': ['ägg'], 'minutes': 5, 'passive': True},
        ]
        row['steps'][index - 1:index] = egg_steps
        mark_process(row, index + 4, ['ägg'], 'peel_after_cooking', 'Hela ägg köps som deklarerat antal, kokas och skalas. Skalen serveras inte; ingen styckvikt eller kokt ätlig vikt har antagits.')
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('New explicit dose: eight whole raw shell eggs replace 400 g ready-cooked peeled egg, without a weight equivalence. Count-based source products preserve exact purchase quantities; boiling/peeling has unknown served mass. Ground Five Spice and frozen coriander cook in the retained broth; tofu oil and side liquid are served. Active pot loading, checks, egg cooling/peeling and turning are separately scheduled.')
    candied_doses = {
        'smako-greek-fanouropita': 4,
        'smako-greek-halvas-simigdalenios': 5,
        'smako-greek-portokalopita': 6,
        'smako-italian-budino-riso-toscana': 5,
        'smako-mexican-camotes-poblanos': 4,
        'smako-italian-ricciarelli-siena': 4,
    }
    if base in candied_doses and any(i['name'] == 'apelsinskal' for c in row['components'] for i in c['ingredients']):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'apelsinskal':
                    item.update(name='kanderade apelsinskal', label='Färdigkanderade apelsinskal, mycket finhackade', form='as_sold', quantity=candied_doses[base], unit='g')
                    item.pop('requirements', None)
        for step in row['steps']:
            step['uses'] = ['kanderade apelsinskal' if n == 'apelsinskal' else n for n in step['uses']]
            step['text'] = step['text'].replace('finriv det uppvägda, tvättade apelsinskalet', 'hacka det färdigkanderade apelsinskalet mycket fint')
            step['text'] = step['text'].replace('finrivet apelsinskal', 'mycket finhackat färdigkanderat apelsinskal')
            if base.endswith('portokalopita'):
                step['text'] = step['text'].replace('tillsammans med apelsinskalet', 'tillsammans med mycket finhackat färdigkanderat apelsinskal')
        row['name'] = row['name'].replace('färsk apelsinarom', 'kanderad apelsin') + ' – med kanderat apelsinskal'
        changes.append(f'Visible candied-peel adaptation: {candied_doses[base]} g very finely chopped ready-candied peel replaces raw zest. This is a new culinary dose, not an identity alias, zest yield or sugar equivalence. Other quantities remain unchanged.')
    if base.endswith('fanouropita'):
        row['steps'].append({'text': 'Ta ut den avsvalnade kakan ur formen och dela efter det angivna antalet portioner.', 'uses': [], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('One active minute for unmoulding and portioning after passive cooling.')
    if base.endswith('halvas-simigdalenios'):
        row['steps'][3]['text'] = 'Låt den formade massan svalna 25 minuter.'
        row['steps'][4]['text'] = 'Ställ i kylskåp 60 minuter så att puddingen sätter sig.'
        insert_step(row, 4, {'text': 'Tryck ner hela massan i en liten sköljd silikonform eller portionsskål.', 'uses': ['mannagryn'], 'minutes': 2, 'after': [3]})
        row['steps'][4]['after'] = [4]
        row['steps'].append({'text': 'Stjälp upp den kalla puddingen eller servera direkt ur skålen.', 'uses': ['mannagryn'], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Separate active moulding/unmoulding from the 25-minute cooling and 60-minute refrigeration.')
    if base.endswith('portokalopita'):
        old = row['steps']
        row['steps'] = [
            {'text': 'Sätt ugnen på 100 °C. Riv filodegen i grova remsor och sprid luftigt på en torr plåt.', 'uses': ['filodeg'], 'minutes': 2},
            {**old[0], 'text': 'Torka filoremsorna cirka 18 minuter tills bladen är spröda men inte brynta.'},
            old[1], old[2],
            {'text': 'Klä den lilla formen med bakplåtspapper och häll i hela smeten.', 'uses': ['filodeg', 'ägg'], 'minutes': 2},
            {**old[3], 'text': 'Grädda cirka 28 minuter vid 180 °C tills mitten har stannat, når minst 72 °C och en sticka inte får med sig rå äggsmet.'},
            {'text': 'Stick några hål i kakan och skeda över hela den avsvalnade sirapen.', 'uses': ['apelsinjuice', 'strösocker'], 'minutes': 2},
            {**old[4], 'text': 'Låt kakan svalna 25 minuter.'},
            {**old[5], 'text': 'Kyl ytterligare 60 minuter så att filolagren hinner ta upp sirapen.'},
            {'text': 'Ta ut kakan ur formen och servera hela mängden, inklusive all sirap, fördelad över det angivna antalet portioner.', 'uses': ['filodeg'], 'minutes': 1},
        ]
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        changes.append('Count active filo tearing, filling the form, syrup application and serving separately from passive oven/cooling time. Explicit egg doneness and all syrup served.')
    if base.endswith('budino-riso-toscana'):
        row['steps'][4]['text'] = 'Låt riskrämen svalna 15 minuter tills den inte längre är het.'
        insert_step(row, 5, {'text': 'Bred ut hela riskrämen i en ren grund skål. Sätt ugnen på 180 °C.', 'uses': ['risottoris'], 'minutes': 1, 'after': [4]})
        row['steps'][5]['after'] = [5]
        row['steps'][-1]['text'] = 'Låt pajen svalna på galler 20 minuter.'
        row['steps'].append({'text': 'Ta den avsvalnade pajen ur formen och servera hela mängden fördelad efter det angivna antalet portioner.', 'uses': [], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Count spreading hot rice cream and unmoulding as active work, preserving the passive cooling times.')
    if base.endswith('camotes-poblanos'):
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Skala och dela sötpotatisen jämnt.', 'Skala sötpotatisen, väg den angivna råa ätliga mängden och dela jämnt.')
        row['steps'][2]['text'] = 'Låt massan svalna 20 minuter tills den går att hantera.'
        insert_step(row, 3, {'text': 'Bred ut hela den heta massan på bakplåtspapper.', 'uses': ['sötpotatis'], 'minutes': 1, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('liten söt mellanmålsportion', 'söt mellanmålsportion')
        changes.append('Weigh peeled raw sweet potato; separate active spreading from passive cooling. Keep the original explicit refrigerated soft-confection method.')
    if base.endswith('ricciarelli-siena'):
        from admit_expansion_20261101 import prepend_steps
        from app.services.egg_preparation import OPERAND

        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'äggvita':
                    item['requirements'] = sorted(set(vocabulary['äggvita|raw_edible'][1]) | {OPERAND})
        prepend_steps(row, [{'text': 'Knäck rena hönsägg och separera vitan från gulan utan tillsatser. Väg den angivna mängden rå vita utan skal. Inköpets äggutbyte är en populationsuppskattning; komplettera om den vägda mängden är för liten. Oanvänd gula och vita är separata rester. Följ förpackningens hanteringsråd.', 'uses': ['äggvita'], 'minutes': 3, 'after': []}])
        changes.append('Use the existing reviewed egg-separation operand and explicit three active preparation minutes; actual white is weighed, unused yolk is a separate remainder, no exact separation yield is claimed.')
    if base.endswith('isterband-dillpotatis'):
        for step in row['steps']:
            step['text'] = step['text'].replace('Skala rödbetorna och tärna dem smått.', 'Skala rödbetorna, väg den angivna råa ätliga mängden och tärna smått.')
            if step['text'].startswith('Skala och tärna potatisen.'):
                step['text'] = 'Skala potatisen, väg den angivna råa ätliga mängden och tärna. Koka upp i 1400 ml vatten utan tillsatt salt.'
                step['uses'].remove('salt')
            step['text'] = step['text'].replace('Rör ner resterande salt', 'Rör ner hela den angivna saltmängden')
            if step['text'].startswith('Vänd potatisen och hackad dill'):
                step['text'] = 'Rör ner fryst hackad dill i såsen och sjud under omrörning minst två minuter eller längre enligt förpackningen. Vänd ner potatisen och låt allt bli genomvarmt. Håll på låg värme och rör varsamt så att botten inte bränns.'
                step['minutes'] = 5
            if step['text'].startswith('Skär gurka och äpple'):
                step['text'] = step['text'].replace('Skär gurka och äpple', 'Kärna ur äpplet och väg den ätliga mängden. Skär gurka och äpple')
        row['steps'][-1]['text'] += ' Fördela också allt genomhettat fett från korvpannan över potatisstuvningen.'
        if row['variant_id'] != 'simple':
            row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('avrunna rödbetor', 'rödbetor med hela den sötsyrliga lagen i separata skålar')
            row['steps'][-1]['uses'] += ['ättiksprit 12 procent', 'strösocker']
        changes.append('Salt is retained in the sauce instead of discarded potato water; unchanged dose. Weigh peeled vegetables, cook frozen dill, serve all sausage fat and all sweet-sour beet dressing. No absorption/retention coefficient.')
    if base.endswith('kollyva-veteskal'):
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('med salt', 'utan tillsatt salt')
        row['steps'][0]['uses'].remove('salt')
        row['steps'][2]['text'] = 'Låt de utbredda kornen svalna 20 minuter och ytan torka.'
        insert_step(row, 3, {'text': 'Häll av överflödigt vatten från de färdigkokta kornen. Bred ut dem i tunt lager på en ren tallrik.', 'uses': ['matvete'], 'minutes': 2, 'after': [2]})
        row['steps'][3]['after'] = [3]
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('kanel, florsocker och nötter', 'kanel, florsocker, hela saltmängden och nötter')
        row['steps'][-1]['uses'].append('salt')
        if row['variant_id'] == 'extended':
            row['steps'][-1]['text'] = row['steps'][-1]['text'].replace('Vänd ner granatäppelkärnor', 'Vänd ner helt tinade granatäppelkärnor med all saft')
            prepend_thaw(row, 'granatäppelkärnor', 120, 'Behåll alla kärnor och all saft till veteskålen.')
        changes.append('Keep the declared matvete breakfast adaptation. Salt moves to the retained bowl; two active draining/spreading minutes are explicit. Extended frozen pomegranate is thawed with all juice retained.')
    if base.endswith('panforte'):
        row['name'] = row['name'].replace('Panforte', 'Panforte med färdigkanderat apelsinskal')
        component = row['components'][0]
        component.update(name='Färdigkanderat apelsinskal', ingredients=[{
            'name': 'kanderade apelsinskal', 'form': 'as_sold', 'quantity': 25, 'unit': 'g', 'role': 'flavour', 'label': 'Kanderade hackade apelsinskal'}])
        row['steps'] = row['steps'][2:]
        for step in row['steps']:
            step['uses'] = ['kanderade apelsinskal' if n == 'apelsinskal' else n for n in step['uses'] if n != 'strösocker']
        row['steps'][1]['text'] = 'Värm honungen med 10 ml vatten tills den bubblar. Rör i de färdigkanderade hackade apelsinskalen och därefter nöt-mjölblandningen. Arbeta till en mycket tjock sammanhängande massa; allt ska användas.'
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        row['steps'].append({'text': 'Servera hela den avsvalnade lilla kakan som en mellanmålsportion.', 'uses': ['kanderade apelsinskal'], 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Visible bought-candied-peel version: use 25 g candied peel instead of 12 g raw peel plus 12 g sugar; no peel yield or equivalence is claimed. Remove home candying and use all the new product, honey and 10 ml process water.')
    if base.endswith('bryta-filmjolk'):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'filmjölk':
                    item.update(quantity=285, unit='g')
        row['name'] = row['name'].replace('rårörda lingon', 'kokta sockrade lingon')
        row['steps'][0].update(text='Lägg frysta lingon, allt socker och 20 ml vatten i en liten kastrull. Koka under omrörning minst en minut eller längre enligt förpackningen. Behåll alla bär och all saft.', minutes=5)
        row['steps'][1].update(text='Fördela lingonen tunt i en ren grund skål och låt svalna 20 minuter. Ställ sedan i kylskåp tills helt kalla före servering med filen.', minutes=20)
        for step in row['steps']:
            step['text'] = step['text'].replace('Häll filmjölken', 'Väg filmjölken i gram').replace('de rårörda lingonen', 'de kalla kokta sockrade lingonen')
        changes.append('New culinary dose 285 g filmjölk per portion replaces 280 ml without a density claim. Frozen lingonberries are explicitly boiled with all sugar/juice retained, then cooled; the cooked topping is visibly named.')
    if base.endswith('schiacciata-uva'):
        row['name'] = row['name'].replace('Schiacciata', 'Schiacciata med kärnfria bordsdruvor')
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('Skölj, torka och halvera druvorna.', 'Använd kärnfria bordsdruvor. Plocka av klasstjälkarna, skölj och torka. Väg den angivna ätliga mängden och halvera utan att ta bort skalet; behåll all saft i brödet.')
        row['steps'][-1]['text'] = row['steps'][-1]['text'].replace(' Servera yoghurten bredvid.', '')
        row['steps'].append({'text': 'Servera hela den avsvalnade portionen med all fruktsaft från formen.' + (' Servera yoghurten bredvid.' if row['variant_id'] == 'extended' else ''), 'uses': ['vindruvor'] + (['yoghurt naturell'] if row['variant_id'] == 'extended' else []), 'minutes': 1, 'after': [len(row['steps'])]})
        changes.append('Explicit seedless table-grape adaptation, retaining edible skin/juice. Weigh after removing stems; purchasing uses the separately reviewed 96% population estimate only with estimates enabled. One active serving minute separated from cooling.')
    if base.endswith('enfrijoladas'):
        row['name'] = row['name'].replace('Enfrijoladas', 'Enfrijoladas med färdiga majstortillas')
        component = next(c for c in row['components'] if c['id'] == 'majsbrod')
        component.update(name='Färdiga mjuka majstortillas', ingredients=[{'name': 'majstortillas', 'form': 'as_sold', 'quantity': 400, 'unit': 'g', 'role': 'side', 'label': 'Mjuka majstortillas'}])
        row['steps'] = row['steps'][3:]
        for step in row['steps']:
            step['uses'] = ['majstortillas' if n == 'masa harina' else n for n in step['uses']]
            step['text'] = step['text'].replace('Skiva avokado', 'Använd helt tinade avokadobitar med all saft')
        if row['variant_id'] == 'extended':
            row['steps'][1]['text'] += ' Tillsätt fryst hackad koriander i bönsåsen och låt den koka med hela tiden.'
            row['steps'][1]['uses'].append('koriander')
            row['steps'][2]['text'] = row['steps'][2]['text'].replace('Tärna tomat och rödlök, hacka koriander och blanda', 'Tärna tomat och rödlök och blanda')
            row['steps'][2]['uses'].remove('koriander')
        row['steps'].insert(-1, {'text': 'Värm de färdiga mjuka majstortillorna i torr panna enligt förpackningen tills böjliga och genomvarma. Lägg i ren handduk och använd direkt.', 'uses': ['majstortillas'], 'minutes': 6})
        for n, step in enumerate(row['steps']):
            step['after'] = [n] if n else []
        prepend_thaw(row, 'avokado', 120, 'Använd alla bitar och all saft i avokadotillbehöret.')
        changes.append('Visible ready-made corn-tortilla adaptation: 400 g replaces 280 g masa harina plus 2 g dough salt, with no cooked-yield equivalence. Keep all bean sauce. Frozen avocado is thawed; frozen coriander moves into the boiled sauce.')
    if base.endswith('doi-maach'):
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('Skär fisken', 'Använd upptinad benfri fiskfilé, spara all vätska i kylskåp och skär fisken')
        row['steps'][5]['text'] += ' Använd samma panna med allt stekfett kvar. Häll i all upptiningssaft och saft från fiskfatet och koka upp innan yoghurten tillsätts. Eventuell kardemumma och kanel är malda.'
        row['steps'][5]['uses'].append('fisk')
        row['steps'][5]['minutes'] += 2
        if row['variant_id'] == 'extended':
            row['steps'][7]['text'] = 'Dela blomkålen i små buketter och väg upp den frysta hackade gröna jalapeñon. Lägg i en kastrull med 100 ml vatten och sjud under lock åtta minuter. Tillsätt ärtor och fryst hackad koriander och värm ytterligare minst tre minuter, eller längre enligt förpackningen, tills allt är genomhett och grönsakerna mjuka. Servera grönsakerna med all kvarvarande vätska bredvid fisken.'
        row['steps'][-1]['text'] += ' Fördela hela yoghurtsåsen och allt stekfett mellan portionerna.'
        prepend_thaw(row, 'fisk', 720, 'All upptiningssaft kokas med löken före yoghurten.')
        changes.append('Explicit frozen-fish thaw and cooking of all juice; retain frying fat, ground spices and side liquid. Frozen jalapeno/coriander are cooked in the extended side.')
    if base.endswith('pescado-zarandeado'):
        row['steps'][0]['text'] = 'Sätt ugnen på 220 °C. Väg upp mald Ancho Style-chili; ingen stjälk eller kärna ska tas bort och pulvret ska inte blötläggas eller rinna av.'
        row['steps'][1]['text'] = 'Låt ugnen bli helt varm, cirka 15 minuter.'
        row['steps'][1]['uses'] = []
        row['steps'][2]['text'] = row['steps'][2]['text'].replace('den avrunna chilin', 'hela mängden mald chili').replace('samt 50 ml vatten', 'samt 50 ml vatten och all upptiningssaft från fisken')
        row['steps'][2]['uses'].append('fisk')
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('Ingen rå fisk har ännu varit i kontakt med pastan.', 'Koka pastan under omrörning hela tiden; upptiningssaften ingår och ska genomhettas.')
        row['steps'][4]['text'] = row['steps'][4]['text'].replace('Kontrollera fiskfilén', 'Kontrollera den helt upptinade benfria fiskfilén')
        if row['variant_id'] == 'extended':
            row['steps'][2]['text'] += ' Tillsätt den frysta hackade koriandern i pastan så att den kokas med hela mängden.'
            row['steps'][2]['uses'].append('koriander')
            row['steps'][7]['text'] = 'Strimla kålen och krama lätt med sin limejuice. Vänd ner de helt tinade avokadobitarna med all avokadosaft. Koriandern ingår i den varma adobopastan.'
            row['steps'][7]['uses'].remove('koriander')
        row['steps'][-1]['text'] += ' Servera också all genomhettad sky och olja från formen samt hela lökdressingen om lök ingår.'
        if row['variant_id'] == 'extended':
            prepend_thaw(row, 'avokado', 120, 'Använd alla bitar och all avokadosaft i kålsalladen.')
        prepend_thaw(row, 'fisk', 720, 'All upptiningssaft kokas i adobopastan före ugnsbakningen.')
        changes.append('Retain the authored edible chili dose as explicitly ground Ancho Style; remove discarded soaking water. Thaw fish, cook all juice and retain oven drippings. Extended avocado is thawed and frozen coriander cooks in the paste.')
    if base.endswith('tacos-de-canasta'):
        row['steps'][0]['text'] = 'Skala potatisen, väg den angivna råa ätliga mängden och dela. Koka upp med 1000 ml vatten utan tillsatt salt. Väg upp den malda Ancho Style-chilin separat till chilioljan.'
        row['steps'][0]['uses'].remove('salt')
        row['steps'][1]['text'] = 'Sjud potatisen cirka 18 minuter tills den är helt mjuk. Häll av potatisen noga. Chilipulvret ska inte blötläggas.'
        row['steps'][1]['uses'] = ['potatis']
        for step in row['steps']:
            if step['text'].startswith('Strimla moroten'):
                step['text'] = step['text'].replace('Strimla moroten tunt och skiva jalapeñon.', 'Skala moroten, väg den ätliga mängden och strimla tunt. Väg upp fryst hackad jalapeño och tillsätt direkt i lagen med all vätska.')
            if step['text'].startswith('Hacka löken'):
                step['text'] = step['text'].replace('resten av saltet', 'hälften av fyllningarnas salt').replace('Mosa potatisen med andra delen.', 'Mosa potatisen med andra delen och återstående hälft av fyllningarnas salt.')
                step['text'] = 'Skölj de kokta bönorna och väg efter avrinning. ' + step['text']
            if step['text'].startswith('Mixa den mjuka anchochilin'):
                step['text'] = step['text'].replace('Mixa den mjuka anchochilin', 'Mixa hela mängden mald Ancho Style-chili')
            if step['text'].startswith('Finhacka tomat och koriander'):
                step['text'] = 'Tärna tomaten. Koka hälften av tomaten med den frysta hackade koriandern under omrörning minst tre minuter eller längre enligt förpackningen. Vänd med resten av tomaten, salsans limejuice och salt. Behåll all saft; detta är en ljummen tomatsalsa.'
                step['minutes'] = 9
        row['steps'][-1]['text'] += ' Skrapa ur all kvarvarande chiliolja från bakpapperet och fördela över tacosen.'
        changes.append('Ground ancho needs no soaking or discard. Salt is added after potato draining, with original dose preserved. Frozen jalapeno cooks in the served pickle liquid; coriander cooks in a visibly warm salsa. All chili oil is served.')
    if base.endswith('chilorio'):
        row['steps'][2].update(text='Väg upp mald Ancho Style-chili. Mixa hela mängden med vitlök, vinäger, oregano och 100 ml vatten till en tjock pasta.' + (' Tillsätt också spiskummin.' if row['variant_id'] != 'simple' else ''), minutes=5, passive=False)
        row['steps'][2]['uses'] = ['anchochili', 'vitlök', 'äppelcidervinäger', 'oregano'] + (['spiskummin'] if row['variant_id'] != 'simple' else [])
        row['steps'][3].update(text='Lyft köttet till ett fat och dra isär det med två gafflar. Behåll allt kokspad, fett och eventuell lök i grytan. Koka utan lock och rör regelbundet cirka 30 minuter tills spadet reducerats till en tjock bottensky; inget spad ska hällas bort. Tiden kan bli längre i en smal gryta.', minutes=35, passive=False, uses=['fläskkarré'] + (['gul lök', 'apelsinjuice'] if row['variant_id'] != 'simple' else []))
        row['steps'][4]['text'] = 'Häll rapsoljan i den breda grytan med den reducerade skyn. Lägg tillbaka allt kött och eventuell saft från fatet. Stek under omrörning tills kanterna får lite färg och rör sedan ner hela chilipastan.'
        row['steps'][5]['text'] = 'Stek och rör på medelvärme tills chilipastan klär köttet och rätten är ganska torr, cirka tio minuter. Om den fastnar, tillsätt 50 ml vatten och låt koka in. Servera hela mängden inklusive allt fett.'
        if row['variant_id'] == 'extended':
            row['steps'][6]['text'] = 'Väg de redan kokta svarta bönorna efter avrinning. Värm med fryst hackad koriander och 30 ml vatten i en liten kastrull minst tre minuter eller längre enligt förpackningen. Koka in allt fritt vatten. Skiva de ansade rädisorna och vänd med bönorna och limejuicen.'
            row['steps'][6]['minutes'] = 9
        changes.append('Ground ancho replaces whole-chili hydration at the same authored edible dose. All pork broth/fat is reduced and served, adding explicit 35 active minutes for pulling/reduction. Frozen coriander and bean liquid are cooked into the side.')
    if base.endswith('spaghetti-aglio-olio'):
        for component in row['components']:
            for item in component['ingredients']:
                if item['name'] == 'pasta':
                    item['requirements'] = ['pack:spaghetti']
                if item['name'] == 'salt' and component['id'] == 'c1':
                    item['quantity'] = 3
        for step in row['steps']:
            if 'med pastakomponentens salt' in step['text']:
                step['text'] = step['text'].replace('med pastakomponentens salt', 'utan tillsatt salt')
                step['uses'].remove('salt')
            if step['text'].startswith('Häll försiktigt 100 ml'):
                step['text'] = step['text'].replace('Lägg i pastan', 'Rör ner pastakomponentens salt. Lägg i spaghettin')
                step['uses'].append('salt')
                step['text'] += ' Servera all sås och hela tillbehörens dressing om tillbehör ingår.'
        changes.append('Require spaghetti. Replace the proposed 8 g salt in discarded cooking water with a new culinary dose of 3 g in the retained sauce; no salt-absorption coefficient is invented.')
    if base.endswith('horiatiki'):
        row['steps'][0]['text'] += ' Låt oliverna rinna av och väg utan fri lag; även kapris vägs efter avrinning om den ingår.' if row['variant_id'] == 'extended' else ' Låt oliverna rinna av och väg utan fri lag.'
        row['steps'][0]['uses'].append('oliver')
        changes.append('Explicit drained olive weight; all salad dressing is served.')
    if base.endswith('gnocchi-di-susine'):
        row['steps'][0]['text'] = 'Skala potatisen, väg den angivna ätliga råa mängden och skär jämnt. Koka upp i 500 ml vatten utan tillsatt salt.'
        row['steps'][2]['text'] = 'Låt den pressade potatisen ånga av och svalna 15 minuter; en blöt massa behöver längre avångning, inte obegränsat extra mjöl.'
        row['steps'][3]['text'] = row['steps'][3]['text'].replace('Dela plommonköttet', 'Kärna ur plommonen, väg den ätliga mängden och dela plommonköttet')
        insert_step(row, 3, {'text': 'Pressa den avrunna potatisen och bred ut tunt på ett fat.', 'uses': ['potatis'], 'minutes': 2, 'after': [2]})
        row['steps'][3]['after'] = [3]
        changes.append('Weigh peeled raw potato and pitted plum; separate two active pressing minutes from fifteen passive cooling minutes.')
    if base.endswith('semla'):
        for step in row['steps']:
            step['text'] = step['text'].replace('Vispa den kalla grädden', 'Vispa den kalla vispgrädden')
        changes.append('Explicit whipping cream, already restricted to reviewed Vispgrädde products by the unchanged intake requirement.')
    if base.endswith('chana-madra'):
        row['steps'][2]['text'] += ' Använd malda kryddor, inklusive malen kardemumma och eventuell malen nejlika; inga hela kapslar eller kryddor ska plockas bort.'
        changes.append('Explicit ground spices retained in the sauce; no assumed extraction from removed pods.')
    if base.endswith('khichu'):
        row['name'] = row['name'].replace('kumminhetta', 'spiskumminhetta')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Hacka chilin fint.', 'Väg upp fryst hackad grön jalapeño och tillsätt direkt utan att tina eller hälla bort vätska.')
        if row['variant_id'] == 'extended':
            for c in row['components']:
                for item in c['ingredients']:
                    if item['name'] == 'jordnötter':
                        item['name'] = 'rostade jordnötter'
            for step in row['steps']:
                step['uses'] = ['rostade jordnötter' if n == 'jordnötter' else n for n in step['uses']]
                step['text'] = step['text'].replace('Hacka jordnötterna', 'Hacka de rostade osaltade jordnötterna')
        changes.append('Use reviewed frozen chopped green jalapeno in the boiled dough; roasted unsalted peanuts explicitly retain the reviewed form.')
    if base.endswith('stompa'):
        for c in row['components']:
            for item in c['ingredients']:
                if item['name'] == 'filmjölk':
                    item.update(quantity=47, unit='g')
        row['steps'][0]['text'] = row['steps'][0]['text'].replace('Rör i filmjölken', 'Väg filmjölken i gram och rör i den')
        changes.append('New culinary gram recipe: 47 g filmjölk per portion replaces the proposed 45 ml. This is a new dose, not a density conversion or a claim of equal amounts.')
    row['version'] = '1.0.1'
    row['notes'] = row.get('notes', '') + ' Innehållsgranskad 2026-11-01 med angiven produktform och mängdenhet; inte provlagad. Mängdändringar redovisas i granskningsrapporten.'
    return changes


def amount_changes(before, after):
    def rows(recipe):
        return {(c['id'], i['name'], i['form']): (i['quantity'], i.get('unit')) for c in recipe['components'] for i in c['ingredients']}
    old, new = rows(before), rows(after)
    return [{'component': k[0], 'ingredient': k[1], 'form': k[2], 'before': old.get(k), 'after': new.get(k)}
            for k in sorted(old.keys() | new.keys()) if old.get(k) != new.get(k)]


def build(stage):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    target = OUTPUT / f'standardized-stage{stage}.json'
    if (REPORT / f'import-stage{stage}.json').exists():
        raise ValueError('Stage is already issued and immutable; create a new stage/version instead')
    vocabulary = library_vocabulary(current_recipes())
    authors, native, records = [], [], []
    for path in sorted(SOURCE.glob('*/source/paket/*.json')):
        doc = json.loads(path.read_bytes())
        for original in doc['recipes']:
            if original['base_id'] not in STAGES[stage]:
                continue
            selected = SELECTED_VARIANTS.get(stage, {}).get(original['base_id'])
            if selected is not None and original['variant_id'] not in selected:
                continue
            row = copy.deepcopy(original)
            changes = correct(row, vocabulary)
            pack, _ = standardize({**doc, 'pack_id': f'reviewed-expansion-round2-stage{stage}', 'recipes': [row]}, vocabulary, reviewed_at='2026-11-01')
            authors.append(row)
            native.extend(pack['recipes'])
            records.append({'source_id': ':'.join(original[k] for k in ('base_id', 'version', 'variant_id')),
                'source_file': path.relative_to(SOURCE).as_posix(), 'source_sha256': sha(path.read_bytes()),
                'runtime_id': ':'.join(row[k] for k in ('base_id', 'version', 'variant_id')),
                'content_review': STAGES[stage][row['base_id']], 'changes': changes,
                'amount_changes': amount_changes(original, row), 'cooking_test': 'not_cooked'})
    assert {r['base_id'] for r in authors} == STAGES[stage].keys()
    raw = encoded({'schema_version': 'smako-meal-pack-v1', 'pack_id': f'reviewed-expansion-round2-stage{stage}', 'recipes': native})
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    hashes = {identity(r): r.design.content_sha256 for r in checked['recipes']}
    for record in records:
        record['content_sha256'] = hashes[record['runtime_id']]
    target.write_bytes(raw)
    (OUTPUT / f'authoring-stage{stage}.json').write_bytes(encoded({'schema_version': 'smako-recipe-authoring-v1', 'pack_id': f'reviewed-expansion-round2-stage{stage}', 'recipes': authors}))
    (REPORT / f'recipe-review-stage{stage}.json').write_bytes(encoded({'reviewed_bases': len(STAGES[stage]), 'reviewed_variants': len(records), 'pack_sha256': sha(raw), 'recipes': records}))
    print({'stage': stage, 'bases': len(STAGES[stage]), 'variants': len(records), 'pack': str(target)})


def admit(stage, qualification=None):
    target = OUTPUT / f'standardized-stage{stage}.json'
    raw = target.read_bytes()
    checked = validate_pack_bytes(raw)
    assert not checked['rejections'], checked['rejections']
    expected = {identity(r) for r in checked['recipes']}
    review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
    assert review['pack_sha256'] == sha(raw)
    assert {r['runtime_id']: r['content_sha256'] for r in review['recipes']} == {
        identity(r): r.design.content_sha256 for r in checked['recipes']}
    if qualification:
        probe = json.loads(qualification.read_bytes())
        results = probe['modes']['estimated']['recipes']
        assert probe['pack_sha256'] == sha(raw) and not probe['input_only']
        assert len(results) == len(expected) and {r['id'] for r in results} == expected
        assert all(r['status'] == 'verified' and r['audit']['passed'] for r in results)
        imported = json.loads((REPORT / f'import-stage{stage}.json').read_bytes())
        assert imported['pack_sha256'] == sha(raw)
        imported.update(qualification_sha256=sha(qualification.read_bytes()), basket_status='verified_estimated')
        (REPORT / f'import-stage{stage}.json').write_bytes(encoded(imported))
        (REPORT / f'qualification-stage{stage}.json').write_bytes(qualification.read_bytes())
        print({'stage': stage, 'qualified': len(expected)})
        return
    diff = pack_diff(checked)
    assert {r['status'] for r in diff} <= {'unchanged', 'new_recipe', 'new_variant'}, diff
    pending = {r['id'] for r in diff if r['status'] in {'new_recipe', 'new_variant'}}
    if not pending:
        print({'stage': stage, 'already_imported': True})
        return
    assert pending == expected, 'The reviewed stage must be imported atomically'
    before = (ROOT / 'library-manifest.json').read_bytes()
    result = import_pack(target, accepted_ids=pending)
    after = (ROOT / 'library-manifest.json').read_bytes()
    assert import_pack(target, accepted_ids=pending)['published_file'] == result['published_file']
    assert (ROOT / 'library-manifest.json').read_bytes() == after
    (REPORT / f'import-stage{stage}.json').write_bytes(encoded({'before_manifest_sha256': sha(before), 'after_manifest_sha256': sha(after),
        'pack_sha256': sha(raw), 'basket_status': 'pending_local_qualification', 'idempotent_reimport': True, 'result': result}))
    print({'stage': stage, 'imported': len(pending)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=int, choices=STAGES, required=True)
    parser.add_argument('--qualifying-report', type=Path)
    parser.add_argument('--import-reviewed', action='store_true')
    args = parser.parse_args()
    if args.qualifying_report:
        admit(args.stage, args.qualifying_report)
    elif args.import_reviewed:
        admit(args.stage)
    else:
        build(args.stage)
