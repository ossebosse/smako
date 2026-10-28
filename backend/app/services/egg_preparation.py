"""Reviewed egg separation within the existing purchase and inventory paths.

Only an issued recipe's explicit method operand authorizes preparation. The
estimate plans edible whole egg; physical outputs are booked only when weighed.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name

METHOD = "hen_egg_separation_estimate_v1"
OPERAND = "prepare:" + METHOD
COMPONENTS = frozenset({"äggula", "äggvita"})


@lru_cache(maxsize=1)
def reference():
    return json.loads((Path(__file__).parents[1] / "data/nutrition/egg-separation-v1.json").read_bytes())


def component(recipe, name):
    if recipe is None or recipe.design is None or not name.casefold().startswith(("äggula", "äggvita")):
        return None
    name = canonicalize_ingredient_name(name)
    if name not in COMPONENTS:
        return None
    operand = next((i for i in recipe.ingredients if i.canonical_name == name), None)
    if (operand is None or operand.unit != "g" or operand.form != "raw_edible"
            or OPERAND not in (operand.product_requirements or ())):
        return None
    return name


def edible_input(yolk=0, white=0, whole=0):
    return whole + max(yolk * 3, white * 1.5)


def plain_source(product, fact):
    from app.services.official_product_facts import _mass_blocking, is_plain_shell_egg

    return bool(fact and not _mass_blocking(fact.conflicts)
                and is_plain_shell_egg(product.name, product.brand, fact.ingredients))


def nutrition(name, product_id):
    from app.services.nutrition_reference import NutritionEvidence

    data = reference()
    return NutritionEvidence(
        source=METHOD, source_product_id=product_id,
        nutrition=dict(data["macro_per_100_g"][name]), nutrition_basis="per_100_g",
        ingredient=name, evidence_kind="reviewed_raw_component_population_estimate",
        field_sources={"nutrition": [{**data["source"], "method": METHOD,
            "scope": data["source_scope"], "form": "raw_edible",
            "not_measured_retention": True}]},
    )
