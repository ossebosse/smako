"""Owner decision 2026-11-19: Claude authors new dinners on cheap ingredients
with few dishes (vitkål, gula ärtor, blodpudding, korv, kycklinglever, bruna
bönor, tonfisk, fläskfärs outside Thai, root vegetables, havregryn), so weeks
vary without costing more. AI-authored drafts, not test-cooked.

Each base is written once; variants select ingredients and steps by tag:
S = simple (about 7-8 counted ingredients), T = standard (10-12),
E = extended (13-15). Run: PYTHONPATH=backend:. python scripts/recipe_layer/cheap_bases_20261119.py OUT.json
"""
from __future__ import annotations

import json
import sys

ALL = "STE"
VARIANTS = {"S": "simple", "T": "standard", "E": "extended"}

def I(name, form, qty, role, label, v=ALL, comp="c1", **extra):
    return {"name": name, "form": form, "quantity": qty, "role": role, "label": label, "v": v, "comp": comp, **extra}

def St(key, text, uses, minutes, after=(), passive=False, v=ALL):
    return {"key": key, "text": text, "uses": uses, "minutes": minutes, "after": list(after), "passive": passive, "v": v}

def build(base, pack_id):
    out = []
    for tag, variant_id in VARIANTS.items():
        if tag not in base.get("variants", ALL):
            continue
        names = base["names"][tag]
        comps = {}
        for ing in base["ingredients"]:
            if tag not in ing["v"]:
                continue
            q = ing["quantity"]
            if isinstance(q, dict):
                q = q[tag]
            row = {k: v for k, v in ing.items() if k not in ("v", "comp")}
            row["quantity"] = q
            comps.setdefault(ing["comp"], []).append(row)
        steps, index = [], {}
        for st in base["steps"]:
            if tag not in st["v"]:
                continue
            text = st["text"][tag] if isinstance(st["text"], dict) else st["text"]
            uses = st["uses"][tag] if isinstance(st["uses"], dict) else st["uses"]
            present = {r["name"] for rows in comps.values() for r in rows}
            uses = [u for u in uses if u in present]
            after = [index[a] for a in st["after"] if a in index]
            row = {"text": text, "uses": uses, "minutes": st["minutes"]}
            if after:
                row["after"] = after
            if st["passive"]:
                row["passive"] = True
            steps.append(row)
            index[st["key"]] = len(steps)
        out.append({
            "base_id": base["base_id"], "name": names, "servings": 4, "meal_type": "dinner",
            "cuisine": base["cuisine"], "family": base["family"], "primary": base["primary"],
            "method": base["method"], "side": base["side"], "flavor": base["flavor"],
            "equipment": base["equipment"], "version": "1.0.0", "variant_id": variant_id,
            "notes": "AI-författat utkast 2026-11-19 (billiga råvaror), inte provlagat.",
            "components": [{"id": cid, "name": base["components"][cid], "ingredients": rows} for cid, rows in comps.items()],
            "steps": steps,
        })
    return out

def main(path, bases_module="cheap_bases_data_20261119"):
    import importlib
    sys.path.insert(0, __import__("os").path.dirname(__file__))
    data = importlib.import_module(bases_module)
    recipes = [r for base in data.BASES for r in build(base, data.PACK_ID)]
    json.dump({"schema_version": "smako-recipe-authoring-v1", "pack_id": data.PACK_ID, "recipes": recipes},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(data.BASES), "baser", len(recipes), "varianter")

if __name__ == "__main__":
    main(*sys.argv[1:])
