"""Read-only, frozen-input reproduction of the real restored personal request.

Run with the scheduler environment and public source mounts. No request reaches
the production API and no user database or active price artifact is written.
"""
import argparse
import asyncio
import hashlib
import inspect
import json
import os
import socket
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings, get_settings
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
from app.services.economic_ingredient_selector import EconomicIngredientSelector
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe import PriceUniverseBuilder
from app.services.price_universe_runtime import (
    LocalPriceUniverseProvider,
    PreparedPriceUniverseArtifact,
    PreparedPriceUniverseManager,
)

from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)


def failed_request():
    """Reconstruct the first failed invocation, whose launcher lost its request."""
    return PlanRequest(
        postal_code="22350", recipes=0, max_stores=2,
        personal=PersonalPlanning(
            allow_nutrition_estimates=True,
            meals=[MealSettings(meal_type=k, count=5, servings=s,
                                limits=PortionLimits(min_protein_g=p))
                   for k, s, p in [("dinner", 2, 40), ("breakfast", 1, 30), ("snack", 1, 20)]],
        ),
    )


def settings_projection(settings):
    # Explicit whitelist; never serialize API credentials or environment dumps.
    names = ("app_env", "build_id", "meal_plan_strategy", "stable_candidate_search_enabled",
             "stable_candidate_base_count", "stable_candidate_search_limit", "max_price_age_hours",
             "price_age_warning_hours", "price_universe_required_context_ids",
             "allow_medium_semantic_matches", "allow_estimated_quantities",
             "allow_unknown_quantities", "allow_unknown_sale_model")
    return {key: getattr(settings, key) for key in names}


async def run(args):
    clock = datetime.fromisoformat(args.clock)
    if clock.tzinfo is None:
        raise ValueError("an explicit aware isolated test clock is required")
    root = args.universes
    before = (root / "active/city-lund.json").read_bytes()
    data = args.artifact.read_bytes()
    baseline = PreparedPriceUniverseArtifact.model_validate_json(data).restore()
    if args.diagnostic_beam_width:
        from app.services.menu_optimizer import MenuOptimizer

        ordinary_search = MenuOptimizer.optimize_slots

        def diagnostic_search(self, *values, **options):
            options['beam_width'] = args.diagnostic_beam_width
            return ordinary_search(self, *values, **options)

        MenuOptimizer.optimize_slots = diagnostic_search
    actual = json.loads(args.request.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    metadata = {
        "wall_started_at": datetime.now(UTC).isoformat(), "frozen_test_clock": clock.isoformat(),
        "artifact_sha256": hashlib.sha256(data).hexdigest(),
        "universe_id": baseline.universe.universe_id,
        "original_built_at": baseline.universe.built_at.isoformat(),
        "status_at_test_clock": baseline.status(now=clock).model_dump(mode="json"),
        "uid": os.getuid(), "gid": os.getgid(), "cwd": os.getcwd(),
        "source_requests": 0, "production_activated": False,
        "actual_planner_module": inspect.getfile(PersonalPlanner),
        "actual_planner_sha256": hashlib.sha256(Path(inspect.getfile(PersonalPlanner)).read_bytes()).hexdigest(),
        "settings_from_environment": settings_projection(get_settings()),
        "settings_direct_defaults": settings_projection(Settings()),
        "state": {"revision": 0, "items": [], "reservations": {}, "events": {}},
        "recipe_generation": "Existing PersonalPlanner._candidates: dynamic 80 dinner candidates plus reviewed 15; breakfast/snack existing generator. No 25-template filter.",
        "random_seed": None,
        "search": {"deterministic": True, "beam_width": args.diagnostic_beam_width or 8,
                   "diagnostic_override": bool(args.diagnostic_beam_width)},
        "source_code_sha256": {str(p.relative_to(Path('/srv/app'))): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(Path('/srv/app/backend/app').rglob('*.py'))},
    }
    (args.output / f"{args.label}-inputs.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf8")
    for case in args.cases.split(','):
        started = time.perf_counter()
        rebuilt = case.endswith('rebuilt')
        legacy = case.startswith('failed')
        request = failed_request() if legacy else PlanRequest.model_validate(actual)
        settings = Settings() if legacy else get_settings()
        prepared = baseline
        if rebuilt:
            universe = PriceUniverseBuilder().build(baseline.universe.key, baseline.universe.products,
                                                     built_at=clock)
            prepared = await PreparedPriceUniverseManager().build_and_activate(
                city="Lund", postal_codes=["22350"], provider=LocalPriceUniverseProvider(universe, baseline.stores),
                memberships={}, selector=EconomicIngredientSelector(), built_at=clock,
            )
        state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
        record = {"case": case, "request": request.model_dump(mode="json"),
                  "request_fields_set": sorted(request.model_fields_set),
                  "settings": settings_projection(settings), "universe_rebuilt": rebuilt,
                  "input_products": len(prepared.universe.products),
                  "input_economic_pool_count": len(prepared.economic_pool.ingredients)}
        path = args.output / f"{args.label}-{case}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
        planner = PersonalPlanner(request, settings, prepared, state, now=clock)
        candidate_names = {}
        ordinary = planner._candidates

        def observed_candidates(meal, ordinary=ordinary, candidate_names=candidate_names):
            rows = ordinary(meal)
            candidate_names[meal.meal_type] = [r.name for r in rows]
            return rows

        planner._candidates = observed_candidates
        try:
            result = planner.create()
            assert len(result.personal.slots) == 15 and result.portions == 20
            assert result.optimized_basket.store_count <= 2
            targets = {m.meal_type: m.limits.min_protein_g for m in request.personal.meals}
            for row in result.personal.checks['nutrition']:
                slot = next(s for s in result.personal.slots if s.id == row['slot_id'])
                assert row['values']['protein_g'] >= targets[slot.meal_type]
            record.update(status="PASS", cost=result.optimized_basket.total,
                          verification=result.optimized_basket.verification_status,
                          portions=result.portions, slots=len(result.personal.slots),
                          store_count=result.optimized_basket.store_count)
            (args.output / f"{args.label}-{case}-plan.json").write_text(result.model_dump_json(indent=2), encoding="utf8")
        except ValueError as exc:
            record.update(status=getattr(exc, 'code', type(exc).__name__), reason=str(exc))
        record.update(seconds=round(time.perf_counter()-started, 3),
                      facts_version=planner.facts_version, reference_version=planner.reference_version,
                      qualified_candidates=candidate_names, diagnostics=planner.diagnostics.snapshot())
        assert state == metadata['state']
        assert (root / "active/city-lund.json").read_bytes() == before
        record['active_manifest_unchanged'] = True
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
        print(json.dumps({k:record[k] for k in ['case','status','seconds']} | {'cost':record.get('cost'), 'pools':planner.diagnostics.snapshot()['pools']}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifact', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--clock', required=True)
    parser.add_argument('--cases', default='failed-rebuilt,restored-original')
    parser.add_argument('--diagnostic-beam-width', type=int, choices=range(1, 129))
    parser.add_argument('--universes', type=Path, default=Path('/srv/app/var/price_universes'))
    args = parser.parse_args()
    with RefreshRunLock(production_refresh_lock_path(Path('/work/base/refreshed.sqlite'), args.universes)), patch.object(socket.socket, 'connect', side_effect=AssertionError('network disabled')):
        asyncio.run(run(args))


if __name__ == '__main__':
    main()
