"""Run the existing managed refresh once, then hot-swap the serving runtime.

This file is orchestration only.  Collection, candidate validation, content-
addressed storage and atomic/LKG activation remain owned by ``daily-refresh``.
The serving process is asked to load the already activated, hash-verified
manifest only after the CLI returned a usable result (exit 0 or degraded 2).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import make_url

from grocery_data.app.services.coop_refresh_configuration import (
    assess_coop_refresh_configuration,
)
from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.manual_refresh_operations import (
    REFRESH_PARENT_LOCK_NONCE_ENV,
    RefreshAlreadyRunningError,
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)


class RuntimeReloadUnavailable(RuntimeError):
    """The serving process could not be reached after disk activation."""


class RuntimeReloadRejected(RuntimeError):
    """The serving process reached the endpoint but rejected the candidate."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"required production setting is missing: {name}")
    return value


def build_refresh_command() -> list[str]:
    city = os.getenv("REFRESH_CITY", "Lund").strip() or "Lund"
    postal_code = os.getenv("REFRESH_POSTAL_CODE", "22350").strip()
    if len(postal_code) != 5 or not postal_code.isdigit():
        raise ValueError("REFRESH_POSTAL_CODE must contain five digits")
    report_dir = os.getenv(
        "REFRESH_REPORT_DIR",
        "/srv/app/var/reports/refresh",
    ).strip()
    universe_root = _required("PRICE_UNIVERSE_CACHE_ROOT")
    return [
        sys.executable,
        "-m",
        "grocery_data",
        "daily-refresh",
        "--city",
        city,
        "--postal-code",
        f"{city}={postal_code}",
        "--price-universe-cache-root",
        universe_root,
        "--report-dir",
        report_dir,
        "--format",
        "json",
    ]


def _reload_runtime() -> dict[str, Any]:
    try:
        base_url = _required("INTERNAL_APP_BASE_URL").rstrip("/")
        token = _required("BETA_ADMIN_TOKEN")
    except RuntimeError as exc:
        raise RuntimeReloadUnavailable("RuntimeReloadConfigurationMissing") from exc
    request = urllib.request.Request(
        f"{base_url}/api/admin/reload-price-universe",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": f"scheduled-refresh-{uuid4().hex}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeReloadRejected(type(exc).__name__) from None
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeReloadUnavailable(type(exc).__name__) from None
    except (UnicodeError, ValueError) as exc:
        raise RuntimeReloadRejected(type(exc).__name__) from None
    if not isinstance(payload, dict):
        raise RuntimeReloadRejected("NonObjectResponse")
    required = {"old_price_universe_id", "new_price_universe_id", "changed"}
    if not required.issubset(payload):
        raise RuntimeReloadRejected("IncompleteResponse")
    return {
        key: payload.get(key)
        for key in (
            "status",
            "old_price_universe_id",
            "new_price_universe_id",
            "changed",
            "pricing_projection",
            "plan_prewarm",
        )
        if key in payload
    }


def _write_status(payload: dict[str, Any]) -> None:
    destination = Path(
        os.getenv(
            "REFRESH_RUNNER_STATUS_PATH",
            "/srv/app/var/reports/operations/refresh-runner-status.json",
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    atomic_write_bytes(
        destination,
        encoded,
        validator=lambda candidate: json.loads(candidate.read_bytes()),
    )


def _artifact_store() -> PreparedUniverseArtifactStore:
    return PreparedUniverseArtifactStore(Path(_required("PRICE_UNIVERSE_CACHE_ROOT")))


def _operations_lock() -> RefreshRunLock:
    database_url = make_url(_required("GROCERY_DATABASE_URL"))
    if database_url.get_backend_name() != "sqlite" or not database_url.database:
        raise RuntimeError("production refresh serialization requires file-backed SQLite")
    database = Path(database_url.database).expanduser().resolve(strict=True)
    universe_root = Path(_required("PRICE_UNIVERSE_CACHE_ROOT"))
    return RefreshRunLock(production_refresh_lock_path(database, universe_root))


def _active_disk_universe_id(
    store: PreparedUniverseArtifactStore,
    *,
    city: str,
) -> str | None:
    """Return only the validated active manifest identity when available."""

    reader = getattr(store, "read_active", None)
    if not callable(reader):
        return None
    try:
        manifest = reader(city)
    except (OSError, ValueError):
        return None
    value = getattr(manifest, "universe_id", None)
    return value if isinstance(value, str) and value else None


def _restore_restart_lkg(
    store: PreparedUniverseArtifactStore,
    *,
    city: str,
    previous: bytes | None,
    promoted: bytes | None,
) -> dict[str, Any]:
    """Restore the pre-refresh restart pointer, leaving candidate bytes intact."""

    if previous is not None:
        from grocery_data.app.services.prepared_universe_activation import (
            ActivePreparedUniverseManifest,
        )
        old = ActivePreparedUniverseManifest.model_validate_json(previous)
        observed = old.oldest_base_observed_at or old.oldest_observed_at
        if (datetime.now(UTC) - observed).total_seconds() >= 48 * 3600:
            return {"status": "not_restored", "reason": "previous_base_prices_expired",
                    "candidate_artifact_retained": True}
    store.restore_active_manifest(
        city,
        previous,
        expected_current=promoted,
    )
    return {
        "status": "restored_previous" if previous is not None else "removed_first_candidate",
        "candidate_artifact_retained": True,
    }


def _run_locked(
    operations_lock: RefreshRunLock,
    *,
    started_at: datetime,
    command: list[str] | None = None,
    run_kind: str = "daily_refresh",
    status_writer: Callable[[dict[str, Any]], None] | None = None,
) -> int:
    command = command or build_refresh_command()
    timeout_seconds = int(os.getenv("REFRESH_TIMEOUT_SECONDS", "7200"))
    if not 300 <= timeout_seconds <= 7200:
        raise ValueError("REFRESH_TIMEOUT_SECONDS must be between 300 and 7200")
    city = command[command.index("--city") + 1]
    artifact_store = _artifact_store()
    previous_manifest = artifact_store.active_manifest_bytes(city)
    previous_manifest_state = "missing"
    if previous_manifest is not None:
        # A corrupt pointer is not an LKG, but it must not block refresh from
        # repairing first boot. Never restore it after a later reload rejection.
        try:
            artifact_store.resolve_active_artifact(city, verify_hash=True)
            previous_manifest_state = "verified"
        except (OSError, ValueError):
            previous_manifest = None
            previous_manifest_state = "invalid"
    status: dict[str, Any] = {
        "schema_version": (
            "source-retry-runner-v1"
            if run_kind == "coop_source_retry"
            else "production-refresh-runner-v1"
        ),
        "started_at": started_at.isoformat(),
        "city": city,
        "run_kind": run_kind,
        "coop_source_configuration": assess_coop_refresh_configuration(
            os.environ
        ).sanitized_report(),
        "previous_restart_manifest": previous_manifest_state,
    }
    try:
        if operations_lock.info is None:
            raise RuntimeError("outer refresh operation lock is not held")
        if run_kind == "daily_refresh" and os.getenv("WILLYS_COLLECTION_LOCATION") == "LOCAL_RELAY":
            from grocery_data.app.config import GroceryDataSettings
            from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
            from grocery_data.app.services.source_artifact import import_source_inbox
            from grocery_data.app.storage import create_database_engine, create_session_factory

            relay_settings = GroceryDataSettings.from_env()
            relay_engine = create_database_engine(relay_settings.database_url)
            try:
                status["source_relay_imports"] = asyncio.run(
                    import_source_inbox(
                        create_session_factory(relay_engine),
                        FilesystemRawSnapshotStore(relay_settings.raw_snapshot_root),
                        Path(
                            os.getenv(
                                "SOURCE_RELAY_INBOX",
                                "/srv/app/var/raw_snapshots/source-inbox/willys",
                            )
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - isolate asynchronous source arrivals
                status["source_relay_imports"] = [
                    {"status": "failed", "error_type": type(exc).__name__}
                ]
            finally:
                relay_engine.dispose()
        child_environment = dict(os.environ)
        child_environment[REFRESH_PARENT_LOCK_NONCE_ENV] = operations_lock.info.owner_nonce
        completed = subprocess.run(
            command,
            check=False,
            timeout=timeout_seconds,
            env=child_environment,
        )
        status["refresh_exit_code"] = completed.returncode
        exit_code = completed.returncode
        if completed.returncode in {0, 2}:
            promoted_manifest = artifact_store.active_manifest_bytes(city)
            try:
                status["runtime_reload"] = _reload_runtime()
            except RuntimeReloadUnavailable as exc:
                # Disk activation is valid and may be the only way a crash-looping
                # app can recover on restart. Do not restore the older pointer.
                status["runtime_reload"] = {
                    "status": "deferred",
                    "reason": "app_unavailable",
                    "error_type": type(exc).__name__,
                }
                disk_universe_id = _active_disk_universe_id(
                    artifact_store,
                    city=city,
                )
                if disk_universe_id is not None:
                    status["runtime_reload"]["disk_price_universe_id"] = disk_universe_id
                status["disk_manifest_rollback"] = {
                    "status": "not_attempted",
                    "reason": "candidate_retained_for_restart",
                }
                exit_code = 2
            except RuntimeReloadRejected as exc:
                status["runtime_reload"] = {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                }
                try:
                    status["disk_manifest_rollback"] = _restore_restart_lkg(
                        artifact_store,
                        city=city,
                        previous=previous_manifest,
                        promoted=promoted_manifest,
                    )
                except Exception as rollback_exc:  # noqa: BLE001 - report class only
                    status["disk_manifest_rollback"] = {
                        "status": "failed",
                        "error_type": type(rollback_exc).__name__,
                    }
                exit_code = 1
        else:
            status["runtime_reload"] = {
                "status": "not_attempted",
                "reason": "refresh_not_usable",
            }
    except Exception as exc:  # noqa: BLE001 - outer operational boundary
        # Preserve the server's in-memory LKG and publish only an allowlisted
        # error class. No exception text is retained.
        exit_code = 1
        status.update(
            {
                "refresh_exit_code": None,
                "runtime_reload": {"status": "not_attempted"},
                "error_type": type(exc).__name__,
            }
        )
    status["completed_at"] = datetime.now(UTC).isoformat()
    status["exit_code"] = exit_code
    status["status"] = "complete" if exit_code == 0 else "degraded" if exit_code == 2 else "failed"
    from grocery_data.app.services.coop_offer_job import record_publication
    try:
        record_publication(status=status, disk_universe_id=_active_disk_universe_id(artifact_store, city=city))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        status["coop_publication_state_error"] = type(exc).__name__
        if exit_code == 0:
            exit_code = 2
            status.update(exit_code=2, status="degraded")
    from grocery_data.app.services.citygross_municipal_job import (
        record_publication as record_citygross,
    )
    try:
        record_citygross(status=status, disk_universe_id=_active_disk_universe_id(artifact_store, city=city))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        status["citygross_publication_state_error"] = type(exc).__name__
        if exit_code == 0:
            exit_code = 2
            status.update(exit_code=2, status="degraded")
    from grocery_data.app.services.lidl_municipal_job import (
        record_publication as record_lidl,
    )
    try:
        record_lidl(status=status, disk_universe_id=_active_disk_universe_id(artifact_store, city=city))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        status["lidl_publication_state_error"] = type(exc).__name__
    from grocery_data.app.services.willys_flyer_job import record_publication as record_willys_flyer
    try:
        record_willys_flyer(status=status, disk_universe_id=_active_disk_universe_id(artifact_store, city=city))
    except (OSError, ValueError, KeyError) as exc:
        status["willys_flyer_publication_state_error"] = type(exc).__name__
        if exit_code == 0:
            exit_code = 2
            status.update(exit_code=2, status="degraded")
    (status_writer or _write_status)(status)
    return exit_code


def demand_refresh_plan(*, now: datetime, environment=None) -> dict:
    """Local due-time inspection only; durable state is shared with this runner.

    Base scope is derived from the serving artifact's required contexts, never
    from a second hand-maintained retailer list. No retailer calls happen here.
    """
    import hashlib
    import sqlite3
    from datetime import timedelta

    from grocery_data.app.services.campaign_refresh_policy import base_fetch_due

    env = os.environ if environment is None else environment
    city = env.get("REFRESH_CITY", "Lund")
    root = Path(env["PRICE_UNIVERSE_CACHE_ROOT"])
    database = Path(make_url(env["GROCERY_DATABASE_URL"]).database)
    state_path = Path(env.get("DEMAND_REFRESH_STATE_PATH", str(root.parent / "reports/operations/demand-refresh.json")))
    state = json.loads(state_path.read_bytes()) if state_path.exists() else {}
    store = PreparedUniverseArtifactStore(root)
    manifest = store.read_active(city)
    required = set(filter(None, env.get("PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS", "").split(",")))
    if not state.get("base_scope") or state.get("scope_universe_id") != manifest.universe_id:
        artifact = json.loads(store.resolve_active_artifact(city, verify_hash=True).read_bytes())
        state["base_scope"] = [s for s in artifact["stores"]
            if (not required or s['store_id'] in required)
            and s.get('source_provenance', {}).get('source_channel') == 'catalog']
        if not state["base_scope"]:
            raise ValueError('no verified base scope for demand refresh')
        state["scope_universe_id"] = manifest.universe_id
    offer_root = Path(env.get('ICA_STRUCTURED_OFFERS_ROOT', str(database.parent / 'ica-structured-offers')))
    from grocery_data.app.services.ica_offer_job import source_location
    _area, offer_location = source_location(city, offer_root, environment=env)
    pointer = offer_location / 'structured-source.json'
    offers = json.loads(pointer.read_bytes()) if pointer.exists() else {}
    from grocery_data.app.services.hemkop_municipal_job import source_plan as hemkop_source_plan
    hemkop_plan = hemkop_source_plan(city=city, environment=env, now=now)
    offer_enabled = env.get('ICA_STRUCTURED_OFFERS_ENABLED', 'false').casefold() == 'true'
    campaign_times = [datetime.fromisoformat(v['next_fetch_at']) for v in offers.get('store_schedule', {}).values()]
    from grocery_data.app.services.coop_offer_job import source_plan
    coop_plan = source_plan(environment=env, now=now)
    from grocery_data.app.services.citygross_municipal_job import (
        source_plan as citygross_source_plan,
    )
    citygross_plan = citygross_source_plan(environment=env, now=now)
    from grocery_data.app.services.lidl_municipal_job import source_plan as lidl_source_plan
    lidl_plan = lidl_source_plan(environment=env, now=now)
    from grocery_data.app.services.willys_flyer_job import source_plan as willys_flyer_source_plan
    willys_flyer_plan = willys_flyer_source_plan(environment=env, now=now)
    willys_flyer_times = [datetime.fromisoformat(r["next_fetch_at"]) for r in willys_flyer_plan["stores"] if r.get("next_fetch_at")]
    lidl_times = [datetime.fromisoformat(r["next_fetch_at"]) for r in lidl_plan["stores"] if r.get("next_fetch_at")]
    coop_times = [datetime.fromisoformat(r["next_fetch_at"]) for r in coop_plan["stores"] if r.get("next_fetch_at")]
    citygross_times = [datetime.fromisoformat(r["next_fetch_at"]) for r in citygross_plan["stores"] if r.get("next_fetch_at")]
    hemkop_times = [datetime.fromisoformat(r['next_fetch_at']) for r in hemkop_plan['store_schedule'].values()]
    campaign_at = min([*(campaign_times if offer_enabled else []), *coop_times, *citygross_times, *lidl_times, *willys_flyer_times, *hemkop_times], default=None)
    sources = {}
    with sqlite3.connect(f'file:{database.as_posix()}?mode=ro', uri=True) as db:
        for physical in state['base_scope']:
            prov = physical['source_provenance']
            if (physical['chain'] == 'citygross' and citygross_plan['enabled']) or (physical['chain'] == 'lidl' and lidl_plan['enabled']):
                continue
            if prov['source_provider'] != 'own':
                continue
            row = db.execute("""SELECT cs.id, min(sp.fetched_at) FROM source_products sp
                JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id
                WHERE cs.is_active=1 AND cs.state='promoted' AND cs.coverage != 'offers_only'
                  AND sp.chain=? AND sp.store_external_id=?
                GROUP BY cs.id ORDER BY cs.promoted_at DESC LIMIT 1""",
                (physical['chain'], prov['provider_store_id'])).fetchone()
            key = physical['chain']
            item = sources.setdefault(key, {'observations': [], 'snapshots': []})
            if row and row[1]:
                item['observations'].append(row[1]); item['snapshots'].append(row[0])
            else:
                item['missing'] = True
    if any(s['source_provenance']['source_provider'] == 'primat' for s in state['base_scope']):
        from grocery_data.app.services.closed_provider_cache_store import (
            ClosedProviderCacheArtifactStore,
        )
        from grocery_data.app.services.freshness import FreshnessPolicy
        resolved = ClosedProviderCacheArtifactStore(root / 'external-provider-cache').resolve_active(city, policy=FreshnessPolicy())
        if resolved:
            # Manifest captured_at is the verified conservative original source observation.
            ext_manifest = json.loads((root / 'external-provider-cache/active' / ('city-' + city.casefold() + '.json')).read_bytes())
            sources['primat'] = {'observations': [ext_manifest['captured_at']], 'snapshots': ext_manifest['snapshot_ids']}
        else:
            sources['primat'] = {'observations': [], 'snapshots': [], 'missing': True}
    due_sources = []
    for key, source in sources.items():
        observed = min((datetime.fromisoformat(x) for x in source['observations']), default=None)
        # The local relay owns its independent durable 35-hour timer. A VPS
        # campaign tick cannot advance it; do not advertise an earlier fetch.
        relay_source = key == 'willys' and env.get('WILLYS_COLLECTION_LOCATION') == 'LOCAL_RELAY'
        due = now if observed is None or source.get('missing') else base_fetch_due(
            observed, now=now, campaign_at=None if relay_source else campaign_at)
        retry = state.get('source_retries', {}).get(key)
        if retry and retry['snapshots'] == source['snapshots']:
            due = max(due, datetime.fromisoformat(retry['retry_at']))
        source.update(next_fetch_at=due.isoformat(), reason='local_relay_35h_deadline' if relay_source else 'base_35h_deadline_or_campaign_coalescing',
                      observed_at=observed.isoformat() if observed else None,
                      hard_stop_at=(observed + timedelta(hours=48)).isoformat() if observed else None)
        if due <= now:
            due_sources.append(key)
    transitions = [datetime.fromisoformat(v['next_transition_at']) for v in offers.get('store_schedule', {}).values() if v.get('next_transition_at')]
    last = datetime.fromisoformat(state.get('last_success_at', '1970-01-01T00:00:00+00:00'))
    local_transition = any(last < t <= now for t in transitions)
    offer_due = offer_enabled and (not offers or any(t <= now for t in campaign_times)
        or datetime.fromisoformat(offers['next_inventory_at']) <= now)
    fingerprint = hashlib.sha256(json.dumps({'base': {k:v['snapshots'] for k,v in sources.items()},
        'offers': offers.get('database') if offer_enabled else None, 'hemkop_municipal': hemkop_plan['fingerprint'], 'coop': coop_plan['fingerprint'], 'citygross': citygross_plan['fingerprint'], 'lidl': lidl_plan['fingerprint'], 'willys_flyer': willys_flyer_plan['fingerprint']}, sort_keys=True).encode()).hexdigest()
    changed = fingerprint != state.get('published_sources')
    reasons = (["source_promotion_pending_publication"] if changed else []) + (["campaign_transition"] if local_transition else []) + (["ica_source_due"] if offer_due else [])
    if coop_plan["work_due"]:
        reasons.append("coop_municipal_work_due")
    if hemkop_plan['work_due']:
        reasons.append('hemkop_municipal_work_due')
    if willys_flyer_plan["work_due"]:
        reasons.append("willys_flyer_work_due")
    if lidl_plan["work_due"]:
        reasons.append("lidl_municipal_work_due")
    if citygross_plan["work_due"]:
        reasons.append("citygross_municipal_work_due")
    remote_due = [k for k in due_sources if k != 'willys' or env.get('WILLYS_COLLECTION_LOCATION') != 'LOCAL_RELAY']
    work = bool(remote_due or reasons)
    if state.get('retry_at') and datetime.fromisoformat(state['retry_at']) > now:
        work = False
    state_path.parent.mkdir(parents=True, exist_ok=True)
    return {'work_due': work, 'reasons': reasons, 'sources': sources, 'due_sources': remote_due,
        'hemkop_municipal': hemkop_plan, 'coop_municipal': coop_plan, 'citygross_municipal': citygross_plan, 'lidl_municipal': lidl_plan, 'willys_flyer': willys_flyer_plan, 'relay_due': 'willys' in due_sources, 'ica_store_schedule': offers.get('store_schedule', {}),
        'source_fingerprint': fingerprint, 'state': state, 'state_path': str(state_path),
        'checked_at': now.isoformat(), 'external_price_requests': 0}


def _run_demand_locked(lock, *, started_at):
    from datetime import timedelta
    plan = demand_refresh_plan(now=started_at)
    state, path = plan.pop('state'), Path(plan.pop('state_path'))
    if not plan['work_due']:
        state['last_check'] = plan
        atomic_write_bytes(path, json.dumps(state, ensure_ascii=False).encode())
        _write_status({'status': 'not_due', **plan})
        return 0
    command = build_refresh_command()
    chains = [k for k in plan['due_sources'] if k != 'primat']
    for chain in chains or ['citygross']:  # existing local-only rebuild path
        command.extend(['--chain', chain])
    if 'primat' not in plan['due_sources']:
        command.append('--no-external-refresh')
    code = _run_locked(lock, started_at=started_at, command=command)
    ended = datetime.now(UTC)
    after = demand_refresh_plan(now=ended)
    state.update(after['state'])
    state['last_check'] = {k:v for k,v in after.items() if k not in {'state', 'state_path'}}
    retries = state.setdefault('source_retries', {})
    for key in plan['due_sources']:
        old, new = plan['sources'][key], after['sources'][key]
        if old['snapshots'] == new['snapshots']:
            failures = retries.get(key, {}).get('failures', 0) + 1
            retries[key] = {'snapshots': new['snapshots'], 'failures': failures,
                'retry_at': (ended + timedelta(minutes=min(360, 15 * 2 ** min(failures-1,5)))).isoformat()}
        else:
            retries.pop(key, None)
    if code in {0, 2}:
        state.update(last_success_at=ended.isoformat(), published_sources=after['source_fingerprint'], failures=0)
        state.pop('retry_at', None)
    else:
        failures = state.get('failures', 0) + 1
        state.update(failures=failures, retry_at=(ended + timedelta(minutes=min(360, 15 * 2 ** min(failures-1,5)))).isoformat())
    atomic_write_bytes(path, json.dumps(state, ensure_ascii=False).encode())
    return code


def main() -> int:
    if os.getenv("SMAKO_RECOVERY_READ_ONLY", "").lower() == "true":
        print(json.dumps({"status": "unavailable", "code": "recovery_read_only"}))
        return 3
    started_at = datetime.now(UTC)
    city = os.getenv("REFRESH_CITY", "Lund").strip() or "Lund"
    operations_lock = _operations_lock()
    try:
        operations_lock.acquire()
    except RefreshAlreadyRunningError:
        completed_at = datetime.now(UTC)
        _write_status(
            {
                "schema_version": "production-refresh-runner-v1",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "city": city,
                "refresh_exit_code": None,
                "runtime_reload": {
                    "status": "not_attempted",
                    "reason": "operation_lock_held",
                },
                "status": "degraded",
                "exit_code": 2,
            }
        )
        return 2
    try:
        if os.getenv("DEMAND_REFRESH_ENABLED", "false").casefold() == "true":
            return _run_demand_locked(operations_lock, started_at=started_at)
        return _run_locked(operations_lock, started_at=started_at)
    finally:
        operations_lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
