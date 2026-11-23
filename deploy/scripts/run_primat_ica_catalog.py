"""Daily slice of the full ICA catalogs from Primat (see primat_ica_catalog).

Runs from the scheduler's cron when ``PRIMAT_ICA_CATALOG_ENABLED=true``.  It
needs no refresh lock: it writes only its own catalog file and a status file.
A second copy started while one runs exits at once.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from app.services.primat_ica_catalog import CatalogStore, QuotaExhausted, run_catalog_step
from grocery_data.app.services.durable_files import atomic_write_bytes

_ALLOWED = {("GET", "/me"), ("GET", "/stores"), ("GET", "/prices"), ("POST", "/batch")}


def _root() -> Path:
    return Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).parent


def catalog_path() -> Path:
    configured = os.getenv("PRIMAT_ICA_CATALOG_DB", "").strip()
    return Path(configured) if configured else _root() / "primat-ica-catalog" / "catalog.sqlite"


def _cities() -> list[str]:
    configured = os.getenv("PRIMAT_ICA_CATALOG_CITIES", "").strip()
    if configured:
        return [city.strip() for city in configured.split(",") if city.strip()]
    from grocery_data.app.services.municipal_rollout import refresh_scopes

    cities = [str(scope["city"]) for scope in refresh_scopes()]
    return cities or [os.getenv("REFRESH_CITY", "Lund")]


def _client() -> tuple[httpx.AsyncClient, Any]:
    key = os.environ.get("PRIMAT_API_KEY", "").strip()
    if not key:
        raise SystemExit("PRIMAT_API_KEY is required")
    base = httpx.URL(os.getenv("PRIMAT_BASE_URL", "https://primat.nu/api/v3").rstrip("/") + "/")
    host = (base.host or "").casefold()
    if base.scheme != "https" or not (host == "primat.nu" or host.endswith(".primat.nu")):
        raise SystemExit("PRIMAT_BASE_URL must be an HTTPS primat.nu address")
    client = httpx.AsyncClient(
        base_url=str(base),
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
        timeout=httpx.Timeout(30.0, connect=10.0),
        transport=httpx.AsyncHTTPTransport(retries=1),
    )

    async def fetch(method: str, path: str, *, params=None, json=None) -> dict[str, Any]:
        if (method, path) not in _ALLOWED:
            raise RuntimeError(f"request outside the catalog job's scope: {method} {path}")
        response = await client.request(method, path.lstrip("/"), params=params, json=json)
        if response.status_code == 429:
            raise QuotaExhausted("Primat rate or row limit reached")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {"data": payload}

    return client, fetch


async def _run() -> dict[str, Any]:
    path = catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = (path.parent / ".lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"status": "skipped", "reason": "already_running"}
    store = CatalogStore(path)
    client, fetch = _client()
    try:
        report = await run_catalog_step(
            store,
            fetch,
            cities=_cities(),
            max_rows=int(os.getenv("PRIMAT_ICA_CATALOG_MAX_ROWS", "19000")),
            reserve_rows=int(os.getenv("PRIMAT_ICA_CATALOG_RESERVE_ROWS", "500")),
            offers=os.getenv("PRIMAT_ICA_CATALOG_OFFERS", "true").casefold() == "true",
        )
        result = {
            "status": "complete",
            **report.as_dict(),
            **store.counts(),
            "round_started_at": store.get("round_started_at"),
            "round_completed_at": store.get("round_completed_at"),
            "finished_at": datetime.now(UTC).isoformat(),
        }
        store.db.execute(
            "INSERT INTO runs(started_at, finished_at, rows_used, report_json) VALUES(?,?,?,?)",
            (report.started_at, result["finished_at"], report.rows_used, json.dumps(result)),
        )
        store.commit()
        return result
    finally:
        await client.aclose()
        store.close()
        lock.close()


def main() -> int:
    if os.getenv("PRIMAT_ICA_CATALOG_ENABLED", "false").casefold() != "true":
        print(json.dumps({"primat_ica_catalog": {"status": "disabled"}}), flush=True)
        return 0
    try:
        result = asyncio.run(_run())
        code = 0
    except Exception as exc:  # noqa: BLE001 - report the class, never the payload
        result = {"status": "failed", "error_type": type(exc).__name__,
                  "finished_at": datetime.now(UTC).isoformat()}
        code = 1
    status_path = _root() / "reports" / "operations" / "primat-ica-catalog.json"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(status_path, json.dumps(result, ensure_ascii=False, indent=2).encode())
    print(json.dumps({"primat_ica_catalog": result}, ensure_ascii=False), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
