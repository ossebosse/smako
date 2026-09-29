"""One real HTTP plan in an isolated, network-disabled scheduler-image container.

The actual scheduler environment supplies policy settings. Only private test
storage/auth and prewarming are overridden. No production pointer is written.
Run once per arm; the unchanged request and final plan are saved without guest
identity, cookies or account data. Source observations are never rewritten.
"""
import argparse
import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--arm', choices=['baseline', 'coop'], required=True)
    parser.add_argument('--expected-base-facts-version', required=True)
    parser.add_argument('--reviewed-nutrition', action='store_true')
    parser.add_argument('--normal-source-build', action='store_true')
    args = parser.parse_args()
    started = time.perf_counter()
    wall = datetime.now(UTC)
    private = Path(tempfile.mkdtemp(prefix='source-http-private-'))
    os.environ.update(
        APP_ENV='development', PUBLIC_BASE_URL='http://127.0.0.1:8000',
        SECRET_KEY=secrets.token_hex(32), BETA_ADMIN_TOKEN=secrets.token_hex(32),
        PLAN_STORE_PATH=str(private / 'plans.sqlite3'),
        GROCERY_DATABASE_URL='sqlite+pysqlite:///' + str(private / 'grocery.sqlite'),
        PRICE_UNIVERSE_PREWARM_ENABLED='false',
    )
    import httpx
    import uvicorn
    from app import main as application
    from app.config import get_settings
    from app.models.plan import PlanResponse
    from app.services import personal_source_facts
    from app.services.personal_planner import PersonalPlanner
    from app.services.price_universe import PriceUniverseBuilder
    from app.services import price_universe as universe_module
    guard = universe_module._uses_disabled_member_price
    def traced_guard(key, product):
        invalid = guard(key, product)
        if invalid:
            (args.output / (args.label+'-membership-blocker.json')).write_text(
                product.model_dump_json(indent=2), encoding='utf8')
        return invalid
    universe_module._uses_disabled_member_price = traced_guard
    from app.services.price_universe_runtime import (
        GLOBAL_PREPARED_PRICE_UNIVERSES,
        PreparedPriceUniverse,
        PreparedPriceUniverseArtifact,
    )
    from lidl_candidate_trace import (
        add_reviewed_candidates_to_preserved_pool,
        trace_reviewed_offers,
    )

    from grocery_data.app.services.manual_refresh_operations import (
        RefreshRunLock,
        production_refresh_lock_path,
    )
    from grocery_data.app.storage import create_database_engine, create_schema

    universes = Path('/srv/app/var/price_universes')
    manifest = universes / 'active/city-lund.json'
    args.output.mkdir(parents=True, exist_ok=True)
    with RefreshRunLock(production_refresh_lock_path(
        Path('/srv/app/var/grocery/grocery_data.sqlite'), universes
    )):
        before = manifest.read_bytes()
        candidate_bytes = b'{}'
        store, products = None, []
        source_build = None
        if args.normal_source_build:
            from normal_source_build import build_original_sources

            args.artifact = args.output / (args.label + '-source-universe.json')
            source_build = build_original_sources(args.artifact, store, products, args.arm == 'coop')
        data = args.artifact.read_bytes()
        baseline = PreparedPriceUniverseArtifact.model_validate_json(data).restore()
        purchase_date = wall.astimezone(__import__('zoneinfo').ZoneInfo('Europe/Stockholm')).date()
        prepared = baseline
        candidate_ids = {p.product_id for p in prepared.universe.products
            if p.source_provenance and p.source_provenance.source_channel == 'offers'
            and p.chain == 'coop' and p.coverage == 'offers_only'}
        if args.arm == 'coop':
            products = [p for p in prepared.universe.products if p.product_id in candidate_ids]
        settings = get_settings()
        required = set(settings.price_universe_required_context_ids)
        assert required.issubset({s.store_id for s in prepared.stores})
        assert not prepared.status(now=wall).excluded_stale_context_count

        def isolated_load(_settings):
            GLOBAL_PREPARED_PRICE_UNIVERSES.activate(prepared)  # This disposable process only.
            return prepared

        application.load_configured_price_universe = isolated_load
        original_facts = personal_source_facts.load_retained_facts
        def isolated_facts(pool):
            values = original_facts(pool, database='/work/base-final/frozen-base.sqlite')
            if args.reviewed_nutrition:
                from app.services.reviewed_product_nutrition import reviewed_facts

                values = personal_source_facts.FactsCollection({
                    **values, **reviewed_facts(pool.universe.products),
                })
            return values

        personal_source_facts.load_retained_facts = isolated_facts
        base_facts = original_facts(baseline, database='/work/base-final/frozen-base.sqlite')
        base_facts_version = getattr(base_facts, 'version', None) or personal_source_facts.facts_version(base_facts)
        if args.expected_base_facts_version != 'paired' and base_facts_version != args.expected_base_facts_version:
            raise ValueError('isolated source fact version does not match the controlled baseline')
        from dataclasses import asdict
        (args.output / (args.label+'-product-facts.json')).write_text(json.dumps([{'store_id': p.store_id, 'product_id': p.product_id, 'name': p.name, 'gtin': p.gtin, 'facts': asdict(base_facts[(p.store_id,p.product_id)]) if (p.store_id,p.product_id) in base_facts else None} for p in products],ensure_ascii=False,indent=2),encoding='utf8')
        diagnostics = []
        request_candidate_trace = []
        generation_trace = []
        qualified_recipe_trace = []
        singlemeal_audits = []
        basket_audits = []
        frozen_recipes = (json.loads((args.output / "baseline-acceptance.json").read_bytes())["generation_trace"]
            if args.arm == "coop" and args.label == "coop-acceptance" else None)
        original_candidates = PersonalPlanner._candidates
        original_basket = PersonalPlanner.basket

        def traced_candidates(planner, meal):
            recipes = original_candidates(planner, meal)
            qualified_recipe_trace.append({'meal_type': meal.meal_type,
                                           'recipes': [r.name for r in recipes]})
            return recipes

        def traced_basket(planner, slots, **kwargs):
            result = original_basket(planner, slots, **kwargs)
            basket_audits.append({'slots': len(slots), 'passed': result['audit'].passed, 'final': kwargs.get('final', True)})
            if (len(slots) == 1 and slots[0].recipe and len(singlemeal_audits) < 100
                and any(p.product_id == i.product_id and p.store_id == i.store_id
                        for s in result['basket'].stores for i in s.items for p in products)):
                    row = {'recipe': slots[0].recipe.model_dump(mode='json'),
                           'basket': result['basket'].model_dump(mode='json'),
                           'audit_passed': result['audit'].passed,
                           'final': kwargs.get('final', True)}
                    if row not in singlemeal_audits:
                        singlemeal_audits.append(row)
            return result

        PersonalPlanner._candidates = traced_candidates
        PersonalPlanner.basket = traced_basket
        from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator

        for method in ('generate_for_meal_type', 'generate_reference_candidates'):
            original_generator = getattr(DeterministicRecipeCandidateGenerator, method)

            def trace_generator(generator, *a, _method=method, _original=original_generator, **kw):
                if frozen_recipes is not None:
                    from app.models.recipe import Recipe
                    entry = frozen_recipes[len(generation_trace)]
                    assert entry['method'] == _method
                    recipes = [Recipe.model_validate(r) for r in entry['recipes']]
                else:
                    recipes = _original(generator, *a, **kw)
                generation_trace.append({'method': _method, 'recipes': [r.model_dump(mode='json') for r in recipes]})
                return recipes

            setattr(DeterministicRecipeCandidateGenerator, method, trace_generator)
        original_create = PersonalPlanner.create

        def observed_create(planner):
            try:
                return original_create(planner)
            finally:
                diagnostics.append(planner.diagnostics.snapshot())
                for product in products:
                    identity = (product.store_id, product.product_id)
                    nutrition = [(key, evidence) for key, evidence in planner.nutrition_cache.items()
                                 if key[:2] == identity and key[5] is not None]
                    request_candidate_trace.append({
                        'product_id': product.product_id, 'store_id': product.store_id,
                        'resolved_names': sorted({key[0] for key, rows in planner.lookup_cache.items()
                            if any((c.store_id, c.product_id) == identity for _, c in rows)}),
                        'individual_nutrition_supported_recipes': sorted({
                            key[5][0] for key, evidence in nutrition if evidence is not None}),
                        'individual_nutrition_missing_recipes': sorted({
                            key[5][0] for key, evidence in nutrition if evidence is None}),
                        'note': 'Individual evidence lookup; not a complete-basket or meal acceptance.',
                    })

        PersonalPlanner.create = observed_create
        engine = create_database_engine(os.environ['GROCERY_DATABASE_URL'])
        create_schema(engine)
        engine.dispose()
        request = json.loads(args.request.read_bytes())
        record = {
            'arm': args.arm, 'wall_started_at': wall.isoformat(),
            'clock': 'actual wall clock; no rewritten source observations',
            'purchase_date': purchase_date.isoformat(), 'request': request,
            'request_sha256': hashlib.sha256(args.request.read_bytes()).hexdigest(),
            'artifact_sha256': hashlib.sha256(data).hexdigest(),
            'candidate_sha256': hashlib.sha256(candidate_bytes).hexdigest(),
            'universe_id': prepared.universe.universe_id,
            'baseline_facts_version': base_facts_version,
            'baseline_facts_count': len(base_facts),
            'source_build': source_build,
            'reviewed_nutrition': args.reviewed_nutrition,
            'declarations_version': (__import__('app.services.reviewed_product_nutrition', fromlist=['declaration_version']).declaration_version() if args.reviewed_nutrition else None),
            'base_products_sha256': hashlib.sha256(json.dumps([
                p.model_dump(mode='json') for p in prepared.universe.products if p.product_id not in {x.product_id for x in products}
            ], sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            'baseline_built_at': baseline.universe.built_at.isoformat(),
            'isolated_build_at': prepared.universe.built_at.isoformat(),
            'status': prepared.status(now=wall).model_dump(mode='json'),
            'uid': os.getuid(), 'gid': os.getgid(), 'network': 'none',
            'automatic_trigger': False, 'production_activated': False,
            'required_contexts': sorted(required),
            'settings': {k: getattr(settings, k) for k in (
                'build_id', 'meal_plan_strategy', 'max_price_age_hours',
                'price_age_warning_hours', 'stable_candidate_search_enabled',
                'stable_candidate_base_count', 'stable_candidate_search_limit')},
            'test_environment_overrides': [
                'private disposable plan/community database', 'private guest authentication',
                'loopback development origin', 'prewarm disabled'],
            'code_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                            for base in ('/srv/app/backend/app', '/srv/app/grocery_data/app')
                            for p in sorted(Path(base).rglob('*.py'))},
        }
        output = args.output / (args.label + '.json')
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf8')
        server = uvicorn.Server(uvicorn.Config(application.app, host='127.0.0.1', port=8000,
                                              log_level='error', access_log=False))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 120
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError('isolated HTTP startup failed')
            time.sleep(.01)
        try:
            with httpx.Client(base_url='http://127.0.0.1:8000', timeout=240) as client:
                state = client.get('/api/personal/state')
                state.raise_for_status()
                assert state.json()['revision'] == request['personal']['pantry_revision'] == 0
                start_request = time.perf_counter()
                response = client.post('/api/plans', json=request)
                record.update(http_status=response.status_code,
                              http_seconds=round(time.perf_counter()-start_request, 3))
                if response.status_code == 201:
                    saved = response.json()
                    plan = PlanResponse.model_validate(saved['plan'])
                    expected_slots = sum(m['count'] for m in request['personal']['meals'])
                    expected_portions = sum(m['count']*m['servings'] for m in request['personal']['meals'])
                    assert len(plan.personal.slots) == expected_slots
                    assert plan.portions == expected_portions
                    assert plan.optimized_basket.store_count <= request['max_stores']
                    assert plan.data.live_chain_requests == 0
                    targets = {m['meal_type']: m['limits']['min_protein_g'] for m in request['personal']['meals']}
                    for row in plan.personal.checks['nutrition']:
                        kind = next(s.meal_type for s in plan.personal.slots if s.id == row['slot_id'])
                        assert row['values']['protein_g'] >= targets[kind]
                    readback = client.get('/api/plans/' + saved['plan_id'])
                    readback.raise_for_status()
                    record.update(result='PASS', slots=expected_slots, portions=expected_portions,
                                  cost=plan.optimized_basket.total,
                                  stores=plan.optimized_basket.store_count,
                                  verification=plan.optimized_basket.verification_status,
                                  persisted_readback=True)
                    (args.output / (args.label + '-plan.json')).write_text(
                        plan.model_dump_json(indent=2), encoding='utf8')
                    record['coop_trace'] = trace_reviewed_offers(prepared, products, purchase_date, plan)
                    record['isolated_health'] = client.get('/health').status_code
                    record['isolated_ready'] = client.get('/ready').status_code
                    record['saved_equals_readback'] = readback.json()['plan'] == saved['plan']
                else:
                    record.update(result='BLOCKED', response=response.json(),
                                  lidl_trace=trace_reviewed_offers(prepared, products, purchase_date))
        finally:
            server.should_exit = True
            thread.join(timeout=15)
            assert not thread.is_alive()
        assert manifest.read_bytes() == before
        if frozen_recipes is not None:
            assert generation_trace == frozen_recipes
        record['frozen_baseline_recipes'] = frozen_recipes is not None
        record['basket_audits'] = basket_audits
        record.update(active_manifest_unchanged=True,
                      active_manifest_sha256=hashlib.sha256(before).hexdigest(),
                      total_seconds=round(time.perf_counter()-started, 3), diagnostics=diagnostics,
                      request_candidate_trace=request_candidate_trace, generation_trace=generation_trace,
                      qualified_recipe_trace=qualified_recipe_trace, singlemeal_audits=singlemeal_audits)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf8')
        print(json.dumps({k: record[k] for k in ('arm', 'http_status', 'result', 'http_seconds', 'total_seconds')} |
                         {'cost': record.get('cost')}), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - sanitize all env-bearing bootstrap failures
        import traceback
        print(json.dumps({'bootstrap_error': type(exc).__name__, 'frames': [
            {'file': f.filename, 'line': f.lineno, 'function': f.name}
            for f in traceback.extract_tb(exc.__traceback__)
        ]}), flush=True)
        raise SystemExit(1) from None
