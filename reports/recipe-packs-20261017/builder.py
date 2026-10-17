"""Compact authoring helper -> smako-meal-pack-v1 records (validated by the official CLI)."""
import json
from collections import Counter
from app.services.recipe_library import current_recipes, ingredient_count

_LIB = current_recipes(6)
_REQ = {}
_c = Counter()
for r in _LIB:
    for i in r.ingredients:
        _c[(i.canonical_name, i.form, i.unit, tuple(i.product_requirements or ()))] += 1
for (can, form, unit, req), n in _c.most_common():
    _REQ.setdefault((can, form), (unit, req))
KNOWN = set(_REQ)
NAMES = {r.name for r in _LIB}
BASES = {r.design.base_id for r in _LIB}

def I(can, form, qty, comp, role, label, req=None, unit=None):
    if (can, form) not in KNOWN:
        raise ValueError(f"okänd identitet {can}|{form}")
    u0, r0 = _REQ[(can, form)]
    return dict(can=can, form=form, qty=float(qty), unit=unit or u0, comp=comp, role=role,
                label=label, req=list(r0 if req is None else req))

def recipe(*, base_id, name, servings, meal_type, cuisine, family, primary, method, side, flavor,
           equipment, vegetarian, fish=False, components, steps, active, total, waiting=0,
           level="crafted", version="1.0.0", note=""):
    ings, comps = [], []
    for cid, cname, items in components:
        comps.append({"id": cid, "name": cname, "amounts": [
            {"ingredient_key": f"{x['can']}|{x['form']}", "name": x["label"], "note": "",
             "quantity": x["qty"], "unit": x["unit"]} for x in items]})
        for x in items:
            ings.append(x | {"comp": cid})
    # merge same identity across components into one purchase line
    merged = {}
    for x in ings:
        k = (x["can"], x["form"])
        if k in merged:
            merged[k]["qty"] += x["qty"]
        else:
            merged[k] = dict(x)
    ingredients = [{"name": x["can"], "canonical_name": x["can"], "quantity": round(x["qty"], 4),
                    "unit": x["unit"], "form": x["form"], "component": x["comp"], "required": True,
                    "role": x["role"], "quantity_min": round(x["qty"], 4), "quantity_max": round(x["qty"], 4),
                    "quantity_step": round(x["qty"], 4), **({"product_requirements": x["req"]} if x["req"] else {})}
                   for x in merged.values()]
    st = []
    for n, (text, keys, minutes, deps) in enumerate(steps, 1):
        st.append({"id": f"s{n}", "text": text, "ingredient_keys": sorted(keys), "depends_on": deps,
                   "duration_minutes": minutes, "parallel_group": None})
    design = {"base_id": base_id, "version": version, "variant_id": "base", "cuisines": [cuisine],
              "family": family, "primary_ingredient": primary, "method": method, "side": side,
              "flavor_profile": flavor, "components": comps, "steps": st, "estimated_minutes": total,
              "equipment": equipment, "vegetarian": vegetarian, "fish": fish, "ingredient_count": 0,
              "provenance": {"reviewed_at": "2026-10-17", "notes": note or
                  "Författat med modellstöd och granskat mot Smakos receptregler. Inte provlagat. Köp, allergener och näring kvalificeras separat."},
              "content_sha256": "0" * 64, "meal_types": [meal_type], "active_minutes": active,
              "waiting_minutes": waiting, "total_minutes": total}
    if level != "crafted":
        design["dinner_level"] = level
    rec = {"name": name, "servings": servings, "ingredients": ingredients,
           "instructions": [s["text"] for s in st], "design": design}
    from app.models import Recipe
    tmp = json.loads(json.dumps(rec)); tmp["design"]["ingredient_count"] = 1
    rec["design"]["ingredient_count"] = ingredient_count(Recipe.model_validate(tmp))
    return rec

def keys(*items):
    return [f"{x['can']}|{x['form']}" for x in items]

def pack(pack_id, recipes):
    return {"schema_version": "smako-meal-pack-v1", "pack_id": pack_id, "recipes": recipes}
