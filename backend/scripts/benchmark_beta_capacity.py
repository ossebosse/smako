"""Measure a realistic public-beta request wave through the deployed HTTP API.

The command targets an already running server.  Run each concurrency level
against a freshly started process when measuring request-cold capacity; this
keeps server lifecycle and resource sampling under the deployment harness'
control.  Reports contain only aggregate timings and closed result facts--no
request body, email, cookies, tokens, or response error text is persisted.
"""

from __future__ import annotations

import argparse
import asyncio
import ctypes
import json
import math
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

_SCHEMA = "public-beta-capacity-benchmark-v2"
_DEFAULT_REPORT_ROOT = Path("reports/public-beta/capacity")
_DEFAULT_PROXY_SLA_SECONDS = 60.0
_DEFAULT_CLIENT_TIMEOUT_SECONDS = 65.0


def _safe_base_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base URL requires an http(s) origin")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain credentials, query, or fragment")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


@dataclass(frozen=True)
class _ProcessSnapshot:
    sampled_at: float
    cpu_seconds: float
    rss_bytes: int
    peak_rss_bytes: int


def _linux_process_snapshot(pid: int) -> _ProcessSnapshot:
    stat_fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").split()
    status_lines = Path(f"/proc/{pid}/status").read_text(encoding="ascii").splitlines()
    ticks = int(os.sysconf("SC_CLK_TCK"))
    memory: dict[str, int] = {}
    for line in status_lines:
        if line.startswith(("VmRSS:", "VmHWM:")):
            key, value, _unit = line.split(maxsplit=2)
            memory[key.rstrip(":")] = int(value) * 1024
    return _ProcessSnapshot(
        sampled_at=perf_counter(),
        cpu_seconds=(int(stat_fields[13]) + int(stat_fields[14])) / ticks,
        rss_bytes=memory.get("VmRSS", 0),
        peak_rss_bytes=memory.get("VmHWM", memory.get("VmRSS", 0)),
    )


def _windows_process_snapshot(pid: int) -> _ProcessSnapshot:
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    psapi.GetProcessMemoryInfo.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    )
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), "OpenProcess failed")
    try:
        created = wintypes.FILETIME()
        exited = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")
        memory = ProcessMemoryCounters()
        memory.cb = ctypes.sizeof(memory)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        kernel_ticks = (kernel.dwHighDateTime << 32) | kernel.dwLowDateTime
        user_ticks = (user.dwHighDateTime << 32) | user.dwLowDateTime
        return _ProcessSnapshot(
            sampled_at=perf_counter(),
            cpu_seconds=(kernel_ticks + user_ticks) / 10_000_000,
            rss_bytes=int(memory.WorkingSetSize),
            peak_rss_bytes=int(memory.PeakWorkingSetSize),
        )
    finally:
        kernel32.CloseHandle(handle)


def _process_snapshot(pid: int) -> _ProcessSnapshot:
    if pid <= 0:
        raise ValueError("target pid must be positive")
    if sys.platform.startswith("linux"):
        return _linux_process_snapshot(pid)
    if sys.platform == "win32":
        return _windows_process_snapshot(pid)
    raise OSError("target-process sampling is supported on Windows and Linux")


async def _sample_target_process(
    pid: int,
    *,
    stop: asyncio.Event,
    interval_seconds: float,
) -> dict[str, Any]:
    snapshots: list[_ProcessSnapshot] = []
    error_type: str | None = None
    while True:
        try:
            snapshots.append(_process_snapshot(pid))
        except (OSError, ValueError) as exc:
            error_type = type(exc).__name__
            break
        if stop.is_set():
            break
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue
    if not snapshots:
        return {"status": "unavailable", "pid": pid, "error_type": error_type}
    first = snapshots[0]
    last = snapshots[-1]
    elapsed = max(last.sampled_at - first.sampled_at, 0.0)
    cpu_delta = max(last.cpu_seconds - first.cpu_seconds, 0.0)
    return {
        "status": "complete" if error_type is None else "partial",
        "pid": pid,
        "samples": len(snapshots),
        "cpu_time_seconds": round(cpu_delta, 6),
        "cpu_percent_during_wave": round((cpu_delta / elapsed) * 100, 3) if elapsed else 0.0,
        "rss_bytes_start": first.rss_bytes,
        "rss_bytes_end": last.rss_bytes,
        "peak_rss_bytes": max(
            snapshot.peak_rss_bytes for snapshot in snapshots
        ),
        **({"error_type": error_type} if error_type else {}),
    }


def _profiles() -> tuple[dict[str, Any], ...]:
    """Return ten bounded consumer profiles without personal data."""

    common: dict[str, Any] = {
        "postal_code": "22350",
        "recipes": 5,
        "servings": 4,
        "strategy": "optimized",
        "candidate_recipe_count": 80,
        "beam_width": 30,
        "debug": False,
    }
    variants = (
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "mixed",
            "memberships": {},
        },
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "mixed",
            "memberships": {
                "ica": True,
                "coop": True,
                "willys": True,
                "hemkop": True,
                "lidl": True,
            },
        },
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "mixed",
            "memberships": {"ica": True},
        },
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "mixed",
            "memberships": {"coop": True},
        },
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "mixed",
            "memberships": {"hemkop": True},
        },
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "mixed",
            "memberships": {"willys": True},
        },
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "mixed",
            "memberships": {"lidl": True},
        },
        {
            "max_stores": 1,
            "diversity_mode": "cheapest",
            "diet_preference": "mixed",
            "memberships": {},
        },
        {
            "max_stores": 3,
            "diversity_mode": "cheapest",
            "diet_preference": "mixed",
            "memberships": {},
        },
        {
            "max_stores": 2,
            "diversity_mode": "balanced",
            "diet_preference": "vegetarian",
            "memberships": {},
        },
    )
    return tuple(common | variant for variant in variants)


def _percentile(values: list[float], percentile: float) -> float:
    """Return a deterministic nearest-rank percentile."""

    if not values:
        raise ValueError("at least one value is required")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


async def _one_request(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
    *,
    ordinal: int,
) -> dict[str, Any]:
    started = perf_counter()
    try:
        response = await client.post(
            "/api/plans",
            json=payload,
            headers={"X-Anonymous-Session-ID": f"capacity-beta-{ordinal:02d}-session"},
        )
    except httpx.HTTPError as exc:
        return {
            "ordinal": ordinal,
            "duration_ms": round((perf_counter() - started) * 1000, 3),
            "status": None,
            "ok": False,
            "error_type": type(exc).__name__,
        }
    duration_ms = round((perf_counter() - started) * 1000, 3)
    if response.status_code != 201:
        retry_after = response.headers.get("Retry-After", "").strip()
        return {
            "ordinal": ordinal,
            "duration_ms": duration_ms,
            "status": response.status_code,
            "ok": False,
            "error_code": response.headers.get("X-Error-Code"),
            "retry_after_seconds": (
                int(retry_after) if retry_after.isdecimal() else None
            ),
        }
    try:
        saved = response.json()
        plan = saved["plan"]
        recipes = plan["recipes"]
        basket = plan["optimized_basket"]
        store_count = len(basket["stores"])
        live_calls = (plan.get("data") or {}).get("live_chain_requests", 0)
        compute_seconds = (
            ((plan.get("optimization") or {}).get("timings_seconds") or {}).get(
                "total_runtime"
            )
        )
        compute_ms = (
            round(float(compute_seconds) * 1000, 3)
            if isinstance(compute_seconds, (int, float)) and compute_seconds >= 0
            else None
        )
        valid = (
            len(recipes) == payload["recipes"]
            and store_count <= payload["max_stores"]
            and live_calls == 0
        )
        return {
            "ordinal": ordinal,
            "duration_ms": duration_ms,
            "status": response.status_code,
            "ok": valid,
            "recipe_count": len(recipes),
            "store_count": store_count,
            "total": basket.get("total"),
            "provider_calls": live_calls,
            "validation_error": None if valid else "consumer_contract_failed",
            **({"compute_ms": compute_ms} if compute_ms is not None else {}),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {
            "ordinal": ordinal,
            "duration_ms": duration_ms,
            "status": response.status_code,
            "ok": False,
            "error_type": "InvalidConsumerResponse",
        }


async def benchmark(
    *,
    base_url: str,
    concurrency: int,
    timeout_seconds: float,
    proxy_sla_seconds: float = _DEFAULT_PROXY_SLA_SECONDS,
    target_pid: int | None = None,
    sample_interval_seconds: float = 0.1,
) -> dict[str, Any]:
    if not 1 <= concurrency <= 10:
        raise ValueError("concurrency must be between 1 and 10")
    if timeout_seconds <= 0 or proxy_sla_seconds <= 0:
        raise ValueError("timeouts must be positive")
    if not 0.02 <= sample_interval_seconds <= 5:
        raise ValueError("sample interval must be between 0.02 and 5 seconds")
    target_origin = _safe_base_url(base_url)
    profiles = _profiles()[:concurrency]
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10.0))
    limits = httpx.Limits(
        max_connections=concurrency,
        max_keepalive_connections=concurrency,
    )
    resource_stop = asyncio.Event()
    resource_task = (
        asyncio.create_task(
            _sample_target_process(
                target_pid,
                stop=resource_stop,
                interval_seconds=sample_interval_seconds,
            )
        )
        if target_pid is not None
        else None
    )
    wave_started = perf_counter()
    try:
        async with httpx.AsyncClient(
            base_url=target_origin,
            timeout=timeout,
            limits=limits,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            results = await asyncio.gather(
                *(
                    _one_request(client, payload, ordinal=index)
                    for index, payload in enumerate(profiles, start=1)
                )
            )
    finally:
        resource_stop.set()
    resource_usage = (
        await resource_task
        if resource_task is not None
        else {"status": "not_requested"}
    )
    wave_ms = round((perf_counter() - wave_started) * 1000, 3)
    durations = [float(row["duration_ms"]) for row in results]
    compute_durations = [
        float(row["compute_ms"])
        for row in results
        if isinstance(row.get("compute_ms"), (int, float))
    ]
    successes = sum(bool(row["ok"]) for row in results)
    controlled_rejections = sum(
        row.get("status") == 503 and row.get("error_code") == "planner_admission_full"
        for row in results
    )
    timeouts = sum("timeout" in str(row.get("error_type") or "").casefold() for row in results)
    proxy_sla_ms = proxy_sla_seconds * 1000
    within_sla = sum(duration <= proxy_sla_ms for duration in durations)
    return {
        "schema_version": _SCHEMA,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "target_origin": target_origin,
        "concurrency": concurrency,
        "client_timeout_seconds": timeout_seconds,
        "request_profile": "distinct-realistic-22350-five-by-four",
        "wave_duration_ms": wave_ms,
        "latency_ms": {
            "median": round(statistics.median(durations), 3),
            "p95_nearest_rank": round(_percentile(durations, 0.95), 3),
            "min": round(min(durations), 3),
            "max": round(max(durations), 3),
        },
        "compute_latency_ms": (
            {
                "status": "available",
                "samples": len(compute_durations),
                "median": round(statistics.median(compute_durations), 3),
                "p95_nearest_rank": round(_percentile(compute_durations, 0.95), 3),
                "min": round(min(compute_durations), 3),
                "max": round(max(compute_durations), 3),
            }
            if compute_durations
            else {"status": "unavailable", "samples": 0}
        ),
        "outcomes": {
            "accepted_http_201": sum(row.get("status") == 201 for row in results),
            "completed_contract": successes,
            "controlled_rejected_503": controlled_rejections,
            "timeouts": timeouts,
            "other_errors": concurrency - successes - controlled_rejections - timeouts,
        },
        "successes": successes,
        "errors": concurrency - successes,
        "proxy_sla": {
            "threshold_seconds": proxy_sla_seconds,
            "status": (
                "pass"
                if successes == concurrency and within_sla == concurrency
                else "fail"
            ),
            "requests_within_threshold": within_sla,
            "requests_over_threshold": concurrency - within_sla,
        },
        "target_process_resources": resource_usage,
        "provider_calls": sum(int(row.get("provider_calls") or 0) for row in results),
        "results": results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, choices=(1, 5, 10), required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=_DEFAULT_CLIENT_TIMEOUT_SECONDS,
        help="HTTP client deadline; defaults just above the 60 s burst proxy SLA",
    )
    parser.add_argument(
        "--proxy-sla-seconds",
        type=float,
        default=_DEFAULT_PROXY_SLA_SECONDS,
    )
    parser.add_argument(
        "--target-pid",
        type=int,
        help="optionally sample CPU/RSS/peak RSS for this backend process",
    )
    parser.add_argument("--sample-interval-seconds", type=float, default=0.1)
    parser.add_argument("--report-dir", type=Path, default=_DEFAULT_REPORT_ROOT)
    parser.add_argument("--format", choices=("human", "json"), default="human")
    return parser


def _exit_code(report: dict[str, Any]) -> int:
    return 0 if (
        report.get("errors") == 0
        and (report.get("proxy_sla") or {}).get("status") == "pass"
    ) else 2


def main() -> int:
    args = _parser().parse_args()
    report = asyncio.run(
        benchmark(
            base_url=args.base_url,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout_seconds,
            proxy_sla_seconds=args.proxy_sla_seconds,
            target_pid=args.target_pid,
            sample_interval_seconds=args.sample_interval_seconds,
        )
    )
    args.report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = args.report_dir / f"capacity-c{args.concurrency}-{timestamp}.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        latency = report["latency_ms"]
        print("PUBLIC BETA CAPACITY")
        print(f"Concurrency: {report['concurrency']}")
        print(f"Successes: {report['successes']} | Errors: {report['errors']}")
        print(
            "Latency: "
            f"median {latency['median'] / 1000:.3f} s | "
            f"p95 {latency['p95_nearest_rank'] / 1000:.3f} s"
        )
        print(f"Wave: {report['wave_duration_ms'] / 1000:.3f} s")
        compute = report["compute_latency_ms"]
        if compute["status"] == "available":
            print(
                "Compute: "
                f"median {compute['median'] / 1000:.3f} s | "
                f"p95 {compute['p95_nearest_rank'] / 1000:.3f} s"
            )
        print(
            f"Proxy SLA ({report['proxy_sla']['threshold_seconds']:.0f} s): "
            f"{report['proxy_sla']['status'].upper()}"
        )
        resources = report["target_process_resources"]
        if resources["status"] != "not_requested":
            print(
                "Target process: "
                f"{resources['status']} | CPU "
                f"{resources.get('cpu_percent_during_wave', 0):.1f}% | peak RSS "
                f"{resources.get('peak_rss_bytes', 0) / (1024 ** 2):.1f} MiB"
            )
        print(f"Provider calls: {report['provider_calls']}")
        print(f"JSON: {destination}")
    return _exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
