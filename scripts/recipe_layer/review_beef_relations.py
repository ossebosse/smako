"""Issue this review's four exact beef-cut relations from frozen source rows.

This is an offline review, never fuzzy matching or a source of new prices.
Existing cut requirements, current facts and purchase-mode gates still apply.
"""
import argparse
import hashlib
import json
from pathlib import Path

REVIEWED = {
    ('Ryggbiff Skivad Utvald Sverige', 'Scan', 180, '101361562_ST'):
        'Plain raw beef striploin slices, fixed 180 g pack; manufacturer corroborates exact full variant and mass. No supplier GTIN is grafted onto retailer identity.',
    ('Nötstek Fransyska Sverige', 'Garant', 1100, '100943534_KG'):
        'Raw beef fransyska roasting cut, representative variable pack; existing estimated purchase consent required.',
    ('Lövbiff Skivat Nötinnanlår Sverige', None, 400, '101228179_KG'):
        'Raw sliced beef inner round explicitly named; representative variable pack. Do not substitute other anonymous minute steaks.',
    ('Oxfilé Hel Brasilien', 'Naturkött', 1800, '100966616_KG'):
        'Whole raw beef tenderloin explicitly named; representative variable pack, not slices or a prepared meal.',
}


def main(args):
    raw = args.research.read_bytes()
    document = json.loads(raw)
    path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    registry = json.loads(path.read_bytes())
    target = next(r for r in registry['ingredients'] if r['name'] == 'nötkött')
    added = []
    for row in document['groups']['nötkött']:
        p, f = row['product'], row['facts'] or {}
        key = (p['name'], p['brand'], p['package_quantity'], f.get('retailer_product_id'))
        if key not in REVIEWED:
            continue
        assert p['package_unit'] == p['usable_unit'] == 'g'
        assert p['package_quantity'] == p['usable_quantity']
        assert p['sale_model'] in {'fixed_package', 'variable_weight_package'}
        assert not f['conflicts'] and f['source_product_id'] == p['product_id']
        assert f['source_snapshot_id'] == p['source_provenance']['source_snapshot_id']
        evidence = {k: p[k] for k in ('store_id', 'product_id', 'gtin', 'name', 'brand',
            'category', 'package_quantity', 'package_unit', 'quantity_confidence', 'sale_model', 'source_provenance')}
        evidence.update(facts=f, review=REVIEWED[key],
                        retrieval_sha256=hashlib.sha256(raw).hexdigest())
        if evidence not in target['evidence']:
            target['evidence'].append(evidence)
            added.append({k: evidence[k] for k in ('store_id', 'product_id', 'name', 'review')})
    assert len(added) in {0, 16}
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    args.output.write_text(json.dumps({'research_scope': document['scope'], 'added': added},
                                    ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print({'reviewed_relations_added': len(added)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args())
