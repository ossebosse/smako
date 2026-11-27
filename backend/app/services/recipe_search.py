"""Owner request 2026-11-27: search Smako's recipes by name or ingredient.

A found recipe can be put in the meal plan (a new dinner or in place of a
meal) or its ingredients added to the shopping list. One result per dish
(``design.base_id``): the variant with the median number of ingredients, at
the requested number of portions. Results are ranked by name match, then
general popularity (recipe_popularity.py), then name.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

MAX_RESULTS = 30
STAPLES = frozenset({"salt", "svartpeppar", "vatten"})


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    return " ".join(re.sub(r"[^\wåäöéü]+", " ", text).split())


@lru_cache(maxsize=12)
def _dishes(servings: int):
    from app.services.recipe_library import _registered_portions

    by_base: dict[str, list] = {}
    for recipe in _registered_portions(servings):
        design = recipe.design
        if design is None or design.scaled_from:
            continue
        by_base.setdefault(design.base_id, []).append(recipe)
    rows = []
    for variants in by_base.values():
        variants.sort(key=lambda r: (len(r.ingredients), r.design.variant_id))
        recipe = variants[(len(variants) - 1) // 2]
        rows.append((recipe, _norm(recipe.name), tuple(_norm(i.name) for i in recipe.ingredients)))
    return tuple(rows)


def _summary(recipe) -> dict:
    from app.services.complete_recipes import identity
    from app.services.recipe_popularity import popularity

    d = recipe.design
    return {
        "recipe_id": identity(recipe), "base_id": d.base_id, "name": recipe.name,
        "servings": recipe.servings, "meal_type": d.meal_types[0], "cuisines": list(d.cuisines),
        "vegetarian": d.vegetarian, "fish": d.fish, "popularity": popularity(d.base_id),
        "active_minutes": d.active_minutes, "total_minutes": d.total_minutes or d.estimated_minutes,
        "ingredients": [{"name": i.name, "quantity": i.quantity, "unit": i.unit} for i in recipe.ingredients],
    }


def search(query: str, servings: int = 2, meal_type: str | None = None, limit: int = MAX_RESULTS) -> list[dict]:
    words = _norm(query).split()
    if not words:
        return []
    found = []
    for recipe, name, ingredients in _dishes(servings):
        if meal_type and meal_type not in recipe.design.meal_types:
            continue
        if not all(w in name or any(w in i for i in ingredients) for w in words):
            continue
        in_name = sum(w in name for w in words)
        found.append((-in_name, -(recipe_popularity(recipe) or 3), recipe.name, recipe))
    found.sort(key=lambda row: row[:3])
    return [_summary(row[3]) for row in found[:max(1, min(limit, MAX_RESULTS))]]


def recipe_popularity(recipe):
    from app.services.recipe_popularity import popularity

    return popularity(recipe.design.base_id)


def recipe_by_id(recipe_id: str, servings: int):
    """The current library recipe with this identity, at ``servings`` portions."""
    from app.services.complete_recipes import identity
    from app.services.recipe_library import _registered_portions

    return next((r for r in _registered_portions(servings) if identity(r) == recipe_id), None)


def shopping_rows(recipe) -> list[dict]:
    """The recipe's ingredients as generic shopping-list rows (salt, pepper and water left out)."""
    rows = []
    for ingredient in recipe.ingredients:
        if _norm(ingredient.name) in STAPLES:
            continue
        rows.append({"query": ingredient.name[:120], "quantity": round(ingredient.quantity, 2), "unit": ingredient.unit})
    return rows
