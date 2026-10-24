"""Frozen ASGI transport and nonempty history probes, using the ordinary planner.

Synthetic local member credentials stay in memory. Only aggregate evidence is
written: no cookies, owner capabilities, recovery codes or saved plan IDs.
The HTTP case is one diagnostic observation, not a load/latency qualification.
Later direct calls use the actual current pantry revision without saving again.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings

EXPECTED = '1c0ad484edda7e36bf026b83a6e4f171dddf9c8d4a2b3d5359d95fa90bc227b7'
LIMIT = 2684354560


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')


def history(path):
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as connection:
        # Hash authoritative history/private state, not mutable derived caches.
        rows = connection.execute('SELECT * FROM consumer_plan_revisions ORDER BY plan_id,revision').fetchall()
        private = connection.execute('SELECT * FROM personal_private_state ORDER BY id').fetchall()
        counts = dict(connection.execute('SELECT kind,COUNT(*) FROM planner_owned_artifacts GROUP BY kind'))
    return {'saved_revisions':len(rows), 'history_sha256':hashlib.sha256(json.dumps(rows).encode()).hexdigest(),
            'private_sha256':hashlib.sha256(json.dumps(private).encode()).hexdigest(), 'artifacts':counts}


def memory():
    return {name:int(Path('/sys/fs/cgroup/memory.'+name).read_text()) for name in ('current','peak','swap.current')}


def validate(plan, request):
    from backend.scripts.planner_acceptance_matrix import quality
    result = quality(plan,request)
    assert result['audit_passed'] and result['paid'] == 988.32
    assert result['semantic_sha256'] == EXPECTED
    return result


def http_probe(settings, prepared, facts, clock, request, output):
    # Bind the synthetic configuration before importing the app, auth or middleware.
    from app import config
    config.get_settings = lambda:settings
    # The probe uses local member accounts and no external identity/database.
    for key in ('SMAKO_OIDC_ISSUER_URL','SMAKO_OIDC_CLIENT_ID','SMAKO_OIDC_CLIENT_SECRET'):
        os.environ.pop(key,None)
    os.environ['GROCERY_DATABASE_URL'] = 'sqlite+pysqlite:///:memory:'
    from app import main
    from app.api import plan as api
    from app.models import SavedPlan
    from app.services import price_universe_runtime
    from app.services.performance_trace import activate_performance_trace
    from app.services.personal_planner import PersonalPlanner
    from app.services.plan_jobs import PlanJobs
    from app.services.plan_store import PlanStore
    from app.services.planner_admission import PlannerAdmissionController
    from fastapi.testclient import TestClient

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.astimezone(tz) if tz else clock.replace(tzinfo=None)

    @asynccontextmanager
    async def lifespan(app):
        app.state.beta_settings = settings
        app.state.plan_store = PlanStore(settings.plan_store_path)
        app.state.planner_admission = PlannerAdmissionController(
            max_concurrent=settings.planner_max_concurrent_requests,
            max_queued=settings.planner_max_queued_requests)
        app.state.plan_jobs = PlanJobs(max_pending=settings.planner_max_concurrent_requests+settings.planner_max_queued_requests)
        app.state.community_session_factory = None
        try:
            yield
        finally:
            await app.state.plan_jobs.close()

    original_init = PersonalPlanner.__init__
    def frozen_init(self, *args, **kwargs):
        kwargs.setdefault('facts',facts)
        kwargs.setdefault('now',clock)
        original_init(self,*args,**kwargs)

    main.app.router.lifespan_context = lifespan
    report = {'status':'HTTP_DIAGNOSTIC_IN_PROGRESS','samples':1,
              'scope':'In-process ASGI routes/auth/middleware/admission/jobs/save/read; no browser/network/metric persistence',
              'startup_prewarm':'disabled in isolated lifespan; catalogue/facts loaded before HTTP',
              'progress_samples':[], 'job_traces':[],
              'poll_interval_seconds':1,
              'wait_scope':'Request start / accepted response until first observed saved-result response; includes polling delay',
              'instrumentation':'Existing request-local performance trace; elapsed HTTP includes its overhead'}
    original_create = api._create_saved_plan
    trace_sequence = 0

    async def traced_create(*args, **kwargs):
        nonlocal trace_sequence
        trace_sequence += 1
        sequence, outcome = trace_sequence, 'returned'
        with activate_performance_trace() as trace:
            try:
                return await original_create(*args,**kwargs)
            except BaseException as error:
                outcome = type(error).__name__
                raise
            finally:
                report['job_traces'].append({'sequence':sequence,'outcome':outcome,
                                             'trace':asdict(trace.snapshot())})

    with (patch.object(PersonalPlanner,'__init__',frozen_init),
          patch.object(api,'_create_saved_plan',traced_create),
          patch.object(api,'datetime',FrozenDateTime),
          patch.object(price_universe_runtime,'datetime',FrozenDateTime),
          patch.object(api,'current_pricing_date',lambda:clock.date()),
          TestClient(main.app,raise_server_exceptions=False) as client):
        # Real local registration; no external identity provider or email delivery.
        response = client.post('/api/account/register',json={
            'email':secrets.token_hex(12)+'@example.invalid','password':secrets.token_urlsafe(32)})
        assert response.status_code == 201, ('registration',response.status_code)
        del response  # Contains a recovery capability; never serialize it.

        def stats():
            return asdict(client.portal.call(main.app.state.planner_admission.stats))

        def post(body):
            started = time.perf_counter()
            response = client.post('/api/plans',headers={'Prefer':'respond-async'},
                                   json=body.model_dump(mode='json',exclude_unset=True))
            assert response.status_code == 202, ('plan start',response.status_code)
            return response.json()['status_url'],time.perf_counter()-started

        def wait_for(predicate, timeout):
            deadline = time.monotonic()+timeout
            while time.monotonic() < deadline:
                value = predicate()
                if value:
                    return value
                time.sleep(.1)
            raise TimeoutError('Bounded HTTP diagnostic did not reach the required state')

        started = time.perf_counter()
        url,report['post_accept_seconds'] = post(request)
        wait_for(lambda:stats()['active']==1,10)
        from backend.scripts.planner_acceptance_matrix import matrix_request
        other = matrix_request(json.loads((output/'base-request.json').read_bytes()),'standard')
        queued,report['queued_post_accept_seconds'] = post(other)
        queue_accepted_at = time.perf_counter()
        report['queued_snapshot'] = wait_for(lambda:(s if (s:=stats())['queued']==1 else None),10)
        assert report['queued_snapshot']['active'] == 1
        cancel_started = time.perf_counter()
        report['queued_accepted_until_cancel_requested_seconds'] = cancel_started-queue_accepted_at
        assert client.delete(queued).status_code == 202
        wait_for(lambda:stats()['queued']==0,10)
        assert client.get(queued).status_code == 404
        report['queued_cancel_until_released_seconds'] = time.perf_counter()-cancel_started
        previous = None
        deadline = time.monotonic()+1800
        while time.monotonic() < deadline:
            response = client.get(url)
            elapsed = time.perf_counter()-started
            if response.status_code != 202:
                break
            status = response.json()
            value = status['stage'],status.get('progress')
            if value != previous:
                report['progress_samples'].append({'elapsed_seconds':elapsed,'stage':value[0],'progress':value[1]})
                write(output/'http-history.json',report)
                previous = value
            time.sleep(1)
        assert response.status_code == 201, ('HTTP final',response.status_code)
        saved = SavedPlan.model_validate(response.json())
        report['start_request_until_saved_response_seconds'] = time.perf_counter()-started
        report['accepted_until_saved_response_seconds'] = (
            report['start_request_until_saved_response_seconds']-report['post_accept_seconds'])
        report['quality'] = validate(saved.plan,saved.request)
        reread = client.get('/api/plans/'+saved.plan_id)
        assert reread.status_code == 200
        assert SavedPlan.model_validate(reread.json()).plan == saved.plan
        assert client.delete(url).status_code == 409
        cookies = dict(client.cookies)
        client.cookies.clear()
        try:
            report['foreign_job_read_status'] = client.get(url).status_code
            assert report['foreign_job_read_status'] == 404
        finally:
            client.cookies.clear()
            client.cookies.update(cookies)
            del cookies
        before = history(settings.plan_store_path)
        assert before['saved_revisions'] == 1
        # Start actual work for the next private revision, then stop it at a
        # real bounded unit. No injected fake planner/sleep replaces the work.
        active,report['active_cancel_post_accept_seconds'] = post(request)
        def running_stage():
            response = client.get(active)
            assert response.status_code == 202
            stage = response.json()['stage']
            return stage if stage != 'queued' and stats()['active']==1 else None
        report['active_cancel_stage'] = wait_for(running_stage,20)
        cancel_started = time.perf_counter()
        assert client.delete(active).status_code == 202
        wait_for(lambda:stats()['active']==0,30)
        assert client.get(active).status_code == 404
        report['active_cancel_until_worker_released_seconds'] = time.perf_counter()-cancel_started
        after = history(settings.plan_store_path)
        assert all(after[k]==before[k] for k in ('saved_revisions','history_sha256','private_sha256'))
        report['history_after_success_and_active_cancel'] = after
        report['admission'] = stats()
        assert report['admission']['peak_active'] == 1 and report['admission']['peak_queued'] >= 1
        # Existing admission timing covers the actual semaphore wait, including
        # a cancelled queued job; it is separate from POST and saved-result time.
        assert len(report['job_traces']) == 3
        assert all('planner_queue_wait' in row['trace']['span_statistics'] for row in report['job_traces'])
        report['status'] = 'HTTP_DIAGNOSTIC_PASSED_NOT_LATENCY_QUALIFICATION'
    write(output/'http-history.json',report)


def direct_probe(settings, prepared, facts, clock, output, mode):
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_store import PersonalStore
    from app.services.plan_store import PlanStore
    from app.services.planner_artifacts import OwnedPlannerArtifacts
    store = PlanStore(settings.plan_store_path)
    before = history(store.path)
    assert before['saved_revisions'] == 1
    with store._connect() as connection:
        row = connection.execute('SELECT plan_id,owner_actor_hash FROM consumer_plan_revisions').fetchone()
    saved = store.get_owned(row['plan_id'],owner_actor_hash=row['owner_actor_hash'])
    state = PersonalStore(store).read(row['owner_actor_hash'])
    assert state['revision'] == 1
    request = saved.request.model_copy(deep=True)
    request.personal.pantry_revision = state['revision']
    artifacts = OwnedPlannerArtifacts(store,row['owner_actor_hash'])
    started = time.perf_counter()
    plan = PersonalPlanner(request,settings,prepared,state,facts=facts,now=clock,artifacts=artifacts).create()
    result = {'mode':mode,'plan_seconds':time.perf_counter()-started,'quality':validate(plan,request),
              'actual_pantry_revision':state['revision'],'before':before,'after':history(store.path)}
    assert all(result['after'][k]==before[k] for k in ('saved_revisions','history_sha256','private_sha256'))
    if mode == 'recover':
        reference = result['quality']['verified_reference']
        assert reference['loaded_publications'] == 11 and reference['replayed_publications'] == 0
    write(output/f'history-{mode}.json',result)


def run(args):
    startup_started = time.perf_counter()
    os.environ['RECIPE_PREPARATION_CACHE_ROOT'] = str(args.output/'prepared')
    args.output.mkdir(parents=True,exist_ok=True)
    from app.services import reference_library
    reference_library.PIN = Path('/review/backend/app/data/recipes/reference-library-262.json')
    manifest = json.loads((args.inputs/'matrix-inputs.json').read_bytes())
    for name,digest in manifest['sha256'].items():
        assert hashlib.sha256((args.inputs/name).read_bytes()).hexdigest() == digest
    clock = datetime.fromisoformat(manifest['now'])
    settings = Settings(app_env='test',complete_recipes_enabled=True,price_provider='own',price_universe_city='Malmö',
        library_search_policy='smako-verified-reference-v1',library_merge_generations=False,
        plan_store_path=args.store,secret_key=secrets.token_hex(32),source_facts_prewarm_enabled=False)
    from app.services.personal_policy import ProductFacts
    from app.services.personal_source_facts import FactsCollection
    from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES

    from backend.scripts.planner_acceptance_matrix import matrix_request
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.load_file_and_activate(args.inputs/'combined-prices.json')
    raw = json.loads((args.inputs/'combined-facts.json').read_bytes())
    facts = FactsCollection({tuple(k):ProductFacts(**v) for k,v in raw['facts']},source_manifests=raw.get('source_manifests',()))
    assert facts.version == raw['facts_version']
    del raw
    from app.services.meal_prepared_artifacts import method_signature
    from app.services.recipe_library import library_version
    method = method_signature()
    assert method == '17568fe52f2f4da372b1263979673cb79f74f731fa8ada05acc6fe8058e0d6b6'
    write(args.output/'protocol.json',{'mode':args.mode,'inputs':manifest,'method_signature':method,
        'library_version':library_version(),'source_commit':'eeda184926f02e73ab76e71e50c740e9dcb01b02',
        'startup_seconds':time.perf_counter()-startup_started,
        'startup_scope':'Input hashes, catalogue validation/index build, frozen facts and method/library identity; before HTTP or direct plan timing'})
    base = json.loads((args.inputs/'combined-request.json').read_bytes())
    # Frozen public request, containing no credentials/private capabilities.
    write(args.output/'base-request.json',base)
    with patch.object(socket.socket,'connect',side_effect=AssertionError('network forbidden')):
        if args.mode == 'http':
            http_probe(settings,prepared,facts,clock,matrix_request(base,'distribution'),args.output)
        else:
            direct_probe(settings,prepared,facts,clock,args.output,args.mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--store',type=Path,required=True)
    parser.add_argument('--mode',choices=('http','prepare','recover'),required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    try:
        run(args)
    finally:
        measured = memory()
        write(args.output/'final-resource.json',{'memory':measured,'memory_target_passed':measured['peak']<=LIMIT,
              'entry_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
        if measured['peak'] > LIMIT:
            raise RuntimeError('HTTP/history diagnostic exceeded the 2.5 GiB target')


if __name__ == '__main__':
    main()
