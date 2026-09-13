"""Candidate image on mounted real retained data; network disabled externally."""

import json
from copy import deepcopy
from pathlib import Path

from app.config import get_settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
manifest = json.loads((root / "active/city-lund.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json(
    (root / manifest["artifact_file"]).read_bytes()
).restore()
accepted = json.loads(Path("/evidence/acceptance.json").read_bytes())
req = PlanRequest.model_validate(accepted["request"])
req.personal.pantry_revision = 0
state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
before = deepcopy(state)
planner = PersonalPlanner(req, get_settings(), prepared, state, now=prepared.universe.built_at)
plan = planner.create()
assert state == before and plan.data.live_chain_requests == 0
assert len(plan.recipes) == 5 and len(plan.optimized_basket.stores) <= 2
assert all(
    n["values"]["protein_g"] >= 20 and n["values"]["kcal"] <= 800
    for n in plan.personal.checks["nutrition"]
)
assert plan.personal.checks["allergy"] == "NOT_REQUESTED"
assert plan.personal.checks["ingredient_exclusions"]
output = {
    "status": "PASS",
    "network": "none",
    "historical_pricing_time": str(prepared.universe.built_at),
    "price_version": manifest["universe_id"],
    "facts_version": planner.facts_version,
    "plan": plan.model_dump(mode="json"),
    "stock_unchanged": True,
    "consumer_external_calls": 0,
}
Path("/evidence/runtime.json").write_text(json.dumps(output, ensure_ascii=False, indent=2))
print(
    json.dumps(
        {"status": "PASS", "cost": plan.optimized_basket.total, "version": manifest["universe_id"]}
    )
)
