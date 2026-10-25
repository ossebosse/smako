"""Author reviewed variants of existing bases; keep previous issued bytes.

This writes a new ordinary authoring pack and explicit withdrawal decisions.
Run author/validate/diff/import, then ordinary revoke, before prepare.
"""
from __future__ import annotations

import copy
import hashlib

from app.services.meal_library_content import ROOT, encoded, read_json
from app.services.recipe_library import current_recipes

SOURCE = ROOT / "reviewed-800-20261025"
GROUPS = {
    "smako-greek-beef-cumin-tomato-oval-balls": (
        "smako-greek-keftedes", "tomato-",
        "Both main components are bound beef mince shaped and pan-fried. Oval shape, egg binding, tomato sauce and rice are variants of the existing keftedes construction, not sufficient evidence of a new base. The existing oven method describes its potato side; its full meat instructions pan-fry the patties."),
    "smako-thai-salmon-peanut-cool-noodle-salad": (
        "smako-thai-sour-noodle-salad", "salmon-",
        "Both constructions cook noodles and raw animal input separately, then assemble noodles, raw vegetables and a sour peanut dressing. Salmon, different vegetables and peanut-butter dressing are ingredient variants, not an independently established main construction."),
}


def build():
    source = read_json(SOURCE / "authoring.json")
    reviews = {r["id"]: r for r in read_json(SOURCE / "REVIEW.json")["reviewed"]}
    baseline = read_json(SOURCE / "baseline-262-manifest.json")
    existing = {r.design.base_id: r for r in current_recipes(len(baseline["current"])) if r.design.variant_id == "base"}
    rows, decisions, withdrawals = [], [], []
    for original in source["recipes"]:
        if original["base_id"] not in GROUPS:
            continue
        source_id = original["base_id"] + ":" + original["version"] + ":" + original["variant_id"]
        base, prefix, reason = GROUPS[original["base_id"]]
        row = copy.deepcopy(original)
        row["base_id"], row["variant_id"] = base, prefix + original["variant_id"]
        row["version"] = "1.0.1"
        row["family"] = existing[base].design.family
        row["notes"] += " Redaktionellt beslut: delar grundrätt och diversitetsfamilj med " + base + ". " + reason
        runtime_id = base + ":" + row["version"] + ":" + row["variant_id"]
        previous = base + ":1.0.0:" + row["variant_id"]
        rows.append(row)
        decisions.append({**reviews[source_id], "id": runtime_id, "source_id": source_id,
            "previous_runtime_id": previous, "reviewed_recipe_sha256": hashlib.sha256(encoded(row)).hexdigest(),
            "existing_reference_base_id": base, "existing_reference_content_sha256": existing[base].design.content_sha256,
            "changes": [*reviews[source_id]["changes"], reason], "base_review": "variant_of_existing_base"})
        withdrawals.append({"id": previous, "replaced_by": runtime_id,
                            "reason": "Diversitetsfamiljen måste följa den befintliga grundrätten. Använd granskad variant " + runtime_id + "."})
    target = SOURCE / "batch-04"
    target.mkdir(exist_ok=True)
    (target / "authoring.json").write_bytes(encoded({"schema_version": "smako-recipe-authoring-v1",
        "pack_id": "recipe-intake-reviewed-20261025-04", "recipes": rows}))
    (target / "REVIEW.json").write_bytes(encoded({"schema_version": "smako-content-review-v1",
        "reviewed": decisions, "held": [], "withdrawals": withdrawals}))
    print(f"Reconciled {len(rows)} variants into {len(GROUPS)} existing bases")


if __name__ == "__main__":
    build()
