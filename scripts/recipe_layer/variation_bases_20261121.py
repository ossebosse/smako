"""Owner request 2026-11-21: "Generera 100 fler recept där det spelar roll".

Measured on beta (Lund, 2026-11-21): fish dinners are the thinnest cheap
segment (11 of 102 fish bases under 100 kr for two), meat next (53 of 301),
then egg/dairy vegetarian and vegan weeks. These 100 bases add cheap fish,
meat, egg/dairy and vegan dinners in six cuisines, on identities with a
product in both Lund and Malmö. AI-authored drafts, not test-cooked.

Same format and variant tags as cheap_bases_20261119.py.
Run: PYTHONPATH=backend:. python scripts/recipe_layer/variation_bases_20261121.py OUT.json
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cheap_bases_20261119 import build  # noqa: E402

NOTE = "AI-författat utkast 2026-11-21 (fler billiga middagar där utbudet är tunt), inte provlagat."


def main(path):
    import variation_data_20261121 as data
    recipes = []
    for base in data.BASES:
        for recipe in build(base, data.PACK_ID):
            recipe["notes"] = NOTE
            recipes.append(recipe)
    json.dump({"schema_version": "smako-recipe-authoring-v1", "pack_id": data.PACK_ID, "recipes": recipes},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(data.BASES), "baser", len(recipes), "varianter")


if __name__ == "__main__":
    main(*sys.argv[1:])
