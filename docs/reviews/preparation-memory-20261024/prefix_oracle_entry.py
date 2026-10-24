"""Diagnostic oracle: every resumed legacy candidate vs fresh search state.

This intentionally repeats work. Timings and peak memory are diagnostic only;
ordinary uninstrumented runs must qualify latency/resources separately.
"""
from __future__ import annotations

import json
import runpy
from collections import OrderedDict
from pathlib import Path

from app.services import reference_library
from app.services.basket_calculator import money
from app.services.library_publications import slots_record
from app.services.menu_optimizer import MenuOptimizer
from app.services.planner_context import content_digest

reference_library.PIN = Path('/review/backend/app/data/recipes/reference-library-262.json')
original = MenuOptimizer.optimize_library_slots
records = []


def checked(self, cohorts, **kwargs):
    cohorts = tuple(cohorts)
    checkpoint = kwargs.get('_prefix_checkpoint')
    if checkpoint is None:
        return original(self, cohorts, **kwargs)
    initial = OrderedDict(kwargs.get('initial_evaluations') or {})
    actual_trace = kwargs.get('search_trace')
    start = len(actual_trace) if actual_trace is not None else 0
    actual = original(self, cohorts, **kwargs)
    oracle_kwargs = {key:value for key,value in kwargs.items()
                     if key not in {'_prefix_checkpoint','_prefix_context'}}
    oracle_trace = []
    oracle_kwargs.update(initial_evaluations=OrderedDict(initial), search_trace=oracle_trace)
    oracle = original(self, cohorts, **oracle_kwargs)
    left_slots, right_slots = slots_record(actual[0]), slots_record(oracle[0])
    left_basket = actual[1]['basket'].model_dump(mode='json')
    right_basket = oracle[1]['basket'].model_dump(mode='json')
    row = {'generation':cohorts[-1][0], 'cohorts':len(cohorts),
        'actual_slots':left_slots,'oracle_slots':right_slots,
        'actual_paid':str(money(actual[1]['basket'].total)),
        'oracle_paid':str(money(oracle[1]['basket'].total)),
        'actual_basket_sha256':content_digest(left_basket),
        'oracle_basket_sha256':content_digest(right_basket),
        'actual_evaluations':sum(r.get('evaluations_executed',0) for r in (actual_trace or [])[start:]),
        'independent_evaluations':sum(r.get('evaluations_executed',0) for r in oracle_trace),
        'resumed_cohorts':sum(r.get('resumed_cohorts',0) for r in (actual_trace or [])[start:]),
        'slots_equal':left_slots==right_slots,'basket_equal':left_basket==right_basket}
    records.append(row)
    Path('/output/legacy-prefix-oracle.json').write_text(json.dumps({
        'status':'DIAGNOSTIC_IN_PROGRESS_NO_LATENCY_OR_MEMORY_QUALIFICATION',
        'source_commit':'ea4bb08f1ace5a854901a81d08ce7facfa11b383','records':records},indent=2)+'\n')
    if not row['slots_equal'] or not row['basket_equal']:
        Path('/output/oracle-counterexample.json').write_text(json.dumps({
            'row':row,'actual_basket':left_basket,'independent_basket':right_basket},indent=2))
        raise AssertionError('Legacy prefix checkpoint differs from independent current search')
    return actual


MenuOptimizer.optimize_library_slots = checked
runpy.run_path('/review/docs/reviews/integration-scaling-20261023/run_matrix.py',run_name='__main__')
assert len(records)==11 and sum(r['resumed_cohorts'] for r in records)>0
Path('/output/legacy-prefix-oracle.json').write_text(json.dumps({
    'status':'PASS_ALL_11_PUBLICATIONS_NO_LATENCY_OR_MEMORY_QUALIFICATION',
    'source_commit':'ea4bb08f1ace5a854901a81d08ce7facfa11b383','records':records},indent=2)+'\n')
