from __future__ import annotations

import asyncio
import os

import httpx
from scripts.benchmark_beta_capacity import (
    _exit_code,
    _percentile,
    _process_snapshot,
    _profiles,
    _safe_base_url,
    benchmark,
)


def test_capacity_profiles_are_distinct_bounded_consumer_requests() -> None:
    profiles = _profiles()

    assert len(profiles) == 10
    assert len({repr(sorted(profile.items())) for profile in profiles}) == 10
    assert all(profile["postal_code"] == "22350" for profile in profiles)
    assert all(profile["recipes"] == 5 for profile in profiles)
    assert all(profile["servings"] == 4 for profile in profiles)
    assert all(1 <= profile["max_stores"] <= 3 for profile in profiles)
    assert all(profile["debug"] is False for profile in profiles)


def test_nearest_rank_percentile_is_deterministic() -> None:
    assert _percentile([5.0], 0.95) == 5.0
    assert _percentile([5.0, 1.0, 4.0, 2.0, 3.0], 0.50) == 3.0
    assert _percentile(list(map(float, range(1, 11))), 0.95) == 10.0


def test_capacity_target_rejects_query_and_credentials() -> None:
    assert _safe_base_url("https://beta.example.test/") == "https://beta.example.test"
    for unsafe in (
        "https://beta.example.test/?plan=secret",
        "https://user:secret@beta.example.test",
        "https://beta.example.test/#plan=secret",
    ):
        try:
            _safe_base_url(unsafe)
        except ValueError:
            pass
        else:
            raise AssertionError(f"unsafe benchmark target accepted: {unsafe}")


def test_capacity_benchmark_validates_consumer_contract(monkeypatch) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = __import__("json").loads(request.content)
        return httpx.Response(
            201,
            json={
                "id": "plan-1",
                "plan": {
                    "recipes": [{"name": f"R{index}"} for index in range(5)],
                    "optimized_basket": {
                        "total": 250.0,
                        "stores": [{}] * payload["max_stores"],
                    },
                    "data": {"live_chain_requests": 0},
                    "optimization": {"timings_seconds": {"total_runtime": 0.75}},
                },
            },
        )

    original = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    report = asyncio.run(
        benchmark(base_url="https://beta.example.test", concurrency=5, timeout_seconds=5)
    )

    assert report["successes"] == 5
    assert report["errors"] == 0
    assert report["provider_calls"] == 0
    assert report["request_profile"] == "distinct-realistic-22350-five-by-four"
    assert report["compute_latency_ms"] == {
        "status": "available",
        "samples": 5,
        "median": 750.0,
        "p95_nearest_rank": 750.0,
        "min": 750.0,
        "max": 750.0,
    }
    assert report["outcomes"] == {
        "accepted_http_201": 5,
        "completed_contract": 5,
        "controlled_rejected_503": 0,
        "timeouts": 0,
        "other_errors": 0,
    }
    assert report["proxy_sla"] == {
        "threshold_seconds": 60.0,
        "status": "pass",
        "requests_within_threshold": 5,
        "requests_over_threshold": 0,
    }
    assert report["target_process_resources"] == {"status": "not_requested"}
    assert all("plan_id" not in result for result in report["results"])

    sampled = asyncio.run(
        benchmark(
            base_url="https://beta.example.test",
            concurrency=1,
            timeout_seconds=5,
            target_pid=os.getpid(),
            sample_interval_seconds=0.02,
        )
    )
    resources = sampled["target_process_resources"]
    assert resources["status"] == "complete"
    assert resources["samples"] >= 1
    assert resources["peak_rss_bytes"] > 0


def test_capacity_benchmark_classifies_controlled_admission_rejection(monkeypatch) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            headers={"X-Error-Code": "planner_admission_full", "Retry-After": "2"},
        )

    original = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)
    report = asyncio.run(
        benchmark(base_url="https://beta.example.test", concurrency=1, timeout_seconds=5)
    )

    assert report["outcomes"] == {
        "accepted_http_201": 0,
        "completed_contract": 0,
        "controlled_rejected_503": 1,
        "timeouts": 0,
        "other_errors": 0,
    }
    assert report["compute_latency_ms"] == {"status": "unavailable", "samples": 0}
    assert report["results"][0]["retry_after_seconds"] == 2


def test_capacity_sampler_reads_current_process_on_windows_or_linux() -> None:
    snapshot = _process_snapshot(os.getpid())

    assert snapshot.cpu_seconds >= 0
    assert snapshot.rss_bytes > 0
    assert snapshot.peak_rss_bytes >= snapshot.rss_bytes


def test_capacity_exit_code_enforces_proxy_sla_even_without_http_errors() -> None:
    assert _exit_code({"errors": 0, "proxy_sla": {"status": "pass"}}) == 0
    assert _exit_code({"errors": 0, "proxy_sla": {"status": "fail"}}) == 2
    assert _exit_code({"errors": 1, "proxy_sla": {"status": "pass"}}) == 2
