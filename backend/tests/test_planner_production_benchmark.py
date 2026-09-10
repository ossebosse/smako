from __future__ import annotations

import argparse
from pathlib import Path

from app.models import PlanRequest

from scripts import benchmark_planner_production as benchmark


def _sample(*, wall_ms: float, equivalent: bool = True) -> dict[str, object]:
    return {
        "request_wall_ms": wall_ms,
        "request_cpu_ms": wall_ms - 1,
        "economic_equivalence": equivalent,
        "actual_semantic_fingerprint": "fingerprint",
        "result": {
            "total": 255.08,
            "recipes": ["A", "B", "C", "D", "E"],
            "stores": ["Store"],
        },
        "trace": {
            "span_statistics": {
                "menu_search": {
                    "calls": 3,
                    "wall_ms": wall_ms - 5,
                    "cpu_ms": wall_ms - 6,
                    "average_ms": (wall_ms - 5) / 3,
                    "max_ms": wall_ms - 8,
                }
            },
            "operation_counters": {"basket_calculations": 42},
            "search_depth_counters": {"1": {"states_evaluated": 10}},
        },
        "search": {
            "states_evaluated": 10,
            "basket_calculations": 42,
            "basket_cache_hit_rate": 0.5,
        },
    }


def _worker(*samples: dict[str, object]) -> dict[str, object]:
    return {
        "samples": list(samples),
        "seed": None,
        "provider_calls": 0,
        "price_universe_load_wall_ms": 100,
        "price_universe_load_trace": {
            "span_statistics": {
                "price_universe_parse_and_validate": {
                    "calls": 1,
                    "wall_ms": 90,
                    "cpu_ms": 89,
                    "average_ms": 90,
                    "max_ms": 90,
                }
            }
        },
        "subprocess_end_to_end_wall_ms": 500,
    }


def test_distribution_reports_nearest_rank_p95() -> None:
    result = benchmark.distribution([1, 2, 3, 100])

    assert result == {
        "samples": 4,
        "values": [1.0, 2.0, 3.0, 100.0],
        "min": 1.0,
        "median": 2.5,
        "p95": 100.0,
        "max": 100.0,
    }


def test_golden_request_preserves_explicit_field_semantics() -> None:
    original = PlanRequest(
        postal_code="22350",
        recipes=5,
        servings=4,
        max_stores=2,
        diversity_mode="balanced",
        diet_preference="mixed",
        membership_programs=(),
        strategy="optimized",
        optimization_iterations=0,
        candidate_recipe_count=80,
        beam_width=30,
        debug=False,
    )
    golden = {
        "dynamic_scenarios": {
            "standard": {
                "input": original.model_dump(mode="json", exclude={"debug"}),
                "input_fields_set": sorted(original.model_fields_set),
            }
        }
    }

    restored = benchmark._golden_request(golden, "standard")

    assert restored == original
    assert restored.model_fields_set == original.model_fields_set


def test_legacy_golden_request_does_not_turn_defaults_into_explicit_overrides() -> None:
    original = PlanRequest(
        postal_code="22350",
        recipes=5,
        servings=4,
        max_stores=2,
        diversity_mode="balanced",
        diet_preference="mixed",
        membership_programs=(),
        strategy="optimized",
        optimization_iterations=0,
        candidate_recipe_count=80,
        beam_width=30,
        debug=False,
    )
    golden = {
        "dynamic_scenarios": {
            "standard": {
                "input": original.model_dump(mode="json", exclude={"debug"}),
            }
        }
    }

    restored = benchmark._golden_request(golden, "standard")

    assert restored.model_fields_set == original.model_fields_set
    assert "max_pairwise_recipe_similarity" not in restored.model_fields_set


def test_phase_report_aggregates_spans_search_and_load() -> None:
    result = benchmark._phase_report(
        "request_cold",
        [_worker(_sample(wall_ms=20)), _worker(_sample(wall_ms=30))],
    )

    assert result["request_latency_ms"]["median"] == 25
    assert result["stage_statistics"]["menu_search"]["calls"]["median"] == 3
    assert (
        result["price_universe_load_stage_statistics"][
            "price_universe_parse_and_validate"
        ]["wall_ms"]["median"]
        == 90
    )
    assert result["search_statistics"]["metrics"]["states_evaluated"]["median"] == 10
    assert result["provider_calls"] == 0
    assert result["economic_equivalence"] is True


def test_process_and_request_cold_use_distinct_latency_boundaries() -> None:
    worker = _worker(_sample(wall_ms=20))

    process_cold = benchmark._phase_report("process_cold", [worker])
    request_cold = benchmark._phase_report("request_cold", [worker])

    # PROCESS COLD is the complete subprocess lifetime: interpreter startup,
    # verified universe load, startup projection and the first request.
    assert process_cold["end_to_end_process_latency_ms"]["median"] == 500
    assert process_cold["price_universe_load_ms"]["median"] == 100
    # REQUEST COLD deliberately measures only the unseen request while the
    # already-loaded universe remains resident.
    assert request_cold["request_latency_ms"]["median"] == 20
    assert "end_to_end_process_latency_ms" not in request_cold


def test_run_benchmark_fails_integrity_on_golden_drift(monkeypatch, tmp_path) -> None:
    golden = {
        "semantic_fingerprint": "suite",
        "price_universe": {"id": "price-universe:test"},
        "dynamic_scenarios": {
            "balanced_max2_no_memberships": {
                "semantic_fingerprint": "expected"
            }
        },
    }
    monkeypatch.setattr(benchmark, "resolve_golden", lambda *_args, **_kwargs: tmp_path / "g.json")
    monkeypatch.setattr(benchmark, "_load_json", lambda _path: golden)
    monkeypatch.setattr(benchmark, "_repository_relative", lambda path: Path(path).name)
    monkeypatch.setattr(
        benchmark,
        "_run_worker",
        lambda **_kwargs: _worker(_sample(wall_ms=20, equivalent=False)),
    )
    monkeypatch.setattr(
        benchmark,
        "_write_report_pair",
        lambda _report, _root: (Path("report.json"), Path("report.md")),
    )
    args = argparse.Namespace(
        golden="production",
        city="Lund",
        scenario="balanced_max2_no_memberships",
        cold=True,
        warm=False,
        runs=1,
        report_dir=tmp_path,
        request_cold_target_seconds=10.0,
        warm_target_seconds=1.0,
        enforce_targets=False,
        format="human",
    )

    report, exit_code = benchmark.run_benchmark(args)

    assert exit_code == 1
    assert report["status"] == "FAIL"
    assert report["acceptance"]["economic_equivalence"] is False


def test_grocery_data_cli_exposes_benchmark_planner() -> None:
    from grocery_data.__main__ import _parser

    args = _parser().parse_args(
        [
            "benchmark-planner",
            "--golden",
            "production",
            "--cold",
            "--warm",
            "--runs",
            "5",
        ]
    )

    assert args.command == "benchmark-planner"
    assert args.golden == "production"
    assert args.cold is True
    assert args.warm is True
    assert args.runs == 5
