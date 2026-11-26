"""Generic nutrition for loose foods whose product has no table (owner decision 2026-11-25).

Meat sold by weight (grytbitar, karré, högrev, lammstek...) and loose
vegetables and herbs (sallad, salladslök, rädisor, mynta...) usually publish
no nutrition table. Before this, a dinner with such an input could never be
planned under a nutrition limit. The owner decided that Smako uses a public
food composition reference for them, also for limits: Livsmedelsverket's
database, Matvaretabellen where Livsmedelsverket has no entry (salladslök,
schalottenlök, dried chili, curry powder and paste, capers, white pepper,
mustard seed) and USDA FoodData Central for lemongrass. Garam masala uses
Matvaretabellen's ground curry powder, the nearest spice blend. The plan marks
these values as estimated.

Only a plain food qualifies: a product with its own table, a contradictory
table, or a label that says it is a different food (marinated, breaded,
smoked, seasoned, cooked, ready-made) gets nothing here.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name

POLICY_VERSION = "loose-food-reference-20261125"
_DATA = Path(__file__).parents[1] / "data/nutrition"
_OTHER_FOOD = re.compile(
    r"marinerad|panerad|grillad|rökt|gravad|kryddad|färdigrätt|färdig|röra\b|sås\b|dressing|soppa|gratäng|kokt|stekt|"
    r"chips|burgare|korv|bacon|kebab|pulled|sous vide|tillagad|kattmat|hundmat|blötmat|pastej|baguette")


def _first(label, rules, default):
    for pattern, identity in rules:
        if re.search(pattern, label):
            return identity
    return default


_BEEF = ((r"högrev", 953), (r"grytbit", 961), (r"ryggbiff|biff", 946), (r"entrec", 960), (r"innanlår", 954),
         (r"fransyska", 950), (r"ytterlår", 959), (r"rostbiff", 957), (r"oxfilé|filé", 949), (r"flank", 1013),
         (r"bringa", 947))
_PORK = ((r"karré", 978), (r"fläskfilé|ytterfilé|innerfilé|filé", 970), (r"kotlett", 971), (r"grytbit", 977),
         (r"bog", 969), (r"innanlår|skinka", 988), (r"sidfläsk|sida", 985))
_LAMB = ((r"stek|fransyska|innanlår", 924), (r"grytbit", 5068), (r"kotlett|racks?|rack", 921), (r"rygg|hals", 923))
_FISH = ((r"sej", 1202), (r"kolja", 1237), (r"pollock|alaska", 4615), (r"torsk", 1246), (r"lax", 1255))
_SALAD = ((r"isberg", 340), (r"roman|romaine", 2559), (r"rucc?ola|rukola", 2561))

# Recipe ingredient (canonical) -> reference, chosen by the bought product's label.
_RULES = {
    "nötkött": lambda l: _first(l, _BEEF, 5066),
    "högrev": lambda l: 953,
    "nötinnanlår": lambda l: 954,
    "nötstek": lambda l: _first(l, _BEEF, 950),
    "nötkött för snabbstekning": lambda l: _first(l, _BEEF, 946),
    "fläskkött": lambda l: _first(l, _PORK, 977),
    "fläskkarré": lambda l: 978,
    "lammkött": lambda l: _first(l, _LAMB, 5067),
    "benfri lammstek": lambda l: 924,
    "kyckling": lambda l: 1174 if re.search(r"lår", l) else (1173 if re.search(r"bröst|filé", l) else 1164),
    "kycklinglever": lambda l: 1453,
    "fisk": lambda l: _first(l, _FISH, 1246),
    "makrill": lambda l: 1260,
    "räkor": lambda l: 1395,
    "palsternacka": lambda l: 290,
    "rotselleri": lambda l: 292,
    "rädisa": lambda l: 293,
    "fänkål": lambda l: 336,
    "pumpa": lambda l: 353,
    "purjolök": lambda l: 6806 if re.search(r"fryst|frysta", l) else 354,
    "sallad": lambda l: _first(l, _SALAD, 3938),
    "rucola": lambda l: 2561,
    "gräslök": lambda l: 378,
    "grönkål": lambda l: 337,
    "rödkål": lambda l: 355,
    "pak choi": lambda l: 7192,
    "haricots verts": lambda l: 332 if re.search(r"fryst|frysta", l) else 331,
    "grön chili": lambda l: 380,
    "jalapeño": lambda l: 380,
    "chili": lambda l: 380,
    "avokado": lambda l: 320,
    "ananas": lambda l: 550,
    "majskolv": lambda l: 345,
    "sockerärtor": lambda l: 359,
    "böngroddar": lambda l: 329,
    "mangold": lambda l: 4942,
    "mynta": lambda l: 7194,
    "salladslök": lambda l: "mvt:salladslök",
    "schalottenlök": lambda l: "mvt:schalottenlök",
    "chiliflakes": lambda l: "mvt:chilipulver",
    "anchochili": lambda l: "mvt:chilipulver",
    "garam masala": lambda l: "mvt:karri",
    "kapris": lambda l: "mvt:kapris",
    "röd currypasta": lambda l: "mvt:currypasta",
    "vitpeppar": lambda l: "mvt:vitpeppar",
    "senapsfrön": lambda l: "mvt:senapsfrön",
    "citrongräs": lambda l: "usda:citrongräs",
    "vitt matlagningsvin": lambda l: "mvt:vitt vin",
    "vitt vin": lambda l: "mvt:vitt vin",
    "rött matlagningsvin": lambda l: "mvt:rött vin",
    "rött vin": lambda l: "mvt:rött vin",
    "balsamvinäger": lambda l: "mvt:balsamvinäger",
    "breda risnudlar": lambda l: 4447,
    "risvermicelli": lambda l: 4447,
    "runda risnudlar": lambda l: 4447,
    "kornris": lambda l: 705,
    "korngryn": lambda l: 705,
    "sardeller": lambda l: 1270,
    "bambuskott": lambda l: 393,
    "surkål": lambda l: 406,
    "saltgurka": lambda l: 490,
    "bröd": lambda l: _bread(l),
    "vattenkastanjer": lambda l: 4042,
    "tonfisk": lambda l: 1275 if "olja" in l else 1278,
    "sardiner": lambda l: 1272 if "tomat" in l else 1271,
    "mozzarella": lambda l: 2255,
    "parmesan": lambda l: 103,
}
# The recipe input form each non-SLV entry describes.
_EXTERNAL_FORMS = {"salladslök": "raw_edible", "schalottenlök": "raw_edible", "chilipulver": "dry", "karri": "dry",
                   "kapris": "preserved_drained", "currypasta": "as_sold", "vitpeppar": "dry", "senapsfrön": "dry",
                   "citrongräs": "as_sold", "ostronsås": "as_sold", "vitt vin": "as_sold", "rött vin": "as_sold", "balsamvinäger": "as_sold"}


_NOT_BREAD = re.compile(r"knäcke|skorpa|skorpor|\bkex|\brån\b|krutong|ströbröd|glutenfri|kanel|bulle|croissant|"
                        r"tårta|sockerkaka|mjukkaka|söt|majs|polar|brödmix|bröd ?mix")


def _bread(label):
    """A plain bread or flatbread by its label; Owner request 2026-11-26."""
    if _NOT_BREAD.search(label):
        return None
    for pattern, ident in ((r"pita", 193), (r"naa?n|nanbröd|naanbröd", 202), (r"hamburger|burgerbröd", 3818),
                           (r"surdeg|levain", 6084), (r"baguette", 200), (r"ciabatta|focaccia", 198),
                           (r"tunnbröd", 217), (r"tortilla|wrap", 5974), (r"formfranska|rostbröd|toast", 3791),
                           (r"grov|fullkorn|råg", 3794), (r"limpa", 3795)):
        if re.search(pattern, label):
            return ident
    return 202 if re.search(r"bröd|fralla|franska|bagel", label) else None


def identity(name, product_label):
    """The reference for this recipe input and bought product, or None."""
    label = " ".join(str(product_label or "").casefold().split())
    canonical = canonicalize_ingredient_name(name)
    if canonical == "ostronsås":
        # The sauce itself; the general filter would read "sås" as another dish.
        return "usda:ostronsås" if re.search(r"ostronsås|oyster sauce", label) and not _OTHER_FOOD.search(
            label.replace("ostronsås", "")) else None
    if _OTHER_FOOD.search(label):
        return None
    rule = _RULES.get(canonical)
    return rule(label) if rule else None


_FILES = {"mvt": "matvaretabellen-20261125-loose.json", "usda": "usda-20261125-loose.json"}


@lru_cache(maxsize=4)
def _external(prefix):
    return json.loads((_DATA / _FILES[prefix]).read_bytes())


@lru_cache(maxsize=64)
def _external_evidence(prefix, key):
    from app.services.nutrition_reference import NutritionEvidence

    source = _external(prefix)
    row = source["foods"][key]
    proof = {"kind": "generic_reference", "policy": POLICY_VERSION, "food_id": row["food_id"],
             "description": row["description"], "source_url": row["source_url"],
             "acquisition": row.get("acquisition", source.get("acquisition")), "original_values": row["original_values"],
             "source": source["attribution"]}
    return NutritionEvidence(source=source["attribution"], source_product_id=row["food_id"],
                             nutrition=dict(row["nutrition"]),
                             nutrition_basis=row["description"] + "; generiskt referensvärde per 100 g, inte produktdeklaration.",
                             field_sources={f"nutrition.{k}": (proof,) for k in row["nutrition"]}, ingredient=key)


def incomplete_table(fact):
    """A product table that lacks one of the four macros counts as no table here."""
    return bool(fact and fact.nutrition and not {"kcal", "protein_g", "fat_g", "carbs_g"} <= fact.nutrition.keys())


def evidence(product, name, fact, form):
    """Unwrapped per-100 g evidence for a plain loose food, or None.

    A preserve's own table may describe the contents with their liquid, so for
    drained grams the generic drained reference is used even when it has one.
    """
    own_table = fact and fact.nutrition and not incomplete_table(fact)
    drained = form in {"preserved_drained", "cooked_drained"}
    if fact and ((fact.conflicts and not drained) or (own_table and not drained)):
        return None
    ident = identity(name, product.name)
    if ident is None:
        return None
    if isinstance(ident, str):
        prefix, key = ident.split(":", 1)
        return _external_evidence(prefix, key) if _EXTERNAL_FORMS.get(key) == form else None
    from app.services.nutrition_reference import MAPPINGS, reference_evidence

    state = MAPPINGS.get(ident, (None, None))[1]
    compatible = {"raw_edible": {"raw", "raw_skinless_breast", "raw_cod", "raw_farmed"},
                  "as_sold": {"frozen", "ready"}, "dry": {"dry"}, "cooked_drained": {"drained"},
                  "preserved_drained": {"preserved_drained", "drained"}}
    if state not in compatible.get(form, set()):
        return None
    return reference_evidence(ident)


def volume_evidence(product, name, fact):
    """Per-100 ml evidence for a plain liquid with a published weight per dl, or None."""
    if fact and (fact.conflicts or (fact.nutrition and not incomplete_table(fact))):
        return None
    ident = identity(name, product.name)
    if not isinstance(ident, str) or not ident.startswith("mvt:"):
        return None
    key = ident.split(":", 1)[1]
    row = _external("mvt").get("density", {}).get(key)
    if row is None or _EXTERNAL_FORMS.get(key) != "as_sold":
        return None
    if row["unit"] != "g/ml" or not 0 < row["value"] < 2:
        raise ValueError("Invalid reviewed density")
    from dataclasses import replace

    base = _external_evidence("mvt", key)
    transformation = {"kind": "food_specific_density_estimate", "source": _external("mvt")["attribution"],
                      "source_url": row["source_url"], "acquisition": _external("mvt")["acquisition"],
                      "food_id": row["food_id"], "description": row["description"], "density_g_per_ml": row["value"],
                      "original_nutrition": dict(base.nutrition),
                      "operation": "source_per_100_g * reference_density_g_per_ml", "purchase_quantity_changed": False}
    return replace(base, nutrition={k: v * row["value"] for k, v in base.nutrition.items()}, nutrition_unit="ml",
                   evidence_kind="food_specific_density_estimate",
                   nutrition_basis=base.nutrition_basis + " Uppskattat per 100 ml med vikt per dl från Matvaretabellen.",
                   field_sources={k: (*v, transformation) for k, v in base.field_sources.items()})


# Flavourings bought whole and removed before eating. Their gross mass has no
# reviewed edible yield; the reference over the whole bought mass is an upper
# bound of a few kcal per portion.
GROSS_FLAVOURINGS = frozenset({"citrongräs"})


def gross_flavouring_evidence(product, name, fact, form):
    from dataclasses import replace

    if canonicalize_ingredient_name(name) not in GROSS_FLAVOURINGS:
        return None
    found = evidence(product, name, fact, form)
    if found is None:
        return None
    return replace(found, nutrition_basis=found.nutrition_basis
                   + " Räknat på hela inköpta vikten; det mesta tas bort före servering (övre gräns).")
