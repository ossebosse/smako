"""Audit draft delivery bytes and native compatibility without publishing recipes.

Run with PYTHONPATH=backend;. on Windows, backend:. on Linux. Exit 1 means
the completed audit found blockers; it does not mean the report is incomplete.
Unknown ingredient identities are never supplied to the native standardizer
with invented requirements. Native compatibility is not content approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.meal_library_content import (
    MANIFEST,
    ROOT,
    manifest_entries,
    read_json,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

DEFAULT_INPUT = ROOT / "incoming/authoring-800-20261025"


def audit(input_root: Path) -> dict:
    source_manifest = read_json(input_root / "SOURCE-MANIFEST.json")
    verified = []
    for entry in source_manifest["preserved_files"]:
        path = (input_root / entry["path"]).resolve()
        if not path.is_relative_to(input_root.resolve()):
            raise ValueError("Delivery path leaves its source directory")
        raw = path.read_bytes()
        if len(raw) != entry["bytes"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Delivery bytes differ: {entry['path']}")
        verified.append(entry["path"])

    manifest_before = MANIFEST.read_bytes()
    library = manifest_entries()
    existing = current_recipes(len(library["current"]))
    vocabulary = library_vocabulary(existing)
    existing_bases = {recipe.design.base_id for recipe in existing}
    bases, seen, results = {}, set(), []
    missing = defaultdict(set)
    packs = sorted(path for path in verified if path.startswith("paket/"))
    for relative in packs:
        source = read_json(input_root / relative)
        if source["schema_version"] != "smako-recipe-authoring-v1":
            raise ValueError(f"Unexpected draft schema: {relative}")
        for index, row in enumerate(source["recipes"]):
            identity = f"{row['base_id']}:{row.get('version', '1.0.0')}:{row['variant_id']}"
            if identity in seen:
                raise ValueError(f"Duplicate draft identity: {identity}")
            seen.add(identity)
            bases.setdefault(row["base_id"], row)
            result = {"id": identity, "source_file": relative, "source_index": index}
            unknown = {
                f"{canonicalize_ingredient_name(item['name'])}|{item['form']}"
                for component in row["components"] for item in component["ingredients"]
            } - vocabulary.keys()
            if unknown:
                for key in unknown:
                    missing[key].add(identity)
                result.update(status="blocked_unknown_ingredients", missing=sorted(unknown))
            else:
                try:
                    single = {**source, "recipes": [row]}
                    pack, details = standardize(single, vocabulary, reviewed_at="2026-10-25")
                    checked = validate_pack_bytes(
                        json.dumps(pack, ensure_ascii=False).encode(), label=relative,
                    )
                    result.update(authoring=details[0], rejections=checked["rejections"])
                    result["status"] = (
                        "native_rejected" if checked["rejections"] else "native_compatible"
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    result.update(status="standardization_failed", reason=str(exc))
            results.append(result)

    counts = {"base_dishes": len(bases), "recipe_variants": len(results),
              "authoring_packs": len(packs)}
    if counts != source_manifest["counts"]:
        raise ValueError(f"Counts disagree with source manifest: {counts}")
    statuses = dict(sorted(Counter(row["status"] for row in results).items()))
    blocked = len(results) - statuses.get("native_compatible", 0)
    if MANIFEST.read_bytes() != manifest_before:
        raise ValueError("Runtime manifest changed during audit")
    return {
        "schema_version": "smako-authoring-audit-v1",
        "delivery_id": source_manifest["delivery_id"],
        "validation_scope": "native author/validate for known identities only; no import or approval",
        "source_manifest_sha256": hashlib.sha256(
            (input_root / "SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
        "verified_source_files": len(verified),
        "runtime_manifest_sha256": hashlib.sha256(manifest_before).hexdigest(),
        "runtime_manifest_unchanged": True,
        "runtime_recipe_count": len(existing),
        "runtime_vocabulary_count": len(vocabulary),
        "runtime_current_packs": len(library["current"]),
        "runtime_history_packs": len(library["history"]),
        "counts": counts,
        "bases_by_meal": dict(sorted(Counter(r["meal_type"] for r in bases.values()).items())),
        "dinner_bases_by_cuisine": dict(sorted(Counter(
            r["cuisine"] for r in bases.values() if r["meal_type"] == "dinner").items())),
        "existing_base_id_collisions": sorted(set(bases) & existing_bases),
        "statuses": statuses,
        "blocked_variants": blocked,
        "unknown_ingredient_identities": len(missing),
        "ingredient_priorities": [
            {"identity": key, "affected_variants": len(ids)}
            for key, ids in sorted(missing.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
        "not_established": [
            "Content review, culinary uniqueness or cooking tests",
            "Native compatibility of drafts with unknown ingredients",
            "Product availability, exact identity/yield, price or campaign qualification",
            "Nutrition, dietary, allergen or organic approval",
        ],
        "recipes": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(args.input.resolve()):
        raise ValueError("Write the audit outside the preserved delivery directory")
    report = audit(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "statuses": report["statuses"],
                      "unknown_ingredient_identities": report["unknown_ingredient_identities"],
                      "runtime_manifest_unchanged": report["runtime_manifest_unchanged"]},
                     ensure_ascii=False))
    return int(bool(report["blocked_variants"] or report["existing_base_id_collisions"]))


if __name__ == "__main__":
    raise SystemExit(main())
