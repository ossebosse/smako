"""Deterministically profile one snapshot-backed Lund meal-plan request.

The command requires explicit immutable inputs and disables all socket access
while the provider and optimiser run.  Human-readable output is written to
stderr; the complete machine-readable report is written to stdout (and,
optionally, to ``--json-output``).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for import_root in (PROJECT_ROOT, BACKEND_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Profilera ett helt meal-plan-flow från explicita frysta Lund-data."
    )
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--recipes", type=int, default=5)
    parser.add_argument("--servings", type=int, default=4)
    parser.add_argument("--max-stores", type=int, default=2)
    parser.add_argument(
        "--diversity",
        choices=("cheapest", "balanced", "varied"),
        default="balanced",
    )
    parser.add_argument("--candidate-count", type=int, default=80)
    parser.add_argument("--candidate-search-limit", type=int)
    parser.add_argument("--beam-width", type=int, default=30)
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Explicit grocery-data SQLite snapshot; always opened immutable/read-only.",
    )
    parser.add_argument(
        "--external-cache",
        type=Path,
        help="Explicit credential-free frozen Primat cache; omit only with --own-only.",
    )
    parser.add_argument("--own-only", action="store_true")
    parser.add_argument("--max-price-age-hours", type=float, default=48.0)
    parser.add_argument(
        "--freshness-now",
        type=str,
        help="Timezone-aware ISO timestamp used by the deterministic readiness gate.",
    )
    parser.add_argument("--json-output", type=Path)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_identity(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    stat = resolved.stat()
    return {
        "path": str(resolved),
        "size_bytes": stat.st_size,
        "sha256": _sha256(resolved),
    }


def _freshness_now(value: str | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("--freshness-now must include a timezone")
    return parsed.astimezone(UTC)


def _validate_args(args: argparse.Namespace) -> tuple[str, datetime]:
    postal_code = "".join(character for character in args.postal_code if character.isdigit())
    if len(postal_code) != 5:
        raise ValueError("postal-code must contain five digits")
    if not 1 <= args.recipes <= 7:
        raise ValueError("recipes must be between 1 and 7")
    if not 1 <= args.servings <= 12:
        raise ValueError("servings must be between 1 and 12")
    if not 1 <= args.max_stores <= 4:
        raise ValueError("max-stores must be between 1 and 4")
    if not 10 <= args.candidate_count <= 300:
        raise ValueError("candidate-count must be between 10 and 300")
    if args.candidate_search_limit is not None and not 5 <= args.candidate_search_limit <= 300:
        raise ValueError("candidate-search-limit must be between 5 and 300")
    if not 5 <= args.beam_width <= 100:
        raise ValueError("beam-width must be between 5 and 100")
    if args.max_price_age_hours <= 0:
        raise ValueError("max-price-age-hours must be positive")
    if args.own_only and args.external_cache is not None:
        raise ValueError("--own-only cannot be combined with --external-cache")
    if not args.own_only and args.external_cache is None:
        raise ValueError("federated profiling requires --external-cache")
    if args.json_output is not None and args.json_output.exists():
        raise FileExistsError("--json-output refuses to overwrite an existing file")
    return postal_code, _freshness_now(args.freshness_now)


async def _profile(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    from app.config import Settings
    from app.models import DiversityMode, PlanRequest
    from app.services.meal_plan_optimizer import MealPlanService
    from app.services.performance_trace import (
        activate_performance_trace,
        performance_span,
    )
    from scripts.benchmark_lund_phase_c import (
        _file_state,
        _network_disabled,
        _provider_for,
        _readiness,
        _TerminalContextFilteredProvider,
    )

    postal_code, freshness_now = _validate_args(args)
    mode = "own-only" if args.own_only else "federated"
    database_before = _file_state(args.database)
    external_identity = _file_identity(args.external_cache) if args.external_cache else None
    readiness = _readiness(
        args.database,
        mode=mode,
        external_cache=args.external_cache,
        max_age_hours=args.max_price_age_hours,
        now=freshness_now,
    )
    if not readiness["ready"]:
        return (
            {
                "profile": "meal_plan",
                "status": "NOT_READY",
                "reasons": list(readiness["reasons"]),
                "database": database_before,
                "external_cache": external_identity,
            },
            2,
        )

    provider = client = engine = None
    network_attempts = 0
    started = perf_counter()
    try:
        provider, client, engine, compatibility_needed, _external = await _provider_for(
            args.database,
            mode=mode,
            postal_code=postal_code,
            external_cache=args.external_cache,
            bounded_primat_live=False,
            primat_max_requests=1,
            max_price_age_hours=args.max_price_age_hours,
            freshness_now=freshness_now,
        )
        filtered = _TerminalContextFilteredProvider(
            provider,
            readiness.get("terminal_context_gaps", ()),
        )
        request = PlanRequest(
            postal_code=postal_code,
            recipes=args.recipes,
            servings=args.servings,
            max_stores=args.max_stores,
            memberships={
                "ica": False,
                "coop": False,
                "willys": False,
                "hemkop": False,
                "citygross": False,
                "lidl": False,
            },
            optimization_iterations=0,
            strategy="optimized",
            candidate_recipe_count=args.candidate_count,
            candidate_search_limit=args.candidate_search_limit,
            beam_width=args.beam_width,
            diversity_mode=DiversityMode(args.diversity),
            debug=True,
        )
        service = MealPlanService(
            Settings(
                price_provider="federated",
                meal_plan_strategy="optimized",
                openai_api_key=None,
                allow_mock_fallback=False,
                allow_medium_semantic_matches=False,
                allow_estimated_quantities=True,
                allow_unknown_quantities=False,
                allow_unknown_sale_model=False,
            )
        )
        with activate_performance_trace() as trace, _network_disabled() as attempts:
            try:
                response = await service._build_optimized_with_provider(request, filtered)
                with performance_span("response_serialization"):
                    serialized = response.model_dump(mode="json")
                snapshot = trace.snapshot()
            finally:
                network_attempts = attempts["count"]
        total_ms = round((perf_counter() - started) * 1000, 3)
        selected_contexts = sorted(
            group.store_id for group in response.optimized_basket.stores
        )
        hotspot_rows = sorted(
            (
                {"stage": name, "milliseconds": milliseconds}
                for name, milliseconds in snapshot.timings_ms.items()
                if name != "total_runtime"
            ),
            key=lambda row: (-row["milliseconds"], row["stage"]),
        )
        result = {
            "profile": "meal_plan",
            "schema_version": "meal-plan-profile-v1",
            "status": "PASS" if network_attempts == 0 else "FAIL",
            "scope": {
                "postal_code": postal_code,
                "mode": mode,
                "freshness_evaluated_at": freshness_now.isoformat().replace("+00:00", "Z"),
                "max_price_age_hours": args.max_price_age_hours,
            },
            "inputs": {
                "database": database_before,
                "external_cache": external_identity,
                "request": request.model_dump(mode="json"),
            },
            "result": {
                "total_sek": response.optimized_basket.total,
                "selected_context_ids": selected_contexts,
                "verification_status": response.optimized_basket.verification_status,
                "recipes": [recipe.name for recipe in response.recipes],
                "serialized_bytes": len(
                    json.dumps(serialized, ensure_ascii=False, separators=(",", ":")).encode(
                        "utf-8"
                    )
                ),
            },
            "timing": snapshot.timings_ms,
            "span_statistics": snapshot.span_statistics,
            "operation_counters": snapshot.operation_counters,
            "search_depth_counters": snapshot.depth_counters,
            "top_hotspots": hotspot_rows[:3],
            "wall_clock_ms": total_ms,
            "network_attempts": network_attempts,
            "immutable_unchanged": database_before == _file_state(args.database),
            "legacy_temp_store_projection": compatibility_needed,
        }
        if not result["immutable_unchanged"]:
            result["status"] = "FAIL"
        return result, 0 if result["status"] == "PASS" else 1
    except Exception as exc:  # noqa: BLE001 - never copy potentially sensitive text
        return (
            {
                "profile": "meal_plan",
                "status": "FAIL",
                "error_type": type(exc).__name__,
                "network_attempts": network_attempts,
                "database": database_before,
                "immutable_unchanged": database_before == _file_state(args.database),
            },
            1,
        )
    finally:
        if provider is not None:
            await provider.aclose()
        if client is not None:
            await client.aclose()
        if engine is not None:
            engine.dispose()


def _human_summary(report: dict[str, Any]) -> str:
    lines = [f"MEAL PLAN PROFILE: {report.get('status', 'UNKNOWN')}"]
    if report.get("status") != "PASS":
        reasons = report.get("reasons") or [report.get("error_type", "unknown failure")]
        lines.extend(f"  {reason}" for reason in reasons)
        return "\n".join(lines)
    result = report["result"]
    lines.extend(
        (
            f"Total: {result['total_sek']:.2f} kr",
            f"Contexts: {', '.join(result['selected_context_ids'])}",
            f"Wall clock: {report['wall_clock_ms']:.3f} ms",
            "Top hotspots:",
        )
    )
    lines.extend(
        f"  {index}. {row['stage']}: {row['milliseconds']:.3f} ms"
        for index, row in enumerate(report["top_hotspots"], start=1)
    )
    counters = report["operation_counters"]
    lines.append(
        "Operations: "
        f"products={counters.get('products_loaded', 0)}, "
        f"semantic={counters.get('semantic_comparisons', 0)}, "
        f"baskets={counters.get('basket_calculations', 0)}, "
        f"packages={counters.get('package_calculations', 0)}, "
        f"cache hits/misses={counters.get('cache_hits', 0)}/"
        f"{counters.get('cache_misses', 0)}"
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        report, exit_code = asyncio.run(_profile(args))
    except Exception as exc:  # noqa: BLE001 - sanitized CLI boundary
        report = {
            "profile": "meal_plan",
            "status": "FAIL",
            "error_type": type(exc).__name__,
        }
        exit_code = 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(_human_summary(report), file=sys.stderr)
    print(rendered)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
