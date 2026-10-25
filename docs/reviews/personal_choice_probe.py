"""Bounded, serial, offline ASGI latency observations; synthetic accounts only.

Each output directory is new. No historical matrix driver is invoked. Linux
alarm stops the entire batch on the first five-minute plan timeout.
"""
from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import secrets
import signal
import time
from contextlib import asynccontextmanager, nullcontext
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--requests", type=Path, required=True)
    parser.add_argument("--policy", default="smako-verified-reference-v1")
    parser.add_argument("--instrument", action="store_true")
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--serve-port", type=int)
    parser.add_argument("--cases", nargs="+", default=["A", "A", "B", "C", "D", "E", "E", "A", "owner", "A", "E"])
    args = parser.parse_args()
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=False)
    def final_resource():
        write(args.output / "final-resource.json", {
            "scope": "atexit after final report serialization and client/server shutdown",
            "memory": {n: int(Path("/sys/fs/cgroup/memory." + n).read_text()) for n in ("current", "peak", "swap.current")}})
    atexit.register(final_resource)
    os.environ["RECIPE_PREPARATION_CACHE_ROOT"] = str(args.output / "prepared")
    os.environ["GROCERY_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    from app import config
    settings = config.Settings(app_env="test", complete_recipes_enabled=True,
        price_provider="own", price_universe_city="Malmö", library_search_policy=args.policy,
        library_merge_generations=False, plan_store_path=args.output / "owned.sqlite",
        secret_key=secrets.token_hex(32), source_facts_prewarm_enabled=False)
    config.get_settings = lambda: settings
    from app import main as application
    from app.api import plan as api
    from app.models import PlanRequest, SavedPlan
    from app.services import price_universe_runtime, reference_library
    from app.services.meal_prepared_artifacts import method_signature
    from app.services.performance_trace import activate_performance_trace
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_policy import ProductFacts
    from app.services.personal_source_facts import FactsCollection
    from app.services.plan_jobs import PlanJobs
    from app.services.plan_store import PlanStore
    from app.services.planner_admission import PlannerAdmissionController
    from app.services.recipe_library import current_recipes, library_version
    from fastapi.testclient import TestClient

    from backend.scripts.planner_acceptance_matrix import quality

    reference_library.PIN = Path("/srv/app/backend/app/data/recipes/reference-library-262.json")
    manifest = json.loads((args.inputs / "matrix-inputs.json").read_bytes())
    for name, digest in manifest["sha256"].items():
        assert hashlib.sha256((args.inputs / name).read_bytes()).hexdigest() == digest
    clock = datetime.fromisoformat(manifest["now"])
    prepared = price_universe_runtime.GLOBAL_PREPARED_PRICE_UNIVERSES.load_file_and_activate(args.inputs / "combined-prices.json")
    raw = json.loads((args.inputs / "combined-facts.json").read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]}, source_manifests=raw.get("source_manifests", ()))
    assert facts.version == raw["facts_version"]
    del raw
    assert len(current_recipes()) == 262, "This probe must never expand the recipe catalogue"
    requests = json.loads(args.requests.read_bytes())
    assert set(requests) == set("ABCDE")
    for body in requests.values():
        PlanRequest.model_validate(body)  # Validate without materializing omitted defaults.
        assert body["postal_code"] in prepared.universe.key.postal_codes
        assert body["recipes"] == 5 and body["servings"] == 4 and body["max_stores"] == 2
    report = {"inputs": manifest, "requests": requests, "policy": args.policy,
        "method": method_signature(), "library": library_version(), "recipe_count": 262, "instrumented": args.instrument,
        "startup_seconds": time.perf_counter() - started, "records": [],
        "requests_sha256": hashlib.sha256(args.requests.read_bytes()).hexdigest(),
        "boundary": "ASGI POST through first observed saved result and GET; UI's 2s polling; no browser/network latency",
        "background_preparation": "none; A seed is an ordinary fully saved request", "status": "running"}
    target = args.output / "report.json"
    write(target, report)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.astimezone(tz) if tz else clock.replace(tzinfo=None)

    @asynccontextmanager
    async def lifespan(app):
        app.state.beta_settings = settings
        app.state.plan_store = PlanStore(settings.plan_store_path)
        app.state.planner_admission = PlannerAdmissionController(max_concurrent=1, max_queued=1)
        app.state.plan_jobs = PlanJobs(max_pending=2)
        app.state.community_session_factory = None
        try:
            yield
        finally:
            await app.state.plan_jobs.close()

    application.app.router.lifespan_context = lifespan
    original_init, original_create = PersonalPlanner.__init__, api._create_saved_plan
    planner_times, traces, live_traces, init_times, save_times = [], [], [], [], []
    original_save = PlanStore.create
    original_plan_create = PersonalPlanner.create
    import threading
    profile_local, profiles = threading.local(), []

    def profiled_plan_create(self, *pos, **kw):
        if not args.profile or getattr(profile_local, "active", False):
            return original_plan_create(self, *pos, **kw)
        import cProfile

        profiler = cProfile.Profile()
        profiles.append(profiler)
        profile_local.active = True
        profiler.enable()
        try:
            return original_plan_create(self, *pos, **kw)
        finally:
            profiler.disable()
            profile_local.active = False

    def profile_summary():
        import pstats

        result = []
        for i, profiler in enumerate(profiles):
            profiler.dump_stats(str(args.output / f"profile-{i}.pstats"))
            stats = pstats.Stats(profiler)
            rows = sorted(stats.stats.items(), key=lambda r: r[1][3], reverse=True)[:45]
            result.append([{"function": f"{k[0]}:{k[1]}:{k[2]}", "calls": v[1], "self_seconds": v[2], "cumulative_seconds": v[3]} for k, v in rows])
        return result

    def timed_save(self, *pos, **kw):
        saved_started = time.perf_counter()
        try:
            return original_save(self, *pos, **kw)
        finally:
            save_times.append(time.perf_counter() - saved_started)

    def frozen_init(self, *pos, **kw):
        init_started = time.perf_counter()
        kw.setdefault("facts", facts)
        kw.setdefault("now", clock)
        original_init(self, *pos, **kw)
        init_times.append(time.perf_counter() - init_started)
        planner_times.append(self.timings)

    async def traced_create(*pos, **kw):
        request_started, timing_index = time.perf_counter(), len(planner_times)
        with activate_performance_trace() if args.instrument else nullcontext() as trace:
            if trace is not None:
                live_traces.append(trace)
            try:
                saved = await original_create(*pos, **kw)
                if args.serve_port:
                    report["records"].append({"outcome": "PASS", "server_saved_seconds": time.perf_counter() - request_started,
                        "normalized_request": saved.request.model_dump(mode="json"),
                        "planner_timings": [dict(t) for t in planner_times[timing_index:]], **quality(saved.plan, saved.request)})
                    write(target, report)
                return saved
            except Exception as error:
                if args.serve_port:
                    report["records"].append({"outcome": "BLOCKED", "code": getattr(error, "code", None),
                        "stage": getattr(error, "stage", None), "exception_type": type(error).__name__,
                        "server_saved_seconds": time.perf_counter() - request_started,
                        "planner_timings": [dict(t) for t in planner_times[timing_index:]]})
                    write(target, report)
                raise
            finally:
                if trace is not None:
                    traces.append(asdict(trace.snapshot()))

    def timeout(_signum, _frame):
        report["status"] = "STOP_FIRST_TIMEOUT"
        report["records"][-1].update(outcome="TIMEOUT", timeout_seconds=300,
            planner_timings=[dict(t) for t in planner_times],
            traces=[asdict(t.snapshot()) for t in live_traces])
        report["records"][-1]["profile"] = profile_summary()
        from app.services import planner_shared_cache
        if hasattr(planner_shared_cache, "CHECKOUT_ARITHMETIC"):
            report["records"][-1]["arithmetic_stats"] = planner_shared_cache.CHECKOUT_ARITHMETIC.stats()
        report["final_memory"] = {n: int(Path("/sys/fs/cgroup/memory." + n).read_text()) for n in ("current", "peak", "swap.current")}
        write(target, report)
        final_resource()
        os._exit(124)

    signal.signal(signal.SIGALRM, timeout)
    with (patch.object(PersonalPlanner, "__init__", frozen_init),
          patch.object(PersonalPlanner, "create", profiled_plan_create),
          patch.object(PlanStore, "create", timed_save),
          patch.object(api, "_create_saved_plan", traced_create),
          patch.object(api, "datetime", FrozenDateTime),
          patch.object(price_universe_runtime, "datetime", FrozenDateTime),
          patch.object(api, "current_pricing_date", lambda: clock.date()),
          (nullcontext() if args.serve_port else TestClient(application.app, raise_server_exceptions=False)) as client):
        if args.serve_port:
            import uvicorn

            uvicorn.run(application.app, host="0.0.0.0", port=args.serve_port, log_level="error", access_log=False)
            report["status"] = "browser_server_stopped"
            report["process_seconds"] = time.perf_counter() - started
            report["final_memory"] = {n: int(Path("/sys/fs/cgroup/memory." + n).read_text()) for n in ("current", "peak", "swap.current")}
            write(target, report)
            return
        def register():
            client.cookies.clear()
            response = client.post("/api/account/register", json={"email": secrets.token_hex(12) + "@example.invalid", "password": secrets.token_urlsafe(32)})
            assert response.status_code == 201, response.status_code

        register()
        owner = 1
        for case in args.cases:
            if case == "owner":
                register()
                owner += 1
                continue
            signal.alarm(300)
            planner_times.clear()
            traces.clear()
            live_traces.clear()
            init_times.clear()
            save_times.clear()
            profiles.clear()
            row = {"case": case, "owner": owner, "stages": []}
            report["records"].append(row)
            write(target, report)
            print(json.dumps({"start": case, "owner": owner}), flush=True)
            call_started = time.perf_counter()
            response = client.post("/api/plans", json=requests[case], headers={"Prefer": "respond-async"})
            row["post_seconds"] = time.perf_counter() - call_started
            if response.status_code == 202:
                url = response.json()["status_url"]
                while response.status_code == 202:
                    stage = response.json().get("stage")
                    if not row["stages"] or row["stages"][-1]["stage"] != stage:
                        row["stages"].append({"stage": stage, "at": time.perf_counter() - call_started})
                        write(target, report)
                    time.sleep(2)
                    response = client.get(url)
            row["saved_response_seconds"] = time.perf_counter() - call_started
            row["http_status"] = response.status_code
            if response.status_code == 201:
                saved = SavedPlan.model_validate(response.json())
                row.update(outcome="PASS", **quality(saved.plan, saved.request))
                row["normalized_request"] = saved.request.model_dump(mode="json")
                reread = client.get("/api/plans/" + saved.plan_id)
                assert reread.status_code == 200
                assert SavedPlan.model_validate(reread.json()).plan == saved.plan
                row["through_get_seconds"] = time.perf_counter() - call_started
                row["history_read_passed"] = True
            else:
                row["outcome"] = "BLOCKED"
                row["error"] = response.json()
            signal.alarm(0)
            row["planner_timings"] = [dict(t) for t in planner_times]
            row["initialization_seconds"] = list(init_times)
            row["save_seconds"] = list(save_times)
            row["profile"] = profile_summary()
            row["traces"] = list(traces)
            from app.services.planner_shared_cache import SHARED_RESOLUTION
            row["resolution_stats"] = SHARED_RESOLUTION.stats()
            from app.services import planner_shared_cache
            if hasattr(planner_shared_cache, "CHECKOUT_ARITHMETIC"):
                row["arithmetic_stats"] = planner_shared_cache.CHECKOUT_ARITHMETIC.stats()
            row["peak_bytes"] = int(Path("/sys/fs/cgroup/memory.peak").read_text())
            write(target, report)
            print(json.dumps({k: row.get(k) for k in ("case", "outcome", "saved_response_seconds", "paid")}), flush=True)
    report["status"] = "complete"
    report["process_seconds"] = time.perf_counter() - started
    report["final_memory"] = {n: int(Path("/sys/fs/cgroup/memory." + n).read_text()) for n in ("current", "peak", "swap.current")}
    write(target, report)


if __name__ == "__main__":
    main()
