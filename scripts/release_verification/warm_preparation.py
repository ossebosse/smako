"""Gate a warm HTTP probe on completed preparation for an exact build/scope."""
from __future__ import annotations

import time


def wait_for_warm_preparation(request, base, *, build_id, universe_ids, timeout=300):
    """Return observed evidence before the caller starts its latency clock.

    Ordinary /ready only proves availability. A restart, partial preparation,
    different build or changed active price scope must never count as warm.
    ``request`` is a Playwright APIRequestContext; no private session is logged.
    """
    expected = set(universe_ids)
    if not build_id or not expected or timeout <= 0:
        raise ValueError("Warm probes require a build ID, active universe IDs and a positive timeout")
    started = time.monotonic()
    observations = 0
    while time.monotonic() - started < timeout:
        response = request.get(base.rstrip("/") + "/ready/preparation",
                               timeout=min(10000, max(1, int((timeout - (time.monotonic() - started)) * 1000))))
        status, evidence = response.status, response.json()
        response.dispose()
        observations += 1
        if status not in {200, 202}:
            raise RuntimeError(f"Warm preparation returned HTTP {status}")
        if evidence.get("build_id") != build_id:
            raise RuntimeError("Warm preparation build differs from the expected build")
        rows = evidence.get("universes", [])
        if {row.get("universe_id") for row in rows} != expected:
            raise RuntimeError("Warm preparation active price scope differs from the expected scope")
        if status == 200:
            if (evidence.get("status") != "ready" or evidence.get("preparation_status") != "ready"
                    or evidence.get("library_status") != "ready"
                    or not all(row.get("status") == "ready" for row in rows)):
                raise RuntimeError("Warm preparation response lacks completed evidence")
            return {"evidence": evidence, "observations": observations,
                    "wait_seconds": round(time.monotonic() - started, 3)}
        time.sleep(min(2, max(0, timeout - (time.monotonic() - started))))
    raise TimeoutError("Preparation did not complete; no warm latency measurement was started")
