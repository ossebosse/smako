"""Free generator input, real historical frozen data; no consumer provider calls."""

import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner

from backend.scripts.personal_v2_cost_audit import inputs
from backend.scripts.personal_v2_dinners_probe import fixture


def main():
    prepared, facts = fixture()
    _, cases = inputs()
    state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
    req = PlanRequest.model_validate(cases["no_fish"]["request"])
    out = {
        "historical_prices": True,
        "price_version": prepared.universe.universe_id,
        "facts_version": facts.version,
        "request": req.model_dump(mode="json"),
    }
    with patch(
        "socket.socket.connect", side_effect=AssertionError("Consumer egress forbidden")
    ) as net:
        planner = PersonalPlanner(
            req,
            Settings(price_provider="mock"),
            prepared,
            state,
            facts=facts,
            now=prepared.universe.built_at,
        )
        try:
            plan = planner.create()
            out.update(status="PASS", plan=plan.model_dump(mode="json"))
            print("PASS", plan.optimized_basket.total, flush=True)
            for r, n in zip(plan.recipes, plan.personal.checks["nutrition"], strict=True):
                print(r.name, n["values"], flush=True)
            swap = req.model_copy(deep=True)
            swap.personal.slots = deepcopy(plan.personal.slots)
            # First dinner is a user-visible position, never a hidden recipe/product ID.
            changed = PersonalPlanner(
                swap,
                Settings(price_provider="mock"),
                prepared,
                state,
                facts=facts,
                now=prepared.universe.built_at,
            ).create(replace_slot=plan.personal.slots[0].id)
            out["replacement"] = changed.model_dump(mode="json")
            print("SWAP", changed.optimized_basket.total, flush=True)
        except ValueError as error:
            out.update(
                status=getattr(error, "code", "ERROR"),
                error=str(error),
                diagnostics=getattr(error, "diagnostics", None),
            )
            print(out["status"], out["error"], flush=True)
        out["external_calls"] = net.call_count
    Path("reports/fishfree-20260913/probe.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf8"
    )


if __name__ == "__main__":
    main()
