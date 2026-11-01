"""Append reviewed store copies of the same already-approved ground cardamom."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

TARGET = Path('backend/app/data/ingredients/intake-all-20261026.json')
REPORT = Path('docs/reviews/recipe-unblock-round2-20261101/cardamom-store-links.json')
SELECTIONS = {('Kardemumma Malen Burk', 'Santa Maria', 28.0),
              ('Kardemumma Malen Burk', 'Kockens', 30.0)}


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def main(path):
    inventory = json.loads(path.read_bytes())
    reference = inventory['reference']
    document = json.loads(TARGET.read_bytes())
    assert document['universe_sha256'] == reference['files']['universe']['sha256']
    assert reference == json.loads(Path('ci/coverage-reference.json').read_bytes())
    row = next(r for r in document['ingredients'] if r['name'] == 'kardemumma')
    assert row['form'] == 'dry' and row['unit'] == 'g' and row['kind'] == 'dry'
    baseline = [p for p in row['evidence'] if p.get('review_batch') != 'ground-cardamom-stores-20261101']
    assert len(baseline) == 6
    known = {(p['store_id'], p['product_id']) for p in baseline}
    additions = []
    for candidate in inventory['groups']['cardamom']['products']:
        p, fact = candidate['product'], candidate['facts']
        if ((p['name'], p.get('brand'), p['package_quantity']) not in SELECTIONS
                or (p['store_id'], p['product_id']) in known):
            continue
        assert (fact and not fact['conflicts'] and p['gtin'] is None
                and p['package_unit'] == p['usable_unit'] == 'g'
                and p['usable_quantity'] == p['package_quantity']
                and p['quantity_confidence'] == 'exact' and p['sale_model'] == 'fixed_package'
                and p.get('purchase_terms') is None)
        original = next(x for x in baseline if (x['name'], x.get('brand'), x['package_quantity'])
                        == (p['name'], p.get('brand'), p['package_quantity']))
        assert fact['retailer_product_id'] == original['facts']['retailer_product_id']
        assert fact['ingredients'] == original['facts']['ingredients']
        assert fact['source_product_id'] == p['product_id']
        assert fact['source_snapshot_id'] == p['source_provenance']['source_snapshot_id']
        proof = {k: copy.deepcopy(p.get(k)) for k in (
            'store_id', 'product_id', 'gtin', 'name', 'brand', 'category', 'package_quantity',
            'package_unit', 'quantity_confidence', 'sale_model', 'source_provenance')}
        proof.update(facts=fact, review_batch='ground-cardamom-stores-20261101',
                     facts_inventory_sha256=reference['files']['facts']['sha256'],
                     source_product_sha256=hashlib.sha256(encode(p)).hexdigest(),
                     review='Same reviewed ground spice, exact retailer article, brand and package; '
                            'separate source/snapshot/store binding. No nutrition, allergen or organic approval.')
        additions.append(proof)
    assert len(additions) == 6
    row['evidence'] = baseline + sorted(additions, key=lambda p: (p['store_id'], p['product_id']))
    # This historical byte-hashed registry uses CRLF; preserve its formatting.
    TARGET.write_bytes(encode(document).replace(b'\n', b'\r\n'))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes(encode({'reference': reference, 'ingredient_requirement': row['requirements'][0],
                              'prior_links': 6, 'added_links': row['evidence'][6:],
                              'reason': 'Existing store copies were missing from the exact source registry; '
                                        'Gulab jamun needed a third store only for cardamom.'}))
    print({'added_store_links': len(additions), 'total_links': len(row['evidence'])})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    main(parser.parse_args().inventory)
