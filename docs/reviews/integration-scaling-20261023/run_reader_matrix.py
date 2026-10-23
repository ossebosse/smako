"""Validate the separate reader image with its native unchanged planner/library.

No search code is overlaid. Old menus get an additional measured, independent
qualification/accepts/basket/audit replay through the native _create callbacks.
That replay never replaces or changes the native planner's delivered result.
"""
import argparse
import gc
import hashlib
import importlib.util
import json
import socket
import sys
import time
import types
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.errors import IncompleteBasketError
from app.services.meal_prepared_artifacts import method_signature
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import current_recipes, library_version


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def slots_record(slots):
    return [{'slot': s.id, 'recipe': digest(s.recipe.model_dump(mode='json')),
             'recipe_name': s.recipe.name} for s in slots]


# The common report formatter imports only this serializer from the new module.
# The native old planner does not import/use it. No runtime search is replaced.
serializer = types.ModuleType('app.services.library_publications')
serializer.slots_record = slots_record
sys.modules['app.services.library_publications'] = serializer
spec = importlib.util.spec_from_file_location(
    'matrix_report_helpers', Path(__file__).parents[3] / 'backend/scripts/planner_acceptance_matrix.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
CASES = ('standard', 'protein40', 'all-macros', 'vegan', 'distribution',
         'organic-share', 'breakfast-snack-weight')


def read_inputs(directory):
    manifest = json.loads((directory / 'matrix-inputs.json').read_bytes())
    for name, sha in manifest['sha256'].items():
        assert Path(name).name == name
        with (directory / name).open('rb') as source:
            assert hashlib.file_digest(source, 'sha256').hexdigest() == sha
    return manifest


def replay_old_menu(subject, record):
    def replay(pools, **kwargs):
        if pools and isinstance(pools[0], tuple):
            options = [[] for _ in pools[0][1]]
            for _, groups in pools:
                for i, group in enumerate(groups):
                    options[i].extend(group)
        else:
            options = pools
        chosen = []
        assert len(options) == len(record)
        for group, row in zip(options, record, strict=True):
            found = next((s for s in group if s.id == row['slot']
                          and digest(s.recipe.model_dump(mode='json')) == row['recipe']), None)
            if found is None:
                raise ValueError('Old exact recipe is absent from the newly qualified pool: ' + row['recipe_name'])
            chosen.append(found)
        if not kwargs['accepts'](chosen, final=True):
            raise ValueError('Old menu fails the current full-pool weekly constraints')
        subject._defer_search_audit = False
        return chosen, kwargs['evaluate'](chosen, final=True)

    optimizer = subject.service.menu_optimizer
    original_slots, original_library = optimizer.optimize_slots, optimizer.optimize_library_slots
    optimizer.optimize_slots = replay
    optimizer.optimize_library_slots = replay
    try:
        return subject._create()
    finally:
        optimizer.optimize_slots, optimizer.optimize_library_slots = original_slots, original_library


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', required=True, type=Path)
    p.add_argument('--city', required=True)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--image-id', required=True)
    p.add_argument('--repeat', type=int, default=3)
    args = p.parse_args()
    args.output.mkdir(exist_ok=True, parents=True)
    manifests = {}
    for arm in ('control', 'enriched'):
        manifests[arm] = read_inputs(args.inputs / ('final-' + arm) / args.city)
    for name in ('combined-prices.json', 'combined-request.json'):
        assert manifests['control']['sha256'][name] == manifests['enriched']['sha256'][name]
    assert manifests['control']['now'] == manifests['enriched']['now']
    control = args.inputs / 'final-control' / args.city
    prepared = PreparedPriceUniverseArtifact.model_validate_json((control / 'combined-prices.json').read_bytes()).restore()
    base = json.loads((control / 'combined-request.json').read_bytes())
    clock = datetime.fromisoformat(manifests['control']['now'])
    settings = Settings(complete_recipes_enabled=True, price_provider='own')
    report = {'schema': 'smako-native-axfood-reader-v1',
              'image': args.image_id, 'method_signature': method_signature(), 'library_version': library_version(),
              'native_recipe_count': len(current_recipes()), 'city': args.city,
              'inputs': manifests, 'repeat': args.repeat, 'records': [],
              'old_menu_replay_changes_native_result': False}
    old_menus = {}
    for arm in ('control', 'enriched'):
        raw = json.loads((args.inputs / ('final-' + arm) / args.city / 'combined-facts.json').read_bytes())
        facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw['facts']})
        assert facts.version == raw['facts_version']
        del raw
        for case in CASES:
            request = helpers.matrix_request(base, case)
            for iteration in range(args.repeat):
                started = time.perf_counter()
                subject = PersonalPlanner(request, settings, prepared,
                    {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts, now=clock)
                row = {'case': case, 'arm': arm, 'iteration': iteration}
                print(json.dumps({'start': row}), flush=True)
                with patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')):
                    try:
                        plan = subject.create()
                        row.update(outcome='PASS', **helpers.quality(plan, request))
                        row['checkout_audit'] = plan.personal.checks['checkout_audit']
                        if arm == 'control' and case not in old_menus:
                            old_menus[case] = slots_record(plan.personal.slots)
                    except (ValueError, IncompleteBasketError) as exc:
                        row.update(outcome='BLOCKED', reason=str(exc), code=getattr(exc, 'code', None),
                                   stage=getattr(exc, 'stage', None))
                    row['native_seconds'] = time.perf_counter() - started
                    if arm == 'enriched' and iteration == 0 and case in old_menus:
                        audit_started = time.perf_counter()
                        audit_subject = PersonalPlanner(request, settings, prepared,
                            {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts, now=clock)
                        try:
                            audited = replay_old_menu(audit_subject, old_menus[case])
                            row['old_menu_reaudit'] = {'status': 'PASS', **helpers.quality(audited, request)}
                            row['old_menu_reaudit']['checkout_audit'] = audited.personal.checks['checkout_audit']
                        except (ValueError, IncompleteBasketError) as exc:
                            row['old_menu_reaudit'] = {'status': 'REJECTED', 'reason': str(exc),
                                'code': getattr(exc, 'code', None), 'stage': getattr(exc, 'stage', None),
                                'qualification_details': audit_subject.diagnostics.details}
                        row['old_menu_reaudit_seconds'] = time.perf_counter() - audit_started
                        del audit_subject
                report['records'].append(row)
                (args.output / (args.city + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2))
                print(json.dumps({k: row[k] for k in ('case', 'arm', 'iteration', 'outcome', 'native_seconds')},
                                 ensure_ascii=False), flush=True)
                del subject
                gc.collect()
        del facts
        gc.collect()


if __name__ == '__main__':
    main()
