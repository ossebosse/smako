"""Review exact flat rice noodles, drained sardines and plain loose black tea.

Uses the existing ingredient registry and public product-facts path. Source
photos describe food/form/quantity only; their displayed prices are never used.
"""
import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

from app.models import Product
from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts
from bs4 import BeautifulSoup
from coverage_reference import digest, file_sha

from grocery_data.app.services.axfood_detail_archive import read_document


def content(path):
    return ' '.join(BeautifulSoup(Path(path).read_bytes(), 'html.parser').get_text(' ', strip=True).split())


def main(args):
    assert not args.output.exists(), 'Preserve earlier fact versions'
    sources = json.loads((args.public/'acquisitions.json').read_bytes())
    more = json.loads((args.public/'more-acquisitions.json').read_bytes())
    sardine = next(x for x in sources if x.get('local_copy', '').endswith('sardines.html'))
    label = next(x for x in more if x['local_copy'].endswith('sardines-large.jpg'))
    rice = next(x for x in more if x['local_copy'].endswith('garant-mathem.html'))
    exact = json.loads((args.public/'sardine-exact-article.json').read_bytes())
    tea = json.loads((args.public/'tea-acquisition.json').read_bytes())
    tea_label = json.loads((args.public/'tea-label-acquisition.json').read_bytes())
    assert file_sha(tea['local_copy']) == tea['sha256'] and tea['status'] == 200
    assert file_sha(tea_label['local_copy']) == tea_label['sha256'] == 'ab89acaf2c0ffe10f0e0fa816c1a69e2a16b1ab8994725a0c4e70cd7d7c03aa5'
    assert 'ingredients black tea origin*: sri lanka' in content(tea['local_copy']).casefold() and '500g Loose Tea Packet' in content(tea['local_copy'])
    for proof in (sardine, label, rice, rice['label_source'], exact):
        assert file_sha(proof['local_copy']) == proof['sha256']
    assert all(x['status'] == 200 for x in (sardine, label, rice, exact))
    assert '7340083483448' in content(exact['local_copy']) and '101321848' in content(exact['local_copy'])
    assert 'SARDINER (Sardina pilchardus), solrosolja, salt.' in content(sardine['local_copy'])
    assert 'Ris, vatten.' in content(rice['local_copy'])
    assert label['sha256'] == '081d440098f7b30758bbcc5f889f99d3231870634dd4e4a4ab4cb0ea8d0f43ba'
    assert rice['label_source']['sha256'] == '2b62604eb241c54bb9f7c26f57eecd261a931b69794d73e1428be3f7ed857162'
    historical = json.loads(Path('docs/reviews/coverage-continuation-20261027/axfood-details-review.json').read_bytes())
    assert file_sha(args.archive/'manifest.json') == historical['archive_manifest_sha256']
    manifest = json.loads((args.archive/'manifest.json').read_bytes())
    detail = read_document(args.archive, 'willys', '101716026_ST', manifest=manifest)
    assert detail.status == 'verified' and detail.raw['ean'] == '7311043018758'
    assert detail.raw['displayVolume'] == '250g' and detail.raw['ingredients'] == 'INGREDIENSER Ris, vatten.'
    original = json.loads(args.facts.read_bytes())
    facts = {tuple(k): ProductFacts(**v) for k, v in original['facts']}
    research = json.loads(args.research.read_bytes())
    registry_path = Path('backend/app/data/ingredients/intake-all-20261026.json')
    before = file_sha(registry_path)
    registry = json.loads(registry_path.read_bytes())
    reviewed = []
    cases = [
        ('sardiner', 'preserved_drained', '101321848_ST', '7340083483448', 120, 85,
         'SARDINER (Sardina pilchardus), solrosolja, salt.', sardine, label,
         'Visually read the native 1000-pixel supplier product label: Eldorado sardines in sunflower oil, 120 g net / 85 g explicitly drained. The earlier 300-pixel thumbnail is insufficient for reading this declaration. Exact consumer GTIN/article/net corroborated by primary retailer Tempo Runmarö; no tomato sauce, soybean-oil inference, fish-only nutrition or new price.'),
        ('breda risnudlar', 'dry', '101716026_ST', '7311043018758', 250, 250,
         'INGREDIENSER Ris, vatten.', rice, rice['label_source'],
         'Visually reviewed the native supplier package photograph: dry flat rice ribbons, rather than thin rice vermicelli or round noodles. No numeric width inferred. Full current exact article declaration supplies rice/water and 250-g net mass. Plain noodles, not seasoned instant noodles, wheat/egg noodles or pad-thai sauce.'),
        ('svart te', 'dry', '101254695_ST', None, 500, 500, 'Black tea', tea, tea_label,
         'The manufacturer declares Black tea for the exact Ahmad Ceylon 500-g loose-leaf variant. The native front label was visually read as Ceylon Tea / 500 g / LOOSE TEA. Retained CityGross article 101254695_ST has the same full brand/variant/net package; no GTIN is published in that retained row and none is invented. Not Earl Grey, flavoured tea, green tea or counted tea bags; used dry for the authored smoking process, not an infusion yield.'),
    ]
    for name, form, article, gtin, net, usable, ingredients, source, image, review in cases:
        row = next(r for r in registry['ingredients'] if (r['name'], r['form']) == (name, form))
        links, seen = [], set()
        for candidate in research['groups'][name]:
            p = Product.model_validate(candidate['product']); key = p.store_id, p.product_id
            if key in seen:
                continue
            seen.add(key)
            f = facts.get(key)
            code = p.source_provenance.retailer_product_id or (f.retailer_product_id if f else None)
            if p.chain not in {'citygross', 'willys', 'hemkop'} or code != article:
                continue
            assert p.gtin is None or p.gtin == gtin
            assert p.package_quantity == net and p.package_unit == 'g'
            assert p.sale_model == 'fixed_package' and p.purchase_terms is None
            assert p.name.casefold() == {'sardiner': 'sardiner olja', 'breda risnudlar': 'risnudlar', 'svart te': 'ceylon tea'}[name]
            assert p.brand.casefold() == {'sardiner': 'eldorado', 'breda risnudlar': 'garant', 'svart te': 'ahmad tea'}[name]
            if f:
                assert f.source_product_id == p.product_id and f.source_snapshot_id == p.source_provenance.source_snapshot_id
                assert not f.conflicts
                if f.ingredients and tuple(f.ingredients) != (ingredients,):
                    raise AssertionError('Conflicting retained composition needs separate review')
            else:
                f = ProductFacts(source=source['url'], source_product_id=p.product_id,
                    source_snapshot_id=p.source_provenance.source_snapshot_id)
            if form == 'preserved_drained':
                assert not f.nutrition, 'Drained nutrition requires separate source review'
            bound = {'bound_product_id': p.product_id, 'bound_store_id': p.store_id,
                'bound_snapshot_id': p.source_provenance.source_snapshot_id}
            fields = {**f.field_sources, 'ingredients': ({'source': source['url'], 'sha256': source['sha256'],
                'observed_at': source['observed_at'], 'review': review, **bound},)}
            if form == 'preserved_drained':
                fields['usable_quantity'] = ({'kind': 'reviewed_declared_drained_mass_v1', 'basis': 'drained',
                    'unit': 'g', 'quantity': usable, 'declared_net_quantity': net,
                    'source': image['url'], 'sha256': image['sha256'], **bound},)
            f = replace(f, ingredients=(ingredients,), ingredients_complete=True,
                ingredient_evidence_kind='product_declaration', field_sources=fields)
            facts[key] = f
            proof = {k: getattr(p, k) for k in ('store_id', 'product_id', 'gtin', 'name', 'brand',
                'category', 'package_quantity', 'package_unit', 'sale_model')}
            proof.update(source_snapshot_id=p.source_provenance.source_snapshot_id,
                source_provenance=p.source_provenance.model_dump(mode='json'),
                source_sha256=digest(p.model_dump(mode='json')), retailer_product_id=article,
                composition_sha256=composition_signature(f), retrieval_sha256=file_sha(args.research), review=review,
                quantity={'method': 'reviewed_declared_drained_mass_v1' if form == 'preserved_drained' else 'reviewed_plain_fixed_contents_v1',
                    'basis': form, 'unit': 'g', 'confidence': 'exact', 'usable_quantity': usable,
                    'declared_net_quantity': net, 'source': source, 'label_source': image,
                    'declared_ingredients': ingredients,
                    'exact_gtin_source': exact if form == 'preserved_drained' else {
                        'url': detail.meta['url'], 'sha256': detail.digest, 'gtin': gtin, 'article': article} if name == 'breda risnudlar' else {
                        'url': tea['url'], 'sha256': tea['sha256'], 'identity_basis': 'manually_reviewed_full_brand_variant_net_mass_and_bound_retained_article', 'source_gtin': 'not_published', 'article': article}})
            links.append(proof)
        assert links, name
        existing = row.setdefault('reviewed_links', [])
        assert not any(p.get('retailer_product_id') == article for p in existing)
        existing.extend(links)
        reviewed.append({'ingredient': name, 'form': form, 'contexts': len(links), 'links': links})
    original['facts'] = [[list(k), asdict(v)] for k, v in facts.items()]
    original['facts_version'] += ':reviewed-noodle-shape-sardine-label:' + digest(reviewed)
    args.output.write_text(json.dumps(original, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'registry_before_sha256': before, 'registry_after_sha256': file_sha(registry_path),
        'facts_before_sha256': file_sha(args.facts), 'facts_after_sha256': file_sha(args.output),
        'reviews': reviewed, 'prices_changed': False, 'recipes_changed': False,
        'allergen_organic_or_nutrition_approval_added': False}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print({x['ingredient']: x['contexts'] for x in reviewed}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public', 'archive', 'facts', 'output', 'research', 'report'):
        parser.add_argument('--'+name, type=Path, required=True)
    main(parser.parse_args())
