"""Frozen candidate identities and a small, provider-free acceptance matrix."""

import argparse
import hashlib
import json
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import get_settings
from app.models import PlanRequest
from app.models.personal import PantryItem
from app.services.personal_planner import POLICY_VERSION, PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--pools-only", action="store_true")
    args = parser.parse_args()
    root, output = Path("/inputs"), Path("/output")
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        (root / "combined-prices.json").read_bytes()
    ).restore()
    raw = json.loads((root / "combined-facts.json").read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
    assert facts.version == raw["facts_version"]
    historical = json.loads((root / "combined-runtime.json").read_bytes())
    now = datetime.fromisoformat(historical["now"])
    base = json.loads((root / "combined-request.json").read_bytes())
    base["personal"]["allow_nutrition_estimates"] = True
    settings = get_settings()
    empty = {"revision": 0, "items": [], "reservations": {}, "events": {}}
    output_data = {
        "policy": POLICY_VERSION,
        "now": now.isoformat(),
        "facts_version": facts.version,
        "price_version": prepared.universe.universe_id,
        "pools": {},
        "cases": {},
    }
    p = PersonalPlanner(
        PlanRequest.model_validate(base), settings, prepared, empty, facts=facts, now=now
    )
    with patch("socket.socket.connect", side_effect=AssertionError("External source call")):
        for meal in p.spec.meals:
            recipes = [r.model_dump(mode="json") for r in p._candidates(meal)]
            output_data["pools"][meal.meal_type] = {
                "qualified": len(recipes),
                "recipes": recipes,
                "sha256": hashlib.sha256(
                    json.dumps(recipes, sort_keys=True, ensure_ascii=False).encode()
                ).hexdigest(),
            }
        if not args.pools_only:
            cases = [(case, estimates, None) for case in "ABC" for estimates in (True, False)]
            cases += [
                ("D", False, None),
                ("B", True, "protein32"),
                ("B", True, "servings2"),
                ("B", True, "pantry"),
            ]
            for case, estimates, variation in cases:
                data, state = deepcopy(base), deepcopy(empty)
                data["personal"]["allow_nutrition_estimates"] = estimates
                for n, meal in enumerate(data["personal"]["meals"]):
                    meal["count"] = 5 if case == "D" or case == "ABC"[n] else 0
                data["recipes"] = data["personal"]["meals"][0]["count"]
                if variation == "protein32":
                    data["personal"]["meals"][1]["limits"]["min_protein_g"] = 32
                if variation == "servings2":
                    data["personal"]["meals"][1]["servings"] = 2
                if variation == "pantry":
                    quark = next(
                        i
                        for s in historical["cases"]["D"]["plan"]["optimized_basket"]["stores"]
                        for i in s["items"]
                        if "kvarg" in i["ingredient"]
                    )
                    key = p.product_keys[p.by_identity[(quark["store_id"], quark["product_id"])]]
                    state["items"] = [
                        PantryItem(
                            id="fixture-quark",
                            name=quark["product_name"],
                            quantity=300,
                            unit="g",
                            product_key=key,
                        ).model_dump()
                    ]
                request = PlanRequest.model_validate(data)
                before = deepcopy(state)
                t = time.perf_counter()
                planner = PersonalPlanner(request, settings, prepared, state, facts=facts, now=now)
                name = f"{case}-{'on' if estimates else 'off'}-{variation or 'base'}"
                try:
                    result = planner.create()
                    assert state == before
                    assert result.data.live_chain_requests == 0
                    assert result.optimized_basket.store_count <= 2
                    for row in result.personal.checks["nutrition"]:
                        slot = next(s for s in result.personal.slots if s.id == row["slot_id"])
                        assert (
                            row["values"]["protein_g"]
                            >= planner.meals[slot.meal_type].limits.min_protein_g
                        )
                    entry = {
                        "status": "PASS",
                        "seconds": time.perf_counter() - t,
                        "plan": result.model_dump(mode="json"),
                    }
                    if variation:
                        with (
                            patch.object(
                                PersonalPlanner,
                                "nutrition_evidence",
                                PersonalPlanner._nutrition_evidence,
                            ),
                            patch.object(
                                PersonalPlanner,
                                "_check_nutrition",
                                PersonalPlanner._check_nutrition_uncached,
                            ),
                        ):
                            reference = PersonalPlanner(
                                request, settings, prepared, state, facts=facts, now=now
                            ).create()
                        assert result.personal == reference.personal
                        assert result.optimized_basket == reference.optimized_basket
                        entry["equals_uncached"] = True
                    if variation == "pantry":
                        assert sum(a["quantity"] for a in result.personal.allocations) == 300
                except ValueError as exc:
                    assert case in "AD" and not estimates, (name, str(exc))
                    entry = {
                        "status": getattr(exc, "code", "ERROR"),
                        "reason": str(exc),
                        "seconds": time.perf_counter() - t,
                    }
                output_data["cases"][name] = entry
                print(
                    json.dumps(
                        {"case": name, "status": entry["status"], "seconds": entry["seconds"]}
                    ),
                    flush=True,
                )
    settings_keys = (
        "meal_plan_strategy",
        "stable_candidate_search_enabled",
        "stable_candidate_base_count",
        "stable_candidate_search_limit",
        "allow_medium_semantic_matches",
        "allow_estimated_quantities",
        "allow_unknown_quantities",
        "allow_unknown_sale_model",
        "max_price_age_hours",
        "price_age_warning_hours",
    )
    output_data["settings"] = {k: getattr(settings, k) for k in settings_keys}
    output_data["search"] = {
        "meal_beam_width": 8,
        "nutrition_choices": 256,
        "seed": "deterministic",
        "objective": "(joint_basket_total + taste_score*2, joint_basket_total, ordered_recipe_names)",
    }
    (output / f"{args.label}.json").write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2)
    )


if __name__ == "__main__":
    main()
