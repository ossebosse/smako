"""Liquid vegetable stock concentrate (Touch of Taste grönsaksfond).

Recipes ask for millilitres of the concentrate itself; the water is a separate
process step. Stores sell several stock products that look alike: cubes and
powder (sold by weight or by the volume they make), jelly pots, and liquid
concentrate. Only a liquid concentrate whose manufacturer states how much to
dilute it is accepted here, because only then can the concentrate's nutrition
be derived from the manufacturer's declaration, which is per 100 ml diluted.

Owner request 2026-11-26. Per 100 ml concentrate:
  energy = declared kcal per 100 ml diluted x (diluted ml / concentrate ml)
  carbohydrate carries that energy (kcal / 4); protein and fat are declared
  as "under 0.5 g" per 100 ml diluted and are counted as 0.
For 35 ml concentrate in a four-portion dish this is about 2 kcal per portion.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

POLICY_VERSION = "stock-concentrate-dilution-v1"
_PATH = Path(__file__).parents[1] / "data/nutrition/touch-of-taste-fond-20261126.json"
_BRAND = re.compile(r"\b(?:touch of taste|bong)\b")
_LABEL = re.compile(r"(?:(?:bong )?touch of taste )?(ekologisk |eko )?grönsaksfond(?: (eko|ekologisk|ekologiskt))?(?: \d+ ?ml)?")
_NOT_CONCENTRATE = re.compile(r"buljong|tärning|pulver|gelé|pack|portion|färdig|drickfärdig")


@lru_cache(maxsize=1)
def data():
    return json.loads(_PATH.read_bytes())


def identity(product, fact=None):
    """The reviewed food key for a liquid Touch of Taste vegetable concentrate, or None."""
    label = " ".join(product.name.casefold().split())
    brand = " ".join((getattr(product, "brand", None) or "").casefold().split())
    if not (_BRAND.search(brand) or _BRAND.search(label)) or _NOT_CONCENTRATE.search(label):
        return None
    match = _LABEL.fullmatch(label)
    if match is None or product.package_unit != "ml" or not 100 <= (product.package_quantity or 0) <= 1000:
        return None
    composition = " ".join(fact.ingredients).casefold() if fact and fact.ingredients else ""
    if composition and not re.match(r"\W*(?:ingredienser:\s*)?vatten,\s*salt\b", composition):
        return None
    return "ekologisk grönsaksfond" if (match.group(1) or match.group(2)) else "grönsaksfond"


def dilution_factor():
    dose = data()["dose"]
    return (dose["concentrate_ml"] + dose["liquid_ml"]) / dose["concentrate_ml"]


@lru_cache(maxsize=4)
def _evidence(key):
    from app.services.nutrition_reference import NutritionEvidence

    source, row = data(), data()["foods"][key]
    factor = dilution_factor()
    kcal = round(row["kcal"] * factor, 2)
    nutrition = {"kcal": kcal, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": round(kcal / 4, 2)}
    proof = {"kind": "manufacturer_dilution_estimate", "policy": POLICY_VERSION, "source": source["attribution"],
             "source_url": row["source_url"], "declaration_basis": row["declaration_basis"],
             "declared_per_100_ml_diluted": {k: row[k] for k in ("kcal", "protein_g", "fat_g", "carbs_g")},
             "dose": source["dose"], "dilution_factor": round(factor, 4), "retrieved_at": source["retrieved_at"],
             "operation": "declared_kcal_per_100_ml_diluted * dilution_factor; carbs = kcal / 4; "
                          "protein and fat declared under 0.5 g counted as 0"}
    return NutritionEvidence(
        source=source["attribution"], source_product_id=f"touch-of-taste:{key}", nutrition=nutrition,
        nutrition_unit="ml", evidence_kind="manufacturer_dilution_estimate", ingredient="grönsaksfond",
        nutrition_basis=(f"Uppskattat per 100 ml koncentrat: tillverkarens deklaration per 100 ml utspädd fond "
                         f"× {factor:.1f} enligt tillverkarens dosering (1,5 msk till 5 dl vätska)."),
        field_sources={f"nutrition.{k}": (proof,) for k in nutrition})


def evidence(product, fact=None):
    key = identity(product, fact)
    return None if key is None else _evidence(key)
