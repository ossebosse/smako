"""Deterministic dietary filtering before recipe candidate generation.

Prices and products stay source-owned.  This module only narrows the canonical
economic ingredient universe and validates the resulting recipes; it never
asks a provider for alternate products and never infers prices.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.models.plan import DietPreference
from app.models.recipe import Recipe
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.product_semantics import semantic_requirement

_MEAT_OR_FISH = frozenset(
    {
        "kyckling",
        "kycklingfilé",
        "kycklinglever",
        "fläskkött",
        "fläskfärs",
        "fläskkotlett",
        "falukorv",
        "korv",
        "nötfärs",
        "nötkött",
        "oxkött",
        "blandfärs",
        "lamm",
        "lammkött",
        "lammfärs",
        "fläsklever",
        "fläsksida med svål",
        "kalvlägg med ben",
        "lufttorkad skinka",
        "kokt skinka",
        "blodpudding",
        "fjälster",
        "gelatinblad",
        "gelatin",
        "kalkon",
        "bacon",
        "skinka",
        "fisk",
        "lax",
        "torsk",
        "tonfisk",
        "sej",
        "räkor",
        "skaldjur",
        "råa räkor",
        "musslor",
        "bläckfisk",
        "makrill",
        "rökt makrill",
        "sardiner",
        "matjessill",
        "stenbitsrom",
        "rimmat fläsk",
        "rökt lax",
        "varmrökt lax",
        "fläskkarré", "kalvfärs", "guanciale", "fisksås", "sardeller",
        "hel kyckling", "nötinnanlår", "högrev", "nötstek", "getkött",
        "nöthjärta", "oxtunga", "nötblod", "räkpasta", "torkade räkor",
        "svensk ansjovis", "svensk ansjovis med spad", "isterband", "ister",
        "nötkött för snabbstekning", "ostronsås", "worcestershiresås",
    }
)
_MEAT_OR_FISH_FAMILIES = frozenset(
    {"meat", "poultry", "fish", "seafood", "shellfish", "organ"}
)
_OTHER_ANIMAL = frozenset(
    {
        "ägg",
        "mjölk",
        "grädde",
        "crème fraiche",
        "ost",
        "smör",
        "yoghurt",
        "yoghurt naturell",
        "kvarg",
        "keso",
        "fetaost",
        "halloumi",
        "grillost",
        "mozzarella",
        "honung",
        "äggvita",
        "äggula",
        "kokta ägg",
        "kondenserad mjölk",
        "ricotta",
        "paneer",
        "getost",
        "mascarpone",
        "ädelost",
        "färskost",
        "kefir",
        "filmjölk",
        "parmesan", "pecorino romano", "ghee", "mjölkpulver", "evaporerad mjölk",
    }
)
_OTHER_ANIMAL_FAMILIES = frozenset({"dairy", "egg"})


def _excluded_by_diet(name: str, preference: DietPreference) -> bool:
    canonical = canonicalize_ingredient_name(name)
    family = semantic_requirement(canonical).food_family
    if preference is DietPreference.VEGETARIAN:
        return canonical in _MEAT_OR_FISH or family in _MEAT_OR_FISH_FAMILIES
    if preference is DietPreference.VEGAN:
        return (
            canonical in _MEAT_OR_FISH
            or canonical in _OTHER_ANIMAL
            or family in _MEAT_OR_FISH_FAMILIES
            or family in _OTHER_ANIMAL_FAMILIES
        )
    return False


def ingredient_is_excluded(name: str, exclusions: Iterable[str]) -> bool:
    """Explicit fish excludes the existing fish family, not only the generic name."""
    canonical = canonicalize_ingredient_name(name)
    exclusions = tuple(exclusions)
    excluded = {canonicalize_ingredient_name(v) for v in exclusions if str(v).strip()}
    return canonical in excluded or (
        any(v.casefold().strip() == "fisk" for v in exclusions)
        and semantic_requirement(canonical).food_family == "fish"
    )


def excluded_ingredients(
    preference: DietPreference | str,
    avoid_ingredients: Iterable[str] = (),
) -> frozenset[str]:
    """Return canonical ingredients excluded by one consumer request."""

    preference = DietPreference(preference)
    excluded = {
        canonicalize_ingredient_name(value)
        for value in avoid_ingredients
        if str(value).strip()
    }
    if preference is DietPreference.VEGETARIAN:
        excluded.update(_MEAT_OR_FISH)
    elif preference is DietPreference.VEGAN:
        excluded.update(_MEAT_OR_FISH)
        excluded.update(_OTHER_ANIMAL)
    return frozenset(excluded)


def filter_economic_pool(
    pool: EconomicIngredientPool,
    *,
    preference: DietPreference | str,
    avoid_ingredients: Iterable[str] = (),
) -> EconomicIngredientPool:
    """Narrow an already local pool without any source/provider request."""

    preference = DietPreference(preference)
    avoid_ingredients = tuple(avoid_ingredients)
    explicitly_excluded = {
        canonicalize_ingredient_name(value)
        for value in avoid_ingredients
        if str(value).strip()
    }
    if preference is DietPreference.MIXED and not explicitly_excluded:
        return pool

    def allowed(name: str) -> bool:
        canonical = canonicalize_ingredient_name(name)
        return not ingredient_is_excluded(canonical, avoid_ingredients) and not _excluded_by_diet(
            canonical, preference
        )

    def candidates(rows: dict[str, list]) -> dict[str, list]:
        return {
            name: values
            for name, values in rows.items()
            if allowed(name)
        }

    return EconomicIngredientPool(
        ingredients=[
            signal
            for signal in pool.ingredients
            if allowed(signal.canonical)
        ],
        candidates_by_name=candidates(pool.candidates_by_name),
        semantic_candidates_by_name=candidates(pool.semantic_candidates_by_name),
        matched_candidates_by_name=candidates(pool.matched_candidates_by_name),
        search_queries_executed=pool.search_queries_executed,
        products_considered=pool.products_considered,
    )


def recipe_respects_diet(
    recipe: Recipe,
    *,
    preference: DietPreference | str,
    avoid_ingredients: Iterable[str] = (),
) -> bool:
    preference = DietPreference(preference)
    avoid_ingredients = tuple(avoid_ingredients)
    return not any(
        (
            ingredient_is_excluded(ingredient.canonical_name or ingredient.name, avoid_ingredients)
            or _excluded_by_diet(
                ingredient.canonical_name or ingredient.name,
                preference,
            )
        )
        for ingredient in recipe.ingredients
    )


__all__ = [
    "excluded_ingredients",
    "filter_economic_pool",
    "recipe_respects_diet",
]
