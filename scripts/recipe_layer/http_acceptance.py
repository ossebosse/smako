"""Ordinary HTTP acceptance against the isolated frozen-input application.

No synthetic products, locks, candidate edits, price clocks or source writes.
Each case gets a fresh real cookie session. The launcher owns the frozen clock.
Output is private evidence and must stay outside Git. A deadline means the
client stopped waiting; it does not prove infeasibility or cancel backend work.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import re
import shlex
import time
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
PROFILE_SOURCE = ROOT / 'docs/releases/public-menu-followup-20261002/personal-regressions.json'


class AcceptanceFailure(AssertionError):
    def __init__(self, message, evidence):
        super().__init__(message)
        self.evidence = evidence


def complete_request(*, servings=2, cuisines=None, mode='balanced', purchase='estimated'):
    return {'postal_code': '22350', 'recipes': 5, 'servings': servings, 'max_stores': 2,
        'memberships': [], 'diversity_mode': mode, 'purchase_planning_mode': purchase,
        'allow_nutrition_estimates': True,
        'recipe_preferences': {'mode': 'complete', 'cuisines': ['greek'] if cuisines is None else cuisines,
            'min_ingredients': 10, 'max_ingredients': 15, 'adaptation': 'approved'},
        'personal': {'allow_nutrition_estimates': True, 'meals': [{'meal_type': 'dinner', 'count': 5,
            'servings': servings, 'limits': {'min_protein_g': 0, 'min_carbs_g': 0, 'min_fat_g': 0, 'max_kcal': 4000}}]}}


def cases():
    result = {
        'greek-two': complete_request(), 'greek-four': complete_request(servings=4),
        'mixed-protein40': complete_request(cuisines=['greek', 'mexican']),
        'greek-exact': complete_request(purchase='exact'),
        'greek-cheapest': complete_request(mode='cheapest'),
        'greek-varied': complete_request(mode='varied'),
        'unrestricted-varied': complete_request(cuisines=[], mode='varied'),
        'greek-pantry': complete_request(), 'indian-vegetarian': complete_request(cuisines=['indian']),
        'mixed-four': complete_request(servings=4, cuisines=['greek', 'mexican']),
        'mixed-four-time-negative': complete_request(servings=4, cuisines=['greek', 'mexican']),
        'mixed-vegetarian': complete_request(cuisines=['greek', 'italian', 'indian']),
        'custom-ingredients': complete_request(cuisines=[]),
        'products-only': complete_request(), 'onion-exclusion': complete_request(cuisines=[]),
        'choices-time-negative': complete_request(), 'fish-conflict-negative': complete_request(),
        'allergy-negative': complete_request(cuisines=['greek']),
        'channel-negative': complete_request(),
    }
    result['mixed-protein40']['recipe_preferences'].update(min_protein_g=40, max_minutes=40)
    result['mixed-four']['recipe_preferences']['max_minutes'] = 45
    result['mixed-four-time-negative']['recipe_preferences']['max_minutes'] = 40
    result['custom-ingredients']['recipe_preferences'].update(min_ingredients=12, max_ingredients=13, max_minutes=50)
    result['products-only']['recipe_preferences']['adaptation'] = 'products'
    result['onion-exclusion']['recipe_preferences']['allow_fish'] = False
    result['onion-exclusion']['personal']['profile'] = {'exclusions': ['lök']}
    for name in ('indian-vegetarian', 'mixed-vegetarian'):
        result[name]['diet_preference'] = 'vegetarian'
        result[name]['personal']['meals'][0]['diet'] = 'vegetarian'
    result['choices-time-negative']['recipe_preferences']['max_minutes'] = 10
    result['fish-conflict-negative']['recipe_preferences']['allow_fish'] = False
    result['fish-conflict-negative']['personal']['meals'][0]['distribution'] = {'fish': 1}
    result['allergy-negative']['personal']['profile'] = {'allergies': ['mjölk']}
    result['channel-negative']['allowed_store_ids'] = ['context:unknown:outside-frozen-universe']
    # Preserve all historical profile food requirements and opt-ins. The sole
    # mutable revision is rebound to the fresh private test workspace below.
    for item in json.loads(PROFILE_SOURCE.read_bytes())['cases']:
        result['legacy-1520-' + item['case']] = copy.deepcopy(item['request'])
    # Original public baseline choices, with no new fields or personal model.
    # Do not send serialized null diversity overrides as explicit user choices.
    result['legacy-public'] = {'postal_code': '22350', 'recipes': 5, 'servings': 2,
        'max_stores': 3, 'diversity_mode': 'balanced', 'purchase_planning_mode': 'exact',
        'diet_preference': 'mixed',
        'memberships': {k: True for k in ('coop', 'ica', 'hemkop', 'willys', 'lidl', 'citygross')}}
    return result


def critical_saved(saved):
    plan = saved['plan']
    return {'request': saved['request'], 'recipes': plan['recipes'], 'basket': plan['optimized_basket'],
            'personal': plan.get('personal'), 'revision': saved['revision']}


def verify_saved(saved, submitted):
    plan = saved['plan']
    personal = plan.get('personal')
    if personal is None:
        assert not submitted.get('recipe_preferences') and not submitted.get('personal')
        assert len(plan['recipes']) == submitted['recipes']
        assert all(r['servings'] == submitted['servings'] for r in plan['recipes'])
        assert len(plan['optimized_basket']['stores']) <= submitted['max_stores']
        assert plan['quality']['basket_audit']['status'] == 'PASS'
        for pair in plan['quality']['diversity']['pairs']:
            assert 'flavor' not in pair['components']  # Absent legacy metadata is not zero.
        return
    meals = {m['meal_type']: m for m in saved['request']['personal']['meals']}
    assert personal['checks']['checkout_audit']['passed'], 'Final checkout audit did not pass'
    assert len(plan['optimized_basket']['stores']) <= submitted['max_stores']
    assert len(personal['slots']) == sum(m['count'] for m in meals.values())
    assert sum(s['recipe']['servings'] for s in personal['slots'] if s.get('recipe')) == sum(m['count'] * m['servings'] for m in meals.values())
    slots = {s['id']: s for s in personal['slots']}
    for row in personal['checks']['nutrition']:
        meal = meals[slots[row['slot_id']]['meal_type']]
        for limit, threshold in meal['limits'].items():
            if threshold is None:
                continue
            value = row['values'][limit.removeprefix('min_').removeprefix('max_')]
            assert value >= threshold if limit.startswith('min_') else value <= threshold
    prefs = submitted.get('recipe_preferences')
    if prefs:
        assert saved['request']['recipe_preferences'] == {**saved['request']['recipe_preferences'], **prefs}
        dinners = [s['recipe'] for s in personal['slots'] if s['meal_type'] == 'dinner']
        assert len({r['design']['base_id'] for r in dinners}) == len(dinners)
        for recipe in dinners:
            design = recipe['design']
            assert design['version'] and design['content_sha256']
            assert not prefs['cuisines'] or set(design['cuisines']) & set(prefs['cuisines'])
            count = len({(i.get('canonical_name') or i['name'], i.get('form')) for i in recipe['ingredients']
                         if (i.get('canonical_name') or i['name']) not in {'salt', 'peppar', 'svartpeppar', 'vatten'}})
            assert prefs['min_ingredients'] <= count <= prefs['max_ingredients']
            assert not prefs.get('max_minutes') or design['estimated_minutes'] <= prefs['max_minutes']
            if prefs.get('min_protein_g') is not None:
                assert meals['dinner']['limits']['min_protein_g'] >= prefs['min_protein_g']


class Session:
    def __init__(self, base):
        self.client = httpx.AsyncClient(base_url=base, headers={'Origin': base, 'Referer': base + '/'}, timeout=20)
        self.http = []

    async def request(self, method, path, **kwargs):
        before = time.perf_counter()
        response = await self.client.request(method, path, **kwargs)
        self.http.append({'method': method, 'path': path, 'status': response.status_code,
            'seconds': time.perf_counter()-before, 'request_id': response.headers.get('x-request-id'),
            'error_code': response.headers.get('x-error-code')})
        return response

    async def bootstrap(self):
        response = await self.request('GET', '/api/personal/state')
        response.raise_for_status()
        return response.json()


async def submit(session, payload, *, deadline, stranger=None, mutation_path=None):
    start = time.perf_counter()
    path = mutation_path or '/api/plans'
    response = await session.request('POST', path, json=payload, headers={'Prefer': 'respond-async'})
    stages, duplicate, denied = [], None, None
    if response.status_code == 202:
        location = response.json()['status_url']
        assert location.startswith('/api/plan-jobs/')
        repeated = await session.request('POST', path, json=payload, headers={'Prefer': 'respond-async'})
        duplicate = repeated.status_code == 202 and repeated.json().get('status_url') == location
        assert duplicate, 'An identical pending submission did not reuse its job'
        if stranger:
            other = await stranger.request('GET', location)
            denied = other.status_code == 404
            assert denied, 'Job leaked across private sessions'
        while response.status_code == 202:
            stages.append({'elapsed': time.perf_counter()-start, 'stage': response.json().get('stage')})
            if time.perf_counter()-start > deadline:
                return {'status': 'client_deadline', 'seconds': time.perf_counter()-start,
                        'pending_status_url': location, 'stages': stages, 'duplicate_reused': duplicate}
            await asyncio.sleep(2)
            response = await session.request('GET', location)
    return {'status': 'complete' if response.status_code in {200, 201} else 'stopped',
        'http_status': response.status_code, 'seconds': time.perf_counter()-start,
        'error_code': response.headers.get('x-error-code'), 'response': response.json(),
        'stages': stages, 'duplicate_reused': duplicate, 'other_owner_job_denied': denied}


async def execute_case(name, payload, args):
    session, stranger = Session(args.base), Session(args.base)
    try:
        state = await session.bootstrap()
        await stranger.bootstrap()
        payload = copy.deepcopy(payload)
        if name == 'greek-pantry':
            stock = {'id': 'acceptance-entered-potato', 'name': 'potatis', 'quantity': 500, 'unit': 'g',
                     'form': 'raw_edible', 'nutrition_reference': 'slv:4457:raw'}
            written = await session.request('PUT', '/api/personal/pantry', json={'revision': state['revision'], 'items': [stock]})
            written.raise_for_status()
            state = written.json()
        if payload.get('personal'):
            payload['personal']['pantry_revision'] = state['revision']
        result = await submit(session, payload, deadline=args.deadline, stranger=stranger)
        result.update(case=name, request=payload, private_stock='explicit_test_entry_500g_potato' if name == 'greek-pantry' else 'empty')
        if result['status'] == 'complete':
            assert not name.endswith('-negative'), 'Expected explicit negative constraints to stop'
            saved = result['response']
            verify_saved(saved, payload)
            reread = await session.request('GET', '/api/plans/' + saved['plan_id'])
            assert critical_saved(reread.json()) == critical_saved(saved)
            forbidden = await stranger.request('GET', '/api/plans/' + saved['plan_id'])
            assert forbidden.status_code in {403, 404}
            result.update(reload_identical=True, other_owner_plan_denied=True,
                          total=saved['plan']['optimized_basket']['total'])
            if name == 'greek-pantry':
                allocations = saved['plan']['personal']['allocations']
                used = sum(a['quantity'] for a in allocations if a['item_id'] == 'acceptance-entered-potato')
                assert 0 < used <= 500
                current = (await session.request('GET', '/api/personal/state')).json()
                assert len(current['items']) == 1, 'Planned leftovers were automatically added to stock'
                result['actual_entered_stock_used_g'] = used
        result['http'] = session.http
        return result
    except Exception as exc:
        evidence = locals().get('result', {'case': name, 'request': payload})
        evidence['http'] = session.http
        raise AcceptanceFailure(str(exc), evidence) from exc
    finally:
        await session.client.aclose()
        await stranger.client.aclose()


async def concurrent_three(args):
    sessions = [Session(args.base) for _ in range(3)]
    async with AsyncExitStack() as stack:
        for session in sessions:
            stack.push_async_callback(session.client.aclose)
        await asyncio.gather(*(s.bootstrap() for s in sessions))
        payload = complete_request()
        started = time.perf_counter()
        results = await asyncio.gather(*(submit(s, payload, deadline=args.deadline, stranger=sessions[(i+1) % 3])
                                         for i, s in enumerate(sessions)))
        for result in results:
            if result['status'] == 'complete':
                verify_saved(result['response'], payload)
        saved = [r['response'] for r in results if r['status'] == 'complete']
        assert len({s['plan_id'] for s in saved}) == len(saved), 'Owners shared a saved plan'
        return {'case': 'concurrent-three', 'seconds': time.perf_counter()-started, 'users': results,
                'http': [s.http for s in sessions], 'request': payload, 'session_count': 3,
                'server_warmth': 'not_controlled; report separately from cold process benchmarks'}


async def monotonic_scopes(args):
    session, stranger = Session(args.base), Session(args.base)
    results = []
    try:
        await session.bootstrap()
        await stranger.bootstrap()
        for stores, purchase in ((1, 'exact'), (2, 'exact'), (2, 'estimated')):
            payload = complete_request(mode='cheapest', purchase=purchase)
            payload['max_stores'] = stores
            result = await submit(session, payload, deadline=args.deadline, stranger=stranger)
            result['scope'] = {'stores': stores, 'purchase': purchase}
            if result['status'] == 'complete':
                verify_saved(result['response'], payload)
                result['total'] = result['response']['plan']['optimized_basket']['total']
            results.append(result)
        comparisons = []
        for i, earlier in enumerate(results):
            if earlier['status'] != 'complete':
                continue
            for later in results[i+1:]:
                passed = later['status'] == 'complete' and later['total'] <= earlier['total']
                comparisons.append({'narrower': earlier['scope'], 'wider': later['scope'], 'passed': passed,
                                    'narrower_total': earlier['total'], 'wider_total': later.get('total')})
        return {'case': 'monotonic-scopes', 'results': results, 'comparisons': comparisons,
                'all_comparisons_passed': all(c['passed'] for c in comparisons) if comparisons else None,
                'http': session.http}
    finally:
        await session.client.aclose()
        await stranger.client.aclose()


async def sample_resources(args, stop, samples):
    if not args.container:
        return
    while not stop.is_set():
        command = ['docker', 'stats', '--no-stream', '--format', '{{json .}}', args.container]
        if args.ssh_host:
            command = ['ssh', '-oBatchMode=yes', args.ssh_host, shlex.join(command)]
        started = time.perf_counter()
        process = await asyncio.create_subprocess_exec(*command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            output, _error = await asyncio.wait_for(process.communicate(), timeout=20)
        except TimeoutError:
            process.kill()
            output, _error = await process.communicate()
        samples.append({'elapsed': started-args.started, 'exit_code': process.returncode,
                        'docker_stats': json.loads(output) if process.returncode == 0 and output.strip() else None})
        try:
            await asyncio.wait_for(stop.wait(), 3)
        except TimeoutError:
            pass


async def main(args):
    selected = cases()
    assert args.base == 'http://127.0.0.1:18122', 'Only the isolated acceptance listener is allowed'
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = {'kind': 'ordinary HTTP on isolated authentic price replay', 'started_utc': datetime.now(UTC).isoformat(),
                'base': args.base, 'profile_source_sha256': hashlib.sha256(PROFILE_SOURCE.read_bytes()).hexdigest(),
                'resource_limits_expected': {'cpus': 2, 'memory_gib': 3}, 'resource_samples': [],
                'case': args.case, 'external_price_requests': 0, 'declared_test_stock_is_not_physical_cookery': True}
    async with httpx.AsyncClient() as client:
        response = await client.get(args.base + '/api/ready', timeout=10)
        if response.status_code == 404:
            response = await client.get(args.base + '/ready', timeout=10)
        metadata['readiness'] = response.json()
        response.raise_for_status()
        assert metadata['readiness'].get('build_id', '').startswith('recipe-candidate-'), 'Listener is not the isolated candidate build'
        assert metadata['readiness'].get('features', {}).get('complete_recipes_enabled') is True
        if args.expected_build:
            assert metadata['readiness']['build_id'] == args.expected_build, 'Isolated build changed'
    stop = asyncio.Event()
    sampler = asyncio.create_task(sample_resources(args, stop, metadata['resource_samples']))
    try:
        if args.case == 'concurrent-three':
            metadata['result'] = await concurrent_three(args)
        elif args.case == 'monotonic-scopes':
            metadata['result'] = await monotonic_scopes(args)
        else:
            metadata['result'] = await execute_case(args.case, selected[args.case], args)
    except Exception as exc:
        metadata.update(runner_failure=type(exc).__name__, reason=str(exc))
        if isinstance(exc, AcceptanceFailure):
            metadata['failed_evidence'] = exc.evidence
        raise
    finally:
        stop.set()
        await sampler
        metadata['seconds'] = time.perf_counter()-args.started
        (args.output / (args.case + '.json')).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf8')
    result = metadata['result']
    print(json.dumps({k: result[k] for k in ('case', 'status', 'http_status', 'seconds', 'total') if k in result}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='http://127.0.0.1:18122')
    parser.add_argument('--case', required=True, choices=[*cases(), 'concurrent-three', 'monotonic-scopes'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deadline', type=float, default=1200)
    parser.add_argument('--expected-build', help='Require this exact isolated build ID before any state writes')
    parser.add_argument('--container', help='Optional isolated container for sampled resource usage')
    parser.add_argument('--ssh-host', help='Optional SSH host for read-only docker stats')
    parsed = parser.parse_args()
    assert urlparse(parsed.base).hostname == '127.0.0.1'
    assert not parsed.container or re.fullmatch(r'[a-zA-Z0-9_-]+', parsed.container)
    assert not parsed.ssh_host or re.fullmatch(r'[a-zA-Z0-9_-]+', parsed.ssh_host)
    parsed.started = time.perf_counter()
    asyncio.run(main(parsed))
