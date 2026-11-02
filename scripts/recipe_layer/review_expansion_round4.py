"""Reproduce two individually reviewed inputs from the existing frozen stores."""
import argparse
import hashlib
import json
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts

TARGET = Path('backend/app/data/ingredients/expansion-round4-20261102.json')
REVIEWS = {
    'apelsinblomsvatten|as_sold|ml': {
        'label': ('Apelsinblom Vatten', 'Yamama', 300), 'article': '101553588_ST',
        'url': 'https://www.yamama-lb.com/rose-blossom-water/',
        'definition': 'Yamama apelsinblomsvatten för matlagning i 300 ml-flaska, samma artikel i befintligt butiksunderlag. Tillverkaren listar blossom water 300 ml separat från rose water. Inte rosvatten, apelsinjuice, sirap eller koncentrerad eterisk olja. Doseras i deklarerade ml; ingen densitet, aromstyrka, renhetsprocent eller näringsdeklaration antas.'},
    'rucola|raw_edible|g': {
        'label': ('Ruccola Klass 1', None, 125), 'article': '101316310_ST',
        'url': 'https://www.garantskafferiet.se/vara-produkter/eko-frukt--gronsaker/sallad/ruccola---garant/',
        'definition': 'Rena finbladiga rucolablad med ätliga stjälkar i 125 g-förpackning. Befintlig butiksetikett Ruccola Klass 1 och artikel 101316310_ST granskas separat från pesto, blandad sallad, krukväxt och 200 g-produkt. Tillverkarens 125 g-sida anger ruccola som enda ingrediens. 65 g-sidan har motstridig småbladsmixtext och används inte som godkännande. Skölj vid behov enligt förpackningen, använd hela uppvägda blad inklusive ätliga stjälkar; ingen rot-/krukvikt eller påhittad svinnandel.'},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def build(inventory):
    document = json.loads(inventory.read_bytes())
    reference = document['reference']
    candidates = {(r['product']['store_id'], r['product']['product_id']): r
                  for group in document['groups'].values() for r in group['products']}
    rows = []
    for key, review in REVIEWS.items():
        name, form, unit = key.split('|')
        links = []
        for candidate in candidates.values():
            p, f = candidate['product'], candidate['facts']
            if (p['name'], p.get('brand'), p['package_quantity']) != review['label']:
                continue
            if (not f or f['conflicts'] or f.get('retailer_product_id') != review['article']
                    or p['package_unit'] != unit or p['usable_unit'] != unit
                    or p['usable_quantity'] != p['package_quantity']
                    or p['sale_model'] != 'fixed_package' or p.get('purchase_terms')
                    or p['quantity_confidence'] != 'exact'):
                continue
            provenance = p['source_provenance']
            assert f['source_product_id'] == p['product_id']
            assert f['source_snapshot_id'] == provenance['source_snapshot_id']
            proof = {field: p.get(field) for field in ('store_id', 'product_id', 'gtin', 'name', 'brand',
                     'category', 'package_quantity', 'package_unit', 'sale_model')}
            proof.update(source_snapshot_id=provenance['source_snapshot_id'], source_sha256=digest(p),
                retailer_product_id=f['retailer_product_id'], source_observed_at=provenance['source_observed_at'],
                source_provenance=provenance, composition_sha256=composition_signature(ProductFacts(**f)),
                review='2026-11-02: ' + review['definition'] + ' No nutrition/allergen/organic approval.',
                culinary_source_url=review['url'], quantity={'method': 'reviewed_plain_fixed_contents_v1',
                    'basis': form, 'unit': unit, 'confidence': 'exact', 'usable_quantity': p['usable_quantity']})
            links.append(proof)
        assert links, key
        requirement = 'intake_all_round4_' + hashlib.sha256(key.encode()).hexdigest()[:12]
        rows.append({'name': name, 'form': form, 'unit': unit, 'requirements': ['pack:' + requirement],
            'kind': 'definition_only', 'definition': review['definition'],
            'required_classification': f'culinary_input:{name}:{form}:{unit}',
            'review_basis': 'Exact source/product/package bindings; culinary review only. ' + review['definition'],
            'evidence': [{'kind': 'reviewed_whole_label_and_form', 'source_url': review['url']}],
            'reviewed_links': links})
    return {'schema_version': 'smako-authoring-vocabulary-v1', 'reviewed_at': '2026-11-02',
        'source_scope': reference['source_scope'], 'universe_sha256': reference['files']['universe']['sha256'],
        'facts_sha256': reference['files']['facts']['sha256'], 'ingredients': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    args = parser.parse_args()
    doc = build(args.inventory)
    TARGET.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print({r['name']: len(r['reviewed_links']) for r in doc['ingredients']})
