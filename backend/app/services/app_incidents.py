"""Bounded private evidence for HTTP 5xx; never store bodies, identities or messages.

Single-worker beta, one atomic index beside the existing private plan store.
This records failures; it neither retries work nor changes the HTTP response.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from grocery_data.app.services.durable_files import atomic_write_bytes

MAX_BYTES = 512_000
MAX_INCIDENTS = 64
_LOCK = Lock()
_REFERENCE = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")
LOGGER = logging.getLogger(__name__)


def reference(value):
    return value if isinstance(value, str) and _REFERENCE.fullmatch(value) else None


def exception_evidence(error):
    """Locations and chain topology only: no exception text, locals or code lines."""
    pending = [(error, None, "root")]
    seen, rows = set(), []
    while pending and len(rows) < 10:
        current, parent, relation = pending.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        frames = []
        tb = current.__traceback__
        while tb:
            path = tb.tb_frame.f_code.co_filename.replace("\\", "/")
            for marker in ("/backend/app/", "/grocery_data/"):
                if marker in path:
                    path = marker.strip("/") + "/" + path.split(marker, 1)[1]
                    break
            else:
                path = Path(path).name
            frames.append({"file": path[:240], "line": tb.tb_lineno,
                           "function": tb.tb_frame.f_code.co_name[:100]})
            tb = tb.tb_next
        index = len(rows)
        rows.append({"type": type(current).__name__[:100], "parent": parent,
                     "relation": relation, "frames": frames[-20:],
                     "frames_truncated": len(frames) > 20})
        if current.__cause__ is not None:
            pending.append((current.__cause__, index, "cause"))
        elif current.__context__ is not None and not current.__suppress_context__:
            pending.append((current.__context__, index, "context"))
        if isinstance(current, BaseExceptionGroup):
            pending.extend((child, index, "group") for child in current.exceptions[:10])
    return {"chain": rows, "truncated": bool(pending)}


def record_http_failure(request, settings, *, error, status, started_at, universe_id):
    """Best effort, with an explicit observable write failure; never hide app errors."""
    try:
        job = getattr(request.state, "diagnostic_plan_job", None)
        outcome, stage, saved_id = "unknown", "http_handler", None
        if job is not None:
            stage = job.stage
            if job.task.cancelled():
                outcome = "cancelled"
            elif not job.task.done():
                outcome = "running"
            elif job.task.exception() is not None:
                outcome = "failed"
                error = error or job.task.exception()
            else:
                outcome = "saved"
                saved = job.task.result()
                saved_id = reference(saved.get("plan_id") if isinstance(saved, dict)
                                     else getattr(saved, "plan_id", None))
                stage = "result_read"
        route = request.scope.get("route")
        endpoint = getattr(route, "path", "unmatched")
        now = datetime.now(UTC).isoformat()
        detail = {"code": "app_http_5xx", "endpoint": endpoint,
                  "method": request.method, "status": status, "stage": stage,
                  "job_outcome": outcome, "job_id": reference(job.job_id) if job else None,
                  "start_request_id": reference(job.request_id) if job else None,
                  "plan_id": saved_id, "build_id": settings.build_id,
                  "price_universe_id_at_request_start": universe_id,
                  "exception": exception_evidence(error),
                  "exception_available": error is not None}
        signature = hashlib.sha256(json.dumps(detail, sort_keys=True).encode()).hexdigest()
        request_id = reference(getattr(request.state, "request_id", None))
        path = settings.plan_store_path.resolve().parent / "app-incidents.json"
        with _LOCK:
            if path.exists():
                if path.stat().st_size > MAX_BYTES:
                    raise ValueError("incident_index_oversized")
                data = json.loads(path.read_bytes())
                if data.get("schema") != "smako-app-incidents-v1":
                    raise ValueError("incident_index_schema")
            else:
                data = {"schema": "smako-app-incidents-v1", "incidents": []}
            rows = data["incidents"]
            row = next((x for x in rows if x["signature"] == signature), None)
            if row is None:
                row = {**detail, "incident_id": "app-" + signature[:20],
                       "signature": signature, "first_seen": now, "occurrences": 0,
                       "first_request_id": request_id, "requests": []}
                rows.append(row)
            row.update(last_seen=now, occurrences=row["occurrences"] + 1)
            row["requests"] = (row["requests"] + [{"request_id": request_id,
                "started_at": started_at, "failed_at": now}])[-8:]
            rows.sort(key=lambda x: x["last_seen"])
            data["incidents"] = rows[-MAX_INCIDENTS:]
            data["updated_at"] = now
            payload = json.dumps(data, separators=(",", ":")).encode()
            while len(payload) > MAX_BYTES and len(data["incidents"]) > 1:
                data["incidents"].pop(0)
                payload = json.dumps(data, separators=(",", ":")).encode()
            if len(payload) > MAX_BYTES:
                raise ValueError("incident_too_large")
            atomic_write_bytes(path, payload)
        return row["incident_id"]
    except Exception as exc:  # noqa: BLE001 -- diagnostics must not replace the app failure
        # No traceback here: a failed write must not leak file paths or secrets.
        LOGGER.error("app_incident_write_failed type=%s", type(exc).__name__)
        request.app.state.app_incident_write_error = type(exc).__name__
        return None
