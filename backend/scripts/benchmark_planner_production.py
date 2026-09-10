"""Benchmark the active production planner against an immutable economic golden.

The public command orchestrates isolated worker processes so the latency names
mean exactly what they say:

* PROCESS COLD: new Python process + verified PriceUniverse load + first plan;
* REQUEST COLD: PriceUniverse resident, first unseen plan/cache key;
* WARM: identical request after an unmeasured seed plan in the same process.

All planning is guarded by the same fail-closed provider used by the golden
suite. Reports contain repository-relative artifact references and exception
types only; environment values, credentials and raw provider payloads are never
serialized.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter, process_time
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
for import_root in (BACKEND_DIR, REPOSITORY_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.config import Settings
from app.models import PlanRequest
from app.services import meal_plan_optimizer as optimizer_module
from app.services.meal_plan_optimizer import MealPlanService
from app.services.performance_trace import (
    activate_performance_trace,
    performance_span,
)
from app.services.price_universe_runtime import PreparedPriceUniverseManager
from app.services.pricing_projection_prewarm import precompute_pricing_semantics
from scripts.benchmark_planner_golden import (
    OfflineSentinelProvider,
    _plan_report,
    _repository_relative,
)

from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)

_REPORT_SCHEMA = "production-planner-benchmark-v1"
_WORKER_SCHEMA = "production-planner-benchmark-worker-v1"
_DEFAULT_GOLDEN_ROOT = Path("reports/planner-performance/golden")
_DEFAULT_REPORT_ROOT = Path("reports/planner-performance/benchmarks")
_STANDARD_SCENARIO = "balanced_max2_no_memberships"
_LEGACY_GOLDEN_REQUEST_FIELDS = frozenset(
    {
        "postal_code",
        "recipes",
        "servings",
        "max_stores",
        "diversity_mode",
        "diet_preference",
        "memberships",
        "membership_programs",
        "strategy",
        "optimization_iterations",
        "candidate_recipe_count",
        "beam_width",
        "debug",
    }
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--golden",
        default="production",
        help="'production' or an explicit immutable golden JSON path",
    )
    parser.add_argument("--city", default="Lund")
    parser.add_argument("--scenario", default=_STANDARD_SCENARIO)
    parser.add_argument("--cold", action="store_true")
    parser.add_argument("--warm", action="store_true")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--report-dir", type=Path, default=_DEFAULT_REPORT_ROOT)
    parser.add_argument("--request-cold-target-seconds", type=float, default=10.0)
    parser.add_argument("--warm-target-seconds", type=float, default=1.0)
    parser.add_argument("--enforce-targets", action="store_true")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--worker-phase",
        choices=("process-cold", "request-cold", "warm"),
        help=argparse.SUPPRESS,
    )
    return parser


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("benchmark JSON must be an object")
    return value


def _active_universe_id(city: str) -> str:
    settings = Settings.from_env()
    store = PreparedUniverseArtifactStore(settings.price_universe_cache_root)
    manifest = store.read_active(city)
    if manifest is None:
        raise RuntimeError(f"no active PriceUniverse for {city}")
    return manifest.universe_id


def resolve_golden(value: str, *, city: str) -> Path:
    """Resolve an explicit golden or the latest matching active production one."""

    if value != "production":
        path = Path(value).resolve(strict=True)
        _repository_relative(path)
        return path
    active_id = _active_universe_id(city)
    candidates: list[tuple[str, Path]] = []
    for path in _DEFAULT_GOLDEN_ROOT.glob("production-planner-golden-*.json"):
        try:
            report = _load_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if (
            report.get("schema_version") == "production-planner-golden-v1"
            and report.get("city") == city
            and (report.get("price_universe") or {}).get("id") == active_id
        ):
            candidates.append((str(report.get("generated_at_utc") or ""), path))
    if not candidates:
        raise FileNotFoundError(
            "no production golden matches the active PriceUniverse; freeze one first"
        )
    return max(candidates, key=lambda row: (row[0], row[1].name))[1].resolve()


def _golden_request(golden: dict[str, Any], scenario: str) -> PlanRequest:
    scenarios = golden.get("dynamic_scenarios") or {}
    row = scenarios.get(scenario)
    if not isinstance(row, dict) or not isinstance(row.get("input"), dict):
        raise TypeError(f"golden does not contain dynamic scenario {scenario!r}")
    validated = PlanRequest.model_validate(row["input"])
    raw_fields_set = row.get("input_fields_set")
    fields_set = (
        frozenset(str(value) for value in raw_fields_set)
        if isinstance(raw_fields_set, list)
        else _LEGACY_GOLDEN_REQUEST_FIELDS
    )
    unknown = fields_set - set(PlanRequest.model_fields)
    if unknown:
        raise ValueError("golden request contains unknown explicit fields")
    # Values have already passed full validation above. model_construct is
    # used only to restore Pydantic's explicit-field provenance exactly.
    return PlanRequest.model_construct(
        _fields_set=set(fields_set),
        **validated.__dict__,
    )


def _trace_row(snapshot: Any) -> dict[str, Any]:
    return {
        "timings_ms": snapshot.timings_ms,
        "span_statistics": snapshot.span_statistics,
        "operation_counters": snapshot.operation_counters,
        "search_depth_counters": snapshot.depth_counters,
    }


async def _measured_plan(
    service: MealPlanService,
    request: PlanRequest,
    *,
    expected_fingerprint: str,
) -> dict[str, Any]:
    started = perf_counter()
    cpu_started = process_time()
    with activate_performance_trace() as trace:
        plan = await service.create_plan(request)
    wall_seconds = perf_counter() - started
    cpu_seconds = process_time() - cpu_started
    report = _plan_report(plan, request, elapsed_seconds=wall_seconds)
    actual_fingerprint = report["semantic_fingerprint"]
    trace_row = _trace_row(trace.snapshot())
    optimization = (
        plan.optimization.model_dump(mode="json") if plan.optimization is not None else {}
    )
    return {
        "request_wall_ms": round(wall_seconds * 1000, 3),
        "request_cpu_ms": round(cpu_seconds * 1000, 3),
        "expected_semantic_fingerprint": expected_fingerprint,
        "actual_semantic_fingerprint": actual_fingerprint,
        "economic_equivalence": actual_fingerprint == expected_fingerprint,
        "result": {
            "total": report["total"],
            "price_per_portion": report["price_per_portion"],
            "recipes": [row["name"] for row in report["recipes"]],
            "stores": [
                row["store_name"] for row in report["selected_basket"]["stores"]
            ],
            "selected_contracts": report["selected_price_contracts"],
        },
        "trace": trace_row,
        "search": optimization,
    }


async def _worker(args: argparse.Namespace) -> dict[str, Any]:
    golden_path = Path(args.golden).resolve(strict=True)
    _repository_relative(golden_path)
    golden = _load_json(golden_path)
    request = _golden_request(golden, args.scenario)
    expected = golden["dynamic_scenarios"][args.scenario]["semantic_fingerprint"]
    pricing_date = date.fromisoformat(golden["pricing_date_europe_stockholm"])

    base = Settings.from_env()
    settings = replace(
        base,
        meal_plan_strategy="optimized",
        price_universe_required=True,
        allow_provider_fallback=False,
        allow_mock_fallback=False,
        openai_api_key=None,
    )
    artifact_store = PreparedUniverseArtifactStore(settings.price_universe_cache_root)
    manager = PreparedPriceUniverseManager()
    load_started = perf_counter()
    load_cpu_started = process_time()
    with activate_performance_trace() as load_trace:
        with performance_span("price_universe_integrity_verification"):
            artifact_path = artifact_store.resolve_active_artifact(args.city)
        if artifact_path is None:
            raise RuntimeError(f"no active PriceUniverse for {args.city}")
        with performance_span("price_universe_load"):
            prepared = manager.load_file_and_activate(artifact_path)
    load_wall_ms = round((perf_counter() - load_started) * 1000, 3)
    load_cpu_ms = round((process_time() - load_cpu_started) * 1000, 3)
    expected_universe = golden["price_universe"]["id"]
    if prepared.universe.universe_id != expected_universe:
        raise AssertionError("active PriceUniverse does not match golden")

    service = MealPlanService(settings, price_universe_manager=manager)
    projection_prewarm = precompute_pricing_semantics(
        settings,
        prepared,
        manager=manager,
        selector=service.economic_selector,
        on_date=pricing_date,
    )
    sentinel = OfflineSentinelProvider()
    original_factory = optimizer_module.create_price_provider
    original_pricing_date = optimizer_module.current_pricing_date
    optimizer_module.create_price_provider = lambda *_args, **_kwargs: sentinel
    optimizer_module.current_pricing_date = lambda: pricing_date
    samples: list[dict[str, Any]] = []
    seed: dict[str, Any] | None = None
    try:
        if args.worker_phase == "warm":
            seed = await _measured_plan(
                service,
                request,
                expected_fingerprint=expected,
            )
            for _ in range(args.runs):
                samples.append(
                    await _measured_plan(
                        service,
                        request,
                        expected_fingerprint=expected,
                    )
                )
        else:
            samples.append(
                await _measured_plan(
                    service,
                    request,
                    expected_fingerprint=expected,
                )
            )
    finally:
        optimizer_module.create_price_provider = original_factory
        optimizer_module.current_pricing_date = original_pricing_date
    if sentinel.calls:
        raise AssertionError("production benchmark attempted provider I/O")
    return {
        "schema_version": _WORKER_SCHEMA,
        "phase": args.worker_phase,
        "city": args.city,
        "scenario": args.scenario,
        "golden_path": _repository_relative(golden_path),
        "price_universe_id": prepared.universe.universe_id,
        "price_universe_load_wall_ms": load_wall_ms,
        "price_universe_load_cpu_ms": load_cpu_ms,
        "price_universe_load_trace": _trace_row(load_trace.snapshot()),
        "pricing_projection_startup_prewarm_ms": round(
            projection_prewarm.duration_seconds * 1000,
            3,
        ),
        "seed": seed,
        "samples": samples,
        "provider_calls": sentinel.calls,
    }


def _worker_command(
    *,
    golden: Path,
    city: str,
    scenario: str,
    phase: str,
    runs: int,
) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--worker-phase",
        phase,
        "--golden",
        str(golden),
        "--city",
        city,
        "--scenario",
        scenario,
        "--runs",
        str(runs),
        "--format",
        "json",
    ]


def _run_worker(
    *,
    golden: Path,
    city: str,
    scenario: str,
    phase: str,
    runs: int,
) -> dict[str, Any]:
    command = _worker_command(
        golden=golden,
        city=city,
        scenario=scenario,
        phase=phase,
        runs=runs,
    )
    started = perf_counter()
    completed = subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    process_wall_ms = round((perf_counter() - started) * 1000, 3)
    if completed.returncode != 0:
        # Never propagate stderr: dependency exceptions can contain environment
        # values. The worker's return code and phase are sufficient diagnostics.
        raise RuntimeError(f"{phase} worker failed with exit {completed.returncode}")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{phase} worker returned invalid JSON") from exc
    if result.get("schema_version") != _WORKER_SCHEMA:
        raise RuntimeError(f"{phase} worker returned an unsupported schema")
    result["subprocess_end_to_end_wall_ms"] = process_wall_ms
    return result


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def distribution(values: list[float]) -> dict[str, Any]:
    """Return stable descriptive statistics without assuming large samples."""

    if not values:
        return {"samples": 0, "values": [], "median": None, "p95": None}
    normalized = [round(float(value), 3) for value in values]
    return {
        "samples": len(normalized),
        "values": normalized,
        "min": round(min(normalized), 3),
        "median": round(statistics.median(normalized), 3),
        "p95": round(_p95(normalized), 3),
        "max": round(max(normalized), 3),
    }


def _aggregate_spans(samples: list[dict[str, Any]]) -> dict[str, Any]:
    names = sorted(
        {
            name
            for sample in samples
            for name in sample["trace"]["span_statistics"]
        }
    )
    result: dict[str, Any] = {}
    for name in names:
        rows = [
            sample["trace"]["span_statistics"].get(name, {}) for sample in samples
        ]
        result[name] = {
            "calls": distribution([float(row.get("calls", 0)) for row in rows]),
            "wall_ms": distribution([float(row.get("wall_ms", 0)) for row in rows]),
            "cpu_ms": distribution([float(row.get("cpu_ms", 0)) for row in rows]),
            "average_ms": distribution(
                [float(row.get("average_ms", 0)) for row in rows]
            ),
            "max_observed_call_ms": round(
                max((float(row.get("max_ms", 0)) for row in rows), default=0),
                3,
            ),
        }
    return result


def _aggregate_load_spans(workers: list[dict[str, Any]]) -> dict[str, Any]:
    synthetic_samples = [
        {"trace": worker["price_universe_load_trace"]} for worker in workers
    ]
    return _aggregate_spans(synthetic_samples)


def _aggregate_counters(samples: list[dict[str, Any]]) -> dict[str, Any]:
    names = sorted(
        {
            name
            for sample in samples
            for name in sample["trace"]["operation_counters"]
        }
    )
    return {
        name: distribution(
            [float(sample["trace"]["operation_counters"].get(name, 0)) for sample in samples]
        )
        for name in names
    }


def _aggregate_search(samples: list[dict[str, Any]]) -> dict[str, Any]:
    numeric_names = sorted(
        {
            name
            for sample in samples
            for name, value in sample.get("search", {}).items()
            if isinstance(value, int | float)
        }
    )
    numeric = {
        name: distribution(
            [float(sample.get("search", {}).get(name, 0)) for sample in samples]
        )
        for name in numeric_names
    }
    return {
        "metrics": numeric,
        "operation_counters": _aggregate_counters(samples),
        "search_depth_samples": [
            sample["trace"]["search_depth_counters"] for sample in samples
        ],
    }


def _phase_report(phase: str, workers: list[dict[str, Any]]) -> dict[str, Any]:
    samples = [sample for worker in workers for sample in worker["samples"]]
    seeds = [worker["seed"] for worker in workers if worker.get("seed") is not None]
    equivalence = all(
        sample["economic_equivalence"] for sample in [*seeds, *samples]
    )
    provider_calls = sum(int(worker["provider_calls"]) for worker in workers)
    phase_row: dict[str, Any] = {
        "phase": phase,
        "worker_processes": len(workers),
        "request_latency_ms": distribution(
            [float(sample["request_wall_ms"]) for sample in samples]
        ),
        "request_cpu_ms": distribution(
            [float(sample["request_cpu_ms"]) for sample in samples]
        ),
        "price_universe_load_ms": distribution(
            [float(worker["price_universe_load_wall_ms"]) for worker in workers]
        ),
        "pricing_projection_startup_prewarm_ms": distribution(
            [
                float(worker.get("pricing_projection_startup_prewarm_ms", 0))
                for worker in workers
            ]
        ),
        "price_universe_load_stage_statistics": _aggregate_load_spans(workers),
        "stage_statistics": _aggregate_spans(samples),
        "search_statistics": _aggregate_search(samples),
        "economic_equivalence": equivalence,
        "seed_economic_equivalence": (
            all(seed["economic_equivalence"] for seed in seeds) if seeds else None
        ),
        "provider_calls": provider_calls,
        "sample_results": [
            {
                "total": sample["result"]["total"],
                "recipes": sample["result"]["recipes"],
                "stores": sample["result"]["stores"],
                "actual_semantic_fingerprint": sample[
                    "actual_semantic_fingerprint"
                ],
            }
            for sample in samples
        ],
    }
    if phase == "process_cold":
        phase_row["end_to_end_process_latency_ms"] = distribution(
            [float(worker["subprocess_end_to_end_wall_ms"]) for worker in workers]
        )
    return phase_row


def _top_spans(phase: dict[str, Any], *, limit: int = 15) -> list[dict[str, Any]]:
    return [
        {"stage": name, **row}
        for name, row in sorted(
            phase.get("stage_statistics", {}).items(),
            key=lambda item: (
                -(item[1].get("wall_ms", {}).get("median") or 0),
                item[0],
            ),
        )[:limit]
    ]


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Production planner benchmark",
        "",
        f"Status: **{report['status']}**",
        "",
        f"Golden: `{report['golden']['path']}`",
        f"PriceUniverse: `{report['price_universe_id']}`",
        f"Scenario: `{report['scenario']}`",
        f"Provider calls: **{report['provider_calls']}**",
        "",
        "## Latency",
        "",
        "| Phase | Samples | Median | p95 | Economic equivalence |",
        "|---|---:|---:|---:|---|",
    ]
    for name in ("process_cold", "request_cold", "warm"):
        phase = report["phases"].get(name)
        if phase is None:
            continue
        latency = (
            phase.get("end_to_end_process_latency_ms")
            if name == "process_cold"
            else phase["request_latency_ms"]
        )
        lines.append(
            f"| {name} | {latency['samples']} | {latency['median']:.3f} ms | "
            f"{latency['p95']:.3f} ms | {phase['economic_equivalence']} |"
        )
    lines.extend(("", "## Slowest request-cold stages", ""))
    request_cold = report["phases"].get("request_cold")
    if request_cold is None:
        lines.append("Request-cold was not requested.")
    else:
        lines.extend(
            (
                "| Stage | Calls median | Wall median | CPU median | Average call | Max call |",
                "|---|---:|---:|---:|---:|---:|",
            )
        )
        for row in _top_spans(request_cold, limit=15):
            lines.append(
                f"| {row['stage']} | {row['calls']['median']:.1f} | "
                f"{row['wall_ms']['median']:.3f} ms | "
                f"{row['cpu_ms']['median']:.3f} ms | "
                f"{row['average_ms']['median']:.3f} ms | "
                f"{row['max_observed_call_ms']:.3f} ms |"
            )
        lines.extend(("", "## PriceUniverse load stages", ""))
        lines.extend(
            (
                "| Stage | Calls median | Wall median | CPU median |",
                "|---|---:|---:|---:|",
            )
        )
        load_stages = request_cold["price_universe_load_stage_statistics"]
        for name, row in sorted(
            load_stages.items(),
            key=lambda item: (-(item[1]["wall_ms"]["median"] or 0), item[0]),
        ):
            lines.append(
                f"| {name} | {row['calls']['median']:.1f} | "
                f"{row['wall_ms']['median']:.3f} ms | "
                f"{row['cpu_ms']['median']:.3f} ms |"
            )
        lines.extend(("", "## Search counters", ""))
        lines.extend(("| Counter | Median | p95 |", "|---|---:|---:|"))
        counters = request_cold["search_statistics"]["operation_counters"]
        preferred = (
            "recipe_candidates_generated",
            "recipe_candidates_structurally_valid",
            "beam_states",
            "states_pruned_by_cost_bound",
            "duplicate_state_rejections",
            "basket_calculations",
            "menu_cache_hits",
            "menu_cache_misses",
            "store_combinations",
            "store_combinations_pruned_infeasible",
            "incremental_requirement_cache_hits",
            "incremental_requirement_cache_misses",
        )
        for name in preferred:
            row = counters.get(name)
            if row is not None:
                lines.append(
                    f"| {name} | {row['median']:.3f} | {row['p95']:.3f} |"
                )
    lines.extend(("", "## Acceptance", ""))
    acceptance = report["acceptance"]
    lines.extend(
        (
            f"- Economic golden equality: **{acceptance['economic_equivalence']}**",
            f"- Provider calls = 0: **{acceptance['provider_calls_zero']}**",
            (
                f"- Request-cold < {acceptance['request_cold_target_seconds']:.1f} s: "
                f"**{acceptance['request_cold_target_met']}**"
            ),
            (
                f"- Warm < {acceptance['warm_target_seconds']:.1f} s: "
                f"**{acceptance['warm_target_met']}**"
            ),
        )
    )
    return "\n".join(lines) + "\n"


def _summary(report: dict[str, Any]) -> str:
    lines = [f"PRODUCTION PLANNER BENCHMARK: {report['status']}"]
    for name in ("process_cold", "request_cold", "warm"):
        phase = report["phases"].get(name)
        if phase is None:
            continue
        latency = (
            phase.get("end_to_end_process_latency_ms")
            if name == "process_cold"
            else phase["request_latency_ms"]
        )
        lines.append(
            f"{name}: median={latency['median']:.3f} ms, "
            f"p95={latency['p95']:.3f} ms, n={latency['samples']}"
        )
    lines.extend(
        (
            f"economic equivalence: {report['acceptance']['economic_equivalence']}",
            f"provider calls: {report['provider_calls']}",
            f"JSON: {report['outputs']['json']}",
            f"Markdown: {report['outputs']['markdown']}",
        )
    )
    return "\n".join(lines)


def _write_report_pair(report: dict[str, Any], report_dir: Path) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    json_path = report_dir / f"benchmark-planner-{stamp}.json"
    markdown_path = report_dir / f"benchmark-planner-{stamp}.md"
    if json_path.exists() or markdown_path.exists():
        raise FileExistsError("benchmark report path already exists")
    report["outputs"] = {
        "json": _repository_relative(json_path),
        "markdown": _repository_relative(markdown_path),
    }
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def run_benchmark(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    if args.runs < 1 or args.runs > 20:
        raise ValueError("--runs must be between 1 and 20")
    if args.request_cold_target_seconds <= 0 or args.warm_target_seconds <= 0:
        raise ValueError("performance targets must be positive")
    selected_cold = args.cold or not (args.cold or args.warm)
    selected_warm = args.warm or not (args.cold or args.warm)
    golden_path = resolve_golden(args.golden, city=args.city)
    golden = _load_json(golden_path)
    expected = golden["dynamic_scenarios"][args.scenario]["semantic_fingerprint"]
    phases: dict[str, Any] = {}
    if selected_cold:
        process_workers = [
            _run_worker(
                golden=golden_path,
                city=args.city,
                scenario=args.scenario,
                phase="process-cold",
                runs=1,
            )
            for _ in range(args.runs)
        ]
        request_workers = [
            _run_worker(
                golden=golden_path,
                city=args.city,
                scenario=args.scenario,
                phase="request-cold",
                runs=1,
            )
            for _ in range(args.runs)
        ]
        phases["process_cold"] = _phase_report("process_cold", process_workers)
        phases["request_cold"] = _phase_report("request_cold", request_workers)
    if selected_warm:
        warm_worker = _run_worker(
            golden=golden_path,
            city=args.city,
            scenario=args.scenario,
            phase="warm",
            runs=args.runs,
        )
        phases["warm"] = _phase_report("warm", [warm_worker])

    all_phases = list(phases.values())
    economic_equivalence = all(row["economic_equivalence"] for row in all_phases)
    provider_calls = sum(int(row["provider_calls"]) for row in all_phases)
    request_cold_median = (
        phases.get("request_cold", {}).get("request_latency_ms", {}).get("median")
    )
    warm_median = phases.get("warm", {}).get("request_latency_ms", {}).get("median")
    request_target_met = (
        request_cold_median is None
        or request_cold_median < args.request_cold_target_seconds * 1000
    )
    warm_target_met = warm_median is None or warm_median < args.warm_target_seconds * 1000
    integrity_passed = economic_equivalence and provider_calls == 0
    performance_passed = request_target_met and warm_target_met
    status = "PASS" if integrity_passed and performance_passed else "FAIL"
    report: dict[str, Any] = {
        "schema_version": _REPORT_SCHEMA,
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "status": status,
        "city": args.city,
        "scenario": args.scenario,
        "runs_requested": args.runs,
        "latency_definitions": {
            "process_cold": "new process + PriceUniverse load + first plan",
            "request_cold": "PriceUniverse resident + first unseen request/cache key",
            "warm": "identical request after an unmeasured seed in the same process",
        },
        "golden": {
            "selector": args.golden,
            "path": _repository_relative(golden_path),
            "suite_fingerprint": golden["semantic_fingerprint"],
            "scenario_fingerprint": expected,
        },
        "price_universe_id": golden["price_universe"]["id"],
        "phases": phases,
        "provider_calls": provider_calls,
        "acceptance": {
            "economic_equivalence": economic_equivalence,
            "provider_calls_zero": provider_calls == 0,
            "request_cold_target_seconds": args.request_cold_target_seconds,
            "request_cold_target_met": request_target_met,
            "warm_target_seconds": args.warm_target_seconds,
            "warm_target_met": warm_target_met,
            "performance_targets_enforced": args.enforce_targets,
        },
    }
    _write_report_pair(report, args.report_dir)
    exit_code = 0 if integrity_passed and (performance_passed or not args.enforce_targets) else 1
    return report, exit_code


def cli_main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        if args.worker:
            if args.worker_phase is None:
                raise ValueError("worker phase is required")
            result = asyncio.run(_worker(args))
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
            return 0
        report, exit_code = run_benchmark(args)
        if args.format == "json":
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(_summary(report))
        return exit_code
    except Exception as exc:  # noqa: BLE001 - sanitized CLI boundary
        print(
            json.dumps(
                {
                    "schema_version": _REPORT_SCHEMA,
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                },
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(cli_main())
