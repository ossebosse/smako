"""Existing read-only rollback accepts new saved models without restoring data."""

import json
from pathlib import Path

from app.main import app
from app.models import PlanRequest, PlanResponse
from fastapi.testclient import TestClient

data = json.loads(Path("/evidence/acceptance.json").read_bytes())
PlanRequest.model_validate(data["request"])
for row in data["cases"].values():
    if "plan" in row:
        PlanResponse.model_validate(row["plan"])
assert TestClient(app).post("/api/plans", json={}).status_code == 503
assert TestClient(app).put("/api/personal/pantry", json={}).status_code == 503
Path("/evidence/rollback.json").write_text(
    json.dumps(
        {
            "status": "PASS",
            "saved_models_readable": True,
            "writes_blocked": True,
            "database_restore": False,
            "image": "personal-v2-dinners-20260911c-rollback",
        }
    )
)
print("ROLLBACK COMPATIBILITY PASS")
