"""Optional municipal sources in the ordinary locked refresh/build lifecycle.

Immutable OWN snapshots, atomic pointers, no additional pricing or scheduler.
The caller holds the existing refresh operation lock for all mutations.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from grocery_data.app.services.area_membership import approved_municipal_stores
from grocery_data.app.services.coop_municipal_refresh import update_selection
from grocery_data.app.services.durable_files import atomic_write_bytes


def read(path):
    return json.loads(path.read_bytes()) if path.exists() else {}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(path, json.dumps(value, ensure_ascii=False, sort_keys=True).encode())


def configuration(environment=None):
    env = os.environ if environment is None else environment
    database = Path(make_url(env.get("GROCERY_DATABASE_URL", "sqlite:///var/grocery/grocery_data.sqlite")).database)
    root = Path(env.get("COOP_MUNICIPAL_OFFERS_ROOT", str(database.parent / "coop-municipal-offers")))
    saved = read(root / "config.json")
    def flag(key, fallback):
        return env.get(key, str(saved.get(fallback, False))).casefold() == "true"
    code = env.get("COOP_MUNICIPALITY_CODE", saved.get("municipality_code"))
    from grocery_data.app.domain.municipality import municipality_name
    fallback_city = saved.get("city") if code == saved.get("municipality_code") else None
    config = {"enabled": flag("COOP_MUNICIPAL_OFFERS_ENABLED", "enabled"),
              "xtra_enabled": flag("COOP_XTRA_OFFERS_ENABLED", "xtra_enabled"),
              "municipality_code": code,
              "city": env.get("COOP_MUNICIPAL_BUILD_CITY") or env.get("REFRESH_CITY") or fallback_city or (municipality_name(code) if code else "")}
    if config["enabled"] and municipality_name(config["municipality_code"]).casefold() != config["city"].casefold():
        raise ValueError("Coop build locality must match the selected municipality")
    return root, config


def location(root, config):
    return root / str(config["municipality_code"]) / "source-state.json"


def enabled_rows(state, config):
    return [r for r in state.get("selection", {}).get("stores", []) if r["selected"]
            and (r["concept"] != "X:-tra" or config["xtra_enabled"])] if config["enabled"] else []


def source_plan(*, environment=None, now=None):
    try:
        return _source_plan(environment=environment, now=now)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"enabled": False, "fingerprint": "invalid_optional_coop_configuration",
                "work_due": False, "due_store_ids": [], "inventory_due": False,
                "publication_due": False, "stores": [], "publication": {},
                "status": "optional_configuration_error", "error_type": type(exc).__name__,
                "external_price_requests": 0}


def _source_plan(*, environment=None, now=None):
    now = now or datetime.now(UTC)
    root, config = configuration(environment)
    state = read(location(root, config))
    rows = enabled_rows(state, config)
    refs = {r["store_id"]: state.get("approved", {}).get(r["store_id"], []) for r in rows}
    # Applicability is part of the local build version, never a fresh observation.
    from grocery_data.app.services.campaign_refresh_policy import STOCKHOLM
    day = now.astimezone(STOCKHOLM).date().isoformat()
    applicability = {identity: [{"sha256": r["sha256"], "snapshots": r["snapshots"],
        "fresh": now < datetime.fromisoformat(r["observed_at"]) + timedelta(hours=48),
        "windows": [(w.get("valid_from"), w.get("valid_to"),
                     bool(w.get("valid_to") and (not w.get("valid_from") or w["valid_from"] <= day) and day <= w["valid_to"]))
                    for w in r.get("windows", [])]} for r in values] for identity, values in refs.items()}
    fingerprint = hashlib.sha256(json.dumps({"config": config, "sources": applicability}, sort_keys=True).encode()).hexdigest()
    from grocery_data.app.services.campaign_refresh_policy import scheduled_source_times
    inventory_fetch = scheduled_source_times(rows, state=state, now=now, environment=environment)
    due = [r["store_id"] for r in rows if not r.get("next_fetch_at") or datetime.fromisoformat(r["next_fetch_at"]) <= now]
    inventory_due = config["enabled"] and (not state or datetime.fromisoformat(state["selection"]["next_inventory_check"]) <= now)
    if inventory_fetch is not None:
        inventory_due = config["enabled"] and inventory_fetch <= now
    publication = state.get("publication", {})
    changed = bool(state) and (fingerprint != publication.get("reloaded_fingerprint")
                              or publication.get("status") == "publication_or_reload_pending")
    retry = publication.get("retry_at")
    publication_due = changed and (not retry or datetime.fromisoformat(retry) <= now)
    return {"enabled": config["enabled"], "fingerprint": fingerprint,
            "work_due": bool(due or inventory_due or publication_due), "due_store_ids": due,
            "inventory_due": inventory_due, "publication_due": publication_due,
            "stores": rows, "publication": publication, "external_price_requests": 0}


def approved_reference(database, identity, *, root, outcome):
    database = database.resolve(strict=True)
    if not database.is_relative_to(root.resolve()):
        raise ValueError("source escaped durable owned root")
    with sqlite3.connect(f"file:{database.as_posix()}?mode=ro", uri=True) as db:
        snapshots = [r[0] for r in db.execute("""SELECT DISTINCT cs.id FROM catalog_snapshots cs
            JOIN source_products sp ON sp.catalog_snapshot_id=cs.id
            WHERE cs.is_active=1 AND cs.state='promoted' AND cs.coverage='offers_only'
              AND sp.chain='coop' AND sp.store_external_id=?""", (identity,))]
    if not snapshots:
        raise ValueError("no approved store-bound snapshot")
    return {"database": str(database.relative_to(root.resolve())),
            "sha256": hashlib.sha256(database.read_bytes()).hexdigest(), "snapshots": sorted(snapshots),
            "observed_at": outcome["observed_at"], "windows": outcome.get("windows", [])}


async def run_offer_job(*, environment=None, now=None):
    """Called once by daily-refresh under its existing parent/operation lock."""
    from grocery_data.app.connectors.coop.municipality_inventory import discover
    from grocery_data.app.domain import GeographicArea
    from grocery_data.app.domain.municipality import municipality_name
    from grocery_data.scripts.collect_coop_municipality import collect_xtra
    from grocery_data.scripts.collect_coop_physical_offers import collect

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
            seed = env.get("COOP_MUNICIPAL_INVENTORY") if not inventory else None
            inventory = read(Path(seed)) if seed else await discover(GeographicArea(
                city=municipality_name(config["municipality_code"]), mode="municipality",
                municipality_code=config["municipality_code"]), attempt / "inventory")
            if inventory["area"]["municipality_code"] != config["municipality_code"]:
                raise ValueError("wrong municipality")
            approved_municipal_stores(inventory, concepts=("Coop", "Stora Coop", "X:-tra"))
            state["inventory_status"] = {"status": "success", "checked_at": now.isoformat()}
        except Exception as exc:  # noqa: BLE001 - optional discovery cannot stop base
            state["inventory_status"] = {"status": "failed", "error_type": type(exc).__name__, "checked_at": now.isoformat()}
            inventory = state.get("inventory")
            if not inventory:
                state.update(selection={"stores": [], "next_inventory_check": (now + timedelta(minutes=15)).isoformat()})
                write(path, state)
                return {"status": "inventory_failed"}
    selection = update_selection(inventory, previous=state.get("selection"), now=now)
    old_signatures = {r["store_id"]: r["source_signature"] for r in state.get("selection", {}).get("stores", [])}
    changed_sources = {r["store_id"] for r in selection["stores"]
                       if r["store_id"] in old_signatures and old_signatures[r["store_id"]] != r["source_signature"]}
    if plan["inventory_due"]:
        selection["next_inventory_check"] = (now + timedelta(hours=72) if state["inventory_status"]["status"] == "success" else now + timedelta(minutes=15)).isoformat()
    approved = approved_municipal_stores(inventory, concepts=("Coop", "Stora Coop", "X:-tra"))
    chosen = {i for i in selection["due_store_ids"] if config["xtra_enabled"] or approved[i].source_fields["concept"] != "X:-tra"}
    structured = {i for i in chosen if approved[i].source_fields["concept"] != "X:-tra"}
    outcomes, references = {}, {}
    if structured:
        try:
            result = await collect(inventory, structured, attempt / "structured")
            for row in result["stores"]:
                identity = row["store_id"]
                parsed = read(attempt / "structured/sources" / (identity + "-extracted.json"))
                windows = [{k: o.get(k) for k in ("valid_from", "valid_to")} for p in parsed.get("products", []) for o in p["offers"]]
                outcomes[identity] = {**row, "windows": windows, "source_version": row.get("source_hash")}
                if (row["status"] == "rejected" or row["status"] == "partial_candidate" and not parsed.get("products")) and parsed and not parsed.get("failures") and not row["qualification"]["shared_blockers"]:
                    # Successful authoritative response, no qualified current rows:
                    # old offers were withdrawn/replaced, not a transport failure.
                    outcomes[identity]["status"] = "confirmed_no_qualified_rows"
                    references[identity] = []
                elif row["status"] == "partial_candidate":
                    try:
                        references[identity] = [approved_reference(attempt / "structured/own.sqlite", identity, root=root, outcome=outcomes[identity])]
                    except (OSError, ValueError, sqlite3.Error) as exc:
                        outcomes[identity].update(status="approved_reference_failed", error_type=type(exc).__name__)
        except Exception as exc:  # noqa: BLE001
            for identity in structured:
                outcomes.setdefault(identity, {"status": "failed", "error_type": type(exc).__name__})
    for identity in chosen - structured:
        row = next(r for r in inventory["stores"] if r["store"]["external_id"] == identity)
        try:
            outcome, _ = await collect_xtra(row, inventory, attempt / ("xtra-" + identity))
            outcomes[identity] = outcome
            if outcome["status"] == "partial_text_candidate":
                refs = []
                for edition in outcome["editions"]:
                    if edition.get("own"):
                        refs.append(approved_reference(Path(edition["directory"]) / "import/own.sqlite", identity, root=root, outcome=outcome))
                references[identity] = refs
        except Exception as exc:  # noqa: BLE001
            outcomes[identity] = {"status": "failed", "error_type": type(exc).__name__}
    state.update(schema_version="coop-municipal-source-v1", municipality_code=config["municipality_code"],
                 inventory=inventory, selection=update_selection(inventory, outcomes, previous=selection, now=now),
                 last_attempt_at=now.isoformat(), last_outcomes=outcomes)
    prior = {k: v for k, v in state.get("approved", {}).items() if k not in changed_sources}
    # Removed/unknown stores cannot survive as approved municipal sources.
    state["approved"] = {k: v for k, v in {**prior, **references}.items() if k in approved}
    if references:
        state["last_source_approval_at"] = now.isoformat()
    write(path, state)
    return {"status": "completed", "attempt": str(attempt), "outcomes": outcomes}


def source_inputs(*, city, environment=None):
    try:
        return _source_inputs(city=city, environment=environment)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"coop_offer_source_errors": [{"status": "optional_configuration_error", "error_type": type(exc).__name__}]}


def _source_inputs(*, city, environment=None):
    root, config = configuration(environment)
    if not config["enabled"] or city.casefold() != config["city"].casefold():
        return {}
    state = read(location(root, config))
    if state and state.get("inventory", {}).get("area", {}).get("municipality_code") != config["municipality_code"]:
        raise ValueError("Coop source inventory belongs to another municipality")
    grouped, errors = {}, []
    for row in enabled_rows(state, config):
        identity = row["store_id"]
        for ref in state.get("approved", {}).get(identity, []):
            try:
                database = (root / ref["database"]).resolve(strict=True)
                if not database.is_relative_to(root.resolve()) or hashlib.sha256(database.read_bytes()).hexdigest() != ref["sha256"]:
                    raise ValueError("source integrity mismatch")
                key = (str(database), row["concept"] == "X:-tra")
                group = grouped.setdefault(key, {"database": database, "include_xtra": key[1],
                    "inventory": {**state["inventory"], "selected_store_ids": []}})
                group["inventory"]["selected_store_ids"].append(identity)
            except (OSError, ValueError) as exc:
                # Corrupt optional source is excluded, never substituted by another store.
                errors.append({"store_id": identity, "status": "approved_source_unreadable", "error_type": type(exc).__name__})
    return {"coop_offer_sources": list(grouped.values()), "coop_offer_source_errors": errors}


def record_build(**kwargs):
    import sys

    from grocery_data.app.services.municipal_publication_receipts import record_build as record
    return record(sys.modules[__name__], **kwargs)


def record_publication(**kwargs):
    import sys

    from grocery_data.app.services.municipal_publication_receipts import (
        record_publication as record,
    )
    return record(sys.modules[__name__], **kwargs)
