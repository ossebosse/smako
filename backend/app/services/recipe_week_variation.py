"""Explicit authored-dinner distribution, version 1.

One dinner contributes at most once to each substantial protein source. All
authored ``primary`` ingredients count, including both parts of a mixed dish;
the display label cannot hide recurring tofu behind another ingredient.
Cuisine, base ID, dish family and method remain independent dimensions.
"""

from __future__ import annotations

from collections import Counter

from app.services.ingredient_normalizer import canonicalize_ingredient_name

CLASSIFICATION_VERSION = "authored-week-sources-v1"

_SOURCES = {
    "tofu": "tofu", "linser": "linser", "röda linser": "linser",
    "kidneybönor": "bönor", "vita bönor": "bönor", "svarta bönor": "bönor",
    "bönor": "bönor", "kikärtor": "kikärtor",
    "kyckling": "kyckling", "kycklingbröst": "kyckling", "kalkon": "kalkon",
    "lax": "lax", "torsk": "torsk", "tonfisk": "tonfisk", "fisk": "fisk",
    "räkor": "skaldjur", "ägg": "ägg", "nötfärs": "nötkött",
    "köttfärs": "kött", "fläskkött": "fläskkött", "halloumi": "ost",
}


def main_protein_sources(recipe) -> frozenset[str]:
    if recipe.design is None:
        return frozenset()
    names = [i.canonical_name or i.name for i in recipe.ingredients if i.role == "primary"]
    names.append(recipe.design.primary_ingredient)
    mapped = {_SOURCES.get(canonicalize_ingredient_name(name), canonicalize_ingredient_name(name))
              for name in names if name}
    return frozenset(mapped)


def cuisine(recipe) -> str | None:
    return recipe.design.cuisines[0] if recipe.design and recipe.design.cuisines else None


def accepts_week(recipes, preferences, *, dinner_count: int, final: bool) -> bool:
    """Necessary partial bounds and exact final checks, without search weights."""
    remaining = 0 if final else max(0, dinner_count - len(recipes))
    cuisines = {value for recipe in recipes if (value := cuisine(recipe))}
    if preferences.cuisine_distribution == "minimum":
        if len(cuisines) + remaining < preferences.min_distinct_cuisines:
            return False
    elif (preferences.cuisine_distribution == "each_selected"
          and len(set(preferences.cuisines) - cuisines) > remaining):
        return False
    cap = preferences.max_same_main_protein_dinners
    if cap is not None:
        counts = Counter(source for recipe in recipes for source in main_protein_sources(recipe))
        if any(count > cap for count in counts.values()):
            return False
    return True


def week_summary(recipes) -> dict:
    cuisine_counts = Counter(value for recipe in recipes if (value := cuisine(recipe)))
    protein_counts = Counter(source for recipe in recipes for source in main_protein_sources(recipe))
    return {
        "classification_version": CLASSIFICATION_VERSION,
        "cuisines": dict(sorted(cuisine_counts.items())),
        "main_proteins": dict(sorted(protein_counts.items())),
        "distinct_cuisines": len(cuisine_counts),
        "dinner_count": len(recipes),
        "base_ids": sorted({r.design.base_id for r in recipes if r.design}),
        "base_id_counts": dict(sorted(Counter(r.design.base_id for r in recipes if r.design).items())),
        "dish_families": dict(sorted(Counter(r.design.family for r in recipes if r.design).items())),
        "cooking_methods": dict(sorted(Counter(r.design.method for r in recipes if r.design).items())),
    }
