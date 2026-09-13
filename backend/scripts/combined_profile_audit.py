"""Reproducible per-candidate audit using one frozen price/fact/time version."""

import argparse
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSlot
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

ROOT = Path("reports/combined-403020")


def fixture():
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        Path("reports/private/combined-prices.json").read_bytes()
    ).restore()
    raw = json.loads(Path("reports/private/combined-facts.json").read_bytes())
    facts = {tuple(k): ProductFacts(**v) for k, v in raw["facts"]}
    return prepared, facts, datetime.fromisoformat(raw["now"])


def request(case="D", estimates=True):
    data = json.loads((ROOT / "before-ui/chromium-D-off.json").read_bytes())["request"]
    data["personal"]["allow_nutrition_estimates"] = estimates
    for n, meal in enumerate(data["personal"]["meals"]):
        meal["count"] = 5 if case == "D" or case == ("A", "B", "C")[n] else 0
    data["recipes"] = data["personal"]["meals"][0]["count"]
    return PlanRequest.model_validate(data)


def planner(req, inputs):
    prepared, facts, now = inputs
    return PersonalPlanner(
        req,
        Settings(price_provider="mock"),
        prepared,
        {"revision": 0, "items": [], "reservations": {}, "events": {}},
        facts=facts,
        now=now,
    )


def audit(inputs, estimates):
    p = planner(request(estimates=estimates), inputs)
    output = {
        "interpreted": p.request.model_dump(mode="json"),
        "price_version": p.prepared.universe.universe_id,
        "facts_version": p.facts_version,
        "now": p.now.isoformat(),
        "candidates": [],
    }
    for meal in p.spec.meals:
        valid = p._candidates(meal)
        for recipe in valid:
            row = {"meal_type": meal.meal_type, "recipe": recipe.model_dump(mode="json")}
            try:
                result = p.basket(
                    [
                        MealSlot(
                            id=f"{meal.meal_type}-1", day=1, meal_type=meal.meal_type, recipe=recipe
                        )
                    ]
                )
                row.update(status="PASS", checks=result["checks"])
            except ValueError as exc:
                row.update(
                    status=getattr(exc, "code", "ERROR"),
                    stage=getattr(exc, "stage", None),
                    reason=str(exc),
                )
            output["candidates"].append(row)
            print(meal.meal_type, recipe.name, row["status"], flush=True)
    output["precheck_rejections"] = p.diagnostics.snapshot()
    # Exact rejected onion products and declarations; never select a fictional winner.
    onion_recipe = (
        next(
            r["recipe"]
            for r in output["candidates"]
            if "1 av 5 ingrediensbehov: gul lök" in r.get("reason", "")
        )
        if not estimates
        else None
    )
    if onion_recipe:
        from app.models.recipe import Recipe
        from app.services.nutrition_reference import product_reference, reference_evidence

        r = Recipe.model_validate(onion_recipe)
        need = next(i for i in r.ingredients if i.name == "gul lök")
        products = p.resolve(need.name, need.quantity, need.unit, profile=p.spec.profile)
        output["onion"] = {"recipe": onion_recipe, "need": need.model_dump(), "products": []}
        for i, _ in products:
            product = p.prepared.universe.products[i]
            f = p.source_facts(product)
            identity = product_reference(product, need.name, f)
            output["onion"]["products"].append(
                {
                    "product_id": product.product_id,
                    "store_id": product.store_id,
                    "name": product.name,
                    "usable_unit": product.usable_unit,
                    "fact": asdict(f) if f else None,
                    "mapped_reference": identity,
                    "reference": asdict(reference_evidence(identity)) if identity else None,
                }
            )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--output", default="before")
    parser.add_argument("--cases", default="A,B,C,D")
    parser.add_argument("--estimates", choices=["both", "on", "off"], default="both")
    args = parser.parse_args()
    inputs = fixture()
    with patch(
        "socket.socket.connect", side_effect=AssertionError("External consumer call forbidden")
    ) as network:
        for estimates in (False, True) if args.estimates == "both" else (args.estimates == "on",):
            if args.audit:
                out = audit(inputs, estimates)
                (ROOT / f"{args.output}-audit-{'on' if estimates else 'off'}.json").write_text(
                    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf8"
                )
                continue
            for case in args.cases.split(","):
                p = planner(request(case, estimates), inputs)
                out = {
                    "case": case,
                    "estimates": estimates,
                    "interpreted": p.request.model_dump(mode="json"),
                    "price_version": p.prepared.universe.universe_id,
                    "facts_version": p.facts_version,
                    "now": p.now.isoformat(),
                }
                try:
                    result = p.create()
                    out.update(status="PASS", plan=result.model_dump(mode="json"))
                except ValueError as exc:
                    out.update(
                        status=getattr(exc, "code", "ERROR"),
                        reason=str(exc),
                        diagnostics=getattr(exc, "diagnostics", None),
                    )
                out["external_calls"] = network.call_count
                (ROOT / f"{args.output}-{case}-{'on' if estimates else 'off'}.json").write_text(
                    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf8"
                )
                print(
                    case,
                    estimates,
                    out["status"],
                    out.get("reason", out.get("plan", {}).get("optimized_basket", {}).get("total")),
                    flush=True,
                )


if __name__ == "__main__":
    main()
