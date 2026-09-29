"""Replay the existing warm-meal case with its original historical clock."""

import gc
import hashlib
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.services.personal_planner import PersonalPlanner
from app.services.plan_store import PlanStore

from backend.tests.test_warm_offer_meal import case

prepared, facts, cheese, request = case()
result = PersonalPlanner(
    request,
    Settings(price_provider="mock"),
    prepared,
    {"revision": 0, "items": [], "reservations": {}, "events": {}},
    facts=facts,
    now=datetime(2026, 9, 24, 21, 16, tzinfo=UTC),
).create()
with tempfile.TemporaryDirectory(prefix="smako-replay-") as directory:
    database = Path(directory) / "plans.sqlite"
    saved = PlanStore(database).create(request, result, owner_actor_hash="a" * 64)
    reread = PlanStore(database).get_owned(saved.plan_id, owner_actor_hash="a" * 64)
    assert reread.plan == result and reread.request == request
    gc.collect()  # Close SQLite connection cycles before Windows removes the temp directory.
summary = {
    "clock_utc": "2026-09-24T21:16:00+00:00",
    "input_sha256": hashlib.sha256(
        Path("reports/purchase-planning-20260925/final/prepared-1281-second.json").read_bytes()
    ).hexdigest(),
    "basket": result.optimized_basket.model_dump(mode="json"),
    "nutrition": result.personal.checks["nutrition"],
    "audit": result.personal.checks["checkout_audit"],
    "saved_and_reread_identical": True,
}
Path(sys.argv[1]).write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf8"
)
print("Historical planner, audit, persistence and reread PASS")
