"""Apply individually reviewed supplier and produce evidence to existing registries.

Run serially through budgeted_check. Uses the established supplier supplement,
request-local quantity projection and exact reviewed-identity gates. No prices,
recipes, source scopes or personal qualifications are created by this script.
"""
import argparse
import json
from dataclasses import asdict
from pathlib import Path

from app.services import intake_product_links as links
from app.services.official_product_facts import (
    _retained_supplier_identity,
    project_usable_quantity,
    supplement_catalog_facts,
)
from coverage_reference import digest, file_sha, load_reference, planner_for

SUPPLIERS = {
    '07332040300219': ('silkestofu', 'as_sold', 'Soft plain silken tofu; supplier declares the complete 400 g product as sold.'),
    '07310130009792': ('gröna linser', 'cooked_drained', 'Supplier explicitly states ready-cooked green lentils, drain/rinse/serve and 230 g drained. Nutrient draining basis remains unspecified.'),
    '07316110003446': ('matjessill', 'preserved_drained', 'Classic spiced matjes herring pieces; supplier declares 125 g drained from 215 g net. Nutrient draining basis remains unspecified.'),
    '07310867511407': ('kefir', 'as_sold', 'Plain kefir: exact supplier package declares 1000 g pack and 1000 ml net. No general dairy density inferred.'),
    '05701073066478': ('gelatinblad', 'as_sold', 'Exact manufacturer GTIN variant declares 12 sheets and 20 g; sibling 10-sheet/17-g variant is excluded. No absent nutrition or ingredient declaration supplied.'),
}
PRODUCE = {
    'pomelo': ('09295', {'Honungspomelo', 'Honungspomelo Klass 1'}),
    'grapefrukt': ('09112', {'Grape Röd', 'Grape Röd Klass 1'}),
}


def proof(product, fact, *, review, quantity, research_sha):
    p = product.model_dump(mode='json')
    prov = p['source_provenance']
    result = {k: p.get(k) for k in ('store_id', 'product_id', 'gtin', 'name', 'brand', 'category',
                                   'package_quantity', 'package_unit', 'sale_model')}
    result.update(source_snapshot_id=prov['source_snapshot_id'], source_sha256=digest(p),
        retailer_product_id=prov.get('retailer_product_id') or (fact.retailer_product_id if fact else None),
        source_observed_at=prov['source_observed_at'], source_provenance=prov,
        review=review, retrieval_sha256=research_sha, quantity=quantity)
    if fact:
        result['composition_sha256'] = links.composition_signature(fact)
    return result


def main(args):
    if args.output.exists():
        raise ValueError('Facts output already exists; preserve it and select a new version')
    prepared, original, _refs, recipes, scope = load_reference(args)
    selected = []
    for p in prepared.universe.products:
        f = original.get((p.store_id, p.product_id))
        gtin = p.gtin or (_retained_supplier_identity(p, f) or {}).get('gtin')
        if gtin and gtin.zfill(14) in SUPPLIERS:
            selected.append(p)
    updated = supplement_catalog_facts(selected, original)
    changed = [{'store_id': k[0], 'product_id': k[1], 'after_sha256': digest(asdict(v)),
                'before_sha256': digest(asdict(original[k])) if k in original else None}
               for k, v in updated.items() if k not in original or v != original[k]]
    version = original.version + ':full-coverage-20261027:' + digest(changed)
    args.output.write_text(json.dumps({'facts_version': version,
        'facts': [[k, asdict(v)] for k, v in updated.items()]}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')

    registry = json.loads(links.PATH.read_bytes())
    rows = {(r['name'], r['form']): r for r in registry['ingredients']}
    added = {}
    for p in selected:
        f = updated.get((p.store_id, p.product_id))
        if not f:
            continue
        declarations = [s for s in f.field_sources.get('supplier_declaration', ())
                        if s.get('identity_method') == 'exact_checksum_gtin_brand_fixed_package'
                        and s.get('gtin', '').zfill(14) in SUPPLIERS]
        if len(declarations) != 1:
            continue
        source = declarations[0]
        name, form, review = SUPPLIERS[source['gtin'].zfill(14)]
        if not f.ingredients_complete and name != 'gelatinblad':
            continue
        row = rows[(name, form)]
        projected = project_usable_quantity(p, f, required_unit=row['unit'])
        if projected.usable_unit != row['unit']:
            continue
        q = {'method': 'existing_exact_supplier_quantity_v1', 'basis': form,
             'unit': projected.usable_unit, 'usable_quantity': projected.usable_quantity,
             'confidence': str(projected.quantity_confidence),
             'source': {k: source[k] for k in ('url', 'sha256', 'observed_at', 'gtin')}}
        item = proof(projected, f, review=review, quantity=q, research_sha=file_sha(args.facts))
        existing = row.setdefault('reviewed_links', [])
        if item not in existing:
            existing.append(item)
            added[name] = added.get(name, 0) + 1

    acquisition = json.loads(args.usda_acquisition.read_bytes())
    assert file_sha(args.food_des) == acquisition['food_des_sha256']
    records = {}
    for line in args.food_des.read_text(encoding='latin-1').splitlines():
        c = [v.strip('~') for v in line.split('^')]
        if c[8]:
            records[c[0]] = {'ndb_no': c[0], 'description': c[2], 'refuse_description': c[7],
                'refuse_percent': float(c[8]), 'scientific_name': c[9], 'raw_record': line}
    yields_path = Path('backend/app/data/nutrition/produce-yields-20261027.json')
    yields = json.loads(yields_path.read_bytes())
    assert yields['source']['food_des_sha256'] == acquisition['food_des_sha256']
    for name, (code, names) in PRODUCE.items():
        row = rows[(name, 'raw_edible')]
        record = records[code]
        fraction = round(1-record['refuse_percent']/100, 8)
        for p in prepared.universe.products:
            if (p.name not in names or not (p.category or '').startswith('Frukt')
                    or p.sale_model not in {'fixed_package', 'variable_weight_package'}
                    or p.package_unit != 'g' or not p.package_quantity or p.purchase_terms):
                continue
            f = updated.get((p.store_id, p.product_id))
            q = {'method': 'usda_sr28_refuse_v1', 'basis': 'raw_edible', 'unit': 'g',
                 'confidence': 'estimated', 'edible_fraction': fraction,
                 'usable_quantity': round(p.package_quantity*fraction, 8),
                 'source': {'url': acquisition['url'], 'sha256': acquisition['food_des_sha256'],
                            'archive_sha256': acquisition['sha256'], 'observed_at': acquisition['observed_at'],
                            'record': record}}
            item = proof(p, f, review='Whole fresh exact pack reviewed against the source taxon and raw edible definition; weigh after removing stated refuse. Population estimate, never exact.',
                         quantity=q, research_sha=file_sha(args.facts))
            item['identity_basis'] = 'whole_fresh_produce'
            existing = row.setdefault('reviewed_links', [])
            if item not in existing:
                existing.append(item)
                added[name] = added.get(name, 0) + 1
        yields['records'][name] = record
    links.PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    yields_path.write_text(json.dumps(yields, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    report = {'before_scope': scope, 'after_facts_sha256': file_sha(args.output),
              'facts_version': version, 'changed_products': changed, 'added_reviewed_links': added}

    # Diagnose the existing beef relation without silently adding meat cuts.
    planner = planner_for('estimated', prepared, original, scope)
    recipe = next(r for r in recipes if any(i.canonical_name == 'nötkött' for i in r.ingredients))
    ingredient = next(i for i in recipe.ingredients if i.canonical_name == 'nötkött')
    from app.services.complete_recipes import product_form_compatible
    report['beef_existing_relation'] = []
    beef = rows[('nötkött', 'raw_edible')]
    for p in prepared.universe.products:
        f = planner.source_facts(p)
        if not links.compatible(beef['requirements'][0].removeprefix('pack:'), p, f):
            continue
        report['beef_existing_relation'].append({'name': p.name, 'store_id': p.store_id,
            'product_id': p.product_id, 'form_passed': product_form_compatible(recipe, 'nötkött', p, f),
            'product_form': p.product_form, 'usable_quantity': p.usable_quantity,
            'recipe_ingredient': ingredient.model_dump(mode='json')})
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print({'selected': len(selected), 'facts_changed': len(changed), 'links': added,
           'beef_current_relations': len(report['beef_existing_relation'])}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'output', 'report', 'usda-acquisition', 'food-des']:
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--clock', required=True)
    main(parser.parse_args())
