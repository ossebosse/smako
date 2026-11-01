"""Reproduce individually reviewed expansion inputs from frozen public products.

Exact complete labels below select previously inspected source records. They
are not runtime fuzzy rules. Purchasing retains exact source, package, form,
composition and personal checks through the existing intake relation.
"""
import argparse
import hashlib
import json
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts

TARGET = Path('backend/app/data/ingredients/expansion-20261101.json')

# name|form: unit, culinary definition, individually inspected (label, brand).
REVIEWS = {
    'isterband|as_sold': ('g', 'Småländska isterband som hel korv med ätligt skinn, tillagas enligt produktens anvisning och receptet. Inte annan korv.', [
        ('Isterband Småländska Långa', 'Lithells'), ('Isterband Kalas', 'Ello Lammhult')]),
    'nötstek|raw_edible': ('g', 'Rå benfri nötstek av fransyska i hel bit för långsam tillagning. Inte skivad tillagad rostbiff, marinad eller vilt.', [
        ('Nötstek Fransyska Sverige', 'Garant'), ('Nötstek av Fransyska Sverige', None)]),
    'nötkött för snabbstekning|raw_edible': ('g', 'Rå benfri ryggbiff för strimling och snabb stekning, inte grytkött, marinerat kött eller färdigrätt.', [
        ('Ryggbiff i Skivor Sverige', 'Garant'), ('Ryggbiff Bit Sverige', 'Garant'), ('Ryggbiff Strimlad Sverige', 'Garant')]),
    'sardeller|preserved_drained': ('g', 'Saltade sardellfiléer av Engraulis encrasicolus, avrunna från olja. Zeta 80 g innehåller deklarerat 43 g avrunnen fisk. Inte svensk ansjovis.', [
        ('Sardeller', 'Zeta')]),
    'nötinnanlår|raw_edible': ('g', 'Rå benfri lövbiff av uttryckligen nötinnanlår, lämplig för tunna skivor. Inte tillagad rostbiff eller kryddad pepparbiff.', [
        ('Lövbiff Skivat Nötinnanlår Sverige', None)]),
    'högrev|raw_edible': ('g', 'Rå benfri högrev i bit för långkok, inte burgare, färs eller korv.', [
        ('Högrev Benfri Sverige', 'Smakavgotland'), ('Högrev Benfri Sverige', 'Garant Eko'), ('Högrev Benfri Sverige', None)]),
    'ostronsås|as_sold': ('g', 'Asiatisk ostronsås i deklarerad gramvikt; inte fisksås, ml utan densitetsbevis eller vegetarisk svampsås.', [
        ('Oyster Sauce Gluten Free', 'Healthy Boy')]),
    'kryddnejlika|dry': ('g', 'Malen torkad kryddnejlika som blandas i grytans kryddning; inte hela blommor som lämnas kvar i maten.', [
        ('Nejlikor Malda Påse', 'Kockens')]),
    'porteröl|as_sold': ('ml', 'Porteröl 3,5 procent, deklarerad flaskvolym. Inte lageröl, saft eller antagande om att alkohol försvinner vid tillagning.', [
        ('Porter 3.5% Folköl Glas', 'Dcarnegie')]),
    'olivolja|as_sold': ('ml', 'Ren osmaksatt olivolja i deklarerad ml-volym; ingen annan olja, smaksatt olja eller fri g/ml-konvertering.', [
        ('Olivolja Extra Vergine Classico', 'Zeta'), ('Olivolja Eko Classico Jungfru', 'Zeta')]),
    'parmesan|as_sold': ('g', 'Parmigiano Reggiano utan oätlig ostkant; här granskas enbart färdigriven ost. Inte Grana Padano, ostsås eller smaksatta snacks.', [
        ('Parmigiano Reggiano Grovriven 30%', 'Zeta'), ('Parmigiano Reggiano Grovriven 12mån', 'Garant'),
        ('Parmigiano Reggiano 22mån Riven', 'Garant')]),
    'schalottenlök|raw_edible': ('g', 'Rå skalad och ansad schalottenlök. Hel lök vägs om med uttryckligt uppskattningsval; nettovikt är inte ätlig vikt.', [
        ('Schalottenlök Eko Klass 1', 'Garant Eko')]),
    'fläskkarré|raw_edible': ('g', 'Rå benfri fläskkarré inklusive dess ätliga fett. Inte ben, marinad, kebab eller färdig rätt. Förpackningsviktens uppskattningsstatus bevaras.', [
        ('Fläskkarré Benfri i Bit Sverige', 'Garant'), ('Fläskkarré Benfri i Bit Sverige', 'Garant Eko')]),
    'fisksås|as_sold': ('ml', 'Fermenterad salt fisksås som asiatisk smaksättare, deklarerad ml-volym. Inte färdig dill-/pepparrotssås till fisk eller vegansk ersättning.', [
        ('Fisksås Fish Sauce', 'Oyster Brand'), ('Fisksås', 'Oyster Brand')]),
    'lagerblad|dry': ('g', 'Torkade hela lagerblad. Inköpsmängden avser blad; recept som tar bort bladen kräver separat processgranskning före import.', [
        ('Lagerblad Hela Påse', 'Santa Maria'), ('Lagerblad', 'Kockens')]),
    'ättiksprit 12 procent|as_sold': ('ml', 'Livsmedelsättiksprit med uttryckligen 12 procent syra, ml. Inte 24 procent, rengöringsmedel eller antagen spädning.', [
        ('Ättiksprit 12%', 'Eldorado')]),
    'pinjenötter|as_sold': ('g', 'Ätliga skalade naturella pinjekärnor. Inte hummus, andra nötter eller skalvikt.', [
        ('Pinjenötter Ekologiska', 'Garant Eko')]),
    'ghee|as_sold': ('g', 'Ghee/skirat smör i gram, inte vanlig smörmängd omräknad till ghee eller vegetabiliskt fett.', [
        ('Ghee Nötig Skirat Smör', 'Kung Markatta')]),
    'fänkålsfrön|dry': ('g', 'Torra hela fänkålsfrön; receptets rostning/mortling behålls.', [
        ('Fänkålsfrön Hela Burk', 'Risberg')]),
    'malen ingefära|dry': ('g', 'Torkad malen ingefära, inte färsk rot, pasta eller sötad ingefära.', [
        ('Ingefära Malen Burk', 'Santa Maria'), ('Ingefära Malen Burk', 'Kockens'), ('Ingefära Malen Påse', 'Kockens')]),
    'ljus sirap|as_sold': ('g', 'Ljus baksirap i deklarerad gramvikt. Inte mörk sirap eller antagen densitet.', [
        ('Ljus Sirap', 'Dansukker'), ('Ljus Sirap', 'Garant')]),
    'saffran|dry': ('g', 'Ren torkad saffran. Inte saffransblandning, bakverk, ris eller arom.', [
        ('Saffran Klass 1 Påse', 'Garant'), ('Saffran Pistiller Hela', 'Garant')]),
    'kalvfärs|raw_edible': ('g', 'Rå benfri kalvfärs, ej blandfärs eller färdig rätt. Endast kyld deklarerad förpackning i denna granskning.', [
        ('Kalvfärs 16% Rullpack Sverige', 'Scan')]),
    'lasagneplattor|dry': ('g', 'Torra lasagneplattor av vete; inte färsk pasta, bönpasta eller färdig lasagne.', [
        ('Lasagneplattor Pasta', 'Barilla'), ('Lasagneplattor Pasta', 'Zeta'), ('Lasagneplattor Eko', 'Garant Eko')]),
    'bruna bönor|dry': ('g', 'Torra svenska bruna bönor, som blötläggs och kokas enligt receptet. Inte generiska bönor eller färdig sötad bönrätt.', [
        ('Bruna Bönor Svenskodlade', 'Gogreen')]),
    'guanciale|as_sold': ('g', 'Lufttorkad saltad griskind, inte bacon, pancetta eller rått kött. Eventuell svål/putsning måste granskas i receptet.', [
        ('Guanciale', 'Fumagalli')]),
    'katrinplommon|as_sold': ('g', 'Torkade urkärnade katrinplommon; inte juice, puré eller barnmat.', [
        ('Katrinplommon Torkade Urkärnade', 'Garant')]),
    'vitpeppar|dry': ('g', 'Torkad malen vitpeppar; inte svartpeppar eller blandad krydda.', [
        ('Vitpeppar Malen Burk', 'Santa Maria'), ('Vitpeppar Malen Burk', 'Kockens'), ('Vitpeppar Malen Påse', 'Eldorado')]),
    'hjorthornssalt|dry': ('g', 'Livsmedelsgodkänt hjorthornssalt som bakhjälpmedel. Inte bakpulver, bikarbonat eller rengöringsmedel.', [
        ('Hjorthornssalt Påse', 'Kockens')]),
    'hårt tunnbröd|as_sold': ('g', 'Färdigbakat hårt tunnbröd; inte mjuk wrap, fylld smörgås eller paltbröd.', [
        ('Tunnbröd Hårt', 'Gene')]),
    'mörkt muscovadosocker|dry': ('g', 'Mörkt muscovadosocker med melass, inte ljust muscovado eller strösocker.', [
        ('Muscovado Mörk Rörsocker', 'Dansukker')]),
    'rostade jordnötter|as_sold': ('g', 'Skalade rostade osaltade jordnötter; inte saltade, kryddade eller dragerade nötter.', [
        ('Jordnötter Rostade Osaltade', 'Estrella')]),
    'agar agar|dry': ('g', 'Agar agar i torr pulverform, inte gelatin eller färdig dessert.', [
        ('Agar Agar Pulver', 'Khoisan Tea')]),
    'enbär|dry': ('g', 'Torkade kulinariska enbär; inte dryck eller blandad krydda.', [
        ('Enbär Burk', 'Santa Maria'), ('Enbär Burk', 'Kockens')]),
    'mariekex|as_sold': ('g', 'Naturella bakade mariekex, inte fyllda eller chokladtäckta kex.', [
        ('Mariekex', 'Eldorado'), ('Mariekex 3-pack', 'First Price')]),
    'mjölkpulver|dry': ('g', 'Torrt mjölkpulver för receptets mjölkbas; inte modersmjölksersättning, vassle eller gräddersättning. Fetthalt/funktion granskas per recept.', [
        ('Mjölkpulver', 'Nido')]),
    'rosenvatten|as_sold': ('ml', 'Kulinariskt rosenvatten i deklarerad ml-volym; inte kosmetika, koncentrerad arom eller olja.', [
        ('Rosenvatten', 'Yamama')]),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def main(args):
    inventory = json.loads(args.inventory.read_bytes())
    initial = json.loads(args.blockers.read_bytes())
    rank = {r['identity']: r for r in initial['blockers']}
    source = json.loads(args.sources.read_bytes())
    rows = []
    for key, (unit, definition, labels) in REVIEWS.items():
        name, form = key.split('|')
        assert {u['unit'] for u in rank[key]['usages']} == {unit}, key
        requirement = 'intake_all_expansion_' + hashlib.sha256(key.encode()).hexdigest()[:12]
        links = []
        for candidate in inventory['groups'][key]['products']:
            p, fact = candidate['product'], candidate['facts']
            if (p['name'], p.get('brand')) not in labels:
                continue
            if (not fact or fact['conflicts'] or p['package_unit'] != unit
                    or p['usable_unit'] != unit or not p['package_quantity']
                    or p['usable_quantity'] != p['package_quantity']
                    or p['sale_model'] not in {'fixed_package', 'variable_weight_package'}
                    or p.get('purchase_terms') or p['quantity_confidence'] not in {'exact', 'estimated'}):
                continue
            prov = p['source_provenance']
            assert fact['source_product_id'] == p['product_id']
            assert fact['source_snapshot_id'] == prov['source_snapshot_id']
            proof = {field: p.get(field) for field in (
                'store_id', 'product_id', 'gtin', 'name', 'brand', 'category',
                'package_quantity', 'package_unit', 'sale_model')}
            proof.update(source_snapshot_id=prov['source_snapshot_id'], source_sha256=digest(p),
                         retailer_product_id=fact.get('retailer_product_id') or prov.get('retailer_product_id'),
                         source_observed_at=prov['source_observed_at'], source_provenance=prov,
                         composition_sha256=composition_signature(ProductFacts(**fact)),
                         review='2026-11-01: exact whole source label/package and authored culinary input reviewed. '
                                + definition + ' No nutrition/allergen/organic approval.',
                         quantity={'method': 'reviewed_plain_fixed_contents_v1',
                                   'basis': form, 'unit': unit, 'confidence': p['quantity_confidence'],
                                   'usable_quantity': p['usable_quantity']})
            if name == 'schalottenlök':
                assert p['sale_model'] == 'fixed_package' and p['package_quantity'] == 250
                proof['quantity'].update(method='matvaretabellen_edible_fraction_v1', confidence='estimated',
                                         edible_fraction=.72, usable_quantity=180.0, source=source['shallot'])
            if name == 'sardeller':
                assert p['sale_model'] == 'fixed_package' and p['package_quantity'] == 80
                proof['quantity'].update(method='reviewed_declared_drained_mass_v1', confidence='exact',
                                         form_evidence_location='review_registry',
                                         usable_quantity=43.0, declared_net_quantity=80.0,
                                         source=source['sardeller'], label_source=source['sardeller'])
            links.append(proof)
        if not links:
            raise ValueError('No reviewed product links: ' + key)
        rows.append({'name': name, 'form': form, 'unit': unit, 'requirements': ['pack:' + requirement],
                     'kind': 'definition_only', 'definition': definition,
                     'required_classification': f'culinary_input:{name}:{form}:{unit}',
                     'review_basis': 'Individually reviewed exact source links; identity/form/quantity only. ' + definition,
                     'evidence': [{'kind': 'authoring_definition_review', 'recipe_ids': rank[key]['ids']}],
                     'reviewed_links': links})
    document = {'schema_version': 'smako-authoring-vocabulary-v1', 'reviewed_at': '2026-11-01',
                'source_scope': inventory['reference']['source_scope'],
                'universe_sha256': inventory['reference']['files']['universe']['sha256'],
                'facts_sha256': inventory['reference']['files']['facts']['sha256'],
                'ingredients': rows}
    TARGET.write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print({r['name']: len(r['reviewed_links']) for r in rows})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ['inventory', 'blockers', 'sources']:
        parser.add_argument('--' + arg, type=Path, required=True)
    main(parser.parse_args())
