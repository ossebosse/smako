"""Version exact supplier facts and reviewed mozzarella links, without pricing I/O.

The sole newly reviewed cheese is GTIN 08000430133035: plain Galbani
mozzarella, fixed 125-g pack, supplier-declared drained quantity 125 g.
No name-only cross-product or gross/edible conversion is authorized.
"""
import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.official_product_facts import _mass_blocking, supplement_catalog_facts
from coverage_reference import digest, file_sha, load_reference

from grocery_data.app.services.product_declarations import declarations, identity_text


def main(args):
    prepared, facts, _references, _recipes, scope = load_reference(args)
    before = {k: digest(asdict(v)) for k, v in facts.items()}
    selected = [p for p in prepared.universe.products
                if (p.gtin or '').zfill(14) == '08000430133035']
    for key, value in supplement_catalog_facts(selected, facts).items():
        facts[key] = value
    registry_path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    registry = json.loads(registry_path.read_bytes())
    row = next(r for r in registry['ingredients']
               if r['name'] == 'mozzarella' and r['form'] == 'preserved_drained')
    supplier = next(r for r in declarations() if r.get('gtin') == '08000430133035')
    assert supplier['comparison_basis'] == 'Per avrunnen vikt'
    assert supplier['comparison_quantity'] == supplier['package_quantity'] == 125
    links = []
    for p in selected:
        fact = facts.get((p.store_id, p.product_id))
        if (p.name != 'Mozzarella' or identity_text(p.brand or '') != 'galbani'
                or p.package_quantity != 125 or p.package_unit != 'g'
                or p.sale_model != 'fixed_package'
                or (p.purchase_terms and (p.purchase_terms.identity_scope != 'product'
                    or p.purchase_terms.quantity_basis != 'source_exact'
                    or p.purchase_terms.variant_selection != 'resolved'
                    or p.purchase_terms.critical_blockers))
                or not fact or _mass_blocking(fact.conflicts)
                or fact.source_product_id != p.product_id
                or fact.source_snapshot_id != p.source_provenance.source_snapshot_id):
            continue
        sources = fact.field_sources.get('usable_quantity', ())
        assert len(sources) == 1 and sources[0]['basis'] == 'drained'
        assert sources[0]['quantity'] == 125 and sources[0]['gtin'].zfill(14) == '08000430133035'
        provenance = p.source_provenance.model_dump(mode='json')
        proof = {field: getattr(p, field) for field in (
            'store_id', 'product_id', 'gtin', 'name', 'brand', 'category',
            'package_quantity', 'package_unit', 'sale_model')}
        proof.update(source_snapshot_id=provenance['source_snapshot_id'],
            source_sha256=digest(p.model_dump(mode='json')),
            retailer_product_id=provenance.get('retailer_product_id'),
            source_observed_at=provenance['source_observed_at'], source_provenance=provenance,
            identity_basis='exact_supplier_gtin_plain_cheese',
            review='Exact checksum GTIN, Galbani brand and fixed 125-g source package. Supplier full milk/salt/rennet/citric-acid formula is plain mozzarella; explicit consumer-level comparison quantity is drained cheese, not brine or transport weight.',
            composition_sha256=composition_signature(fact),
            quantity={'method': 'supplier_declared_drained_mass_v1', 'basis': 'preserved_drained',
                      'unit': 'g', 'confidence': 'exact', 'usable_quantity': 125,
                      'source': supplier['source'], 'supplier_gtin': supplier['gtin'],
                      'declared_quantity_evidence': dict(sources[0])})
        links.append(proof)
    assert links, 'No exact priced supplier identity found; do not fabricate a link'
    row['reviewed_links'] = links
    row.pop('product_evidence_pending', None)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    changes = [{'store_id': k[0], 'product_id': k[1], 'before_sha256': before.get(k),
                'after_sha256': digest(asdict(v)), 'conflicts': list(v.conflicts)}
               for k, v in facts.items() if before.get(k) != digest(asdict(v))]
    version = facts.version + ':coverage-followup-20261027:' + digest(changes)
    args.output.write_text(json.dumps({'facts_version': version,
        'facts': [[k, asdict(v)] for k, v in facts.items()]}, ensure_ascii=False,
        separators=(',', ':')), encoding='utf-8')
    report = {'before_scope': scope, 'after_facts_sha256': file_sha(args.output),
              'after_facts_version': version, 'reviewed_mozzarella_links': links,
              'registry_sha256': file_sha(registry_path), 'changed_products': changes,
              'quantity_blocking_conflicts_in_actual_input': dict(Counter(
                  c for fact in facts.values() for c in _mass_blocking(fact.conflicts)))}
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print({'selected': len(selected), 'linked': len(links), 'changed_facts': len(changes),
           'quantity_blocking_conflicts': report['quantity_blocking_conflicts_in_actual_input']}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'output', 'report']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    main(p.parse_args())
