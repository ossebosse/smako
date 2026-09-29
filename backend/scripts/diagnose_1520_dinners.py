"""Read-only exhaustive dinner-set diagnostic over the frozen qualified pool.

This is a diagnostic, not an alternative production planner. It keeps the full
saved 15/20 request, evaluates the dinner phase as a partial basket using the
existing rules, and makes no claim about the remaining ten meals.
"""
import argparse
import hashlib
import inspect
import json
import os
import socket
import time
from collections import Counter
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from unittest.mock import patch

from app.config import get_settings
from app.models import PlanRequest
from app.models.personal import MealSlot
from app.services.personal_planner import PersonalPlanner, personal_policy_request
from app.services.personal_policy import distribution_ok
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf8")


def source_identity(candidate):
    return {"store_id": candidate.store_id, "product_id": candidate.product_id}


def intersection_evidence(planner, slots, candidates, groups, rows):
    """Reapply the existing per-need evidence filter, without changing it."""
    result = []
    for group in groups:
        key = group["key"]
        needs = [r for r in rows if r.get("purchase_key") == key and r.get("nutrients")]
        if not needs:
            continue
        per_need = []
        for need in needs:
            recipe = next(s.recipe for s in slots if s.id == need["source"])
            requested = set(need["nutrients"])
            # resolve returns immutable identity matches; use the exact profile,
            # property and source qualification route from PersonalPlanner.
            matched = planner.resolve(need["name"], need["quantity"], need["unit"],
                product_key=need.get("product_key"), properties=need.get("properties", ()),
                profile=need["profile"], organic_animals=need["organic_animals"], food=need["food"])
            qualified = []
            for position, candidate in matched:
                evidence = planner.nutrition_evidence(planner.prepared.universe.products[position],
                    need["name"], need["unit"], requested, recipe)
                if (evidence and evidence.nutrition_unit == need["unit"] and evidence.nutrition_basis
                        and evidence.nutrition_preparation == "as_sold" and requested <= evidence.nutrition.keys()):
                    qualified.append({**source_identity(candidate), "requested_nutrition": {
                        n: evidence.nutrition[n] for n in sorted(requested)},
                        "basis": evidence.nutrition_basis, "unit": evidence.nutrition_unit})
            per_need.append({"slot_id": need["source"], "recipe": recipe.name, "ingredient": need["name"],
                "quantity": need["quantity"], "unit": need["unit"], "qualified_count": len(qualified),
                "qualified_products": qualified[:200], "truncated": len(qualified) > 200})
        selected = candidates[key]
        result.append({"purchase_key": key, "aggregate_quantity": group["quantity"], "unit": group["unit"],
                       "after_intersection_count": len(selected),
                       "after_intersection_products": [source_identity(c) for c in selected[:200]],
                       "truncated": len(selected) > 200, "per_need": per_need})
    return result


def run(args):
    clock = datetime.fromisoformat(args.clock)
    if clock.tzinfo is None:
        raise ValueError("explicit aware frozen clock required")
    artifact_bytes, request_bytes = args.artifact.read_bytes(), args.request.read_bytes()
    prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact_bytes).restore()
    request = PlanRequest.model_validate_json(request_bytes)
    if request.personal.slots is not None or request.personal.product_locks:
        raise ValueError("probe requires the unedited generated request, without product locks")
    state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
    planner = PersonalPlanner(request, get_settings(), prepared, state, now=clock)
    dinner = next(m for m in request.personal.meals if m.meal_type == "dinner" and m.count)
    pool = planner._candidates(dinner)
    policy = planner.service._diversity_policy_for(personal_policy_request(request, dinner.count), request.diversity_mode)
    constraints = planner.service._culinary_constraints(pool, policy)
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = (args.universes / "active/city-lund.json").read_bytes()
    report = {"wall_started_at": datetime.now(UTC).isoformat(), "frozen_clock": clock.isoformat(),
        "artifact_sha256": hashlib.sha256(artifact_bytes).hexdigest(),
        "request_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "universe_id": prepared.universe.universe_id, "source_requests": 0, "activated": False,
        "uid": os.getuid(), "gid": os.getgid(), "cwd": os.getcwd(),
        "planner_sha256": hashlib.sha256(Path(inspect.getfile(PersonalPlanner)).read_bytes()).hexdigest(),
        "dinner_count": dinner.count, "qualified_pool": [r.name for r in pool],
        "scope": "all unique qualified dinner sets; full request retained; breakfast/snack not yet evaluated",
        "rows": [], "complete": False}
    target = args.output / f"{args.label}.json"
    dump(target, report)
    active = None
    ordinary_qualified = planner._qualified_nutrition_basket
    ordinary_nutrition = planner._check_nutrition
    ordinary_optimize = planner.optimizer.optimize

    def nutrition(slots, selected, rows, allocations):
        try:
            return ordinary_nutrition(slots, selected, rows, allocations)
        except ValueError as exc:
            if active is not None:
                code = getattr(exc, "code", type(exc).__name__)
                message = str(exc)
                active["nutrition_failures"][f"{code}: {message}"] += 1
                if len(active["nutrition_failure_samples"]) < 12:
                    active["nutrition_failure_samples"].append({"reason": message,
                        "selected_products": {k: source_identity(v) for k,v in selected.items()}})
            raise

    def optimize(*values, **options):
        try:
            result = ordinary_optimize(*values, **options)
            if active is not None:
                active["priced_combinations"] += 1
            return result
        except ValueError as exc:
            if active is not None:
                active["checkout_failures"][str(exc)] += 1
            raise

    def qualified(slots, baseline, ingredients, candidates, groups, rows, allocations, *, final):
        if active is not None and "intersections" not in active:
            active["intersections"] = intersection_evidence(planner, slots, candidates, groups, rows)
        return ordinary_qualified(slots, baseline, ingredients, candidates, groups, rows, allocations, final=final)

    planner._check_nutrition = nutrition
    planner._qualified_nutrition_basket = qualified
    planner.optimizer.optimize = optimize
    started = time.perf_counter()
    for count, recipes in enumerate(combinations(pool, dinner.count), 1):
        if count > args.max_sets:
            break
        slots = [MealSlot(id=f"dinner-{day}", day=day, meal_type="dinner", recipe=r)
                 for day, r in enumerate(recipes, 1)]
        record = {"set_index": count, "recipes": [r.name for r in recipes]}
        if (not distribution_ok(slots, request.personal.meals, partial=True)
                or not planner.service.menu_optimizer.accepts_recipes(recipes, constraints)):
            record["status"] = "VARIATION_OR_DISTRIBUTION_REJECTED"
        else:
            active = {"nutrition_failures": Counter(), "checkout_failures": Counter(),
                      "nutrition_failure_samples": [], "priced_combinations": 0}
            row_started = time.perf_counter()
            try:
                result = planner.basket(slots, final=False)
                record.update(status="DINNER_PHASE_PASS", cost=result["basket"].total,
                              nutrition=result["checks"]["nutrition"],
                              stores=[s.store_id for s in result["basket"].stores])
            except ValueError as exc:
                record.update(status=getattr(exc, "code", type(exc).__name__), reason=str(exc))
            record.update(seconds=round(time.perf_counter() - row_started, 3), diagnostic=active)
            active = None
        report["rows"].append(record)
        if count % 20 == 0 or record["status"] == "DINNER_PHASE_PASS":
            dump(target, report)
            print(json.dumps({"set": count, "status": record["status"], "seconds": round(time.perf_counter()-started,2)}), flush=True)
    else:
        report["complete"] = True
    report.update(seconds=round(time.perf_counter()-started,3), evaluated_sets=len(report["rows"]),
                  counts=dict(Counter(r["status"] for r in report["rows"])),
                  active_manifest_unchanged=(args.universes / "active/city-lund.json").read_bytes() == manifest)
    if not report["active_manifest_unchanged"]:
        raise ValueError("active manifest changed during readonly probe")
    dump(target, report)
    print(json.dumps({k:report[k] for k in ("complete","evaluated_sets","counts","seconds")}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--clock", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--max-sets", type=int, default=512)
    parser.add_argument("--universes", type=Path, default=Path("/srv/app/var/price_universes"))
    args = parser.parse_args()
    if not 1 <= args.max_sets <= 2048:
        raise ValueError("max-sets must be bounded 1..2048")
    with RefreshRunLock(production_refresh_lock_path(Path("/srv/app/var/grocery/grocery_data.sqlite"), args.universes)), patch.object(socket.socket, "connect", side_effect=AssertionError("network disabled")):
        run(args)


if __name__ == "__main__":
    main()
