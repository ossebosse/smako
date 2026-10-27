"""Review exact plain/dry or raw cured contents from the approved article batch.

Adds scoped links in the existing ingredient registry, never prices or implied
allergy/organic approval. Every listed composition was individually reviewed.
"""
import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from app.models import Product
from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import project_raw_facts
from coverage_reference import digest, file_sha

from grocery_data.app.services.axfood_detail_archive import read_document, verify_release

REVIEWS = {
    '101328401_ST': ('popcornmajs', '7340083482694', 500, 'INGREDIENSER Majskorn.',
        'Plain dry unpopped corn kernels, not microwave oil/salt mixture or popped snacks.'),
    '101350897_ST': ('popcornmajs', '7340083491924', 400,
        'INGREDIENSER Majskorn*. *Ekologisk ingrediens.',
        'Plain dry unpopped corn kernels. Organic status remains a separate source gate.'),
    '101234770_ST': ('psylliumfröskal', '7320880010016', 300,
        'Ingredienser: Malda psylliumfröskal. Kan innehålla spår av sesam- och senapsfrön.',
        'Ground psyllium husks, not whole seeds. Retain sesame/mustard trace warning and all personal allergy gates.'),
    '101405340_ST': ('psylliumfröskal', '7320880011846', 200,
        'Ingredienser: Ljust pulveriserat psylliumfröskal (psyllium husk)',
        'Pure powdered light psyllium husks, not whole seeds or a composite gluten-free flour.'),
    '101278378_ST': ('rimmat fläsk', '7300202770002', 375,
        'Ingredienser: Svenskt sidfläsk (92%), vatten, salt, glykossirap, antioxidationsmedel (E301), konserveringsmedel (E250). Stekfläsk är en rå produkt som ska tillagas före användning.',
        'Sliced raw cured pork belly, explicitly requiring cooking. Not smoked/cooked bacon; the complete 375-g cured pack is the raw recipe input.'),
}


def main(args):
    assert not args.output.exists(), 'Preserve prior fact versions'
    original = json.loads(args.facts.read_bytes())
    research = json.loads(args.research.read_bytes())
    facts = {tuple(k): ProductFacts(**v) for k, v in original['facts']}
    manifest = verify_release(args.archive)
    registry_path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    before = file_sha(registry_path)
    registry = json.loads(registry_path.read_bytes())
    changed = {}
    fact_reviews = []
    for code, (name, gtin, net, ingredients, review) in REVIEWS.items():
        doc = read_document(args.archive, 'willys', code, manifest=manifest)
        assert doc.status == 'verified'
        raw = doc.raw
        assert (raw['ean'], raw['displayVolume'], raw['ingredients']) == (gtin, f'{net}g', ingredients)
        row = next(r for r in registry['ingredients'] if r['name'] == name)
        assert row['kind'] == 'definition_only' and row['form'] in {'dry', 'raw_edible'} and row['unit'] == 'g'
        links = []
        for candidate in research['groups'][name]:
            p = Product.model_validate(candidate['product'])
            f = facts.get((p.store_id, p.product_id))
            if p.chain not in {'willys', 'hemkop'} or not f or f.retailer_product_id != code:
                continue
            assert p.name == raw['name'] and p.brand == raw['manufacturer']
            assert p.gtin is None or p.gtin == gtin
            assert p.source_provenance and f.source_product_id == p.product_id
            assert f.source_snapshot_id == p.source_provenance.source_snapshot_id and not f.conflicts
            assert p.package_quantity == p.usable_quantity == net
            assert p.package_unit == p.usable_unit == 'g' and p.quantity_confidence == 'exact'
            assert p.sale_model == 'fixed_package' and p.purchase_terms is None
            detail = project_raw_facts(raw, chain=p.chain, product_id=p.product_id,
                snapshot_id=f.source_snapshot_id, source_reference=doc.meta['url'], observed_at=doc.meta['fetched_at'])
            assert f.ingredients and tuple(f.ingredients) == tuple(detail.ingredients)
            # The generic raw projector intentionally leaves completeness unknown.
            # These exact five complete declarations were manually reviewed above;
            # mark only their bound facts, retaining every warning/personal flag.
            before_fact = digest(asdict(f))
            complete_source = {'kind': 'reviewed_complete_product_declaration_v1',
                'source': doc.meta['url'], 'sha256': doc.digest, 'article_code': code,
                'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
                'bound_snapshot_id': f.source_snapshot_id, 'review': review}
            f = replace(f, ingredients_complete=True, ingredient_evidence_kind='product_declaration',
                field_sources={**f.field_sources, 'ingredients_complete': (complete_source,)})
            facts[p.store_id, p.product_id] = f
            fact_reviews.append({'product_id': p.product_id, 'store_id': p.store_id,
                'before_sha256': before_fact, 'after_sha256': digest(asdict(f))})
            proof = {k: getattr(p, k) for k in ('store_id', 'product_id', 'gtin', 'name', 'brand',
                'category', 'package_quantity', 'package_unit', 'sale_model')}
            proof.update(source_snapshot_id=p.source_provenance.source_snapshot_id,
                source_provenance=p.source_provenance.model_dump(mode='json'),
                source_sha256=digest(p.model_dump(mode='json')), retailer_product_id=code,
                composition_sha256=composition_signature(f), retrieval_sha256=file_sha(args.research),
                review=review + ' Exact retained article, complete current source composition and fixed net grams reviewed; prices and personal property checks remain separate.',
                quantity={'method': 'reviewed_plain_fixed_contents_v1', 'basis': row['form'], 'unit': 'g',
                    'confidence': 'exact', 'usable_quantity': net,
                    'source': {'url': doc.meta['url'], 'sha256': doc.digest, 'observed_at': doc.meta['fetched_at']}})
            links.append(proof)
        assert links, code
        existing = row.setdefault('reviewed_links', [])
        assert not any(p.get('retailer_product_id') == code for p in existing), 'Preserve and review existing links'
        existing.extend(links)
        changed[code] = {'ingredient': name, 'reviewed_product_contexts': len(links),
            'source_url': doc.meta['url'], 'source_sha256': doc.digest, 'declared_gtin': gtin,
            'declared_net_grams': net, 'review': review, 'links': links}
    original['facts'] = [[list(k),asdict(v)] for k,v in facts.items()]
    original['facts_version'] += ':reviewed-plain-contents:' + digest(fact_reviews)
    args.output.write_text(json.dumps(original,ensure_ascii=False,separators=(',', ':'))+'\n',encoding='utf-8')
    registry_path.write_text(json.dumps(registry,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    args.report.write_text(json.dumps({'registry_before_sha256': before,
        'registry_after_sha256': file_sha(registry_path), 'facts_sha256': file_sha(args.facts),
        'facts_after_sha256': file_sha(args.output), 'fact_reviews': fact_reviews,
        'archive_manifest_sha256': file_sha(args.archive/'manifest.json'), 'reviews': changed,
        'prices_changed': False, 'allergen_or_organic_approval_added': False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print({code: {'ingredient': row['ingredient'], 'product_contexts': row['reviewed_product_contexts']}
        for code,row in changed.items()},flush=True)


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('research','facts','archive','report','output'):
        p.add_argument('--'+name,type=Path,required=True)
    main(p.parse_args())
