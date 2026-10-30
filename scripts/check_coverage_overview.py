"""Validate a full CI report and compare original recipe IDs with its baseline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SCOPE_KEYS = ("universe_sha256", "facts_sha256", "clock", "store_ids", "max_stores", "servings", "pantry", "conditions",
              "imported_reference_ids_sha256")


def validate(report):
    if report.get("schema") != "smako-coverage-overview-v1" or report.get("status") != "complete":
        raise ValueError("Coverage report is missing or incomplete")
    if set(report["modes"]) != {"exact", "estimated"}:
        raise ValueError("Both purchase modes must be measured")
    if type(report["scope"]["max_stores"]) is not int or report["scope"]["max_stores"] < 1:
        raise ValueError("Invalid store cap")
    for mode, data in report["modes"].items():
        products, rows = data["products"], data["recipes"]
        if products["retained_product_rows"] != sum(products[k] for k in (
                "recipe_candidate_rows", "rejected_in_tested_paths_rows", "not_demonstrated_rows")):
            raise ValueError("Product denominator changed")
        if not len(rows) == len({r["id"] for r in rows}) == report["active_recipe_count"]:
            raise ValueError("Active recipe denominator changed")
        originals = [r["original_import_id"] for r in rows if r["original_import_id"]]
        if not len(originals) == len(set(originals)) == report["imported_recipe_count"] == 2200:
            raise ValueError("Imported recipe denominator must retain all 2200 original identities")
        for row in rows:
            status = row["basket"]
            if status not in {"verified", "data_blocked", "checkout_blocked", "search_incomplete", "not_checked"}:
                raise ValueError("Unknown basket result")
            if row["blocking_scope_ids"] and status != "data_blocked":
                raise ValueError("Blocked ingredient cannot count as a successful recipe")
            if status == "verified" and (not row["checkout"]["audit_passed"]
                    or row["checkout"]["store_count"] > report["scope"]["max_stores"]
                    or not row["checkout"]["evidence_sha256"]):
                raise ValueError("Verified basket requires final audit evidence")
        for label, subset in (("all_recipes", rows), ("imported_recipes", [r for r in rows if r["original_import_id"]])):
            from coverage_overview import recipe_totals
            if recipe_totals(subset) != data[label]:
                raise ValueError("Recipe summary does not match its full denominator: " + mode)


def baseline(report):
    validate(report)
    return {"schema": "smako-coverage-baseline-v1", "scope": {k: report["scope"][k] for k in SCOPE_KEYS},
            "measured_code": report["code_revision"], "modes": {
                mode: {"inputs_resolved": sorted(r["original_import_id"] for r in data["recipes"]
                                               if r["original_import_id"] and not r["blocking_scope_ids"]),
                       "basket_verified": sorted(r["original_import_id"] for r in data["recipes"]
                                                if r["original_import_id"] and r["basket"] == "verified")}
                for mode, data in report["modes"].items()}}


def compare(report, prior):
    validate(report)
    if prior.get("schema") != "smako-coverage-baseline-v1":
        raise ValueError("Unsupported coverage baseline")
    for key in SCOPE_KEYS:
        if prior["scope"][key] != report["scope"][key]:
            raise ValueError("Reference scope changed; review a new baseline: " + key)
    result = {"regressions": {}, "incomplete": {}, "gains": {}}
    for mode, old in prior["modes"].items():
        rows = {r["original_import_id"]: r for r in report["modes"][mode]["recipes"] if r["original_import_id"]}
        resolved = {key for key, r in rows.items() if not r["blocking_scope_ids"]}
        verified = {key for key, r in rows.items() if r["basket"] == "verified"}
        # Timeouts are unknown, never data regressions or successful plans.
        incomplete = {key for key in old["basket_verified"] if key in rows and rows[key]["basket"] in {"search_incomplete", "not_checked"}}
        result["regressions"][mode] = {"inputs_lost": sorted(set(old["inputs_resolved"]) - resolved),
                                      "baskets_lost": sorted(set(old["basket_verified"]) - verified - incomplete)}
        result["incomplete"][mode] = sorted(incomplete)
        result["gains"][mode] = {"inputs": sorted(resolved - set(old["inputs_resolved"])),
                                 "baskets": sorted(verified - set(old["basket_verified"]))}
    result["passed"] = not any(values for mode in result["regressions"].values() for values in mode.values())
    # An incomplete CI run must never silently greenlight the old coverage claim.
    result["fully_checked"] = not any(result["incomplete"].values())
    return result


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, default=Path("ci/coverage-baseline.json"))
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    current = json.loads(args.report.read_bytes())
    if args.write_baseline:
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(baseline(current), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        comparison = compare(current, json.loads(args.baseline.read_bytes()))
        if args.output:
            args.output.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"passed": comparison["passed"], "fully_checked": comparison["fully_checked"],
                          "incomplete": {k: len(v) for k, v in comparison["incomplete"].items()}}))
        raise SystemExit(0 if comparison["passed"] and comparison["fully_checked"] else 1)
