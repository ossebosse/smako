"""Content-driven CLI: author -> validate -> diff -> import -> prepare -> qualify -> build.

`author` standardizes a compact smako-recipe-authoring-v1 file (see
docs/recipes/AUTHORING.md) into an ordinary pack and can import, prepare and
qualify it in one run.

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
    revoke_recipe,
    validate_pack,
)


def _preparation_facts(universe, path):
    from app.services.official_product_facts import shell_egg_quantity_proofs
    from app.services.personal_policy import ProductFacts
    from app.services.personal_source_facts import FactsCollection
    document = json.loads(path.read_bytes())
    facts = FactsCollection({tuple(k):ProductFacts(**v) for k,v in document["facts"]})
    facts.version = document["facts_version"]
    shell_egg_quantity_proofs(universe.universe.products, facts)
    return facts


def _prepare_current_cli(args):
    from app.services.meal_library_content import library_signature
    from app.services.meal_prepared_artifacts import (
        prepare_content,
        prepare_current_sources,
        shared_preparation,
    )
    from app.services.recipe_library import _current_issued_index, current_recipes
    if args.universe:
        from app.services.personal_source_facts import load_retained_facts
        from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
        universe = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
        if args.facts:
            facts = _preparation_facts(universe, args.facts)
        else:
            facts = load_retained_facts(universe)
        result = prepare_current_sources(universe, facts, portions=args.servings or (4,))
    else:
        with shared_preparation({"library":library_signature(), "scope":"current_content", "portions":args.servings}) as lease:
            result = prepare_content(current_recipes())
            result["prepared_portions"] = {str(n):len(_current_issued_index(n)) for n in args.servings}
        result["ready"] = lease.ready
        result["persistence_failures"] = lease.failures
    result["manifest_sha256"] = library_signature()
    if args.universe:
        result["artifact_sha256"] = digest(args.universe.read_bytes())
        result["facts_sha256"] = digest(args.facts.read_bytes()) if args.facts else None
    result["library_scope"] = "current_manifest"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("expand", help="Expand reviewed flexible families to an ordinary meal pack")
    p.add_argument("input", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("author", help="Standardize compact recipes; optionally import, prepare and qualify")
    p.add_argument("input", type=Path)
    p.add_argument("--output", type=Path, required=True, help="Standardized smako-meal-pack-v1 file")
    p.add_argument("--report", type=Path, help="Standardization/readiness/qualification report")
    p.add_argument("--import", dest="do_import", action="store_true", help="Import the pack into the library")
    p.add_argument("--prepare", type=int, action="append", choices=range(1,13), default=[],
                   help="Prepare structure and these portion sizes after import (repeatable)")
    p.add_argument("--universe", type=Path, help="Prepared PriceUniverse artifact for qualification")
    p.add_argument("--facts", type=Path, help="Offline product-facts export (else retained facts are loaded)")
    p.add_argument("--clock", help="ISO date/time with offset for qualification")
    p.add_argument("--purchase-mode", choices=["exact","estimated"], default="exact")
    p.add_argument("--max-stores", type=int, default=2)
    p = sub.add_parser("revoke")
    p.add_argument("--recipe-id", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--output", type=Path, required=True)
    for name in ["validate", "diff", "import"]:
        p = sub.add_parser(name)
        p.add_argument("input",type=Path)
        p.add_argument("--output",type=Path)
        if name == "import":p.add_argument("--accept-id",action="append")
    for name in ["prepare", "build"]:
        p = sub.add_parser(name)
        p.add_argument("--output",type=Path,required=True)
        p.add_argument("--universe",type=Path,help="Prepare public source projections for this exact artifact")
        p.add_argument("--facts",type=Path,help="Exact retained public facts export for this artifact")
        if name == "prepare":
            p.add_argument("--current",action="store_true",help="Coordinate bounded cache retention for only the current manifest")
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
    if args.command == "expand":
        from app.services.flexible_recipes import expand_pack
        from app.services.meal_library_content import atomic_write
        if args.input.resolve() == args.output.resolve():
            raise ValueError("Källan och det utökade paketet måste vara olika filer")
        expanded = expand_pack(args.input)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(args.output, encoded(expanded))
        print(json.dumps({"pack_id": expanded["pack_id"], "recipes": len(expanded["recipes"]),
                          "output": str(args.output), "wall_seconds": time.perf_counter() - started}))
        return
    if args.command == "author":
        _author(args, started)
        return
    if args.command == "revoke":
        report = revoke_recipe(args.recipe_id, args.reason)
    elif args.command in {"validate","diff","import"}:
        checked = validate_pack(args.input)
        report = {k:v for k,v in checked.items() if k != "recipes"}
        report["valid_identities"] = [f"{r.design.base_id}:{r.design.version}:{r.design.variant_id}" for r in checked["recipes"]]
        if args.command == "diff":report["diff"] = pack_diff(checked)
        if args.command == "import":report = import_pack(args.input,accepted_ids=args.accept_id)
    elif args.command in {"prepare","build"}:
        if getattr(args, "current", False):
            report = _prepare_current_cli(args)
        else:
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
                from app.services.meal_prepared_artifacts import (
                    declaration_index,
                    prepare_ingredient_search,
                )
                from app.services.personal_source_facts import facts_version, load_retained_facts
                from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
                universe = PreparedPriceUniverseArtifact.model_validate_json(args.universe.read_bytes()).restore()
                facts = _preparation_facts(universe, args.facts) if args.facts else load_retained_facts(universe)
                def exact_facts(product):
                    fact = facts.get((product.store_id,product.product_id))
                    return fact if (fact and fact.source and fact.source_product_id == product.product_id
                                    and product.source_provenance and fact.source_snapshot_id ==
                                    product.source_provenance.source_snapshot_id) else None
                classes = declaration_index(universe.universe,facts,exact_facts)
                ingredients = prepare_ingredient_search(universe)
                report["source_preparation"] = {"universe_id":universe.universe.universe_id,
                    "artifact_sha256":digest(args.universe.read_bytes()),
                    "facts_version":getattr(facts,"version",None) or facts_version(facts),
                    "classified_products":len(classes),"ingredient_queries":len(ingredients),
                    "purchase_qualification":"not_performed"}
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
                           nutrition=result.get("checks",{}).get("nutrition"))
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


def _author(args, started):
    from datetime import UTC

    from app.services.recipe_authoring import library_vocabulary, readiness, standardize, write_json
    from app.services.recipe_library import current_recipes

    source = json.loads(args.input.read_text(encoding="utf-8"))
    vocabulary = library_vocabulary(current_recipes(len(manifest_entries()["current"])))
    pack, rows = standardize(source, vocabulary, reviewed_at=datetime.now(UTC).date().isoformat())
    write_json(args.output, pack)
    checked = validate_pack(args.output)
    report = {"pack_id": pack["pack_id"], "output": str(args.output), "recipes": rows,
              "rejections": checked["rejections"]}
    if checked["rejections"]:
        return _finish(args, report, started)
    if args.do_import:
        imported = import_pack(args.output)
        report["import"] = {k: imported.get(k) for k in ("published_file", "diff", "rejections", "manifest_sha256")}
        if imported.get("rejections"):
            report["rejections"] = imported["rejections"]
            return _finish(args, report, started)
        from app.services.recipe_library import current_recipes as current
        issued = [r for r in current(len(manifest_entries()["current"]))
                  if r.design.content_source and r.design.content_source.pack_id == pack["pack_id"]]
        ready = readiness(issued)
        for row in rows:
            row["default_selection"] = ready.get(row["id"])
        if args.prepare:
            # Precompute what the planner otherwise builds inside the first user
            # request: content structure and the requested portion scalings.
            from app.services.meal_prepared_artifacts import prepare_content
            from app.services.recipe_library import _registered_historical_portions
            m = manifest_entries()
            prepare_content(load_entries([*m["current"], *m["history"]]))
            report["prepared_portions"] = {str(n): len(_registered_historical_portions(n))
                                           for n in sorted(set(args.prepare))}
        if args.universe:
            report["qualification"] = _qualify_issued(args, issued)
    return _finish(args, report, started)


def _qualify_issued(args, recipes):
    """One-recipe weekly baskets through the ordinary planner, exact by default."""
    from app.config import Settings
    from app.models import PlanRequest
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_policy import PolicyConflict
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

    if not args.clock:
        raise SystemExit("--clock krävs för kvalificering")
    clock = datetime.fromisoformat(args.clock)
    if clock.utcoffset() is None:
        raise SystemExit("--clock måste ha tidszon")
    prepared = PreparedPriceUniverseArtifact.model_validate_json(args.universe.read_bytes()).restore()
    if args.facts:
        from app.services.personal_policy import ProductFacts
        from app.services.personal_source_facts import FactsCollection
        raw = json.loads(args.facts.read_bytes())
        facts = FactsCollection({(r["store_id"], r["product_id"]): ProductFacts(**r["facts"]) for r in raw["rows"]})
        facts.version = raw.get("facts_version")
        # An offline export holds the retained facts before load-time
        # derivations; add the egg standard-weight proofs that
        # load_retained_facts adds (owner decision 2026-10-17/21).
        from app.services.official_product_facts import shell_egg_quantity_proofs
        shell_egg_quantity_proofs(prepared.universe.products, facts)
    else:
        from app.services.personal_source_facts import load_retained_facts
        facts = load_retained_facts(prepared)
    rows = []
    for recipe in recipes:
        meal_type = recipe.design.meal_types[0]
        slot = {"id": f"{meal_type}-1", "day": 1, "meal_type": meal_type, "recipe": recipe.model_dump(mode="json")}
        request = PlanRequest.model_validate({
            "recipes": 1 if meal_type == "dinner" else 0, "max_stores": args.max_stores,
            "purchase_planning_mode": args.purchase_mode, "recipe_preferences": {"mode": "complete"},
            "personal": {"allow_nutrition_estimates": True, "pantry_revision": 0, "slots": [slot],
                         "meals": [{"meal_type": meal_type, "count": 1, "servings": recipe.servings}]}})
        row = {"id": f"{recipe.design.base_id}:{recipe.design.version}:{recipe.design.variant_id}",
               "name": recipe.name}
        try:
            plan = PersonalPlanner(request, Settings(complete_recipes_enabled=True, price_provider="own"),
                                   prepared, {"revision": 0, "items": [], "reservations": {}, "events": {}},
                                   facts=facts, now=clock).create()
            row.update(status="qualified", total=plan.optimized_basket.total)
        except (PolicyConflict, ValueError) as error:
            row.update(status="stopped", reason=str(error), code=getattr(error, "code", None))
        rows.append(row)
    return {"universe_id": prepared.universe.universe_id, "clock": args.clock,
            "purchase_mode": args.purchase_mode, "max_stores": args.max_stores, "recipes": rows}


def _finish(args, report, started):
    from app.services.recipe_authoring import write_json

    report["wall_seconds"] = round(time.perf_counter() - started, 2)
    if args.report:
        write_json(args.report, report)
    print(json.dumps({"pack_id": report["pack_id"], "recipes": len(report["recipes"]),
                      "warnings": sum(len(r["warnings"]) for r in report["recipes"]),
                      "rejections": len(report["rejections"]),
                      "qualified": sum(r["status"] == "qualified" for r in report.get("qualification", {}).get("recipes", [])),
                      "wall_seconds": report["wall_seconds"]}, ensure_ascii=False))
    stopped = any(r["status"] != "qualified" for r in report.get("qualification", {}).get("recipes", []))
    if report["rejections"] or stopped:
        raise SystemExit(1)


if __name__ == "__main__":main()
