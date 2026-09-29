"""Conservative additive nutrient bounds over already qualified candidates.

This is a search filter, never a nutrition approval or a price calculator.
Every surviving selection still passes the ordinary nutrition, checkout and
audit paths. Bounds deliberately relax shared product and store constraints:
an impossible relaxed problem also rules out its more constrained purchases.
Pantry/history and cooked-weight requests use the existing calculation path.
"""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class NutrientLimit:
    slot_id: str
    recipe_name: str
    nutrient: str
    minimum: float | None
    maximum: float | None


@dataclass
class NutritionSearchBounds:
    limits: tuple[NutrientLimit, ...]
    # purchase key -> (store, product) -> per-portion contribution vector.
    contributions: dict[str, dict[tuple[str, str], tuple[float, ...]]]

    def compile_choices(self, keys, choices):
        """Summarize each nutrient class once, not its products on every visit."""
        fixed = {k: v for k, v in self.contributions.items() if k not in keys}
        lower, upper = NutritionSearchBounds(self.limits, fixed).intervals()
        axes = []
        for i, limit in enumerate(self.limits):
            dimensions = []
            for key, groups in zip(keys, choices, strict=True):
                values = self.contributions.get(key)
                if values is None:
                    continue
                intervals = []
                for group in groups:
                    v = [values[(c.store_id, c.product_id)][i] for c in group]
                    intervals.append((min(v), max(v)))
                if any(lo or hi for lo, hi in intervals):
                    dimensions.append((keys.index(key), intervals))
            axes.append((limit, lower[i], upper[i], dimensions))

        def violates(indices):
            for limit, base_lower, base_upper, dimensions in axes:
                lo, hi = base_lower, base_upper
                for dimension, intervals in dimensions:
                    a, b = intervals[indices[dimension]]
                    lo += a
                    hi += b
                tolerance = 1e-9 * max(1.0, abs(lo), abs(hi))
                if (limit.minimum is not None and hi + tolerance < limit.minimum) or (
                    limit.maximum is not None and lo - tolerance > limit.maximum
                ):
                    return True
            return False

        return violates

    def intervals(self, domains=None):
        """Independent per-key extrema; not a purchasable witness basket."""
        lower = [0.0] * len(self.limits)
        upper = [0.0] * len(self.limits)
        for key, values in self.contributions.items():
            vectors = (
                list(values.values())
                if domains is None
                else [values[(c.store_id, c.product_id)] for c in domains[key]]
            )
            if not vectors:
                return None
            for i in range(len(self.limits)):
                lower[i] += min(v[i] for v in vectors)
                upper[i] += max(v[i] for v in vectors)
        return lower, upper

    def violations(self, domains=None):
        interval = self.intervals(domains)
        if interval is None:
            return []  # Missing domains are handled by the purchase path.
        lower, upper = interval
        result = []
        for i, limit in enumerate(self.limits):
            # Conservative guard only. It must never approve a nearly passing
            # result: the final validator retains its exact comparison.
            tolerance = 1e-9 * max(1.0, abs(lower[i]), abs(upper[i]))
            if limit.minimum is not None and upper[i] + tolerance < limit.minimum:
                result.append(
                    {
                        "slot_id": limit.slot_id,
                        "recipe": limit.recipe_name,
                        "nutrient": limit.nutrient,
                        "direction": "minimum",
                        "limit": limit.minimum,
                        "lower": lower[i],
                        "upper": upper[i],
                        "shortfall": limit.minimum - upper[i],
                    }
                )
            elif limit.maximum is not None and lower[i] - tolerance > limit.maximum:
                result.append(
                    {
                        "slot_id": limit.slot_id,
                        "recipe": limit.recipe_name,
                        "nutrient": limit.nutrient,
                        "direction": "maximum",
                        "limit": limit.maximum,
                        "lower": lower[i],
                        "upper": upper[i],
                        "excess": lower[i] - limit.maximum,
                    }
                )
        return result


def build_nutrition_bounds(slots, rows, candidates, allocations, *, meal_limits, evidence):
    """Use qualified evidence in each recipe's actual unit and used quantity.

    ``evidence(candidate, need, slot, requested)`` must be the existing recipe
    qualification function, not a raw declaration or inferred food reference.
    No cross-request cache: facts, prices, membership and source scope have
    already selected these exact domains in the calling planner.
    """
    if allocations or any(r["original_quantity"] > r["quantity"] + 1e-8 for r in rows):
        return None
    active = [s for s in slots if s.recipe and meal_limits(s).active]
    if not active:
        return None
    limits = []
    indices = {}
    for slot in active:
        settings = meal_limits(slot)
        if settings.min_weight_g is not None or settings.max_weight_g is not None:
            return None
        if not isfinite(slot.recipe.servings) or slot.recipe.servings <= 0:
            return None
        nutrients = sorted({k[4:] for k, v in settings.model_dump().items() if v is not None})
        for nutrient in nutrients:
            indices[(slot.id, nutrient)] = len(limits)
            limits.append(
                NutrientLimit(
                    slot.id,
                    slot.recipe.name,
                    nutrient,
                    getattr(settings, "min_" + nutrient, None),
                    getattr(settings, "max_" + nutrient, None),
                )
            )
    if not limits:
        return None
    by_slot = {s.id: s for s in active}
    contributions = {}
    for key, products in candidates.items():
        needs = [r for r in rows if r.get("purchase_key") == key and r["source"] in by_slot]
        if not needs:
            continue
        values = {}
        for candidate in products:
            vector = [0.0] * len(limits)
            for need in needs:
                slot = by_slot[need["source"]]
                requested = {n for sid, n in indices if sid == slot.id}
                fact = evidence(candidate, need, slot, requested)
                if (
                    not fact
                    or fact.nutrition_unit != need["unit"]
                    or not fact.nutrition_basis
                    or fact.nutrition_preparation != "as_sold"
                    or not requested <= fact.nutrition.keys()
                    or not isfinite(need["quantity"])
                    or need["quantity"] < 0
                ):
                    return None
                for nutrient in requested:
                    value = fact.nutrition[nutrient]
                    if not isfinite(value) or value < 0:
                        return None
                    vector[indices[(slot.id, nutrient)]] += (
                        value * need["quantity"] / 100 / slot.recipe.servings
                    )
            values[(candidate.store_id, candidate.product_id)] = tuple(vector)
        if not values:
            return None
        contributions[key] = values
    # Never silently turn an unrepresented required ingredient into zero.
    if any(
        r["source"] in by_slot
        and r["quantity"] > 1e-8
        and r.get("purchase_key") not in contributions
        for r in rows
    ):
        return None
    return NutritionSearchBounds(tuple(limits), contributions)
