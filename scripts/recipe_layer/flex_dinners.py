"""Draft flexible versions of the dinners where scaling makes sense.

Owner decisions 2026-11-24/25 (docs/recipes/AUTHORING.md, scalable_recipes.py).
Reads the current library and the reviewed pilot (its lower upper bounds win),
and writes ``smako-meal-pack-v1`` packages with new minor versions plus a report.
Rules:

* main ingredient: a protein (meat, poultry, fish, seafood, tofu, tempeh,
  cheese, keso/kvarg, legumes; eggs only in egg dishes without another protein),
  not a dry ingredient cooked in a fixed amount of water and not named with an
  amount in a step. 75 % to 125 % for filled, wrapped, layered or shaped dishes,
  130 % for soups, stews and oven bakes, 150 % otherwise, and at most 250 g
  meat or fish, 200 g legumes or tofu, 120 g firm cheese, 180 g egg or 250 g
  keso/kvarg/ricotta per portion;
* side: a real starch side (rice, pasta, potato, bread, ...) 70-120 %, unless
  it is dry and cooks in a fixed amount of water;
* followers: seasonings, marinade, sauce and fat in the main ingredient's own
  component that share a step with it; never milk, cream, flour or semolina.

Usage (in the app image or a checkout with the library):
    PYTHONPATH=backend:. python scripts/recipe_layer/flex_dinners.py \
        --pilot backend/app/data/recipes/incoming/scalable-pilot-20261124/pack.json --output out/
"""
import argparse
import collections
import json
import math
import re
import sys
from pathlib import Path

from app.services.meal_library_content import validate_pack_bytes
from app.services.recipe_library import current_recipes
from app.services.scalable_recipes import follower_amount

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--pilot", type=Path)
parser.add_argument("--output", type=Path)
ARGS = parser.parse_args()
PILOT_SOURCE = json.loads(ARGS.pilot.read_text(encoding="utf-8") if ARGS.pilot else sys.stdin.read())
PILOT = {f"{r['design']['base_id']}:{r['design']['variant_id']}": r for r in PILOT_SOURCE["recipes"]}
MEAT = {"kyckling", "fläskfärs", "nötfärs", "blandfärs", "lammfärs", "kalvfärs", "fläskkött", "nötkött", "lammkött",
        "fläskkarré", "rimmat fläsk", "benfri lammstek", "högrev", "nötinnanlår", "nötstek", "nötkött för snabbstekning",
        "kycklinglever", "ungnötslever", "fläsklever", "falukorv", "isterband", "blodpudding", "kokt skinka",
        "fisk", "lax", "tonfisk", "sardiner", "räkor", "rökt lax", "matjessill", "ätklar inläggningssill", "musslor",
        "blåmusselkött utan skal", "bläckfisk", "råa räkor"}
PLANT = {"tofu", "tempeh", "silkestofu", "bönor", "svarta bönor", "kidneybönor", "bruna bönor", "kikärtor", "linser",
         "gröna linser", "svarta linser", "uradlinser", "gula ärtor", "gröna mungbönor"}
FIRM_CHEESE = {"paneer", "halloumi", "fetaost", "ost", "mozzarella", "getost"}
SOFT = {"keso", "kvarg", "ricotta", "ägg", "kokta ägg"}
CAP = {**{k: 250 for k in MEAT}, **{k: 200 for k in PLANT}, **{k: 120 for k in FIRM_CHEESE}, **{k: 250 for k in SOFT}}
CAP["ägg"] = CAP["kokta ägg"] = 180
ENCLOSED = re.compile(r"pirog|calzone|empanad|knyte|bröd|wrap|tortill|burrito|pizza|paj|quiche|lasagn|börek|pastej|"
                      r"dumpling|ravioli|bull|rull|fyll|pitepalt|kroppkak|plätt|crêpe|crepe|pannkak|omelett|frittata|filled|stuffed|"
                      r"relleno|limpa|loaf|kaka|cake|gratäng|gratin|krokett|croquet|pudding|gatt|gateau|terrin", re.IGNORECASE)
EGG_DISH = re.compile(r"ägg|egg|omelett|frittata|shakshuka|äggröra|kuku|tortilla espa", re.IGNORECASE)
REAL_SIDES = {"ris", "pasta", "potatis", "nudlar", "breda risnudlar", "risnudlar", "äggnudlar", "couscous", "bulgur",
              "bröd", "quinoa", "korngryn", "matvete", "majstortillas", "tortillas", "polenta", "fullkornspasta",
              "gnocchi", "sötpotatis", "basmatiris", "jasminris", "fullkornsris", "glasnudlar", "udon", "soba", "pitabröd",
              "naanbröd", "tunnbröd", "rågbröd", "surdegsbröd", "baguette", "ciabatta", "fullkornsbröd"}
NO_FOLLOW = {"mjölk", "grädde", "vispgrädde", "matlagningsgrädde", "mellanmjölk", "lättmjölk", "havredryck",
             "sojadryck", "mannagryn", "vetemjöl", "dinkelmjöl"}
GRAMS = re.compile(r"\b\d+(?:[,.]\d+)?\s*(?:g|kg|st)\b")

def snap(q, value, step, down):
    k = math.floor(round(abs(value - q) / step, 6))
    return round(q - k * step if down else q + k * step, 4)

def step_for(q):
    return 20.0 if q >= 200 else 10.0 if q >= 60 else 5.0

rows, report, skipped = [], [], collections.Counter()
for recipe in current_recipes():
    d = recipe.design
    if not d or "dinner" not in d.meal_types:
        continue
    if d.scaling or d.unmeasured_processes or d.active_minutes is None:
        skipped["unmeasured_or_old_format"] += 1; continue
    water = {k for s in d.steps if s.scalable_amounts for k in s.ingredient_keys}
    enclosed = bool(ENCLOSED.search(recipe.name + " " + d.family + " " + d.base_id))
    hi = 1.25 if enclosed else 1.3 if d.method in ("pot", "bake") else 1.5
    proteins = [i for i in recipe.ingredients if i.role == "primary" and i.canonical_name in CAP]
    egg_dish = bool(EGG_DISH.search(recipe.name))
    key = lambda i: f"{i.canonical_name}|{i.form}"
    pilot = PILOT.get(f"{d.base_id}:{d.variant_id}")
    pilot_max = {i["name"]: i["quantity_max"] for i in pilot["ingredients"]} if pilot else {}
    data = json.loads(recipe.model_dump_json(exclude={"preparation"}))
    lines = {i["name"]: i for i in data["ingredients"]}
    mains, sides, notes = [], [], []
    for i in recipe.ingredients:
        if i.unit != "g":
            continue
        k = key(i)
        steps_with = [s for s in d.steps if k in s.ingredient_keys]
        if i.role == "primary" and i.canonical_name in ("ägg", "kokta ägg") and (
                not egg_dish or any(p.canonical_name not in ("ägg", "kokta ägg") for p in proteins)):
            notes.append(f"{i.name}: ägg som bindemedel"); continue
        if i.role == "primary" and i.canonical_name in CAP:
            if i.form == "dry" and k in water:
                notes.append(f"{i.name}: torr i fast vatten"); continue
            if any(GRAMS.search(s.text) and i.canonical_name.split()[0] in s.text.lower() for s in steps_with):
                notes.append(f"{i.name}: mängd i stegtexten"); continue
            q, st = i.quantity, step_for(i.quantity)
            top = min(q * hi, max(q, CAP[i.canonical_name] * recipe.servings))
            if i.name in pilot_max:
                top = min(top, pilot_max[i.name])
            low, high = snap(q, q * 0.75, st, True), snap(q, top, st, False)
            if high <= q:
                notes.append(f"{i.name}: redan vid taket"); continue
            mains.append((i, low, high, st))
        elif i.role == "side" and i.canonical_name in REAL_SIDES and not (i.form == "dry" and k in water):
            q, st = i.quantity, step_for(i.quantity)
            sides.append((i, snap(q, q * 0.7, st, True), snap(q, q * 1.2, st, False), st))
    if not mains:
        skipped["no_scalable_protein"] += 1; continue
    for i, low, high, st in mains + sides:
        lines[i.name].update(quantity_min=low, quantity_max=high, quantity_step=st)
    followers = []
    for m, low, high, _ in mains:
        mk = key(m)
        comps = {c.id for c in d.components if any(a.ingredient_key == mk for a in c.amounts)}
        step_keys = {k for s in d.steps if mk in s.ingredient_keys for k in s.ingredient_keys}
        for i in recipe.ingredients:
            k = key(i)
            if (i.role not in {"flavour", "cooking", "sauce"} or k not in step_keys or lines[i.name].get("scales_with")
                    or i.canonical_name in NO_FOLLOW):
                continue
            share = sum(a.quantity for c in d.components if c.id in comps for a in c.amounts if a.ingredient_key == k)
            if not share:
                continue
            lo = follower_amount(i.quantity - share * (1 - low / m.quantity))
            up = follower_amount(i.quantity + share * (high / m.quantity - 1))
            lines[i.name].update(scales_with=mk, quantity_min=min(lo, i.quantity), quantity_max=max(up, i.quantity),
                                 quantity_step=0.5)
            followers.append(i.name)
    major, minor, _ = (int(x) for x in d.version.split("."))
    data["design"]["version"] = f"{major}.{minor + 1}.0"
    data["design"]["scaling"] = "reviewed_ranges"
    source = data["design"].get("content_source")
    if source:
        for k in ("pack_id", "proposal_id", "sha256"):
            source.pop(k, None)
        source["scaling_note"] = (source.get("scaling_note", "") + " Huvudråvara, tillbehör och smaksättning till "
                                  "huvudråvaran har granskade intervall (ägarbeslut 2026-11-24/25); utan näringsgränser "
                                  "används receptets mängd.").strip()
    rows.append(data)
    report.append({"id": f"{d.base_id}:{data['design']['version']}:{d.variant_id}", "name": recipe.name,
                   "servings": recipe.servings, "method": d.method, "enclosed": enclosed,
                   "mains": [f"{i.name} {i.quantity:g} → {lo:g}–{hi_:g}" for i, lo, hi_, _ in mains],
                   "sides": [f"{i.name} {i.quantity:g} → {lo:g}–{hi_:g}" for i, lo, hi_, _ in sides],
                   "followers": followers, "notes": notes})

packs, rejections, accepted = [], [], 0
for n in range(0, len(rows), 900):
    pack = {"schema_version": "smako-meal-pack-v1", "pack_id": f"flex-dinners-20261125-{n // 900 + 1}", "recipes": rows[n:n + 900]}
    raw = json.dumps(pack, ensure_ascii=False, indent=1).encode()
    checked = validate_pack_bytes(raw, label=pack["pack_id"])
    bad = {int(r["field"].split("[")[1].split("]")[0]) for r in checked["rejections"]}
    rejections += [{**r, "pack": pack["pack_id"]} for r in checked["rejections"]]
    pack["recipes"] = [r for i, r in enumerate(pack["recipes"]) if i not in bad]
    accepted += len(pack["recipes"])
    packs.append(pack)
result = {"report": report, "skipped": skipped, "rejections": rejections, "accepted": accepted}
if ARGS.output:
    ARGS.output.mkdir(parents=True, exist_ok=True)
    for pack in packs:
        (ARGS.output / f"{pack['pack_id']}.json").write_text(
            json.dumps(pack, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (ARGS.output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "report"}, ensure_ascii=False))
else:
    print(json.dumps({"packs": packs, **result}, ensure_ascii=False))
