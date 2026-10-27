"""Compact all original IDs, source needs and dependency-checked basket receipts."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.services.intake_product_links import entries
from app.services.meal_prepared_artifacts import method_signature
from check_recipe_coverage import atomic_json, read_receipt, receipt_key
from coverage_reference import digest, file_sha, imported_recipes, prior_input_report


def source_need(name, form, unit, definition, supported_estimated):
    if supported_estimated:
        return {'classification': ['quantity_policy'],
                'next_action': 'Use the existing documented estimate only after explicit estimated choice, or source an exact prepared-edible quantity for this same culinary form.'}
    specific = {
        'mynta': 'Obtain source-stated edible leaf g for the cut 25-g mint article, or a reviewed yield applicable to its botanical/presentation scope. Fresh net stem+leaf mass is not leaf mass; 429-g pots and dry 8/9-g spice packs are negative cases.',
        'tamarindpasta': 'Only retained food candidate is Chua Hah Seng Tamarindpaste Sour Concentrate 435 ml. Obtain seedless unsweetened paste of the authored strength in g; do not equate concentrated ml with paste g or rewrite the recipe.',
        'masa harina': 'Find an exact priced nixtamalised maize flour SKU and package. The retained masala matches are retrieval false positives; ordinary maize flour/polenta is not masa harina.',
        'pärlkorn': 'Obtain a manufacturer declaration of whole polished pearl barley for an exact priced SKU; Guldkorn/korngryn/full-grain search hits are not evidence of this shape.',
        'kaffe': 'Source actual unsweetened prepared coffee in ml, or separately review a traceable authored brewing correction. Dry coffee g is not brewed coffee ml.',
        'äggula': 'Source separated raw yolk with declared usable g, or a documented reviewed yolk/whole-egg method. Whole shell-egg mass and edible whole egg do not establish yolk g.',
        'äggvita': 'Source separated white with declared usable g, or both source-stated mass and volume for the exact liquid-white pack. Do not assume ml = g.',
    }
    if name in specific:
        return {'classification': ['identity_form', 'quantity_unit', 'source_evidence'], 'next_action': specific[name]}
    if form in {'preserved_drained', 'cooked_drained'}:
        return {'classification': ['form', 'drained_quantity', 'source_evidence'],
                'next_action': f'Source a plain {name} SKU with verified {form} state, exact net and drained {unit}, and current source/retailer/GTIN binding. Raw, shell-on, cooking-water and net-in-brine weights cannot replace drained edible mass.'}
    if unit == 'ml':
        return {'classification': ['quantity_unit', 'source_evidence'],
                'next_action': f'Obtain source-declared usable ml for an exact {name} SKU; a g-only package needs a source-bound mass/volume declaration, never a generic 1:1 density.'}
    if form == 'raw_edible':
        return {'classification': ['identity_form', 'edible_quantity', 'source_evidence'],
                'next_action': f'Source an exact {name} product matching the authored definition and prepared edible g, or a reviewed population yield applicable to that purchased form in estimated mode. No pot/bone/peel/shell or cooked mass inference.'}
    return {'classification': ['identity_form', 'composition', 'quantity_unit', 'source_evidence'],
            'next_action': f'Obtain an exact priced {name} SKU with reviewed full form/composition and native usable {unit}. Required definition: {definition or form}. Keep substitutes/composite flavours blocked.'}


def main(args):
    report = json.loads(args.after.read_bytes())
    before = prior_input_report(json.loads(args.before.read_bytes()), compared_scope=report['scope'])
    references, recipes = imported_recipes()
    assert report['denominator'] == len(report['variants']) == 2200
    assert report['scope']['method_signature'] == method_signature()
    assert references == before['imported_reference_ids'] == [r['original_id'] for r in report['variants']]
    rows_by_name = defaultdict(list)
    for row in entries().values():
        rows_by_name[row['name']].append(row)
    counts, singles, affected = {}, {}, {}
    for mode in ['exact', 'estimated']:
        counts[mode], singles[mode], affected[mode] = Counter(), Counter(), defaultdict(list)
        scopes = report['modes'][mode]['input_scopes']
        for index, row in enumerate(report['variants']):
            groups = {scopes[k]['name'] + '|' + scopes[k]['form'] + '|' + scopes[k]['unit']
                      for k in row['modes'][mode]['blocking_scope_ids']}
            counts[mode].update(groups)
            if len(groups) == 1:
                singles[mode].update(groups)
            for group in groups:
                affected[mode][group].append(index)
    groups = {}
    for group in sorted(counts['exact'].keys() | counts['estimated'].keys()):
        name, form, unit = group.split('|')
        definitions = [r for r in rows_by_name[name] if r['form'] == form]
        definition = definitions[0].get('definition') if definitions else None
        supported_estimated = counts['estimated'][group] == 0 and counts['exact'][group] > 0
        groups[group] = {**source_need(name, form, unit, definition, supported_estimated),
                        'definition': definition,
                        'blocked_variants': {m: counts[m][group] for m in counts},
                        'single_remaining_group_upper_bound': {m: singles[m][group] for m in singles},
                        'affected_indices': {m: affected[m][group] for m in affected},
                        'source_state': 'No new external search is implied; see retained review and acquisition receipts. Missing SKU/evidence is unknown, not proven market absence.'}
    args.output.mkdir(parents=True, exist_ok=True)
    receipt_index = {}
    verified = Counter()
    for index, row in enumerate(report['variants']):
        for mode, outcome in row['modes'].items():
            scopes = report['modes'][mode]['input_scopes']
            outcome['source_need_refs'] = sorted({scopes[k]['name'] + '|' + scopes[k]['form'] + '|' + scopes[k]['unit']
                                                for k in outcome['blocking_scope_ids']})
            outcome['newly_resolved'] = index in report['modes'][mode]['newly_resolved_indices']
            if outcome['receipt']:
                path = Path(outcome['receipt'])
                expected = receipt_key(report['scope'], recipes[index], mode, report['checker_sha256'])
                receipt = read_receipt(path, expected)
                assert receipt and receipt['status'] == outcome['basket']
                receipt_index[path.as_posix()] = {'sha256': file_sha(path), 'dependencies': expected,
                                                  'evidence_sha256': receipt.get('evidence_sha256'), 'status': receipt['status']}
                if receipt['status'] == 'verified':
                    assert receipt['evidence']['basket']['store_count'] <= 2
                    verified[mode] += 1
        row['requires_estimated_input_choice'] = (row['modes']['exact']['inputs'] != 'resolved'
                                                 and row['modes']['estimated']['inputs'] == 'resolved')
        row['verified_basket_only_with_estimated'] = (row['modes']['exact']['basket'] != 'verified'
                                                     and row['modes']['estimated']['basket'] == 'verified')
    for mode in ['exact', 'estimated']:
        assert verified[mode] == report['modes'][mode]['basket_status'].get('verified', 0)
        report['modes'][mode]['blocked_variants_by_group'] = dict(counts[mode])
        report['modes'][mode]['single_group_upper_bound'] = dict(singles[mode])
    report.update(before_sha256=file_sha(args.before), raw_after_sha256=file_sha(args.after),
                  raw_after_local_copy=args.after.as_posix(), source_needs='blockers.json',
                  basket_receipt_index='basket-receipts.json',
                  original_reference_scope={'universe_sha256': before['universe_sha256'],
                                             'facts_sha256': before['facts_sha256'], 'clock': before['clock']})
    atomic_json(args.output / 'coverage.json', report)
    atomic_json(args.output / 'blockers.json', {'groups': groups, 'scope': report['scope'], 'denominator': 2200})
    atomic_json(args.output / 'basket-receipts.json', {'scope_sha256': digest(report['scope']), 'receipts': receipt_index})
    print({'verified': dict(verified), 'groups': len(groups), 'raw_receipts': len(receipt_index)}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['before', 'after', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    main(p.parse_args())
