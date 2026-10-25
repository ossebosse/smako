"""Frozen native PlanStore history arrivals; no HTTP or private-state rewinds.

Seed workers make a real legacy delivery on 262 recipes and persist it through
PlanStore.create. Arrival workers use the original 5,000-recipe context and
measure current checkout after that identity arrives. A four-meal delivery is
valid for its original request but incomplete for the current five-meal request.
This is distinct from the permanent synthetic checkout-rejection regression.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import http_history_entry as bootstrap

METHOD = '17568fe52f2f4da372b1263979673cb79f74f731fa8ada05acc6fe8058e0d6b6'
ENTRY = Path(__file__)


@contextmanager
def observe_native_calls():
    from app.services.basket_auditor import BasketAuditor
    from app.services.menu_optimizer import MenuOptimizer

    codes = {MenuOptimizer.optimize_library_slots.__code__:'optimizer',
             BasketAuditor.audit.__code__:'audit'}
    counts = {'optimizer':0,'audit':0}
    previous = sys.getprofile()
    assert previous is None, 'Do not combine this diagnostic with another profiler'
    def observed(frame,event,_value):
        if event == 'call' and frame.f_code in codes:
            counts[codes[frame.f_code]] += 1
    try:
        sys.setprofile(observed)
        yield counts
    finally:
        sys.setprofile(previous)


def seed_request(current, kind):
    from app.models import PlanRequest

    body = current.model_dump(mode='json')
    assert len(body['personal']['meals']) == 1
    meal = body['personal']['meals'][0]
    assert meal['count'] == body['recipes'] == 5
    if kind == 'incomplete':
        assert meal['distribution']['vegetarian'] == 2
        meal['count'] = body['recipes'] = 4
        meal['distribution']['vegetarian'] = 1
    return PlanRequest.model_validate(body)


def original_context(store,expected_revision):
    from app.services.personal_store import PersonalStore

    with store._connect() as connection:
        rows = connection.execute(
            'SELECT plan_id,owner_actor_hash FROM consumer_plan_revisions').fetchall()
    owners = {row['owner_actor_hash'] for row in rows}
    assert len(owners) == 1 and None not in owners, 'Expected one synthetic owner'
    owner = owners.pop()
    originals = []
    for row in rows:
        saved = store.get_owned(row['plan_id'],owner_actor_hash=owner)
        if saved.request.personal.pantry_revision == 0:
            originals.append(saved)
    assert len(originals) == 1, 'Expected the one original HTTP delivery'
    state = PersonalStore(store).read(owner)
    assert state['revision'] == expected_revision, 'Use the actual current private revision'
    request = originals[0].request.model_copy(deep=True)
    request.personal.pantry_revision = state['revision']
    return owner,request,state


def probe(settings, prepared, facts, clock, output, args):
    from app.services.library_publications import slots_record
    from app.services.meal_prepared_artifacts import method_signature
    from app.services.personal_planner import PersonalPlanner
    from app.services.plan_store import PlanStore
    from app.services.planner_artifacts import OwnedPlannerArtifacts

    from backend.scripts.planner_acceptance_matrix import digest, quality

    store = PlanStore(settings.plan_store_path)
    before = bootstrap.history(store.path)
    expected_rows = 1 if args.stage == 'seed' else 2
    assert before['saved_revisions'] == expected_rows
    assert before['private_sha256'] == args.expected_private_sha256
    assert before['history_sha256'] == args.expected_history_sha256
    owner,current,state = original_context(store,args.expected_revision)
    protocol = json.loads((output/'protocol.json').read_bytes())
    assert protocol['method_signature'] == method_signature() == METHOD
    protocol.update(probe_entry_sha256=hashlib.sha256(ENTRY.read_bytes()).hexdigest(),
        bootstrap_entry_sha256=hashlib.sha256(Path(bootstrap.__file__).read_bytes()).hexdigest(),
        arrival_kind=args.arrival_kind,cache_path=args.cache_path,
        scope='Native PlanStore identity arrival in an isolated copy; distinct from HTTP Save',
        cache_mode='new process, warm copied public disk and qualified owner; OS disk cache uncontrolled',
        instrumentation=('Uninstrumented native legacy setup' if args.stage == 'seed' else
            'CPython call-profile hook counts native optimizer/auditor calls; timing includes its overhead; native methods unchanged'))
    bootstrap.write(output/'protocol.json',protocol)
    report = {'stage':args.stage,'arrival_kind':args.arrival_kind,'cache_path':args.cache_path,
        'method_signature':METHOD,'before':before,'actual_pantry_revision':state['revision'],
        'status':'IN_PROGRESS'}
    if args.stage == 'seed':
        request = seed_request(current,args.arrival_kind)
        legacy = replace(settings,library_search_policy='legacy')
        started = time.perf_counter()
        plan = PersonalPlanner(request,legacy,prepared,state,facts=facts,now=clock).create()
        report['native_plan_seconds'] = time.perf_counter()-started
        report['quality'] = quality(plan,request)
        report['instrumented'] = False
        assert len(plan.personal.slots) == (5 if args.arrival_kind == 'valid' else 4)
        with store._connect() as connection:
            original_row = connection.execute(
                'SELECT plan_id FROM consumer_plan_revisions').fetchone()
        original = store.get_owned(original_row['plan_id'],owner_actor_hash=owner)
        assert digest(slots_record(plan.personal.slots)) != digest(slots_record(original.plan.personal.slots))
        assert not plan.personal.allocations, 'This arrival mode requires the unchanged empty pantry'
        started = time.perf_counter()
        store.create(request,plan,owner_actor_hash=owner)
        report['native_store_create_seconds'] = time.perf_counter()-started
        report['after'] = bootstrap.history(store.path)
        _,_,after_state = original_context(store,args.expected_revision+1)
        report['private_revision_after'] = after_state['revision']
        passed = (report['after']['saved_revisions'] == 2
                  and after_state['id'] == state['id']
                  and after_state['items'] == state['items'] == []
                  and after_state['profile'] == state['profile'])
        report['status'] = 'NATIVE_262_DELIVERY_SAVED' if passed else 'HISTORY_SEED_FAILED'
        bootstrap.write(output/'history-seed.json',report)
        assert passed, 'Native history write changed effective pantry/profile inputs'
        return

    artifacts = OwnedPlannerArtifacts(store,owner)
    calls = {'optimizer':0,'audit':0}
    started = time.perf_counter()
    try:
        with observe_native_calls() as calls:
            plan = PersonalPlanner(current,settings,prepared,state,facts=facts,now=clock,artifacts=artifacts).create()
    except Exception as error:
        report.update(status='HISTORY_ARRIVAL_RAISED',error_type=type(error).__name__,
            plan_seconds=time.perf_counter()-started,native_optimizer_calls=calls['optimizer'],
            native_audit_calls=calls['audit'],instrumented=True,
            after=bootstrap.history(store.path))
        bootstrap.write(output/'history-arrival.json',report)
        raise
    report.update(plan_seconds=time.perf_counter()-started,quality=quality(plan,current),
        native_optimizer_calls=calls['optimizer'],native_audit_calls=calls['audit'],instrumented=True,
        after=bootstrap.history(store.path))
    reference = report['quality']['verified_reference']
    unchanged = all(report['after'][key] == before[key] for key in
                    ('saved_revisions','history_sha256','private_sha256'))
    passed = (unchanged and calls['optimizer'] == 0 and calls['audit'] > 0
              and reference['replayed_publications'] == 0
              and reference['context'] == args.expected_context
              and Decimal(str(report['quality']['paid'])) <= Decimal(args.baseline_paid))
    report['status'] = 'HISTORY_ARRIVAL_PASSED' if passed else 'HISTORY_ARRIVAL_FAILED'
    bootstrap.write(output/'history-arrival.json',report)
    assert passed, 'History arrival repeated search, changed authoritative state, or lost the valid price'


def write_final(output,stage,complete):
    from app.services.meal_prepared_artifacts import method_signature

    actual_method = method_signature()
    report = output/f'history-{stage}.json'
    report_sha = hashlib.sha256(report.read_bytes()).hexdigest() if report.exists() else None
    entry_sha = hashlib.sha256(ENTRY.read_bytes()).hexdigest()
    measured = bootstrap.memory()
    bootstrap.write(output/'final-resource.json',{
        'measurement_complete':complete and actual_method == METHOD and report_sha is not None,
        'scope':'After native calls, report serialization and report/source hashing; before tiny footer',
        'method_signature':actual_method,'target_method_signature':METHOD,
        'target_enforced_for_current_runtime':actual_method == METHOD,
        'memory':measured,'memory_target_passed':measured['peak'] <= bootstrap.LIMIT,
        'entry_sha256':entry_sha,'report_sha256':report_sha})
    if measured['peak'] > bootstrap.LIMIT or measured['swap.current'] != 0:
        raise RuntimeError('History arrival exceeded the unchanged memory/swap gate')
    if actual_method != METHOD:
        raise RuntimeError('History arrival source method differs from the frozen runtime')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','output','store'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--stage',choices=('seed','arrival'),required=True)
    parser.add_argument('--arrival-kind',choices=('valid','incomplete'),required=True)
    parser.add_argument('--cache-path',choices=('prepared','certificate'),required=True)
    parser.add_argument('--expected-private-sha256',required=True)
    parser.add_argument('--expected-history-sha256',required=True)
    parser.add_argument('--expected-revision',type=int,required=True)
    parser.add_argument('--expected-context',required=True)
    parser.add_argument('--baseline-paid',required=True)
    args = parser.parse_args()
    args.mode = args.stage
    args.output.mkdir(parents=True,exist_ok=True)
    bootstrap.direct_probe = lambda settings,prepared,facts,clock,output,mode: probe(
        settings,prepared,facts,clock,output,args)
    complete = False
    try:
        bootstrap.run(args)
        complete = True
    finally:
        write_final(args.output,args.stage,complete)


if __name__ == '__main__':
    main()
