"""Reproduce the individually reviewed fixed-pack produce/yield bindings.

Inputs are the frozen retrieval report and the acquired official USDA SR28
FOOD_DES file. Full labels below were reviewed individually; this is not fuzzy
approval. Loose-weight goods and pot weights are intentionally unsupported.
"""
import argparse
import json
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts
from coverage_reference import digest, file_sha

# Source record and culinary scope, checked against each authored definition.
# USDA refuse is a population estimate; actual prepared portions must be weighed.
REVIEWS = {
    'purjolök': ('11246', {'Purjolök St ,', 'Purjolök St Klass 1'}),
    'salladslök': ('11291', {'Salladslök Knippe'}),
    'päron': ('09252', {'Päron Kl 1 Concorde', 'Päron Conference', 'Päron Conference Klass 2', 'Päron Kl 1'}),
    'apelsin': ('09202', {'Apelsiner Eko Navelina', 'Apelsiner Eko Klass 1'}),
    'rädisa': ('11429', {'Rädisa'}),
    'pak choi': ('11116', {'Pak Choi', 'Pak Choi Klass 1'}),
    'palsternacka': ('11298', {'Palsternacka', 'Palsternacka Ekologisk', 'Palsternacka Klass 1', 'Palsternacka Ekologisk Klass 1'}),
    'plommon': ('09279', {'Plommon Röda Laetitia', 'Plommon Röda Klass 1'}),
    'pumpa': ('11485', {'Pumpa Butternut'}),
    'fänkål': ('11957', {'Fänkål Klass 1'}),
    'rotselleri': ('11141', {'Rotselleri Hel Sverige Klass 1'}),
    'banan': ('09040', {'Banan 5-6 St Fairtrade Klass 1 Eko Klase', 'Banan Eko Klass 1', 'Banan Klass 1'}),
    'kålrot': ('11435', {'Kålrot Hel Sverige Klass 1', 'Kålrot Klass 1'}),
    'rättika': ('11430', {'Rättika Mini Klass 1'}),
}


def main(args):
    research = json.loads(args.research.read_bytes())
    acquisition = json.loads(args.acquisition.read_bytes())
    assert file_sha(args.food_des) == acquisition['food_des_sha256']
    records = {}
    for line in args.food_des.read_text(encoding='latin-1').splitlines():
        cols = [v.strip('~') for v in line.split('^')]
        if not cols[8]:
            continue
        records[cols[0]] = {'ndb_no': cols[0], 'description': cols[2], 'refuse_description': cols[7],
                            'refuse_percent': float(cols[8]), 'scientific_name': cols[9], 'raw_record': line}
    path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    registry = json.loads(path.read_bytes())
    counts = {}
    yields = {'method': 'usda_sr28_refuse_v1', 'source': acquisition,
              'interpretation': 'Raw edible = purchased fixed-pack net g * (1 - refuse_percent/100). Population estimate, never exact; weigh the actual edible portion. No pot, density, drained or cooked conversion.', 'records': {}}
    for row in registry['ingredients']:
        if row['name'] not in REVIEWS or row['form'] != 'raw_edible':
            continue
        code, names = REVIEWS[row['name']]
        record = records[code]
        fraction = round(1 - record['refuse_percent'] / 100, 8)
        links = []
        for candidate in research['groups'][row['name']]:
            p, raw_fact = candidate['product'], candidate['facts']
            if (p['name'] not in names or p['sale_model'] not in {'fixed_package', 'variable_weight_package'}
                    or p['package_unit'] != 'g' or not p['package_quantity'] or p.get('purchase_terms')
                    or not (p.get('category') or '').startswith('Frukt')):
                continue
            # Navelina is source-stated navel. The other exact catalogue label
            # is bound to the same GTIN; do not apply navel yield to all oranges.
            article = (p.get('source_provenance') or {}).get('retailer_product_id') or (raw_fact or {}).get('retailer_product_id')
            if row['name'] == 'apelsin' and not (p.get('gtin') == '7311041049730' or article == '100930511_ST'):
                continue
            prov = p['source_provenance']
            proof = {field: p.get(field) for field in ['store_id', 'product_id', 'gtin', 'name', 'brand', 'category',
                                                      'package_quantity', 'package_unit', 'sale_model']}
            proof.update(source_snapshot_id=prov['source_snapshot_id'], source_sha256=digest(p),
                source_observed_at=prov['source_observed_at'], source_provenance=prov,
                identity_basis='whole_fresh_produce',
                review='Whole fresh label/category and exact source identity reviewed against authored raw edible definition; package is gross produce, never edible mass.',
                retrieval_sha256=file_sha(args.research),
                quantity={'method': 'usda_sr28_refuse_v1', 'basis': 'raw_edible', 'unit': 'g',
                          'confidence': 'estimated', 'edible_fraction': fraction,
                          'usable_quantity': round(p['package_quantity'] * fraction, 8),
                          'source': {'url': acquisition['url'], 'sha256': acquisition['food_des_sha256'],
                                     'archive_sha256': acquisition['sha256'], 'observed_at': acquisition['observed_at'],
                                     'record': record}})
            if raw_fact:
                proof['composition_sha256'] = composition_signature(ProductFacts(**raw_fact))
            links.append(proof)
        if links:
            row['reviewed_links'] = links
            yields['records'][row['name']] = record
            counts[row['name']] = len(links)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    Path('backend/app/data/nutrition/produce-yields-20261027.json').write_text(json.dumps(yields, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(counts)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['research', 'acquisition', 'food-des']:
        p.add_argument('--' + name, type=Path, required=True)
    main(p.parse_args())
