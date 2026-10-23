"""Acceptance matrix behind combined_performance_probe --matrix.

Uses existing PersonalPlanner, frozen artifact/facts and PerformanceTrace.
No production access, completed-menu cache, source collection or private state.
Run each case in a fresh process for comparable cold/warm measurements.
"""
from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import math
import os
import platform
import pstats
import socket
import time
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models import PlanRequest
from app.services.performance_trace import activate_performance_trace
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

CASES = {
    "standard": {"meals": [{"count": 5, "servings": 4}]},
    "protein40": {"meals": [{"count": 5, "servings": 4, "limits": {"min_protein_g": 40}}]},
    "all-macros": {"meals": [{"count": 5, "servings": 4, "limits": {
        "min_protein_g": 40, "max_protein_g": 90, "min_carbs_g": 10,
        "max_carbs_g": 130, "min_fat_g": 1, "max_fat_g": 60, "max_kcal": 1000}}]},
    "vegan": {"meals": [{"count": 3, "servings": 4, "diet": "vegan",
                         "limits": {"min_protein_g": 20}}]},
    "distribution": {"meals": [{"count": 5, "servings": 4,
        "distribution": {"chicken": 1, "fish": 1, "meat": 1, "vegetarian": 2},
        "limits": {"min_protein_g": 25}}]},
    "organic-share": {"organic_percent": 20, "meals": [{"count": 3, "servings": 4}]},
    "breakfast-snack-weight": {"meals": [
        {"meal_type": "breakfast", "count": 1, "servings": 2,
         "limits": {"min_weight_g": 100, "max_weight_g": 600},
         "recipe_choices": {"max_ingredients": 8}},
        {"meal_type": "snack", "count": 1, "servings": 2,
         "limits": {"min_weight_g": 100, "max_weight_g": 400},
         "recipe_choices": {"max_ingredients": 8}}]},
    "allergy-milk": {"profile": {"allergies": ["mjölk"]},
                     "meals": [{"count": 1, "servings": 4}]},
    "organic-animals": {"organic_animals": True, "meals": [{"count": 1, "servings": 4}]},
    "impossible-protein": {"meals": [{"count": 1, "servings": 4,
                                     "limits": {"min_protein_g": 300}}]},
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


# Search settings a full-library reference must state explicitly. A report
# without every key (for example one written before seed_variant_shortlist
# existed, which still kept four variants per base) is not a reference.
FULL_LIBRARY_REFERENCE_CONTRACT = "smako-full-library-reference-v5"
FULL_LIBRARY_SEARCH_LIMITS = {
    "seed": 0, "refinement": 0, "seed_variant_shortlist": False, "substitution": 0,
    "merge_generations": False, "substitution_screen_margin": -1.0, "substitution_slot_limit": 0,
}


def full_library_search_limits(settings):
    """Settings for a full-library reference: whole qualified library, no shortlist."""
    return replace(settings, library_seed_pool_limit=0, library_refinement_pool_limit=0,
                   library_seed_variant_shortlist=False, library_substitution_pool_limit=0,
                   library_merge_generations=False, library_substitution_screen_margin=-1.0,
                   library_substitution_slot_limit=0)


def validate_full_library_reference(reference, inputs):
    """Reject anything but an explicit full-library reference over the same inputs.

    Code versions may differ intentionally (method_signature is not compared),
    but the reference's search settings must always be explicit and exact.
    """
    if reference.get("schema") != "smako-planner-acceptance-v1":
        raise ValueError(f"unknown report schema {reference.get('schema')!r}")
    if reference.get("inputs") != inputs:
        raise ValueError("reference inputs differ")
    if reference.get("uncapped") is not True:
        raise ValueError("reference is not an --uncapped run")
    contract = reference.get("reference_contract")
    if contract is not None and contract != FULL_LIBRARY_REFERENCE_CONTRACT:
        raise ValueError(f"unknown reference contract {contract!r}")
    limits = reference.get("search_limits")
    if not isinstance(limits, dict):
        raise ValueError("reference has no search_limits")  # noqa: TRY004 - rejected report, not a caller bug
    for key, expected in FULL_LIBRARY_SEARCH_LIMITS.items():
        if key not in limits:
            raise ValueError(f"reference search_limits lacks {key!r}; older reports are not accepted")
        value = limits[key]
        # bool is an int subclass: seed=False or shortlist=0 is not explicit.
        if type(value) is not type(expected) or value != expected:
            raise ValueError(f"reference search_limits[{key!r}] is {value!r}, expected {expected!r}")
    if not reference.get("records"):
        raise ValueError("reference has no records")


def matrix_request(base, case):
    # Store scope, price mode and memberships come from the frozen base.
    body = deepcopy(base)
    body["personal"] = {"allow_nutrition_estimates": True, "pantry_revision": 0,
                        **deepcopy(CASES[case])}
    body["recipes"] = sum(m["count"] for m in body["personal"]["meals"]
                          if m.get("meal_type", "dinner") == "dinner")
    return PlanRequest.model_validate(body)


def cap_regression(capped, uncapped):
    """'ok' unless the bounded search lost a cheaper (or any) menu.

    The search caps are heuristics; this compares one profile's capped result
    with the same inputs searched over the whole qualified library.
    """
    if capped["outcome"] != uncapped["outcome"]:
        return f"outcome {capped['outcome']} != uncapped {uncapped['outcome']}"
    if capped["outcome"] != "PASS":
        same = (capped.get("code"), capped.get("stage")) == (uncapped.get("code"), uncapped.get("stage"))
        return "ok" if same else "failure differs from uncapped"
    if round(capped["paid"], 2) > round(uncapped["paid"], 2):
        return f"capped pays {capped['paid']:.2f} kr, uncapped {uncapped['paid']:.2f} kr"
    return "ok"


def quality(plan, request):
    """Check the result, not a hardcoded recipe selection or basket price."""
    from app.services.diet_policy import recipe_respects_diet
    from app.services.personal_policy import merged_profile

    audit = plan.personal.checks["checkout_audit"]
    assert audit["passed"] and audit["totals_reconciled"] and not audit["deficits"]
    assert audit["unknown_quantities"] == 0
    assert plan.data.live_chain_requests == 0
    assert len(plan.personal.slots) == sum(m.count for m in request.personal.meals)
    assert plan.portions == sum(m.count * m.servings for m in request.personal.meals)
    assert plan.optimized_basket.store_count <= request.max_stores
    chosen = {p["store_id"] for item in audit["items"] for p in item["selected_products"]}
    if request.allowed_store_ids:
        assert chosen <= set(request.allowed_store_ids)
    meals = {m.meal_type: m for m in request.personal.meals}
    nutrients = {n["slot_id"]: n for n in plan.personal.checks["nutrition"]}
    for slot in plan.personal.slots:
        meal = meals[slot.meal_type]
        profile = merged_profile(request.personal.profile, meal.profile)
        assert recipe_respects_diet(slot.recipe, preference=meal.diet,
                                   avoid_ingredients=profile.exclusions + profile.allergies)
        for key, bound in meal.limits.model_dump().items():
            if bound is None:
                continue
            direction, nutrient = key.split("_", 1)
            value = nutrients[slot.id]["values"][nutrient]
            assert math.isfinite(value)
            assert value + 1e-8 >= bound if direction == "min" else value <= bound + 1e-8
    for meal in request.personal.meals:
        counts = Counter(row["protein"] for row in plan.personal.checks["distribution"]
                         if row["meal_type"] == meal.meal_type)
        assert all(counts[kind] == count for kind, count in meal.distribution.items())
    if request.personal.profile.allergies or any(m.profile.allergies for m in request.personal.meals if m.count):
        assert plan.personal.checks["allergy"] == "VERIFIED"
    if request.personal.organic_animals or any(m.organic_animals for m in request.personal.meals if m.count):
        assert plan.personal.checks["organic_animals"] == "VERIFIED"
    eco = plan.personal.checks.get("organic_cost_percent")
    if request.personal.organic_percent:
        assert eco is not None and eco + 1e-8 >= request.personal.organic_percent
    # Full recipes, purchase terms, source evidence and portion checks must be
    # identical before/after an optimization, excluding diagnostic timings.
    signature = digest({
        "recipes": [r.model_dump(mode="json") for r in plan.recipes],
        "basket": plan.optimized_basket.model_dump(mode="json"),
        "nutrition": plan.personal.checks["nutrition"],
        "audit": audit,
        "allocations": [x.model_dump(mode="json") for x in plan.personal.allocations],
    })
    return {"paid": plan.optimized_basket.total, "audit_passed": True,
            "unknown_quantities": 0, "recipes": [r.name for r in plan.recipes],
            "distinct_recipes": len({r.name for r in plan.recipes}),
            "week_distribution": plan.personal.checks.get("week_distribution"),
            "search_outcome": plan.personal.checks.get("search_outcome"),
            "nutrition": [{k: v for k, v in n.items() if k in ("slot_id", "status", "values")}
                          for n in nutrients.values()],
            "organic_cost_percent": eco, "semantic_sha256": signature,
            "purchase_surplus": plan.personal.checks.get("purchase_surplus"),
            "joint_refinement": [r for r in plan.personal.checks.get("planning_diagnostics", {}).get("search", [])
                                 if r.get("library_phase") == "joint_refinement"]}


def summarize(records):
    plain = [r for r in records if not r["profiled"]]
    times = sorted(r["wall_seconds"] for r in plain)
    # This is a sample percentile, never a population/load-test claim.
    return {"samples": len(plain), "successful": sum(r["outcome"] == "PASS" for r in plain),
            "sample_p95_seconds": times[math.ceil(.95 * len(times)) - 1] if times else None,
            "p95_capacity_claim": False, "queue_seconds": None,
            "queue_measurement": "not measured: direct offline planner",
            "targets_seconds": {"ordinary": 30, "sample_p95": 60},
            "within_30_seconds": sum(t <= 30 for t in times),
            "within_60_seconds": sum(t <= 60 for t in times),
            "successful_within_30_seconds": sum(r["outcome"] == "PASS" and r["wall_seconds"] <= 30 for r in plain),
            "successful_within_60_seconds": sum(r["outcome"] == "PASS" and r["wall_seconds"] <= 60 for r in plain)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matrix", action="store_true")
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--preparation-cache-root", type=Path,
                   help="Explicit reusable disk preparation cache; default isolates each profile/label")
    p.add_argument("--label", default="baseline")
    p.add_argument("--matrix-case", choices=CASES, required=True)
    p.add_argument("--repeat", type=int, default=2)
    p.add_argument("--profile", action="store_true")
    p.add_argument("--baseline", type=Path)
    p.add_argument("--uncapped", action="store_true",
                   help="Reference run: seed and refinement search over the whole qualified library")
    p.add_argument("--uncapped-reference", type=Path,
                   help="Report from an --uncapped run; fail if the capped search pays more")
    p.add_argument("--substitution-limit", type=int,
                   help="Override LIBRARY_SUBSTITUTION_POOL_LIMIT for this run (0 = every new recipe)")
    p.add_argument("--screen-margin", type=float,
                   help="library_substitution_screen_margin (negative turns the screen off)")
    p.add_argument("--slot-limit", type=int, help="library_substitution_slot_limit (0: off)")
    p.add_argument("--substitution-pool", type=int,
                   help="library_substitution_pool_limit for experiments (0: whole generation)")
    p.add_argument("--merge-generations", action="store_true",
                   help="Search every newer pack as one cohort (library_merge_generations=True)")
    p.add_argument("--per-pack-generations", action="store_true",
                   help="Search each published pack as its own cohort (library_merge_generations=False)")
    p.add_argument("--reference-preparation", action="store_true",
                   help="Bypass only new shared preparation; retain ordinary planner and audits")
    p.add_argument("--prepared-startup", action="store_true",
                   help="Measure the new serving startup preparation separately before first request")
    args = p.parse_args()
    if args.repeat < 1 or not args.label.replace("-", "").replace("_", "").isalnum():
        p.error("positive repeat and simple label required")
    if args.substitution_limit is not None and (args.substitution_limit < 0 or args.uncapped):
        p.error("--substitution-limit must be >= 0 and cannot be combined with --uncapped")
    args.output.mkdir(parents=True, exist_ok=True)
    # Separate bounded cache roots; don't clear any existing deployment cache.
    # Profiles sharing an output folder must still start with independent
    # disk preparation; otherwise later cold-process samples inherit the
    # previous profile's artifacts and cannot be compared to fresh baselines.
    preparation_root = args.preparation_cache_root or args.output / f"{args.label}-{args.matrix_case}-prepared"
    os.environ["RECIPE_PREPARATION_CACHE_ROOT"] = str(preparation_root)
    preparation_disk_present = preparation_root.exists()
    manifest = json.loads((args.inputs / "matrix-inputs.json").read_bytes())
    files = {}
    for name in ("combined-prices.json", "combined-facts.json", "combined-request.json"):
        raw = (args.inputs / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == manifest["sha256"][name], name
        files[name] = raw
    now = datetime.fromisoformat(manifest["now"])
    assert now.utcoffset() is not None
    started = time.perf_counter()
    prepared = PreparedPriceUniverseArtifact.model_validate_json(files["combined-prices.json"]).restore()
    raw = json.loads(files["combined-facts.json"])
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
    assert facts.version == raw["facts_version"]
    request = matrix_request(json.loads(files["combined-request.json"]), args.matrix_case)
    inputs = {"sha256": manifest["sha256"], "now": now.isoformat(),
              "request_sha256": digest(request.model_dump(mode="json")),
              "facts_version": facts.version, "universe_id": prepared.universe.universe_id}
    baseline = json.loads(args.baseline.read_bytes()) if args.baseline else None
    if baseline:
        assert baseline["inputs"] == inputs, "Baseline inputs differ"
    settings = Settings(complete_recipes_enabled=True, price_provider="own")
    if args.substitution_limit is not None:
        settings = replace(settings, library_substitution_pool_limit=args.substitution_limit)
    if args.screen_margin is not None:
        settings = replace(settings, library_substitution_screen_margin=args.screen_margin)
    if args.slot_limit is not None:
        settings = replace(settings, library_substitution_slot_limit=args.slot_limit)
    if args.substitution_pool is not None:
        settings = replace(settings, library_substitution_pool_limit=args.substitution_pool)
    if args.merge_generations:
        settings = replace(settings, library_merge_generations=True)
    if args.per_pack_generations:
        settings = replace(settings, library_merge_generations=False)
    if args.uncapped:
        settings = full_library_search_limits(settings)
    uncapped = json.loads(args.uncapped_reference.read_bytes()) if args.uncapped_reference else None
    if uncapped is not None:
        try:
            validate_full_library_reference(uncapped, inputs)
        except ValueError as exc:
            p.error(f"--uncapped-reference rejected: {exc}")
    records = []
    report = {"schema": "smako-planner-acceptance-v1", "case": args.matrix_case,
              "inputs": inputs, "label": args.label, "records": records,
              "environment": {"python": platform.python_version(), "platform": platform.platform(),
                              "logical_cpus": os.cpu_count()},
              "load_seconds": time.perf_counter() - started, "network": "blocked",
              "historical_replay": True, "shared_preparation": not args.reference_preparation,
              "preparation_cache_explicit": args.preparation_cache_root is not None,
              "preparation_disk_present_at_start": preparation_disk_present,
              "uncapped": args.uncapped,
              "search_limits": {"seed": settings.library_seed_pool_limit,
                                "refinement": settings.library_refinement_pool_limit,
                                "seed_variant_shortlist": settings.library_seed_variant_shortlist,
                                "substitution": settings.library_substitution_pool_limit,
                                "merge_generations": settings.library_merge_generations,
                                "substitution_screen_margin": settings.library_substitution_screen_margin,
                                "substitution_slot_limit": settings.library_substitution_slot_limit}}
    if args.uncapped:
        assert report["search_limits"] == FULL_LIBRARY_SEARCH_LIMITS, report["search_limits"]
        report["reference_contract"] = FULL_LIBRARY_REFERENCE_CONTRACT
    from app.services.meal_prepared_artifacts import STATS, method_signature

    from backend.scripts.benchmark_beta_capacity import _process_snapshot
    report["method_signature"] = method_signature()
    report["startup_preparation_seconds"] = 0.0
    if args.prepared_startup and not args.reference_preparation:
        from app.services.meal_prepared_artifacts import prepare_ingredient_search
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")):
            startup = time.perf_counter()
            prepare_ingredient_search(prepared)
            report["startup_preparation_seconds"] = time.perf_counter() - startup
    report["prepared_startup"] = args.prepared_startup
    for iteration in range(args.repeat):
        state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
        before_state = deepcopy(state)
        before_stats = dict(STATS)
        profiler = cProfile.Profile() if args.profile else None
        start, cpu = time.perf_counter(), time.process_time()
        with (
            patch.object(socket.socket, "connect", side_effect=AssertionError("Network forbidden")),
            activate_performance_trace() as trace,
            ExitStack() as bypass,
        ):
            if args.reference_preparation:
                from app.services.ingredient_normalizer import (
                    CANONICAL_ALIASES,
                    canonicalize_ingredient_name,
                )
                from app.services.product_search import ProductSearchRequest

                def original_search(universe, name, *, complete):
                    aliases = ((name, *CANONICAL_ALIASES.get(canonicalize_ingredient_name(name), ()))
                               if complete else (name,))
                    index = universe.product_search_index
                    return frozenset(i for alias in dict.fromkeys(aliases)
                                     for key in index.retrieve(ProductSearchRequest(query=alias))[0]
                                     for i in index.groups[key])

                bypass.enter_context(patch("app.services.meal_prepared_artifacts.ingredient_search_positions", original_search))
            if profiler:
                profiler.enable()
            try:
                planner = PersonalPlanner(request, settings, prepared, state, facts=facts, now=now)
                plan = planner.create()
                elapsed = time.perf_counter() - start
                cpu_elapsed = time.process_time() - cpu
                if profiler:
                    profiler.disable()
                row = {"outcome": "PASS", **quality(plan, request)}
            except PolicyConflict as exc:
                elapsed = time.perf_counter() - start
                cpu_elapsed = time.process_time() - cpu
                row = {"outcome": "BLOCKED", "code": exc.code, "stage": exc.stage,
                       "reason": str(exc), "diagnostics": getattr(exc, "diagnostics", None)}
            finally:
                if profiler:
                    profiler.disable()
        row.update(iteration=iteration, cache_mode="process-cold" if iteration == 0 else "process-warm",
                   profiled=args.profile, wall_seconds=elapsed, cpu_seconds=cpu_elapsed,
                   verification_seconds=time.perf_counter() - start - elapsed,
                   trace=asdict(trace.snapshot()), preparation_stats={k: STATS[k]-before_stats[k] for k in STATS})
        try:
            memory = _process_snapshot(os.getpid())
            row.update(rss_bytes=memory.rss_bytes, process_peak_rss_bytes=memory.peak_rss_bytes)
        except OSError:
            row.update(rss_bytes=None, process_peak_rss_bytes=None)
        assert state == before_state
        if baseline:
            old = baseline["records"][min(iteration, len(baseline["records"])-1)]
            assert row["outcome"] == old["outcome"], "Outcome changed"
            if row["outcome"] == "PASS":
                assert row["semantic_sha256"] == old["semantic_sha256"], "Result changed"
            else:
                assert (row["code"], row["stage"]) == (old["code"], old["stage"]), "Failure changed"
            row["baseline_equivalent"] = True
        if uncapped:
            row["uncapped_check"] = cap_regression(row, uncapped["records"][min(iteration, len(uncapped["records"])-1)])
            assert row["uncapped_check"] == "ok", row["uncapped_check"]
        records.append(row)
        report["summary"] = summarize(records)
        path = args.output / f"{args.label}-{args.matrix_case}.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
        if profiler:
            profiler.dump_stats(args.output / f"{args.label}-{args.matrix_case}-{iteration}.prof")
            with (args.output / f"{args.label}-{args.matrix_case}-{iteration}-profile.txt").open("w", encoding="utf8") as stream:
                pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(45)
                pstats.Stats(profiler, stream=stream).sort_stats("tottime").print_stats(45)
        print(json.dumps({k: row[k] for k in ("iteration", "outcome", "wall_seconds")}), flush=True)


if __name__ == "__main__":
    main()
