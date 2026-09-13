"""Actual isolated ASGI/HTTP lifecycle, warm repeat and two-owner admission probe.

Run with Docker network=none and read-only public source mounts. The plan store
and every guest belong only to this disposable test container. No cookies,
tokens, owner hashes or plan IDs are written to the report.
"""

import json
import os
import resource
import secrets
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from pathlib import Path

START = time.perf_counter()
OUT = Path("/output/http-private") / secrets.token_hex(8)
OUT.mkdir(mode=0o700, parents=True, exist_ok=True)
os.environ.update(
    APP_ENV="development",
    PUBLIC_BASE_URL="http://127.0.0.1:8000",
    SECRET_KEY=secrets.token_hex(32),
    BETA_ADMIN_TOKEN=secrets.token_hex(32),
    PLAN_STORE_PATH=str(OUT / "plans.sqlite3"),
    GROCERY_DATABASE_URL="sqlite+pysqlite:///" + str(OUT / "grocery.sqlite"),
    PRICE_UNIVERSE_PREWARM_ENABLED="false",  # No test-answer prewarming.
)

import fastapi.routing
import httpx
import uvicorn
from app.main import app
from app.services import personal_source_facts
from app.services.personal_planner import PersonalPlanner
from app.services.personal_store import PersonalStore
from app.services.plan_store import PlanStore

from grocery_data.app.storage import create_database_engine, create_schema

ACTIVE = ContextVar("http_probe_trace", default=None)
traces = []


@contextmanager
def span(name):
    trace = ACTIVE.get()
    if trace is None:
        yield
        return
    entry = [time.perf_counter(), 0.0]
    trace["stack"].append(entry)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - entry[0]
        trace["stack"].pop()
        if trace["stack"]:
            trace["stack"][-1][1] += elapsed
        trace["seconds"][name] += elapsed - entry[1]


def wrap_sync(cls, method, name):
    original = getattr(cls, method)

    @wraps(original)
    def measured(*args, **kwargs):
        with span(name):
            return original(*args, **kwargs)

    setattr(cls, method, measured)


def wrap_async(cls, method, name):
    original = getattr(cls, method)

    @wraps(original)
    async def measured(*args, **kwargs):
        with span(name):
            return await original(*args, **kwargs)

    setattr(cls, method, measured)


class TimingMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] != "/api/plans":
            return await self.inner(scope, receive, send)
        trace = {"stack": [], "seconds": Counter()}
        token = ACTIVE.set(trace)
        try:
            with span("http_and_response_other"):
                await self.inner(scope, receive, send)
        finally:
            traces.append(dict(trace["seconds"]))
            ACTIVE.reset(token)


@contextmanager
def guest():
    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=180)
    try:
        client.get("/api/personal/state").raise_for_status()
        yield client
    finally:
        client.close()


BASE = json.loads(Path("/inputs/combined-request.json").read_bytes())
BASE["personal"]["allow_nutrition_estimates"] = True


def submit(client):
    base = json.loads(json.dumps(BASE))
    base["personal"]["pantry_revision"] = client.get("/api/personal/state").json()["revision"]
    started = time.perf_counter()
    response = client.post("/api/plans", json=base)
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    saved = response.json()
    plan = saved["plan"]
    assert len(plan["personal"]["slots"]) == 15 and plan["portions"] == 20
    assert plan["optimized_basket"]["store_count"] <= 2
    assert plan["data"]["live_chain_requests"] == 0
    for row in plan["personal"]["checks"]["nutrition"]:
        kind = next(s["meal_type"] for s in plan["personal"]["slots"] if s["id"] == row["slot_id"])
        assert row["values"]["protein_g"] >= {"dinner": 40, "breakfast": 30, "snack": 20}[kind]
    return {
        "seconds": elapsed,
        "status": response.status_code,
        "cost": plan["optimized_basket"]["total"],
        "price_version": plan["data"]["price_universe_id"],
    }, saved


def main():
    engine = create_database_engine(os.environ["GROCERY_DATABASE_URL"])
    create_schema(engine)
    engine.dispose()
    original_facts = personal_source_facts.load_retained_facts

    def public_facts(prepared):
        with span("public_fact_load"):
            return original_facts(prepared, database="/srv/app/var/grocery/grocery_data.sqlite")

    personal_source_facts.load_retained_facts = public_facts
    wrap_sync(PersonalPlanner, "__init__", "request_init_and_data")
    wrap_sync(PersonalPlanner, "create", "planner_create")
    wrap_sync(PlanStore, "create", "storage_create")
    wrap_sync(PlanStore, "append", "storage_append")
    wrap_sync(PersonalStore, "read", "storage_read")
    wrap_async(fastapi.routing, "serialize_response", "response_serialization")
    server = uvicorn.Server(
        uvicorn.Config(
            TimingMiddleware(app), host="127.0.0.1", port=8000, log_level="error", access_log=False
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        if not thread.is_alive():
            raise RuntimeError("App startup failed")
        time.sleep(0.01)
    startup = time.perf_counter() - START
    wrap_async(app.state.planner_admission._capacity, "acquire", "admission_queue")
    wrap_async(app.state.planner_admission._state_lock, "acquire", "admission_lock")
    output = {"startup_seconds": startup, "plan_prewarm": False, "network": "none"}
    try:
        with guest() as client:
            cold, saved = submit(client)
            output["process_cold_to_http_result_seconds"] = time.perf_counter() - START
            output["first_http"] = cold
            output["request_cold_http"] = []
            for run in range(3):
                with guest() as fresh:
                    measured, _ = submit(fresh)
                    output["request_cold_http"].append(measured)
                    print(json.dumps({"request_cold_run": run + 1, **measured}), flush=True)
            warm, repeated = submit(client)
            output["warm_http"] = warm
            assert saved["plan_id"] != repeated["plan_id"]
            output["warm_has_new_owned_plan_id"] = True
        print(json.dumps({k: v for k, v in output.items()}), flush=True)
        with guest() as one, guest() as two, guest() as probe, ThreadPoolExecutor(2) as workers:
            started = time.perf_counter()
            futures = [workers.submit(submit, one), workers.submit(submit, two)]
            health, searches = [], []
            for _ in range(3):
                time.sleep(2)
                for path in ("/health", "/ready"):
                    t = time.perf_counter()
                    response = probe.get(path)
                    health.append(
                        {
                            "path": path,
                            "seconds": time.perf_counter() - t,
                            "status": response.status_code,
                        }
                    )
                    response.raise_for_status()
                t = time.perf_counter()
                response = probe.post(
                    "/api/product-search", json={"query": "mjölk", "postal_code": "22350"}
                )
                searches.append(
                    {"seconds": time.perf_counter() - t, "status": response.status_code}
                )
                response.raise_for_status()
            results = [f.result() for f in futures]
            assert results[0][1]["plan_id"] != results[1][1]["plan_id"]
            assert one.get("/api/plans/" + results[1][1]["plan_id"]).status_code in {403, 404}
            output["concurrency"] = {
                "plans": [r[0] for r in results],
                "wave_seconds": time.perf_counter() - started,
                "health": health,
                "search": searches,
                "owner_isolation": True,
            }
        # All requests have completed; no worker can still update these counters.
        output["admission"] = {
            "peak_active": app.state.planner_admission._peak_active,
            "peak_queued": app.state.planner_admission._peak_queued,
            "remaining_in_flight": len(app.state.planner_admission._in_flight),
        }
        assert output["admission"]["peak_active"] == 1
        assert output["admission"]["remaining_in_flight"] == 0
        output["exclusive_http_stages"] = traces
        output["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        Path("/output/http.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(json.dumps(output), flush=True)
    finally:
        server.should_exit = True
        thread.join(timeout=15)
        assert not thread.is_alive(), "Uncontrolled ASGI worker"


if __name__ == "__main__":
    main()
