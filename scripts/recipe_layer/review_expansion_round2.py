"""Reproduce individually selected identities; labels are review selections only."""
import argparse
import hashlib
import json
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts

TARGET = Path('backend/app/data/ingredients/expansion-round2-20261101.json')
REVIEWS = {
    'gruyère|as_sold|g': (
        [('Gruyére Hårdost', 'Lustenberger')],
        'Lustenberger schweizisk Gruyère-hårdost, 150 g, artikel 101774848_ST. Källan deklarerar opastöriserad komjölk, salt, syrningskulturer och löpe. Ingen fontinaidentitet, generisk ostblandning eller vegetarisk löpedeklaration. Inköpt gramvikt inkluderar eventuell ostkant som receptet putsar med okänd förlust; ingen avdragsandel eller serverad näring antas.',
        'https://www.hemkop.se/produkt/Gruyere-Hardost-101774848_ST'),
    'mjukt hamburgerbröd|as_sold|g': (
        [('Hamburgerbröd Ljusa 8-pack', 'Pågen')],
        'Pågen färdigbakade mjuka ljusa hamburgerbröd med sesam, 416 g per åttapack. Innehåller bland annat vete, havre, socker och sesam; inte indiskt ladi pav, osötat bröd eller allergenfritt. Ny synligt namngiven brödversion doserar uppvägd gramvikt; ingen styckvikt eller rå deg används i beräkningen.',
        'https://www.pagen.se/produkter/korvbrod-hamburgerbrod/hamburgerbrod/'),
    'cornflakes|as_sold|g': (
        [('Cornflakes', 'Garant')],
        'Garant naturella färdigrostade majsflingor, 500 g, för direkt konsumtion. Innehåller redan socker, salt och kornmalt; inte osötad ren majs, glutenfri produkt, rå makai poha eller risflingor. Ingen smakbeläggning eller choklad. Hela uppvägda produkten används i uttrycklig cornflakes-chivda. Tillverkarens aktuella procent/näring skrivs inte över butikskällans historiska deklaration.',
        'https://www.garantskafferiet.se/vara-produkter/skafferi/flingor--musli/corn-flakes/'),
    'torkade makrutlimeblad|dry|g': (
        [('Lime Blad Torkade', 'Krua')],
        'KRUA torkade makrutlimeblad, 25 g, artikel 101255053_ST. Importörens produkt T05164 beskriver kaffir lime leaves och 100 procent limeblad; leverantörsdeklarationen hos Mathem anger samma märke, vikt och limeblad. Inte färska blad, vanligt limeskal eller currypasta. Gram avser torra inköpta blad före infusion och borttagning. Receptet anger en egen torr dos och okänd överföring till vätskan; inga färsk-torr-faktorer, ätlig slutmassa eller näringsvärden antas.',
        'https://achaulien.se/products/dried-lime-leaves-12-x-25g-krua'),
    'färsk salsicciakorv|as_sold|g': (
        [('Salsicciakorv Färsk Sverige', 'Garant')],
        'Rå färsk salsicciakorv av fläsk från Garant, 350 g. Hela korven inklusive ätlig svintarm används; inte skinnfri färs, tillagad grillkorv eller grekisk loukaniko. Tillverkaren beskriver fänkål, vitlök och örter. Kräver genomstekning i uttrycklig receptversion; all steksky används. Ingen närings- eller allergengodkännande följer av denna identitetsgranskning.',
        'https://production.garantskafferiet.se/vara-produkter/chark/korv/salsiccia/'),
    'benfri lammstek|as_sold|g': (
        [('Lammstek Benfri Sverige', 'Scan'), ('Lammstek Benfri Nya Zeeland', 'Farmers'),
         ('Lammstek Benfri Fryst Nya Zeeland', 'Affco')],
        'Rå benfri lammstek som inköpt vikt före eventuell putsning, färsk eller fryst enligt exakt produktetikett. Inte lammytterfilé, rostbiff, benbärande stek eller get. Källans varierande förpackningsmassa behålls; uppskattat inköpsläge krävs. Recepten beskriver kylupptining, genomkokning av all upptiningsvätska och okänd förlust av eventuella grova senor. Ingen ätlig slutvikt eller näringsretention antas.',
        None),
    'färsk chorizokorv|as_sold|g': (
        [('Chorizokorv Färsk Sverige', 'Garant')],
        'Rå svensk färsk chorizokorv från Garant, 350 g, artikel 101236339_ST och GTIN 7340045507557. Tillverkaren anger fläsk och nöt med bland annat chili, spiskummin, vitlök, oregano och vinäger. Inte mexikansk ursprungsidentitet, färdig grillkorv eller lufttorkad salami. Inköpt hel produkt före borttagning av fjälster; egen granskad receptdos och okänd förlust, ingen ren köttandel eller näring överförs.',
        'https://www.garantskafferiet.se/vara-produkter/chark/korv/chorizo/'),
    'ätklar inläggningssill|preserved_drained|g': (
        [('5minuters Sill Hela Filéer', 'Abba')],
        'Abba 5-minuterssill hela filéer, färdigbehandlad och ätklar direkt enligt tillverkaren. Inte rå salt sill som måste vattnas ur eller läggas in. Förpackning 430 g med 210 g deklarerad avrunnen sill; butikens 210 g är redan avrunnen jämförmängd. Ingen ytterligare avdragsfaktor eller näringsöverföring från lagen.',
        'https://www.mathem.se/se/products/10375-abba-sill-hela-fileer-5-minuter/'),
    'saltgurka|preserved_drained|g': (
        [('Saltgurka Hel', 'Felix')],
        'Felix hela saltgurkor med senapsfrö i saltare ättikslag. Inte alias för sötsur ättiksgurka eller smörgåsgurka. 700 g burk med 340 g deklarerad avrunnen gurka; butikens 340 g är redan avrunnen jämförmängd. Endast explicit receptanpassning med egen mängd; ingen lag konsumeras.',
        'https://www.mathem.se/se/products/9544-felix-saltgurka-hel/'),
    'corned beef på burk|as_sold|g': (
        [('Corned Beef', 'Al Madina')],
        'Al Madina Corned Beef i 340 g-konserv, färdigkokt saltat finfördelat nötkött. Inte rå rimmad oxbringa, rå köttfärs eller skivad pastrami. Hela deklarerade konservinnehållet används inklusive fett och gelé. Egen receptversion och ny dos, ingen rå-kokt-konvertering eller överförd näringsdeklaration.',
        'https://www.almadina.se/products'),
    'ungnötslever|as_sold|g': (
        [('Ungnötslever i Bit Sverige', 'Garant')],
        'Rå ungnötslever i hel bit från Garant, inköpt bruttovikt före eventuell putsning av hinnor. Inte fläsklever, kalvlever, leverpastej eller djurfoder. Källans variabla cirka 800 g och kilopris bevaras; tillverkarens aktuella cirka 600 g byts inte in i referensen. Ny receptversion anger byte från gris till ungnöt och okänt putsutbyte.',
        'https://www.garantskafferiet.se/vara-produkter/svenskt-kott--fagel/not-flask--kalv/ungnotslever-600g/'),
    'kokbanan med skal|as_sold|g': (
        [('Kokbanan', None)],
        'Hel kokbanan/matbanan inklusive tjockt oätligt skal, inte vanlig dessertbanan. Källans variabla cirka 300 g och kilopris bevaras. Receptet kräver mogen gul/svartfläckig frukt och anger kontroll före matlagning; butiksunderlaget bevisar inte mognadsgrad. Ingen skalad vikt, mogen andel eller skalprocent antas.',
        'https://www.hemkop.se/produkt/Kokbanan-100153496_KG'),
    'råa skalade vannameiräkor|as_sold|g': (
        [('Vannameiräka Utan Skal 26/30 Fryst', 'Miramar')],
        'Miramar råa skalade vannameiräkor 26/30 i 400 g-förpackning, GTIN 7350001292809 och artikel 101240180_ST. Hela deklarerade produkten innehåller även vatten, salt och antioxidationsmedel; 90 procent i ingredienslistan används inte som avrunnen andel. Inte kokta räkor eller skalbärande räkor. Kylupptining och genomkokning krävs.',
        'https://www.dabas.com/productsheet/07350001292809'),
    'blåmusselkött utan skal|as_sold|g': (
        [('Musslor', 'Garant')],
        'Garant djupfrysta chilenska blåmusslor utan skal, Mytilus chilensis, 200 g. Artikel 101502109_ST, GTIN 7311043004386. Inte levande musslor med skal, vongole eller musslor i konservlag. Ingen skalandel eller rå/kokt viktkonvertering antas; uppvägd fryst produkt genomhettas enligt förpackningen i granskad receptversion.',
        'https://www.garantskafferiet.se/vara-produkter/fisk--skaldjur/kott-fagel--fisk/blamusslor-utan-skal/'),
    'rostade saltade pistaschkärnor|as_sold|g': (
        [('Pistaschkärnor Utan Skal Rostade Och Saltade', 'Garant')],
        'Garant 65 g rostade saltade pistaschkärnor utan skal. Tillverkarens specifika pistaschkärnor-sida bekräftar ätliga kärnor och salt 1,8 procent. Inte råa osaltade nötter eller den separata äldre pistaschnötter-sidan med motstridigt skalbesked. Explicit saltad garnityr i nya receptversioner; ingen skalandel antas.',
        'https://www.garantskafferiet.se/vara-produkter/choklad--snacks/notter--torkad-frukt/pistaschkarnor/'),
    'salsa verde av tomatillo|as_sold|g': (
        [('Tomatillo Grön', 'Clementejaques')],
        'Färdig Salsa Verde från Clemente Jacques, 370 g. Dabas/Yora GTIN 7501052473505 och samma artikel 101594296 i butikskällorna identifierar tomatillosåsen. Innehåller bland annat vatten, chili, lök, soja och salt; inte hela råa tomatillor. Endast uttrycklig ny såsdos och sänkt tillsatt salt i anpassat recept, ingen mängd tomatillokött antas.',
        'https://www.dabas.com/productsheet/07501052473505'),
    'nötblod|as_sold|ml': (
        [('Nötblod Fryst/sverige', 'Scan')],
        'Fryst rått nötblod för matlagning, Scan 500 ml i befintlig matbutik. Deklarerad volym, ingen densitet eller gramvikt antas. Kräver kylupptining och genomkokning i granskad varm receptversion; inte färdig blodpudding eller djurfoder.',
        None),
    'evaporerad mjölk|as_sold|g': (
        [('Original Kondenserad Mjölk Osötad', 'Rainbow')],
        'Rainbow Original osötad evaporerad komjölk i 410 g-burk. Inte sötad kondenserad mjölk, karamelliserad mjölk eller mjölkpulver. Receptet väger den osötade mjölken i gram; ingen ml-densitet antas.',
        'https://www.rainbowmilk.com/en/products/original-evaporated-milk-15-g'),
    'svensk ansjovis|preserved_drained|g': (
        [('Ansjovis Original', 'Grebbestads')],
        'Kryddade skarpsillsfiléer från Grebbestads, inte sardeller eller ansjoviskryddad sill. Granskad 125 g-burk med deklarerade 79 g avrunnen fisk. Butikskällans mängdfält är redan 79 g jämförmängd; ingen ytterligare avdragsfaktor. Recept väger avrunna filéer utan spad.',
        'https://www.dabas.com/productsheet/07311170022116'),
    'lagrad pecorino|as_sold|g': (
        [('Pecorino 8mån', 'Garant')],
        'Lagrad italiensk hårdost av fårmjölk, Garant 8 månader 150 g. Inte verifierad Pecorino Romano eller DOP. Gram avser inköpt bit före bortskärning av eventuell hård ytkant; ingen ätlig andel antas. Kräver uttrycklig receptanpassning med okänt utbyte.',
        'https://www.garantskafferiet.se/vara-produkter/ost/lagrad-ost/pecorino/'),
    'surdegsfralla|as_sold|g': (
        [('Surdegsfralla Svenskt', 'Dafgårds')],
        'Naturell svensk surdegsfralla från butikens lösbrödsavdelning, deklarerad 80 g. Inte fyllt bröd, surdegsknäcke eller verifierat mexikanskt birote. Receptet anger uttrycklig brödanpassning och uppfriskning av färdigbakad fralla före fyllning; rå deg får inte användas.',
        'https://www.willys.se/produkt/Surdegsfralla-Svenskt-101676551_ST'),
    'hel kyckling|as_sold|g': (
        [('Kyckling Hel Färsk Sverige', 'Garant')],
        'Hel rå färsk kyckling som bruttovikt inklusive skinn och ben. Källans rörliga förpackningsvikt och kilopris behålls; endast uppskattat inköpsläge. Ingen ätlig andel eller tillagad portionsvikt antas.',
        'https://www.garantskafferiet.se/vara-produkter/svenskt-kott--fagel/fagel/farsk-hel-kyckling/'),
    'oxsvans med ben|as_sold|g': (
        [('Oxsvans i Bitar Sverige', 'Garant')],
        'Råa oxsvansbitar som inköpt bruttovikt med ben; inte benfritt nötkött, färdig fond eller uppmätt ätlig vikt. Källans variabla vikt och kilopris behålls. Ben tas bort i granskad tillagning utan antagen utbytesandel.',
        None),
    'rimmat fläsklägg|as_sold|g': (
        [('Fläsklägg Rimmad Sverige', 'Moab')],
        'Rå rimmad fläsklägg som inköpt bruttovikt. Moab säljer både med och utan ben och den frysta butiksetiketten fastställer inte vilken; receptet måste fungera för båda och avlägsna eventuella ben och seg svål. Ingen benfri ätlig mängd eller kokt vikt antas. Variabel vikt/kilopris kräver uppskattat inköpsläge.',
        'https://www.moab.se/konsument'),
    'ägg|as_sold|st': (
        [('Ägg 6p Frigående Inomhus Medium/large', 'Garant'),
         ('Ägg 10p Frigående Inomhus Large', 'Garant'),
         ('Ägg 18p Frigående Inomhus Medium / Large', 'Garant')],
        'Hela råa hönsägg med skal, köpta och doserade som deklarerat antal. Inte gram rå äggmassa eller gram färdigkokt ägg. Kokning och skalning måste beskrivas i receptet med okänd färdig vikt; ingen styckvikt, skalprocent eller kokförlust antas.',
        None),
    'svartvinbärssaft|as_sold|ml': (
        [('Svart Vinbärs Extra Koncentrerad Saft Glas', 'Brunneby')],
        'Koncentrerad sötad svartvinbärssaft i 500 ml-flaska. Inte drickfärdig saft, blanddryck, sockerfri smaksatt dryck eller utspädd volym. Tillverkarens näringsvärde för utspädd dryck används inte som koncentratets.',
        'https://www.brunnebymusteri.se/produkt/svartvinbarssaft/'),
    'svartvinbärsgelé|as_sold|g': (
        [('Svart Vinbärs Gelé', 'Garant')],
        'Sötad svartvinbärsgelé med pektin i 225 g-burk. Inte rödvinbärsgelé, saft eller råa vinbär. Hela uppvägda produkten används.',
        'https://www.mathem.se/se/products/4940-garant-svartvinbarsgele/'),
    'femkryddor|dry|g': (
        [('Five Spice', 'Risberg')],
        'Mald kinesisk Five Spice-blandning från Risberg, 50 g. Tillverkaren anger koriander, fänkål, muskot, ingefära, kanel, nejlika, stjärnanis, sichuanpeppar och kryddextrakt. Inte fem individuella hela kryddor som ska silas bort.',
        'https://www.risbergimporter.se/produkter/five-spices'),
    'salvia|dry|g': (
        [('Salvia Burk', 'Kockens')],
        'Torkade salviablad i 11 g-burk. Separat torr form; inte färsk salvia inklusive stjälkar och ingen färsk-torr-konvertering. Använd smulad i uttrycklig receptversion.',
        'https://www.mathem.se/se/products/822-kockens-salvia-11g-kockens/'),
    'grönsaksfond|as_sold|ml': (
        [('Grönsaksfond', 'Touch Of Taste')],
        'Flytande koncentrerad grönsaksfond i 180 ml-flaska. Inte buljongpulver, tärningar, utspädd buljong eller automatisk ersättning för 12 g pulver. Ny receptversion anger koncentratets ml och processvattnet separat. Näringsvärden för utspädd fond kopieras inte till koncentratet.',
        'https://www.bongtouchoftaste.se/produkter/gronsaksfond/'),
    'grön chili|raw_edible|g': (
        [('Jalapeno Hackad Fryst', 'Garant')],
        'Grön jalapeño, naturell hackad och fryst. Inte röd chili, laginlagd jalapeño eller hel frukt inklusive stjälk. Receptets hackning/upptining/tillagning måste uttryckligen följa denna form.',
        'https://www.garantskafferiet.se/vara-produkter/fryst/gronsaker--potatis/jalapeno/'),
    'jalapeño|raw_edible|g': (
        [('Jalapeno Hackad Fryst', 'Garant')],
        'Naturell hackad fryst grön jalapeño. Separat precis identitet, inte ett globalt alias för alla gröna chilifrukter. Inte inlagda skivor; använd hela uppvägda mängden med all vätska.',
        'https://www.garantskafferiet.se/vara-produkter/fryst/gronsaker--potatis/jalapeno/'),
    'anchochili|dry|g': (
        [('Chili Ancho Burk', 'Santa Maria')],
        'Mald mild Ancho Style-chili i 35 g-burk, inte hela frukter. Endast granskade receptversioner med mald krydda; inga antagna utbyten från frön/stjälkar eller automatiskt ändrad dosering.',
        'https://www.mathem.se/se/products/19889-santa-maria-chilipeppar-ancho-style/'),
    'majstortillas|as_sold|g': (
        [('Corn Tortillas Glutenfri', 'El Taco Truck')],
        'Färdigbakade mjuka majstortillas gjorda med majsmjöl, inte vete-/majsblandning, chips eller spansk potatisomelett. Hela förpackningens deklarerade gram används.',
        'https://eltacotruck.se/produkter/corn-tortillas'),
    'mejram|dry|g': (
        [('Mejram Burk', 'Santa Maria'), ('Mejram Burk', 'Kockens')],
        'Torkad mejram som krydda. Inte färsk mejram i kruka eller kryddblandning.', None),
    'stjärnanis|dry|g': (
        [('Stjärnanis Påse', 'Santa Maria'), ('Stjärnanis Påse', 'Kockens')],
        'Torkad hel stjärnanis. Malning eller borttagning efter kokning behöver uttrycklig receptgranskning; ingen konsumerad andel antas.', None),
    'nejlika|dry|g': (
        [('Nejlikor Malda Påse', 'Kockens'), ('Nejlika Malen Påse', 'Santa Maria')],
        'Malen kryddnejlika för genomblandning i rätten. Inte hela blommor som senare plockas bort. Granskas separat från befintligt register utan att gamla recept ändras.', None),
    'worcestershiresås|as_sold|ml': (
        [('Worcestershire Sauce', 'Lea&perrins')],
        'Lea & Perrins Worcestershire-sås, deklarerad ml-volym. Animalisk fisksås med sardeller; inte vegansk Worcestershire eller soja.',
        'https://www.dabas.com/productsheet/05000111041065'),
    'filmjölk|as_sold|g': (
        [('Filmjölk Original 3%', 'Arla Ko'), ('Filmjölk Ekologisk 3%', 'Garant Eko'),
         ('Naturell Filmjölk Laktosfri 3%', 'Garant')],
        'Naturell osötad filmjölk 3 procent med deklarerad gramvikt. För recept som uttryckligen väger filen. Ingen konvertering av ml till g och ingen antagen densitet.',
        'https://kund.arla.se/sortiment/produkt/arla-ko/filmjolk-3-3pct-1000g-580190/'),
    'vitt matlagningsvin|as_sold|ml': (
        [('Matlagningsvin Vitt', 'Zeta')],
        'Zeta vitt matlagningsvin med reducerad alkoholhalt, deklarerad ml-volym. Uttrycklig kulinarisk anpassning i granskad receptversion; inte alias för vanligt vitt vin.',
        'https://www.zeta.nu/produkter/matlagningsvin-vitt/'),
    'rött matlagningsvin|as_sold|ml': (
        [('Matlagningsvin Rött', 'Zeta')],
        'Zeta rött matlagningsvin med reducerad alkoholhalt, deklarerad ml-volym. Uttrycklig kulinarisk anpassning i granskad receptversion; inte alias för vanligt rött vin.',
        'https://www.zeta.nu/produkter/matlagningsvin-rott/'),
    'granatäppelkärnor|raw_edible|g': (
        [('Granatäpple Kärnor Fryst', 'Garant')],
        'Naturella frysta granatäppelkärnor, skal och membran borttagna. Hela uppvägda mängden inklusive upptiningssaft används; ingen vikt från hel granatfrukt eller juice räknas om.',
        'https://www.mathem.se/se/products/5156-garant-granatapplekarnor-fryst/'),
    'kanderade apelsinskal|as_sold|g': (
        [('Apelsinskal Kanderat', 'Dr Oetker')],
        'Färdigkanderade hackade söta apelsinskal i deklarerad gramvikt, inklusive produktens socker. Ny ingrediens för uttryckliga receptanpassningar; inte rått rivet skal eller dess påhittade utbyte.',
        'https://www.oetker.se/produkter/p/apelsinskal'),
    'vindruvor|raw_edible|g': (
        [('Gröna Druvor Kärnfria Ekologisk Klass 1', None), ('Druvor Mix Kärnfri Klass 1', None)],
        'Råa kärnfria bordsdruvor med ätligt skal. Klasstjälkar räknas bort med uttryckligt tillåten populationsuppskattning, 96 procent ätlig del enligt Matvaretabellen. Inte russin, must eller exakt utbyte för varje klase.',
        'https://www.matvaretabellen.no/drue-ra/'),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def main(args):
    selected = getattr(args, 'only', None)
    if selected and not set(selected) <= REVIEWS.keys():
        raise ValueError('Unknown explicitly selected review')
    candidates = {}
    reference = None
    for path in args.inventory:
        document = json.loads(path.read_bytes())
        if reference is not None:
            assert reference == document['reference']
        reference = document['reference']
        for group in document['groups'].values():
            for candidate in group['products']:
                p = candidate['product']
                key = (p['store_id'], p['product_id'])
                if key in candidates:
                    assert candidates[key] == candidate
                candidates[key] = candidate
    rows = []
    for key, (labels, definition, source_url) in REVIEWS.items():
        if selected and key not in selected:
            continue
        name, form, unit = key.split('|')
        gross_variable = key in {'hel kyckling|as_sold|g', 'oxsvans med ben|as_sold|g',
                                 'rimmat fläsklägg|as_sold|g', 'ungnötslever|as_sold|g',
                                 'kokbanan med skal|as_sold|g', 'benfri lammstek|as_sold|g'}
        requirement = 'intake_all_round2_' + hashlib.sha256(key.encode()).hexdigest()[:12]
        links = []
        for candidate in candidates.values():
            p, fact = candidate['product'], candidate['facts']
            if (p['name'], p.get('brand')) not in labels:
                continue
            drained = {'svensk ansjovis': (125, 79), 'ätklar inläggningssill': (430, 210),
                       'saltgurka': (700, 340)}.get(name)
            if drained and p['package_quantity'] != drained[1]:
                continue
            if (not fact or fact['conflicts'] or p['package_unit'] != unit
                    or p['usable_unit'] != unit or not p['package_quantity']
                    or p['usable_quantity'] != p['package_quantity']
                    or p['sale_model'] != ('variable_weight_package' if gross_variable else 'fixed_package')
                    or p.get('purchase_terms')
                    or p['quantity_confidence'] != ('estimated' if gross_variable else 'exact')):
                continue
            provenance = p['source_provenance']
            assert fact['source_product_id'] == p['product_id']
            assert fact['source_snapshot_id'] == provenance['source_snapshot_id']
            proof = {field: p.get(field) for field in (
                'store_id', 'product_id', 'gtin', 'name', 'brand', 'category',
                'package_quantity', 'package_unit', 'sale_model')}
            proof.update(source_snapshot_id=provenance['source_snapshot_id'], source_sha256=digest(p),
                         retailer_product_id=fact.get('retailer_product_id') or provenance.get('retailer_product_id'),
                         source_observed_at=provenance['source_observed_at'], source_provenance=provenance,
                         composition_sha256=composition_signature(ProductFacts(**fact)),
                         review='2026-11-01: Individually reviewed whole label, source package and culinary form. '
                                + definition + ' No nutrition/allergen/organic approval.',
                         quantity={'method': ('reviewed_as_sold_source_mass_v1' if gross_variable else 'reviewed_plain_fixed_contents_v1'),
                                   'basis': form, 'unit': unit, 'confidence': p['quantity_confidence'],
                                   'usable_quantity': p['usable_quantity']})
            if source_url:
                proof['culinary_source_url'] = source_url
            if drained:
                net, usable = drained
                excerpt = {'svensk ansjovis': 'Grebbestads Ansjovisfilé 125 g x 20 (skarpsillvikt 79 g).',
                           'ätklar inläggningssill': '430 g, Abba. Avrunnen vikt: 210 gram. Leverantör: Orkla Foods Sverige.',
                           'saltgurka': '700 g, Felix. Avrunnen vikt: 340 gram. Leverantör: Orkla Foods Sverige.'}[name]
                source = {'url': source_url, 'reviewed_excerpt': excerpt,
                          'sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                          'sha256_scope': 'UTF-8 reviewed excerpt, not the HTML response',
                          'evidence_kind': 'reviewed_manufacturer_drained_mass',
                          'declared_net_g': net, 'declared_drained_g': usable,
                          'reviewed_at': '2026-11-01'}
                proof['quantity'].update(method='reviewed_source_already_drained_mass_v1',
                    form_evidence_location='review_registry', source_quantity_basis='declared_drained',
                    declared_net_quantity=net, declared_drained_quantity=usable,
                    source=source, label_source=source)
            if name == 'filmjölk' and p['brand'] in {'Garant', 'Garant Eko'}:
                proof['culinary_source_url'] = ('https://production.garantskafferiet.se/vara-produkter/mejeri/fil--yoghurt/ekologisk-fil-3-/'
                    if p['brand'] == 'Garant Eko' else 'https://production.garantskafferiet.se/vara-produkter/mejeri/laktosfritt/laktosfri-filmjolk-3-/')
            if name == 'vindruvor':
                excerpt = 'Drue, rå. Spiselig del: 96 %. Matvare-ID: 06.528.'
                proof['quantity'].update(method='matvaretabellen_edible_fraction_v1', confidence='estimated',
                    edible_fraction=.96, usable_quantity=round(p['package_quantity']*.96, 4),
                    source={'url': source_url, 'record': 'Drue, rå', 'record_id': '06.528',
                        'reviewed_excerpt': excerpt, 'sha256': hashlib.sha256(excerpt.encode()).hexdigest(),
                        'sha256_scope': 'UTF-8 reviewed excerpt, not the HTML response',
                        'edible_fraction': .96, 'reviewed_at': '2026-11-01', 'evidence_kind': 'primary_source_web_read'})
            links.append(proof)
        if not links:
            raise ValueError('No reviewed links: ' + key)
        rows.append({'name': name, 'form': form, 'unit': unit, 'requirements': ['pack:' + requirement],
                     'kind': 'definition_only', 'definition': definition,
                     'required_classification': f'culinary_input:{name}:{form}:{unit}',
                     'review_basis': 'Exact source/product/package bindings; culinary review only. ' + definition,
                     'evidence': [{'kind': 'reviewed_whole_label_and_form', 'source_url': source_url}],
                     'reviewed_links': links})
        if gross_variable or key in {'ägg|as_sold|st', 'lagrad pecorino|as_sold|g', 'gruyère|as_sold|g', 'färsk chorizokorv|as_sold|g', 'torkade makrutlimeblad|dry|g'}:
            rows[-1]['gross_inedible_mass'] = True
    if selected:
        existing = json.loads(TARGET.read_bytes())
        assert existing['universe_sha256'] == reference['files']['universe']['sha256']
        assert existing['facts_sha256'] == reference['files']['facts']['sha256']
        assert existing['source_scope'] == reference['source_scope']
        replacement = {'|'.join(r[k] for k in ('name', 'form', 'unit')): r for r in rows}
        old_keys = {'|'.join(r[k] for k in ('name', 'form', 'unit')) for r in existing['ingredients']}
        rows = [replacement.get('|'.join(r[k] for k in ('name', 'form', 'unit')), r)
                for r in existing['ingredients']] + [r for k, r in replacement.items() if k not in old_keys]
    TARGET.write_text(json.dumps({'schema_version': 'smako-authoring-vocabulary-v1',
        'reviewed_at': '2026-11-01', 'source_scope': reference['source_scope'],
        'universe_sha256': reference['files']['universe']['sha256'],
        'facts_sha256': reference['files']['facts']['sha256'], 'ingredients': rows},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print({r['name']+'|'+r['unit']: len(r['reviewed_links']) for r in rows})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, action='append', required=True)
    parser.add_argument('--only', action='append', help='Review selected name|form|unit keys and preserve other rows; requires the same reference.')
    main(parser.parse_args())
