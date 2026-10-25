"""Reconcile all 2,200 source variants with actual reviewed/imported stages."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    manifest_entries,
    read_json,
)
from app.services.recipe_authoring import REVIEWED_VOCABULARY, readiness
from app.services.recipe_library import COUNT_EXEMPT, current_recipes
from audit_authoring_delivery import audit

OUT = Path("docs/reviews/recipe-integration-800-20261025")
SOURCE = ROOT / "incoming/authoring-800-20261025"
REVIEWED = ROOT / "reviewed-800-20261025"


def summarize():
    original = audit(SOURCE)
    (OUT / "original-after.json").write_bytes(encoded(original))
    manifest = manifest_entries()
    current = current_recipes()
    baseline = read_json(REVIEWED / "baseline-262-manifest.json")
    assert baseline["current"] == manifest["current"][:len(baseline["current"])]
    old = current_recipes(len(baseline["current"]))
    assert len(old) == 262
    issued = [r for r in current if r.design.content_source and r.design.content_source.pack_id in {
        "recipe-intake-reviewed-20261025", "recipe-intake-reviewed-20261025-02", "recipe-intake-reviewed-20261025-03",
        "recipe-intake-reviewed-20261025-04"}]
    accepted_ids = {identity(r) for r in issued}
    folders = (REVIEWED, REVIEWED / "batch-02", REVIEWED / "batch-03", REVIEWED / "batch-04")
    all_reviews = [entry for path in (folder / "REVIEW.json" for folder in folders)
              for entry in read_json(path)["reviewed"]]
    review = [row for row in all_reviews if row["id"] in accepted_ids]
    assert accepted_ids == {r["id"] for r in review}
    accepted_source_ids = {r.get("source_id", r["id"]) for r in review}
    assert len(accepted_source_ids) == len(accepted_ids) == 45
    reconciled = read_json(REVIEWED / "batch-04/REVIEW.json")
    withdrawn = [r["id"] for folder in folders for r in read_json(folder / "REVIEW.json").get("withdrawals", [])]
    before = (ROOT / "library-manifest.json").read_bytes()
    sizes = []
    for folder in folders:
        result = import_pack(folder / "standardized.json")
        assert all(r["status"] == "unchanged" for r in result["diff"])
        sizes.append({"standardized_file": (folder / "standardized.json").relative_to(ROOT).as_posix(),
                      "standardized_bytes": (folder / "standardized.json").stat().st_size,
                      "published_file": result["published_file"], "published_bytes": (ROOT / result["published_file"]).stat().st_size})
    assert before == (ROOT / "library-manifest.json").read_bytes()
    all_rows, missing, counts, within_defaults = [], defaultdict(list), {}, defaultdict(list)
    for path in sorted(SOURCE.glob("paket/*.json")):
        for index, row in enumerate(read_json(path)["recipes"]):
            key = row["base_id"] + ":" + row.get("version", "1.0.0") + ":" + row["variant_id"]
            names = {(canonicalize_ingredient_name(i["name"]), i["form"])
                     for c in row["components"] for i in c["ingredients"]}
            count = len({(n, f) for n, f in names if n not in COUNT_EXEMPT})
            counts[key] = count
            if row["meal_type"] == "dinner" and 10 <= count <= 15:
                within_defaults[row["base_id"]].append(key)
            all_rows.append({"id": key, "base_id": row["base_id"], "meal_type": row["meal_type"], "cuisine": row["cuisine"],
                "variant_id": row["variant_id"], "counted_ingredients": count, "source_file": path.relative_to(SOURCE).as_posix(),
                "source_index": index, "imported_corrected_variant": key in accepted_source_ids})
    for row in original["recipes"]:
        if row.get("authoring"):
            assert counts[row["id"]] == row["authoring"]["counted_ingredients"]
        for name in row.get("missing", []):
            missing[name].append({"recipe_id": row["id"], "source_file": row["source_file"], "source_index": row["source_index"]})
    ingredient_decisions = []
    for name, rows in sorted(missing.items(), key=lambda p: (-len(p[1]), p[0])):
        form = name.split("|")[1]
        next_step = ({"raw_edible": "Review exact whole raw product and verified edible purchase mass/yield; no assumed whole-fruit, piece or trimming conversion.",
                      "cooked_drained": "Bind exact cooked/drained product and declared drained gram amount or a supported source-backed cooking conversion.",
                      "preserved_drained": "Bind exact preserved product, edible form and source-backed drained gram amount.",
                      "dry": "Review exact dry whole product, grain/flour/spice form, package mass and supported culinary requirements.",
                      "as_sold": "Review exact as-sold whole product, package unit/mass and composition-dependent culinary requirements."})[form]
        ingredient_decisions.append({"identity": name, "affected_variants": len(rows),
            "status": "blocked_unregistered_identity", "next_step": next_step, "recipes": rows})
    new_ingredients = read_json(REVIEWED_VOCABULARY)
    bands = {"simple": (5, 7), "standard": (8, 11), "extended": (12, 15)}
    exceptions = [r for r in all_rows if r["meal_type"] == "dinner"
                  and not bands[r["variant_id"]][0] <= r["counted_ingredients"] <= bands[r["variant_id"]][1]]
    dinner_bases = {r["base_id"] for r in all_rows if r["meal_type"] == "dinner"}
    source_review = read_json(SOURCE / "smako-dubblettgranskning.json")
    rationales = [
        "Broth retains 1600 ml cooking water; kornotto uses 850 ml and explicitly mashes beans to bind a thick dish without free broth.",
        "Palt cooks pressed raw-potato dough for 35 minutes; kroppkakor use pre-cooked potato/egg dough and a 12-minute final simmer.",
        "Chicken is enclosed between polenta layers and baked; lamb is pulled after long braising and served on loose polenta without final baking.",
        "Loose toasted tortilla pieces are dressed immediately before serving; intact tortillas form a layered baked and cut casserole.",
        "Bread is dissolved into a thick tomato porridge; the beef soup retains broth and serves bread separately.",
        "Ravioli enclose filling in rolled thin pasta; bread-bean dumplings are a homogeneous soaked-bread mass cooked by steaming.",
    ]
    pairs = [{"left": r["left_base_id"], "right": r["right_base_id"],
              "decision": "retain_distinct_process_candidates", "rationale": rationale,
              "publication": "not_part_of_this_import"}
             for r, rationale in zip(source_review["machine_retrieved_candidate_pairs"]["pairs"], rationales, strict=True)]
    pairs.extend([
        {"left": "smako-swedish-salmon-cakes-potatoes", "right": "smako-swedish-mustard-salmon",
         "decision": "retain_distinct_bases", "rationale": "New salmon is chopped, bound and pan-fried as patties; existing full instructions bake intact salmon. Shared sides do not remove this main structural difference."},
        {"left": "smako-indian-breakfast-bulgur-lentil-breakfast-pilaf", "right": "smako-breakfast-lentil-carrot-porridge",
         "decision": "reject_additional_new_base_claim", "rationale": "Both are the same simmered lentil/carrot breakfast structure. Bulgur changes grain texture but no sufficiently independent construction is established. Treat the two source variants as variants of the existing base; no import until bulgur requirements and complete variant review pass.",
         "future_base_id": "smako-breakfast-lentil-carrot-porridge", "future_variant_ids": ["bulgur-simple", "bulgur-extended"]},
    ])
    seen = set()
    for row in reconciled["reviewed"]:
        source_base = row["source_id"].split(":")[0]
        if source_base in seen:
            continue
        seen.add(source_base)
        pairs.append({"left": source_base, "right": row["existing_reference_base_id"],
                      "decision": "published_as_variant_of_existing_base", "rationale": row["changes"][-1],
                      "existing_reference_content_sha256": row["existing_reference_content_sha256"]})
    old_bases = {r.design.base_id for r in old}
    issued_bases = {r.design.base_id for r in issued}
    summary = {"schema_version": "smako-reviewed-delivery-summary-v1",
        "received": {"base_candidates": 800, "variants": 2200},
        "new_base_claims_after_editorial_merges": 797, "global_unique_new_bases": None,
        "baseline": {"variants": len(old), "base_dishes": len({r.design.base_id for r in old}), "manifest": "backend/app/data/recipes/reviewed-800-20261025/baseline-262-manifest.json"},
        "corrected_and_imported": {"base_dishes": len(issued_bases), "new_base_dishes": len(issued_bases - old_bases),
            "existing_bases_with_new_variants": len(issued_bases & old_bases), "source_base_candidates": 20,
            "variants": len(issued), "historically_issued_variants": len(all_reviews),
            "withdrawn_superseded_ids": withdrawn,
            "source_to_runtime_id": {r.get("source_id", r["id"]): r["id"] for r in review},
            "by_meal": dict(Counter(r.design.meal_types[0] for r in issued)),
            "by_cuisine": dict(Counter(r.design.cuisines[0] for r in issued)), "ids": sorted(accepted_ids),
            "default_static_selection": readiness(issued)},
        "current_library": {"variants": len(current), "base_dishes": len({r.design.base_id for r in current}),
            "current_generations": len(manifest["current"]), "historical_generations": len(manifest["history"])},
        "source_native_audit": {"statuses": original["statuses"], "unknown_identities": original["unknown_ingredient_identities"],
                                "verified_source_files": original["verified_source_files"], "source_manifest_sha256": original["source_manifest_sha256"]},
        "remaining_unimported": {"variants": len(all_rows) - len(issued),
            "by_native_source_status": dict(Counter(r["status"] for r in original["recipes"] if r["id"] not in accepted_source_ids))},
        "new_ingredient_identities": [r["name"] + "|" + r["form"] for r in new_ingredients["ingredients"]],
        "reviewed_source_product_references": sum(len(r["evidence"]) for r in new_ingredients["ingredients"]),
        "source_dinner_variant_interval_exceptions": exceptions,
        "dinner_bases_without_10_15_variant": sorted(dinner_bases - within_defaults.keys()),
        "alias_decisions": [
            {"names": ["koriander", "färsk koriander"], "decision": "same fresh canonical; dried seed stays separate"},
            {"names": ["rädisa", "rädisor"], "decision": "same canonical singular/plural"},
            {"names": ["pumpafrön", "pumpakärnor"], "decision": "no automatic merge; verify husk/kernel and quantity basis"},
            {"names": ["solrosfrön", "solroskärnor"], "decision": "no automatic merge; verify husk/kernel and quantity basis"},
            {"names": ["polenta", "majsgryn"], "decision": "no automatic merge; review grind and preparation requirements"},
            {"names": ["korngryn", "pärlkorn"], "decision": "remain distinct; pearling is not merely a name alias"},
            {"names": ["matbanan", "grön matbanan"], "decision": "remain distinct until required ripeness is source-backed"}],
        "duplicate_pair_reviews": pairs, "unresolved_family_groups": source_review["supplementary_process_reviews"]["mexican_swedish/quality-review.json"]["remaining_groups"],
        "import_idempotent_manifest_unchanged": True, "sizes": sizes,
        "not_established": ["Cooking tests", "General nutrition/allergen/organic approval", "All 800 new bases are unique", "Full V2 prototype or 30–60 second new-choice latency", "HTTP GET/browser latency", "Production or beta activation"]}
    (OUT / "ingredient-blockers.json").write_bytes(encoded({"identities": ingredient_decisions}))
    (OUT / "all-source-variants.json").write_bytes(encoded({"recipes": all_rows}))
    (OUT / "summary.json").write_bytes(encoded(summary))
    print({"imported": len(issued), "current": len(current), "remaining": len(all_rows) - len(issued),
           "ingredient_blockers": len(missing), "interval_exceptions": len(exceptions),
           "no_default_dinner_variant": len(summary["dinner_bases_without_10_15_variant"])})


if __name__ == "__main__":
    summarize()
