"""Canonical ingredient names and deterministic unit conversion."""

from __future__ import annotations

import re
import unicodedata
from collections import OrderedDict
from collections.abc import Iterable
from decimal import Decimal

from app.models.ingredient import NormalizedIngredient
from app.models.recipe import Recipe

from grocery_data.app.domain.recipe import RECIPE_RELEVANT_INGREDIENTS

# Aliases are intentionally conservative.  In particular, ingredients which
# are not always interchangeable (nötfärs/blandfärs, smör/margarin) remain
# distinct canonical ingredients.
CANONICAL_ALIASES: dict[str, tuple[str, ...]] = {
    # Organ ingredients are distinct recipe requirements.  They deliberately
    # precede the backwards-compatible generic ``kyckling`` identity so a
    # chicken-heart recipe can match heart while ordinary chicken never does.
    "kycklinghjärta": (
        "kycklinghjärta",
        "kycklinghjärtan",
        "kycklinghjarta",
        "kycklinghjartan",
        "kyckling hjärta",
        "kyckling hjärtan",
        "kyckling hjarta",
        "kyckling hjartan",
        "chicken heart",
        "chicken hearts",
        "chicken_heart",
    ),
    "kycklinglever": (
        "kycklinglever",
        "kyckling lever",
        "chicken liver",
        "chicken_liver",
    ),
    "kycklingkrås": (
        "kycklingkrås",
        "kycklingkras",
        "kyckling krås",
        "kyckling kras",
    ),
    "kycklingmage": (
        "kycklingmage",
        "kycklingmagar",
        "kyckling mage",
        "kyckling magar",
        "chicken gizzard",
        "chicken gizzards",
        "chicken_gizzard",
    ),
    "kycklinginälvor": (
        "kycklinginälvor",
        "kycklinginalvor",
        "kyckling inälvor",
        "kyckling inalvor",
        "chicken offal",
        "chicken_offal",
    ),
    # Keep the long-standing Swedish recipe normalization below (filé is
    # aggregated with generic chicken).  This explicit internal canonical is
    # available when a caller deliberately asks for a breast-only semantic
    # requirement rather than when ordinary recipe text happens to say filé.
    "chicken_breast": ("chicken breast",),
    "kyckling": (
        "kyckling",
        "kycklingfilé",
        "kycklingfile",
        "kyckling filé",
        "kyckling file",
        "kycklingbröst",
        "kycklingbrost",
        "bröstfilé",
        "brostfile",
        "kycklinglårfilé",
        "kycklinglarfile",
        "kycklinglår",
    ),
    "nötfärs": ("nötfärs", "notfars"),
    "blandfärs": ("blandfärs", "blandfars"),
    "köttfärs": ("köttfärs", "kottfars"),
    "fläskkött": ("fläsk", "fläskkött", "flask", "flaskkott"),
    "falukorv": ("falukorv",),
    "korv": ("korv",),
    "fisk": ("fisk", "vit fisk", "vitfisk", "torsk", "sej", "kolja"),
    "tonfisk": ("tonfisk", "tuna"),
    "lax": ("lax", "laxfilé", "laxfile"),
    "ägg": ("ägg", "agg", "äggula", "aggula"),
    "bönor": ("bönor", "bonor", "vita bönor", "vita bonor"),
    "kidneybönor": ("kidneybönor", "kidneybonor"),
    "svarta bönor": ("svarta bönor", "svarta bonor"),
    "kokta linser": (
        "kokta linser",
        "färdigkokta linser",
        "fardigkokta linser",
        "linser på burk",
        "linser pa burk",
        "cooked lentils",
        "canned lentils",
    ),
    "torra linser": (
        "torra linser",
        "torkade linser",
        "okokta linser",
        "dry lentils",
        "dried lentils",
    ),
    "linser": ("lins", "linser", "röda linser", "roda linser"),
    "kikärtor": ("kikärta", "kikärtor", "kikärter", "kikarta", "kikartor"),
    "pasta": ("pasta", "spaghetti", "spagetti", "makaroner", "penne"),
    "ris": ("ris", "matris", "basmatiris", "jasminris"),
    "potatis": ("potatis", "potatisar"),
    "couscous": ("couscous",),
    "nudlar": ("nudel", "nudlar", "äggnudlar", "aggnudlar"),
    "gul lök": ("gul lök", "gul lok", "matlök", "matlok", "lök", "lok"),
    "rödlök": ("rödlök", "rodlok", "röd lök", "rod lok"),
    "morot": ("morot", "morötter", "morotter"),
    "tomat": ("tomat", "tomater", "färska tomater", "farska tomater"),
    "paprika": ("paprika", "paprikor"),
    "broccoli": ("broccoli",),
    "purjolök": ("purjolök", "purjolok"),
    "ärtor": ("gröna ärtor", "grön ärta", "ärtor", "ärter"),
    "selleri": ("selleri", "bladselleri", "blekselleri", "stjälkselleri"),
    "vitkål": ("vitkål", "vitkal", "kål", "kal"),
    "frysta grönsaker": (
        "frysta grönsaker",
        "frysta gronsaker",
        "grönsaksblandning",
        "gronsaksblandning",
        "wokgrönsaker",
        "wokgronsaker",
        "wok mix",
        "wokmix",
    ),
    "mjölk": ("mjölk", "mjolk", "standardmjölk", "standardmjolk"),
    "grädde": ("grädde", "gradde", "matlagningsgrädde", "matlagningsgradde"),
    "crème fraiche": (
        "crème fraiche",
        "creme fraiche",
        "crème fraîche",
        "lätt crème fraiche",
        "latt creme fraiche",
    ),
    "ost": ("ost", "riven ost", "hårdost", "hardost"),
    "smör": ("smör", "smor"),
    "krossade tomater": (
        "krossade tomater",
        "tomatkross",
        "krossad tomat",
    ),
    "kokosmjölk": ("kokosmjölk", "kokosmjolk"),
    "tortillas": ("tortilla", "tortillas", "tortillabröd", "tortillabrod"),
    "vitlök": ("vitlök", "vitlok", "vitlöksklyfta", "vitloksklyfta"),
    "majs": ("majs",),
    "oliver": ("oliv", "oliver", "olive", "olives"),
    "buljong": (
        "buljong",
        "kycklingbuljong",
        "kyckling buljong",
        "grönsaksbuljong",
        "gronsaksbuljong",
        "chicken broth",
        "vegetable broth",
        "chicken stock",
        "vegetable stock",
    ),
    "tomatpuré": ("tomatpuré", "tomatpure"),
}


def _search_text(value: str) -> str:
    """Return a comparison form without accents or punctuation."""

    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", unaccented).strip()


_ALIAS_TO_CANONICAL: dict[str, str] = {
    _search_text(alias): canonical
    for canonical, aliases in CANONICAL_ALIASES.items()
    for alias in (canonical, *aliases)
}
_SORTED_ALIASES = sorted(_ALIAS_TO_CANONICAL, key=lambda value: (-len(value), value))


def _presented_canonical_from_query(query: str) -> str:
    """Resolve one authoritative recipe alias into the matcher vocabulary."""

    cleaned = _search_text(query)
    return _ALIAS_TO_CANONICAL.get(cleaned) or re.sub(r"\s+", " ", query.casefold().strip())


# The collector owns the recipe-relevant product identity vocabulary, while
# the meal backend has a backwards-compatible Swedish matcher vocabulary.
# Keep the boundary explicit and derive it from the one authoritative recipe
# set instead of maintaining a second query dictionary in this service.
RECIPE_CANONICAL_TO_MATCHER_CANONICAL: dict[str, str] = {
    ingredient.canonical: _presented_canonical_from_query(ingredient.queries[0])
    for ingredient in RECIPE_RELEVANT_INGREDIENTS
}
_RECIPE_ID_TO_MATCHER_CANONICAL = {
    _search_text(source): matcher
    for source, matcher in RECIPE_CANONICAL_TO_MATCHER_CANONICAL.items()
}

_recipe_sources_by_exact_term: dict[str, list[str]] = {}
_recipe_ingredient_by_canonical = {
    ingredient.canonical: ingredient for ingredient in RECIPE_RELEVANT_INGREDIENTS
}
for _ingredient in RECIPE_RELEVANT_INGREDIENTS:
    for _term in (_ingredient.canonical, *_ingredient.queries):
        sources = _recipe_sources_by_exact_term.setdefault(_search_text(_term), [])
        if _ingredient.canonical not in sources:
            sources.append(_ingredient.canonical)
_RECIPE_SOURCES_BY_EXACT_TERM = {
    term: tuple(sources) for term, sources in _recipe_sources_by_exact_term.items()
}
_UNAMBIGUOUS_RECIPE_SOURCE_BY_EXACT_TERM = {
    term: sources[0] for term, sources in _RECIPE_SOURCES_BY_EXACT_TERM.items() if len(sources) == 1
}
_MAX_LITERAL_RECIPE_ALIASES = 6


def recipe_source_canonical_foods(name: str) -> tuple[str, ...]:
    """Return every structured recipe identity addressed by an exact term.

    Some deliberately shared discovery terms, currently ``röda linser``,
    address both a generic and a more specific collector identity. Returning
    that small authoritative set lets snapshot-backed providers query exact
    indexes without guessing one identity or using fuzzy text matching.
    """

    if not isinstance(name, str) or not name.strip():
        return ()
    return _RECIPE_SOURCES_BY_EXACT_TERM.get(_search_text(name), ())


def recipe_source_query_aliases(name: str) -> tuple[str, ...]:
    """Return a bounded set of exact public aliases for legacy snapshots.

    For one unambiguous recipe identity all of its curated aliases are safe.
    When a term addresses multiple identities, retain only aliases containing
    the same tokens (including reversed word order). This prevents a request
    for red lentils from broadening into the distinct ``gröna linser`` alias.
    """

    sources = recipe_source_canonical_foods(name)
    if not sources:
        return ()
    requested_tokens = sorted(_search_text(name).split())
    aliases: list[str] = []
    seen_aliases: set[str] = set()
    for source in sources:
        ingredient = _recipe_ingredient_by_canonical[source]
        for alias in ingredient.queries:
            normalized_alias = _search_text(alias)
            if len(sources) > 1 and sorted(normalized_alias.split()) != requested_tokens:
                continue
            if normalized_alias not in seen_aliases:
                aliases.append(alias)
                seen_aliases.add(normalized_alias)
    return tuple(aliases[:_MAX_LITERAL_RECIPE_ALIASES])


def recipe_source_canonical_food(name: str) -> str | None:
    """Return an exact recipe product identity for a canonical ID/query alias.

    Ambiguous aliases intentionally return ``None``.  Callers may use this to
    address a structured ``canonical_food`` index, but never as fuzzy product
    identity or as a replacement for the semantic matcher.
    """

    if not isinstance(name, str) or not name.strip():
        return None
    return _UNAMBIGUOUS_RECIPE_SOURCE_BY_EXACT_TERM.get(_search_text(name))


def canonicalize_ingredient_name(name: str) -> str:
    """Map a Swedish ingredient expression to a conservative canonical name."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Ingredient name must be a non-empty string")

    cleaned = _search_text(name)
    recipe_canonical = _RECIPE_ID_TO_MATCHER_CANONICAL.get(cleaned)
    if recipe_canonical:
        return recipe_canonical
    direct = _ALIAS_TO_CANONICAL.get(cleaned)
    if direct:
        return direct

    padded = f" {cleaned} "
    for alias in _SORTED_ALIASES:
        if f" {alias} " in padded:
            return _ALIAS_TO_CANONICAL[alias]

    # Unknown ingredients are still stable and matchable.  Keep Swedish
    # letters in the presented canonical name while normalising whitespace.
    return re.sub(r"\s+", " ", name.casefold().strip())


_UNIT_CONVERSIONS: dict[str, tuple[str, Decimal]] = {
    "g": ("g", Decimal(1)),
    "gram": ("g", Decimal(1)),
    "kg": ("g", Decimal(1000)),
    "kilogram": ("g", Decimal(1000)),
    "ml": ("ml", Decimal(1)),
    "milliliter": ("ml", Decimal(1)),
    "l": ("ml", Decimal(1000)),
    "liter": ("ml", Decimal(1000)),
    "dl": ("ml", Decimal(100)),
    "deciliter": ("ml", Decimal(100)),
    "cl": ("ml", Decimal(10)),
    "centiliter": ("ml", Decimal(10)),
    "msk": ("ml", Decimal(15)),
    "matsked": ("ml", Decimal(15)),
    "tsk": ("ml", Decimal(5)),
    "tesked": ("ml", Decimal(5)),
    "krm": ("ml", Decimal(1)),
    "kryddmatt": ("ml", Decimal(1)),
    "st": ("st", Decimal(1)),
    "stuck": ("st", Decimal(1)),
    "styck": ("st", Decimal(1)),
    "pcs": ("st", Decimal(1)),
    "pc": ("st", Decimal(1)),
}


def normalize_quantity(quantity: float, unit: str) -> tuple[float, str]:
    """Convert a quantity to grams, millilitres or pieces.

    Decimal is used for the multiplication so common decimal recipe amounts do
    not gain binary floating point noise.
    """

    if not isinstance(unit, str):
        raise TypeError("Unit must be a string")
    try:
        numeric = Decimal(str(quantity))
    except Exception as exc:  # Decimal raises several input-specific errors
        raise ValueError("Quantity must be numeric") from exc
    if not numeric.is_finite() or numeric <= 0:
        raise ValueError("Quantity must be a finite number greater than zero")

    unit_key = _search_text(unit.rstrip("."))
    conversion = _UNIT_CONVERSIONS.get(unit_key)
    if conversion is None:
        raise ValueError(f"Unsupported ingredient unit: {unit}")
    base_unit, factor = conversion
    converted = numeric * factor
    return float(converted), base_unit


class IngredientNormalizer:
    """Aggregate ingredients across recipes without making price assumptions."""

    @staticmethod
    def normalize_quantity(quantity: float, unit: str) -> tuple[float, str]:
        return normalize_quantity(quantity, unit)

    @staticmethod
    def canonicalize_name(name: str) -> str:
        return canonicalize_ingredient_name(name)

    def normalize_and_aggregate(self, recipes: Iterable[Recipe]) -> list[NormalizedIngredient]:
        # The base unit is part of the key.  Converting pieces to grams would
        # require an invented average weight, so dimensionally different recipe
        # declarations are deliberately kept separate.
        aggregated: OrderedDict[tuple[str, str], dict[str, object]] = OrderedDict()
        for recipe in recipes:
            for ingredient in recipe.ingredients:
                canonical = canonicalize_ingredient_name(
                    ingredient.canonical_name or ingredient.name
                )
                quantity, base_unit = normalize_quantity(ingredient.quantity, ingredient.unit)
                key = (canonical, base_unit)
                if key not in aggregated:
                    aggregated[key] = {
                        "canonical_name": canonical,
                        "required_quantity": Decimal(0),
                        "unit": base_unit,
                        "display_name": ingredient.name,
                        "source_recipes": [],
                    }
                row = aggregated[key]
                row["required_quantity"] = row["required_quantity"] + Decimal(str(quantity))
                sources = row["source_recipes"]
                if recipe.name not in sources:
                    sources.append(recipe.name)

        return [
            NormalizedIngredient(
                canonical_name=str(row["canonical_name"]),
                required_quantity=float(row["required_quantity"]),
                unit=str(row["unit"]),
                display_name=str(row["display_name"]),
                source_recipes=list(row["source_recipes"]),
            )
            for row in aggregated.values()
        ]


def normalize_and_aggregate(recipes: Iterable[Recipe]) -> list[NormalizedIngredient]:
    """Functional wrapper useful from small scripts and tests."""

    return IngredientNormalizer().normalize_and_aggregate(recipes)


__all__ = [
    "CANONICAL_ALIASES",
    "IngredientNormalizer",
    "canonicalize_ingredient_name",
    "normalize_and_aggregate",
    "normalize_quantity",
    "recipe_source_canonical_food",
    "recipe_source_canonical_foods",
    "recipe_source_query_aliases",
]
