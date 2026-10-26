"""Account for every delivered variant, correct explicit issues, import only valid content.

All product/date/facts/personal qualification remains in the ordinary planner.
No source bytes, historical packages, default filters or prices are rewritten.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import re
from collections import Counter

from app.services.diet_policy import _MEAT_OR_FISH
from app.services.ingredient_normalizer import _search_text, canonicalize_ingredient_name
from app.services.meal_library_content import (
    ROOT,
    encoded,
    import_pack,
    pack_diff,
    read_json,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes
from build_reviewed_subset import correct

SOURCE = ROOT / "incoming/authoring-800-20261025"
OUTPUT = ROOT / "reviewed-all-20261026"
REPORT = ROOT.parents[3] / "docs/reviews/recipe-integration-all-20261026"
STRUCTURES = {
    "masa_pocket": "fyllda pannstekta majsknyten", "potatoroll": "bakad potatisrulle med fyllning",
    "breadpudding": "brödpudding med stanning och fyllning", "bakedpotato": "bakad potatis med varm fyllning",
    "dumpling": "fyllda kroppkakor av kokt potatis", "croquette": "panerade fyllda potatiskroketter",
    "roesti": "rårivna potatiskakor med fyllning", "tart": "förgräddad paj med stanning",
    "flatbread": "fyllda kavlade pannbröd", "flan": "vattenbadsbakad mjölk- och äggflan",
    "tortillabake": "bakad tortillastapel med fyllning", "waffle": "potatisvåfflor med varm fyllning",
    "masa_cake": "stekta majskakor med upphöjd kant och fyllning",
}
TITLE_FOODS = ["sotpotatis", "pumpa", "palsternacka", "aubergine", "broccoli", "blomkal", "morot",
               "purjolok", "salladslok", "spenat", "gronkal", "rodbeta", "kyckling", "lax", "torsk",
               "lamm", "tofu", "halloumi", "ricotta", "mynta", "koriander", "banan", "apple", "paron",
               "mango", "bulgur", "tamarind", "kikart"]


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def phases(row, changes):
    steps, ends = [], {}
    active_words = r"\b(?:blanda|skar|skolj|skala|vispa|lagg|hall|satt|forma|knada|riv|ansa|pensla|fordela)\b"
    for n, original in enumerate(row["steps"], 1):
        step = copy.deepcopy(original)
        step["after"] = [ends[d] for d in step.get("after", [])]
        text = _search_text(step["text"])
        if step.get("passive") and re.search(active_words, text) and step["minutes"] >= 5:
            numbers = {"en": 1, "ett": 1, "tva": 2, "tre": 3, "fyra": 4, "fem": 5,
                       "sex": 6, "atta": 8, "tio": 10, "tolv": 12, "femton": 15,
                       "tjugo": 20, "trettio": 30}
            stated = []
            for value, unit in re.findall(r"\b(\d+|en|ett|tva|tre|fyra|fem|sex|atta|tio|tolv|femton|tjugo|trettio) (minuter|timme|timmar)\b", text):
                value = int(value) if value.isdigit() else numbers[value]
                stated.append(value * (60 if unit.startswith("timm") else 1))
            passive = sum(stated) if stated else max(1, step["minutes"] - 3)
            active = max(1, step["minutes"] - passive)
            step.update(minutes=active, passive=False,
                        text="Förbered och påbörja momentet: " + step["text"])
            steps.append(step)
            steps.append({"text": "Låt momentet fortsätta tills den angivna tiden och färdighetskontrollen är uppnådda.",
                          "uses": list(step["uses"]), "minutes": passive, "passive": True, "after": [len(steps)]})
            changes.append({"code": "separate_active_setup_and_passive_phase", "source_step": n,
                            "active_minutes": active, "passive_minutes": passive})
        else:
            steps.append(step)
        ends[n] = len(steps)
    row["steps"] = steps


def frozen_preparation(row, ingredients, changes):
    prefix = []
    fruit = []
    for i in ingredients:
        if i["name"] not in {"mango", "hallon", "blåbär", "jordgubbar", "ananas", "gräslök", "avokado", "koriander", "lingon"}:
            continue
        hot = any(i["name"] in s["uses"] and re.search(r"koka|sjud|stek|baka|grädda|rosta", s["text"], re.IGNORECASE) for s in row["steps"])
        if i["name"] == "hallon":
            prefix.append({"text": "Lägg de uppvägda frysta hallonen i en liten kastrull. Värm under omrörning till ett ordentligt uppkok och håll hela bärmassan kokande minst en minut. Behåll all fruktsaft.",
                           "uses": ["hallon"], "minutes": 5})
            if not hot:
                prefix.extend([
                    {"text": "Fördela de upphettade hallonen tunt i en ren grund behållare och ställ i kylskåp. Behåll all fruktsaft till receptet.", "uses": ["hallon"], "minutes": 2, "after": [len(prefix)]},
                    {"text": "Låt hallonen bli helt kalla i kylskåp innan de blandas med kalla ingredienser; räkna med ungefär två timmar.", "uses": ["hallon"], "minutes": 120, "passive": True, "after": [len(prefix)+1]},
                ])
            changes.append({"code": "frozen_raspberries_boiled_and_if_needed_chilled",
                            "source": "https://fragor.livsmedelsverket.se/org/livsmedelsverket/d/varfor-finns-det-virus-pa-importerade-frysta-bar/"})
        elif not hot and i["name"] in {"gräslök", "koriander"}:
            prefix.append({"text": f"Väg upp den frysta finhackade örten ({i['name']}). Blanda den direkt i receptets kalla sås eller fyllning och låt den tina där. Använd hela den uppvägda mängden.", "uses": [i["name"]], "minutes": 2})
            changes.append({"code": "explicit_frozen_chive_use"})
        elif not hot:
            fruit.append(i["name"])
    if fruit:
        names = ", ".join(sorted(set(fruit)))
        prefix.extend([
            {"text": f"Väg upp fryst {names} i en täckt skål och ställ i kylskåp. Vikten avser den ätliga frukten utan skal eller kärnor.", "uses": sorted(set(fruit)), "minutes": 2},
            {"text": "Låt frukten tina helt i kylskåp, lämpligen över natten; räkna med cirka åtta timmar. Behåll fruktsaften och använd den tillsammans med frukten i receptet.", "uses": sorted(set(fruit)), "minutes": 480, "passive": True, "after": [len(prefix)+1]},
        ])
        changes.append({"code": "authored_frozen_fruit_thaw_chain", "ingredients": sorted(set(fruit)), "waiting_minutes": 480})
    if prefix:
        for n, step in enumerate(prefix, 1):
            if n > 1:
                step["after"] = sorted(set(step.get("after", [])) | {n-1})
        offset = len(prefix)
        for step in row["steps"]:
            step["after"] = [d+offset for d in step.get("after", [])] or [offset]
        row["steps"] = prefix + row["steps"]


def build(do_import=False):
    OUTPUT.mkdir(exist_ok=True)
    REPORT.mkdir(exist_ok=True, parents=True)
    baseline = ROOT / "library-manifest.json"
    if not (OUTPUT / "baseline-307-manifest.json").exists():
        (OUTPUT / "baseline-307-manifest.json").write_bytes(baseline.read_bytes())
    vocabulary = library_vocabulary(current_recipes(17))
    previous = read_json(REPORT.with_name("recipe-integration-800-20261025") / "summary.json")["corrected_and_imported"]["source_to_runtime_id"]
    groups = read_json(SOURCE / "smako-dubblettgranskning.json")["supplementary_process_reviews"]["mexican_swedish/quality-review.json"]["remaining_groups"]
    mapping = {base: ("smako-intake-" + group["structure"].replace("_", "-"), STRUCTURES[group["structure"]])
               for group in groups for base in group["base_ids"]}
    existing = {r.design.base_id: r for r in current_recipes(13)}
    accepted, records = [], []
    for path in sorted(SOURCE.glob("paket/*.json")):
        file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        for index, original in enumerate(read_json(path)["recipes"]):
            source_id = original["base_id"] + ":" + original["version"] + ":" + original["variant_id"]
            record = {"source_id": source_id, "source_file": path.relative_to(SOURCE).as_posix(),
                      "source_index": index, "source_sha256": file_sha, "source_recipe_sha256": sha(original)}
            if source_id in previous:
                records.append({**record, "status": "already_imported", "runtime_id": previous[source_id], "blockers": []})
                continue
            row, prior_changes = correct(copy.deepcopy(original), vocabulary)
            changes = [{"code": "prior_review_correction", "detail": c} for c in prior_changes]
            blockers = []
            if row["base_id"] == "smako-swedish-beef-mushroom-pirog" and row["variant_id"] == "simple":
                row["name"] = row["name"].replace(" och purjolök", "")
                changes.append({"code": "remove_absent_leek_from_title_no_ingredient_substitution"})
            if row["base_id"] == "smako-italian-snack-coffee-dipped-sponge-layer-cup":
                # Both full source variants bake the weighed raw egg into the
                # sponge at 190 C / at least 72 C, then cool and assemble it.
                # The cheese cream contains no raw egg. Preserve that chain.
                row["method"] = "oven"
                changes.append({"code": "reviewed_baked_egg_sponge_then_cold_assembly"})
            if row["base_id"] in mapping:
                source_base = row["base_id"]
                row["base_id"], row["family"] = mapping[source_base]
                row["variant_id"] = hashlib.sha256(source_base.encode()).hexdigest()[:8] + "-" + row["variant_id"]
                changes.append({"code": "shared_base_and_family", "base_id": row["base_id"]})
            if original["base_id"] == "smako-thai-salmon-peanut-cool-noodle-salad":
                row.update(base_id="smako-thai-sour-noodle-salad", variant_id="salmon-" + original["variant_id"], version="1.0.1",
                           family=existing["smako-thai-sour-noodle-salad"].design.family)
            if original["base_id"] == "smako-indian-breakfast-bulgur-lentil-breakfast-pilaf":
                row.update(base_id="smako-breakfast-lentil-carrot-porridge", variant_id="bulgur-" + original["variant_id"],
                           family=existing["smako-breakfast-lentil-carrot-porridge"].design.family)
            all_ingredients = [i for c in row["components"] for i in c["ingredients"]]
            for i in all_ingredients:
                canonical = canonicalize_ingredient_name(i["name"])
                if canonical != i["name"]:
                    previous_name = i["name"]
                    i["name"] = canonical
                    for step in row["steps"]:
                        step["uses"] = [canonical if name == previous_name else name for name in step["uses"]]
                if i["name"] in {"solrosfrön", "pumpafrön"}:
                    previous_name = i["name"]
                    i["name"] = {"solrosfrön": "solroskärnor", "pumpafrön": "pumpakärnor"}[previous_name]
                    i["label"] = i["name"].capitalize() + ", naturella skalade ätliga kärnor, vikt som såld"
                    for step in row["steps"]:
                        step["uses"] = [i["name"] if name == previous_name else name for name in step["uses"]]
                        step["text"] = step["text"].replace(previous_name, i["name"])
                    changes.append({"code": "authored_edible_kernel_variant_not_global_alias", "from": previous_name, "to": i["name"]})
                canonical = canonicalize_ingredient_name(i["name"])
                key = canonical + "|" + i["form"]
                if key not in vocabulary:
                    blockers.append({"code": "missing_ingredient_evidence", "identity": key, "required_unit": i["unit"],
                                     "label": i.get("label", ""), "quantity": i["quantity"]})
                    continue
                if canonical in {"koriander", "grönkål", "mango", "gräslök", "hallon", "blåbär", "jordgubbar", "ananas", "avokado", "sparris", "okra", "lingon"}:
                    i["label"] = canonical.capitalize() + ", fryst ätlig insatsvikt (g), inte hel frukt med skal/kärnor"
                    for step in row["steps"]:
                        step["text"] = step["text"].replace("färsk koriander", "fryst finhackad koriander").replace("Färsk koriander", "Fryst finhackad koriander")
                    changes.append({"code": "explicit_frozen_product_variant_not_fresh_dry_alias", "identity": key})
                requirements = set(i.get("requirements", vocabulary[key][1]))
                label = _search_text(i.get("label", ""))
                if canonical == "kyckling" and "brost" in label:
                    requirements.add("pack:chicken_breast")
                if canonical == "kyckling" and "larfile" in label:
                    requirements.add("pack:chicken_thigh")
                if canonical == "bönor" and "vita" in label:
                    requirements.add("white_beans")
                if canonical == "oliver":
                    requirements.add("pitted")
                if canonical in {"nötkött", "lammkött"}:
                    long_heat = any(i["name"] in s["uses"] and s["minutes"] >= 60
                                    and re.search(r"bräser|sjud|långkok|ugn|baka", s["text"], re.IGNORECASE) for s in row["steps"])
                    requirements.add("pack:" + ("beef" if canonical == "nötkött" else "lamb")
                                     + ("_braising_cut" if long_heat else "_quick_cut"))
                    changes.append({"code": "explicit_meat_cut_for_actual_cooking", "identity": key,
                                    "cooking": "braising" if long_heat else "quick"})
                i["requirements"] = sorted(requirements)
            text = " ".join(s["text"] for s in row["steps"])
            if row["method"] in {"cold_assembly", "refrigerated_assembly", "salad"}:
                raw_animals = {i["name"] for i in all_ingredients if i["form"] == "raw_edible" and i["name"] in _MEAT_OR_FISH}
                heated = {name for name in raw_animals if any(name in s["uses"] and re.search(r"stek|fräs|koka|sjud|baka|grädda", s["text"], re.IGNORECASE) for s in row["steps"])}
                if raw_animals and heated == raw_animals:
                    row["method"] = "oven" if re.search(r"ugnen|baka|grädda", text, re.IGNORECASE) else "pan" if re.search(r"stek|fräs", text, re.IGNORECASE) else "pot"
                    changes.append({"code": "actual_heating_method_retained_raw_inputs", "method": row["method"]})
            ingredient_text = _search_text(" ".join(i["name"] + " " + i.get("label", "") for i in all_ingredients))
            title = _search_text(row["name"])
            for food in TITLE_FOODS:
                if re.search(r"\b" + food, title) and food not in ingredient_text:
                    blockers.append({"code": "title_promises_absent_ingredient", "word": food, "title": row["name"]})
            frozen_preparation(row, all_ingredients, changes)
            phases(row, changes)
            row["notes"] = ("Systematiskt innehållsgranskad utvecklingsimport 2026-10-26. AI-författad, inte provlagad. "
                "Ingredienser, användning, stegberoenden, tidskedja, råvaruform, namngivna processgrupper och diet kontrollerade. "
                f"Källoriginal {path.name}, rad {index}, SHA-256 {file_sha}. Produktköp, diet, näring, allergener och eko prövas fortsatt för faktiska produkter och användarval.")
            runtime_id = row["base_id"] + ":" + row["version"] + ":" + row["variant_id"]
            if not blockers:
                try:
                    pack, _details = standardize({"schema_version": "smako-recipe-authoring-v1", "pack_id": "intake-all-analysis", "recipes": [row]}, vocabulary, reviewed_at="2026-10-26")
                    checked = validate_pack_bytes(encoded(pack))
                    if checked["rejections"]:
                        blockers.extend({"code": "content_validation", "detail": r} for r in checked["rejections"])
                except (ValueError, TypeError, KeyError) as exc:
                    blockers.append({"code": "authoring_validation", "detail": str(exc)})
            record.update(runtime_id=runtime_id, changes=changes, blockers=blockers,
                          corrected_recipe_sha256=sha(row), status="blocked" if blockers else "accepted")
            records.append(record)
            if not blockers:
                accepted.append(row)
    packages = []
    for start in range(0, len(accepted), 150):
        n = start // 150 + 1
        directory = OUTPUT / f"batch-{n:02}"
        directory.mkdir(exist_ok=True)
        source = {"schema_version": "smako-recipe-authoring-v1", "pack_id": f"recipe-intake-all-20261026-{n:02}", "recipes": accepted[start:start+150]}
        (directory / "authoring.json").write_bytes(encoded(source))
        pack, author = standardize(source, vocabulary, reviewed_at="2026-10-26")
        path = directory / "standardized.json"
        path.write_bytes(encoded(pack))
        checked = validate_pack_bytes(path.read_bytes())
        assert not checked["rejections"]
        (REPORT / f"author-{n:02}.json").write_bytes(encoded(author))
        (REPORT / f"validate-{n:02}.json").write_bytes(encoded({k:v for k,v in checked.items() if k != "recipes"}))
        (REPORT / f"diff-{n:02}.json").write_bytes(encoded(pack_diff(checked)))
        imported = import_pack(path) if do_import else None
        if imported:
            (REPORT / f"import-{n:02}.json").write_bytes(encoded(imported))
        packages.append({"pack_id": source["pack_id"], "recipes": len(source["recipes"]), "standardized_bytes": path.stat().st_size})
    assert len(records) == 2200
    status = Counter(r["status"] for r in records)
    summary = {"schema": "smako-all-recipe-integration-v1", "source_variants": 2200,
               "status": dict(status), "packages": packages, "all_source_ids_accounted": True,
               "blocker_counts": dict(Counter(b["code"] for r in records for b in r["blockers"])),
               "culinary_group_decisions": [{**g, "decision": "shared_base_and_family", "new_base_id": "smako-intake-" + g["structure"].replace("_", "-"),
                   "reason": "Full source constructions share dough/binder/formation and final cooking; filling/protein/flavour changes are variants."} for g in groups],
               "recipes": records}
    (REPORT / "all-recipes.json").write_bytes(encoded(summary))
    print({"statuses": dict(status), "blockers": summary["blocker_counts"], "packages": len(packages)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import", dest="do_import", action="store_true")
    build(parser.parse_args().do_import)
