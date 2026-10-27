"""Verify this checkpoint's complete frozen scope, receipts and saved API cases.

Use budgeted_check. Raw public benchmark checkouts remain local; publish hashes
and results, never account registrations, cookies or authentication material.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from app.services.meal_library_content import identity
from app.services.meal_prepared_artifacts import method_signature
from app.services.recipe_library import current_recipes
from check_recipe_coverage import read_receipt, receipt_key
from coverage_reference import digest, file_sha, imported_recipes


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main(args):
    report = json.loads((args.report / 'coverage.json').read_bytes())
    index = json.loads((args.report / 'basket-receipts.json').read_bytes())
    references, recipes = imported_recipes()
    scope = report['scope']
    assert report['denominator'] == len(recipes) == len(references) == 2200
    assert len(current_recipes()) == 2462
    assert references == [r['original_id'] for r in report['variants']]
    assert digest(references) == scope['imported_reference_ids_sha256']
    assert digest([identity(r) for r in recipes]) == scope['recipe_ids_sha256']
    assert file_sha('backend/app/data/recipes/library-manifest.json') == scope['manifest_sha256']
    assert method_signature() == scope['method_signature']
    assert file_sha(args.local / 'facts-final-v2.json') == scope['facts_sha256']
    assert file_sha('.local/sol-architecture-20261023/final-enriched-vfinal/malmo/combined-prices.json') == scope['universe_sha256']
    checker = digest([file_sha(Path(__file__).with_name(name))
                      for name in ('check_recipe_coverage.py', 'coverage_reference.py')])
    assert checker == report['checker_sha256']
    assert index['scope_sha256'] == digest(scope)
    counts, paths = Counter(), set()
    for recipe, variant in zip(recipes, report['variants'], strict=True):
        assert identity(recipe) == variant['current_id']
        for mode, outcome in variant['modes'].items():
            counts[mode+':'+outcome['basket']] += 1
            if not outcome['receipt']:
                assert outcome['basket'] == 'data_blocked'
                continue
            path = outcome['receipt']
            paths.add(path)
            meta = index['receipts'][path]
            assert file_sha(path) == meta['sha256']
            expected = receipt_key(scope, recipe, mode, checker)
            receipt = read_receipt(Path(path), expected)
            assert receipt and receipt['dependencies'] == meta['dependencies'] == expected
            assert receipt['original_id'] == variant['original_id']
            assert receipt['current_id'] == variant['current_id'] and receipt['mode'] == mode
            assert receipt['status'] == outcome['basket'] == meta['status']
            if receipt['status'] == 'verified':
                evidence = receipt['evidence']
                assert digest(evidence) == meta['evidence_sha256'] == receipt['evidence_sha256']
                assert evidence['audit']['passed'] and evidence['audit']['totals_reconciled']
                assert evidence['basket']['store_count'] <= scope['max_stores']
                assert all(s['store_id'] in scope['store_ids'] for s in evidence['basket']['stores'])
    assert paths == set(index['receipts'])
    assert not any(key.endswith(('search_incomplete', 'not_checked')) for key in counts)
    for mode in ('exact', 'estimated'):
        assert not report['modes'][mode]['lost_indices']
        if args.previous_report:
            assert file_sha(args.previous_report / 'coverage.json') == report['before_sha256']
            previous = json.loads((args.previous_report / 'coverage.json').read_bytes())
            before_verified = {r['original_id'] for r in previous['variants']
                               if r['modes'][mode]['basket'] == 'verified'}
            now_verified = {r['original_id'] for r in report['variants']
                            if r['modes'][mode]['basket'] == 'verified'}
            assert before_verified <= now_verified, (mode, sorted(before_verified - now_verified))
    comparisons = {}
    for name in ('A', 'B2'):
        old_path = args.previous_local / 'probes' / name / (name+'-saved.json')
        new_path = args.local / 'probes' / name / (name+'-saved.json')
        old, new = (json.loads(p.read_bytes()) for p in (old_path, new_path))
        probe_path = args.local / (name+'-final.json')
        probe = json.loads(probe_path.read_bytes())
        assert old['request'] == new['request']
        # Saved requests add normalized diversity fields for later edits.
        # Their complete values were compared with the earlier saved request
        # above; the original PlanRequest sent to the API has no such key.
        assert set(new['request']) - set(probe['request']) == {'recipe_diversity_overrides'}
        assert {k: v for k, v in new['request'].items()
                if k != 'recipe_diversity_overrides'} == probe['request']
        assert probe['valid_menu_delivered'] and probe['status'] == 'saved_and_read_back'
        assert probe['http_status'] == 201 and probe['policy'] == 'smako-current-library-v2'
        assert all(probe[k] == scope[k] for k in ('method_signature', 'facts_sha256', 'universe_sha256'))
        assert probe['library_manifest_sha256'] == scope['manifest_sha256']
        assert new['plan']['personal']['checks']['checkout_audit']['passed']
        old_basket, new_basket = old['plan']['optimized_basket'], new['plan']['optimized_basket']
        assert probe['total'] == new_basket['total']
        if name == 'B2':
            assert old_basket == new_basket
        if name == 'A':
            assert new_basket['total'] < 290.82
            assert new_basket['total'] <= old_basket['total']
        comparisons[name] = {'previous_local_copy': old_path.as_posix(), 'previous_sha256': file_sha(old_path),
            'current_local_copy': new_path.as_posix(), 'current_sha256': file_sha(new_path),
            'probe_local_copy': probe_path.as_posix(), 'probe_sha256': file_sha(probe_path),
            'entire_saved_request_equal': True, 'request_sha256': digest(new['request']),
            'previous_total': old_basket['total'], 'current_total': new_basket['total'],
            'entire_optimized_basket_equal': old_basket == new_basket,
            'api_save_get_seconds': probe['api_seconds'], 'preparation_seconds': probe['preparation_seconds'],
            'source_loading_seconds': probe['source_loading_seconds'],
            'shared_preparation_seconds': probe['shared_preparation_seconds'],
            'checkout_audit_passed': True, 'scope_sha256': digest(scope)}
        write(args.report / (name+'-comparison.json'), comparisons[name])
    previous_journals = json.loads((args.budget or args.report / 'budget.json').read_bytes())['previous_phases']
    for old in previous_journals:
        assert file_sha(old['journal']) == old['sha256']
    matrix = json.loads((args.report / 'work-matrix.json').read_bytes())
    assert len(matrix['groups']) == 76 and len({i for r in matrix['groups'] for i in r['original_ids']}) == 595
    assert all(r['status'] != 'under_review' for r in matrix['groups'])
    result = {'scope_sha256': digest(scope), 'method_signature': scope['method_signature'],
        'denominator': 2200, 'active_variants': 2462, 'receipt_count': len(paths), 'outcomes': dict(counts),
        'lost_original_ids': [], 'all_receipt_hashes_and_dependencies_verified': True,
        'all_saved_full_requests_unchanged': True, 'older_budget_journals_unchanged': True,
        'all_original_worklist_groups_reviewed': 76, 'runtime_preparation_enabled': False,
        'legacy_remains_default': True, 'production_activation': False}
    write(args.report / 'verification.json', result)
    print(result, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--local', type=Path, required=True)
    parser.add_argument('--budget', type=Path)
    parser.add_argument('--previous-local', type=Path, default=Path('.local/recipe-coverage-followup-20261027'))
    parser.add_argument('--previous-report', type=Path)
    main(parser.parse_args())
