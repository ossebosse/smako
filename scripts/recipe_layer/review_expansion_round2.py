"""Reproduce individually selected identities; labels are review selections only."""
import argparse
import hashlib
import json
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts

TARGET = Path('backend/app/data/ingredients/expansion-round2-20261101.json')
REVIEWS = {
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
        name, form, unit = key.split('|')
        requirement = 'intake_all_round2_' + hashlib.sha256(key.encode()).hexdigest()[:12]
        links = []
        for candidate in candidates.values():
            p, fact = candidate['product'], candidate['facts']
            if (p['name'], p.get('brand')) not in labels:
                continue
            if (not fact or fact['conflicts'] or p['package_unit'] != unit
                    or p['usable_unit'] != unit or not p['package_quantity']
                    or p['usable_quantity'] != p['package_quantity']
                    or p['sale_model'] != 'fixed_package' or p.get('purchase_terms')
                    or p['quantity_confidence'] != 'exact'):
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
                         quantity={'method': 'reviewed_plain_fixed_contents_v1',
                                   'basis': form, 'unit': unit, 'confidence': 'exact',
                                   'usable_quantity': p['usable_quantity']})
            if source_url:
                proof['culinary_source_url'] = source_url
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
    TARGET.write_text(json.dumps({'schema_version': 'smako-authoring-vocabulary-v1',
        'reviewed_at': '2026-11-01', 'source_scope': reference['source_scope'],
        'universe_sha256': reference['files']['universe']['sha256'],
        'facts_sha256': reference['files']['facts']['sha256'], 'ingredients': rows},
        ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print({r['name']+'|'+r['unit']: len(r['reviewed_links']) for r in rows})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, action='append', required=True)
    main(parser.parse_args())
