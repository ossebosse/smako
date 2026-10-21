"""How much could a proven lower cost bound prune whole-week evaluations?

Wraps the ordinary BasketOptimizer.optimize of ONE planner run and, for every
whole-week basket (all dinner slots filled), compares the actual checkout
total with a conservative admissible floor computed from the very same
qualified candidates:

  floor = sum over groups of the cheapest single-package price, where any
          candidate with any offer, a weight/rate sale model or no
          positive fixed price contributes 0, and groups whose candidate sets
          share a product are merged (one package might serve both).

It ignores quantities above one package, store limits and pairing, so it
can never exceed the true total (checked for every basket below). A week can
only be pruned when floor > incumbent total; the final paid total is a lower
estimate of every incumbent, so the reported count is an upper estimate.

usage: bound_tightness.py --inputs DIR --case standard --output out.json
"""
import argparse
import json
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.config import Settings
from app.models.product import SaleModel
from app.services.basket_optimizer import BasketOptimizer
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from backend.scripts.planner_acceptance_matrix import matrix_request


def floor(candidate):
    if candidate.sale_model not in {SaleModel.FIXED_PACKAGE, SaleModel.SOLD_BY_PIECE}:
        return Decimal(0)
    # Frozen historical replays must not use today's offer validity. Returning
    # zero for every offer is conservative even for conditional/group discounts.
    if candidate.offers or getattr(candidate, "group_offers", None):
        return Decimal(0)
    values = [candidate.price, candidate.effective_price]
    if candidate.sale_model == SaleModel.SOLD_BY_PIECE:
        values.append(candidate.piece_price)
    positive = [Decimal(str(v)) for v in values if v is not None and v > 0]
    return min(positive, default=Decimal(0))


def week_floor(candidate_map):
    groups = [(key, {(c.store_id, c.product_id) for c in cs}, min((floor(c) for c in cs), default=Decimal(0)))
              for key, cs in candidate_map.items()]
    parent = list(range(len(groups)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    owner = {}
    for index, (_key, products, _floor) in enumerate(groups):
        for product in products:
            if product in owner:
                parent[find(index)] = find(owner[product])
            else:
                owner[product] = index
    components = {}
    for index, (_key, _products, value) in enumerate(groups):
        root = find(index)
        components[root] = min(components.get(root, value), value)
    return sum(components.values(), Decimal(0))


def main():
    from unittest.mock import patch

    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--case", default="standard")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.setdefault("RECIPE_PREPARATION_CACHE_ROOT", str(args.output.with_suffix(".cache")))
    manifest = json.loads((args.inputs / "matrix-inputs.json").read_bytes())
    prepared = PreparedPriceUniverseArtifact.model_validate_json((args.inputs / "combined-prices.json").read_bytes()).restore()
    raw = json.loads((args.inputs / "combined-facts.json").read_bytes())
    facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
    request = matrix_request(json.loads((args.inputs / "combined-request.json").read_bytes()), args.case)
    dinners = sum(m.count for m in request.personal.meals)
    rows = []
    original = BasketOptimizer.optimize

    def observed(self, ingredients, candidate_map, stores, **kwargs):
        basket = original(self, ingredients, candidate_map, stores, **kwargs)
        sources = {s for ingredient in ingredients for s in ingredient.source_recipes}
        rows.append((len(sources), float(week_floor(candidate_map)), float(basket.total)))
        return basket

    with patch.object(BasketOptimizer, "optimize", observed):
        plan = PersonalPlanner(request, Settings(complete_recipes_enabled=True, price_provider="own"), prepared,
                               {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=facts,
                               now=datetime.fromisoformat(manifest["now"])).create()
    paid = float(plan.optimized_basket.total)
    weeks = [(f, t) for n, f, t in rows if n == dinners]
    violations = [(f, t) for _n, f, t in rows if f > t + 1e-9]
    ratios = sorted(f / t for f, t in weeks if t)
    out = {"paid": paid, "baskets": len(rows), "whole_weeks": len(weeks), "floor_above_total_violations": len(violations),
           "floor_to_total_ratio": {"min": ratios[0], "median": ratios[len(ratios) // 2], "max": ratios[-1]} if ratios else None,
           "weeks_prunable_upper_estimate": sum(f > paid for f, _t in weeks),
           "max_floor": max((f for f, _t in weeks), default=None)}
    args.output.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
