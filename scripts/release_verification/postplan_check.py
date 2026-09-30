"""Verify private saved plans through ordinary rebuild and process restart.

Run without external network in the final image, with /work as a copied state
root and repo evaluation helpers mounted at /evaluation. The original profile
plans were created before the first rebuild, which this script checks in the
plan database. A new guest plan keeps its session cookie through a second
ordinary rebuild and a real application restart for HTTP GET verification.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx
from job import configure

image_build_id = os.environ.get("BUILD_ID")
configure()
if image_build_id:
    os.environ["BUILD_ID"] = image_build_id
os.environ["PLAN_PREWARM_ENABLED"] = "false"
P = Path("/work")
profiles = json.loads((P / "http-results.json").read_bytes())
first_rebuild = json.loads((P / "second-result.json").read_bytes())
assert first_rebuild["runner"]["completed_at"] > profiles["started_at"]

with sqlite3.connect(P / "plans.sqlite") as database:
    persisted = {}
    for case in profiles["cases"]:
        row = database.execute(
            "SELECT response_json FROM consumer_plan_revisions "
            "WHERE plan_id = ? ORDER BY revision DESC LIMIT 1",
            (case["plan_id"],),
        ).fetchone()
        assert row is not None, case["case"]
        saved = json.loads(row[0])
        assert saved == case["response"]["plan"]
        persisted[case["case"]] = case["plan_id"]


def start():
    with (P / "postplan-app.log").open("a") as log:
        process = subprocess.Popen(
            [sys.executable, "/evaluation/http_job.py", "--serve"],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    for _ in range(1200):
        if process.poll() is not None:
            raise RuntimeError("private app startup failed")
        try:
            if httpx.get("http://127.0.0.1:8000/ready", timeout=1).status_code == 200:
                return process
        except httpx.TransportError:
            pass
        time.sleep(0.1)
    raise RuntimeError("private app startup timed out")


def stop(process):
    process.terminate()
    process.wait(30)


app = start()
try:
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=600) as client:
        # The old guest cookie was deliberately not exported with the report.
        # A fresh client must not gain access to those private plans.
        old_guest = client.get("/api/plans/" + profiles["cases"][0]["plan_id"])
        assert old_guest.status_code in {401, 403}, old_guest.text
        selected = next(
            row
            for row in json.loads((P / "representative-bdc9-results.json").read_bytes())["cases"]
            if row["case"] == "ica-loose-weight"
        )
        request = json.loads(json.dumps(selected["request"]))
        request["personal"]["pantry_revision"] = client.get(
            "/api/personal/state"
        ).json()["revision"]
        created = client.post("/api/plans", json=request)
        assert created.status_code == 201, created.text[:500]
        saved = created.json()
        assert client.get("/api/plans/" + saved["plan_id"]).status_code == 200
        stop(app)
        app = None
        with (P / "postplan-rebuild.log").open("w") as log:
            rebuild = subprocess.run(
                [sys.executable, "/evaluation/refresh_job.py", "second"],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=3600,
                check=False,
            )
        assert rebuild.returncode == 0, rebuild.returncode
        second = json.loads((P / "second-result.json").read_bytes())
        serving = json.loads((P / "second-serving-after.json").read_bytes())
        assert second["runner"]["completed_at"] > saved["created_at"]
        app = start()
        status = client.get("/api/price-universe/status")
        assert status.status_code == 200
        assert serving["universe_id"] in str(status.json())
        retrieved = client.get("/api/plans/" + saved["plan_id"])
        assert retrieved.status_code == 200, retrieved.text[:500]
        current = retrieved.json()
        assert current["plan"] == saved["plan"]
        assert current["price_universe_id"] == saved["price_universe_id"]
        report = {
            "network": "none",
            "earlier_profile_rows_persisted_after_first_rebuild": persisted,
            "old_guest_without_cookie_http_status": old_guest.status_code,
            "new_guest_plan_id": saved["plan_id"],
            "new_guest_plan_get_after_second_rebuild": retrieved.status_code,
            "retained_plan_identical": True,
            "retained_price_universe_id": current["price_universe_id"],
            "loaded_universe_id": serving["universe_id"],
            "rebuild_exit": second["exit"],
            "rebuild_reload": second["runner"].get("runtime_reload"),
            "price_version_status": current.get("price_version_status"),
            "recalculation_available": current.get("recalculation_available"),
        }
        (P / "postplan-check.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf8"
        )
        print(json.dumps(report))
finally:
    if app is not None:
        stop(app)
