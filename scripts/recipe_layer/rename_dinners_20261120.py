"""Owner decision 2026-11-20: dinners carry the dish's real name.

Only `name` changes. Amounts, forms, steps, timing and purchase inputs are
compared with the issued version by the language review's pair check, and old
packs stay immutable. Run --prepare, read recipe-review.json, then --publish.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json

import rewrite_recipe_language as first
from app.services.meal_library_content import encoded, identity, load_entries, manifest_entries, validate_pack_bytes
from app.services.recipe_library import current_recipes

REPORT = first.ROOT.parents[3] / "docs/reviews/recipe-names-20261120"
WORK = first.ROOT.parents[3] / ".local/recipe-names-20261120"
NOTE = " Namngranskning 2026-11-20: maträttens riktiga namn på vanlig svenska; endast namnet ändrat."


def rewrite_recipe(original, overrides):
    row = copy.deepcopy(original)
    # The original core library (complete-dinners-v1, pinned by hash and without
    # pack timing) is renamed with its own next library version, not here.
    if row["design"].get("active_minutes") is None:
        return row, []
    row["name"] = overrides.get(row["name"], row["name"])
    return row, []


def verify_pair(old, new, *, check_scaling=True):
    first.verify_pair(old, new, check_scaling=check_scaling)
    assert old.instructions == new.instructions and old.ingredients == new.ingredients
    assert [s.model_dump(mode="json") for s in old.design.steps] == [s.model_dump(mode="json") for s in new.design.steps]


def prepare():
    if (REPORT / "library-transition.json").exists():
        raise ValueError("Already published; use --verify")
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = manifest_entries()
    overrides = json.loads((REPORT / "recipe-names.json").read_bytes())
    issued = load_entries([*manifest["current"], *manifest["history"]])
    latest = {}
    for recipe in issued:
        key = recipe.design.base_id, recipe.design.variant_id
        latest[key] = max(latest.get(key, (0, 0, 0)), tuple(map(int, recipe.design.version.split("."))))
    changed, originals, records, used = [], {}, [], set()
    legacy = {r.name for r in current_recipes() if r.design.active_minutes is None}
    for recipe in current_recipes():
        old = recipe.model_dump(mode="json")
        row, _ = rewrite_recipe(old, overrides)
        if row == old:
            continue
        used.add(old["name"])
        major, minor, patch = latest[recipe.design.base_id, recipe.design.variant_id]
        row["design"]["version"] = f"{major}.{minor}.{patch + 1}"
        row["design"]["provenance"]["reviewed_at"] = "2026-11-20"
        row["design"]["provenance"]["notes"] += NOTE
        for key in ("pack_id", "proposal_id", "sha256"):
            (row["design"].get("content_source") or {}).pop(key, None)
        changed.append(row)
        originals[recipe.design.base_id, recipe.design.variant_id] = recipe
        records.append({"previous_id": identity(recipe), "previous_content_sha256": recipe.design.content_sha256,
                        "name_before": old["name"], "name_after": row["name"], "merged_wait_steps": []})
    if set(overrides) - used - legacy:
        raise ValueError(("Names without a current recipe", sorted(set(overrides) - used)[:5]))
    published, drafts = [], []
    for offset in range(0, len(changed), 200):
        number = offset // 200 + 1
        payload = {"schema_version": "smako-meal-pack-v1", "pack_id": f"recipe-names-20261120-{number:02}",
                   "recipes": changed[offset:offset + 200]}
        source = encoded(payload)
        validated = validate_pack_bytes(source)
        if validated["rejections"]:
            raise ValueError(validated["rejections"][:5])
        for recipe in validated["recipes"]:
            verify_pair(originals[recipe.design.base_id, recipe.design.variant_id], recipe)
            published.append(recipe)
        path = WORK / f"pack-{number:02}.json"
        path.write_bytes(source)
        drafts.append({"file": path.name, "sha256": hashlib.sha256(source).hexdigest()})
        print(f"Validated pack {number}: {len(validated['recipes'])} recipes", flush=True)
    for record, recipe in zip(records, published, strict=True):
        record.update(runtime_id=identity(recipe), content_sha256=recipe.design.content_sha256)
    review = {"before_manifest": manifest, "before_manifest_file_sha256": first.sha(manifest),
              "active_variants": len(current_recipes()), "changed_variants": len(records),
              "checked_servings": list(range(1, 13)), "drafts": drafts, "corrected": records,
              "cooking_test": "not_cooked", "purchase_qualification": "unchanged inputs; names only",
              "core_library_names_pending": sorted(set(overrides) & legacy)}
    (REPORT / "recipe-review.json").write_bytes(encoded(review))
    print(json.dumps({"changed": len(records), "names": len(used)}, ensure_ascii=False))


def checked_transition(review, *, check_scaling=False):
    return first.checked_transition(review, check_scaling=check_scaling, report=REPORT,
                                    rewriter=rewrite_recipe, pair_check=verify_pair)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--publish", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.publish:
        first.publish(report=REPORT, work=WORK, rewriter=rewrite_recipe, pair_check=verify_pair)
    else:
        first.verify(report=REPORT, rewriter=rewrite_recipe, pair_check=verify_pair)
