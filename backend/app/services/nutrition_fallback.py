"""Generic nutrition for a recipe input whose bought product has no usable table.

Owner report 2026-11-22: in a five-dinner plan four dinners showed no
nutrition. Each lacked one input with usable values: loose potatoes, small
eggs, cherry tomatoes, frozen basil, canned tuna, lamb fillet... One missing
input hid the whole dinner's values.

For the shown (informational) values only, such an input now uses
Livsmedelsverket's generic reference for that food, in the recipe's input form
(the same calculation as the person's own staples, pantry_evidence). The plan
marks the values as estimated. Nutrition limits still need every input's own
qualified evidence; this module is never used for them.
"""

from __future__ import annotations

import re

from app.services.ingredient_normalizer import canonicalize_ingredient_name

# A product of these kinds is a different food than the plain ingredient.
_PROCESSED = re.compile(r"panerad|marinerad|grillad|rökt|gravad|kryddad|färdigrätt|röra\b|bearnaise|gratäng")
_DRIED = re.compile(r"pulver|tork|mos\b|flingor")


def _tomato(label):
    return 4937 if re.search(r"körsbär|cocktail|plommon|snack", label) else 364


def _paprika(label):
    for colour, identity in (("röd", 351), ("grön", 350), ("gul", 381)):
        if re.search(rf"\b{colour}\b", label):
            return identity
    return 392


# Recipe ingredient (canonical) -> SLV reference, by the bought product's label.
_RULES = {
    "potatis": lambda label: None if "söt" in label or _DRIED.search(label) else 4457,
    "tomat": _tomato,
    "körsbärstomater": lambda label: 4937,
    "paprika": _paprika,
    "kyckling": lambda label: None if re.search(r"lår|vinge|klubb|hel kyckling|helkyckling|kyckling hel", label) else 1173,
    "lammkött": lambda label: 5067,
    "lamm": lambda label: 5067,
    "tonfisk": lambda label: 1275 if "olja" in label else 1278,
    "sardiner": lambda label: 1272 if "tomat" in label else 1271,
    "mozzarella": lambda label: 2255,
    # The reviewed olive reference is black olives (recipe_ingredient_references).
    "oliver": lambda label: 402 if "svart" in label else None,
    "parmesan": lambda label: 103,
    "bakpulver": lambda label: 1981,
    "ägg": lambda label: 1225,
    "koriander": lambda label: None if _DRIED.search(label) else 7193,
    "basilika": lambda label: None if _DRIED.search(label) else 379,
}


def fallback_identity(name, product_label=""):
    """The generic reference for this recipe input, or None."""
    from app.services.nutrition_reference import MAPPINGS

    canonical = canonicalize_ingredient_name(name)
    label = " ".join(str(product_label or "").casefold().split())
    if label and _PROCESSED.search(label):
        return None
    rule = _RULES.get(canonical)
    if rule is not None:
        identity = rule(label)
        return identity if identity in MAPPINGS else None
    # Otherwise only a reference reviewed for exactly this ingredient name.
    # A dried product is not the raw food the reference describes.
    return next((identity for identity, (ingredient, state) in MAPPINGS.items()
                 if canonicalize_ingredient_name(ingredient) == canonical
                 and not (state.startswith("raw") and _DRIED.search(label))), None)


def fallback_evidence(recipe, name, product_label=""):
    """Reference evidence in the recipe's input form; None when the forms differ."""
    if recipe is None or recipe.preparation is None:
        return None
    identity = fallback_identity(name, product_label)
    if identity is None:
        return None
    from app.services.recipe_preparation import pantry_evidence

    try:
        return pantry_evidence(recipe, name, identity)
    except (KeyError, ValueError, TypeError):
        return None
