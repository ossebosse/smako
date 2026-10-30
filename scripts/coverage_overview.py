"""Offline product/recipe coverage through Smako's real resolver and final basket.

Run from the repository root. JSON is the agent contract, Markdown the CI view.
No retailer calls, source activation, user profiles or production writes.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import platform
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT), str(ROOT / "scripts/recipe_layer")]

SCHEMA = "smako-coverage-overview-v1"
REASONS = {
    "recipe_match": "Identitet, sammansättning eller tillagningsform passar inte receptet",
    "quantity_unit": "Mängden/enheten kan inte styrkas för receptets behov",
    "price_contract": "Prisvillkor, giltighet eller viktuppskattning hindrar köp",
    "store_freshness": "Butiken/priskontexten ingår inte i det användbara urvalet",
    "policy": "Personliga krav eller nödvändiga produktfakta kan inte styrkas",
    "variant_properties": "Begärda produktegenskaper kan inte styrkas",
}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".next")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def offline():
    os.environ.update(PYTHON_DOTENV_DISABLED="1", SMAKO_PLANNER_SHARED_RESOLUTION="0")

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("Coverage runs offline; network is forbidden")
    sys.addaudithook(audit)


class CoverageTrace:
    """Compact unlimited product inventory; aggregate only actual resolver stops.

    Installed on the diagnostic planner, never on the serving planner. Recording
    all candidate keys avoids the production trace's intentional 256-item sample.
    No unvisited product is classified as rejected, and passing another recipe
    always takes precedence over a stop observed on an incompatible recipe.
    """
    def __init__(self, products):
        self.products = {(p.store_id, p.product_id): True for p in products}
        self.stops = defaultdict(set)
        self.examples = defaultdict(list)
        self.reached = set()
        self.collect = True
        self.comparisons = []

    def event(self, product, recipe, ingredient, stage, outcome, reason, **evidence):
        if not self.collect:
            return
        key = (product.store_id, product.product_id)
        self.reached.add(key)
        if outcome == "stopped":
            self.stops[stage].add(key)
            if reason not in self.examples[stage] and len(self.examples[stage]) < 3:
                self.examples[stage].append(reason)

    @staticmethod
    def identity(recipe):
        from app.services.product_planning_trace import recipe_identity
        return recipe_identity(recipe)


def product_counts(products, accepted, trace):
    keys = {(p.store_id, p.product_id) for p in products}
    stopped = set().union(*trace.stops.values()) if trace.stops else set()
    rejected = stopped - accepted
    # These are disjoint product states. The reason lists below can overlap.
    unexplained = keys - accepted - rejected
    return {
        "retained_product_rows": len(keys), "recipe_candidate_rows": len(accepted),
        "rejected_in_tested_paths_rows": len(rejected), "not_demonstrated_rows": len(unexplained),
        "candidate_percent": round(100 * len(accepted) / len(keys), 2) if keys else None,
        "rejection_reasons": sorted([
            {"stage": stage, "label": REASONS.get(stage, stage),
             "product_rows": len(values - accepted), "examples": trace.examples[stage]}
            for stage, values in trace.stops.items() if values - accepted
        ], key=lambda row: (-row["product_rows"], row["stage"])),
    }


def rank_blockers(recipes, scopes):
    affected, alone = defaultdict(set), defaultdict(set)
    for row in recipes:
        groups = {scopes[key]["group"] for key in row["blocking_scope_ids"]}
        for group in groups:
            affected[group].add(row["id"])
            if len(groups) == 1:
                alone[group].add(row["id"])
    return [{"ingredient": group, "blocked_recipes": len(ids),
             "sole_input_blocker_recipes": len(alone[group]), "recipe_ids": sorted(ids)}
            for group, ids in sorted(affected.items(), key=lambda pair: (-len(pair[1]), pair[0]))]


def recipe_totals(rows):
    return {"total": len(rows), "inputs_resolved": sum(not r["blocking_scope_ids"] for r in rows),
            "basket_status": dict(sorted(Counter(r["basket"] for r in rows).items()))}


def gap_queries(recipes):
    from app.services.ingredient_normalizer import CANONICAL_ALIASES, canonicalize_ingredient_name
    used = {canonicalize_ingredient_name(i.name) for _, r in recipes for i in r.ingredients}
    # Collector keys such as `cheese`/`milk` are not authored ingredient names.
    # Probing them as new ingredients would falsely claim missing cheese recipes.
    names = {canonicalize_ingredient_name(name) for name in CANONICAL_ALIASES} | used
    return names, used


def basket_check(planner, recipe, seconds):
    from app.models.personal import MealSlot
    from app.services.plan_jobs import PlanningDeadlineExceeded, planning_deadline
    started = time.perf_counter()
    meal = recipe.design.meal_types[0]
    try:
        with planning_deadline(seconds):
            result = planner.basket([MealSlot(id=meal + "-1", day=1, meal_type=meal, recipe=recipe)], final=True)
        basket, audit = result["basket"], result["audit"]
        if not audit.passed or basket.store_count > planner.request.max_stores:
            raise RuntimeError("Final basket invariant failed")
        evidence = {"basket": basket.model_dump(mode="json"), "audit": audit.model_dump(mode="json"),
                    "checks": result["checks"], "remaining_demands": result["remaining_demands"]}
        return {"status": "verified", "total": basket.total, "evidence_sha256": digest(evidence),
                "selected_products": sorted({(i.store_id, i.product_id) for s in basket.stores for i in s.items}),
                "audit_passed": True, "store_count": basket.store_count,
                "seconds": time.perf_counter() - started}
    except PlanningDeadlineExceeded:
        return {"status": "search_incomplete", "seconds": time.perf_counter() - started}
    except ValueError as exc:
        return {"status": "checkout_blocked", "reason": str(exc), "code": getattr(exc, "code", None),
                "stage": getattr(exc, "stage", None), "seconds": time.perf_counter() - started}


def run_mode(prepared, facts, recipes, originals, scope, mode, args):
    from app.services.recipe_library import _scaled
    from coverage_reference import planner_for
    started = time.perf_counter()
    planner = planner_for(mode, prepared, facts, scope)
    trace = CoverageTrace(prepared.universe.products)
    planner.product_trace = trace
    planner.diagnostics.product_trace = None
    accepted, viable, selected = set(), set(), set()
    recipe_indexes_by_product = defaultdict(list)
    scopes, rows, groups = {}, [], {}
    phase = {"planner_load": time.perf_counter() - started, "input_resolution": 0.0, "checkout": 0.0}
    for index, (rid, original) in enumerate(recipes):
        recipe = _scaled(original, scope["servings"][original.design.meal_types[0]])
        meal = planner.meals[recipe.design.meal_types[0]]
        blocked, recipe_products, recipe_groups = set(), set(), set()
        before = time.perf_counter()
        # Call the ordinary resolver per issued recipe. Its own key includes the
        # reviewed preparation/forms; an ingredient name alone is not a cache key.
        for ingredient in planner.service.normalizer.normalize_and_aggregate([recipe]):
            source = next(i for i in recipe.ingredients if i.canonical_name == ingredient.canonical_name)
            group = f"{ingredient.canonical_name}|{source.form}|{ingredient.unit}"
            recipe_groups.add(group)
            item = {"name": ingredient.canonical_name, "form": source.form, "unit": ingredient.unit,
                    "quantity": ingredient.required_quantity,
                    "requirements": list(source.product_requirements or ()), "group": group}
            # Keep the complete authored recipe value in the resolution identity.
            key = digest([item, recipe.model_dump(mode="json"), mode])
            group_row = groups.setdefault(group, {"ingredient": group, "recipes": set(), "base_dishes": set(),
                                                  "candidates": set(), "input_resolved": set(), "verified": set()})
            group_row["recipes"].add(rid)
            group_row["base_dishes"].add(recipe.design.base_id)
            try:
                candidates = planner.resolve(ingredient.canonical_name, ingredient.required_quantity, ingredient.unit,
                    profile=planner._merged_profile(meal), organic_animals=False, recipe=recipe)
                if not candidates:
                    raise RuntimeError("Resolver returned an empty success")
                keys = {(c.store_id, c.product_id) for _, c in candidates}
                accepted.update(keys)
                recipe_products.update(keys)
                group_row["candidates"].update(keys)
            except ValueError as exc:
                blocked.add(key)
                scopes[key] = {**item, "reason": str(exc), "code": getattr(exc, "code", None)}
        phase["input_resolution"] += time.perf_counter() - before
        row = {"id": rid, "name": recipe.name, "base_id": recipe.design.base_id,
               "original_import_id": originals.get(rid), "blocking_scope_ids": sorted(blocked),
               "basket": "data_blocked" if blocked else "not_checked"}
        if not blocked and args.baskets:
            trace.collect = False  # Input rejection counts must not mix later basket attempts.
            receipt = basket_check(planner, recipe, args.variant_seconds)
            trace.collect = True
            phase["checkout"] += receipt["seconds"]
            row.update(basket=receipt["status"], checkout=receipt)
            if receipt["status"] == "verified":
                viable.update(recipe_products)
                selected.update(tuple(k) for k in receipt["selected_products"])
        for group in recipe_groups:
            if not blocked:
                groups[group]["input_resolved"].add(rid)
                if row["basket"] == "verified":
                    groups[group]["verified"].add(rid)
        for product_key in recipe_products:
            recipe_indexes_by_product[product_key].append(index)
        rows.append(row)
        if index % 200 == 0:
            print(json.dumps({"mode": mode, "recipes_checked": index + 1,
                              "seconds": round(time.perf_counter() - started, 2)}), flush=True)

    trace.collect = False
    before = time.perf_counter()
    # Generic probes discover gaps in existing canonical/declared food groups.
    # They are leads for authoring, never a fabricated complete recipe approval.
    names, used_names = gap_queries(recipes)
    opportunities = []
    for name in sorted(names):
        candidates = set()
        for unit in ("g", "ml", "st"):
            try:
                found = planner.resolve(name, 1, unit, profile=planner.spec.profile)
                candidates.update((c.store_id, c.product_id) for _, c in found)
            except ValueError:
                pass
        uncovered = candidates - accepted
        if uncovered:
            opportunities.append({"ingredient": name, "generic_candidate_rows": len(candidates),
                "uncovered_product_rows": len(uncovered), "has_authored_recipes": name in used_names,
                "next_action": "review_form_or_product_facts" if name in used_names else "author_and_review_recipe",
                "example_products": [list(k) for k in sorted(uncovered)[:5]]})
    phase["gap_probes"] = time.perf_counter() - before
    product_summary = product_counts(prepared.universe.products, accepted, trace)
    product_summary.update(candidate_in_verified_recipe_rows=len(viable), bought_in_verified_basket_rows=len(selected))
    unseen_categories = defaultdict(list)
    for p in prepared.universe.products:
        if (p.store_id, p.product_id) not in accepted:
            unseen_categories[p.category or "Okänd kategori"].append(p)
    unclassified = [{"category": category, "product_rows": len(products),
                     "next_action": "review_food_identity_and_recipe_relevance",
                     "examples": [{"store_id": p.store_id, "product_id": p.product_id, "name": p.name}
                                  for p in products[:3]]}
                    for category, products in sorted(unseen_categories.items(), key=lambda kv: (-len(kv[1]), kv[0]))]
    product_file = args.output / (mode + "-products.csv.gz")
    with gzip.open(product_file, "wt", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["store_id", "product_id", "name", "category", "gtin", "status", "candidate_in_verified_recipe", "bought", "stop_stages",
                         "recipe_variants", "base_dishes", "recipe_indexes"])
        for p in prepared.universe.products:
            key = (p.store_id, p.product_id)
            stages = sorted(s for s, keys in trace.stops.items() if key in keys)
            status = "recipe_candidate" if key in accepted else "rejected_in_tested_paths" if stages else "not_demonstrated"
            indexes = recipe_indexes_by_product[key]
            writer.writerow([p.store_id, p.product_id, p.name, p.category, getattr(p, "gtin", None), status,
                             key in viable, key in selected, ";".join(stages), len(indexes),
                             len({rows[i]["base_id"] for i in indexes}), ";".join(map(str, indexes))])
    group_rows = [{"ingredient": key, "recipe_variants": len(v["recipes"]), "base_dishes": len(v["base_dishes"]),
                   "candidate_product_rows": len(v["candidates"]), "input_resolved_recipes": len(v["input_resolved"]),
                   "verified_recipes": len(v["verified"]), "recipe_ids": sorted(v["recipes"])} for key, v in sorted(groups.items())]
    imported = [r for r in rows if r["original_import_id"]]
    return {"products": product_summary, "all_recipes": recipe_totals(rows), "imported_recipes": recipe_totals(imported),
            "blockers": rank_blockers(imported, scopes), "all_library_blockers": rank_blockers(rows, scopes),
            "recipes": rows, "blocking_scopes": scopes, "ingredient_coverage": group_rows,
            "uncovered_categories": unclassified,
            "recipe_opportunities": sorted(opportunities, key=lambda r: (r["has_authored_recipes"], -r["uncovered_product_rows"], r["ingredient"])),
            "phases_seconds": phase, "wall_seconds": time.perf_counter() - started}


def markdown(report):
    scope = report["scope"]
    lines = ["# Smako: varor, recept och täckning", "",
             f"Underlag: **{scope['name']}**. Prisklocka: `{scope['clock']}`.",
             f"Kod: `{report['code_revision']}`. Aktiva varianter: **{report['active_recipe_count']}**; importerade: **{report['imported_recipe_count']}**.", "",
             ("Produktpost = en vara i en priskontext; samma vara i flera butiker räknas flera gånger. "
             "Nämnaren är bevarade PriceUniverse-poster, inte alla råposter som hämtats från handlarna. Avvisningar före PriceUniverse är inte mätta."), "",
             "| Mått | Exakt | Med tillåtna uppskattningar |", "| --- | ---: | ---: |"]
    fields = [("Inlästa produktposter", "products", "retained_product_rows"),
              ("Kandidat för minst en receptingrediens", "products", "recipe_candidate_rows"),
              ("Stoppad i prövade receptvägar", "products", "rejected_in_tested_paths_rows"),
              ("Användbarhet ännu inte visad", "products", "not_demonstrated_rows"),
              ("Kandidat i ett recept med verifierad hel korg", "products", "candidate_in_verified_recipe_rows"),
              ("Importerade: alla ingredienser stöds", "imported_recipes", "inputs_resolved")]
    for label, section, field in fields:
        lines.append(f"| {label} | " + " | ".join(str(report["modes"][m][section][field]) for m in ("exact", "estimated")) + " |")
    for status, label in [("verified", "Importerade: hel korg verifierad"), ("checkout_blocked", "Importerade: stopp vid checkout"),
                          ("search_incomplete", "Importerade: sökningen hann inte klart"), ("not_checked", "Importerade: korg inte kontrollerad")]:
        lines.append(f"| {label} | " + " | ".join(str(report["modes"][m]["imported_recipes"]["basket_status"].get(status, 0)) for m in ("exact", "estimated")) + " |")
    lines += ["", ("Uppskattningsläget är ett separat uttryckligt val. Kandidatstöd bevisar inte hela korgen, "
              "alla användarkrav eller en komplett veckomeny. En vara kan vara kandidat utan att bli det billigaste köpet.")]
    for mode, label in (("exact", "Exakt"), ("estimated", "Med tillåtna uppskattningar")):
        data = report["modes"][mode]
        lines += ["", f"## {label}: främsta avvisningsorsaker", "",
                  "Unika produktposter som inte godkändes i någon prövad receptväg. Orsaksgrupper kan överlappa.", "",
                  "| Orsak | Produktposter |", "| --- | ---: |"]
        lines += [f"| {r['label']} | {r['product_rows']} |" for r in data["products"]["rejection_reasons"]]
        lines += ["", f"## {label}: varor som blockerar flest importerade recept", "",
                  "Sista kolumnen är ett övre tak på möjlig förbättring av ingrediensstödet, inte lovade hela korgar.", "",
                  "| Ingrediens / form / enhet | Recept | Enda ingredienshindret |", "| --- | ---: | ---: |"]
        lines += [f"| {r['ingredient'].replace('|', ' / ')} | {r['blocked_recipes']} | {r['sole_input_blocker_recipes']} |" for r in data["blockers"][:15]]
    data = report["modes"]["estimated"]
    lines += ["", "## Recept att lägga till eller granska", "",
              ("Prioriterat efter antal produktposter med generiskt kandidatstöd som saknar stöd i bibliotekets recept. "
              "Detta är granskningsförslag; generiskt stöd bevisar inte receptets form, mängd eller hel korg. "
              "Oklassificerade och aldrig sökta varor finns i produktfilen och är inte automatiskt receptluckor."), "",
              "| Råvara | Oanvända produktposter | Nästa steg |", "| --- | ---: | --- |"]
    lines += [f"| {r['ingredient']} | {r['uncovered_product_rows']} | " +
              ("Granska form/varufakta i befintliga recept" if r["has_authored_recipes"] else "Lägg till och granska recept") + " |"
              for r in data["recipe_opportunities"][:20]]
    lines += ["", "Fullständig koppling råvara → recept, alla hinder och produktstatus finns i `overview.json` och `*-products.csv.gz`.",
              "", "## Prestanda", "", ("Denna körning mäter inventering och enskild checkout, inte tid till genererad veckomeny. "
              "Faser per läge finns i JSON. Kallstart/varm ny begäran/identisk upprepning och end-to-end-förslaget beskrivs i `docs/COVERAGE-OVERVIEW.md`."),
              "", (f"Rapportkörning: {report['wall_seconds']:.1f} s på {report['environment']['platform']}. "
              "CI-maskinens väggtid är information, inte ett produktlöfte.")]
    return "\n".join(lines) + "\n"


def main(args):
    offline()
    import subprocess

    from app.services.meal_library_content import identity
    from app.services.meal_prepared_artifacts import method_signature
    from app.services.official_product_facts import shell_egg_quantity_proofs
    from app.services.personal_policy import ProductFacts
    from app.services.personal_source_facts import FactsCollection
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
    from app.services.recipe_library import current_recipes
    from coverage_reference import imported_recipes, request_for
    started = time.perf_counter()
    args.output.mkdir(parents=True, exist_ok=True)
    clock = datetime.fromisoformat(args.clock)
    if clock.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    prepared = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    raw = json.loads(args.facts.read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
    facts.version = raw["facts_version"]
    del raw
    shell_egg_quantity_proofs(prepared.universe.products, facts)
    references, imported = imported_recipes()
    originals = {identity(r): key for key, r in zip(references, imported, strict=True)}
    recipes = [(identity(r), r) for r in current_recipes()]
    stores = sorted({p.store_id for p in prepared.universe.products})
    conditions = {mode: request_for(mode, stores).model_dump(mode="json") for mode in ("exact", "estimated")}
    for condition in conditions.values():
        condition["max_stores"] = args.max_stores
    scope = {"name": args.name, "clock": args.clock, "universe_sha256": file_sha(args.universe),
             "facts_sha256": file_sha(args.facts), "facts_version": facts.version,
             "universe_id": prepared.universe.universe_id, "snapshot_ids": sorted(prepared.universe.key.snapshot_ids),
             "method_signature": method_signature(), "store_ids": stores, "max_stores": args.max_stores,
             "servings": {"dinner": 4, "breakfast": 1, "snack": 1}, "pantry": False,
             "conditions": conditions, "manifest_sha256": file_sha(ROOT / "backend/app/data/recipes/library-manifest.json"),
             "recipe_ids_sha256": digest([key for key, _ in recipes]), "imported_reference_ids_sha256": digest(references)}
    report = {"schema": SCHEMA, "status": "in_progress", "scope": scope,
              "generated_at": datetime.now(UTC).isoformat(),
              "code_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "analyzer_sha256": file_sha(__file__), "imported_recipe_count": len(references),
              "active_recipe_count": len(recipes), "source_loading_seconds": time.perf_counter() - started,
              "environment": {"platform": platform.platform(), "python": platform.python_version(), "cpus": os.cpu_count()},
              "scope_sha256": digest(scope), "modes": {}}
    write_json(args.output / "overview.json", report)
    for mode in ("exact", "estimated"):
        report["modes"][mode] = run_mode(prepared, facts, recipes, originals, scope, mode, args)
        write_json(args.output / "overview.json", report)
    report.update(status="complete", wall_seconds=time.perf_counter() - started)
    write_json(args.output / "overview.json", report)
    (args.output / "summary.md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps({m: r["imported_recipes"] for m, r in report["modes"].items()}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("universe", "facts"):
        parser.add_argument("--" + field, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--clock")
    parser.add_argument("--name")
    parser.add_argument("--max-stores", type=int, default=2, choices=range(1, 51))
    parser.add_argument("--baskets", action="store_true")
    parser.add_argument("--variant-seconds", type=float, default=3)
    arguments = parser.parse_args()
    if arguments.reference:
        if not arguments.input_root or any((arguments.universe, arguments.facts, arguments.clock, arguments.name)):
            parser.error("--reference requires --input-root and cannot override explicit reference fields")
        reference = json.loads(arguments.reference.read_bytes())
        for name in ("universe", "facts"):
            path = arguments.input_root / (name + ".json")
            if file_sha(path) != reference["files"][name]["sha256"]:
                parser.error("Reference hash mismatch: " + name)
            setattr(arguments, name, path)
        arguments.clock, arguments.name = reference["clock"], reference["name"]
    elif not all((arguments.universe, arguments.facts, arguments.clock, arguments.name)):
        parser.error("Supply --reference/--input-root or --universe/--facts/--clock/--name")
    if arguments.variant_seconds <= 0:
        parser.error("--variant-seconds must be positive")
    main(arguments)
