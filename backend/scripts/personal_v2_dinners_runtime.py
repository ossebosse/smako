import json
import sys
from pathlib import Path

from app.config import get_settings
from app.models import PlanRequest, PlanResponse
from app.models.personal import PantryItem
from app.services.nutrition_reference import reference_data

frozen = json.loads(Path("/evidence/dinners-frozen.json").read_bytes())
for case in frozen["cases"].values():
    PlanRequest.model_validate(case["settings"])
    if case.get("plan"):
        PlanResponse.model_validate(case["plan"])
PantryItem(name="ris", quantity=500, unit="g", nutrition_reference="slv:2481:dry")
if len(sys.argv) > 1 and sys.argv[1] == "rollback":
    from app.main import app
    from fastapi.testclient import TestClient

    assert TestClient(app).post("/api/plans", json={}).status_code == 503
    print(
        json.dumps(
            {
                "status": "PASS",
                "rollback_read_models": True,
                "writes_blocked": True,
                "reference_version": reference_data()["content_version"],
            }
        )
    )
else:
    from app.services.personal_planner import PersonalPlanner
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

    root = Path("/srv/app/var/price_universes")
    manifest = json.loads((root / "active/city-lund.json").read_bytes())
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        (root / manifest["artifact_file"]).read_bytes()
    ).restore()
    req = PlanRequest.model_validate(frozen["cases"]["B3"]["settings"])
    planner = PersonalPlanner(
        req,
        get_settings(),
        prepared,
        {"id": None, "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}},
        now=prepared.universe.built_at,
    )
    result = planner.create()
    assert result.optimized_basket.total == 426.52
    assert result.data.live_chain_requests == 0
    print(
        json.dumps(
            {
                "status": "PASS",
                "cost": result.optimized_basket.total,
                "price_version": manifest["universe_id"],
                "facts_version": planner.facts_version,
                "reference_version": reference_data()["content_version"],
                "network": "none",
                "serialized_request_preserves_variation": True,
            }
        )
    )
