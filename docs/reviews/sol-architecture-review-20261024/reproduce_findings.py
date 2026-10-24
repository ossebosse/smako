"""Offline review probes: passing means the reported bug was reproduced.

Reviewed revision: ac0bbfe. These are evidence probes, not passing acceptance
tests for the corrected implementation. Reverse the bug assertions when adding
permanent regression tests. No production data or retailer network is used.
"""
import asyncio
import sys
from contextlib import nullcontext
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_approved_snapshot_with_base_release_creates_staging_before_new_check(tmp_path):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('review_fetch', Path.cwd() / 'scripts/fetch_axfood_product_details.py')
    fetch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fetch)
    archive = tmp_path / 'archive'
    database = tmp_path / 'catalog.sqlite'
    database.touch()
    from backend.tests.test_axfood_detail_archive import CODE, NOW, raw
    from grocery_data.app.services.axfood_detail_archive import publish_release, retain_response
    retain_response(archive / 'staging/seed', 'willys', CODE, raw(), now=NOW)
    base = publish_release(archive, 'seed')
    engine = SimpleNamespace(dispose=lambda: None)
    argv = ['fetch', '--chain', 'willys', '--store-id', '1',
            '--approved-snapshot', 'approved', '--database', str(database),
            '--price-universe-root', str(tmp_path / 'prices'),
            '--archive-root', str(archive), '--run-id', 'next', '--base-release', str(base)]
    with (patch.object(sys, 'argv', argv), patch.object(fetch, 'RefreshRunLock', lambda *a: nullcontext()),
          patch('grocery_data.app.storage.create_database_engine', return_value=engine),
          patch('grocery_data.app.storage.create_session_factory', return_value=lambda: nullcontext(None)),
          patch('grocery_data.app.services.axfood_catalogue_queue.approved_catalogue_codes',
                return_value=(['123'], {'fixture': True})),
          patch('deploy.scripts.storage_maintenance.maintain_axfood_archives', return_value={'status': 'ok'}),
          pytest.raises(SystemExit) as exc):
        asyncio.run(fetch.main())
    assert exc.value.code == 2
    assert (archive / 'staging/next/approved-catalogue-willys.json').exists()
    print('CONFIRMED: approved-snapshot + base-release aborts before copying LKG')


def test_prepared_hit_ignores_new_saved_cheaper_valid_delivery(tmp_path):
    from app.services.personal_planner import PersonalPlanner
    from app.services.plan_store import PlanStore
    from app.services.planner_artifacts import OwnedPlannerArtifacts

    from backend.tests.test_complete_scope_incumbents import fixture, planner
    from backend.tests.test_personal_planning_v2 import NOW

    request, universe, facts, pantry = fixture()
    pantry['items'] = []
    settings = replace(planner(request, universe, facts, pantry).settings,
                       library_search_policy='smako-verified-reference-v1')
    store = PlanStore(tmp_path / 'plans.sqlite')
    cache = OwnedPlannerArtifacts(store, 'a' * 64)
    def subject():
        return PersonalPlanner(request, settings, universe, deepcopy(pantry), facts=facts,
                               now=NOW, artifacts=cache)
    # Real qualification, prices and checkout; only the first search's proposal
    # is adversarial, as in the repository's incumbent regression tests.
    initial = subject()
    def expensive(cohorts, *, evaluate, accepts, **kwargs):
        group = list(cohorts)[-1][1][0]
        valid = []
        for slot in group:
            slots = (slot,)
            if accepts(slots, final=True):
                try:
                    result = evaluate(slots, final=False)
                    valid.append((slots, result))
                except ValueError:
                    pass
        return max(valid, key=lambda row: row[1]['basket'].total)
    initial.service.menu_optimizer.optimize_library_slots = expensive
    expensive_plan = initial.create(_compare_scopes=False)
    cheap = PersonalPlanner(request, settings, universe, deepcopy(pantry), facts=facts, now=NOW).create(_compare_scopes=False)
    assert cheap.optimized_basket.total < expensive_plan.optimized_basket.total
    assert cheap.personal.checks['verified_reference']['context'] == expensive_plan.personal.checks['verified_reference']['context']
    reaudit = subject().basket(cheap.personal.slots, final=True)
    assert reaudit['audit'].passed
    assert reaudit['basket'].total == cheap.optimized_basket.total
    store.create(request, cheap, owner_actor_hash=cache.owner)
    assert cache.recent_menu_records()
    warm = subject().create(_compare_scopes=False)
    assert warm.personal.checks['verified_reference']['prepared_menu_hit']
    assert warm.optimized_basket.total > cheap.optimized_basket.total
    print('CONFIRMED: cached plan', warm.optimized_basket.total,
          'ignores saved audited menu', cheap.optimized_basket.total)
