"""Reproduce the explicitly reviewed first subset; never import or approve products.

Original delivery bytes are read only. The review and corrected authoring pack
are written separately. Run author/validate/diff/import/prepare afterwards.
"""
from __future__ import annotations

import argparse
import copy
import hashlib

from app.services.meal_library_content import ROOT, encoded, read_json, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

SOURCE = ROOT / "incoming/authoring-800-20261025"
OUTPUT = ROOT / "reviewed-800-20261025"
BASES = {
    "smako-greek-beef-cumin-tomato-oval-balls",
    "smako-greek-aubergine-chickpea-onion-boats",
    "smako-italian-chicken-spinach-roulades",
    "smako-italian-broccoli-almond-whitebean-pasta",
    "smako-mexican-cheese-stuffed-peppers",
    "smako-indian-lentil-crepes-potato",
    "smako-indian-aubergine-chickpea-bread-mash",
    "smako-swedish-salmon-cakes-potatoes",
    "smako-thai-chicken-sweetcorn-soup",
    "smako-thai-chicken-potstickers-flour-lace",
    "smako-thai-breakfast-clear-rice-tofu-breakfast-soup",
    "smako-swedish-breakfast-french-toast-apple-quark",
    "smako-greek-snack-coarse-olive-caper-tapenade",
    "smako-swedish-snack-cottage-cheese-apple-cake",
    "smako-swedish-chicken-cold-mustard-bread",
    "smako-thai-salmon-peanut-cool-noodle-salad",
}
BATCH_TWO = {
    "smako-italian-breakfast-chickpea-flour-oven-flatbread",
    "smako-mexican-breakfast-baked-tortilla-egg-nest",
    "smako-thai-breakfast-steamed-egg-custard-peas",
    "smako-greek-snack-garlic-potato-emulsion",
}


def split_steps(row, mode):
    new, ends = [], {}
    for n, original in enumerate(row["steps"], 1):
        step = copy.deepcopy(original)
        step["after"] = [ends[d] for d in step.get("after", [])]
        if n == 1 and mode == "potstickers":
            step.update(minutes=7, passive=False, text="Blanda mjölet och degens salt. Arbeta in 170 ml vatten till en fast men smidig deg. Knåda fem minuter.")
            new.append(step)
            new.append({"text": "Låt degen vila övertäckt i 25 minuter så att mjölet hinner ta upp vattnet.",
                        "uses": step["uses"], "minutes": 25, "passive": True, "after": [len(new)]})
        elif n == 1 and mode == "soup":
            step.update(minutes=3, passive=False, text="Skölj riset. Lägg det i en kastrull med 100 ml vatten och koka upp under lock.")
            new.append(step)
            new.append({"text": "Sänk värmen och sjud riset under lock cirka 15 minuter tills det är mjukt men grynen fortfarande hela. Följ förpackningens längre tid vid behov.",
                        "uses": step["uses"], "minutes": 15, "passive": True, "after": [len(new)]})
        elif n == 3 and mode == "chickpea":
            step.update(minutes=2, passive=False, text="Sätt ugnen på 230 °C. Ställ in en grund metallform, cirka 20 cm bred.")
            new.append(step)
            new.append({"text": "Låt ugnen och formen bli helt varma, cirka 15 minuter.", "uses": [],
                        "minutes": 15, "passive": True, "after": [len(new)]})
            new.append({"text": "Ta ut formen med grytlappar. Häll hela mängden olja i formen, rör smeten och häll i ett tunt lager, högst en centimeter. Ställ tillbaka formen i ugnen.",
                        "uses": step["uses"], "minutes": 2, "after": [len(new)]})
            new.append({"text": "Baka cirka 25 minuter tills kanterna har fått färg och mitten är fast och helt genomgräddad.",
                        "uses": step["uses"], "minutes": 25, "passive": True, "after": [len(new)]})
        elif n == 2 and mode == "egg":
            step.update(minutes=3, passive=False, text="Häll 700 ml vatten i en kastrull och sätt i en ånginsats ovanför vattenytan. Koka upp och ställ skålen i insatsen. Lägg på kastrullens lock.")
            new.append(step)
            new.append({"text": "Ånga försiktigt utan häftig kokning i cirka 18 minuter tills äggstanningen har satt sig.",
                        "uses": step["uses"], "minutes": 18, "passive": True, "after": [len(new)]})
        elif n == 2 and mode == "potato":
            step.update(text="Koka potatisen helt mjuk, cirka femton minuter.")
            new.append(step)
            new.append({"text": "Häll av potatisen och låt den ånga av i kastrullen.", "uses": step["uses"],
                        "minutes": 2, "after": [len(new)]})
        else:
            new.append(step)
        if n == 2 and mode == "potstickers":
            new[-1]["text"] = new[-1]["text"].replace(" Låt svalna innan degskalen fylls.", "")
            new.append({"text": "Bred ut fyllningen tunt på en ren tallrik och låt den svalna i cirka 15 minuter innan knytena fylls.",
                        "uses": step["uses"], "minutes": 15, "passive": True, "after": [len(new)]})
        ends[n] = len(new)
    row["steps"] = new


def correct(original, vocabulary):
    row, changes = copy.deepcopy(original), []
    base = row["base_id"]
    if base in {"smako-swedish-chicken-cold-mustard-bread", "smako-thai-salmon-peanut-cool-noodle-salad"}:
        row["method"] = "pan"
        changes.append("Hot method reflects explicit raw-animal cooking step; input remains raw_edible.")
    if base == "smako-swedish-chicken-cold-mustard-bread":
        row["name"] = row["name"].replace("rågbröd", "bröd")
        changes.append("Title no longer promises rye when actual product requirement is plain bread.")
    if base == "smako-mexican-cheese-stuffed-peppers":
        row["name"] = row["name"].replace("i tomatsås med bönris", "med bönris")
        changes.append("Removed tomato sauce from title: recipe contains no tomato.")
    if base == "smako-greek-beef-cumin-tomato-oval-balls":
        row["steps"][1]["text"] = "Arbeta den kalla nötfärsen kort med sked så att den blir sammanhängande. Håll råvaran kall och diska redskapen efteråt."
        row["steps"][4]["text"] = row["steps"][4]["text"].replace("små bollar, cirka 2 cm stora", "avlånga små färsbullar, cirka 4 cm långa och 2 cm tjocka")
        changes.append("Existing mince is worked briefly; oval shape now matches title; temperature checks retained.")
    if base == "smako-italian-broccoli-almond-whitebean-pasta":
        row["steps"][4]["text"] = "Värm rapsoljan i grytan. Fräs broccolin under omrörning på medelvärme tills den börjar mjukna." + (
            " Rör ner vitlöken den sista minuten utan att låta den brännas." if row["variant_id"] != "simple" else "")
        row["steps"][5]["text"] = "Rör ner bönor, mandel och salt och 400 ml vatten. Koka upp under omrörning."
        row["steps"][7]["text"] = "Mixa broccoli-bönkrämen slät med stavmixer; håll mixerklockan under ytan för att undvika stänk."
        changes.append("Broccoli is added once; garlic fries briefly; sauce is named correctly.")
    if base == "smako-thai-chicken-potstickers-flour-lace":
        split_steps(row, "potstickers")
        changes.append("Split 7 active + 25 passive dough minutes; added 15-minute filling cooling dependency.")
    if base == "smako-thai-breakfast-clear-rice-tofu-breakfast-soup":
        split_steps(row, "soup")
        changes.append("Separated 3 active wash/boil minutes from 15 passive simmer minutes.")
    if base == "smako-italian-breakfast-chickpea-flour-oven-flatbread":
        split_steps(row, "chickpea")
        changes.append("Separated active oven loading, 15-minute preheat and 25-minute bake; no waiting omitted.")
    if base == "smako-thai-breakfast-steamed-egg-custard-peas":
        row["steps"][0]["text"] = row["steps"][0]["text"].replace("; pressa ur spenat om den ingår", "")
        split_steps(row, "egg")
        changes.append("Removed absent spinach; separated active steamer setup from passive steaming.")
    if base == "smako-greek-snack-garlic-potato-emulsion":
        split_steps(row, "potato")
        changes.append("Separated active draining from passive potato cooking.")
    for component in row["components"]:
        for item in component["ingredients"]:
            key = item["name"] + "|" + item["form"]
            if key not in vocabulary:
                continue
            unit = item.get("unit", vocabulary[key][0])
            item["unit"] = unit
            if item["form"] == "as_sold" and ("vikt" in item.get("label", "") or "volym" in item.get("label", "") or unit == "ml"):
                old = item.get("label")
                item["label"] = item["name"].capitalize() + ", " + ("volym som såld (ml)" if unit == "ml" else "vikt som såld (g)")
                if old != item["label"]:
                    changes.append("Display basis follows explicit " + unit + " for " + item["name"] + "; no density conversion.")
            requirements = set(item.get("requirements", vocabulary[key][1]))
            if item["name"] == "bönor" and "vita" in item.get("label", "").casefold():
                requirements.add("white_beans")
            if item["name"] == "kyckling" and base == "smako-italian-chicken-spinach-roulades":
                requirements.add("pack:chicken_breast")
            if item["name"] == "oliver":
                requirements.add("pitted")
            if requirements != set(vocabulary[key][1]) or "requirements" in item:
                item["requirements"] = sorted(requirements)
    return row, sorted(set(changes))


def build(output=OUTPUT, *, batch=1):
    bases = BASES if batch == 1 else BATCH_TWO
    pack_id = "recipe-intake-reviewed-20261025" + ("-02" if batch == 2 else "")
    vocabulary = library_vocabulary(current_recipes())
    accepted, reviews, held = [], [], []
    for path in sorted(SOURCE.glob("paket/*.json")):
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        relative = path.relative_to(SOURCE).as_posix()
        for index, original in enumerate(read_json(path)["recipes"]):
            if original["base_id"] not in bases:
                continue
            row, changes = correct(original, vocabulary)
            row["notes"] = ("Innehållsgranskad utvecklingsleverans 2026-10-25. AI-författad och inte provlagad. "
                f"Källoriginal: {relative} SHA-256 {sha}. Produktköp, mängdomvandling, diet, näring, "
                "allergener och ekologiskt kvalificeras separat för faktiska produkter och användarval.")
            identity = row["base_id"] + ":" + row.get("version", "1.0.0") + ":" + row["variant_id"]
            try:
                pack, details = standardize({"schema_version": "smako-recipe-authoring-v1",
                    "pack_id": pack_id, "recipes": [row]}, vocabulary, reviewed_at="2026-10-25")
                checked = validate_pack_bytes(encoded(pack))
                if checked["rejections"]:
                    raise ValueError(str(checked["rejections"]))
            except ValueError as exc:
                held.append({"id": identity, "reason": str(exc)})
                continue
            accepted.append(row)
            reviews.append({"id": identity, "source_file": relative, "source_index": index,
                "source_sha256": sha, "source_recipe_sha256": hashlib.sha256(encoded(original)).hexdigest(),
                "reviewed_recipe_sha256": hashlib.sha256(encoded(row)).hexdigest(), "changes": changes,
                "decision": "content_reviewed_not_cooked", "authoring": details[0]})
    output.mkdir(parents=True, exist_ok=True)
    (output / "authoring.json").write_bytes(encoded({"schema_version": "smako-recipe-authoring-v1",
        "pack_id": pack_id, "recipes": accepted}))
    (output / "REVIEW.json").write_bytes(encoded({"schema_version": "smako-content-review-v1", "reviewed": reviews, "held": held}))
    print(f"accepted={len(accepted)} bases={len({r['base_id'] for r in accepted})} held={len(held)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    build(OUTPUT if args.batch == 1 else OUTPUT / "batch-02", batch=args.batch)
