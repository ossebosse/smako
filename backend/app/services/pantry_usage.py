"""How the recipe library asks for an ingredient, as advice for the pantry.

Pantry goods are taken as uncooked (complete_recipes.pantry_form_compatible).
This module reads which unit the current recipes use for a name, and in how
many recipe uses a row typed with that name would be accepted, so an
interface can say when a chosen product is needed. Nothing here states a fact
about the goods at home, and nothing is matched or priced.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache

from app.services.ingredient_normalizer import canonicalize_ingredient_name, normalize_quantity


@lru_cache(maxsize=2)
def _usage(generation: int):
    from app.services.recipe_library import current_recipes

    forms, units, rows = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    for recipe in current_recipes(generation):
        for ingredient in recipe.ingredients:
            name = canonicalize_ingredient_name(ingredient.canonical_name or ingredient.name)
            if ingredient.form:
                forms[name][ingredient.form] += 1
                rows[name][(ingredient.name, ingredient.form, tuple(ingredient.product_requirements or ()))] += 1
            try:
                units[name][normalize_quantity(ingredient.quantity, ingredient.unit)[1]] += 1
            except (TypeError, ValueError):
                continue
    return ({name: counts.most_common(1)[0][0] for name, counts in forms.items()},
            {name: counts.most_common(1)[0][0] for name, counts in units.items()}, dict(rows))


COOKED_OR_DRAINED = frozenset({"cooked_drained", "preserved_drained"})


def _usable(typed: str, unit: str | None, rows) -> list[int]:
    """In how many recipe uses a row typed like this is accepted, and of how many.

    Uses the planner's own rule (pantry_form_compatible) for an uncooked row.
    Many recipes ask for a particular kind (which rice, which cut), and only a
    chosen product can show that; such uses count as not accepted, exactly as
    when planning. So do recipes that want the food cooked or drained.
    """
    from app.services.complete_recipes import pantry_form_compatible

    fits = total = drained = 0
    for (name, form, requirements), uses in rows.items():
        drained += uses if form in COOKED_OR_DRAINED else 0
        try:
            accepted = pantry_form_compatible({"name": typed, "unit": unit},
                                              {"name": name, "input_form": form, "product_requirements": requirements})
        except (AttributeError, KeyError, TypeError, ValueError):
            accepted = False
        fits += uses if accepted else 0
        total += uses
    # [covered, all uses, uses that want the food cooked or drained]
    return [fits, total, drained]


def usual_recipe_use(name: str) -> dict:
    """The unit recipes most often use for this name, and how many uses an uncooked row covers."""
    from app.services.meal_library_content import manifest_entries

    forms, units, rows = _usage(len(manifest_entries()["current"]))
    canonical = canonicalize_ingredient_name(name)
    return {"form": forms.get(canonical), "unit": units.get(canonical), "used_in_recipes": canonical in units,
            "usable": _usable(name, units.get(canonical), rows.get(canonical, {}))}


def drained_from_package(name: str, product, fact) -> bool:
    """Recipes want this name drained and the product declares no drained mass.

    The planner then counts the package weight (owner decision 2026-11-13),
    and the interface says the drained weight can be lower.
    """
    from app.services.complete_recipes import declared_drained
    from app.services.meal_library_content import manifest_entries

    canonical = canonicalize_ingredient_name(name)
    drained = [(n, form, requirements) for (n, form, requirements) in
               _usage(len(manifest_entries()["current"]))[2].get(canonical, {}) if form in COOKED_OR_DRAINED]
    return bool(drained) and not any(
        declared_drained(canonicalize_ingredient_name(n), form, requirements, product, fact)
        for n, form, requirements in drained)
