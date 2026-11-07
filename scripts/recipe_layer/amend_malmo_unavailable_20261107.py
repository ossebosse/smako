"""Reviewed successors for ingredients no Malmö store sells (2026-11-07).

Live Malmö universe 0ff24174 (2026-11-07): no store sells tamarind concentrate
(article 101674821_ST left the Axfood range), tapioca starch, fresh mackerel,
green unripe mango or chana dal. Each affected active variant gets a new
version with an explicit buyable ingredient; no identity alias, density or
yield conversion. Quantities are kept as authored estimates. Not cooked.
Original packs stay immutable; the newest version supersedes as before.

Run --prepare, read the change report, then --publish.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter

from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    load_entries,
    manifest_entries,
    validate_pack_bytes,
)
from app.services.recipe_library import current_recipes

REPORT = ROOT.parents[3] / "docs/reviews/malmo-unavailable-20261107"
WORK = ROOT.parents[3] / ".local/malmo-unavailable-20261107"
PACK = "malmo-unavailable-20261107"
GREEN_MANGO = "pack:intake_all_shape_green_mango"
# old canonical -> (new canonical, form, unit, requirements, label, group)
SUBSTITUTES = {
    "tamarindkoncentrat": ("limejuice", "as_sold", "ml", ["pure_juice"], "Limejuice, ren pressad juice", "tamarind"),
    "tapiokastärkelse": ("potatismjöl", "dry", "g", ["pack:intake_all_3afd0244c1bd"], "Potatismjöl", "tapioca"),
    "makrill": ("lax", "raw_edible", "g", [], "Laxfilé, rå vikt utan ben", "mackerel"),
    "mango": ("äpple", "raw_edible", "g", [], "Syrligt grönt äpple, rå ätlig vikt utan kärnhus", "green_mango"),
    "chana dal": ("gula ärtor", "dry", "g", ["pack:intake_all_aa2766b52ef7"], "Gula ärtor, torr vikt", "chana_dal"),
}
# Where a recipe already uses lime juice, tamarind becomes lemon juice so each
# ingredient and form still appears once.
LEMON = ("citronjuice", "as_sold", "ml", ["pure_juice"], "Citronjuice, ren pressad juice", "tamarind_lemon")
# Longest first; applied case-preservingly to names and step texts.
WORDS = {
    "tamarind": [("tamarindkoncentratet", "limejuicen"), ("tamarindkoncentrat", "limejuice"), ("tamarind", "lime")],
    "tamarind_lemon": [("tamarindkoncentratet", "citronjuicen"), ("tamarindkoncentrat", "citronjuice"), ("tamarind", "citron")],
    "tapioca": [("tapiokastärkelsen", "potatismjölet"), ("tapiokastärkelse", "potatismjöl"),
                ("tapiokakakor", "potatismjölskakor"), ("tapiokakaka", "potatismjölskaka"),
                ("tapiokadeg", "potatismjölsdeg"), ("tapioka", "potatismjöl")],
    "mackerel": [("makrill", "lax")],
    "green_mango": [("grön mangosås", "grön äppelsås"), ("grön mangopuré", "grön äppelpuré"),
                    ("den fasta omogna mangon", "det fasta syrliga äpplet"), ("omogna mangon", "syrliga äpplet"),
                    ("den omogna frukten", "den syrliga frukten"), ("syrlig mango", "syrligt äpple"),
                    ("grön omogen mango", "syrligt grönt äpple"), ("gröna omogna mangon", "gröna äpplet"),
                    ("omogen mango", "syrligt grönt äpple"), ("gröna mangon", "gröna äpplet"),
                    ("grön mango", "grönt äpple"), ("mangon", "äpplet"), ("mangopurén", "äppelpurén"),
                    ("mangopuré", "äppelpuré"), ("mangobitarna", "äppelbitarna"), ("mangobitar", "äppelbitar"),
                    ("mangostavarna", "äppelstavarna"), ("mangostavar", "äppelstavar"),
                    ("mangostrimlorna", "äppelstrimlorna"), ("mangostrimlor", "äppelstrimlor"),
                    ("mangosallad", "äppelsallad"), ("mangosåsen", "äppelsåsen"), ("mangosås", "äppelsås"),
                    ("mango(?!ld)", "äpple")],
    "chana_dal": [("chana dalen", "de gula ärtorna"), ("chana dal", "gula ärtor")],
}
REASON = ("Malmö-sortimentet 2026-11-07 saknar {old}; ny version med köpbar {new}. "
          "Anpassning av smak och textur, inte samma råvara; mängder och tider är författaruppskattningar, "
          "inte provlagat. Originalversionen bevaras. Se docs/reviews/malmo-unavailable-20261107.")


def recase(text, pairs):
    for before, after in pairs:
        text = re.sub(before, lambda m, a=after: a[0].upper() + a[1:] if m[0][0].isupper() else a,
                      text, flags=re.IGNORECASE)
    return text


def targets(recipe):
    found = []
    for item in recipe["ingredients"]:
        old = item["canonical_name"]
        if old not in SUBSTITUTES:
            continue
        if old == "mango" and GREEN_MANGO not in (item.get("product_requirements") or []):
            continue
        found.append(old)
    return sorted(set(found))


LIME_BASES = set()


def choices(recipe):
    present = {(i["canonical_name"], i["form"]) for i in recipe["ingredients"]}
    chosen = {}
    for old in targets(recipe):
        sub = SUBSTITUTES[old]
        # One choice per dish: every variant of a base that elsewhere already
        # uses lime juice gets lemon juice.
        if old == "tamarindkoncentrat" and recipe["design"]["base_id"] in LIME_BASES:
            sub = LEMON
        if (sub[0], sub[1]) in present:
            raise ValueError((recipe["design"]["base_id"], "substitute already present", sub[0]))
        chosen[old] = sub
    return chosen


def amend(original):
    row = copy.deepcopy(original)
    chosen = choices(row)
    olds = sorted(chosen)
    pairs = [p for old in olds for p in WORDS[chosen[old][5]]]
    keys = {}
    for old in olds:
        new, form, unit, requirements, _, _ = chosen[old]
        for item in row["ingredients"]:
            if item["canonical_name"] == old:
                keys[f"{old}|{item['form']}"] = f"{new}|{form}"
                item.update(name=new, canonical_name=new, form=form, unit=unit, product_requirements=list(requirements))
        forms = row["preparation"]["input_forms"]
        if old in forms:
            forms[new] = form
            del forms[old]
    design = row["design"]
    for component in design["components"]:
        component["name"] = recase(component["name"], pairs)
        for amount in component["amounts"]:
            if amount["ingredient_key"] in keys:
                old = amount["ingredient_key"].split("|")[0]
                amount["ingredient_key"] = keys[amount["ingredient_key"]]
                amount["name"] = chosen[old][4]
    # In steps a bare "tamarind" names the ingredient itself, i.e. the juice.
    step_pairs = [(r"\btamarind\b", chosen[o][0]) for o in olds if o == "tamarindkoncentrat"] + pairs
    for step in design["steps"]:
        step["ingredient_keys"] = [keys.get(k, k) for k in step["ingredient_keys"]]
        step["text"] = recase(step["text"], step_pairs)
        if "äpple|raw_edible" in step["ingredient_keys"] and "mango" in olds:
            step["text"] = re.sub(r"\bkärnan\b", "kärnhuset", step["text"])
            step["text"] = re.sub(r"skal och kärna\b", "skal och kärnhus", step["text"])
            step["text"] = step["text"].replace(" Frysta tärningar uppfyller inte receptets formkrav.", "")
    row["instructions"] = [s["text"] for s in design["steps"]]
    row["name"] = recase(row["name"], pairs)
    for key in ("primary_ingredient", "side"):
        if isinstance(design.get(key), str):
            design[key] = recase(design[key], pairs)
    if isinstance(design.get("flavor_profile"), list):
        design["flavor_profile"] = [recase(v, pairs) for v in design["flavor_profile"]]
    major, minor, patch = map(int, design["version"].split("."))
    design["version"] = f"{major}.{minor}.{patch + 1}"
    design["provenance"]["reviewed_at"] = "2026-11-07"
    reasons = [REASON.format(old="grön omogen mango" if o == "mango" else o, new=chosen[o][0]) for o in olds]
    design["provenance"]["notes"] += " " + " ".join(reasons)
    for key in ("pack_id", "proposal_id", "sha256"):
        design["content_source"].pop(key, None)
    return row, chosen


def check_pair(old, new, chosen):
    olds = set(chosen)
    assert len(old.ingredients) == len(new.ingredients)
    for before, after in zip(old.ingredients, new.ingredients, strict=True):
        if before.canonical_name in olds and (before.canonical_name != "mango" or GREEN_MANGO in (before.product_requirements or ())):
            name, form, unit, requirements, _, _ = chosen[before.canonical_name]
            assert (after.canonical_name, after.form, after.unit) == (name, form, unit)
            assert list(after.product_requirements or ()) == requirements
            assert after.quantity == before.quantity
        else:
            assert before == after, (identity(old), before.canonical_name)
    assert set(re.findall(r"\d+ °C", " ".join(old.instructions))) <= set(re.findall(r"\d+ °C", " ".join(new.instructions)))
    assert (old.design.vegetarian, old.design.fish) == (new.design.vegetarian, new.design.fish)
    assert old.design.ingredient_count == new.design.ingredient_count
    assert (old.design.active_minutes, old.design.total_minutes) == (new.design.active_minutes, new.design.total_minutes)
    stems = {"tamarindkoncentrat": r"tamarind", "tapiokastärkelse": r"tapiok", "makrill": r"makrill",
             "chana dal": r"chana", "mango": r"\bmango(?!ld)"}
    pattern = "|".join(stems[o] for o in olds)
    leftovers = re.findall(pattern, " ".join([new.name, *new.instructions]).casefold())
    assert not leftovers, (identity(new), leftovers)


def prepare():
    if (REPORT / "recipe-review.json").exists():
        raise ValueError("Already prepared")
    WORK.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    manifest = manifest_entries()
    rows, originals, records = [], {}, []
    LIME_BASES.update(r.design.base_id for r in current_recipes()
                      if {i.canonical_name for i in r.ingredients} >= {"tamarindkoncentrat", "limejuice"})
    for recipe in current_recipes():
        old = recipe.model_dump(mode="json")
        olds = targets(old)
        if not olds:
            continue
        row, chosen = amend(old)
        rows.append(row)
        originals[recipe.design.base_id, recipe.design.variant_id] = (recipe, chosen)
        records.append({"previous_id": identity(recipe), "previous_content_sha256": recipe.design.content_sha256,
                        "replaced": [f"{o}->{chosen[o][0]}" for o in sorted(chosen)],
                        "name_before": old["name"], "name_after": row["name"]})
    source = encoded({"schema_version": "smako-meal-pack-v1", "pack_id": PACK, "recipes": rows})
    validated = validate_pack_bytes(source)
    if validated["rejections"]:
        raise ValueError(validated["rejections"][:5])
    for record, recipe in zip(records, validated["recipes"], strict=True):
        old, chosen = originals[recipe.design.base_id, recipe.design.variant_id]
        check_pair(old, recipe, chosen)
        record.update(runtime_id=identity(recipe), content_sha256=recipe.design.content_sha256,
                      steps_after=list(recipe.instructions))
    path = WORK / "pack.json"
    path.write_bytes(source)
    review = {"schema": "smako-malmo-unavailable-review-v1", "before_manifest": manifest,
              "before_manifest_file_sha256": hashlib.sha256(encoded(manifest)).hexdigest(),
              "evidence": "Live Malmö PriceUniverse 0ff241747c22de2d7228d9e2f2039c50e9dc85f2c3660293102b1002cc46d6ac "
                          "(activated 2026-11-07T07:26Z): no buyable product for the replaced identities.",
              "substitutes": {**{k: list(v[:5]) for k, v in SUBSTITUTES.items()},
                              "tamarindkoncentrat_when_lime_present": list(LEMON[:5])},
              "group_counts": dict(Counter(r for rec in records for r in rec["replaced"])),
              "cooking_test": "not_cooked", "draft_sha256": hashlib.sha256(source).hexdigest(), "corrected": records}
    (REPORT / "recipe-review.json").write_bytes(encoded(review))
    print(json.dumps({"changed": len(records), "groups": review["group_counts"]}, ensure_ascii=False))


def publish():
    review = json.loads((REPORT / "recipe-review.json").read_bytes())
    if manifest_entries() != review["before_manifest"]:
        raise ValueError("Manifest changed after review")
    path = WORK / "pack.json"
    if hashlib.sha256(path.read_bytes()).hexdigest() != review["draft_sha256"]:
        raise ValueError("Draft changed after review")
    receipt = import_pack(path)
    after = manifest_entries()
    review["corrected"] = [{k: v for k, v in r.items() if k != "steps_after"} for r in review["corrected"]]
    review.update(after_manifest_file_sha256=hashlib.sha256(encoded(after)).hexdigest(), import_receipt=receipt)
    del review["before_manifest"]
    (REPORT / "recipe-review.json").write_bytes(encoded(review))
    current = {identity(r) for r in current_recipes()}
    issued = {identity(r) for r in load_entries([*after["current"], *after["history"]])}
    assert all(r["runtime_id"] in current and r["previous_id"] in issued for r in review["corrected"])
    print(json.dumps({"published": len(review["corrected"])}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    prepare() if args.prepare else publish() if args.publish else parser.error("choose --prepare or --publish")
