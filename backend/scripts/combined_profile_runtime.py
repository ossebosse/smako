"""Candidate image against retained production facts, with Docker network=none."""

import json
import time
from copy import deepcopy
from datetime import UTC, datetime
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
base = json.loads(Path("/evidence/combined-request.json").read_bytes())
now = datetime.now(UTC)
out = {
    "price_version": manifest["universe_id"],
    "now": now.isoformat(),
    "network": "none",
    "cases": {},
}
for case in ("D", "A", "B", "C"):
    req = PlanRequest.model_validate(base)
    req.personal.allow_nutrition_estimates = True
    for n, meal in enumerate(req.personal.meals):
        meal.count = 5 if case == "D" or case == ("A", "B", "C")[n] else 0
    req.recipes = req.personal.meals[0].count
    state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
    before = deepcopy(state)
    p = PersonalPlanner(req, get_settings(), prepared, state, now=now)
    start = time.perf_counter()
    ordinary_basket = p.basket
    reached = [0]

    def observed_basket(
        slots,
        *,
        final=True,
        reached=reached,
        case=case,
        start=start,
        ordinary_basket=ordinary_basket,
    ):
        if len(slots) > reached[0]:
            reached[0] = len(slots)
            print(
                json.dumps(
                    {"case": case, "depth": len(slots), "seconds": time.perf_counter() - start}
                ),
                flush=True,
            )
        return ordinary_basket(slots, final=final)

    p.basket = observed_basket
    try:
        result = p.create()
        assert state == before and result.data.live_chain_requests == 0
        assert len(result.personal.slots) == sum(m.count for m in req.personal.meals)
        assert result.portions == sum(m.count * m.servings for m in req.personal.meals)
        assert result.optimized_basket.store_count <= req.max_stores
        meals = {m.meal_type: m for m in req.personal.meals}
        for row in result.personal.checks["nutrition"]:
            slot = next(s for s in result.personal.slots if s.id == row["slot_id"])
            assert row["values"]["protein_g"] >= meals[slot.meal_type].limits.min_protein_g
        entry = {"status": "PASS", "plan": result.model_dump(mode="json")}
    except ValueError as exc:
        entry = {
            "status": getattr(exc, "code", "ERROR"),
            "reason": str(exc),
            "diagnostics": getattr(exc, "diagnostics", None),
        }
    entry.update(
        seconds=time.perf_counter() - start,
        request=req.model_dump(mode="json"),
        facts_version=p.facts_version,
    )
    out["cases"][case] = entry
    Path("/evidence/combined-runtime.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2)
    )
    print(
        json.dumps(
            {
                "case": case,
                "status": entry["status"],
                "seconds": entry["seconds"],
                "cost": entry.get("plan", {}).get("optimized_basket", {}).get("total"),
            }
        ),
        flush=True,
    )
