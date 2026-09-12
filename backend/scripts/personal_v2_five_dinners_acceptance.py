"""Fixed acceptance profiles, actual retained prices/facts, forbidden networking."""

import json
import time
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator

from backend.scripts.personal_v2_dinners_probe import fixture

OUTPUT = Path("reports/five-dinners-20260912")


def profiles():
    previous = json.loads(Path("reports/personal-v2-dinners/frozen.json").read_bytes())["cases"]
    requests = {"B5": deepcopy(previous["B"]["settings"]),
                "A3_generated": deepcopy(previous["B3"]["settings"]),
                "D_strict": deepcopy(previous["A2"]["settings"])}
    for new, old in [("A3_original", "B3"), ("E3_original", "E3")]:
        requests[new] = deepcopy(previous[old]["settings"])
        requests[new]["personal"]["slots"] = deepcopy(previous[old]["plan"]["personal"]["slots"])
    requests["C5"] = deepcopy(requests["B5"])
    requests["blocked_old_pool"] = deepcopy(requests["B5"])
    requests["blocked_variation"] = deepcopy(requests["B5"])
    requests["blocked_variation"]["max_same_cooking_method_meals"] = 1
    return requests


def main():
    OUTPUT.mkdir(exist_ok=True)
    requests = profiles()
    (OUTPUT / "profiles.json").write_text(json.dumps(requests, ensure_ascii=False, indent=2), encoding="utf8")
    prepared, facts = fixture()
    output = {"price_version": prepared.universe.universe_id, "facts_version": facts.version,
              "external_calls": 0, "cases": {}}
    original_generator = DeterministicRecipeCandidateGenerator.generate_reference_candidates
    with patch("socket.socket.connect", side_effect=AssertionError("Forbidden consumer egress")) as network:
        for key, req in requests.items():
            inventory = {"revision": 0, "items": [], "reservations": {}, "events": {}}
            if key == "C5":
                inventory["items"] = [{"id": "acceptance-rice", "name": "ris", "quantity": 500,
                                       "unit": "g", "product_key": None, "unusable": False,
                                       "food": True, "nutrition_reference": "slv:2481:dry"}]
            before = deepcopy(inventory)
            planner = PersonalPlanner(PlanRequest.model_validate(req), Settings(price_provider="mock"),
                                      prepared, inventory, facts=facts, now=prepared.universe.built_at)
            start = time.perf_counter()
            try:
                if key == "blocked_old_pool":
                    with patch.object(DeterministicRecipeCandidateGenerator, "generate_reference_candidates",
                                      lambda self, **k: original_generator(self, **k)[:8]):
                        plan = planner.create()
                else:
                    plan = planner.create()
                assert inventory == before
                assert plan.data.live_chain_requests == 0
                assert len(plan.optimized_basket.stores) <= req["max_stores"]
                assert all(i.packages_needed == int(i.packages_needed)
                           for s in plan.optimized_basket.stores for i in s.items)
                for recipe, n in zip(plan.recipes, plan.personal.checks["nutrition"], strict=True):
                    assert n["values"]["protein_g"] >= req["personal"]["meals"][0]["limits"]["min_protein_g"]
                    assert n["values"]["kcal"] <= req["personal"]["meals"][0]["limits"]["max_kcal"]
                    assert sum(s["quantity"] for s in n["sources"]) == sum(i.quantity for i in recipe.ingredients)
                if key in {"B5", "C5"}:
                    assert len(plan.recipes) == 5
                    for s in plan.optimized_basket.stores:
                        assert all("skalade" not in i.product_name.casefold() for i in s.items)
                if key == "A3_original":
                    assert plan.optimized_basket.total == 426.52
                if key == "E3_original":
                    assert plan.optimized_basket.total == 480.05
                    assert plan.personal.checks["organic_cost_percent"] >= 25
                if key == "D_strict":
                    assert plan.optimized_basket.total == 30.38
                    assert all(n["status"] == "VERIFIED" for n in plan.personal.checks["nutrition"])
                if key == "C5":
                    assert sum(a["quantity"] for a in plan.personal.allocations) == 500
                result = {"status": "PASS", "plan": plan.model_dump(mode="json")}
            except PolicyConflict as exc:
                assert key.startswith("blocked"), f"{key}: {exc}"
                result = {"status": exc.code, "message": str(exc), "diagnostics": exc.diagnostics}
                d = exc.diagnostics
                assert d["raw_recipe_pool"] == sum(r["rejected"] for r in d["candidate_rejections"]) + d["singleton_passed"] + d["not_singleton_evaluated"]
            result.update(settings=req, seconds=time.perf_counter()-start,
                          stock_before=before["items"], stock_after=inventory["items"])
            output["cases"][key] = result
            print(json.dumps({"case": key, "status": result["status"],
                              "cost": result.get("plan", {}).get("optimized_basket", {}).get("total"),
                              "seconds": result["seconds"]}), flush=True)
            (OUTPUT / "verified-frozen.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8")
        assert network.call_count == 0


if __name__ == "__main__":
    main()
