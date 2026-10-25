"""Central semantic interpretation for recipe ingredients and grocery products.

Catalogue search metadata is not product identity.  In particular, Primat may
return a neighbouring product tagged with the original search term.  This
module therefore interprets the visible product name before considering
provider-supplied canonical metadata and keeps semantic compatibility separate
from lexical similarity and price.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.models.product import SemanticConfidence
from app.services.ingredient_normalizer import (
    CANONICAL_ALIASES,
    _search_text,
    canonicalize_ingredient_name,
)
from pydantic import BaseModel, ConfigDict, Field


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {_search_text(phrase)} " in f" {text} "


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


@dataclass(frozen=True, slots=True)
class IngredientSemanticRule:
    """Semantic constraints for one externally visible canonical ingredient."""

    canonical_food: str
    food_family: str | None
    identity_terms: tuple[str, ...]
    allowed_roles: frozenset[str] = frozenset()
    excluded_roles: frozenset[str] = frozenset()
    excluded_forms: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class PrimaryProductIdentityRule:
    """A purchasable product class which dominates flavour/component words.

    Grocery names do not consistently include words such as ``med`` or
    ``smak av``.  A product-class noun such as ``koppnudlar``, ``bratwurst``
    or ``crème fraiche`` is therefore stronger identity evidence than a raw
    ingredient appearing elsewhere in the same name.  These are positive
    identities, not target-specific blacklists: the same classification is
    reused no matter which recipe ingredient initiated the catalogue search.
    """

    canonical_food: str
    food_family: str | None
    product_role: str
    product_form: str
    name_terms: tuple[str, ...]
    category_terms: tuple[str, ...] = ()


class SemanticRequirement(BaseModel):
    """Resolved food/role requirement behind a normalized recipe ingredient."""

    model_config = ConfigDict(frozen=True)

    canonical_name: str = Field(min_length=1)
    canonical_food: str = Field(min_length=1)
    food_family: str | None = None
    allowed_roles: frozenset[str] = frozenset()
    excluded_roles: frozenset[str] = frozenset()
    excluded_forms: frozenset[str] = frozenset()


class SemanticMatchResult(BaseModel):
    """Auditable semantic gate result, independent of price and quantity."""

    model_config = ConfigDict(frozen=True)

    compatible: bool
    canonical_food: str | None = None
    food_family: str | None = None
    product_role: str | None = None
    product_form: str | None = None
    confidence: SemanticConfidence
    evidence: list[str] = Field(default_factory=list)


# These textual exclusions are a final safety net.  The primary decision is
# food identity + role + form below; strings are intentionally centralised here
# rather than spread between the provider, matcher and optimizer.
STRICT_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    "smör": (
        "bregott",
        "margarin",
        "lätt & lagom",
        "latt lagom",
        "milda",
        "bredbart",
        "matfettsblandning",
    ),
    "nötfärs": ("blandfärs", "fläskfärs", "kycklingfärs", "vegofärs"),
    "blandfärs": ("nötfärs", "fläskfärs", "kycklingfärs", "vegofärs"),
    "köttfärs": (
        "köttfärssås",
        "köttfärs sås",
        "köttfärspaj",
        "köttfärs paj",
        "köttfärslasagne",
        "köttfärs lasagne",
    ),
    "mjölk": ("kokosmjölk", "havredryck", "sojadryck", "mandeldryck"),
    "grädde": ("crème fraiche", "creme fraiche", "gräddfil", "gradfil"),
    "linser": (
        "kikärtor",
        "kikartor",
        "gula ärter",
        "gula arter",
        "linssoppa",
        "linsgryta",
        "linschips",
    ),
    "ärtor": ("gula ärter", "gula arter", "gul ärta", "gul arta"),
    "selleri": ("rotselleri", "celeriac"),
    "ris": (
        "grötris",
        "gröt-ris",
        "risgryn",
        "ris gryn",
        "risgröt",
        "ris pudding",
        "pudding rice",
        "riskakor",
        "risdryck",
        "rismjöl",
        "blomkålsris",
        "risnudlar",
    ),
    "crème fraiche": (
        "potatissallad",
        "pastasallad",
        "dressing",
        "dipmix",
        "dippmix",
        "chips",
        "sås",
    ),
    "tortillas": ("chips",),
    "vitlök": (
        "krossade tomater",
        "krossad tomat",
        "tomatkross",
        "marinad",
        "dressing",
        "baguette",
        "baguetter",
        "vitlöksbaguette",
        "vitlöksbaguetter",
        "vitlöksbröd",
        "bröd",
        "aioli",
        "kryddsmör",
        "kosttillskott",
        "tablett",
        "tabletter",
        "vitlökskapslar",
        "örter",
        "orter",
    ),
    "ost": (
        "vegansk ost",
        "ostbågar",
        "grillost",
        "grill ost",
        "grill cheese",
        "grilling cheese",
        "halloumi",
        "fetaost",
        "salladsost",
        "chèvre",
        "getost",
        "färskost",
        "mjukost",
        "smältost",
        "dessertost",
        "mögelost",
        "ostsås",
        "ost sås",
        "ostpaj",
        "ostkaka",
        "potatisgratäng",
        "dressing",
        "chips",
    ),
    "kyckling": (
        "kycklinghjärta",
        "kyckling hjärta",
        "kycklinglever",
        "kyckling lever",
        "kycklingmage",
        "kyckling mage",
        "kycklingkrås",
        "kyckling krås",
        "kycklinginälvor",
        "kyckling inälvor",
        "chicken offal",
        "kycklingfötter",
        "kyckling fötter",
        "kycklingskinn",
        "kyckling skinn",
        "kycklingbuljong",
        "kyckling buljong",
        "kycklingfond",
        "kyckling fond",
        "kycklingsoppa",
        "kyckling soppa",
        "kycklinglasagne",
        "kycklingnuggets",
        "kycklingkorv",
        "kyckling korv",
        "kycklingkebab",
        "kyckling kebab",
        "kycklingburgare",
        "kyckling burgare",
        "kycklingfärs",
        "kyckling färs",
    ),
    "paprika": ("paprikapulver", "paprikachips", "paprikasås", "färdigrätt"),
    "fisk": (
        "fiskpinnar",
        "fiskgratäng",
        "fisksoppa",
        "fiskbuljong",
        "fiskbullar",
        "fisk bullar",
        "fiskburgare",
        "fisk burgare",
        "fiskkakor",
        "fisk kakor",
        "fish cakes",
        "fish burger",
    ),
    "fläskkött": ("fläskfärs", "fläsksås", "färdigrätt"),
}


def _raw_produce_rule(
    *,
    canonical_food: str,
    food_family: str,
    identity_terms: tuple[str, ...],
    product_role: str = "whole_vegetable",
) -> IngredientSemanticRule:
    """Declare that an unqualified recipe canonical means raw whole produce.

    The declaration, rather than a separate hand-maintained name allowlist,
    drives both the default role and the preserved-category rejection gate.
    Canonicals which intentionally represent preserved foods use their own
    rules and are therefore not swept into the raw-produce policy.
    """

    return IngredientSemanticRule(
        canonical_food=canonical_food,
        food_family=food_family,
        identity_terms=identity_terms,
        allowed_roles=frozenset({product_role}),
        excluded_roles=frozenset(
            {
                "pickled_vegetable_mixture",
                "preserved_in_oil",
                "preserved_product",
                "processed_ready_meal",
            }
        ),
        excluded_forms=frozenset({"canned", "pickled", "preserved"}),
    )


_RULES: dict[str, IngredientSemanticRule] = {
    # Keep the public canonical name ``kyckling`` for backwards compatibility,
    # while its semantic requirement is specifically ordinary chicken meat.
    "kyckling": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=("kyckling", "chicken"),
        allowed_roles=frozenset(
            {"generic_meat", "breast", "thigh", "drumstick", "wing", "whole_meat"}
        ),
        # Generic recipe grams are edible meat. Bone-in package mass has no
        # verified edible yield; exact requested wings remain a whole-product buy.
        excluded_forms=frozenset({'bone_in'}),
        excluded_roles=frozenset(
            {
                "heart",
                "liver",
                "gizzard",
                "organ_mix",
                "feet",
                "skin_only",
                "broth",
                "minced_meat",
                "processed_sausage",
                "processed_kebab",
                "processed_stick",
                "processed_burger",
                "processed_ready_meal",
            }
        ),
    ),
    "kycklinghjärta": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=("kycklinghjärta", "kycklinghjartan", "chicken heart"),
        allowed_roles=frozenset({"heart"}),
    ),
    "kycklinglever": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=("kycklinglever", "chicken liver"),
        allowed_roles=frozenset({"liver"}),
    ),
    "kycklingmage": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=("kycklingmage", "kycklingmagar", "chicken gizzard"),
        allowed_roles=frozenset({"gizzard"}),
    ),
    "kycklingkrås": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=("kycklingkrås", "kycklingkras", "kyckling krås"),
        allowed_roles=frozenset({"gizzard"}),
    ),
    "kycklinginälvor": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=("kycklinginälvor", "kycklinginalvor", "chicken offal"),
        allowed_roles=frozenset({"organ_mix"}),
    ),
    "chicken_breast": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=(
            "kycklingfilé",
            "kycklingfile",
            "kycklingbröst",
            "bröstfilé",
            "chicken breast",
        ),
        allowed_roles=frozenset({"breast"}),
        excluded_roles=frozenset(
            {
                "generic_meat",
                "thigh",
                "drumstick",
                "wing",
                "whole_meat",
                "heart",
                "liver",
                "gizzard",
                "feet",
                "skin_only",
                "broth",
                "minced_meat",
                "processed_sausage",
                "processed_kebab",
                "processed_stick",
                "processed_burger",
                "processed_ready_meal",
            }
        ),
    ),
    "kycklinggyros": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=("kycklinggyros", "kyckling gyros", "chicken gyros"),
        allowed_roles=frozenset({"processed_kebab"}),
    ),
    "kycklingpinnar": IngredientSemanticRule(
        canonical_food="chicken",
        food_family="poultry",
        identity_terms=(
            "kycklingpinnar",
            "kyckling pinnar",
            "chicken sticks",
            "chicken fingers",
        ),
        allowed_roles=frozenset({"processed_stick"}),
    ),
    "köttfärs": IngredientSemanticRule(
        canonical_food="meat_mince",
        food_family="meat",
        identity_terms=("köttfärs", "nötfärs", "blandfärs"),
        allowed_roles=frozenset({"generic_meat_mince", "beef_mince", "mixed_mince"}),
        excluded_roles=frozenset(
            {"pork_mince", "chicken_mince", "plant_mince", "processed_ready_meal"}
        ),
    ),
    "nötfärs": IngredientSemanticRule(
        canonical_food="meat_mince",
        food_family="meat",
        identity_terms=("nötfärs",),
        allowed_roles=frozenset({"beef_mince"}),
    ),
    "blandfärs": IngredientSemanticRule(
        canonical_food="meat_mince",
        food_family="meat",
        identity_terms=("blandfärs",),
        allowed_roles=frozenset({"mixed_mince"}),
    ),
    "potatis": _raw_produce_rule(
        canonical_food="potato",
        food_family="vegetable",
        identity_terms=("potatis", "potatisar", "potato", "potatoes"),
    ),
    "gul lök": _raw_produce_rule(
        canonical_food="yellow_onion",
        food_family="allium",
        identity_terms=("gul lök", "gul lok", "lök gul", "lok gul", "matlök", "matlok"),
    ),
    "rödlök": _raw_produce_rule(
        canonical_food="red_onion",
        food_family="allium",
        identity_terms=("rödlök", "rodlok", "röd lök", "rod lok", "lök röd", "lok rod", "red onion"),
    ),
    "morot": _raw_produce_rule(
        canonical_food="carrot",
        food_family="vegetable",
        identity_terms=("morot", "morötter", "morotter", "carrot", "carrots"),
    ),
    "tomat": _raw_produce_rule(
        canonical_food="tomato",
        food_family="vegetable",
        identity_terms=("tomat", "tomater", "tomato", "tomatoes"),
    ),
    "broccoli": _raw_produce_rule(
        canonical_food="broccoli",
        food_family="vegetable",
        identity_terms=("broccoli",),
    ),
    "aubergine": _raw_produce_rule(
        canonical_food="aubergine",
        food_family="vegetable",
        identity_terms=("aubergine", "auberginer"),
    ),
    "zucchini": _raw_produce_rule(
        canonical_food="zucchini",
        food_family="vegetable",
        identity_terms=("zucchini", "squash"),
    ),
    "pepparrot": _raw_produce_rule(
        canonical_food="horseradish", food_family="vegetable", identity_terms=("pepparrot",),
    ),
    "rödbeta": _raw_produce_rule(
        canonical_food="beetroot", food_family="vegetable", identity_terms=("rödbeta", "rödbetor"),
    ),
    "sötpotatis": _raw_produce_rule(
        canonical_food="sweet_potato", food_family="vegetable", identity_terms=("sötpotatis",),
    ),
    "purjolök": _raw_produce_rule(
        canonical_food="leek",
        food_family="allium",
        identity_terms=("purjolök", "purjolok", "leek"),
    ),
    "ärtor": _raw_produce_rule(
        canonical_food="peas",
        food_family="legume",
        identity_terms=("gröna ärtor", "grön ärta", "ärtor", "ärter", "green peas"),
    ),
    "selleri": _raw_produce_rule(
        canonical_food="celery",
        food_family="vegetable",
        identity_terms=("selleri", "bladselleri", "blekselleri", "stjälkselleri", "celery"),
        product_role="stalk_vegetable",
    ),
    "vitkål": _raw_produce_rule(
        canonical_food="white_cabbage",
        food_family="vegetable",
        identity_terms=("vitkål", "vitkal", "white cabbage"),
    ),
    "gurka": _raw_produce_rule(
        canonical_food="cucumber",
        food_family="vegetable",
        identity_terms=("gurka", "gurkor", "cucumber", "cucumbers"),
    ),
    "champinjoner": _raw_produce_rule(
        canonical_food="mushroom",
        food_family="fungus",
        identity_terms=("champinjon", "champinjoner", "mushroom", "mushrooms"),
        product_role="whole_mushroom",
    ),
    "ris": IngredientSemanticRule(
        canonical_food="rice",
        food_family="grain",
        identity_terms=("ris", "basmatiris", "jasminris", "matris"),
        allowed_roles=frozenset({"cooking_staple"}),
        excluded_roles=frozenset(
            {
                "pudding_rice",
                "rice_noodle",
                "rice_flour",
                "rice_drink",
                "snack",
                "processed_ready_meal",
            }
        ),
    ),
    "havreris": IngredientSemanticRule(
        canonical_food="oat",
        food_family="grain",
        identity_terms=("havreris", "havre ris", "oat rice"),
        allowed_roles=frozenset({"cooking_staple"}),
    ),
    "kornris": IngredientSemanticRule(
        canonical_food="barley",
        food_family="grain",
        identity_terms=("kornris", "korn ris", "barley rice"),
        allowed_roles=frozenset({"cooking_staple"}),
    ),
    "vitlök": IngredientSemanticRule(
        canonical_food="garlic",
        food_family="allium",
        identity_terms=("vitlök", "vitlöksklyfta", "garlic"),
        allowed_roles=frozenset({"bulb", "clove"}),
        excluded_roles=frozenset({"bread", "sauce", "seasoning", "spread", "processed_ready_meal"}),
    ),
    "ost": IngredientSemanticRule(
        canonical_food="cheese",
        food_family="dairy",
        identity_terms=("ost", "cheddar", "gouda", "mozzarella", "parmesan"),
        allowed_roles=frozenset(
            {"standard_cheese", "hard_cheese", "cheddar", "gouda", "mozzarella", "parmesan"}
        ),
        excluded_roles=frozenset(
            {
                "grilling_cheese",
                "salad_cheese",
                "cream_cheese",
                "cheese_sauce",
                "cheese_flavoured_snack",
                "processed_ready_meal",
            }
        ),
    ),
    "mesost": IngredientSemanticRule(
        canonical_food="whey_cheese",
        food_family="dairy",
        identity_terms=("mesost", "brunost", "whey cheese", "brown cheese"),
        allowed_roles=frozenset({"whey_cheese"}),
    ),
    "crème fraiche": IngredientSemanticRule(
        canonical_food="creme_fraiche",
        food_family="dairy",
        identity_terms=("crème fraiche", "creme fraiche"),
        allowed_roles=frozenset({"dairy_base"}),
        excluded_roles=frozenset({"salad", "dressing", "dip_mix", "processed_ready_meal"}),
    ),
    "mjölk": IngredientSemanticRule(
        canonical_food="milk",
        food_family="dairy",
        identity_terms=("mjölk", "milk"),
    ),
    "grädde": IngredientSemanticRule(
        canonical_food="cream",
        food_family="dairy",
        identity_terms=("grädde", "cream"),
    ),
    "ägg": IngredientSemanticRule(
        canonical_food="eggs",
        food_family="egg",
        identity_terms=("ägg", "hönsägg", "egg", "eggs"),
    ),
    "linser": IngredientSemanticRule(
        canonical_food="lentil",
        food_family="legume",
        identity_terms=("lins", "linser", "lentil"),
        allowed_roles=frozenset({"dry_staple"}),
        excluded_roles=frozenset({"soup", "snack", "processed_ready_meal"}),
    ),
    "kikärtor": IngredientSemanticRule(
        canonical_food="chickpeas",
        food_family="legume",
        identity_terms=("kikärta", "kikärtor", "kikärter", "chickpea", "chickpeas"),
        allowed_roles=frozenset({"dry_staple", "cooked_staple", "canned_staple"}),
        excluded_roles=frozenset({"snack", "processed_ready_meal"}),
    ),
    "bönor": IngredientSemanticRule(
        canonical_food="white_bean",
        food_family="legume",
        identity_terms=("bönor", "vita bönor", "white beans"),
        allowed_roles=frozenset({"plain_bean", "dry_bean", "canned_bean"}),
    ),
    "kidneybönor": IngredientSemanticRule(
        canonical_food="kidney_bean",
        food_family="legume",
        identity_terms=("kidneybönor", "kidney beans"),
        allowed_roles=frozenset({"plain_bean", "dry_bean", "canned_bean"}),
    ),
    "svarta bönor": IngredientSemanticRule(
        canonical_food="black_bean",
        food_family="legume",
        identity_terms=("svarta bönor", "black beans"),
        allowed_roles=frozenset({"plain_bean", "dry_bean", "canned_bean"}),
    ),
    "torra linser": IngredientSemanticRule(
        canonical_food="lentil",
        food_family="legume",
        identity_terms=("torra linser", "torkade linser", "okokta linser", "dry lentils"),
        allowed_roles=frozenset({"dry_staple"}),
    ),
    "kokta linser": IngredientSemanticRule(
        canonical_food="lentil",
        food_family="legume",
        identity_terms=(
            "kokta linser",
            "färdigkokta linser",
            "linser på burk",
            "cooked lentils",
            "canned lentils",
        ),
        allowed_roles=frozenset({"cooked_staple", "canned_staple"}),
    ),
    "paprika": IngredientSemanticRule(
        canonical_food="pepper",
        food_family="vegetable",
        identity_terms=("paprika", "spetspaprika", "bell pepper"),
        allowed_roles=frozenset({"whole_vegetable", "mixed_whole_vegetable"}),
        excluded_roles=frozenset({"seasoning", "snack", "sauce", "processed_ready_meal"}),
    ),
    "fisk": IngredientSemanticRule(
        canonical_food="fish_meat",
        food_family="fish",
        identity_terms=("fisk", "fiskfilé", "torsk", "sej", "kolja", "lax"),
        allowed_roles=frozenset({"generic_fish", "white_fish", "salmon", "tuna_meat"}),
        excluded_roles=frozenset(
            {
                "breaded_ready_food",
                "broth",
                "canned_tuna",
                "fish_balls",
                "fish_burger",
                "fish_cakes",
                "processed_ready_meal",
            }
        ),
    ),
    "tonfisk": IngredientSemanticRule(
        canonical_food="fish_meat",
        food_family="fish",
        identity_terms=("tonfisk", "tuna"),
        allowed_roles=frozenset({"tuna_meat", "canned_tuna"}),
    ),
    "lax": IngredientSemanticRule(
        canonical_food="fish_meat",
        food_family="fish",
        identity_terms=("lax", "salmon"),
        allowed_roles=frozenset({"salmon"}),
    ),
    "fläskkött": IngredientSemanticRule(
        canonical_food="pork_meat",
        food_family="meat",
        identity_terms=("fläskkött", "fläskfilé", "fläskytterfilé", "pork"),
        allowed_roles=frozenset({"generic_meat", "fillet", "chop", "roast"}),
        excluded_roles=frozenset({"pork_mince", "processed_ready_meal"}),
    ),
    "falukorv": IngredientSemanticRule(
        canonical_food="korv",
        food_family="meat",
        identity_terms=("falukorv",),
        allowed_roles=frozenset({"falukorv"}),
    ),
    "frysta grönsaker": IngredientSemanticRule(
        canonical_food="vegetable_mixture",
        food_family="vegetable",
        identity_terms=(
            "grönsaksblandning",
            "gronsaksblandning",
            "wokmix",
            "wok mix",
            "broccoli mix",
            "vegetable mix",
        ),
        allowed_roles=frozenset({"vegetable_mixture"}),
    ),
    "oliver": IngredientSemanticRule(
        canonical_food="olive",
        food_family="fruit",
        identity_terms=("oliv", "oliver", "olive", "olives"),
        allowed_roles=frozenset(
            {"plain_olive", "preserved_olive", "marinated_olive", "stuffed_olive"}
        ),
    ),
    "buljong": IngredientSemanticRule(
        canonical_food="broth",
        food_family="broth",
        identity_terms=("buljong", "fond", "broth", "stock"),
        allowed_roles=frozenset({"broth"}),
    ),
}


_RAW_PRODUCE_ROLE_FORMS: dict[str, str] = {
    "stalk_vegetable": "fresh",
    "whole_mushroom": "fresh",
    "whole_vegetable": "fresh",
}


def _raw_produce_default(rule: IngredientSemanticRule) -> tuple[str, str] | None:
    role = next(
        (candidate for candidate in _RAW_PRODUCE_ROLE_FORMS if candidate in rule.allowed_roles),
        None,
    )
    if role is None:
        return None
    return role, _RAW_PRODUCE_ROLE_FORMS[role]


# This classification is derived from the semantic rule itself. Adding a new
# raw produce canonical automatically opts it into preserved-category safety;
# there is no second list which can silently omit it.
_RAW_VISIBLE_DEFAULTS: dict[str, tuple[str, str]] = {
    canonical: default
    for canonical, rule in _RULES.items()
    if (default := _raw_produce_default(rule)) is not None
}
_FRESH_PRODUCE_CANONICALS = frozenset(_RAW_VISIBLE_DEFAULTS)


_FAMILY_BY_CANONICAL: dict[str, str] = {
    "nötfärs": "meat",
    "blandfärs": "meat",
    "köttfärs": "meat",
    "fläskkött": "meat",
    "fisk": "fish",
    "lax": "fish",
    "bönor": "legume",
    "kidneybönor": "legume",
    "svarta bönor": "legume",
    "pasta": "grain",
    "potatis": "vegetable",
    "gul lök": "allium",
    "rödlök": "allium",
    "mjölk": "dairy",
    "grädde": "dairy",
}


_NON_HUMAN_FOOD_TERMS = (
    "torrfoder",
    "våtfoder",
    "blötmat",
    "hundmat",
    "kattmat",
    "hundfoder",
    "kattfoder",
    "djurfoder",
    "valpfoder",
    "kattungefoder",
    "hundgodis",
    "kattgodis",
    "hundsnack",
    "kattsnack",
    "dog food",
    "cat food",
    "dog treat",
    "dog treats",
    "cat treat",
    "cat treats",
    "pet food",
    "catmilk",
    "kattmjölk",
)
_PET_AUDIENCE_TERMS = ("hund", "katt", "dog", "cat", "valp", "puppy", "kitten")
_PET_PRODUCT_TERMS = ("foder", "godis", "treat", "treats", "pet food")


def is_non_human_food(*visible_values: str) -> bool:
    """Return whether visible source facts identify animal food.

    The compound markers cover product names while the paired audience/feed
    test covers category paths such as ``Djur > Hund > Foder``.  Generic
    ``dog`` alone is intentionally insufficient, so human products such as a
    hot dog remain valid sausage candidates.
    """

    visible = _search_text(" ".join(value for value in visible_values if value))
    if _contains_any(visible, _NON_HUMAN_FOOD_TERMS):
        return True
    return _contains_any(visible, _PET_AUDIENCE_TERMS) and _contains_any(
        visible, _PET_PRODUCT_TERMS
    )


# Raw/base ingredients must not silently become a prepared dish merely because
# the dish name contains the search term. Canonicals which are inherently
# processed (korv, buljong, sojasås, krossade tomater, etc.) are deliberately
# absent rather than special-cased in the matcher.
_RAW_RECIPE_CANONICALS = (
    frozenset(
        {
            "kyckling",
            "chicken_breast",
            "kycklinghjärta",
            "kycklinglever",
            "kycklingmage",
            "kycklingkrås",
            "kycklinginälvor",
            "nötfärs",
            "blandfärs",
            "köttfärs",
            "fläskkött",
            "fisk",
            "lax",
            "ägg",
            "bönor",
            "kidneybönor",
            "svarta bönor",
            "kikärtor",
            "linser",
            "torra linser",
            "pasta",
            "nudlar",
            "couscous",
            "ris",
            "potatis",
            "gul lök",
            "rödlök",
            "morot",
            "tomat",
            "paprika",
            "broccoli",
            "vitkål",
            "mjölk",
            "grädde",
            "crème fraiche",
            "ost",
            "smör",
            "vitlök",
            "majs",
            "tofu",
        }
    )
    | _FRESH_PRODUCE_CANONICALS
)

_PREPARED_FORM_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "ready_meal",
        (
            "färdigrätt",
            "fardigratt",
            "bolognese",
            "lasagne",
            "lasagna",
            "gratäng",
            "gratang",
            "nuggets",
            "fiskpinnar",
            "burek",
            "börek",
        ),
    ),
    ("pizza", ("pizza",)),
    ("wrap", ("wrap",)),
    ("sushi", ("sushi",)),
    ("hummus", ("hummus",)),
    ("pesto", ("pesto",)),
    ("wok_dish", ("wok",)),
    ("chili_dish", ("chili",)),
    ("snack", ("chips", "snack", "snacks")),
    ("cracker", ("kex", "ostkex", "smörgåskex", "cracker", "crackers")),
    ("deli_product", ("pålägg", "palagg", "deli meat")),
    ("smoked", ("rökt", "rokt", "smoked")),
    ("cured", ("gravad", "gravade", "gravlax", "rimmad", "rimmade", "cured")),
    (
        "fermented",
        ("surkål", "surkal", "sauerkraut", "kimchi", "fermenterad", "fermented"),
    ),
    ("pickled", ("inlagd", "inlagda", "picklad", "picklade", "pickled")),
    (
        "preserved_in_oil",
        ("i solrosolja", "i olivolja", "i olja", "in sunflower oil", "in olive oil", "in oil"),
    ),
    ("canned", ("i vatten", "in water", "konserv", "canned")),
    ("mixture", ("mix", "blandning", "mixture", "soppgrönsaker")),
    ("stuffed", ("fylld", "fyllda", "stuffed")),
    ("marinated", ("marinerad", "marinerade", "marinated")),
    ("gyros", ("gyros",)),
    (
        "processed_stick",
        (
            "kycklingpinnar",
            "kyckling pinnar",
            "chicken sticks",
            "chicken fingers",
        ),
    ),
    ("skewer", ("spett", "skewer", "skewers")),
    (
        "seasoned",
        (
            "kryddad",
            "kryddade",
            "seasoned",
            "teriyaki",
            "tandoori",
            "barbecue",
            "bbq",
            "sweet chili",
            "sweet chilli",
        ),
    ),
    ("sauce", ("sås", "sas", "sauce")),
    ("condiment", ("salsa", "chutney", "relish", "ketchup", "senap", "mustard")),
    ("pie", ("paj", "pie")),
    ("burger", ("burgare", "burger")),
    ("soup", ("soppa", "soup")),
    ("salad", ("sallad", "salad")),
    ("pudding", ("pudding", "gröt", "grot")),
    ("sausage", ("korv", "sausage")),
    ("meatballs", ("köttbullar", "kottbullar", "meatballs")),
    ("loaf", ("färslimpa", "farslimpa", "meatloaf")),
    ("powder", ("pulver", "powder")),
)

_PREPARED_ROLE_BY_FORM: dict[str, str] = {
    "fermented": "fermented_vegetable_mixture",
    "pizza": "prepared_dish",
    "wrap": "prepared_dish",
    "sushi": "prepared_dish",
    "hummus": "prepared_dish",
    "pesto": "prepared_dish",
    "wok_dish": "prepared_dish",
    "chili_dish": "prepared_dish",
    "snack": "snack",
    "cracker": "cracker",
    "deli_product": "processed_deli_meat",
    "smoked": "smoked_product",
    "cured": "cured_product",
    "pasta_dish": "prepared_dish",
    "pickled": "pickled_vegetable_mixture",
    "preserved_in_oil": "preserved_in_oil",
    "canned": "preserved_product",
    "mixture": "ambiguous_mixture",
    "stuffed": "stuffed_product",
    "marinated": "marinated_product",
    "gyros": "processed_kebab",
    "processed_stick": "processed_stick",
    "skewer": "prepared_skewer",
    "seasoned": "seasoned_product",
    "sauce": "sauce",
    "condiment": "condiment",
    "pie": "prepared_dish",
    "burger": "processed_burger",
    "soup": "prepared_dish",
    "salad": "prepared_dish",
    "pudding": "prepared_dish",
    "sausage": "processed_sausage",
    "meatballs": "processed_meatballs",
    "loaf": "processed_meatloaf",
    "ready_meal": "processed_ready_meal",
    "powder": "powdered_product",
}

_KNOWN_PROCESSED_ROLES = frozenset(
    {
        "bread",
        "breaded_ready_food",
        "broth",
        "canned_tuna",
        "cheese_flavoured_snack",
        "cheese_sauce",
        "condiment",
        "dressing",
        "fermented_vegetable_mixture",
        "fish_balls",
        "fish_burger",
        "fish_cakes",
        "grilling_cheese",
        "ambiguous_mixture",
        "pickled_vegetable_mixture",
        "pudding_rice",
        "powdered_product",
        "prepared_dish",
        "processed_burger",
        "processed_kebab",
        "processed_meatballs",
        "processed_meatloaf",
        "processed_ready_meal",
        "processed_sausage",
        "processed_stick",
        "preserved_in_oil",
        "preserved_product",
        "preserved_fish",
        "processed_deli_meat",
        "sauce",
        "seasoning",
        "snack",
        "spread",
        "smoked_product",
        "stuffed_olive",
        "marinated_olive",
        "marinated_product",
        "preserved_olive",
        "prepared_skewer",
        "seasoned_product",
    }
)

# Product-class identities are ordered from the strongest retail identity to
# the more general food classes.  The order matters for names such as
# ``Parmesan Lätt Crème Fraiche``: the sold product is crème fraiche, while
# parmesan is a flavour/variant. Likewise ``Cheddar Majskakor`` is a snack,
# not a block of cheese. This is deliberately one central taxonomy rather than
# a growing collection of target-specific rejection strings.
_PRIMARY_PRODUCT_IDENTITIES: tuple[PrimaryProductIdentityRule, ...] = (
    PrimaryProductIdentityRule(
        canonical_food="supplement",
        food_family="non_meal",
        product_role="supplement",
        product_form="supplement",
        name_terms=(
            "kosttillskott",
            "vitlökstabletter",
            "vitlokstabletter",
            "vitlökskapslar",
            "vitlokskapslar",
            "garlic supplement",
            "garlic capsules",
        ),
        category_terms=("kosttillskott", "vitaminer och mineraler"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="baby_food",
        food_family="prepared_food",
        product_role="processed_ready_meal",
        product_form="baby_food",
        name_terms=(
            "barnmat",
            "baby food",
            "babyfood",
            "från 6 månader",
            "från 8 månader",
            "från 12 månader",
        ),
        category_terms=("barnmat", "baby food"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="fish_roe",
        food_family="fish",
        product_role="fish_roe_spread",
        product_form="spread",
        name_terms=("kaviar", "caviar", "fish roe"),
        category_terms=("kaviar & rom", "kaviar och rom", "caviar", "fish roe"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="krossade_tomater",
        food_family="vegetable",
        product_role="preserved_tomato",
        product_form="canned",
        name_terms=(
            "krossade tomater",
            "tomater krossade",
            "krossad tomat",
            "tomatkross",
            "chopped tomatoes",
        ),
    ),
    PrimaryProductIdentityRule(
        canonical_food="korv",
        food_family="meat",
        product_role="falukorv",
        product_form="sausage",
        name_terms=("falukorv",),
    ),
    PrimaryProductIdentityRule(
        canonical_food="korv",
        food_family="meat",
        product_role="processed_sausage",
        product_form="sausage",
        name_terms=(
            "bratwurst",
            "korv",
            "sausage",
            "salami",
            "hotdog",
            "hot dog",
        ),
        category_terms=("korv", "salami", "hotdog", "hot dog"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="charcuterie",
        food_family="meat",
        product_role="processed_deli_meat",
        product_form="charcuterie",
        name_terms=("bacon", "prosciutto", "pastrami"),
        category_terms=("chark", "charcuterie"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="mayonnaise",
        food_family="condiment",
        product_role="condiment",
        product_form="condiment",
        name_terms=("majonnäs", "majonnas", "mayonnaise", "mayo"),
        category_terms=("majonnäs", "majonnas", "mayonnaise"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="cooking_oil",
        food_family="fat",
        product_role="cooking_oil",
        product_form="oil",
        # Do not use generic ``olja`` as a name term: in "tonfisk i
        # solrosolja" it describes the packing medium, not the sold food.
        name_terms=(
            "vitlöksolja",
            "vitloksolja",
            "garlic oil",
            "olja vitlök",
            "olja vitlok",
            "olja med vitlök",
            "olja med vitlok",
        ),
        category_terms=("matolja", "smaksatt olja", "flavoured oil", "flavored oil"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="grain_snack",
        food_family="grain",
        product_role="snack",
        product_form="processed",
        name_terms=("majskakor", "riskakor", "rice cakes", "corn cakes"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="oat",
        food_family="grain",
        product_role="cooking_staple",
        product_form="grain",
        name_terms=("havreris", "havre ris", "oat rice"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="barley",
        food_family="grain",
        product_role="cooking_staple",
        product_form="grain",
        name_terms=("kornris", "korn ris", "barley rice"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="creme_fraiche",
        food_family="dairy",
        product_role="dairy_base",
        product_form="cultured",
        name_terms=("crème fraiche", "creme fraiche", "crème fraîche"),
        category_terms=("crème fraiche", "creme fraiche"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="nudlar",
        food_family="grain",
        product_role="processed_ready_meal",
        product_form="prepared",
        name_terms=(
            "cup noodles",
            "koppnudlar",
            "snabbnudlar",
            "instant noodles",
        ),
    ),
    PrimaryProductIdentityRule(
        canonical_food="nudlar",
        food_family="grain",
        product_role="cooking_staple",
        product_form="dried",
        name_terms=("nudlar", "noodles"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="couscous",
        food_family="grain",
        product_role="cooking_staple",
        product_form="grain",
        name_terms=("couscous",),
    ),
    PrimaryProductIdentityRule(
        canonical_food="gnocchi",
        food_family="grain",
        product_role="prepared_dish",
        product_form="prepared",
        name_terms=("gnocchi",),
    ),
    PrimaryProductIdentityRule(
        canonical_food="risotto",
        food_family="grain",
        product_role="prepared_dish",
        product_form="prepared",
        name_terms=("risotto",),
    ),
    PrimaryProductIdentityRule(
        canonical_food="labneh",
        food_family="dairy",
        product_role="dairy_spread",
        product_form="cultured",
        name_terms=("labneh",),
    ),
    PrimaryProductIdentityRule(
        canonical_food="cheese",
        food_family="dairy",
        product_role="cream_cheese",
        product_form="spreadable",
        name_terms=(
            "färskost",
            "farskost",
            "cream cheese",
            "mjukost",
            "smältost",
            "smaltost",
            "spreadable cheese",
        ),
        category_terms=(
            "färskost",
            "farskost",
            "cream cheese",
            "mjukost",
            "smältost",
            "smaltost",
        ),
    ),
    PrimaryProductIdentityRule(
        canonical_food="cheese",
        food_family="dairy",
        product_role="salad_cheese",
        product_form="cheese",
        name_terms=("vitost", "fetaost", "salladsost"),
        category_terms=("fetaost", "salladsost"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="whey_cheese",
        food_family="dairy",
        product_role="whey_cheese",
        product_form="whey_cheese",
        name_terms=("mesost", "brunost", "whey cheese", "brown cheese"),
        category_terms=("mesost", "brunost", "whey cheese", "brown cheese"),
    ),
    PrimaryProductIdentityRule(
        canonical_food="cheese",
        food_family="dairy",
        product_role="hard_cheese",
        product_form="cheese",
        name_terms=(
            "cambozola",
            "gorgonzola",
            "camembert",
            "hushållsost",
            "cheddar",
            "gouda",
            "mozzarella",
            "parmesan",
        ),
        category_terms=("hårdost", "hard cheese"),
    ),
)

_PRESERVED_PRODUCE_CATEGORY_TERMS = (
    "grönsakskonserver",
    "gronsakskonserver",
    "konserverade grönsaker",
    "konserverade gronsaker",
    "canned vegetables",
)


def _identity_term_visible(text: str, term: str) -> bool:
    normalized = _search_text(term)
    if _contains_phrase(text, normalized):
        return True
    # Retail compounds such as ``koppnudlar`` are product-class nouns.  Only
    # suffix matching is allowed here; broad substring matching would turn a
    # flavour word back into product identity.
    return (
        " " not in normalized
        and len(normalized) >= 4
        and any(token.endswith(normalized) for token in text.split())
    )


def _infer_primary_product_identity(
    name_text: str,
    category_text: str,
) -> tuple[str, str | None, str, str] | None:
    """Infer the sold product's dominant class before ingredient flavours.

    Visible product-class nouns win first. A narrow category fallback is used
    only when it names a concrete class, never for generic catalogue branches
    such as ``Livsmedel`` or ``Mat``.
    """

    # A low-confidence collector may preserve the whole raw label as its food
    # key (e.g. rodbeta_klass_1). The complete label AND fresh-produce category
    # establish the actual food; no juice, pickle, puree or flavoured composite.
    if any(t in category_text for t in ('frukt', 'gronsak', 'gront', 'rotsak', 'potatis', 'aubergine', 'zucchini')):
        if re.fullmatch(r'(?:rodlok|rod lok|lok rod)(?: klass 1| eko| ekologisk| svensk| sverige| i pase)*', name_text):
            return 'red_onion', 'allium', 'whole_vegetable', 'fresh'
        for pattern, food in (
            (r'rodbet(?:a|or)', 'beetroot'), (r'sotpotatis', 'sweet_potato'),
            (r'aubergine', 'aubergine'), (r'(?:zucchini|squash)', 'zucchini'),
            (r'pepparrot', 'horseradish'),
        ):
            if re.fullmatch(rf'(?:ekologisk |farsk )?{pattern}(?: klass 1| eko| ekologisk| svensk| sverige| i ask)*', name_text):
                return food, 'vegetable', 'whole_vegetable', 'fresh'
    # A complete Swedish bread-loaf noun, including branded compounds. A loaf
    # shape alone is not food identity: meat/fish/vegetable loaves and cake/mix
    # names must not become bread. Nutrition still needs its own declaration.
    if (re.fullmatch(r"[a-z]+limpan?(?: \d+(?: \d+)? (?:g|kg))?", name_text)
            and not any(t in name_text for t in
                        ("fars", "kott", "fisk", "kyckling", "lax", "lins", "bon", "banan", "kaka", "mix"))):
        return "brod", "grain", "bread", "ready"
    for rule in _PRIMARY_PRODUCT_IDENTITIES:
        if any(_identity_term_visible(name_text, term) for term in rule.name_terms):
            return (
                rule.canonical_food,
                rule.food_family,
                rule.product_role,
                rule.product_form,
            )
    for rule in _PRIMARY_PRODUCT_IDENTITIES:
        # ``Kött, chark & fågel`` is an ancestor navigation branch, not a
        # declaration that every child is charcuterie. Let an exact visible
        # meat identity (for example chicken fillet or beef mince) and its
        # structured identity be evaluated below. Concrete chark categories
        # and visible class nouns such as bacon/salami still retain their
        # normal dominant-product behaviour.
        if (
            rule.canonical_food == "charcuterie"
            and _contains_phrase(category_text, "chark")
            and _contains_any(
                category_text,
                ("kött", "kott", "fågel", "fagel", "meat", "poultry"),
            )
        ):
            continue
        if rule.category_terms and _contains_any(category_text, rule.category_terms):
            return (
                rule.canonical_food,
                rule.food_family,
                rule.product_role,
                rule.product_form,
            )
    return None


def _classify_produce_category_form(category_text: str) -> str | None:
    if _contains_any(category_text, _PRESERVED_PRODUCE_CATEGORY_TERMS):
        return "canned"
    return None


# Filled-dough dishes named by the product itself ("Dumplings Kyckling",
# "Gyoza Pork & Masala", "Köttfärspirog"). Their visible meat is a filling, so
# they are ready meals and never a recipe's raw meat line. Name only: broad
# navigation such as "Pizza, paj & piroger" is not product-class proof, and
# separate dough/sauce products ("Gyoza Skin Deg", "Gyoza Sauce") are excluded.
_FILLED_DOUGH_DISH_MARKERS = (
    "dumpling", "gyoza", "wonton", "dim sum", "dimsum", "pirog", "varrull", "spring roll",
)
_FILLED_DOUGH_COMPONENT_WORDS = ("sauce", "sas", "deg", "skin", "skins", "dough", "wrapper", "wrappers")


def _is_pepper_colour_mix(text: str) -> bool:
    """A pack of whole bell peppers in mixed colours, not a vegetable blend."""
    return bool(re.fullmatch(
        r"(?:spets)?paprika(?: (?:spets|snacks|ramiro|eko|ekologisk|klass [12]))* mix"
        r"(?: (?:eko|ekologisk|klass [12]))*", text))


def _is_filled_dough_dish(text: str) -> bool:
    return (any(marker in text for marker in _FILLED_DOUGH_DISH_MARKERS)
            and not _contains_any(text, _FILLED_DOUGH_COMPONENT_WORDS))


def _classify_prepared_form(text: str) -> str | None:
    for product_form, markers in _PREPARED_FORM_MARKERS:
        if any(_search_text(marker) in text for marker in markers):
            return product_form
    return None


_SECONDARY_COMPONENT_CUES: tuple[tuple[str, ...], ...] = tuple(
    tuple(_search_text(cue).split())
    for cue in (
        "med",
        "with",
        "smak av",
        "flavour of",
        "flavor of",
        "fylld med",
        "fyllda med",
        "stuffed with",
    )
)


def _sequence_positions(tokens: list[str], sequence: tuple[str, ...]) -> list[int]:
    width = len(sequence)
    return [
        index
        for index in range(len(tokens) - width + 1)
        if tuple(tokens[index : index + width]) == sequence
    ]


def _component_position(
    requirement: SemanticRequirement,
    name_text: str,
) -> str | None:
    """Return whether target evidence is primary or only a secondary component."""

    tokens = name_text.split()
    cue_ranges = [
        (start, start + len(cue) - 1)
        for cue in _SECONDARY_COMPONENT_CUES
        for start in _sequence_positions(tokens, cue)
    ]
    if not cue_ranges:
        return None

    rule = _RULES.get(requirement.canonical_name)
    terms = {
        requirement.canonical_name,
        *(rule.identity_terms if rule is not None else ()),
        *CANONICAL_ALIASES.get(requirement.canonical_name, ()),
    }
    target_positions: set[int] = set()
    for term in terms:
        normalized = tuple(_search_text(term).split())
        if not normalized:
            continue
        target_positions.update(_sequence_positions(tokens, normalized))
        if len(normalized) == 1 and len(normalized[0]) >= 4:
            target_positions.update(
                index for index, token in enumerate(tokens) if normalized[0] in token
            )

    if not target_positions:
        return None
    first_target = min(target_positions)
    first_cue_start = min(start for start, _ in cue_ranges)
    if first_target < first_cue_start:
        return "primary"
    if any(cue_end < first_target for _, cue_end in cue_ranges):
        return "secondary"
    return None


def has_semantic_rule(canonical_name: str) -> bool:
    """Whether a generic query has an authoritative shared identity/form rule."""
    return canonicalize_ingredient_name(canonical_name) in _RULES or canonicalize_ingredient_name(canonical_name) in {
        "yoghurt naturell", "paprikapulver", "keso", "kapris", *_CULINARY_LABELS,
    }


# Full, plain product labels supply identity for culinary ingredients absent
# from the historical dinner taxonomy. They cannot match a flavour inside a
# cheese/chip/ready meal. Recipe input-form guards remain independently binding.
_CULINARY_LABELS = {
    "salt": (r"(?:salt|hushallssalt|finkornigt salt)(?: med jod| utan jod| fint| finkornigt)*", "salt"),
    "svartpeppar": (r"svartpeppar", "single_spice"),
    "rökt paprikapulver": (r"(?:rokt paprikapulver|paprikapulver rokt|rokt paprika|paprika rokt|paprika smoked|smoked paprika)", "single_spice"),
    "malen koriander": (r"(?:malen koriander|koriander malen)", "single_spice"),
    "chiliflakes": (r"(?:chiliflakes|chili flakes|chiliflingor)", "single_spice"),
    "strösocker": (r"strosocker", "sugar"),
    "jordnötter": (r"(?:rostade )?jordnotter(?: rostade| osaltade)*", "nuts"),
    "gnocchi": (r"(?:potatisgnocchi|gnocchi)(?: di patate| potatis| naturell| original)*", "pasta"),
    "spiskummin": (r"spiskummin", "single_spice"),
    "cayennepeppar": (r"cayennepeppar", "single_spice"),
    "kanel": (r"kanel(?: cassia| ceylon)?", "single_spice"),
    "gurkmeja": (r"gurkmeja", "single_spice"),
    "oregano": (r"oregano", "herb"),
    "persilja": (r"(?:persilja|bladpersilja)", "herb"),
    "basilika": (r"basilika", "herb"),
    "dill": (r"dill", "herb"),
    "sesamfrön": (r"sesamfron", "seed"),
    "jordnötssmör": (r"jordnotssmor", "nut_butter"),
}
from app.services.content_pack_requirements import INTAKE_IDENTITIES

_CULINARY_LABELS.update({name: (entry[1], entry[2]) for name, entry in INTAKE_IDENTITIES.items()})


def _culinary_label_match(canonical, product):
    label = _search_text(str(_value(product, "name", "")))
    identity, role = _CULINARY_LABELS[canonical]
    descriptors = r"(?:malen|mald|eko|ekologisk|ekologiska|burk|pase|tetra|hel|hela|torkad|krus|blad|knippe|kruka|i kruka|i ask|fryst|frysta|finhackad|farsk|vita|skalade|oskalade|klass 1)"
    if canonical == 'jordnötssmör':
        descriptors = r'(?:crunchy|smooth|creamy|crunch|super chunk|eko|ekologiskt|ekologisk)'
    if canonical == 'salt':
        descriptors = r'(?:fint|finkornigt)'
    compatible = bool(re.fullmatch(rf"(?:{descriptors} )*{identity}(?: {descriptors})*", label))
    return SemanticMatchResult(
        compatible=compatible,
        confidence=SemanticConfidence.HIGH if compatible else SemanticConfidence.REJECTED,
        canonical_food=canonical, product_role=role,
        evidence=["complete_plain_culinary_label" if compatible else "different_whole_product_identity"],
    )


def semantic_requirement(canonical_name: str) -> SemanticRequirement:
    """Resolve an external canonical ingredient to food/role constraints."""

    canonical = canonicalize_ingredient_name(canonical_name)
    rule = _RULES.get(canonical)
    if rule is None:
        rule = IngredientSemanticRule(
            canonical_food=_search_text(canonical).replace(" ", "_"),
            food_family=_FAMILY_BY_CANONICAL.get(canonical),
            identity_terms=CANONICAL_ALIASES.get(canonical, (canonical,)),
        )
    return SemanticRequirement(
        canonical_name=canonical,
        canonical_food=rule.canonical_food,
        food_family=rule.food_family,
        allowed_roles=rule.allowed_roles,
        excluded_roles=rule.excluded_roles,
        excluded_forms=rule.excluded_forms,
    )


def _normalize_food_identity(value: Any) -> str | None:
    """Accept both external canonical names and internal food identifiers."""

    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    internal = _search_text(raw).replace(" ", "_")
    if internal in {rule.canonical_food for rule in _RULES.values()}:
        return internal
    canonical = canonicalize_ingredient_name(raw)
    rule = _RULES.get(canonical)
    if rule is not None:
        return rule.canonical_food
    return _search_text(canonical).replace(" ", "_")


def _has_broth_identity(text: str) -> bool:
    return any(
        marker in token
        for token in text.split()
        for marker in ("buljong", "bouillon", "fond", "broth", "stock")
    )


def _infer_chicken_role(text: str) -> tuple[str, str | None] | None:
    if not ("kyckling" in text or _contains_phrase(text, "chicken")):
        return None
    # Broth identity is independent of word order and compounds. Catalogue
    # names include both ``Kycklingbuljong`` and reversed forms such as
    # ``Ramenbuljong Kyckling``. Once a chicken identity and any broth/stock
    # marker coexist, this is a liquid broth rather than ordinary meat.
    if _has_broth_identity(text):
        return "broth", "liquid"
    ordered_roles: tuple[tuple[str, tuple[str, ...], str | None], ...] = (
        (
            "heart",
            (
                "kycklinghjärta",
                "kycklinghjartan",
                "kyckling hjärta",
                "kyckling hjärtan",
                "chicken heart",
            ),
            "organ",
        ),
        ("liver", ("kycklinglever", "kyckling lever", "chicken liver"), "organ"),
        (
            "gizzard",
            (
                "kycklingmage",
                "kycklingmagar",
                "kyckling mage",
                "kycklingkrås",
                "kycklingkras",
                "kyckling krås",
                "kyckling kras",
                "chicken gizzard",
            ),
            "organ",
        ),
        (
            "organ_mix",
            (
                "kycklinginälvor",
                "kycklinginalvor",
                "kyckling inälvor",
                "kyckling inalvor",
                "chicken offal",
            ),
            "organ",
        ),
        (
            "feet",
            ("kycklingfot", "kycklingfötter", "kyckling fot", "kyckling fötter", "chicken feet"),
            "organ",
        ),
        ("skin_only", ("kycklingskinn", "kyckling skinn", "chicken skin"), "skin"),
        (
            "broth",
            (
                "kycklingbuljong",
                "kyckling buljong",
                "kycklingfond",
                "kyckling fond",
                "chicken broth",
            ),
            "liquid",
        ),
        (
            "minced_meat",
            ("kycklingfärs", "kyckling färs", "chicken mince", "ground chicken"),
            "minced",
        ),
        (
            "processed_sausage",
            ("kycklingkorv", "kyckling korv", "chicken sausage"),
            "processed",
        ),
        (
            "processed_kebab",
            (
                "kycklingkebab",
                "kyckling kebab",
                "chicken kebab",
                "kycklinggyros",
                "kyckling gyros",
                "chicken gyros",
            ),
            "processed",
        ),
        (
            "processed_stick",
            (
                "kycklingpinnar",
                "kyckling pinnar",
                "chicken sticks",
                "chicken fingers",
            ),
            "processed",
        ),
        (
            "processed_burger",
            ("kycklingburgare", "kyckling burgare", "chicken burger"),
            "processed",
        ),
        (
            "processed_ready_meal",
            (
                "kycklingsoppa",
                "kycklinglasagne",
                "kycklinggryta",
                "kycklingnuggets",
                "chicken nuggets",
                "färdigrätt",
            ),
            "prepared",
        ),
        ("thigh", ("kycklinglårfilé", "kycklinglår", "chicken thigh"), "thigh_fillet"),
        ("breast", ("kycklingbröst", "bröstfilé", "kycklingfilé", "chicken breast"), "fillet"),
        ("drumstick", ("kycklingklubba", "kycklingben", "drumstick"), "bone_in"),
        ("wing", ("kycklingvinge", "kycklingvingar", "chicken wing"), "bone_in"),
        ("whole_meat", ("hel kyckling", "whole chicken"), "whole"),
    )
    for role, phrases, form in ordered_roles:
        if any(_search_text(phrase) in text for phrase in phrases):
            return role, form
    return "generic_meat", "meat"


def _infer_special_identity(
    text: str,
    category_text: str = "",
) -> tuple[str, str | None, str | None, str | None] | None:
    # A condiment containing a food flavour is still the condiment, not the
    # raw food. This identity check deliberately precedes garlic/chicken/etc.
    # so e.g. "Salsa Vitlök" cannot inherit garlic's raw bulb semantics.
    condiment_identities = ("salsa", "chutney", "relish", "ketchup", "senap", "mustard")
    for condiment in condiment_identities:
        if _contains_phrase(text, condiment):
            identity = _search_text(condiment).replace(" ", "_")
            return identity, "condiment", "condiment", "condiment"

    if _has_broth_identity(text):
        return "broth", "broth", "broth", "liquid"

    tokens = text.split()
    if any(token in {"oliv", "olive", "olives"} or token.endswith("oliver") for token in tokens):
        if _contains_any(text, ("fylld", "fyllda", "stuffed")):
            return "olive", "fruit", "stuffed_olive", "stuffed"
        if any(marker in token for token in tokens for marker in ("marinerad", "marinated")):
            return "olive", "fruit", "marinated_olive", "marinated"
        return "olive", "fruit", "preserved_olive", "preserved"

    # "Paprika Mix Klass 1" is a pack of whole bell peppers in mixed colours,
    # not a vegetable blend; it continues to the pepper branch below.
    if not _is_pepper_colour_mix(text) and _classify_prepared_form(text) == "mixture" and any(
        marker in text
        for marker in (
            "broccoli",
            "morot",
            "paprika",
            "gronsak",
            "wok",
            "blomkal",
            "bonor",
            "majs",
        )
    ):
        return "vegetable_mixture", "vegetable", "vegetable_mixture", "mixture"

    chicken = _infer_chicken_role(text)
    if chicken is not None:
        role, form = chicken
        if role == "broth":
            return "broth", "broth", role, form
        return "chicken", "poultry", role, form

    if any(token.startswith(("paprika", "spetspaprika")) for token in text.split()):
        # "Paprika Rökt"/"Paprika Smoked" on the spice shelf is smoked paprika
        # powder, never a fresh bell pepper.
        if _contains_any(text, ("paprikapulver", "krydda", "rokt", "smoked")):
            return "pepper", "vegetable", "seasoning", "dried"
        if _contains_any(text, ("paprikachips", "snack")):
            return "pepper", "vegetable", "snack", "processed"
        if _contains_any(text, ("paprikasås", "paprikasas")):
            return "pepper", "vegetable", "sauce", "processed"
        role = "mixed_whole_vegetable" if "mix" in text else "whole_vegetable"
        return "pepper", "vegetable", role, "fresh"

    if "tonfisk" in text or _contains_phrase(text, "tuna"):
        tuna_form = _classify_prepared_form(text)
        if tuna_form in {"canned", "preserved_in_oil"}:
            return "fish_meat", "fish", "canned_tuna", tuna_form
        return "fish_meat", "fish", "tuna_meat", "fillet"

    fish_processed_roles: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("fish_balls", ("fiskbullar", "fisk bullar", "fish balls")),
        ("fish_burger", ("fiskburgare", "fisk burgare", "fish burger")),
        ("fish_cakes", ("fiskkakor", "fisk kakor", "fish cakes")),
    )
    for role, phrases in fish_processed_roles:
        if any(_search_text(phrase) in text for phrase in phrases):
            return "fish_meat", "fish", role, "processed"
    if _contains_any(text, ("fiskpinnar", "fiskgratäng", "fiskgratang")):
        return "fish_meat", "fish", "breaded_ready_food", "prepared"
    if _contains_any(text, ("fiskbuljong", "fiskfond")):
        return "fish_meat", "fish", "broth", "liquid"
    if any(marker in text for marker in ("torsk", "sej", "kolja")):
        return "fish_meat", "fish", "white_fish", "fillet"
    if "lax" in text or _contains_phrase(text, "salmon"):
        return "fish_meat", "fish", "salmon", "fillet"
    if "fisk" in text:
        return "fish_meat", "fish", "generic_fish", "meat"

    if _contains_any(text, ("fläskfärs", "flaskfars")):
        return "pork_meat", "meat", "pork_mince", "minced"
    if any(
        marker in text for marker in ("flaskytterfile", "flaskfile", "fläskytterfilé", "fläskfilé")
    ):
        return "pork_meat", "meat", "fillet", "fillet"
    if _contains_any(text, ("fläskkotlett", "flaskkotlett", "pork chop")):
        return "pork_meat", "meat", "chop", "bone_in"
    if "flaskkott" in text or _contains_phrase(text, "pork"):
        return "pork_meat", "meat", "generic_meat", "meat"

    mince_ready_meals = (
        "köttfärssås",
        "köttfärs sås",
        "köttfärspaj",
        "köttfärs paj",
        "köttfärslasagne",
        "köttfärs lasagne",
        "mince sauce",
        "mince pie",
        "mince lasagne",
    )
    if any(_search_text(phrase) in text for phrase in mince_ready_meals):
        return "meat_mince", "meat", "processed_ready_meal", "prepared"

    mince_roles: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("beef_mince", ("nötfärs", "notfars")),
        ("mixed_mince", ("blandfärs", "blandfars")),
        ("pork_mince", ("fläskfärs", "flaskfars")),
        ("chicken_mince", ("kycklingfärs", "kycklingfars")),
        ("plant_mince", ("vegofärs", "vegofars", "sojafärs", "formbar färs")),
        ("generic_meat_mince", ("köttfärs", "kottfars")),
    )
    for role, phrases in mince_roles:
        if any(_search_text(phrase) in text for phrase in phrases):
            family = "plant" if role == "plant_mince" else "meat"
            food = "plant_mince" if role == "plant_mince" else "meat_mince"
            return food, family, role, "minced"

    bean_identity: tuple[str, str] | None = None
    if "kidneybon" in text or _contains_phrase(text, "kidney beans"):
        bean_identity = ("kidney_bean", "plain_bean")
    elif _contains_any(text, ("svarta bönor", "svarta bonor", "black beans")):
        bean_identity = ("black_bean", "plain_bean")
    elif _contains_any(text, ("vita bönor", "vita bonor", "white beans")):
        bean_identity = ("white_bean", "plain_bean")
    if bean_identity is not None:
        bean_food, bean_role = bean_identity
        if _contains_any(text, ("burk", "tetra", "konserv", "canned", "kokta")):
            bean_role = "canned_bean"
            bean_form = "canned"
        elif _contains_any(text, ("torra", "torkade", "okokta", "dry", "dried")):
            bean_role = "dry_bean"
            bean_form = "dry"
        else:
            bean_form = "plain"
        return bean_food, "legume", bean_role, bean_form

    if any(marker in text for marker in ("kikarta", "kikartor", "kikarter", "chickpea")):
        if _contains_any(text, ("burk", "tetra", "konserv", "canned")) or _contains_any(
            category_text, ("konserv", "burk", "tetra", "canned")
        ):
            return "chickpeas", "legume", "canned_staple", "canned"
        if _contains_any(text, ("kokt", "kokta", "färdigkokt", "cooked")):
            return "chickpeas", "legume", "cooked_staple", "cooked"
        return "chickpeas", "legume", "dry_staple", "dry"
    if _contains_any(text, ("gula ärter", "gul ärta", "yellow peas")) or (
        set(text.split()) & {"gul", "gula"} and set(text.split()) & {"arta", "artor", "arter"}
    ):
        return "yellow_pea", "legume", "dry_staple", None
    if _contains_any(text, ("gröna ärtor", "grön ärta", "green peas")) or any(
        token in {"artor", "arter"} for token in text.split()
    ):
        product_form = "frozen" if _contains_any(text, ("fryst", "frysta", "frozen")) else "fresh"
        return "peas", "legume", "whole_vegetable", product_form
    if _contains_any(text, ("rotselleri", "celeriac")):
        return "celeriac", "vegetable", "root_vegetable", "fresh"
    if any(
        marker in text for marker in ("bladselleri", "blekselleri", "stjalkselleri")
    ) or _contains_phrase(text, "selleri"):
        return "celery", "vegetable", "stalk_vegetable", "fresh"
    if any(token == "lins" or token.endswith("linser") for token in text.split()):
        if _contains_any(text, ("linssoppa", "linsgryta")):
            return "lentil", "legume", "processed_ready_meal", "prepared"
        if _contains_any(text, ("linschips",)):
            return "lentil", "legume", "snack", "processed"
        canned_name = _contains_any(
            text,
            ("burk", "tetra", "konserv", "canned"),
        )
        cooked_name = _contains_any(
            text,
            ("kokt", "kokta", "färdigkokt", "färdigkokta", "cooked", "ready to eat"),
        )
        canned_category = _contains_any(
            category_text,
            ("konserv", "burk", "tetra", "canned"),
        )
        dry_name = _contains_any(
            text,
            ("torr", "torra", "torkad", "torkade", "okokt", "okokta", "dry", "dried"),
        )
        dry_category = _contains_any(
            category_text,
            (
                "torrvaror",
                "torra baljväxter",
                "torkade baljväxter",
                "dry goods",
                "dried pulses",
            ),
        )
        if canned_name or canned_category:
            return "lentil", "legume", "canned_staple", "canned"
        if cooked_name:
            return "lentil", "legume", "cooked_staple", "cooked"
        if dry_name or dry_category:
            return "lentil", "legume", "dry_staple", "dry"
        return "lentil", "legume", "unknown_lentil_form", "unknown"

    if "vitlok" in text or _contains_phrase(text, "garlic"):
        if any(
            marker in text for marker in ("vitloksbaguette", "vitloksbaguetter")
        ) or _contains_any(text, ("baguette", "baguetter", "vitlöksbröd", "garlic bread")):
            return "garlic", "allium", "bread", "prepared"
        if _contains_any(text, ("aioli", "sås", "dressing", "marinad")):
            return "garlic", "allium", "sauce", "processed"
        if _contains_any(text, ("kryddsmör", "spread")):
            return "garlic", "allium", "spread", "processed"
        if _contains_any(text, ("pulver", "krydda", "seasoning")):
            return "garlic", "allium", "seasoning", "dried"
        if _contains_any(text, ("klyfta", "clove")):
            return "garlic", "allium", "clove", "fresh"
        return "garlic", "allium", "bulb", "fresh"

    cheese_tokens = {"cheddar", "gouda", "mozzarella", "parmesan"}
    tokens = set(text.split())
    cheese_form_markers = (
        "ostbågar",
        "ostchips",
        "ostsås",
        "ostkaka",
        "ostpaj",
    )
    if (
        any(token == "ost" or token.endswith("ost") for token in tokens)
        or tokens & cheese_tokens
        or _contains_any(text, cheese_form_markers)
    ):
        if _contains_any(
            text,
            ("grillost", "grill ost", "halloumi", "grill cheese", "grilling cheese"),
        ):
            return "cheese", "dairy", "grilling_cheese", "grilling"
        if _contains_any(text, ("fetaost", "salladsost", "chèvre", "chevre", "getost")):
            return "cheese", "dairy", "salad_cheese", "specialty"
        if _contains_any(text, ("färskost", "mjukost", "smältost", "cream cheese")):
            return "cheese", "dairy", "cream_cheese", "spreadable"
        if _contains_any(text, ("ostsås", "ost sås", "cheese sauce")):
            return "cheese", "dairy", "cheese_sauce", "processed"
        if _contains_any(text, ("ostbågar", "ostchips", "cheese snack")):
            return "cheese", "dairy", "cheese_flavoured_snack", "processed"
        if _contains_any(text, ("ostkaka", "ostpaj", "potatisgratäng")):
            return "cheese", "dairy", "processed_ready_meal", "prepared"
        for named in cheese_tokens:
            if named in tokens:
                return "cheese", "dairy", named, "cheese"
        return "cheese", "dairy", "hard_cheese", "cheese"

    if _contains_any(text, ("crème fraiche", "creme fraiche")):
        if _contains_any(text, ("potatissallad", "pastasallad")):
            return "creme_fraiche", "dairy", "salad", "prepared"
        if _contains_any(text, ("dressing", "sås")):
            return "creme_fraiche", "dairy", "dressing", "processed"
        if _contains_any(text, ("dipmix", "dippmix")):
            return "creme_fraiche", "dairy", "dip_mix", "processed"
        return "creme_fraiche", "dairy", "dairy_base", "cultured"

    rice_tokens = [
        token
        for token in text.split()
        if token in {"ris", "rice"} or token.endswith(("ris", "rice"))
    ]
    if rice_tokens:
        if _contains_any(
            text,
            (
                "grötris",
                "risgryn",
                "ris gryn",
                "risgröt",
                "ris pudding",
                "pudding rice",
                "rice pudding rice",
            ),
        ):
            return "rice", "grain", "pudding_rice", "grain"
        if _contains_any(text, ("risnudlar", "rice noodles")):
            return "rice", "grain", "rice_noodle", "processed"
        if _contains_any(text, ("rismjöl", "rice flour")):
            return "rice", "grain", "rice_flour", "milled"
        if _contains_any(text, ("risdryck", "rice drink")):
            return "rice", "grain", "rice_drink", "liquid"
        if _contains_any(text, ("riskakor", "rice cakes")):
            return "rice", "grain", "snack", "processed"
        if _contains_any(text, ("blomkålsris",)):
            return "cauliflower", "vegetable", "processed_ready_meal", "riced"
        return "rice", "grain", "cooking_staple", "grain"

    return None


def _visible_generic_identity(name_text: str, canonical: str) -> bool:
    aliases = CANONICAL_ALIASES.get(canonical, (canonical,))
    tokens = name_text.split()
    for alias in aliases:
        normalized = _search_text(alias)
        if _contains_phrase(name_text, normalized):
            return True
        # Swedish product identities are commonly compounds
        # (``mellanmjölk``, ``matlagningsgrädde``, ``spetspaprika``).
        # Only accept a sufficiently specific one-token suffix here; prefix
        # matches such as ``potatissallad`` remain metadata-only and are not
        # promoted to a safe food identity.
        if (
            " " not in normalized
            and len(normalized) >= 4
            and any(token.endswith(normalized) for token in tokens)
        ):
            return True
    return False


def _structured_red_lentils_have_dry_package_evidence(
    product: Any,
    *,
    explicit_food_raw: Any,
    name_text: str,
    category_text: str,
    prepared_form: str | None,
) -> bool:
    """Conservatively resolve a source-explicit red-lentil fixed package.

    Some full catalogues identify the food precisely as ``red_lentils`` but
    omit a dry/cooked role and use a broad pantry category. A positive fixed
    gram package is sufficient to default this *specific* source identity to
    dry only when no visible preserved, cooked, or prepared signal conflicts.
    Generic ``lentil`` metadata remains ambiguous by design.
    """

    source_food = _search_text(str(explicit_food_raw or "")).replace(" ", "_")
    if source_food != "red_lentils" or prepared_form is not None:
        return False

    visible_text = f"{name_text} {category_text}".strip()
    if _contains_any(
        visible_text,
        (
            "burk",
            "tetra",
            "konserv",
            "canned",
            "kokt",
            "kokta",
            "färdigkokt",
            "färdigkokta",
            "cooked",
            "ready to eat",
            "soppa",
            "gryta",
            "färdigrätt",
            "prepared",
        ),
    ):
        return False

    sale_model = _value(product, "sale_model")
    sale_model_value = getattr(sale_model, "value", sale_model)
    quantity_confidence = _value(product, "quantity_confidence")
    quantity_confidence_value = getattr(
        quantity_confidence,
        "value",
        quantity_confidence,
    )
    package_quantity = _value(product, "package_quantity")
    package_unit = str(_value(product, "package_unit", "") or "").casefold()
    return (
        sale_model_value == "fixed_package"
        and isinstance(package_quantity, int | float)
        and not isinstance(package_quantity, bool)
        and package_quantity > 0
        and package_unit == "g"
        and quantity_confidence_value in {"exact", "derived", "estimated"}
    )


def _requires_red_lentil_identity(canonical_name: str) -> bool:
    requested = _search_text(canonical_name).replace(" ", "_")
    return requested in {
        "red_lentils",
        "roda_linser",
        "rod_lins",
        "linser_roda",
        "lins_rod",
    }


def evaluate_product_semantics(
    canonical_name: str,
    product: Any,
) -> SemanticMatchResult:
    """Apply food, role, form and explicit-exclusion gates in that order."""

    requirement = semantic_requirement(canonical_name)
    if requirement.canonical_name in _CULINARY_LABELS:
        return _culinary_label_match(requirement.canonical_name, product)
    # Specific culinary identities absent from the legacy dinner taxonomy.
    # Full product labels are required; a component/flavour word cannot match.
    if requirement.canonical_name in {"yoghurt naturell", "paprikapulver", "keso", "kapris"}:
        label = _search_text(str(_value(product, "name", "")))
        if requirement.canonical_name == "paprikapulver":
            compatible = bool(re.fullmatch(r"paprikapulver(?: milt| mild| stark| rokt| eko| burk| pase)*", label))
            role, form, food = "single_spice", "dry", "paprikapulver"
        elif requirement.canonical_name == "keso":
            compatible = bool(re.fullmatch(
                r"(?:laktosfri )?(?:keso(?: cottage cheese)?|cottage cheese)(?: naturell| mini| supermini| laktosfri| ekologisk| eko| [0-9]+)*", label
            ))
            role, form, food = "plain_cottage_cheese", "as_sold", "keso"
        elif requirement.canonical_name == "kapris":
            compatible = bool(re.fullmatch(r"kapris(?: sma| medelstora| fina| non pareilles| i lag)*", label))
            role, form, food = "capers", "preserved", "kapris"
        else:
            compatible = bool(re.fullmatch(
                r"(?:(?:mild|grekisk|turkisk|laktosfri|latt|naturell) )*yoghurt(?: (?:naturell|mild|latt|laktosfri|eko|ekologisk|[0-9]+))*", label
            ) and "naturell" in label)
            role, form, food = "plain_yoghurt", "as_sold", "yoghurt naturell"
        return SemanticMatchResult(
            compatible=compatible,
            confidence=SemanticConfidence.HIGH if compatible else SemanticConfidence.REJECTED,
            canonical_food=food, product_role=role, product_form=form,
            evidence=["exact_plain_culinary_product_label" if compatible else "different_culinary_product_or_flavour"],
        )
    requires_red_lentils = _requires_red_lentil_identity(canonical_name)
    name = str(_value(product, "name", _value(product, "product_name", "")))
    name_text = _search_text(name)
    category_text = _search_text(str(_value(product, "category", "") or ""))
    prepared_form = _classify_prepared_form(name_text)
    if prepared_form is None and _is_filled_dough_dish(name_text):
        prepared_form = "ready_meal"
    if prepared_form == "mixture" and _is_pepper_colour_mix(name_text):
        prepared_form = None
    # A specific compound product-class label is stronger than a flavour in
    # a short name. Broad navigation such as "Ost & kex" is not such proof.
    if prepared_form is None and _contains_any(category_text, ("ostkex", "smörgåskex")):
        prepared_form = _classify_prepared_form(category_text)
    if prepared_form is None and requirement.canonical_name in _FRESH_PRODUCE_CANONICALS:
        prepared_form = _classify_produce_category_form(category_text)
    if (
        prepared_form is None
        and requirement.canonical_name != "pasta"
        and _contains_phrase(name_text, "pasta")
    ):
        prepared_form = "pasta_dish"
    evidence: list[str] = []

    # Narrow, source-proven synonym only. Broad alias matching must not turn
    # specialty flour, mixes, or flour as a component into plain wheat flour.
    if requirement.canonical_name == "vetemjöl" and not re.fullmatch(
        r"(?:karnvetemjol|vetemjol)(?: \d+(?: \d+)? (?:g|kg))?", name_text
    ):
        return SemanticMatchResult(
            compatible=False, confidence=SemanticConfidence.REJECTED,
            evidence=["plain_wheat_flour_identity_unverified"],
        )

    # Whole-word exclusions miss Swedish compounds. These are distinct foods,
    # not interchangeable defaults for an ordinary milk/cheese requirement.
    special_dairy = (
        requirement.canonical_name == "mjölk"
        and any(word in name_text for word in ("getmjolk", "farmjolk", "goat milk", "sheep milk"))
    ) or (
        requirement.canonical_name == "ost"
        and any(word in name_text for word in ("mogelost", "blue cheese", "organic blue", "brie", "camembert", "chevre"))
    )
    if special_dairy:
        return SemanticMatchResult(
            compatible=False, confidence=SemanticConfidence.REJECTED,
            evidence=["distinct_dairy_variant_requires_explicit_identity"],
        )

    if is_non_human_food(name, str(_value(product, "category", "") or "")):
        return SemanticMatchResult(
            compatible=False,
            confidence=SemanticConfidence.REJECTED,
            evidence=["excluded_audience:non_human_food"],
        )

    primary_identity = _infer_primary_product_identity(name_text, category_text)
    special_identity = _infer_special_identity(name_text, category_text)
    # Existing role/form inference is more specific when both classifiers
    # agree on the food (for example cheese sauce versus generic cheese). A
    # different dominant product class still wins over a flavour/component:
    # ``Cambozola Vitlök`` is cheese, not a garlic bulb.
    if (
        primary_identity is not None
        and special_identity is not None
        and primary_identity[0] == special_identity[0]
    ):
        inferred = special_identity
    else:
        inferred = primary_identity or special_identity
    explicit_food_raw = _value(product, "canonical_food")
    explicit_food = _normalize_food_identity(explicit_food_raw)
    explicit_family = _value(product, "food_family")
    explicit_role = _value(product, "product_role")
    explicit_form = _value(product, "product_form")
    component_position = _component_position(requirement, name_text)

    # A visible primary target ("Pizza med kyckling", target pizza) outranks
    # inference from a later ingredient. Conversely, when the target occurs
    # only after the cue, it is not the purchasable primary product.
    if (
        component_position == "primary"
        and primary_identity is None
        and inferred is not None
        and inferred[0] != requirement.canonical_food
    ):
        inferred = None

    if (
        component_position == "secondary"
        # A cue-position match is the strongest signal that the requested
        # ingredient is merely a component/flavour of the purchasable item.
        # Keep the more specific fermented/pickled identity when available;
        # all other generic composite forms still remain secondary matches.
        and prepared_form not in {"fermented", "pickled"}
        and (inferred is None or inferred[0] == requirement.canonical_food)
    ):
        inferred_food = inferred[0] if inferred is not None else explicit_food
        inferred_family = inferred[1] if inferred is not None else explicit_family
        return SemanticMatchResult(
            compatible=False,
            canonical_food=inferred_food,
            food_family=str(inferred_family) if inferred_family else requirement.food_family,
            product_role="secondary_component",
            product_form="secondary_component",
            confidence=SemanticConfidence.REJECTED,
            evidence=["secondary_component_after_cue"],
        )

    if inferred is not None:
        product_food, product_family, product_role, product_form = inferred
        evidence.append(f"visible_food:{product_food}")
        if primary_identity is not None:
            evidence.append(f"primary_product_identity:{product_food}")
        if product_role:
            evidence.append(f"visible_role:{product_role}")
    else:
        product_food = explicit_food
        product_family = str(explicit_family) if explicit_family else None
        product_role = str(explicit_role) if explicit_role else None
        product_form = str(explicit_form) if explicit_form else None

    # Visible identity outranks provider metadata. Structured values only fill
    # gaps, never overwrite an explicit organ/prepared-form signal in the name.
    if product_food is None and explicit_food:
        product_food = explicit_food
        evidence.append(f"structured_food:{product_food}")
    if product_family is None and explicit_family:
        product_family = str(explicit_family)
    if product_role is None and explicit_role:
        product_role = str(explicit_role)
        evidence.append(f"structured_role:{product_role}")
    if product_form is None and explicit_form:
        product_form = str(explicit_form)
    if (
        product_food == "lentil"
        and product_role == "unknown_lentil_form"
        and product_form == "unknown"
        and _structured_red_lentils_have_dry_package_evidence(
            product,
            explicit_food_raw=explicit_food_raw,
            name_text=name_text,
            category_text=category_text,
            prepared_form=prepared_form,
        )
    ):
        product_role = "dry_staple"
        product_form = "dry"
        evidence.append("structured_red_lentils_dry_package")
    if prepared_form is not None and requirement.canonical_name in _RAW_RECIPE_CANONICALS:
        # Product-name evidence outranks provider metadata.  A search hit for
        # a raw ingredient may carry the right canonical metadata while still
        # visibly being a pie, soup, burger or other prepared dish.
        if product_food is None or product_food == requirement.canonical_food:
            product_form = prepared_form
            if product_role not in _KNOWN_PROCESSED_ROLES:
                product_role = _PREPARED_ROLE_BY_FORM[prepared_form]
        elif product_food == "vegetable_mixture":
            # The same item is a valid mixture when explicitly requested, but
            # remains an ambiguous substitute for one raw component.
            product_role = "ambiguous_mixture"
        evidence.append(f"visible_prepared_form:{prepared_form}")

    declared = _value(product, "canonical_name")
    declared_canonical = canonicalize_ingredient_name(str(declared)) if declared else None
    target_rule = _RULES.get(requirement.canonical_name)
    visible_identity = (
        any(_identity_term_visible(name_text, term) for term in target_rule.identity_terms)
        if target_rule is not None
        else _visible_generic_identity(name_text, requirement.canonical_name)
    )

    raw_default = _RAW_VISIBLE_DEFAULTS.get(requirement.canonical_name)
    if (
        prepared_form is None
        and visible_identity
        and product_role is None
        and raw_default is not None
    ):
        product_role, product_form = raw_default
        if _contains_any(name_text, ("fryst", "frozen")):
            product_form = "frozen"
        evidence.extend((f"visible_role:{product_role}", f"visible_raw_form:{product_form}"))

    if product_food is None and visible_identity:
        product_food = requirement.canonical_food
        product_family = product_family or requirement.food_family
        evidence.append(f"visible_food:{product_food}")
    elif product_food is None and declared_canonical == requirement.canonical_name:
        product_food = requirement.canonical_food
        product_family = product_family or requirement.food_family
        evidence.append("declared_canonical_only")

    if requires_red_lentils:
        source_food = _search_text(str(explicit_food_raw or "")).replace(" ", "_")
        visible_red = _contains_any(
            name_text,
            ("röda linser", "röd lins", "linser röda", "lins röd"),
        )
        visible_green = _contains_any(
            name_text,
            ("gröna linser", "grön lins", "linser gröna", "lins grön"),
        )
        if visible_green or not (visible_red or source_food == "red_lentils"):
            return SemanticMatchResult(
                compatible=False,
                canonical_food=product_food,
                food_family=product_family,
                product_role=product_role,
                product_form=product_form,
                confidence=SemanticConfidence.REJECTED,
                evidence=[*evidence, "variant_mismatch:requires_red_lentils"],
            )

    if product_food is not None and product_food != requirement.canonical_food:
        return SemanticMatchResult(
            compatible=False,
            canonical_food=product_food,
            food_family=product_family,
            product_role=product_role,
            product_form=product_form,
            confidence=SemanticConfidence.REJECTED,
            evidence=[*evidence, f"food_mismatch:requires_{requirement.canonical_food}"],
        )

    if product_role in requirement.excluded_roles:
        return SemanticMatchResult(
            compatible=False,
            canonical_food=product_food,
            food_family=product_family,
            product_role=product_role,
            product_form=product_form,
            confidence=SemanticConfidence.REJECTED,
            evidence=[*evidence, f"excluded_role:{product_role}"],
        )
    if requirement.allowed_roles and product_role not in requirement.allowed_roles:
        return SemanticMatchResult(
            compatible=False,
            canonical_food=product_food,
            food_family=product_family,
            product_role=product_role,
            product_form=product_form,
            confidence=SemanticConfidence.REJECTED,
            evidence=[*evidence, f"role_mismatch:requires_{sorted(requirement.allowed_roles)}"],
        )
    if prepared_form is not None and requirement.canonical_name in _RAW_RECIPE_CANONICALS:
        return SemanticMatchResult(
            compatible=False,
            canonical_food=product_food,
            food_family=product_family,
            product_role=product_role,
            product_form=product_form,
            confidence=SemanticConfidence.REJECTED,
            evidence=[*evidence, f"excluded_prepared_form:{prepared_form}"],
        )
    if product_form in requirement.excluded_forms:
        return SemanticMatchResult(
            compatible=False,
            canonical_food=product_food,
            food_family=product_family,
            product_role=product_role,
            product_form=product_form,
            confidence=SemanticConfidence.REJECTED,
            evidence=[*evidence, f"excluded_form:{product_form}"],
        )

    visible_text = f"{name_text} {category_text}".strip()
    excluded_phrase = next(
        (
            phrase
            for phrase in STRICT_EXCLUSIONS.get(requirement.canonical_name, ())
            # A different food in broad navigation is not this product's
            # identity. Preserve category exclusions for preparation/mixtures;
            # only explicit alternative food identities defer to the name.
            if _contains_phrase(
                name_text if visible_identity
                and _infer_special_identity(_search_text(phrase)) is not None
                and _classify_prepared_form(_search_text(phrase)) is None
                else visible_text, phrase
            )
        ),
        None,
    )
    if excluded_phrase is not None:
        return SemanticMatchResult(
            compatible=False,
            canonical_food=product_food,
            food_family=product_family,
            product_role=product_role,
            product_form=product_form,
            confidence=SemanticConfidence.REJECTED,
            evidence=[*evidence, f"explicit_exclusion:{_search_text(excluded_phrase)}"],
        )

    if product_food != requirement.canonical_food:
        return SemanticMatchResult(
            compatible=False,
            canonical_food=product_food,
            food_family=product_family,
            product_role=product_role,
            product_form=product_form,
            confidence=SemanticConfidence.LOW,
            evidence=[*evidence, "missing_food_identity"],
        )

    supplied_confidence = _value(product, "semantic_confidence", SemanticConfidence.LOW)
    if (
        explicit_food == requirement.canonical_food
        and explicit_role == product_role
        and supplied_confidence == SemanticConfidence.EXACT
    ):
        confidence = SemanticConfidence.EXACT
        evidence.append("structured_semantics_match")
    elif visible_identity or inferred is not None:
        confidence = SemanticConfidence.HIGH
        evidence.append("visible_identity_match")
    else:
        # Search-query canonical metadata without visible product evidence is
        # deliberately only medium. Production defaults reject it.
        confidence = SemanticConfidence.MEDIUM
        evidence.append("metadata_only_match")

    return SemanticMatchResult(
        compatible=True,
        canonical_food=product_food,
        food_family=product_family,
        product_role=product_role,
        product_form=product_form,
        confidence=confidence,
        evidence=evidence,
    )


__all__ = [
    "STRICT_EXCLUSIONS",
    "SemanticMatchResult",
    "SemanticRequirement",
    "evaluate_product_semantics",
    "has_semantic_rule",
    "is_non_human_food",
    "semantic_requirement",
]
