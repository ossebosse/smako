"""Issue separate egg-separation versions, preserving every original operand."""

import argparse
import copy
import hashlib

from app.services.egg_preparation import COMPONENTS, METHOD, OPERAND, reference
from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    load_entries,
    manifest_entries,
    read_json,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

OUTPUT = ROOT / "reviewed-egg-separation-20261028"
REPORT = ROOT.parents[3] / "docs/reviews/egg-preparation-20261028"


def issue_reviewed_preparation(do_import, *, output, report, method, operand, source,
                               eligible_names, instruction, pack_id):
    """Use the existing authoring/import path for a reviewed preparation."""
    OUTPUT, REPORT = output, report
    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    if (REPORT / "recipe-review.json").exists():
        reviewed = read_json(REPORT / "recipe-review.json")
        manifest = manifest_entries()
        issued = {identity(r): r for r in load_entries([*manifest["current"], *manifest["history"]])}
        for record in reviewed["corrected"]:
            assert issued[record["previous_id"]].design.content_sha256 == record["previous_sha256"]
            assert issued[record["runtime_id"]].design.content_sha256 == record["content_sha256"]
        print({"already_issued": len(reviewed["corrected"]), "all_issued_hashes_verified": True, "no_bytes_rewritten": True})
        return
    active = {identity(r): r for r in current_recipes()}
    authoring = {}
    for path in ROOT.rglob("authoring.json"):
        if path.parent == OUTPUT:
            continue
        for row in read_json(path)["recipes"]:
            key = row["base_id"] + ":" + row["version"] + ":" + row["variant_id"]
            if key in active:
                authoring[key] = row
    authors, standardized, review = [], [], []
    for key, original in sorted(authoring.items()):
        runtime = active[key]
        names = eligible_names(runtime)
        if not names:
            continue
        assert all(i.form == "raw_edible" and i.unit == "g" for i in runtime.ingredients if i.canonical_name in names)
        row = copy.deepcopy(original)
        vocabulary = library_vocabulary([runtime])
        for part in row["components"]:
            for ingredient in part["ingredients"]:
                if ingredient["name"] in names:
                    assert operand not in ingredient["requirements"]
                    ingredient["requirements"] = [*ingredient["requirements"], operand]
                    vocabulary[ingredient["name"] + "|raw_edible"] = ("g", ingredient["requirements"])
        for step in row["steps"]:
            step["after"] = [n + 1 for n in step.get("after", [])] or [1]
        row["steps"].insert(0, {"after": [], "minutes": 3, "uses": sorted(names),
            "text": instruction})
        row["version"] = ".".join([*row["version"].split(".")[:-1], str(int(row["version"].split(".")[-1]) + 1)])
        row["notes"] += " Separat granskad beredningsversion 2026-10-28: " + method + "; " + source["source"]["url"]
        pack, _ = standardize({"schema_version": "smako-recipe-authoring-v1",
            "pack_id": pack_id, "recipes": [row]}, vocabulary, reviewed_at="2026-10-28")
        authors.append(row)
        standardized.extend(pack["recipes"])
        review.append({"previous_id": key, "previous_sha256": runtime.design.content_sha256,
                       "components": sorted(names), "quantities_preserved": True})
    assert review, "No eligible authored recipes"
    (OUTPUT / "authoring.json").write_bytes(encoded({"schema_version": "smako-recipe-authoring-v1",
        "pack_id": pack_id, "recipes": authors}))
    path = OUTPUT / "standardized.json"
    path.write_bytes(encoded({"schema_version": "smako-meal-pack-v1", "pack_id": pack_id, "recipes": standardized}))
    checked = validate_pack_bytes(path.read_bytes())
    assert not checked["rejections"], checked["rejections"]
    for record, recipe in zip(review, checked["recipes"], strict=True):
        before = active[record["previous_id"]]
        assert len(before.ingredients) == len(recipe.ingredients)
        for old, new in zip(before.ingredients, recipe.ingredients, strict=True):
            if old.canonical_name in record['components']:
                assert new == old.model_copy(update={"product_requirements": (*old.product_requirements, operand)})
            else:
                assert old == new
        assert recipe.design.active_minutes == before.design.active_minutes + 3
        assert recipe.design.total_minutes == before.design.total_minutes + 3
        assert recipe.design.waiting_minutes == before.design.waiting_minutes
        record.update(runtime_id=identity(recipe), content_sha256=recipe.design.content_sha256,
                      active_minutes=recipe.design.active_minutes, total_minutes=recipe.design.total_minutes)
    if do_import:
        before_manifest = hashlib.sha256((ROOT / "library-manifest.json").read_bytes()).hexdigest()
        (REPORT / "import.json").write_bytes(encoded(import_pack(path)))
        (REPORT / "recipe-review.json").write_bytes(encoded({"method": method, "corrected": review,
            "originals_preserved": True, "source": source, "before_manifest_file_sha256": before_manifest,
            "after_manifest_file_sha256": hashlib.sha256((ROOT / "library-manifest.json").read_bytes()).hexdigest()}))
    print({"reviewed_versions": len(review), "imported": do_import})


def main(do_import):
    issue_reviewed_preparation(do_import, output=OUTPUT, report=REPORT, method=METHOD, operand=OPERAND,
        source=reference(), eligible_names=lambda r: {i.canonical_name for i in r.ingredients if i.canonical_name in COMPONENTS},
        pack_id="egg-separation-review-20261028",
        instruction="Knäck rena hönsägg och separera gula och vita utan tillsatser. Väg de råa delarna var för sig utan skal till receptets angivna gram. Inköpets utbytesförhållande är en populationsuppskattning; komplettera vid för litet faktiskt utbyte och bokför uppmätt insats, gula och vita. Oanvänd gula/vita är separata rester. Följ förpackningens hantering; ingen hållbarhet är fastställd här. De tre aktiva minuterna är en författaruppskattning.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--import", dest="do_import", action="store_true")
    main(parser.parse_args().do_import)
