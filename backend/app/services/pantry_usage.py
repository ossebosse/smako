"""How the recipe library asks for an ingredient, as a suggestion for the pantry.

A pantry row without a chosen product is only used by a recipe when its unit
and form (raw, dry, as sold ...) are the ones the recipe asks for. This module
reads the form and unit the current recipes most often use for a name, so an
interface can propose them. The user confirms; nothing here states a fact
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


def _usable(typed: str, unit: str | None, rows) -> dict:
    """Per form: in how many recipe uses a row typed like this is accepted, and of how many.

    Uses the planner's own rule (pantry_form_compatible). Many recipes ask for
    a particular kind (which rice, which cut), and only a chosen product can
    show that; such uses count as not accepted here, exactly as when planning.
    """
    from app.services.complete_recipes import pantry_form_compatible

    result: dict[str, list[int]] = {}
    for (name, form, requirements), uses in rows.items():
        try:
            accepted = pantry_form_compatible({"name": typed, "unit": unit, "form": form},
                                              {"name": name, "input_form": form, "product_requirements": requirements})
        except (AttributeError, KeyError, TypeError, ValueError):
            accepted = False
        counts = result.setdefault(form, [0, 0])
        counts[0] += uses if accepted else 0
        counts[1] += uses
    return result


def usual_recipe_use(name: str) -> dict:
    """The form and unit recipes most often use for this name; None when no recipe uses it."""
    from app.services.meal_library_content import manifest_entries

    forms, units, rows = _usage(len(manifest_entries()["current"]))
    canonical = canonicalize_ingredient_name(name)
    return {"form": forms.get(canonical), "unit": units.get(canonical), "used_in_recipes": canonical in units,
            "usable": _usable(name, units.get(canonical), rows.get(canonical, {}))}
