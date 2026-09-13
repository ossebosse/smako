"""Offline, reproducible combined-plan benchmark; never opens user databases.

Run inside the release image with --network none. Input directory contains the
retained combined-prices/facts/request.json and combined-runtime.json. Timings
include a fresh PersonalPlanner (no request-local search state) on every run.
"""

import argparse
import cProfile
import hashlib
import json
import pstats
import signal
import socket
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from pathlib import Path
from unittest.mock import patch

try:
    import resource
except ImportError:  # Diagnostic fixtures may also run on the Windows workspace.
    resource = None


def main():
    process_start = time.perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=Path("/inputs"))
    parser.add_argument("--output", type=Path, default=Path("/output"))
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--fixed", action="store_true")
    parser.add_argument("--case", choices=["A", "B", "C", "D"], default="D")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    from app.config import get_settings
    from app.models import PlanRequest
    from app.services.personal_planner import POLICY_VERSION, PersonalPlanner
    from app.services.personal_policy import ProductFacts
    from app.services.personal_source_facts import FactsCollection
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

    loaded = time.perf_counter()
    price_bytes = (args.inputs / "combined-prices.json").read_bytes()
    prepared = PreparedPriceUniverseArtifact.model_validate_json(price_bytes).restore()
    raw = json.loads((args.inputs / "combined-facts.json").read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
    facts.version = raw["facts_version"]
    now = datetime.fromisoformat(
        json.loads((args.inputs / "combined-runtime.json").read_bytes())["now"]
    )
    base = json.loads((args.inputs / "combined-request.json").read_bytes())
    base["personal"]["allow_nutrition_estimates"] = True
    for n, meal in enumerate(base["personal"]["meals"]):
        meal["count"] = 5 if args.case == "D" or args.case == ("A", "B", "C")[n] else 0
    base["recipes"] = base["personal"]["meals"][0]["count"]
    if args.fixed:
        historical = json.loads((args.inputs / "combined-runtime.json").read_bytes())
        base["personal"]["slots"] = historical["cases"][args.case]["plan"]["personal"]["slots"]
    settings = get_settings()
    load_seconds = time.perf_counter() - loaded
    records = []
    stages, calls, stack = Counter(), Counter(), []

    @contextmanager
    def stage(name):
        entry = [name, time.perf_counter(), 0.0]
        stack.append(entry)
        try:
            yield
        finally:
            elapsed = time.perf_counter() - entry[1]
            stack.pop()
            if stack:
                stack[-1][2] += elapsed
            stages[name] += elapsed - entry[2]
            calls[name] += 1

    def observe(cls, method, label):
        original = getattr(cls, method)

        @wraps(original)
        def measured(*pos, **kw):
            name = label(pos) if callable(label) else label
            with stage(name):
                return original(*pos, **kw)

        setattr(cls, method, measured)

    if args.profile:
        from app.services.basket_optimizer import BasketOptimizer

        for method, label in (
            ("__init__", "request_data_and_init"),
            ("_candidates", lambda pos: "candidates_" + pos[1].meal_type),
            ("resolve", "product_qualification"),
            ("nutrition_evidence", "nutrition_evidence"),
            ("_check_nutrition", "nutrition_validation"),
            ("basket", "joint_basket_preparation_and_audit"),
            ("_qualified_nutrition_basket", "nutrition_product_search"),
            ("_create", "meal_search_and_result"),
        ):
            observe(PersonalPlanner, method, label)
        observe(BasketOptimizer, "optimize", "stores_and_package_pricing")

    for run in range(args.repeat):
        request = PlanRequest.model_validate(base)
        state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
        state_before = json.dumps(state, sort_keys=True)
        profiler = cProfile.Profile() if args.profile else None
        if profiler and hasattr(signal, "SIGUSR1"):

            def snapshot(_signum, _frame, profiler=profiler):
                profiler.dump_stats(args.output / f"{args.label}-live.prof")
                (args.output / f"{args.label}-live.json").write_text(
                    json.dumps(
                        {"exclusive_stage_seconds": dict(stages), "calls": dict(calls)}, indent=2
                    ),
                    encoding="utf8",
                )
                # cProfile.dump_stats disables collection via create_stats.
                profiler.enable()

            signal.signal(signal.SIGUSR1, snapshot)
        started, cpu = time.perf_counter(), time.process_time()
        if profiler:
            profiler.enable()
        with patch.object(socket.socket, "connect", side_effect=AssertionError("External call")):
            planner = PersonalPlanner(request, settings, prepared, state, facts=facts, now=now)
            initialized = time.perf_counter()
            result = planner.create()
        completed, cpu_end = time.perf_counter(), time.process_time()
        if profiler:
            profiler.disable()
            profiler.dump_stats(args.output / f"{args.label}-{run + 1}.prof")
            with (args.output / f"{args.label}-{run + 1}-profile.txt").open(
                "w", encoding="utf8"
            ) as stream:
                stats = pstats.Stats(profiler, stream=stream)
                stats.sort_stats("cumulative").print_stats()
                stats.sort_stats("tottime").print_stats()
        serialized = time.perf_counter()
        plan = result.model_dump(mode="json")
        plan_json = json.dumps(plan, ensure_ascii=False, indent=2)
        serialization_seconds = time.perf_counter() - serialized
        assert json.dumps(state, sort_keys=True) == state_before
        assert result.data.live_chain_requests == 0
        assert len(result.personal.slots) == sum(m.count for m in request.personal.meals)
        assert result.portions == sum(m.count * m.servings for m in request.personal.meals)
        assert result.optimized_basket.store_count <= request.max_stores
        meals = {m.meal_type: m for m in request.personal.meals}
        for row in result.personal.checks["nutrition"]:
            slot = next(s for s in result.personal.slots if s.id == row["slot_id"])
            assert row["values"]["protein_g"] >= meals[slot.meal_type].limits.min_protein_g
        record = {
            "run": run + 1,
            "profiled": args.profile,
            "case": args.case,
            "request_cold_seconds": completed - started,
            "planner_init_seconds": initialized - started,
            "create_seconds": completed - initialized,
            "cpu_seconds": cpu_end - cpu,
            "serialization_seconds": serialization_seconds,
            "process_to_result_seconds": completed - process_start if run == 0 else None,
            "peak_rss_mib": (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 if resource else None
            ),
            "cost": result.optimized_basket.total,
            "exclusive_stage_seconds": dict(stages),
            "stage_calls": dict(calls),
            "diagnostics": result.personal.checks["planning_diagnostics"],
        }
        records.append(record)
        (args.output / f"{args.label}-{run + 1}-plan.json").write_text(plan_json, encoding="utf8")
        output = {
            "price_version": prepared.universe.universe_id,
            "price_artifact_sha256": hashlib.sha256(price_bytes).hexdigest(),
            "facts_version": facts.version,
            "reference_version": planner.reference_version,
            "policy_version": POLICY_VERSION,
            "request": request.model_dump(mode="json"),
            "now": now.isoformat(),
            "load_seconds": load_seconds,
            "network": "none",
            "seed": "deterministic",
            "pantry": state,
            "records": records,
        }
        (args.output / f"{args.label}.json").write_text(
            json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(
            json.dumps(
                {
                    k: v
                    for k, v in record.items()
                    if k not in {"diagnostics", "exclusive_stage_seconds", "stage_calls"}
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
