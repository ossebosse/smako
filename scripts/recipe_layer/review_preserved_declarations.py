"""Review three preserved foods from exact manufacturer/retailer declarations.

Field-specific evidence is retained: current ingredients, declared drained mass,
and exact retail package labels. No prices or nutrient draining basis change.
"""
import argparse
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.models import Product
from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts
from bs4 import BeautifulSoup
from coverage_reference import digest, file_sha

from grocery_data.app.services.axfood_detail_archive import read_document

CASES = [
    ('kronärtskocka', '7311043010936', '101602829_ST', 400, 240),
    ('vinblad', '7331217011699', '101243232_ST', 620, 350),
    ('surkål', '4068500810242', '101194302_ST', 680, 650),
]


def main(args):
    assert not args.output.exists(), 'Preserve prior fact versions'
    original = json.loads(args.facts.read_bytes())
    facts = {tuple(k): ProductFacts(**v) for k, v in original['facts']}
    research = json.loads(args.research.read_bytes())
    manifest_path = args.archive/'manifest.json'
    previous = json.loads(Path('docs/reviews/coverage-continuation-20261027/axfood-details-review.json').read_bytes())
    assert file_sha(manifest_path) == previous['archive_manifest_sha256']
    manifest = json.loads(manifest_path.read_bytes())
    registry_path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    registry_before = file_sha(registry_path)
    registry = json.loads(registry_path.read_bytes())
    reviews = []
    for name, gtin, article, net, drained in CASES:
        doc = read_document(args.archive, 'willys', article, manifest=manifest)
        assert doc.status == 'verified' and doc.raw['ean'] == gtin
        assert doc.raw['displayVolume'] == f'{net}/{drained}g'
        ingredients = doc.raw['ingredients']
        assert ingredients
        # This is the publisher's actual package-label field, not a draining
        # inference. A separate explicit primary declaration below supplies basis.
        label = {'kind': 'verified_retailer_package_label', 'url': doc.meta['url'],
            'sha256': doc.digest, 'display_volume': doc.raw['displayVolume'], 'gtin': gtin,
            'observed_at': doc.meta['fetched_at']}
        extras = {}
        conflicts = ()
        if name == 'kronärtskocka':
            path = args.public/'artichoke-web.txt'; text = path.read_text(encoding='utf-8')
            assert gtin in text and 'Innehåll: 400g (avrunnen vikt: 240g)' in text
            assert 'Kronärtskockshjärtan, vatten, salt, surhetsreglerande medel (citronsyra).' in text
            assert ingredients == 'Ingredienser: Kronärtskockshjärtan, vatten, salt, surhetsreglerande medel (citronsyra).'
            source = {'url': 'https://www.delitea.se/monte-castello-inlagda-kronartskockshjartan-400240g',
                'sha256': file_sha(path), 'local_copy': path.as_posix(),
                'source_format': 'web_tool_extracted_primary_product_page',
                'observed_by_tool_at': datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(),
                'tool_reported_crawl_age': re.search(r'Crawled: ([^;]+)', text).group(1)}
            notes = 'Plain preserved artichoke hearts in water/salt/citric acid; not marinated oil, spread or raw whole artichoke. Primary page explicitly declares 400-g net / 240-g drained and exact consumer EAN. Its cached extraction is identified as such; the freshly verified article label and composition agree.'
        elif name == 'vinblad':
            primary = json.loads((args.public/'sevan-acquisition.json').read_bytes())
            assert primary['status'] == 200 and file_sha(primary['local_copy']) == primary['sha256']
            image = primary['label_source']
            assert file_sha(image['local_copy']) == image['sha256'] == '2aac4a7dddf282272c8c1f39f52bca066d859cd3ad5dab9f94c26c51919c058b'
            text = ' '.join(BeautifulSoup(Path(primary['local_copy']).read_bytes(), 'html.parser').get_text(' ', strip=True).split())
            assert gtin in text and 'NATRIUMDISULFIT' in text and 'NATRIUMDISULFIT' in ingredients
            assert 'Vinblad, vatten / vann, salt,' in ingredients
            source = {**image, 'source_format': 'visually_reviewed_manufacturer_label',
                'manufacturer_page_url': primary['url'], 'manufacturer_page_sha256': primary['sha256'],
                'observed_at': primary['observed_at'], 'visually_verified_pair': '620 g net / 350 g drained',
                'visually_verified_consumer_gtin': gtin}
            # Current manufacturer/Willys ingredients agree. Older third-party
            # potassium-disulfite text is recorded but never imported as facts.
            extras['older_transcription_not_used'] = {'source': 'https://www.delitea.se/sevan-vinblad-620-g',
                'difference': 'Older cached declaration says potassium disulfite; current manufacturer and verified article say sodium disulfite.'}
            extras['nutrition_conflict'] = {'current_manufacturer_protein_per_100g': 3.1,
                'older_visible_label_protein_per_100g': 5.1,
                'resolution': 'No nutritional values or drained nutrition basis approved.'}
            conflicts = ('supplier_nutrition_conflict',)
            notes = 'Plain grape leaves in brine, not stuffed dolmas. Manufacturer page and freshly verified exact article agree on sodium disulfite. Manufacturer label visibly declares consumer GTIN and 620/350-g net/drained pair. Wholesale x12 is not one purchase pack. Older retailer potassium text is not adopted; disputed nutrition remains unknown and flagged.'
        else:
            source = json.loads((args.public/'stollenwerk-acquisition.json').read_bytes())
            assert file_sha(source['local_copy']) == source['sha256'] == '05b8c051b6a609b406b09507ffcf5d38410480c0fe628425e9c5df7546a8340a'
            assert source['matching_page_one_based'] == 21
            visual = args.public.parent/'tmp/pdfs/stollenwerk-p21.png'
            assert visual.exists()
            assert ingredients == 'Ingredienser: Vitkål, salt'
            source.update(source_format='manufacturer_pdf_product_table', manufacturer_article='81212',
                declared_consumer_gtin=gtin, declared_net_grams=680, declared_drained_grams=650,
                visually_reviewed_page=21, visual_copy=visual.as_posix(), visual_sha256=file_sha(visual),
                original_publication_date='unknown')
            notes = 'Plain fermented cabbage and salt. Visually verified manufacturer table, page 21, Sauerkraut article 81212, consumer GTIN 4068500810242: 680-g net / 650-g drained. The 720-ml glass-size field is not a food volume or density. Fresh exact article label agrees; no nutrition draining basis.'
        candidates = [r['product'] for r in research['groups'][name]
            if r['product'].get('gtin') == gtin and r['product']['chain'] == 'citygross']
        assert len(candidates) == 1
        p = Product.model_validate(candidates[0]); key = p.store_id, p.product_id
        assert (p.package_quantity, p.usable_quantity, p.package_unit, p.sale_model) == (net, drained, 'g', 'fixed_package')
        assert p.store_id == 'context:citygross:33b01007b20e8988' and p.source_provenance.retailer_product_id == article
        assert key not in facts, 'Review pre-existing facts separately'
        bound = {'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
            'bound_snapshot_id': p.source_provenance.source_snapshot_id}
        f = ProductFacts(source=doc.meta['url'], source_product_id=p.product_id,
            source_snapshot_id=p.source_provenance.source_snapshot_id, ingredients=(ingredients,),
            ingredients_complete=True, ingredient_evidence_kind='product_declaration', conflicts=conflicts,
            field_sources={'ingredients': ({'source': doc.meta['url'], 'sha256': doc.digest,
                'observed_at': doc.meta['fetched_at'], 'gtin': gtin, **bound},),
                'usable_quantity': ({'kind': 'reviewed_declared_drained_mass_v1', 'basis': 'drained',
                    'quantity': drained, 'unit': 'g', 'declared_net_quantity': net,
                    'source': source['url'], 'sha256': source['sha256'], **bound},)})
        facts[key] = f
        proof = {k: getattr(p, k) for k in ('store_id', 'product_id', 'gtin', 'name', 'brand',
            'category', 'package_quantity', 'package_unit', 'sale_model')}
        proof.update(source_snapshot_id=p.source_provenance.source_snapshot_id,
            source_provenance=p.source_provenance.model_dump(mode='json'), source_sha256=digest(p.model_dump(mode='json')),
            retailer_product_id=article, composition_sha256=composition_signature(f),
            retrieval_sha256=file_sha(args.research), review=notes,
            quantity={'method': 'reviewed_declared_drained_mass_v1', 'basis': 'preserved_drained',
                'unit': 'g', 'confidence': 'exact', 'declared_net_quantity': net, 'usable_quantity': drained,
                'source': source, 'label_source': label, 'declared_ingredients': ingredients},
            source_review_notes=extras)
        row = next(r for r in registry['ingredients'] if (r['name'], r['form']) == (name, 'preserved_drained'))
        prior = row.setdefault('reviewed_links', [])
        assert not any(r['gtin'] == gtin for r in prior)
        prior.append(proof); reviews.append(proof)
    original['facts'] = [[list(k), asdict(v)] for k, v in facts.items()]
    original['facts_version'] += ':reviewed-preserved-declarations:' + digest(reviews)
    args.output.write_text(json.dumps(original, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'facts_before_sha256': file_sha(args.facts),
        'facts_after_sha256': file_sha(args.output), 'registry_before_sha256': registry_before,
        'registry_after_sha256': file_sha(registry_path), 'reviews': reviews,
        'nutrition_drained_basis_approved': False, 'new_price_rows': 0}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print({'reviewed_preserved_product_contexts': len(reviews)}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public', 'research', 'archive', 'facts', 'output', 'report'):
        parser.add_argument('--'+name, type=Path, required=True)
    main(parser.parse_args())
