"""Issue reviewed frozen-input amendments without rewriting any issued bytes.

Process decisions are explicit culinary decisions, never inferred from heat
words or a whole step's uses list. Timing values are author estimates, with
doneness/thaw checks in the instructions; these recipes are not cooking-tested.
"""
from __future__ import annotations

import argparse
import copy
from collections import Counter

from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    load_entries,
    manifest_entries,
    pack_diff,
    read_json,
    revoke_recipe,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

REPORT = ROOT.parents[3] / "docs/reviews/recipe-quality-and-planning-20261026"
OUTPUT = ROOT / "reviewed-frozen-20261026"
FROZEN = {"mango", "ananas", "avokado", "hallon", "blåbär", "jordgubbar",
          "lingon", "grönkål", "sparris", "okra", "gräslök", "koriander"}
HOT_FRUIT = {
    "mango": {"smako-indian-chicken-mango-skillet", "smako-thai-chicken-mango-cashew-glaze"},
    "ananas": {"smako-thai-beef-pineapple-glaze", "smako-thai-fish-pineapple-glaze"},
    "blåbär": {"smako-swedish-breakfast-berry-soup-cottage-dumplings",
               "smako-swedish-breakfast-whipped-blueberry-semolina-porridge",
               "smako-swedish-snack-apple-crumble", "smako-swedish-snack-cold-pressed-berry-bread-pudding"},
    "jordgubbar": {"smako-swedish-snack-layered-cream-cake-almond-cover"},
    "hallon": {"smako-swedish-snack-coconut-macaroons", "smako-swedish-snack-cold-pressed-berry-bread-pudding",
               "smako-swedish-snack-filled-fried-yeast-doughnut", "smako-swedish-snack-jam-thumbprint-shortbread"},
}
FRESH_SHAPES = {
    "smako-indian-fish-unripe-mango-puree-batons": ("mango", "green_mango", "Fast grön omogen mango, rå ätlig vikt utan skal och kärna"),
    "smako-thai-pounded-green-mango-tofu-salad": ("mango", "green_mango", "Fast grön omogen mango för tunna stavar, rå ätlig vikt utan skal och kärna"),
    "smako-thai-fluffy-crisp-fish-mango-rice": ("mango", "green_mango", "Fast grön mango för strimlor, rå ätlig vikt utan skal och kärna"),
    "smako-swedish-breakfast-breaded-avocado-egg-cream": ("avokado", "firm_avocado", "Fast färsk avokado för hela klyftor, rå ätlig vikt utan skal och kärna"),
    "smako-swedish-nori-rice-rolls-warm-smoked-salmon": ("avokado", "firm_avocado", "Fast färsk avokado för långa stavar, rå ätlig vikt utan skal och kärna"),
}
SKEWERS = {"smako-mexican-tofu-pinapple-skewers", "smako-thai-chicken-pineapple-skewers",
           "smako-thai-paneer-mango-skewers"}
OLD_PREFIXES = (
    "Väg upp fryst ", "Låt frukten tina helt i kylskåp, lämpligen över natten;",
    "Väg upp den frysta finhackade örten", "Lägg de uppvägda frysta hallonen",
    "Fördela de upphettade hallonen tunt", "Låt hallonen bli helt kalla i kylskåp",
)
# Literal edits to reviewed preparation instructions. This is not a heat detector.
REPLACEMENTS = {
    "repa och strimla grönkålsbladen": "väg upp fryst hackad grönkål och tillsätt den direkt från frysen vid upphettningen",
    "Skölj grönkålen och finstrimla bladen.": "Väg upp den frysta hackade grönkålen; den ska inte sköljas eller repas.",
    "finhacka gräslök": "väg upp fryst finhackad gräslök",
    "Finhacka gräslöken": "Väg upp den frysta finhackade gräslöken",
    "finhacka fryst finhackad koriander": "väg upp fryst finhackad koriander",
    "hacka koriandern": "väg upp den frysta finhackade koriandern",
    "Hacka koriandern": "Väg upp den frysta finhackade koriandern",
    "Hacka koriander och gurka": "Väg upp den frysta finhackade koriandern och hacka gurkan",
    "Finhacka tomat, koriander och rödlök": "Finhacka tomat och rödlök och tillsätt den frysta finhackade koriandern",
    "Finhacka tomat, gurka och koriander": "Finhacka tomat och gurka och tillsätt den frysta finhackade koriandern",
    "Finhacka de mjuka delarna av citrongräs, koriander, vitlök och ingefära mycket fint.": "Finhacka de mjuka delarna av citrongräs, vitlök och ingefära mycket fint. Väg upp den frysta finhackade koriandern och tillsätt med de övriga örterna.",
    "Skiva rädisorna tunt och skär gräslöken.": "Skiva rädisorna tunt och väg upp den frysta finhackade gräslöken.",
    "Skölj och finhacka gräslök och purjolök.": "Skölj och finhacka purjolöken och väg upp den frysta finhackade gräslöken.",
    "plocka örterna": "väg upp den frysta koriandern och plocka myntabladen",
    "Mosa färska hallon": "Mosa de kokta hallonen",
    "de färska blåbären": "de tinade blåbären",
    "färska blåbär": "tinade blåbär",
    "Ansa och skiva jordgubbarna.": "Skiva de helt tinade jordgubbarna och behåll all bärsaft.",
    "Ansa och dela jordgubbarna": "Dela de helt tinade jordgubbarna",
    "Ansa och skär jordgubbarna i bitar": "Skär de helt tinade jordgubbarna i bitar",
    "Ansa jordgubbarna och skär dem i bitar.": "Skär de helt tinade jordgubbarna i bitar; behåll bärsaften.",
    "Ansa och finhacka jordgubbarna.": "Lägg de frysta ansade jordgubbarna direkt i kastrullen och mosa dem när de mjuknat.",
    "Skala och tärna mangons fruktkött.": "Använd de helt tinade mangobitarna och all fruktsaft; dela bara större bitar vid behov.",
    "Skala och tärna mangons uppvägda fruktkött.": "Använd de helt tinade mangobitarna och all fruktsaft; vikten avser skalade urkärnade bitar.",
    "Skala och kärna ur mangon och väg det ätliga fruktköttet.": "Väg upp de frysta skalade mangobitarna. Använd en mixer avsedd för frysta livsmedel.",
    "Skala mangon och skär fruktköttet och gurkan i små bitar.": "Använd de tinade mangobitarna med all fruktsaft och skär gurkan i små bitar.",
    "tärna mangoköttet": "använd mangobitarna med all fruktsaft enligt upptiningssteget",
    "tärna den ansade ananasen": "använd de helt tinade ananasbitarna med all fruktsaft",
    "skölj eller ansa och skär mango i små bitar": "väg upp frysta skalade mangobitar och lägg dem direkt i den varma pannan i tillagningssteget",
    "skölj eller ansa och skär ananas i små bitar": "väg upp frysta skalade ananasbitar och lägg dem direkt i den varma pannan i tillagningssteget",
    "Dela avokadon och väg det råa ätliga fruktköttet utan skal och kärna.": "Använd de helt tinade skalade avokadotärningarna, vägda frysta, med all vätska.",
    "Dela avokadon, ta bort skal och kärna och tärna köttet.": "Använd de helt tinade skalade avokadotärningarna med all vätska.",
    "skär avokadoköttet i bitar": "använd de helt tinade skalade avokadotärningarna med all vätska",
    "skär sparrisen i korta bitar": "skär den tinade ansade sparrisen i korta bitar; behåll vätskan till pannan",
    "Skölj okran hel och torka mycket noga. Låt ligga på en ren duk 10 minuter så att ytan är helt torr. Ansa ändarna och skär sedan i tunna sneda skivor med torr kniv.": "Använd den tinade frysta okran. Torka ytan med rent papper, låt ligga på ren duk 10 minuter och skiva med torr kniv. Häll eventuell upptiningsvätska i pannan och låt den avdunsta före krispstekningen; ingen ätlig mängd kasseras.",
}


def strip_prefix(row):
    count = 0
    while row["steps"][count]["text"].startswith(OLD_PREFIXES):
        count += 1
    row["steps"] = row["steps"][count:]
    for step in row["steps"]:
        step["after"] = [d - count for d in step.get("after", []) if d > count]


def process(base, name):
    if base in FRESH_SHAPES and name == FRESH_SHAPES[base][0]:
        return "fresh_shape_required"
    if name in {"gräslök", "koriander"}:
        return "frozen_chopped_at_actual_use"
    if name == "grönkål":
        return "frozen_chopped_direct_heat"
    if name in {"sparris", "okra"}:
        return "thaw_before_cutting"
    if name == "hallon":
        return "boil_then_hot_process" if base in HOT_FRUIT[name] else "boil_then_chill"
    if base in HOT_FRUIT.get(name, set()):
        return "frozen_direct_heat"
    if base == "smako-swedish-snack-finely-blended-fruit-sorbet":
        return "frozen_blender"
    if base in SKEWERS:
        return "thaw_before_threading"
    return "thaw_cold_use"


def revise(original):
    row = copy.deepcopy(original)
    strip_prefix(row)
    base = row["base_id"]
    ingredients = [i for c in row["components"] for i in c["ingredients"]]
    names = {i["name"] for i in ingredients} & FROZEN
    modes = {name: process(base, name) for name in sorted(names)}
    for i in ingredients:
        name = i["name"]
        if name not in modes:
            continue
        if modes[name] == "fresh_shape_required":
            _, shape, label = FRESH_SHAPES[base]
            i.update(label=label, requirements=["pack:intake_all_shape_" + shape])
        elif name in {"gräslök", "koriander", "grönkål"}:
            i["label"] = name.capitalize() + ", fryst hackad, ätlig vikt vägd direkt ur förpackningen"
        else:
            i["label"] = name.capitalize() + ", fryst ansad ätlig mängd vägd före upptining; all saft används"
    for step in row["steps"]:
        for before, after in REPLACEMENTS.items():
            # Preserve the fresh preparation required for long avocado sticks.
            if modes.get("avokado") == "fresh_shape_required" and "avokado" in before:
                continue
            step["text"] = step["text"].replace(before, after)
        # The generic side-component template incorrectly washes frozen food.
        if step["text"].startswith("För komponenten ") and "Skölj och ansa " in step["text"]:
            opening, rest = step["text"].split("Skölj och ansa ", 1)
            prep, tail = rest.split(". ", 1)
            frozen_here = names & set(step["uses"])
            for name in sorted(frozen_here, key=len, reverse=True):
                prep = prep.replace(name + " och ", "").replace(" och " + name, "").replace(name + ", ", "").replace(", " + name, "")
                if prep == name:
                    prep = ""
            instruction = ("Skölj och ansa " + prep + ". ") if prep else ""
            detail = " ".join("Använd " + n + " enligt det separata beredningssteget." for n in sorted(frozen_here))
            step["text"] = opening + instruction + detail + " " + tail
        if (base in {"smako-thai-snack-tapioca-pearl-pudding", "smako-thai-snack-fruit-filled-glutinous-rice-dough"}
                and step["text"].startswith(("Skölj tapiokapärlorna", "Sjud på låg värme", "Rör ner sockret", "Vispa klibbigt rismjöl", "Ställ skålen i ånginsats"))):
            step["uses"] = [n for n in step["uses"] if n != "mango"]
        if base == "smako-swedish-snack-finely-blended-fruit-sorbet" and step["text"].startswith(("Koka sockret", "Låt sockerlagen")):
            step["uses"] = [n for n in step["uses"] if n != "mango"]
        if base == "smako-swedish-snack-layered-cream-cake-almond-cover" and step["text"].startswith(("Vispa mjölk", "Finmixa skalad mandel")):
            step["uses"] = [n for n in step["uses"] if n != "jordgubbar"]
    prefix = []
    decisions = []
    for name, mode in modes.items():
        amount = sum(i["quantity"] for i in ingredients if i["name"] == name)
        minutes = 0
        if mode == "fresh_shape_required":
            text = "Använd " + FRESH_SHAPES[base][2].lower() + ". Skala och kärna ur före vägning. Frysta tärningar uppfyller inte receptets formkrav."
            prefix.append({"text": text, "uses": [name], "minutes": 2})
        elif mode.startswith("boil_then_"):
            prefix.append({"text": "Lägg de uppvägda frysta hallonen i en kastrull. Koka upp under omrörning och håll hela bärmassan kokande minst en minut. Behåll all saft.", "uses": [name], "minutes": 5})
            if mode == "boil_then_chill":
                prefix.append({"text": "Fördela de kokta hallonen tunt i ren grund behållare och ställ i kylskåp. Behåll all saft.", "uses": [name], "minutes": 2})
                minutes = 120
                prefix.append({"text": "Låt hallonen bli helt kalla före kall fyllning eller blandning. Planera ungefär två timmar i kylskåp; förläng om de ännu är varma.", "uses": [name], "minutes": minutes, "passive": True})
        elif mode in {"thaw_cold_use", "thaw_before_threading", "thaw_before_cutting"}:
            minutes = 120 if amount <= 200 else 240
            prefix.append({"text": f"Väg upp fryst {name} och sprid i ett tunt lager i täckt kärl i kylskåp. Vikten avser ansad ätlig insats, inte skal eller kärnor; behåll all vätska.", "uses": [name], "minutes": 2})
            purpose = "före skärning och trädning på spett" if mode == "thaw_before_threading" else "före skärning" if mode == "thaw_before_cutting" else "före kall användning"
            prefix.append({"text": f"Låt {name} tina helt {purpose}. Planera cirka {minutes // 60} timmar i kylskåp i ett tunt lager; kontrollera att ingen hård fryst kärna finns kvar och förläng vid behov. Följ också förpackningens anvisningar. Använd hela mängden och all saft.", "uses": [name], "minutes": minutes, "passive": True})
        else:
            action = "Använd direkt från frysen i mixer avsedd för frysta livsmedel." if mode == "frozen_blender" else "Tillsätt direkt från frysen när ingrediensen används i instruktionen; den ska inte skalas, ansas eller hackas på nytt."
            prefix.append({"text": f"Väg upp fryst {name}. {action} Behåll hela den uppvägda ätliga mängden.", "uses": [name], "minutes": 1})
        decisions.append({"ingredient": name, "process": mode, "frozen_grams": amount, "passive_preparation_minutes": minutes})
    # Conservative serial dependencies: never imply an unreviewed overlap.
    for n, step in enumerate(prefix):
        step["after"] = [n] if n else []
    offset = len(prefix)
    for step in row["steps"]:
        step["after"] = [d + offset for d in step.get("after", [])] or [offset]
    row["steps"] = prefix + row["steps"]
    row["version"] = "1.0.2"
    row["notes"] += " Beredningsrättning 1.0.2: uttryckligt granskad produktform och faktisk användning; tider är författaruppskattningar, inte provlagning."
    return row, decisions


def main(do_import=False):
    REPORT.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    if (REPORT / "recipe-review.json").exists():
        reviewed = read_json(REPORT / "recipe-review.json")
        current = {identity(r): r for r in current_recipes()}
        if all(r["runtime_id"] in current for r in reviewed["recipes"]):
            assert all(current[r["runtime_id"]].design.content_sha256 == r["content_sha256"] for r in reviewed["recipes"])
            print({"already_issued_and_verified": len(reviewed["recipes"]), "no_historical_bytes_rewritten": True})
            return
    previous = read_json(ROOT.parents[3] / "docs/reviews/recipe-integration-all-20261026/all-recipes.json")
    affected = {r["runtime_id"]: r for r in previous["recipes"] if any(c["code"] == "explicit_frozen_product_variant_not_fresh_dry_alias" for c in r.get("changes", []))}
    rows = [r for p in sorted((ROOT / "reviewed-all-20261026").glob("batch-*/authoring.json")) for r in read_json(p)["recipes"] if r["base_id"] + ":" + r["version"] + ":" + r["variant_id"] in affected]
    assert len(rows) == 337
    manifest = manifest_entries()
    issued = load_entries([*manifest["current"], *manifest["history"]], ROOT)
    current = {identity(r): r for r in issued}
    revised, records = [], []
    for original in rows:
        old_id = original["base_id"] + ":" + original["version"] + ":" + original["variant_id"]
        row, decisions = revise(original)
        revised.append(row)
        records.append({"source_id": affected[old_id]["source_id"], "previous_id": old_id,
                        "runtime_id": row["base_id"] + ":1.0.2:" + row["variant_id"],
                        "status": "corrected", "processes": decisions,
                        "before": {k: getattr(current[old_id].design, k) for k in ("active_minutes", "waiting_minutes", "total_minutes")}})
    vocabulary = library_vocabulary(current_recipes(17))
    for start in range(0, len(revised), 100):
        batch = start // 100 + 1
        path = OUTPUT / f"batch-{batch:02}"
        path.mkdir(exist_ok=True)
        source = {"schema_version": "smako-recipe-authoring-v1", "pack_id": f"recipe-frozen-review-20261026-{batch:02}", "recipes": revised[start:start+100]}
        (path / "authoring.json").write_bytes(encoded(source))
        pack = {"schema_version": "smako-meal-pack-v1", "pack_id": source["pack_id"], "recipes": []}
        author = []
        for row in source["recipes"]:
            reviewed_vocabulary = dict(vocabulary)
            if row["base_id"] in FRESH_SHAPES:
                name, shape, _ = FRESH_SHAPES[row["base_id"]]
                reviewed_vocabulary[name + "|raw_edible"] = ("g", ["pack:intake_all_shape_" + shape])
            checked_pack, details = standardize({**source, "recipes": [row]}, reviewed_vocabulary, reviewed_at="2026-10-26")
            pack["recipes"].extend(checked_pack["recipes"])
            author.extend(details)
        standardized = path / "standardized.json"
        standardized.write_bytes(encoded(pack))
        validated = validate_pack_bytes(standardized.read_bytes())
        assert not validated["rejections"], validated["rejections"]
        (REPORT / f"author-{batch:02}.json").write_bytes(encoded(author))
        (REPORT / f"validate-{batch:02}.json").write_bytes(encoded({k: v for k, v in validated.items() if k != "recipes"}))
        (REPORT / f"diff-{batch:02}.json").write_bytes(encoded(pack_diff(validated)))
        for r, record in zip(validated["recipes"], records[start:start+100], strict=True):
            record["after"] = {k: getattr(r.design, k) for k in ("active_minutes", "waiting_minutes", "total_minutes")}
            record["content_sha256"] = r.design.content_sha256
        if do_import:
            (REPORT / f"import-{batch:02}.json").write_bytes(encoded(import_pack(standardized)))
    if do_import:
        revoked = [revoke_recipe(r["previous_id"], "Superseded by 1.0.2: explicit frozen/fresh product form, actual ingredient use and reviewed preparation dependencies.") for r in records]
        (REPORT / "revocations.json").write_bytes(encoded(revoked))
    report = {"schema": "smako-frozen-recipe-review-v1", "affected_variants": len(records),
              "affected_bases": len({r["base_id"] for r in revised}), "recipes": records,
              "process_counts": dict(Counter(p["process"] for r in records for p in r["processes"])),
              "timing_basis": "Authored estimates with explicit readiness checks; no cooking trial. Serial dependencies retained."}
    (REPORT / "recipe-review.json").write_bytes(encoded(report))
    print({k: v for k, v in report.items() if k != "recipes"})


def refine_fish(do_import=False):
    """The fish glaze uses the same direct-heat chunks as the beef glaze.

    Keep the locally issued 1.0.2 bytes too; fix only these three versions.
    """
    base = "smako-thai-fish-pineapple-glaze"
    report = read_json(REPORT / "recipe-review.json")
    records = [r for r in report["recipes"] if r["previous_id"].startswith(base + ":")]
    if all(":1.0.3:" in r["runtime_id"] for r in records):
        print({"fish_refinement_already_issued": len(records)})
        return
    rows = []
    for path in sorted((ROOT / "reviewed-all-20261026").glob("batch-*/authoring.json")):
        for original in read_json(path)["recipes"]:
            if original["base_id"] == base:
                row, _ = revise(original)
                row["version"] = "1.0.3"
                rows.append(row)
    source = {"schema_version": "smako-recipe-authoring-v1", "pack_id": "recipe-frozen-review-20261026-fish-03", "recipes": rows}
    directory = OUTPUT / "fish-refinement"
    directory.mkdir(exist_ok=True)
    (directory / "authoring.json").write_bytes(encoded(source))
    pack, author = standardize(source, library_vocabulary(current_recipes(17)), reviewed_at="2026-10-26")
    path = directory / "standardized.json"
    path.write_bytes(encoded(pack))
    checked = validate_pack_bytes(path.read_bytes())
    assert not checked["rejections"]
    (REPORT / "fish-author.json").write_bytes(encoded(author))
    (REPORT / "fish-validate.json").write_bytes(encoded({k: v for k, v in checked.items() if k != "recipes"}))
    (REPORT / "fish-diff.json").write_bytes(encoded(pack_diff(checked)))
    if do_import:
        (REPORT / "fish-import.json").write_bytes(encoded(import_pack(path)))
        revoked = []
        for row, recipe in zip(rows, checked["recipes"], strict=True):
            prior = base + ":1.0.2:" + row["variant_id"]
            revoked.append(revoke_recipe(prior, "Superseded by 1.0.3: frozen pineapple chunks are heated directly in the fish glaze; no cutting or threading requires thawing."))
            record = next(r for r in records if r["runtime_id"] == prior)
            record.update(runtime_id=identity(recipe), superseded_intermediate_id=prior,
                          content_sha256=recipe.design.content_sha256,
                          after={k: getattr(recipe.design, k) for k in ("active_minutes", "waiting_minutes", "total_minutes")})
            record["processes"] = revise(next(r for r in rows if r["variant_id"] == row["variant_id"]))[1]
        (REPORT / "fish-revocations.json").write_bytes(encoded(revoked))
        report["process_counts"] = dict(Counter(p["process"] for r in report["recipes"] for p in r["processes"]))
        (REPORT / "recipe-review.json").write_bytes(encoded(report))
    print({"fish_direct_heat_refinement": len(rows)})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--import", dest="do_import", action="store_true")
    p.add_argument("--fish-refinement-only", action="store_true")
    args = p.parse_args()
    (refine_fish if args.fish_refinement_only else main)(args.do_import)
