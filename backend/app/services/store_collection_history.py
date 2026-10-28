"""Read municipal offer-job history without collecting or changing source state."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from grocery_data.app.domain.municipality import municipality_code
from grocery_data.app.services.campaign_refresh_policy import scheduled_source_times


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.astimezone(UTC) if parsed.tzinfo else None
    except (TypeError, ValueError):
        return None


def _read(path):
    try:
        if path.stat().st_size > 16 * 1024 * 1024:
            return {}
        value = json.loads(path.read_bytes())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _mapping(value):
    return value if isinstance(value, dict) else {}


def offer_collection_history(city, database, *, now=None):
    """Index by exact chain/store identity, within a verified municipality."""
    code = municipality_code(city)
    if not code:
        return {}
    now = now or datetime.now(UTC)
    parent = Path(database or "var/grocery/grocery_data.sqlite").parent
    roots = {
        "ica": Path(os.getenv("ICA_STRUCTURED_OFFERS_ROOT", str(parent / "ica-structured-offers"))),
        "coop": Path(os.getenv("COOP_MUNICIPAL_OFFERS_ROOT", str(parent / "coop-municipal-offers"))),
    }
    result = {}
    for chain, root in roots.items():
        state = _read(root / code / ("structured-source.json" if chain == "ica" else "source-state.json"))
        if chain == "ica":
            area = _mapping(_mapping(state.get("coverage")).get("area"))
            rows = state.get("store_schedule", {})
            if area.get("municipality_code") != code or not isinstance(rows, dict):
                continue
            rows = rows.items()
        else:
            selection = _mapping(state.get("selection"))
            if state.get("municipality_code") != code or selection.get("municipality_code") != code:
                continue
            stores = selection.get("stores", [])
            if not isinstance(stores, list):
                continue
            rows = ((r.get("store_id"), r) for r in stores
                    if isinstance(r, dict) and r.get("selected"))
        for identity, row in rows:
            if not isinstance(identity, str) or not identity or not isinstance(row, dict):
                continue
            # Project the same deployed policy as the source job. Saved legacy
            # retry times are evidence, not the current collection schedule.
            row = dict(row)
            scheduled_source_times([row], state=state, now=now)
            failures = row.get("failed_attempts", 0)
            failures = failures if isinstance(failures, int) and failures >= 0 else 0
            raw_status = row.get("status")
            raw_status = raw_status if isinstance(raw_status, str) else None
            succeeded = raw_status in {
                "success", "confirmed_empty", "partial_candidate", "partial_text_candidate",
                "confirmed_no_qualified_rows",
            }
            failed = failures > 0 or raw_status in {
                "failed", "blocked_or_incomplete_publications", "inventory_failed",
            }
            result[(chain, str(identity))] = {
                "status": "failed" if failed else "succeeded" if succeeded else "unknown",
                "history_source": "municipal_offer_job",
                "last_attempt_at": _timestamp(row.get("last_attempt_at") or row.get("last_attempt")),
                "last_success_at": _timestamp(row.get("last_success_at") or row.get("last_success")),
                "next_fetch_at": _timestamp(row.get("next_fetch_at")),
                "failed_attempts": failures,
                "error": "Insamlingen misslyckades" if failed else None,
            }
    return result
