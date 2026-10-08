"""Read-only private app evidence; runnable over the existing admin SSH stdin.

Works on dd12 too: absent exception evidence remains explicitly unavailable.
No schema creation, planner imports, requests, source reads or database writes.
"""
import argparse
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


def read_app_evidence(*, database, plan_store, request_id=None):
    now = datetime.now(UTC)
    out = {"checked_at": now.isoformat(), "status": "observed"}
    with sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True,
                         timeout=2) as db:
        db.row_factory = sqlite3.Row
        # request_id and created_at already have indexes. Never scan plan bodies.
        where = "request_id=?" if request_id else "created_at>=? AND status_code>=500"
        value = request_id or (now - timedelta(days=1)).isoformat()
        rows = db.execute("SELECT request_id,created_at,endpoint,method,status_code,"
            "error_code,duration_ms,plan_id,price_universe_id,build_id "
            "FROM beta_request_metrics WHERE " + where + " ORDER BY created_at DESC LIMIT 20",
            (value,)).fetchall()
        out["http_metrics"] = [dict(row) for row in rows]
    path = Path(plan_store).resolve().parent / "app-incidents.json"
    if not path.exists():
        out["exception_evidence"] = {"status": "unavailable",
            "reason": "app_incident_capture_not_present", "incidents": []}
    else:
        if path.stat().st_size > 512_000:
            raise ValueError("app_incident_index_oversized")
        index = json.loads(path.read_bytes())
        if index.get("schema") != "smako-app-incidents-v1":
            raise ValueError("app_incident_schema_unknown")
        rows = index["incidents"]
        if request_id:
            rows = [row for row in rows if request_id == row["first_request_id"]
                    or any(r["request_id"] == request_id for r in row["requests"])]
        out["exception_evidence"] = {"status": "observed", "updated_at": index["updated_at"],
                                    "incidents": rows[-20:]}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request-id")
    args = parser.parse_args()
    try:
        from sqlalchemy.engine import make_url
        data = read_app_evidence(database=make_url(os.environ["GROCERY_DATABASE_URL"]).database,
                                 plan_store=os.environ["PLAN_STORE_PATH"],
                                 request_id=args.request_id)
    except Exception as exc:  # noqa: BLE001 -- admin output must never expose raw exceptions
        data = {"status": "unknown", "reason": "app_evidence_read_failed",
                "error_type": type(exc).__name__}
    print(json.dumps(data))
    return int(data["status"] == "unknown")


if __name__ == "__main__":
    raise SystemExit(main())
