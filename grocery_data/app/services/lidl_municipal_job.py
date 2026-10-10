"""Lidl offers adapter for the existing locked daily-refresh lifecycle.

Municipal selection and immutable OWN references are durable. All pricing,
source freshness, build, publication and reload use the existing components.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from grocery_data.app.domain.municipality import municipality_name
from grocery_data.app.services.campaign_refresh_policy import (
    STOCKHOLM,
    base_fetch_due,
    campaign_schedule,
)
from grocery_data.app.services.coop_offer_job import read, write


def configuration(environment=None):
    env = os.environ if environment is None else environment
    database = Path(make_url(env.get("GROCERY_DATABASE_URL", "sqlite:///var/grocery/grocery_data.sqlite")).database)
    root = Path(env.get("LIDL_MUNICIPAL_ROOT", str(database.parent / "lidl-municipal")))
    saved = read(root / "config.json")
    flag = env.get("LIDL_MUNICIPAL_ENABLED", str(saved.get("enabled", False))).casefold()
    if flag not in {"true", "false"}:
        raise ValueError("ambiguous Lidl municipality switch")
    code = env.get("LIDL_MUNICIPALITY_CODE", saved.get("municipality_code"))
    fallback_city = saved.get("city") if code == saved.get("municipality_code") else None
    config = {"enabled": flag == "true", "municipality_code": code,
              "city": env.get("LIDL_MUNICIPAL_BUILD_CITY") or env.get("REFRESH_CITY")
              or fallback_city or (municipality_name(code) if code else "")}
    if config["enabled"]:
        official_city = municipality_name(code)
        if config["city"].casefold() != official_city.casefold():
            raise ValueError("Lidl build locality must match the selected municipality")
    return root, config


def location(root, config):
    return root / str(config["municipality_code"]) / "source-state.json"


def _approved(inventory):
    from grocery_data.app.connectors.lidl.municipality_inventory import (
        approved_lidl_stores,
    )
    return approved_lidl_stores(inventory)


def update_selection(inventory, outcomes=None, *, previous=None, now=None):
    now = now or datetime.now(UTC)
    previous, outcomes = previous or {}, outcomes or {}
    code = inventory["area"]["municipality_code"]
    if previous and previous.get("municipality_code") != code:
        raise ValueError("source state belongs to another municipality")
    approved = _approved(inventory)
    old = {r["store_id"]: r for r in previous.get("stores", [])}
    rows = []
    for item in inventory["stores"]:
        store = item["store"]
        identity = store["external_id"]
        binding = {k: store.get(k) for k in ("external_id", "address", "postal_code", "city")}
        binding["source"] = {k: store["source_fields"].get(k) for k in (
            "canonical_url", "source_id_namespace", "official_store_url", "identity_conflict")}
        signature = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
        row = {"store_id": identity, "name": store["name"],
               "municipality_status": item["geographic_evidence"]["status"],
               "source_signature": signature, "selected": identity in approved, "due": False}
        if identity not in approved:
            row.update(status="not_selected", reason="municipality_or_source_identity_not_verified")
        elif identity in outcomes:
            result = outcomes[identity]
            failed = result["status"] not in {"success", "confirmed_no_qualified_rows"}
            count = old.get(identity, {}).get("failed_attempts", 0) + 1 if failed else 0
            observed = old.get(identity, {}).get("last_success") if failed else result.get("observed_at")
            windows = result.get("windows", [])
            schedule = campaign_schedule(windows, now=now, failed_attempts=count)
            if not failed and observed:
                base_due = base_fetch_due(datetime.fromisoformat(observed), now=now)
                if not windows or base_due < datetime.fromisoformat(schedule["next_fetch_at"]):
                    schedule.update(next_fetch_at=base_due.isoformat(), reason="base_35h_source_check")
            row.update(**schedule, status=result["status"], failed_attempts=count,
                       last_success=observed, last_attempt=now.isoformat())
            if observed:
                row["price_hard_stop_at"] = (datetime.fromisoformat(observed) + timedelta(hours=48)).isoformat()
        elif identity in old and old[identity].get("source_signature") == signature:
            row.update({k: v for k, v in old[identity].items()
                        if k not in {"selected", "due", "municipality_status"}})
            row["due"] = not row.get("next_fetch_at") or datetime.fromisoformat(row["next_fetch_at"]) <= now
        else:
            row.update(status="new_or_changed_source", reason="new_or_changed_source",
                       next_fetch_at=now.isoformat(), due=True)
        rows.append(row)
    return {"municipality_code": code, "stores": rows,
            "next_inventory_check": previous.get("next_inventory_check") or (now + timedelta(hours=72)).isoformat(),
            "due_store_ids": [r["store_id"] for r in rows if r["selected"] and r["due"]]}


def source_plan(*, environment=None, now=None):
    now = now or datetime.now(UTC)
    try:
        root, config = configuration(environment)
        state = read(location(root, config))
        rows = [r for r in state.get("selection", {}).get("stores", [])
                if r["selected"] and config["enabled"]]
        day = now.astimezone(STOCKHOLM).date().isoformat()
        refs = {r["store_id"]: [{"sha256": ref["sha256"], "snapshots": ref["snapshots"],
            "fresh": now < datetime.fromisoformat(ref["observed_at"]) + timedelta(hours=48),
            "windows": [(w.get("valid_from"), w.get("valid_to"),
                         (not w.get("valid_from") or w["valid_from"] <= day)
                         and bool(w.get("valid_to") and day <= w["valid_to"]))
                        for w in ref.get("windows", [])]}
            for ref in [*state.get("approved", {}).get(r["store_id"], []),
                        *state.get("partial_approved", {}).get(r["store_id"], [])]] for r in rows}
        fingerprint = hashlib.sha256(json.dumps({"config": config, "sources": refs}, sort_keys=True).encode()).hexdigest()
        due = [r["store_id"] for r in rows if not r.get("next_fetch_at") or datetime.fromisoformat(r["next_fetch_at"]) <= now]
        inventory_due = config["enabled"] and (not state or datetime.fromisoformat(state["selection"]["next_inventory_check"]) <= now)
        publication = state.get("publication", {})
        changed = bool(state) and (fingerprint != publication.get("reloaded_fingerprint")
                                  or publication.get("status") == "publication_or_reload_pending")
        retry = publication.get("retry_at")
        publication_due = changed and (not retry or datetime.fromisoformat(retry) <= now)
        return {"enabled": config["enabled"], "fingerprint": fingerprint,
                "work_due": bool(due or inventory_due or publication_due), "due_store_ids": due,
                "inventory_due": inventory_due, "publication_due": publication_due,
                "stores": rows, "publication": publication, "external_price_requests": 0}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"enabled": False, "fingerprint": "invalid_optional_lidl_configuration",
                "work_due": False, "due_store_ids": [], "inventory_due": False,
                "publication_due": False, "stores": [], "publication": {},
                "status": "optional_configuration_error", "error_type": type(exc).__name__,
                "external_price_requests": 0}


def approved_reference(database, identity, *, root, outcome):
    database = Path(database).resolve(strict=True)
    if not database.is_relative_to(root.resolve()):
        raise ValueError("source escaped durable owned root")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        rows = db.execute("""SELECT cs.id, min(sp.fetched_at), cs.coverage FROM catalog_snapshots cs
            JOIN source_products sp ON sp.catalog_snapshot_id=cs.id
            WHERE cs.is_active=1 AND cs.state='promoted'
              AND cs.coverage IN ('offers_only')
              AND sp.chain='lidl' AND sp.store_external_id=? GROUP BY cs.id""", (identity,)).fetchall()
    if not rows or any(not row[1] for row in rows):
        raise ValueError("no approved store-bound source observation")
    if len({r[2] for r in rows}) != 1:
        raise ValueError("ambiguous full/partial snapshot source")
    return {"database": str(database.relative_to(root.resolve())), "coverage": rows[0][2],
            "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
            "snapshots": sorted(r[0] for r in rows), "observed_at": min(r[1] for r in rows),
            "windows": outcome.get("windows", [])}


async def run_source_job(*, environment=None, now=None):
    from grocery_data.app.connectors.lidl.municipality_inventory import discover
    from grocery_data.app.domain import GeographicArea
    from grocery_data.scripts.collect_lidl_municipality import collect

    now = now or datetime.now(UTC)
    env = os.environ if environment is None else environment
    root, config = configuration(env)
    if not os.getenv("MUNICIPAL_REFRESH_SCOPE") and (config["enabled"] or (root / "config.json").exists()):
        write(root / "config.json", config)
    if not config["enabled"]:
        return {"status": "disabled", "external_price_requests": 0}
    path = location(root, config)
    state = read(path)
    plan = source_plan(environment=env, now=now)
    if not plan["due_store_ids"] and not plan["inventory_due"]:
        return {"status": "not_due", "external_price_requests": 0}
    attempt = path.parent / "attempts" / (now.strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:12])
    attempt.mkdir(parents=True)
    inventory = state.get("inventory")
    if plan["inventory_due"]:
        try:
            seed = env.get("LIDL_MUNICIPAL_INVENTORY") if not inventory else None
            inventory = read(Path(seed)) if seed else await discover(GeographicArea(
                city=municipality_name(config["municipality_code"]), mode="municipality",
                municipality_code=config["municipality_code"]), attempt / "inventory")
            if inventory["area"]["municipality_code"] != config["municipality_code"]:
                raise ValueError("wrong municipality")
            _approved(inventory)
            state["inventory_status"] = {"status": "success", "checked_at": now.isoformat()}
        except Exception as exc:  # noqa: BLE001 - isolate optional source
            state["inventory_status"] = {"status": "failed", "error_type": type(exc).__name__, "checked_at": now.isoformat()}
            inventory = state.get("inventory")
            if not inventory:
                state["selection"] = {"stores": [], "next_inventory_check": (now + timedelta(minutes=15)).isoformat()}
                write(path, state)
                return {"status": "inventory_failed"}
    selection = update_selection(inventory, previous=state.get("selection"), now=now)
    old_signatures = {r["store_id"]: r["source_signature"] for r in state.get("selection", {}).get("stores", [])}
    changed = {r["store_id"] for r in selection["stores"] if r["store_id"] in old_signatures
               and old_signatures[r["store_id"]] != r["source_signature"]}
    if plan["inventory_due"]:
        selection["next_inventory_check"] = (now + (timedelta(hours=72)
            if state["inventory_status"]["status"] == "success" else timedelta(minutes=15))).isoformat()
    chosen = set(selection["due_store_ids"])
    outcomes, references, partial_references = {}, {}, {}
    if chosen:
        try:
            result = await collect(inventory, chosen, attempt / "collection")
            outcomes = {r["store_id"]: r for r in result["stores"] if r["store_id"] in chosen}
        except Exception as exc:  # noqa: BLE001
            outcomes = {identity: {"status": "failed", "error_type": type(exc).__name__, "reason": str(exc)[:200]} for identity in chosen}
        for identity in chosen:
            row = outcomes.setdefault(identity, {"status": "failed", "reason": "collector_outcome_missing"})
            if row["status"] == "success":
                try:
                    database = row.get("resolved_database") or attempt / "collection" / row["database"]
                    ref = approved_reference(database, identity, root=root, outcome=row)
                    row["observed_at"] = ref["observed_at"]
                    references[identity] = [ref]
                    partial_references[identity] = []
                except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
                    row.update(status="approved_reference_failed", error_type=type(exc).__name__)
            elif row["status"] == "confirmed_no_qualified_rows":
                references[identity] = []
    state.update(schema_version="lidl-municipal-source-v1", municipality_code=config["municipality_code"],
                 inventory=inventory, selection=update_selection(inventory, outcomes, previous=selection, now=now),
                 last_attempt_at=now.isoformat(), last_outcomes=outcomes)
    approved = _approved(inventory)
    prior = {k: v for k, v in state.get("approved", {}).items() if k not in changed}
    state["approved"] = {k: v for k, v in {**prior, **references}.items() if k in approved}
    old_partial = {k: v for k, v in state.get("partial_approved", {}).items() if k not in changed}
    state["partial_approved"] = {k: v for k, v in {**old_partial, **partial_references}.items() if k in approved}
    if references or partial_references:
        state["last_source_approval_at"] = now.isoformat()
    write(path, state)
    return {"status": "completed", "attempt": str(attempt), "outcomes": outcomes,
            "selected_store_ids": sorted(approved)}


def source_inputs(*, city, environment=None, now=None):
    now = now or datetime.now(UTC)
    try:
        root, config = configuration(environment)
        if not config["enabled"] or city.casefold() != config["city"].casefold():
            return {}
        state = read(location(root, config))
        verified = _approved(state["inventory"]) if state.get("inventory") else {}
        sources, errors = [], []
        for identity, refs in state.get("approved", {}).items():
            if identity not in verified:
                continue
            for ref in refs:
                try:
                    database = (root / ref["database"]).resolve(strict=True)
                    if not database.is_relative_to(root.resolve()) or hashlib.sha256(database.read_bytes()).hexdigest() != ref["sha256"]:
                        raise ValueError("source integrity mismatch")
                    sources.append({"database": database, "snapshot_ids": ref["snapshots"],
                        "store_ids": [identity], "inventory": state["inventory"]})
                except (OSError, ValueError) as exc:
                    errors.append({"store_id": identity, "status": "approved_source_unreadable", "error_type": type(exc).__name__})
        return {"lidl_municipal_enabled": True, "lidl_sources": sources,
                "lidl_source_errors": errors}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"lidl_municipal_enabled": True,
                "lidl_source_errors": [{"status": "optional_configuration_error", "error_type": type(exc).__name__}]}


def record_build(**kwargs):
    from grocery_data.app.services.municipal_publication_receipts import record_build as record
    return record(sys.modules[__name__], **kwargs)


def record_publication(**kwargs):
    from grocery_data.app.services.municipal_publication_receipts import (
        record_publication as record,
    )
    return record(sys.modules[__name__], **kwargs)
