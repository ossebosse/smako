"""Bounded exhaustive audit of the retained qualified pool, using existing engines."""

import json
from collections import Counter
from dataclasses import asdict
from decimal import Decimal
from itertools import combinations
from unittest.mock import patch

from app.config import Settings
from app.errors import IncompleteBasketError
from app.models import NormalizedIngredient, PlanRequest
from app.models.personal import MealSlot
from app.services.nutrition_reference import product_reference
from app.services.personal_planner import PersonalPlanner, personal_policy_request
from app.services.personal_policy import PolicyConflict
from app.services.recipe_profile import RecipeProfileBuilder

from backend.scripts.personal_v2_cost_audit import OUTPUT, inputs, save
from backend.scripts.personal_v2_dinners_probe import fixture


def main():
    old, cases = inputs()
    prepared, facts = fixture()
    assert prepared.universe.universe_id == old["price_version"]
    out = {"price_version": old["price_version"], "facts_version": facts.version,
           "complete_ingredient_facts": sum(f.ingredients_complete for f in facts.values()),
           "facts_count": len(facts), "product_alternatives": {}, "menu_audit": {}}
    def planner(case):
        return PersonalPlanner(PlanRequest.model_validate(cases[case]["request"]),
                               Settings(price_provider="mock"), prepared,
                               {"revision": 0, "items": [], "reservations": {}, "events": {}},
                               facts=facts, now=prepared.universe.built_at)

    with patch("socket.socket.connect", side_effect=AssertionError("Forbidden consumer egress")) as network:
        p = planner("same_menu")
        slots = p.spec.slots
        result = p.basket(slots)
        out["same_menu_total"] = result["basket"].total
        out["same_menu_stores"] = []
        for n in (1, 2):
            for subset in combinations(p.view.stores, n):
                ids = {s.store_id for s in subset}
                mapping = {g["key"]: [g["candidates"][i] for i in g["positions"]
                                      if prepared.universe.products[i].store_id in ids]
                           for g in result["groups"]}
                try:
                    b = p.optimizer.optimize(result["ingredients"], mapping, list(subset), max_stores=n)
                    p._check_final(slots, b, result["groups"], result["remaining_demands"], [])
                    row = {"stores": [s.name for s in subset], "status": "PASS", "cost": b.total}
                except (ValueError, IncompleteBasketError) as exc:
                    row = {"stores": [s.name for s in subset], "status": "REJECTED", "reason": str(exc)}
                out["same_menu_stores"].append(row)
        for g in result["groups"]:
            recipes = [s.recipe for s in slots if s.id in g["sources"]]
            req = NormalizedIngredient(canonical_name=g["name"], required_quantity=g["quantity"], unit=g["unit"])
            resolved = p.resolve(g["name"], g["quantity"], g["unit"], profile=p.spec.profile)
            rows = []
            for i, c in resolved:
                product = prepared.universe.products[i]
                fact = p.source_facts(product)
                identity = product_reference(product, g["name"], fact)
                evidence = [p.nutrition_evidence(product, g["name"], g["unit"], {"protein_g", "kcal"}, r)
                            for r in recipes]
                q = p.optimizer._candidate_quotes(req, [c])
                rows.append({"product": product.name, "product_id": product.product_id, "store_id": product.store_id,
                             "store": product.store_name, "package_quantity": product.package_quantity,
                             "reference_id": identity, "qualified_all_recipes": all(evidence),
                             "decision": "qualified" if all(evidence) else "conflicting_data" if fact and fact.conflicts else "mapping_not_qualified" if identity is None else "nutrition_or_preparation_data",
                             "facts_conflicts": fact.conflicts if fact else [],
                             "declared_ingredients": fact.ingredients if fact else [],
                             "quantity_confidence": product.quantity_confidence,
                             "sale_model": product.sale_model,
                             "price_eligible": bool(q),
                             "nutrition": [e.nutrition if e else None for e in evidence],
                             "price": str(q[0].total_price) if q else None,
                             "packages": q[0].packages_needed if q else None,
                             "price_rule": q[0].price_mechanism if q else None})
            rows.sort(key=lambda r: Decimal(r["price"]) if r["price"] else Decimal("Infinity"))
            out["product_alternatives"][g["name"]] = rows
        save(OUTPUT / "candidate-audit.json", out)
        print("Product/store audit complete", flush=True)
        for mode, case in [("balanced", "original"), ("cheapest", "cheapest"), ("no_fish", "no_fish")]:
            p = planner(case)
            try:
                pool = p._candidates(p.spec.meals[0])
            except PolicyConflict:
                pool = []
            policy = p.service._diversity_policy_for(personal_policy_request(p.request, 5), p.request.diversity_mode)
            constraints = p.service._culinary_constraints(pool, policy)
            qualified = []
            singles = []
            for r in pool:
                try:
                    b = p.basket([MealSlot(id="dinner-1", day=1, meal_type="dinner", recipe=r)])
                    qualified.append(r)
                    singles.append({"recipe": r.name, "cost": b["basket"].total, "status": "PASS",
                                    "profile": asdict(RecipeProfileBuilder().build(r)),
                                    "nutrition": b["checks"]["nutrition"]})
                except (ValueError, IncompleteBasketError) as exc:
                    singles.append({"recipe": r.name, "status": "REJECTED", "reason": str(exc)})
            counts = Counter()
            menus = []
            for combo in combinations(qualified, 5):
                counts["combinations"] += 1
                if not p.service.menu_optimizer.accepts_recipes(combo, constraints):
                    counts["variation"] += 1
                    continue
                slots = [MealSlot(id=f"dinner-{i}", day=i, meal_type="dinner", recipe=r)
                         for i, r in enumerate(combo, 1)]
                try:
                    b = p.basket(slots)
                    menus.append({"recipes": [r.name for r in combo], "cost": b["basket"].total,
                                  "stores": [s.store_name for s in b["basket"].stores]})
                    counts["priced"] += 1
                except (ValueError, IncompleteBasketError) as exc:
                    counts[getattr(exc, "stage", None) or "other_evaluation"] += 1
            menus.sort(key=lambda m: (m["cost"], m["recipes"]))
            out["menu_audit"][mode] = {"policy": policy.model_dump(mode="json"), "counts": dict(counts),
                                       "singletons": singles, "menus": menus, "diagnostics": p.diagnostics.snapshot()}
            save(OUTPUT / "candidate-audit.json", out)
            print(json.dumps({"mode": mode, "counts": dict(counts), "minimum": menus[0] if menus else None}), flush=True)
        out["external_calls"] = network.call_count
        assert network.call_count == 0
        save(OUTPUT / "candidate-audit.json", out)


if __name__ == "__main__":
    main()
