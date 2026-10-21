"""Deterministic synthetic test library for recipe-scaling measurements.

NOT production content. Writes smako-recipe-authoring-v1 drafts for the
ordinary `meal_library_cli author` path, so every recipe goes through the
same standardisation, import and preparation as real content.

Bases are distinct dishes: protein x flavour x sauce x vegetable pair.
Variations share a base_id and differ only in side (variant_id), as the
library defines a variant. Generation is nested: the first N recipes of a
larger library are exactly the smaller library, so sizes are comparable.

usage: generate_library.py --recipes 758 --output drafts.json [--seed 20261019]
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from pathlib import Path

# name, form, quantity, kind; kind decides wording and safety text.
PROTEINS = [
    ("kyckling", "raw_edible", 360, "kyckling", "Kyckling"),
    ("nötfärs", "raw_edible", 300, "färs", "Nötfärs"),
    ("fläskfärs", "raw_edible", 300, "färs", "Fläskfärs"),
    ("blandfärs", "raw_edible", 300, "färs", "Blandfärs"),
    ("fisk", "raw_edible", 360, "fisk", "Fisk"),
    ("lax", "raw_edible", 300, "fisk", "Lax"),
    ("linser", "dry", 180, "linser", "Röda linser"),
    ("kikärtor", "cooked_drained", 400, "baljväxt", "Kikärtor"),
    ("bönor", "cooked_drained", 400, "baljväxt", "Bönor"),
    ("tofu", "as_sold", 400, "tofu", "Tofu"),
]
FLAVOURS = [  # spice name, form, qty, cuisine, adjective
    ("paprikapulver", "dry", 3, "swedish", "paprika"),
    ("spiskummin", "dry", 3, "indian", "spiskummin"),
    ("ingefära", "raw_edible", 15, "thai", "ingefära"),
    ("oregano", "dry", 2, "italian", "oregano"),
    ("chiliflakes", "dry", 1, "mexican", "chili"),
    ("gurkmeja", "dry", 3, "indian", "gurkmeja"),
]
SAUCES = [  # name, form, qty, label
    ("krossade tomater", "as_sold", 300, "tomatsås"),
    ("kokosmjölk", "as_sold", 200, "kokossås"),
    ("crème fraiche", "as_sold", 150, "gräddsås"),
]
VEGETABLES = [  # name, form, qty
    ("paprika", "raw_edible", 150), ("zucchini", "raw_edible", 150),
    ("spenat", "as_sold", 150), ("ärtor", "as_sold", 150),
    ("morot", "raw_edible", 150), ("broccoli", "raw_edible", 150),
    ("champinjoner", "raw_edible", 150), ("vitkål", "raw_edible", 150),
    ("aubergine", "raw_edible", 150), ("blomkål", "raw_edible", 150),
]
SIDES = [  # name, form, qty, variant label, cooking step
    ("ris", "dry", 150, "ris", "Koka riset i 300 ml vatten, cirka 15 minuter. Låt vila under lock.", 18),
    ("pasta", "dry", 200, "pasta", "Koka pastan i 2000 ml saltat vatten enligt förpackningen, cirka 10 minuter. Häll av.", 14),
    ("couscous", "dry", 150, "couscous", "Häll 250 ml kokande vatten över couscousen. Låt stå under lock i 5 minuter.", 7),
    ("potatis", "raw_edible", 500, "potatis", "Skala och dela potatisen. Koka i 1500 ml vatten i cirka 20 minuter. Häll av.", 25),
]
SAFETY = {
    "kyckling": "tills tjockaste biten når minst 74 °C",
    "färs": "tills färsen är genomstekt och når minst 72 °C",
    "fisk": "tills fisken når minst 63 °C i mitten",
}


def bases(seed):
    combos = list(itertools.product(range(len(PROTEINS)), range(len(FLAVOURS)), range(len(SAUCES)),
                                    itertools.combinations(range(len(VEGETABLES)), 2)))
    random.Random(seed).shuffle(combos)
    return combos


def recipe(index, combo, side, *, servings=2):
    p, f, s, (v1, v2) = combo
    name, form, qty, kind, title = PROTEINS[p]
    spice, spice_form, spice_qty, cuisine, adjective = FLAVOURS[f]
    sauce, sauce_form, sauce_qty, sauce_label = SAUCES[s]
    veg = [VEGETABLES[v1], VEGETABLES[v2]]
    side_name, side_form, side_qty, side_label, side_text, side_minutes = side
    base_id = f"smako-scaling-test-{index:05d}"
    protein_step = {
        "kyckling": f"Skär kycklingen i bitar. Bryn i oljan och sjud sedan i såsen {SAFETY['kyckling']}.",
        "färs": f"Bryn {name}en i oljan och sjud i såsen {SAFETY['färs']}.",
        "fisk": f"Skär {name}en i bitar och lägg ner i såsen. Sjud {SAFETY['fisk']}.",
        "linser": "Skölj linserna och koka dem i såsen med 300 ml vatten i cirka 15 minuter.",
        "baljväxt": f"Låt {name} rinna av och värm dem i såsen i 5 minuter. Bryn först kort i oljan.",
        "tofu": "Skär tofun i tärningar, bryn i oljan och vänd ner i såsen.",
    }[kind]
    uses_protein = [name, "rapsolja"]
    return {
        "base_id": base_id,
        "variant_id": "base" if side is SIDES[0] else side_label,
        "name": f"{title} i {sauce_label} med {adjective}, {veg[0][0]} och {veg[1][0]}, med {side_label}",
        "servings": servings, "meal_type": "dinner", "cuisine": cuisine,
        "family": f"scaling-{kind}-{sauce_label}", "primary": name, "method": "pot", "side": side_name,
        "flavor": [spice, "citronjuice"], "equipment": ["Kastrull", "Gryta", "Skärbräda", "Kniv"],
        "notes": "Syntetiskt skalningstest 2026-10-19. Inte produktionsinnehåll, inte provlagat.",
        "components": [
            {"id": "protein", "name": title, "ingredients": [
                {"name": name, "form": form, "quantity": qty, "role": "primary", "label": name}]},
            {"id": "sauce", "name": "Sås", "ingredients": [
                {"name": "gul lök", "form": "raw_edible", "quantity": 100, "role": "vegetable", "label": "gul lök"},
                {"name": "vitlök", "form": "raw_edible", "quantity": 8, "role": "flavour", "label": "vitlök"},
                {"name": "rapsolja", "form": "as_sold", "quantity": 20, "role": "cooking", "label": "rapsolja"},
                {"name": "salt", "form": "as_sold", "quantity": 2, "role": "flavour", "label": "salt"},
                {"name": sauce, "form": sauce_form, "quantity": sauce_qty, "role": "sauce", "label": sauce},
                *({"name": n, "form": fm, "quantity": q, "role": "vegetable", "label": n} for n, fm, q in veg),
                {"name": spice, "form": spice_form, "quantity": spice_qty, "role": "flavour", "label": spice},
                {"name": "citronjuice", "form": "as_sold", "quantity": 10, "role": "flavour", "label": "citronjuice"},
            ]},
            {"id": "side", "name": side_label.capitalize(), "ingredients": [
                {"name": side_name, "form": side_form, "quantity": side_qty, "role": "side", "label": side_name}]},
        ],
        "steps": [
            {"text": side_text, "uses": [side_name], "minutes": side_minutes, "passive": True},
            {"text": (f"Hacka lök och vitlök och skär {veg[0][0]} och {veg[1][0]}. Fräs i oljan med {spice}. "
                      f"Tillsätt {sauce} och sjud 10 minuter. Smaka av med citronjuice och salt."),
             "uses": ["gul lök", "vitlök", "rapsolja", "salt", sauce, veg[0][0], veg[1][0], spice, "citronjuice"],
             "minutes": 18},
            {"text": protein_step, "uses": uses_protein, "minutes": 15, "after": [2]},
            {"text": "Servera med tillbehöret. Kyl eventuella rester snabbt.", "uses": [name, side_name],
             "minutes": 2, "after": [1, 3]},
        ],
    }


def library(count, seed):
    """First `count` recipes; each base gets 1-4 side variants (deterministic)."""
    rng = random.Random(seed + 1)
    out = []
    for index, combo in enumerate(bases(seed)):
        variants = rng.choice((1, 1, 2, 2, 3, 4))
        sides = [SIDES[0], *rng.sample(SIDES[1:], variants - 1)]
        for side in sides:
            if len(out) == count:
                return out
            out.append(recipe(index, combo, side))
    raise SystemExit(f"only {len(out)} combinations available")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--recipes", type=int, required=True)
    p.add_argument("--seed", type=int, default=20261019)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    recipes = library(args.recipes, args.seed)
    pack = {"schema_version": "smako-recipe-authoring-v1",
            "pack_id": f"scaling-test-{args.recipes}-{args.seed}", "recipes": recipes}
    args.output.write_text(json.dumps(pack, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"recipes": len(recipes), "bases": len({r["base_id"] for r in recipes}),
                      "variations": sum(r["variant_id"] != "base" for r in recipes)}))


if __name__ == "__main__":
    main()
