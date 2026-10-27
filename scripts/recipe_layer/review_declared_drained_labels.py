"""Bind a reviewed Spicefield label to its exact retained priced product.

Only identity and declared net/drained mass are reviewed here. No price,
nutrient draining basis, allergy or organic status comes from this label.
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

REVIEWS = {
    'water-chestnut': {
        'url': 'https://www.mathem.se/se/products/63223-spicefield-vattenkastanj/',
        'label_sha': 'd9c5a7075782545e859a84e1cb333a7c98f6232681302516739c5070ad3dd52f',
        'label_file': 'water-chestnut-label-acquisition.json', 'name': 'vattenkastanjer',
        'page_name': 'Vattenkastanj', 'product_name': 'Water Chestnut Slices',
        'gtin': '7611612109376', 'article': '101285963_ST', 'net': 220, 'drained': 140,
        'description': 'Skivad vattenkastanj i vatten. 220 gram, avrunnen vikt 140 gram.',
        'ingredients': 'Vatten/vand, vattenkastanjer/ vandkastanjer 63%, surhetsreglerande medel/middel (E330)'},
    'bamboo': {
        'url': 'https://www.mathem.se/se/products/4649-spicefield-bambuskott-skivad/',
        'label_sha': '9ff3aef1da26466e0d4203edf18cc72bd0c2c8b0275ec141159ede2a2e42c62c',
        'label_file': 'bamboo-label-acquisition.json', 'name': 'bambuskott',
        'page_name': 'Bambuskott Skivad', 'product_name': 'Bamboo Shoots Sliced In Water',
        'gtin': '7611612109383', 'article': '101285964_ST', 'net': 410, 'drained': 200,
        'description': 'Bambuskott skivor i vatten.',
        'ingredients': 'Vatten/vand, bambuskott/skud 49%, surhetsreglerande medel/middel (E330).'},
}


def main(args):
    assert not args.output.exists(), 'Preserve prior facts and choose a new output'
    review = REVIEWS[args.kind]
    net, drained = review['net'], review['drained']
    acquisitions = json.loads((args.public / 'mathem-acquisitions.json').read_bytes())
    source = next(r for r in acquisitions if r['url'] == review['url'])
    assert source['status'] == 200 and file_sha(source['local_copy']) == source['sha256']
    soup = BeautifulSoup(Path(source['local_copy']).read_bytes(), 'html.parser')
    text = ' '.join(soup.get_text(' ', strip=True).split())
    assert review['description'] in text
    assert 'Dagab Inköp & Logistik AB har angett ovanstående information.' in text
    product = next(json.loads(n.get_text()) for n in soup.select('script[type="application/ld+json"]')
                   if json.loads(n.get_text()).get('@type') == 'Product')
    assert (product['name'], product['brand']) == (review['page_name'], 'Spicefield')
    label = json.loads((args.public / review['label_file']).read_bytes())
    assert file_sha(label['local_copy']) == label['sha256'] == review['label_sha']
    label['url'] = product['image'][0].replace('&amp;', '&')
    research = json.loads(args.research.read_bytes())
    selected = {}
    for candidates in research['groups'].values():
        for candidate in candidates:
            p = candidate['product']
            if p.get('gtin') == review['gtin']:
                selected[p['store_id'], p['product_id']] = candidate
    assert len(selected) == 1, 'Review any new product/context separately'
    facts = {tuple(k): ProductFacts(**v) for k, v in json.loads(args.facts.read_bytes())['facts']}
    links = []
    for key, candidate in selected.items():
        p = Product.model_validate(candidate['product'])
        assert (p.name, p.brand, p.package_quantity, p.package_unit, p.sale_model) == (
            review['product_name'], 'SPICEFIELD', net, 'g', 'fixed_package')
        assert p.source_provenance.retailer_product_id == review['article']
        assert key not in facts, 'Review any pre-existing declaration before supplementation'
        ingredients = review['ingredients']
        assert ingredients in text
        f = ProductFacts(source=review['url'], source_product_id=p.product_id,
            source_snapshot_id=p.source_provenance.source_snapshot_id,
            ingredients=(ingredients,), ingredients_complete=True,
            ingredient_evidence_kind='product_declaration',
            field_sources={'ingredients': ({**source, 'bound_product_id': p.product_id,
                'bound_store_id': p.store_id, 'bound_snapshot_id': p.source_provenance.source_snapshot_id},),
                'usable_quantity': ({'kind': 'reviewed_declared_drained_mass_v1', 'basis': 'drained',
                    'unit': 'g', 'quantity': drained, 'declared_net_quantity': net,
                    'source': review['url'], 'sha256': source['sha256'], 'label_sha256': label['sha256'],
                    'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
                    'bound_snapshot_id': p.source_provenance.source_snapshot_id},)})
        facts[key] = f
        assert f.source_product_id == p.product_id and f.source_snapshot_id == p.source_provenance.source_snapshot_id
        proof = {k: getattr(p, k) for k in ('store_id', 'product_id', 'gtin', 'name', 'brand',
                 'category', 'package_quantity', 'package_unit', 'sale_model')}
        proof.update(source_snapshot_id=p.source_provenance.source_snapshot_id,
            source_sha256=digest(p.model_dump(mode='json')), source_provenance=p.source_provenance.model_dump(mode='json'),
            retailer_product_id=review['article'], composition_sha256=composition_signature(f),
            retrieval_sha256=file_sha(args.research),
            review=(f"Reviewed branded fixed pack {review['product_name']}, Spicefield {net} g, "
                f"article {review['article']} / GTIN {review['gtin']}. Supplier-provided primary page "
                f"and visually reviewed English front label identify the sliced-in-water pack. The label "
                f"explicitly declares net {net} g and drained {drained} g. The page does not publish a GTIN; "
                "its identity is corroborated by complete brand, variant, net mass and label, not fuzzy "
                "automatic matching. No price or nutrition basis is approved."),
            quantity={'method': 'reviewed_declared_drained_mass_v1', 'basis': 'preserved_drained', 'unit': 'g',
                'confidence': 'exact', 'declared_net_quantity': net, 'usable_quantity': drained,
                'source': source, 'label_source': label, 'declared_ingredients': ingredients})
        links.append(proof)
    registry_path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    registry = json.loads(registry_path.read_bytes())
    row = next(r for r in registry['ingredients'] if (r['name'], r['form']) == (review['name'], 'preserved_drained'))
    row['reviewed_links'] = links
    original = json.loads(args.facts.read_bytes())
    original['facts'].append([list(key), asdict(facts[key])])
    original['facts_version'] += ':reviewed-' + args.kind + '-label:' + digest([links, asdict(f)])
    args.output.write_text(json.dumps(original,ensure_ascii=False,separators=(',', ':'))+'\n',encoding='utf-8')
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'source': source, 'label_source': label,
        'exact_product_links': links, 'facts_before_sha256': file_sha(args.facts),
        'facts_after_sha256': file_sha(args.output), 'nutrition_draining_basis_approved': False,
        'new_price_rows': 0}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print({'reviewed_product_contexts': len(links), 'purchased_net_g': net, 'declared_drained_g': drained})


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('public', 'research', 'facts', 'report', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--kind', choices=REVIEWS, default='water-chestnut')
    main(p.parse_args())
