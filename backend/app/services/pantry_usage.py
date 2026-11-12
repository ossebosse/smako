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

    forms, units = defaultdict(Counter), defaultdict(Counter)
    for recipe in current_recipes(generation):
        for ingredient in recipe.ingredients:
            name = canonicalize_ingredient_name(ingredient.canonical_name or ingredient.name)
            if ingredient.form:
                forms[name][ingredient.form] += 1
            try:
                units[name][normalize_quantity(ingredient.quantity, ingredient.unit)[1]] += 1
            except (TypeError, ValueError):
                continue
    return ({name: counts.most_common(1)[0][0] for name, counts in forms.items()},
            {name: counts.most_common(1)[0][0] for name, counts in units.items()})


def usual_recipe_use(name: str) -> dict:
    """The form and unit recipes most often use for this name; None when no recipe uses it."""
    from app.services.meal_library_content import manifest_entries

    forms, units = _usage(len(manifest_entries()["current"]))
    canonical = canonicalize_ingredient_name(name)
    return {"form": forms.get(canonical), "unit": units.get(canonical), "used_in_recipes": canonical in units}
