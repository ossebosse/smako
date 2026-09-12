"""Reproduce retained acceptance inputs; historical data, consumer networking forbidden."""

import hashlib
import json
import time
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict

from backend.scripts.personal_v2_dinners_probe import fixture

OUTPUT = Path("reports/affordable-five-20260912")


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf8")


def inputs():
    old = json.loads(Path("reports/five-dinners-20260912/verified-frozen.json").read_bytes())
    cases = {}
    for key, original in [("original", "B5"), ("pantry", "C5"), ("strict", "D_strict")]:
        c = old["cases"][original]
        cases[key] = {"request": deepcopy(c["settings"]), "stock": deepcopy(c["stock_before"])}
    cases["same_menu"] = deepcopy(cases["original"])
    cases["same_menu"]["request"]["personal"]["slots"] = old["cases"]["B5"]["plan"]["personal"]["slots"]
    cases["cheapest"] = deepcopy(cases["original"])
    cases["cheapest"]["request"]["diversity_mode"] = "cheapest"
    cases["no_fish"] = deepcopy(cases["original"])
    cases["no_fish"]["request"]["personal"]["profile"]["exclusions"] = ["fisk"]
    assert not cases["no_fish"]["request"]["personal"]["profile"]["allergies"]
    return old, cases


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="baseline.json")
    args = parser.parse_args()
    OUTPUT.mkdir(exist_ok=True)
    old, cases = inputs()
    save(OUTPUT / "predeclared-inputs.json", cases)
    prepared, facts = fixture()
    assert prepared.universe.universe_id == old["price_version"]
    assert facts.version == old["facts_version"]
    out = {"historical_test_data": True, "price_version": prepared.universe.universe_id,
           "facts_version": facts.version, "pricing_time": str(prepared.universe.built_at),
           "frozen_files": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in [
               Path("reports/private/gaps-price-fixture.json"), Path("reports/private/qualified-facts.json"),
               Path("backend/app/data/nutrition/slv-20260911.json"),
               Path("backend/app/data/nutrition/couscous-assembly-20260912.json")
           ]}, "cases": {}}
    with patch("socket.socket.connect", side_effect=AssertionError("Forbidden consumer egress")) as network:
        for key, c in cases.items():
            state = {"revision": 0, "items": deepcopy(c["stock"]), "reservations": {}, "events": {}}
            before = deepcopy(state)
            planner = PersonalPlanner(PlanRequest.model_validate(c["request"]), Settings(price_provider="mock"),
                                      prepared, state, facts=facts, now=prepared.universe.built_at)
            start = time.perf_counter()
            try:
                plan = planner.create()
                row = {"status": "PASS", "plan": plan.model_dump(mode="json")}
                assert plan.data.live_chain_requests == 0
                assert len(plan.optimized_basket.stores) <= 2
                assert all(i.packages_needed == int(i.packages_needed)
                           for s in plan.optimized_basket.stores for i in s.items)
                if key == "same_menu":
                    assert plan.optimized_basket.total == 677.43
                if key == "strict":
                    assert plan.optimized_basket.total == 30.38
                    assert all(n["status"] == "VERIFIED" for n in plan.personal.checks["nutrition"])
                if key == "pantry":
                    assert sum(a["quantity"] for a in plan.personal.allocations) == 500
            except PolicyConflict as exc:
                row = {"status": exc.code, "message": str(exc), "diagnostics": exc.diagnostics}
            assert state == before
            row.update(seconds=time.perf_counter()-start, stock_unchanged=True)
            out["cases"][key] = row
            save(OUTPUT / args.output, out)
            print(json.dumps({"case": key, "status": row["status"],
                              "cost": row.get("plan", {}).get("optimized_basket", {}).get("total"),
                              "message": row.get("message"), "seconds": row["seconds"]}), flush=True)
        assert network.call_count == 0
        out["external_calls"] = network.call_count
        save(OUTPUT / args.output, out)


if __name__ == "__main__":
    main()
