"""Bind missing store copies of two individually reviewed frozen foods."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts

TARGET = Path('backend/app/data/ingredients/intake-all-20261026.json')
REPORT = Path('docs/reviews/recipe-unblock-round2-20261101/frozen-store-links.json')
SELECTIONS = {'koriander': ('Koriander Finhackad Fryst', 'Garant', 50.0),
              'avokado': ('Avokado Skivor Fryst', 'Garant', 300.0)}
BATCH = 'frozen-coriander-avocado-stores-20261101'


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def main(path):
    inventory = json.loads(path.read_bytes())
    reference = inventory['reference']
    document = json.loads(TARGET.read_bytes())
    assert document['universe_sha256'] == reference['files']['universe']['sha256']
    assert reference == json.loads(Path('ci/coverage-reference.json').read_bytes())
    changes = []
    for name, selection in SELECTIONS.items():
        row = next(r for r in document['ingredients'] if r['name'] == name)
        assert row['form'] == 'raw_edible' and row['unit'] == 'g' and row['kind'] == 'frozen_edible'
        baseline = [p for p in row['evidence'] if p.get('review_batch') != BATCH]
        assert len(baseline) == {'koriander': 2, 'avokado': 3}[name]
        original = next(p for p in baseline if (p['name'], p.get('brand'), p['package_quantity']) == selection)
        known = {(p['store_id'], p['product_id']) for p in baseline}
        additions = []
        for candidate in inventory['groups']['frozen_store_copies']['products']:
            p, fact = candidate['product'], candidate['facts']
            if ((p['name'], p.get('brand'), p['package_quantity']) != selection
                    or (p['store_id'], p['product_id']) in known):
                continue
            assert (fact and not fact['conflicts'] and p['gtin'] is None
                    and p['package_unit'] == p['usable_unit'] == 'g'
                    and p['usable_quantity'] == p['package_quantity']
                    and p['quantity_confidence'] == 'exact' and p['sale_model'] == 'fixed_package'
                    and p.get('purchase_terms') is None)
            assert fact['retailer_product_id'] == original['facts']['retailer_product_id']
            assert composition_signature(ProductFacts(**fact)) == composition_signature(ProductFacts(**original['facts']))
            assert fact['source_product_id'] == p['product_id']
            assert fact['source_snapshot_id'] == p['source_provenance']['source_snapshot_id']
            proof = {k: copy.deepcopy(p.get(k)) for k in (
                'store_id', 'product_id', 'gtin', 'name', 'brand', 'category', 'package_quantity',
                'package_unit', 'quantity_confidence', 'sale_model', 'source_provenance')}
            proof.update(facts=fact, review_batch=BATCH,
                         facts_inventory_sha256=reference['files']['facts']['sha256'],
                         source_product_sha256=hashlib.sha256(encode(p)).hexdigest(),
                         review='Same frozen edible food, exact article/brand/package and unchanged '
                                'composition signature; separate source/store binding. Not fresh herbs '
                                'or whole avocado. No additional nutrition/allergen/organic approval.')
            additions.append(proof)
        assert additions
        row['evidence'] = baseline + sorted(additions, key=lambda p: (p['store_id'], p['product_id']))
        changes.append({'name': name, 'requirement': row['requirements'][0], 'prior_links': len(baseline),
                        'added_links': row['evidence'][len(baseline):]})
    # Historical registry bytes use CRLF and are part of coverage identities.
    TARGET.write_bytes(encode(document).replace(b'\n', b'\r\n'))
    REPORT.write_bytes(encode({'reference': reference, 'ingredients': changes,
                              'reason': 'The same reviewed products existed in more reference stores; '
                                        'missing bindings forced Carne en su jugo into three stores.'}))
    print({r['name']: len(r['added_links']) for r in changes})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    main(parser.parse_args().inventory)
