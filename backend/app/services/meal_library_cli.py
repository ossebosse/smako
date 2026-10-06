"""Content-driven CLI: validate -> diff -> import -> prepare -> qualify -> build.

Run with PYTHONPATH=backend;. (Windows), backend:. (Linux). Qualifications use the ordinary PersonalPlanner,
PriceUniverse and audit; no product synthesis or model API is used.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from app.services.meal_library_content import (
    MANIFEST,
    ROOT,
    digest,
    encoded,
    import_pack,
    load_entries,
    manifest_entries,
    pack_diff,
    validate_pack,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["validate", "diff", "import"]:
        p = sub.add_parser(name)
        p.add_argument("input",type=Path)
        p.add_argument("--output",type=Path)
        if name == "import":p.add_argument("--accept-id",action="append")
    for name in ["prepare", "build"]:
        p = sub.add_parser(name)
        p.add_argument("--output",type=Path,required=True)
        p.add_argument("--universe",type=Path,help="Prepare public source projections for this exact artifact")
        p.add_argument("--servings",type=int,action="append",choices=range(1,13),default=[])
    p = sub.add_parser("qualify")
    p.add_argument("--pack",type=Path,required=True)
    p.add_argument("--universe",type=Path,required=True)
    p.add_argument("--clock",required=True,help="Explicit ISO date/time; label older prices historical replay")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--purchase-mode",choices=["exact","estimated"],default="estimated")
    p.add_argument("--max-stores",type=int,default=3)
    p.add_argument("--protein",type=float)
    p.add_argument("--allow-nutrition-estimates",action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()
    if args.command in {"validate","diff","import"}:
        checked = validate_pack(args.input)
        report = {k:v for k,v in checked.items() if k != "recipes"}
        report["valid_identities"] = [f"{r.design.base_id}:{r.design.version}:{r.design.variant_id}" for r in checked["recipes"]]
        if args.command == "diff":report["diff"] = pack_diff(checked)
        if args.command == "import":report = import_pack(args.input,accepted_ids=args.accept_id)
    elif args.command in {"prepare","build"}:
        from app.services.meal_prepared_artifacts import prepare_content
        m = manifest_entries()
        recipes = load_entries([*m["current"],*m["history"]])
        report = prepare_content(recipes)
        report["manifest_sha256"] = digest(encoded(m))
        if args.servings:
            from app.services.recipe_library import _registered_historical_portions
            report["prepared_portions"] = {str(n):len(_registered_historical_portions(n))
                                           for n in sorted(set(args.servings))}
        if args.universe:
            from app.services.meal_prepared_artifacts import declaration_index
            from app.services.personal_source_facts import facts_version, load_retained_facts
            from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
            universe = PreparedPriceUniverseArtifact.model_validate_json(args.universe.read_bytes()).restore()
            facts = load_retained_facts(universe)
            def exact_facts(product):
                fact = facts.get((product.store_id,product.product_id))
                return fact if (fact and fact.source and fact.source_product_id == product.product_id
                                and product.source_provenance and fact.source_snapshot_id ==
                                product.source_provenance.source_snapshot_id) else None
            classes = declaration_index(universe.universe,facts,exact_facts)
            report["source_preparation"] = {"universe_id":universe.universe.universe_id,
                "artifact_sha256":digest(args.universe.read_bytes()),
                "facts_version":getattr(facts,"version",None) or facts_version(facts),
                "classified_products":len(classes),"purchase_qualification":"not_performed"}
        from app.services.meal_prepared_artifacts import STATS, root
        report["stats"] = dict(STATS)
        cache = root()
        report["storage"] = {folder.name:{"files":len(list(folder.glob("*.json"))),
            "bytes":sum(p.stat().st_size for p in folder.glob("*.json"))}
            for folder in cache.iterdir() if folder.is_dir()} if cache.exists() else {}
        if args.command == "build":
            # A hash-bound content candidate is data, not an app/code deployment.
            args.output.mkdir(parents=True,exist_ok=False)
            for entry in [*m["current"],*m["history"]]:
                target = args.output / entry["file"]
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/entry["file"]).read_bytes())
            (args.output/MANIFEST.name).write_bytes(encoded(m))
            args.output = args.output / "PREPARATION.json"
    else:
        from app.config import Settings
        from app.models import PlanRequest
        from app.models.personal import MealSlot
        from app.services.personal_planner import PersonalPlanner
        from app.services.personal_source_facts import load_retained_facts
        from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

        prepared = PreparedPriceUniverseArtifact.model_validate_json(args.universe.read_bytes()).restore()
        clock = datetime.fromisoformat(args.clock)
        assert clock.utcoffset() is not None,"Use timezone-aware clock"
        facts = load_retained_facts(prepared)
        checked = validate_pack(args.pack)
        report = {"price_basis":"explicit historical replay when clock is older than execution",
                  "universe_id":prepared.universe.universe_id,"universe_artifact_sha256":digest(args.universe.read_bytes()),
                  "source_sha256":checked["source_sha256"],
                  "rejections":checked["rejections"],"recipes":[]}
        for recipe in checked["recipes"]:
            category = recipe.design.meal_types[0]
            limits = {"min_protein_g":args.protein if args.protein is not None else 0,
                      "min_carbs_g":0,"min_fat_g":0,"max_kcal":4000}
            request = PlanRequest(recipes=0,max_stores=args.max_stores,diversity_mode="cheapest",
                purchase_planning_mode=args.purchase_mode,recipe_preferences={"mode":"complete"},
                personal={"use_pantry":False,"allow_nutrition_estimates":args.allow_nutrition_estimates,
                          "meals":[{"meal_type":category,"count":1,"servings":recipe.servings,
                                    "recipe_choices":{},"limits":limits}]})
            planner = PersonalPlanner(request,Settings(price_provider="mock",complete_recipes_enabled=True),
                prepared,{"revision":0,"items":[],"reservations":{},"events":{}},facts=facts,now=clock)
            row = {"id":recipe.design.base_id,"content_version":recipe.design.version,
                   "meal_type":category,"explicit_conditions":request.model_dump(mode="json"),
                   "protein_target":args.protein,"numerical_macro_probe_minima":0}
            try:
                recipe = planner.clean_recipe(recipe,planner.meals[category])
                result = planner.basket([MealSlot(id=category+"-1",day=1,meal_type=category,recipe=recipe)])
                row.update(status="qualified",basket=result["basket"].model_dump(mode="json"),
                           audit=result["audit"].model_dump(mode="json"),checks=result.get("checks"),
                           nutrition=result.get("nutrition"))
            except ValueError as error:
                row.update(status="stopped",reason=str(error),stage=getattr(error,"stage",None),code=getattr(error,"code",None))
            row["candidate_trace"] = planner.product_trace.snapshot()
            report["recipes"].append(row)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_bytes(encoded(report))
    report["wall_seconds"] = time.perf_counter()-started
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_bytes(encoded(report))
    print(json.dumps({k:v for k,v in report.items() if k not in {"recipes","dependencies"}},ensure_ascii=False))
    if report.get("rejections") or (args.command == "qualify" and any(
            row["status"] != "qualified" for row in report["recipes"])):
        raise SystemExit(1)


if __name__ == "__main__":main()
