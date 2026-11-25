"""Generic nutrition for loose foods whose product has no table (owner decision 2026-11-25).

Meat sold by weight (grytbitar, karré, högrev, lammstek...) and loose
vegetables and herbs (sallad, salladslök, rädisor, mynta...) usually publish
no nutrition table. Before this, a dinner with such an input could never be
planned under a nutrition limit. The owner decided that Smako uses a public
food composition reference for them, also for limits: Livsmedelsverket's
database, and Matvaretabellen where Livsmedelsverket has no entry
(salladslök, schalottenlök). The plan marks these values as estimated.

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
    r"marinerad|panerad|grillad|rökt|gravad|kryddad|färdigrätt|färdig|röra\b|sås\b|soppa|gratäng|kokt|stekt|"
    r"inlagd|konserv|torkad|pulver|chips|burgare|korv|bacon|kebab|pulled|sous vide|tillagad")


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
}


def identity(name, product_label):
    """The reference for this recipe input and bought product, or None."""
    label = " ".join(str(product_label or "").casefold().split())
    if _OTHER_FOOD.search(label):
        return None
    rule = _RULES.get(canonicalize_ingredient_name(name))
    return rule(label) if rule else None


@lru_cache(maxsize=1)
def _matvaretabellen():
    return json.loads((_DATA / "matvaretabellen-20261125-loose.json").read_bytes())


@lru_cache(maxsize=64)
def _matvaretabellen_evidence(key):
    from app.services.nutrition_reference import NutritionEvidence

    source = _matvaretabellen()
    row = source["foods"][key]
    proof = {"kind": "generic_reference", "policy": POLICY_VERSION, "food_id": row["food_id"],
             "description": row["description"], "source_url": row["source_url"],
             "acquisition": source["acquisition"], "original_values": row["original_values"],
             "source": source["attribution"]}
    return NutritionEvidence(source=source["attribution"], source_product_id=row["food_id"],
                             nutrition=dict(row["nutrition"]),
                             nutrition_basis=row["description"] + "; generiskt referensvärde per 100 g, inte produktdeklaration.",
                             field_sources={f"nutrition.{k}": (proof,) for k in row["nutrition"]}, ingredient=key)


def evidence(product, name, fact, form):
    """Unwrapped per-100 g evidence for a plain loose food, or None."""
    if fact and (fact.conflicts or fact.nutrition):
        return None
    ident = identity(name, product.name)
    if ident is None:
        return None
    if isinstance(ident, str):
        return _matvaretabellen_evidence(ident.split(":", 1)[1]) if form == "raw_edible" else None
    from app.services.nutrition_reference import MAPPINGS, reference_evidence

    state = MAPPINGS.get(ident, (None, None))[1]
    compatible = {"raw_edible": {"raw", "raw_skinless_breast", "raw_cod", "raw_farmed"},
                  "as_sold": {"frozen", "ready"}, "cooked_drained": {"drained"}}
    if state not in compatible.get(form, set()):
        return None
    return reference_evidence(ident)
