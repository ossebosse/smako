"""Meal-oriented canonical ingredient taxonomy.

The existing normalizer remains the source of truth for canonical names and
aliases.  This module adds only the information needed to decide whether an
ingredient is useful in a weekday dinner and how it should be searched for.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.models.product import CanonicalUnit
from app.services.ingredient_normalizer import (
    CANONICAL_ALIASES,
    canonicalize_ingredient_name,
)


class IngredientCategory(StrEnum):
    """Structural meal roles used by candidate validation and pool quotas."""

    PROTEIN = "protein"
    CARBOHYDRATE = "carbohydrate"
    VEGETABLE = "vegetable"
    LEGUME = "legume"
    DAIRY = "dairy"
    SAUCE_BASE = "sauce_base"
    FLAVOUR_SUPPORT = "flavour_support"


@dataclass(frozen=True, slots=True)
class IngredientTaxonomyEntry:
    """Search and meal-utility metadata for one canonical ingredient."""

    canonical: str
    display_name: str
    category: IngredientCategory
    search_query: str
    expected_unit: CanonicalUnit
    typical_meal_quantity: float
    utility_weight: float = 1.0
    identity_terms: tuple[str, ...] = ()
    exclusion_terms: tuple[str, ...] = ()

    @property
    def aliases(self) -> tuple[str, ...]:
        """Expose aliases from the existing canonical system, without copying it."""

        return CANONICAL_ALIASES.get(self.canonical, (self.canonical,))


def _entry(
    canonical: str,
    category: IngredientCategory,
    *,
    query: str | None = None,
    unit: CanonicalUnit = "g",
    typical: float = 400,
    utility: float = 1.0,
    identity: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
    display_name: str | None = None,
) -> IngredientTaxonomyEntry:
    return IngredientTaxonomyEntry(
        canonical=canonical,
        display_name=display_name or canonical,
        category=category,
        search_query=query or canonical,
        expected_unit=unit,
        typical_meal_quantity=typical,
        utility_weight=utility,
        identity_terms=identity,
        exclusion_terms=exclude,
    )


# Forty-two deliberately meal-relevant searches keep one live pool build below
# the Primat free-tier request budget while covering the requested food groups.
INGREDIENT_TAXONOMY: tuple[IngredientTaxonomyEntry, ...] = (
    # Protein
    _entry(
        "kyckling",
        IngredientCategory.PROTEIN,
        typical=600,
        utility=1.20,
        identity=("kyckling",),
        exclude=(
            "nuggets",
            "pålägg",
            "palagg",
            "hjärta",
            "hjarta",
            "lever",
            "mage",
            "magar",
            "krås",
            "kras",
            "inälvor",
            "inalvor",
            "organmix",
            "organ mix",
            "fötter",
            "fotter",
            "skinn",
            "buljong",
            "fond",
            "soppa",
            "lasagne",
        ),
    ),
    _entry(
        "fläskkött",
        IngredientCategory.PROTEIN,
        query="fläsk",
        typical=600,
        utility=1.15,
        identity=("fläsk", "flask"),
        exclude=("pålägg", "palagg"),
    ),
    _entry(
        "falukorv", IngredientCategory.PROTEIN, typical=500, utility=1.15, identity=("falukorv",)
    ),
    _entry(
        "korv",
        IngredientCategory.PROTEIN,
        typical=500,
        utility=1.05,
        identity=("korv",),
        exclude=("korvbröd", "korvbrod", "korv bröd"),
    ),
    _entry(
        "nötfärs",
        IngredientCategory.PROTEIN,
        typical=500,
        utility=1.15,
        identity=("nötfärs", "notfars"),
    ),
    _entry(
        "blandfärs",
        IngredientCategory.PROTEIN,
        typical=500,
        utility=1.10,
        identity=("blandfärs", "blandfars"),
    ),
    _entry(
        "fisk",
        IngredientCategory.PROTEIN,
        typical=500,
        utility=1.10,
        identity=("fisk", "torsk", "sej", "kolja"),
        exclude=("fiskpinnar", "fiskbullar", "soppa"),
    ),
    _entry(
        "lax",
        IngredientCategory.PROTEIN,
        typical=500,
        utility=1.05,
        identity=("lax",),
        exclude=("pålägg", "palagg", "rökt", "rokt"),
    ),
    _entry(
        "ägg",
        IngredientCategory.PROTEIN,
        unit="st",
        typical=8,
        utility=1.20,
        identity=("ägg", "agg"),
    ),
    _entry("tofu", IngredientCategory.PROTEIN, typical=400, utility=1.05, identity=("tofu",)),
    # Carbohydrates
    _entry(
        "potatis",
        IngredientCategory.CARBOHYDRATE,
        typical=1200,
        utility=1.25,
        identity=("potatis",),
        exclude=("gratäng", "gratang", "sallad", "chips"),
    ),
    _entry(
        "ris",
        IngredientCategory.CARBOHYDRATE,
        typical=320,
        utility=1.20,
        identity=("ris",),
        exclude=(
            "grötris",
            "grot ris",
            "risgryn",
            "risgröt",
            "risgrot",
            "riskaka",
            "risdryck",
            "rismjöl",
            "rismjol",
            "blomkålsris",
        ),
    ),
    _entry(
        "pasta",
        IngredientCategory.CARBOHYDRATE,
        typical=400,
        utility=1.20,
        identity=("pasta", "spaghetti", "spagetti", "makaron", "penne", "fusilli"),
        exclude=("pastasås", "pastasas", "sallad"),
    ),
    _entry(
        "nudlar",
        IngredientCategory.CARBOHYDRATE,
        typical=350,
        utility=1.10,
        identity=("nudel", "nudlar"),
        exclude=("färdigrätt", "fardigratt"),
    ),
    _entry(
        "couscous",
        IngredientCategory.CARBOHYDRATE,
        typical=350,
        utility=1.05,
        identity=("couscous",),
    ),
    _entry(
        "bröd",
        IngredientCategory.CARBOHYDRATE,
        typical=400,
        utility=0.80,
        identity=("bröd", "brod"),
        exclude=("ströbröd", "strodrod", "krutong"),
    ),
    _entry(
        "tortillas",
        IngredientCategory.CARBOHYDRATE,
        unit="st",
        typical=8,
        utility=0.95,
        identity=("tortilla",),
        exclude=("chips",),
    ),
    # Vegetables
    _entry(
        "gul lök",
        IngredientCategory.VEGETABLE,
        query="gul lök",
        typical=300,
        utility=1.20,
        # Primat catalogues use both adjective–noun and noun–adjective order.
        identity=("gul lök", "gul lok", "lök gul", "lok gul", "matlök", "matlok"),
    ),
    _entry(
        "rödlök",
        IngredientCategory.VEGETABLE,
        typical=250,
        utility=0.90,
        identity=("rödlök", "rodlok", "röd lök", "rod lok"),
    ),
    _entry(
        "morot",
        IngredientCategory.VEGETABLE,
        typical=500,
        utility=1.20,
        identity=("morot", "morötter", "morotter"),
    ),
    _entry(
        "tomat",
        IngredientCategory.VEGETABLE,
        typical=400,
        utility=1.00,
        identity=("tomat",),
        exclude=("krossad", "tomatpuré", "tomatpure", "ketchup", "sås", "sas"),
    ),
    _entry(
        "paprika",
        IngredientCategory.VEGETABLE,
        typical=300,
        utility=0.90,
        identity=("paprika",),
        exclude=("pulver", "krydda"),
    ),
    _entry(
        "broccoli",
        IngredientCategory.VEGETABLE,
        typical=400,
        utility=1.10,
        identity=("broccoli",),
        exclude=("gratäng", "gratang", "soppa"),
    ),
    _entry(
        "vitkål",
        IngredientCategory.VEGETABLE,
        typical=500,
        utility=1.20,
        identity=("vitkål", "vitkal"),
        exclude=("sallad",),
    ),
    _entry(
        "ärtor",
        IngredientCategory.VEGETABLE,
        typical=400,
        utility=0.95,
        identity=("ärtor", "artor", "ärter", "arter"),
        exclude=("gula ärter", "gula arter", "soppa"),
    ),
    _entry(
        "frysta grönsaker",
        IngredientCategory.VEGETABLE,
        typical=500,
        utility=1.20,
        identity=(
            "grönsaksblandning",
            "gronsaksblandning",
            "grönsaksmix",
            "gronsaksmix",
            "wokmix",
            "wok mix",
            "wokgrönsaker",
            "wokgronsaker",
        ),
    ),
    _entry(
        "majs",
        IngredientCategory.VEGETABLE,
        typical=300,
        utility=0.90,
        identity=("majs", "majskorn", "sockermajs"),
        exclude=("chips", "mjöl", "mjol"),
    ),
    # Legumes
    _entry(
        "linser",
        IngredientCategory.LEGUME,
        typical=300,
        utility=1.30,
        identity=("lins", "linser"),
        exclude=("linssoppa", "linsgryta", "linschips"),
    ),
    _entry(
        "kidneybönor",
        IngredientCategory.LEGUME,
        typical=500,
        utility=1.25,
        identity=("kidneybönor", "kidneybonor", "kidney beans"),
    ),
    _entry(
        "svarta bönor",
        IngredientCategory.LEGUME,
        typical=500,
        utility=1.25,
        identity=("svarta bönor", "svarta bonor", "black beans"),
    ),
    _entry(
        "kikärtor",
        IngredientCategory.LEGUME,
        typical=500,
        utility=1.25,
        identity=("kikärtor", "kikartor", "chickpeas"),
    ),
    _entry(
        "bönor",
        IngredientCategory.LEGUME,
        query="vita bönor",
        typical=500,
        utility=1.15,
        identity=("vita bönor", "vita bonor"),
        exclude=("gröna bönor", "grona bonor", "haricots verts"),
    ),
    # Dairy
    _entry(
        "mjölk",
        IngredientCategory.DAIRY,
        unit="ml",
        typical=500,
        utility=0.90,
        identity=("mjölk", "mjolk"),
        exclude=("kokosmjölk", "kokosmjolk", "havredryck", "pulver"),
    ),
    _entry(
        "grädde",
        IngredientCategory.DAIRY,
        unit="ml",
        typical=300,
        utility=0.85,
        identity=("grädde", "gradde"),
        exclude=("crème fraiche", "creme fraiche", "gräddfil", "gradfil"),
    ),
    _entry(
        "crème fraiche",
        IngredientCategory.DAIRY,
        unit="ml",
        typical=250,
        utility=0.90,
        identity=("crème fraiche", "creme fraiche"),
        exclude=("potatissallad", "pastasallad", "dressing", "dipmix", "dippmix"),
    ),
    _entry(
        "ost",
        IngredientCategory.DAIRY,
        typical=200,
        utility=0.85,
        identity=("ost", "cheddar", "gouda", "mozzarella"),
        exclude=(
            "grillost",
            "halloumi",
            "fetaost",
            "salladsost",
            "färskost",
            "farskost",
            "mjukost",
            "ostsås",
            "ostsas",
            "chips",
            "gratäng",
        ),
    ),
    # Sauce bases
    _entry(
        "krossade tomater",
        IngredientCategory.SAUCE_BASE,
        typical=600,
        utility=1.20,
        identity=("krossade tomater", "krossad tomat", "tomatkross"),
    ),
    _entry(
        "kokosmjölk",
        IngredientCategory.SAUCE_BASE,
        unit="ml",
        typical=400,
        utility=1.00,
        identity=("kokosmjölk", "kokosmjolk"),
    ),
    _entry(
        "tomatpuré",
        IngredientCategory.SAUCE_BASE,
        typical=100,
        utility=0.80,
        identity=("tomatpuré", "tomatpure"),
    ),
    # Flavour/support products are deliberately lower utility so they cannot
    # crowd substantial dinner ingredients out solely through a low unit price.
    _entry(
        "vitlök",
        IngredientCategory.FLAVOUR_SUPPORT,
        typical=30,
        utility=0.65,
        identity=("vitlök", "vitlok"),
        exclude=(
            "sås",
            "sas",
            "pulver",
            "krossade tomater",
            "krossad tomat",
            "tomatkross",
            "marinad",
            "dressing",
            "baguette",
            "baguetter",
            "bröd",
            "brod",
            "kosttillskott",
            "tablett",
            "tabletter",
            "vitlökskapslar",
            "vitlokskapslar",
            "örter",
            "orter",
            "aioli",
            "kryddsmör",
            "kryddsmor",
        ),
    ),
    _entry(
        "sojasås",
        IngredientCategory.FLAVOUR_SUPPORT,
        query="soja",
        unit="ml",
        typical=60,
        utility=0.65,
        identity=("soja",),
        exclude=("dryck", "färs", "fars"),
    ),
    _entry(
        "buljong",
        IngredientCategory.FLAVOUR_SUPPORT,
        typical=40,
        utility=0.60,
        identity=("buljong",),
        exclude=("soppa", "fond"),
    ),
)


TAXONOMY_BY_CANONICAL: dict[str, IngredientTaxonomyEntry] = {
    entry.canonical: entry for entry in INGREDIENT_TAXONOMY
}


def get_taxonomy_entry(name: str) -> IngredientTaxonomyEntry | None:
    """Find taxonomy metadata through the project's existing alias resolver."""

    return TAXONOMY_BY_CANONICAL.get(canonicalize_ingredient_name(name))


def ingredients_in_category(
    category: IngredientCategory | str,
) -> tuple[IngredientTaxonomyEntry, ...]:
    """Return the stable configured order for one structural meal role."""

    resolved = IngredientCategory(category)
    return tuple(entry for entry in INGREDIENT_TAXONOMY if entry.category == resolved)


__all__ = [
    "INGREDIENT_TAXONOMY",
    "TAXONOMY_BY_CANONICAL",
    "IngredientCategory",
    "IngredientTaxonomyEntry",
    "get_taxonomy_entry",
    "ingredients_in_category",
]
