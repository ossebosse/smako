from __future__ import annotations

import asyncio
from time import sleep

import app.services.meal_plan_optimizer as meal_plan_module
import pytest
from app.main import app
from app.providers.mock import MockPriceProvider
from app.services.performance_trace import (
    PerformanceTrace,
    activate_performance_trace,
    current_performance_trace,
    increment_performance_counter,
    performance_span,
    record_performance_depth,
)
from fastapi.testclient import TestClient
from scripts.profile_meal_plan import _human_summary, _parser, _validate_args


def test_trace_is_request_local_and_helpers_are_noops_when_inactive() -> None:
    assert current_performance_trace() is None
    increment_performance_counter("ignored", 3)
    record_performance_depth(1, ignored=2)

    first = PerformanceTrace()
    second = PerformanceTrace()
    with activate_performance_trace(first):
        increment_performance_counter("products_loaded", 4)
        with performance_span("load_snapshots"):
            sleep(0.001)
        with activate_performance_trace(second):
            increment_performance_counter("products_loaded", 9)
        assert current_performance_trace() is first

    assert current_performance_trace() is None
    assert first.snapshot().operation_counters == {"products_loaded": 4}
    assert second.snapshot().operation_counters == {"products_loaded": 9}
    assert first.snapshot().timings_ms["load_snapshots"] > 0
    statistic = first.snapshot().span_statistics["load_snapshots"]
    assert statistic["calls"] == 1
    assert statistic["wall_ms"] > 0
    assert statistic["cpu_ms"] >= 0
    assert statistic["average_ms"] == statistic["wall_ms"]
    assert statistic["max_ms"] == statistic["wall_ms"]


def test_trace_reports_call_average_and_max_for_repeated_spans() -> None:
    with activate_performance_trace() as trace:
        with performance_span("candidate_retrieval"):
            sleep(0.001)
        with performance_span("candidate_retrieval"):
            sleep(0.002)

    statistic = trace.snapshot().span_statistics["candidate_retrieval"]
    assert statistic["calls"] == 2
    assert statistic["wall_ms"] >= statistic["max_ms"] > 0
    assert statistic["average_ms"] == pytest.approx(
        statistic["wall_ms"] / 2,
        abs=0.001,
    )


@pytest.mark.asyncio
async def test_trace_propagates_to_to_thread_and_accumulates_depth_counters() -> None:
    with activate_performance_trace() as trace:
        await asyncio.to_thread(increment_performance_counter, "package_calculations", 7)
        record_performance_depth(1, states_expanded=20, states_kept=5)
        record_performance_depth(1, states_expanded=10, states_kept=3)

    snapshot = trace.snapshot()
    assert snapshot.operation_counters["package_calculations"] == 7
    assert snapshot.depth_counters == {
        "1": {"states_expanded": 30, "states_kept": 8}
    }


def test_optimized_api_exposes_additive_timing_and_operation_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = MockPriceProvider()
    monkeypatch.setattr(
        meal_plan_module,
        "create_price_provider",
        lambda *_args, **_kwargs: provider,
    )

    response = TestClient(app).post(
        "/api/plan",
        json={
            "postal_code": "22350",
            "recipes": 5,
            "servings": 4,
            "max_stores": 2,
            "strategy": "optimized",
            "candidate_recipe_count": 12,
            "beam_width": 5,
            "optimization_iterations": 0,
            "debug": True,
        },
    )

    assert response.status_code == 200, response.text
    optimization = response.json()["optimization"]
    assert optimization["timings_seconds"]["total_runtime"] >= 0
    assert optimization["timings_ms"]["total_runtime"] >= 0
    assert optimization["timings_ms"]["menu_search"] > 0
    assert optimization["span_statistics"]["menu_search"]["calls"] > 0
    assert optimization["span_statistics"]["menu_search"]["cpu_ms"] >= 0
    assert optimization["operation_counters"]["products_loaded"] > 0
    assert optimization["operation_counters"]["semantic_comparisons"] > 0
    assert optimization["operation_counters"]["basket_calculations"] > 0
    assert optimization["operation_counters"]["package_calculations"] > 0
    assert set(optimization["search_depth_counters"]) == {"1", "2", "3", "4", "5"}


def test_profile_cli_requires_explicit_frozen_inputs_and_has_stable_summary(tmp_path) -> None:
    database = tmp_path / "snapshot.sqlite"
    external = tmp_path / "external.json"
    database.touch()
    external.write_text("{}", encoding="utf-8")
    args = _parser().parse_args(
        [
            "--database",
            str(database),
            "--external-cache",
            str(external),
            "--freshness-now",
            "2026-08-24T08:00:00Z",
        ]
    )

    postal_code, freshness_now = _validate_args(args)

    assert postal_code == "22350"
    assert freshness_now.isoformat() == "2026-08-24T08:00:00+00:00"
    summary = _human_summary(
        {
            "status": "PASS",
            "result": {
                "total_sek": 236.68,
                "selected_context_ids": ["context:hemkop:a", "context:willys:b"],
            },
            "wall_clock_ms": 5100.0,
            "top_hotspots": [
                {"stage": "menu_search", "milliseconds": 4000.0},
            ],
            "operation_counters": {
                "products_loaded": 100,
                "semantic_comparisons": 200,
                "basket_calculations": 50,
                "package_calculations": 500,
                "cache_hits": 300,
                "cache_misses": 20,
            },
        }
    )
    assert "236.68 kr" in summary
    assert "menu_search: 4000.000 ms" in summary
    assert "cache hits/misses=300/20" in summary
