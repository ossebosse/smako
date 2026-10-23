"""Offline shared-process matrix using the ordinary planner and final audit.

Run with Python 3.12 and PYTHONPATH=<checkout>/backend:<checkout>. Mount the
chosen author-imported recipe library at backend/app/data/recipes. This helper
does not fetch data or alter a library. Each city/library uses a fresh process;
each plan uses an empty synthetic user's state. Use the acceptance CLI for
separate-process cold/warm-disk measurements.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import socket
import time
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.services.library_search_cohorts import MERGED_SEARCH_CONTRACT
from app.services.meal_prepared_artifacts import STATS, method_signature
from app.services.performance_trace import activate_performance_trace
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_library import library_version

from backend.scripts.benchmark_beta_capacity import _process_snapshot
from backend.scripts.planner_acceptance_matrix import (
    FULL_LIBRARY_REFERENCE_CONTRACT,
    digest,
    full_library_search_limits,
    matrix_request,
    quality,
)

CASES = ("standard", "protein40", "all-macros", "vegan", "distribution",
         "organic-share", "breakfast-snack-weight")


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--size", required=True, type=int)
    parser.add_argument("--repeat", default=1, type=int)
    parser.add_argument("--cases", nargs="+", choices=CASES, default=CASES)
    parser.add_argument("--arms", nargs="+", choices=("main", "geo16", "geo32", "geo48", "uncapped"))
    parser.add_argument("--preparation-cache-root", required=True, type=Path)
    parser.add_argument("--execution-environment", required=True)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    args.output.mkdir(parents=True, exist_ok=True)
    os.environ["RECIPE_PREPARATION_CACHE_ROOT"] = str(args.preparation_cache_root)
    start = time.perf_counter()
    manifest = json.loads((args.inputs / "matrix-inputs.json").read_bytes())
    files = {}
    for name in ("combined-prices.json", "combined-facts.json", "combined-request.json"):
        raw = (args.inputs / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest["sha256"][name], name
        files[name] = raw
    prepared = PreparedPriceUniverseArtifact.model_validate_json(files.pop("combined-prices.json")).restore()
    raw = json.loads(files.pop("combined-facts.json"))
    facts = FactsCollection({tuple(key): ProductFacts(**value) for key, value in raw["facts"]})
    assert facts.version == raw["facts_version"]
    base = json.loads(files["combined-request.json"])
    del files, raw
    clock = datetime.fromisoformat(manifest["now"])
    assert clock.utcoffset() is not None
    signature, library = method_signature(), library_version()
    write(args.output / f"L{args.size}-startup.json", {
        "load_seconds": time.perf_counter() - start, "method_signature": signature,
        "library_version": library, "process": asdict(_process_snapshot(os.getpid())),
    })
    defaults = ["main", "geo16", "geo32", "geo48"] + (["uncapped"] if args.size == 262 else [])
    arms = args.arms or defaults
    sample = 0
    for case in args.cases:
        request = matrix_request(base, case)
        settings = Settings(complete_recipes_enabled=True, price_provider="own", library_merge_generations=False)
        inputs = {"sha256": manifest["sha256"], "now": clock.isoformat(),
                  "request_sha256": digest(request.model_dump(mode="json")),
                  "facts_version": facts.version, "universe_id": prepared.universe.universe_id}
        for arm in arms:
            selected = settings
            if arm.startswith("geo"):
                selected = replace(settings, library_merge_generations=True,
                                   library_substitution_pool_limit=0, library_substitution_slot_limit=int(arm[3:]))
            elif arm == "uncapped":
                selected = full_library_search_limits(settings)
            limits = {name: getattr(selected, attribute) for name, attribute in {
                "seed": "library_seed_pool_limit", "refinement": "library_refinement_pool_limit",
                "seed_variant_shortlist": "library_seed_variant_shortlist", "substitution": "library_substitution_pool_limit",
                "merge_generations": "library_merge_generations", "substitution_screen_margin": "library_substitution_screen_margin",
                "substitution_slot_limit": "library_substitution_slot_limit",
            }.items()}
            label = f"L{args.size}-{arm}"
            target = args.output / f"{label}-{case}.json"
            report = {"schema": "smako-planner-acceptance-v1", "case": case, "label": label,
                      "inputs": inputs, "method_signature": signature, "library_version": library,
                      "search_limits": limits, "uncapped": arm == "uncapped", "records": [],
                      "network": "blocked", "historical_replay": True,
                      "measurement_protocol": "one process per city/library; shared public preparation; new empty user per call",
                      "execution_environment": args.execution_environment, "platform": platform.platform()}
            if arm == "uncapped":
                report["reference_contract"] = FULL_LIBRARY_REFERENCE_CONTRACT
            if arm.startswith("geo"):
                report["merged_search_contract"] = dict(MERGED_SEARCH_CONTRACT)
            if target.exists():
                prior = json.loads(target.read_bytes())
                if (all(prior.get(key) == report[key] for key in ("inputs", "method_signature", "library_version", "search_limits"))
                        and len(prior.get("records", [])) == args.repeat):
                    print(json.dumps({"reuse": label, "case": case}), flush=True)
                    continue
                raise ValueError(f"Refusing to overwrite incompatible evidence: {target}")
            for iteration in range(args.repeat):
                state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
                before, before_stats = deepcopy(state), dict(STATS)
                print(json.dumps({"start": label, "case": case, "iteration": iteration}), flush=True)
                started, cpu = time.perf_counter(), time.process_time()
                with patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")), activate_performance_trace() as trace:
                    planner = PersonalPlanner(request, selected, prepared, state, facts=facts, now=clock)
                    try:
                        plan = planner.create()
                        elapsed = time.perf_counter() - started
                        row = {"outcome": "PASS", **quality(plan, request)}
                        del plan
                    except PolicyConflict as exc:
                        elapsed = time.perf_counter() - started
                        row = {"outcome": "BLOCKED", "code": exc.code, "stage": exc.stage, "reason": str(exc)}
                memory = _process_snapshot(os.getpid())
                row.update(iteration=iteration, grid_process_sample=sample,
                           cache_mode="process-first-plan" if sample == 0 else "process-shared-public-preparation",
                           profiled=False, wall_seconds=elapsed, cpu_seconds=time.process_time() - cpu,
                           rss_bytes=memory.rss_bytes, process_peak_rss_bytes=memory.peak_rss_bytes,
                           trace=asdict(trace.snapshot()),
                           preparation_stats={key: STATS[key] - before_stats.get(key, 0) for key in STATS})
                cgroup = Path("/sys/fs/cgroup/memory.peak")
                if cgroup.exists():
                    row["cgroup_peak_bytes"] = int(cgroup.read_text())
                assert state == before
                report["records"].append(row)
                sample += 1
                write(target, report)
                print(json.dumps({"label": label, "case": case, "outcome": row["outcome"],
                                  "paid": row.get("paid"), "seconds": elapsed,
                                  "peak_rss_bytes": memory.peak_rss_bytes}), flush=True)
                del planner
                gc.collect()
    write(args.output / f"L{args.size}-complete.json", {
        "samples": sample, "method_signature": signature, "library_version": library,
        "cases": args.cases, "arms": arms, "repeat": args.repeat,
    })


if __name__ == "__main__":
    main()
