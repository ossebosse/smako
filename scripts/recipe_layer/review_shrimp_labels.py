"""Bind the reviewed ready-to-eat shrimp labels to two exact priced contexts.

Uses the existing intake registry and quantity projector. No prices, nutrient
basis, allergen clearance or organic approval are created by drained mass.
"""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.models import Product
from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts
from bs4 import BeautifulSoup
from coverage_reference import digest, file_sha

from grocery_data.app.services.axfood_detail_archive import read_document

REVIEWED = {
    '7340083487538': (400, 200, 'faeb5c95d8dafcad74baee52104041b557497b67f78be630703110899b9f302a'),
    '7311043015993': (280, 140, '0fd013a55cf847bbe704e8dbc8d874d760867c4143cf1b6014b4b55716b6803a'),
}


def main(args):
    assert not args.output.exists(), 'Preserve prior facts'
    preflight = json.loads(args.preflight.read_bytes())
    assert {r['gtin'] for r in preflight['reviews']} == set(REVIEWED)
    original = json.loads(args.facts.read_bytes())
    facts = {tuple(k): ProductFacts(**v) for k, v in original['facts']}
    manifest_path = args.archive/'manifest.json'
    historical = json.loads(Path('docs/reviews/coverage-continuation-20261027/axfood-details-review.json').read_bytes())
    assert file_sha(manifest_path) == historical['archive_manifest_sha256']
    manifest = json.loads(manifest_path.read_bytes())
    registry_path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    registry_before = file_sha(registry_path)
    registry = json.loads(registry_path.read_bytes())
    row = next(r for r in registry['ingredients'] if (r['name'], r['form']) == ('räkor', 'cooked_drained'))
    links = []
    for review in preflight['reviews']:
        net, drained, label_sha = REVIEWED[review['gtin']]
        source, label = review['source'], review['source']['label_source']
        assert source['status'] == 200 and file_sha(source['local_copy']) == source['sha256']
        assert file_sha(label['local_copy']) == label['sha256'] == label_sha
        text = ' '.join(BeautifulSoup(Path(source['local_copy']).read_bytes(), 'html.parser').get_text(' ', strip=True).split())
        assert 'Dagab Inköp & Logistik AB har angett ovanstående information.' in text
        assert f'Avrunnen vikt {drained} gram' in text
        assert review['declared_ingredients'] in text
        ready = review['retailer_detail_source']
        detail = read_document(args.archive, 'willys', review['article'], manifest=manifest)
        assert detail.status == 'verified' and detail.digest == ready['sha256']
        assert detail.raw['ean'] == review['gtin'] and detail.meta['url'] == ready['url']
        assert detail.raw['displayVolume'] == f'{net}/{drained}g'
        assert detail.raw['description'] == ready['ready_to_eat_description']
        assert 'Färdiga att använda direkt' in ready['ready_to_eat_description'] or 'äta som de är' in ready['ready_to_eat_description']
        p = Product.model_validate(review['retained_product'])
        assert (p.gtin, p.chain, p.store_id, p.package_quantity, p.usable_quantity, p.package_unit) == (
            review['gtin'], 'citygross', 'context:citygross:33b01007b20e8988', net, drained, 'g')
        assert p.source_provenance.retailer_product_id == review['article']
        assert p.sale_model == 'fixed_package' and p.purchase_terms is None
        key = (p.store_id, p.product_id)
        assert key not in facts, 'Review existing current facts separately'
        bound = {'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
                 'bound_snapshot_id': p.source_provenance.source_snapshot_id}
        quantity = {'kind': 'reviewed_declared_drained_mass_v1', 'basis': 'drained', 'unit': 'g',
            'quantity': drained, 'declared_net_quantity': net, 'source': source['url'],
            'sha256': source['sha256'], 'label_sha256': label_sha, **bound}
        f = ProductFacts(source=source['url'], source_product_id=p.product_id,
            source_snapshot_id=p.source_provenance.source_snapshot_id,
            ingredients=(review['declared_ingredients'],), ingredients_complete=True,
            ingredient_evidence_kind='product_declaration', field_sources={
                'ingredients': ({**source, **bound},), 'usable_quantity': (quantity,),
                'reviewed_culinary_form': ({'form': 'cooked_drained', 'basis': 'hand_peeled_ready_to_eat_shrimp_in_brine',
                    'source': ready['url'], 'sha256': ready['sha256'], **bound},)})
        facts[key] = f
        proof = {name: getattr(p, name) for name in ('store_id', 'product_id', 'gtin', 'name', 'brand',
            'category', 'package_quantity', 'package_unit', 'sale_model')}
        proof.update(source_snapshot_id=p.source_provenance.source_snapshot_id,
            source_provenance=p.source_provenance.model_dump(mode='json'), source_sha256=digest(p.model_dump(mode='json')),
            retailer_product_id=review['article'], composition_sha256=composition_signature(f),
            retrieval_sha256=file_sha(args.preflight),
            review='Exact GTIN and article corroborated by the verified retained Willys document. Supplier-provided Mathem page declares drained shrimp mass, and the visually reviewed front label declares the same net/shrimp pair. Hand-peeled ready-to-eat shrimp in brine is reviewed for cooked_drained input; raw/shell-on shrimp and composite dishes are separate. The catalogue brand field is retained unchanged. No new price or nutrient draining basis.',
            quantity={'method': 'reviewed_declared_drained_mass_v1', 'basis': 'cooked_drained', 'unit': 'g',
                'confidence': 'exact', 'declared_net_quantity': net, 'usable_quantity': drained,
                'source': source, 'label_source': label, 'declared_ingredients': review['declared_ingredients'],
                'exact_gtin_source': ready})
        links.append(proof)
    existing = row.setdefault('reviewed_links', [])
    assert not any(p['gtin'] in REVIEWED for p in existing), 'Preserve and separately review existing links'
    existing.extend(links)
    original['facts'] = [[list(k), asdict(v)] for k, v in facts.items()]
    original['facts_version'] += ':reviewed-falkenberg-drained-labels:' + digest([links, [asdict(facts[p['store_id'], p['product_id']]) for p in links]])
    args.output.write_text(json.dumps(original, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'preflight_sha256': file_sha(args.preflight),
        'facts_before_sha256': file_sha(args.facts), 'facts_after_sha256': file_sha(args.output),
        'registry_before_sha256': registry_before, 'registry_after_sha256': file_sha(registry_path),
        'reviews': links, 'prices_changed': False, 'nutrition_drained_basis_approved': False,
        'allergen_or_organic_approval_added': False}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print({'reviewed_exact_products': len(links)}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('preflight', 'facts', 'output', 'report', 'archive'):
        parser.add_argument('--'+name, type=Path, required=True)
    main(parser.parse_args())
