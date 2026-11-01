"""Export current authored recipes for a writing brief, without publishing.

Run from the repository with PYTHONPATH=backend;. (Windows) or backend:.
(POSIX). The output directory must be new. No prices or user data are read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from app.services.meal_library_content import (
    MANIFEST,
    encoded,
    identity,
    library_signature,
    load_entries,
    manifest_entries,
    validate_pack_bytes,
)
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes, ingredient_count

REPO = Path(__file__).resolve().parents[2]


def export(output: Path) -> dict:
    if output.exists():
        raise ValueError("Choose a new output directory; existing exports are preserved.")
    manifest_before = MANIFEST.read_bytes()
    manifest = manifest_entries()
    signature = library_signature()
    recipes = sorted(current_recipes(), key=identity)
    issued = load_entries(manifest["current"] + manifest["history"])
    vocabulary = library_vocabulary(recipes)
    groups = defaultdict(list)
    details = []
    for recipe in recipes:
        d = recipe.design
        groups[d.base_id].append(recipe)
        details.append({
            "id": identity(recipe), "base_id": d.base_id, "version": d.version,
            "variant_id": d.variant_id, "name": recipe.name, "servings": recipe.servings,
            "meal_types": list(d.meal_types), "cuisines": list(d.cuisines),
            "family": d.family, "primary": d.primary_ingredient, "method": d.method,
            "side": d.side, "flavor": list(d.flavor_profile),
            "ingredient_count": ingredient_count(recipe),
            "ingredients": [i.model_dump(mode="json") for i in recipe.ingredients],
            "components": [c.model_dump(mode="json") for c in d.components],
            "instructions": recipe.instructions,
            "preparation_version": recipe.preparation.version if recipe.preparation else None,
            "unmeasured_processes": [p.model_dump(mode="json") for p in d.unmeasured_processes or ()],
            "active_minutes": d.active_minutes,
            "waiting_minutes": d.waiting_minutes,
            "total_minutes": d.total_minutes or d.estimated_minutes,
        })
    bases = []
    for base_id, variants in sorted(groups.items()):
        bases.append({
            "base_id": base_id, "names": sorted({r.name for r in variants}),
            "cuisines": sorted({c for r in variants for c in r.design.cuisines}),
            "meal_types": sorted({m for r in variants for m in r.design.meal_types}),
            "families": sorted({r.design.family for r in variants}),
            "primaries": sorted({r.design.primary_ingredient for r in variants}),
            "methods": sorted({r.design.method for r in variants}),
            "sides": sorted({r.design.side for r in variants}),
            "flavor": sorted({f for r in variants for f in r.design.flavor_profile}),
            "ingredient_keys": sorted({f"{i.canonical_name}|{i.form}"
                                       for r in variants for i in r.ingredients}),
            "variants": [{"id": identity(r), "variant_id": r.design.variant_id,
                          "ingredient_count": ingredient_count(r)} for r in variants],
        })

    now = datetime.now(UTC)
    example_bytes = (REPO / "docs/recipes/examples/authoring-example.json").read_bytes()
    example = json.loads(example_bytes)
    pack, authoring_report = standardize(example, vocabulary, reviewed_at=now.date().isoformat())
    validation = validate_pack_bytes(encoded(pack), label="reference format example")
    if validation["rejections"] or len(validation["recipes"]) != len(example["recipes"]):
        raise ValueError(f"Reference format example failed native validation: {validation['rejections']}")
    if MANIFEST.read_bytes() != manifest_before or library_signature() != signature:
        raise ValueError("Library manifest changed during export; retry on a stable checkout.")
    if len(details) != len({r["id"] for r in details}):
        raise ValueError("Current recipe identities are not unique.")

    summary = {
        "created_at": now.isoformat(),
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "tracked_worktree_dirty": bool(subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO, text=True).strip()),
        "library_signature": signature,
        "scope": "Current authored library in this checkout; not live beta or purchasing coverage.",
        "base_count": len(bases), "variant_count": len(details),
        "ingredient_identity_count": len(vocabulary),
        "ingredient_unit_identity_count": len(vocabulary.by_unit),
        "cuisine_base_counts": dict(Counter("+".join(b["cuisines"]) or "unassigned" for b in bases)),
        "meal_type_base_counts": dict(Counter("+".join(b["meal_types"]) for b in bases)),
        "issued_base_count": len({r.design.base_id for r in issued}),
        "issued_variant_versions": len(issued),
    }
    files = {
        "befintliga-grundratter.json": encoded({"bases": bases,
            "note": "Include unassigned and multi-cuisine bases in duplicate checks."}),
        "befintliga-recept-detaljer.jsonl": "".join(
            json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in details).encode("utf-8"),
        "reserverade-idn.json": encoded({
            "base_ids": sorted({r.design.base_id for r in issued}),
            "recipe_ids": sorted({identity(r) for r in issued}),
            "revoked_recipe_ids": sorted(manifest.get("revocations", {})),
        }),
        "ingrediensregister.json": encoded({
            "scope": "Known authoring identities, default units and separately reviewed unit options; not availability, nutrition or price evidence. Unit options are not conversions or density/yield factors. Requirements may depend on reviewed recipe identities; do not generalize them to new recipes without review.",
            "ingredients": [{"key": key, "name": key.split("|", 1)[0],
                "form": key.split("|", 1)[1], "unit": value[0], "requirements": value[1],
                "unit_options": [{"unit": unit, "requirements": requirements}
                    for (option_key, unit), (_, requirements) in sorted(vocabulary.by_unit.items())
                    if option_key == key]}
                for key, value in sorted(vocabulary.items())],
        }),
        "AUTHORING.md": (REPO / "docs/recipes/AUTHORING.md").read_bytes(),
        "authoring-example.json": example_bytes,
        "exempelkontroll.json": encoded({"authoring_report": authoring_report,
            "accepted_count": len(validation["recipes"]), "rejections": validation["rejections"],
            "scope": "Existing format example only. No new recipes authored, cooked, qualified or imported."}),
        "referensmanifest.json": encoded(summary),
    }
    files["FILMANIFEST.json"] = encoded({"files": [
        {"file": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        for name, data in sorted(files.items())]})
    output.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        (output / name).write_bytes(data)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export(args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
