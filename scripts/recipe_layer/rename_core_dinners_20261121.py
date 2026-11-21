"""Owner decision 2026-11-20: dinners carry the dish's real name (core library).

The original core library (complete-dinners-v1 and the 2026-10-04 registered
expansion) predates pack timing: its recipes have no `active_minutes`, so they
cannot pass the authoring-pack validator without new timing claims. This
issues name-only successors in the published pack format instead. Every
successor passes the library's structural check, keeps ingredients, steps,
components, timing and preparation identical, and old packs stay immutable.
Run --prepare, read recipe-review.json, then --publish.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json

import rewrite_recipe_language as first
from app.models.recipe import Recipe
from app.services.meal_library_content import (
    MANIFEST, ROOT, SCHEMA, atomic_write, digest, encoded, identity, load_entries, manifest_entries)
from app.services.recipe_library import _structural_check, content_hash, current_recipes, reset_library_caches

REPORT = first.ROOT.parents[3] / "docs/reviews/recipe-names-core-20261121"
WORK = first.ROOT.parents[3] / ".local/recipe-names-core-20261121"
NOTE = " Namngranskning 2026-11-21: maträttens riktiga namn på vanlig svenska; endast namnet ändrat."


def rewrite_recipe(original, overrides):
    row = copy.deepcopy(original)
    if row["design"].get("active_minutes") is None:
        row["name"] = overrides.get(row["name"], row["name"])
    return row, []


def verify_pair(old, new, *, check_scaling=True):
    first.verify_pair(old, new, check_scaling=check_scaling)
    assert old.instructions == new.instructions and old.ingredients == new.ingredients
    assert old.design.content_source == new.design.content_source
    assert [s.model_dump(mode="json") for s in old.design.steps] == [s.model_dump(mode="json") for s in new.design.steps]
    assert old.preparation.model_dump(exclude={"parent_sha256"}) == new.preparation.model_dump(exclude={"parent_sha256"})
    assert new.preparation.parent_sha256 == new.design.content_sha256


def successor(recipe, overrides, latest):
    row, _ = rewrite_recipe(recipe.model_dump(mode="json"), overrides)
    if row["name"] == recipe.name:
        return None
    major, minor, patch = latest[recipe.design.base_id, recipe.design.variant_id]
    row["design"]["version"] = f"{major}.{minor}.{patch + 1}"
    row["design"]["provenance"]["reviewed_at"] = "2026-11-21"
    row["design"]["provenance"]["notes"] += NOTE
    new = Recipe.model_validate(row)
    sha = content_hash(new)
    new = new.model_copy(update={"design": new.design.model_copy(update={"content_sha256": sha}),
                                 "preparation": new.preparation.model_copy(update={"parent_sha256": sha})})
    new = Recipe.model_validate(new.model_dump(mode="json"))
    _structural_check(new)
    return new


def prepare():
    if (REPORT / "library-transition.json").exists():
        raise ValueError("Already published; use --verify")
    WORK.mkdir(parents=True, exist_ok=True)
    manifest = manifest_entries()
    overrides = json.loads((REPORT / "recipe-names.json").read_bytes())
    latest = {}
    for recipe in load_entries([*manifest["current"], *manifest["history"]]):
        key = recipe.design.base_id, recipe.design.variant_id
        latest[key] = max(latest.get(key, (0, 0, 0)), tuple(map(int, recipe.design.version.split("."))))
    published, records, used = [], [], set()
    for recipe in current_recipes():
        new = successor(recipe, overrides, latest)
        if new is None:
            continue
        verify_pair(recipe, new)
        used.add(recipe.name)
        published.append(new)
        records.append({"previous_id": identity(recipe), "previous_content_sha256": recipe.design.content_sha256,
                        "name_before": recipe.name, "name_after": new.name, "merged_wait_steps": [],
                        "runtime_id": identity(new), "content_sha256": new.design.content_sha256})
    if set(overrides) - used:
        raise ValueError(("Names without a current core recipe", sorted(set(overrides) - used)[:5]))
    source = encoded({"library_version": SCHEMA, "recipes": [r.model_dump(mode="json") for r in published]})
    path = WORK / "pack-01.json"
    path.write_bytes(source)
    review = {"before_manifest": manifest, "before_manifest_file_sha256": first.sha(manifest),
              "active_variants": len(current_recipes()), "changed_variants": len(records),
              "checked_servings": list(range(1, 13)),
              "drafts": [{"file": path.name, "sha256": hashlib.sha256(source).hexdigest()}],
              "corrected": records, "cooking_test": "not_cooked",
              "purchase_qualification": "unchanged inputs; names only"}
    (REPORT / "recipe-review.json").write_bytes(encoded(review))
    print(json.dumps({"changed": len(records), "names": len(used)}, ensure_ascii=False))


def publish():
    review = json.loads((REPORT / "recipe-review.json").read_bytes())
    if manifest_entries() != review["before_manifest"]:
        raise ValueError("Manifest changed after review")
    (draft,) = review["drafts"]
    source = (WORK / draft["file"]).read_bytes()
    if hashlib.sha256(source).hexdigest() != draft["sha256"]:
        raise ValueError("Draft changed after review")
    sha = digest(source)
    target = ROOT / f"meal-pack-{sha}.json"
    if target.exists() and target.read_bytes() != source:
        raise ValueError("Befintligt paket har ändrats")
    atomic_write(target, source)
    manifest = manifest_entries()
    entry = {"file": target.name, "sha256": sha}
    manifest["current"].append(entry)
    atomic_write(ROOT / MANIFEST.name, encoded(manifest))
    reset_library_caches()
    after = manifest_entries()
    review.update(after_manifest=after, after_manifest_file_sha256=first.sha(after), added_entries=[entry],
                  import_receipts=[{"published_file": target.name, "manifest_sha256": first.sha(after)}])
    (REPORT / "library-transition.json").write_bytes(encoded(review))
    verify()


def checked_transition(review, *, check_scaling=False):
    return first.checked_transition(review, check_scaling=check_scaling, report=REPORT,
                                    rewriter=rewrite_recipe, pair_check=verify_pair)


def verify():
    first.verify(report=REPORT, rewriter=rewrite_recipe, pair_check=verify_pair)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--publish", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    {"prepare": prepare, "publish": publish, "verify": verify}[
        next(k for k in ("prepare", "publish", "verify") if getattr(args, k))]()
