"""Bind the reviewed trimmed-mint estimate to exact cut 25-g product contexts.

Inputs are retained source rows plus a hash-bound public food-table acquisition.
No prices, retailer sessions, inferred pot weights or nutrition facts are added.
"""
import argparse
import json
from pathlib import Path

from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts
from coverage_reference import digest, file_sha


def main(args):
    source = json.loads(args.acquisition.read_bytes())
    assert source['url'] == 'https://www.matvaretabellen.no/mynte-ra/'
    assert file_sha(args.source) == source['sha256']
    record = {'food_id': '06.259', 'description': 'Mynte, rå', 'scientific_name': 'Mentha L.',
              'edible_percent': 85, 'foodex2': 'A00XZ', 'part_nature': 'A0F0C',
              'part_description': 'Aromatic herbs (leaves and other minor parts)'}
    source['record'] = record
    research = json.loads(args.research.read_bytes())
    candidates = [(r, file_sha(args.research)) for r in research['groups']['mynta']]
    lund = json.loads(args.lund_universe.read_bytes())['universe']['products']
    facts = {tuple(k): v for k, v in json.loads(args.lund_facts.read_bytes())['facts']}
    # The two user-supplied products are reviewed in their own retained contexts.
    for product in lund:
        if (product['store_id'], product['product_id']) in {
            ('context:hemkop:756955d0e6e05f23', '85a42d2be68940139dcefb7fb924ba96'),
            ('context:coop:23eaae11c9661e68', 'bf0db1652fbb440e976fa47c8ad952ea'),
        }:
            candidates.append(({'product': product, 'facts': facts.get((product['store_id'], product['product_id']))},
                               file_sha(args.lund_universe)))
    links = []
    for candidate, retrieval in candidates:
        p, raw_fact = candidate['product'], candidate['facts']
        prov = p['source_provenance']
        article = prov.get('retailer_product_id') or (raw_fact or {}).get('retailer_product_id')
        axfood = (article == '101599969_ST' and p['name'] == 'Mynta Klass 1'
                  and prov['chain'] in {'willys', 'hemkop'})
        coop = (p.get('gtin') == '7300156599834' and p['name'] == 'Mynta'
                and prov['chain'] == 'coop' and prov['provider_store_id'] == '730400'
                and prov['price_context'] == 'online_fulfillment')
        if not (axfood or coop):
            continue
        assert p['package_quantity'] == 25 and p['package_unit'] == 'g'
        assert p['sale_model'] == 'fixed_package' and not p.get('purchase_terms')
        assert (p.get('category') or '').casefold().startswith('frukt') or (coop and p['category'] == 'Färska örter & Smaksättare')
        assert not raw_fact or not raw_fact.get('ingredients')
        proof = {field: p.get(field) for field in ('store_id', 'product_id', 'gtin', 'name', 'brand', 'category',
                                                  'package_quantity', 'package_unit', 'sale_model')}
        proof.update(source_snapshot_id=prov['source_snapshot_id'], source_sha256=digest(p),
            retailer_product_id=article, source_observed_at=prov['source_observed_at'],
            source_provenance=prov, identity_basis='whole_fresh_produce', retrieval_sha256=retrieval,
            review='Exact cut fresh mint 25-g food package. Generic trimmed leaves and tender stems, not picked leaves alone. No roots, pot, dried spice, tea, sauce or pet product.',
            quantity={'method': 'matvaretabellen_edible_fraction_v1', 'basis': 'raw_edible', 'unit': 'g',
                      'confidence': 'estimated', 'edible_fraction': 0.85, 'usable_quantity': 21.25,
                      'source': source})
        if raw_fact:
            proof['composition_sha256'] = composition_signature(ProductFacts(**raw_fact))
        links.append(proof)
    assert len({(p['store_id'], p['product_id']) for p in links}) == len(links)
    assert any(p['store_id'] == 'context:hemkop:756955d0e6e05f23' for p in links)
    assert any(p['store_id'] == 'context:coop:23eaae11c9661e68' for p in links)
    assert len(links) >= 6
    row = {'name': 'mynta', 'form': 'raw_edible', 'unit': 'g',
           'requirements': ['pack:intake_all_shape_trimmed_mint'], 'kind': 'definition_only',
           'definition': 'Färsk mynta: blad och mjuka stjälkar efter att grova/skadade delar tagits bort. Väg ansad rå ätlig mängd. Gäller inte recept som kräver enbart plockade blad.',
           'required_classification': 'culinary_input:trimmed_fresh_mint:raw_edible:g',
           'review_basis': 'Original generic raw-edible recipes reviewed separately from leaf-only recipes. Matvaretabellen 06.259 population edible fraction, estimated only, exact cut 25-g package identities.',
           'evidence': [], 'reviewed_links': links}
    path = Path('backend/app/data/ingredients/recipe-shapes-20261026.json')
    registry = json.loads(path.read_bytes())
    registry['ingredients'] = [r for r in registry['ingredients'] if r['requirements'] != row['requirements']] + [row]
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    reference = {'method': 'matvaretabellen_edible_fraction_v1', 'source': source,
        'interpretation': 'Generic population estimate: purchased cut fresh mint net grams times 0.85. Weigh trimmed edible portions. Leaves and tender minor parts; never leaf-only, root/pot, dry, cooked or density conversion.',
        'reviewed_at': '2026-10-27', 'product_links': len(links)}
    Path('backend/app/data/nutrition/mint-yield-20261027.json').write_text(
        json.dumps(reference, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print({'reviewed_mint_links': len(links), 'usable_g_per_25g': 21.25, 'confidence': 'estimated'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'acquisition', 'research', 'lund-universe', 'lund-facts'):
        parser.add_argument('--' + name, type=Path, required=True)
    main(parser.parse_args())
