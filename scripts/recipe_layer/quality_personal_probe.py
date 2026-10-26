"""Bounded real plan/save/GET API against retained public inputs and new owners.

Run ONLY through budgeted_check. No plan, price, policy or checkout API is
replaced. The replay adapter supplies the saved source facts and price clock.
"""
import argparse
import dataclasses
import hashlib
import json
import os
import secrets
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from smako_budget_context import arm_phase


def main(args):
    cancel_phase = arm_phase(120)
    started = time.perf_counter()
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    base = "http://127.0.0.1:18226"
    os.environ.update(PYTHON_DOTENV_DISABLED="1", SECRET_KEY=secrets.token_hex(32),
        PLAN_STORE_PATH=str(state / "plans.sqlite3"), GROCERY_DATABASE_URL="sqlite:///" + (state / "grocery.sqlite").as_posix(),
        PRICE_PROVIDER="own", PRICE_UNIVERSE_REQUIRED="true", PRICE_UNIVERSE_CITY="Malmö",
        COMPLETE_RECIPES_ENABLED="true", APP_ENV="test", PUBLIC_BASE_URL=base,
        PRICE_UNIVERSE_PREWARM_ENABLED="false", SOURCE_FACTS_PREWARM_ENABLED="false",
        ALLOW_PROVIDER_FALLBACK="false", ALLOW_MOCK_FALLBACK="false",
        RECIPE_PREPARATION_CACHE_ROOT=str(state.parent / "quality-prepared"),
        LIBRARY_SEARCH_POLICY=args.policy)
    from app.config import get_settings

    from grocery_data.app.storage.database import create_database_engine, create_schema
    engine = create_database_engine(os.environ["GROCERY_DATABASE_URL"])
    create_schema(engine)
    engine.dispose()
    from app.services.personal_policy import ProductFacts
    from app.services.personal_source_facts import FactsCollection
    from app.services.price_universe_runtime import (
        GLOBAL_PREPARED_PRICE_UNIVERSES,
        PreparedPriceUniverseArtifact,
    )
    prepared = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    GLOBAL_PREPARED_PRICE_UNIVERSES.activate(prepared)
    raw = json.loads(args.facts.read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
    facts.version = raw["facts_version"]
    del raw
    source_loading_seconds = time.perf_counter() - started
    shared_preparation = None
    shared_preparation_seconds = 0
    from app.services.official_product_facts import shell_egg_quantity_proofs
    shell_egg_quantity_proofs(prepared.universe.products, facts)
    if args.policy == "smako-current-library-v2":
        from app.services.meal_prepared_artifacts import prepare_current_sources
        payload = json.loads(args.requests.read_bytes())[args.case]
        portions = {m["servings"] for m in payload["personal"]["meals"] if m["count"]}
        common_started = time.perf_counter()
        shared_preparation = prepare_current_sources(prepared, facts, portions=portions)
        shared_preparation_seconds = time.perf_counter() - common_started
    from app.services import personal_source_facts
    personal_source_facts.load_retained_facts = lambda *a, **kw: facts
    clock = datetime.fromisoformat(args.clock)

    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.astimezone(tz) if tz else clock.replace(tzinfo=None)

    from app.api import plan as plan_api
    from app.services import (
        beta_observability,
        meal_plan_optimizer,
        personal_planner,
        price_universe_runtime,
        user_pricing,
    )
    for module in (plan_api, beta_observability, meal_plan_optimizer, personal_planner, price_universe_runtime):
        module.datetime = ReplayClock
    meal_plan_optimizer.current_pricing_date = user_pricing.current_pricing_date = lambda: clock.astimezone(ZoneInfo("Europe/Stockholm")).date()
    from app.main import app
    from app.models import PlanRequest
    from app.services.meal_library_content import encoded
    from app.services.meal_prepared_artifacts import method_signature
    from app.services.performance_trace import activate_performance_trace
    from app.services.plan_store import PlanStore
    from app.services.recipe_library import current_recipes
    from fastapi.testclient import TestClient
    app.state.plan_store = PlanStore(state / "plans.sqlite3")
    # Observe actual planners without changing their inputs or search policy.
    planners = []
    initialize = personal_planner.PersonalPlanner.__init__

    def observed(self, *a, **kw):
        planners.append(self)
        initialize(self, *a, **kw)

    personal_planner.PersonalPlanner.__init__ = observed
    request = PlanRequest.model_validate(json.loads(args.requests.read_bytes())[args.case])
    result = {"case": args.case, "request": request.model_dump(mode="json"), "clock": args.clock,
        "total_current_variants": len(current_recipes()), "policy": get_settings().library_search_policy,
        "source_loading_seconds": source_loading_seconds,
        "shared_preparation": shared_preparation, "shared_preparation_seconds": shared_preparation_seconds,
        "library_merge_generations": get_settings().library_merge_generations,
        "method_signature": method_signature(),
        "library_manifest_sha256": hashlib.sha256(Path("backend/app/data/recipes/library-manifest.json").read_bytes()).hexdigest(),
        "universe_sha256": hashlib.sha256(args.universe.read_bytes()).hexdigest(),
        "facts_sha256": hashlib.sha256(args.facts.read_bytes()).hexdigest(), "facts_version": facts.version,
        "scope": "Real in-process HTTP plan/save/GET; frozen source replay, no live collection or browser transport",
        "started_at": datetime.now(UTC).isoformat(), "status": "starting"}

    def save():
        if planners and hasattr(planners[-1], "diagnostics"):
            result["diagnostics"] = planners[-1].diagnostics.snapshot()
            result["engine_timings_seconds"] = dict(planners[-1].timings)
        temporary = args.output.with_suffix(".next")
        temporary.write_bytes(encoded(result))
        temporary.replace(args.output)

    if args.browser:
        from quality_browser_ui import run
        run(app, request, result, args, started, save)
        cancel_phase()
        return

    client = TestClient(app, base_url=base, headers={"Origin": base})
    registration = client.post("/api/account/register", json={"email": secrets.token_hex(12) + "@example.invalid", "password": secrets.token_urlsafe(30)})
    assert registration.status_code == 201, registration.status_code
    result["preparation_seconds"] = time.perf_counter() - started
    print({"case": args.case, "preparation_seconds": result["preparation_seconds"]}, flush=True)
    request_start = time.perf_counter()
    result.update(status="running", deadline_seconds=75)
    save()

    def progress_receipt():
        result.update(last_observed_api_seconds=time.perf_counter() - request_start,
                      valid_menu_delivered=False)
        result["performance"] = dataclasses.asdict(trace.snapshot())
        if sampler is not None:
            result["profile"] = sampler.report()
        save()

    receipt_timer = threading.Timer(60, progress_receipt)
    receipt_timer.daemon = True
    receipt_timer.start()
    cancel_phase()
    cancel_phase = arm_phase(75)
    sampler = None
    if args.profile:
        from sample_week_stacks import StackSampler
        sampler = StackSampler(interval_seconds=0.1)
        sampler.__enter__()
    with activate_performance_trace() as trace:
        response = client.post("/api/plans", json=request.model_dump(mode="json"))
        result.update(http_status=response.status_code, api_post_seconds=time.perf_counter() - request_start)
        if response.status_code == 201:
            saved = response.json()
            loaded = client.get("/api/plans/" + saved["plan_id"])
            assert loaded.status_code == 200, loaded.status_code
            plan = saved["plan"]
            assert loaded.json()["plan"] == plan
            checks = plan["personal"]["checks"]
            assert checks["checkout_audit"]["passed"]
            result.update(status="saved_and_read_back", valid_menu_delivered=True, total=plan["optimized_basket"]["total"],
                checks=checks, plan_sha256=hashlib.sha256(encoded(plan)).hexdigest(),
                recipe_names=[r["name"] for r in plan["recipes"]])
            (state / (args.case + "-saved.json")).write_bytes(encoded(saved))
        else:
            result.update(status="blocked", valid_menu_delivered=False, error=response.json())
        result["api_seconds"] = time.perf_counter() - request_start
        result["performance"] = dataclasses.asdict(trace.snapshot())
    receipt_timer.cancel()
    cancel_phase()
    if sampler is not None:
        sampler.__exit__()
        result["profile"] = sampler.report()
    save()
    print({k: result[k] for k in ("case", "status", "api_seconds", "http_status")}, flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for field in ("universe", "facts", "requests", "output", "state"):
        p.add_argument("--" + field, type=Path, required=True)
    p.add_argument("--clock", required=True)
    p.add_argument("--case", required=True)
    p.add_argument("--profile", action="store_true")
    p.add_argument("--browser", action="store_true")
    p.add_argument("--expected-total", type=float)
    p.add_argument("--policy", choices=["legacy", "smako-current-library-v2"], default="legacy")
    main(p.parse_args())
