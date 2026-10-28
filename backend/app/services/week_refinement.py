"""Search signals over qualified recipes and already priced whole baskets.

No price, nutrition, stock or promotion calculation lives here. Both proposed
replacements must pass the caller's ordinary whole-week checks and checkout.
"""
from collections import defaultdict
from decimal import Decimal
from heapq import nsmallest
from itertools import combinations

from app.services.basket_calculator import money
from app.services.recipe_candidate_validator import recipe_id
from app.services.stable_candidate_pool import stratified_candidate_shortlist


def surplus_summary(basket, *, preparations=()):
    """Allocate paid merchandise to unused usable quantity; never a saving.

    Currency fractions and package equivalents are dimensionless comparisons.
    Physical quantities stay separated by g/ml/st. Unknown purchase quantities
    cannot masquerade as zero surplus. Estimates retain their explicit status.
    """
    value, packages = Decimal(0), Decimal(0)
    component_unused = defaultdict(Decimal)
    for preparation in preparations:
        purchased = Decimal(str(preparation["purchase_input_quantity_g"]))
        if purchased <= 0:
            continue
        # Allocate the population-estimated coproduct surplus proportionally
        # between purchased input and existing raw stock. This is a search
        # signal only; no future value is subtracted from checkout or booked.
        total = Decimal(str(preparation["input_quantity_g"]))
        surplus = sum((Decimal(str(q)) for q in preparation["estimated_surplus_g"].values()), Decimal(0))
        component_unused[preparation["purchase_key"]] += surplus * purchased / total
    preparation_value = Decimal(0)
    quantities = defaultdict(Decimal)
    unknown, estimated = 0, False
    for store in basket.stores:
        for item in store.items:
            paid = item.merchandise_total
            usable = Decimal(str(item.purchased_usable_quantity))
            extra = component_unused.get(item.ingredient, Decimal(0))
            unused = Decimal(str(item.waste_quantity)) + extra
            if (paid is None or usable <= 0 or unused < 0 or unused > usable
                    or item.quantity_confidence == "unknown" or item.purchase_units):
                unknown += 1
                continue
            estimated |= item.quantity_confidence == "estimated"
            estimated |= extra > 0
            fraction = unused / usable
            value += Decimal(str(paid)) * fraction
            preparation_value += Decimal(str(paid)) * extra / usable
            packages += Decimal(item.packages_needed) * fraction
            quantities[item.unit] += unused
    return {
        "unknown_lines": unknown,
        "unused_purchase_value": float(money(value)) if not unknown else None,
        "unused_package_equivalents": float(packages) if not unknown else None,
        "unused_quantities": {unit: float(amount) for unit, amount in sorted(quantities.items())},
        "quantity_status": "UNKNOWN" if unknown else "ESTIMATED" if estimated else "VERIFIED",
        "method": "proportional_paid_merchandise_cost_of_unused_usable_quantity",
        "deposit_included": False,
        "deducted_from_checkout": False,
        **({"preparation_unused_purchase_value": float(money(preparation_value)),
            "preparation_basis": "estimated_coproduct_mass_proportional_to_purchased_edible_input"}
           if preparations else {}),
    }


def surplus_key(basket, *, preparations=()):
    summary = surplus_summary(basket, preparations=preparations)
    return (summary["unknown_lines"], summary["unused_purchase_value"] or 0,
            summary["unused_package_equivalents"] or 0)


def qualified_joint_proposals(options, anchor, evidence):
    """At most 256 pairs from at most eight qualified choices per position.

    No single-slot feasibility test is used. Retain cheap and overlapping
    choices, fill with the existing culinary stratification, then interleave
    price-led and sharing-led pairs. These are heuristics, never cost bounds.
    """
    ids = {id(s.recipe): recipe_id(s.recipe) for group in options for s in group if s.recipe}
    features = {}
    for group in options:
        for slot in group:
            if not slot.recipe:
                continue
            key = (slot.meal_type, ids[id(slot.recipe)])
            if key not in features:
                e = evidence.get(key)
                ingredients = frozenset((i.canonical_name or i.name, i.unit, i.form) for i in slot.recipe.ingredients)
                features[key] = (e.paid if e else float("inf"), e.packages if e else frozenset(), ingredients)

    def feature(slot):
        return features.get((slot.meal_type, ids.get(id(slot.recipe))), (float("inf"), frozenset(), frozenset()))

    shortlists = []
    for index, group in enumerate(options):
        available = [s for s in group if s.recipe and s != anchor[index]]
        available.sort(key=lambda s: feature(s)[0])
        others = [feature(s) for j, s in enumerate(anchor) if j != index]
        products = set().union(*(f[1] for f in others))
        ingredients = set().union(*(f[2] for f in others))
        shared = sorted(available, key=lambda s: (-len(feature(s)[1] & products),
                        -len(feature(s)[2] & ingredients), feature(s)[0]))
        protected = frozenset(ids[id(s.recipe)] for s in [*available[:2], *shared[:2]])
        if len(available) > 8:
            retained = stratified_candidate_shortlist([s.recipe for s in available], limit=8,
                                                       stable_recipe_ids=protected)
            chosen = {recipe_id(r) for r in retained.recipes}
            available = [s for s in available if ids[id(s.recipe)] in chosen]
        shortlists.append(available)

    def pairs():
        for left, right in combinations(range(len(shortlists)), 2):
            for a, first in enumerate(shortlists[left]):
                for b, second in enumerate(shortlists[right]):
                    x, y = feature(first), feature(second)
                    shared_products, shared_ingredients = len(x[1] & y[1]), len(x[2] & y[2])
                    tie = (a+b, max(a, b), left, right, a, b)
                    yield ((x[0]+y[0], -shared_products, -shared_ingredients, *tie),
                           (-shared_products, -shared_ingredients, x[0]+y[0], *tie),
                           (left, right, first, second))

    # Bounded memory even if later libraries/meal counts grow. Keep both ranking
    # signals without letting a large single queue consume the whole budget.
    cheap = nsmallest(256, pairs(), key=lambda row: row[0])
    shared = nsmallest(256, pairs(), key=lambda row: row[1])
    result, seen = [], set()
    for price_pair, shared_pair in zip(cheap, shared, strict=True):
        for row in (price_pair, shared_pair):
            left, right, first, second = row[2]
            identity = (left, right, ids[id(first.recipe)], ids[id(second.recipe)])
            if identity not in seen:
                seen.add(identity)
                result.append(row[2])
                if len(result) == 256:
                    return result
    return result
