"""Predeclared profiles, real frozen prices/facts, no external consumer requests."""

import argparse
import json
import time
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.errors import IncompleteBasketError
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import complete_identity_facts, project_raw_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact


def fixture():
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        Path("reports/private/gaps-price-fixture.json").read_bytes()
    ).restore()
    raw = json.loads(Path("reports/private/qualified-facts.json").read_bytes())
    before = {tuple(k): ProductFacts(**v) for k, v in raw["facts"]}
    mapped = {}
    for p in prepared.universe.products:
        f = before.get((p.store_id, p.product_id))
        if f:
            mapped[(p.store_id, p.product_id)] = project_raw_facts(
                raw["raw"][p.product_id],
                chain=p.chain,
                product_id=p.product_id,
                snapshot_id=f.source_snapshot_id,
                source_reference=f.source,
                observed_at=p.source_provenance.source_observed_at.isoformat(),
            )
    return prepared, complete_identity_facts(prepared, mapped)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default="A,B,C,D,E")
    args = parser.parse_args()
    prepared, facts = fixture()
    profiles = json.loads(Path("reports/personal-v2-dinners/profiles.json").read_bytes())
    out = {
        "price_version": prepared.universe.universe_id,
        "facts_version": facts.version,
        "cases": {},
        "external_calls": 0,
    }
    path = Path("reports/personal-v2-dinners/frozen.json")
    if path.exists():
        out["cases"].update(json.loads(path.read_bytes()).get("cases", {}))
    for key in args.cases.split(","):
        settings = profiles[key]
        if "extends" in settings:
            settings = profiles[settings["extends"]] | settings
        count = settings.get("dinners", 0)
        spec = PersonalPlanning(
            meals=[
                MealSettings(
                    meal_type="dinner" if count else "breakfast",
                    count=count or settings["breakfasts"],
                    servings=settings["servings"],
                    limits=PortionLimits(
                        min_protein_g=settings.get("min_protein_g"),
                        max_kcal=settings.get("max_kcal"),
                    ),
                )
            ],
            allow_nutrition_estimates=settings["allow_nutrition_estimates"],
            organic_percent=settings.get("organic_percent", 0),
        )
        if key == "A2":
            from app.models.personal import MealSlot
            from app.models.recipe import Recipe, RecipeIngredient

            spec.slots = [
                MealSlot(
                    id="breakfast-1",
                    day=1,
                    meal_type="breakfast",
                    recipe=Recipe(
                        name="Ostsmörgås",
                        servings=2,
                        ingredients=[
                            RecipeIngredient(name="bröd", quantity=160, unit="g"),
                            RecipeIngredient(name="ost", quantity=120, unit="g"),
                        ],
                        instructions=["Servera tillsammans."],
                    ),
                )
            ]
        inventory = {
            "id": None,
            "revision": 0,
            "profile": None,
            "items": [],
            "reservations": {},
            "events": {},
        }
        if key in {"C", "C4", "C3"}:
            inventory["items"] = [
                {
                    "id": "acceptance-rice",
                    "name": "ris",
                    "quantity": 500,
                    "unit": "g",
                    "product_key": None,
                    "unusable": False,
                    "food": True,
                    "nutrition_reference": "slv:2481:dry",
                }
            ]
        req = PlanRequest(
            recipes=count,
            servings=settings["servings"],
            diversity_mode=settings["mode"],
            max_stores=settings["max_stores"],
            memberships={},
            personal=spec,
        )
        p = PersonalPlanner(
            req,
            Settings(price_provider="mock"),
            prepared,
            inventory,
            facts=facts,
            now=prepared.universe.built_at,
        )
        start = time.perf_counter()
        try:
            plan = p.create()
            result = {"status": "PASS", "plan": plan.model_dump(mode="json")}
        except (ValueError, IncompleteBasketError) as e:
            result = {"status": getattr(e, "code", "SEARCH_BLOCKED"), "message": str(e)}
        result.update(
            seconds=time.perf_counter() - start,
            settings=req.model_dump(mode="json"),
            stock_after=inventory["items"],
        )
        out["cases"][key] = result
        print(
            json.dumps(
                {
                    "case": key,
                    "status": result["status"],
                    "cost": result.get("plan", {}).get("optimized_basket", {}).get("total"),
                    "message": result.get("message"),
                    "seconds": result["seconds"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        Path("reports/personal-v2-dinners/frozen.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf8"
        )


if __name__ == "__main__":
    with patch(
        "socket.socket.connect",
        side_effect=AssertionError("External networking forbidden in consumer planning"),
    ):
        main()
