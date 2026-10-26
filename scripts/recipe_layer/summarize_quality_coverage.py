"""Normalize repeated public inventory references into compact review evidence."""
import argparse
import hashlib
import json
from pathlib import Path


def main(args):
    report = json.loads(args.input.read_bytes())
    review = json.loads(args.review.read_bytes())
    replacements = {r["superseded_intermediate_id"]: r["runtime_id"] for r in review["recipes"] if r.get("superseded_intermediate_id")}
    result = {k: report[k] for k in ("scope", "universe_sha256", "facts_sha256", "facts_version", "clock")}
    result.update(raw_inventory_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        source_recipe_review_sha256=hashlib.sha256(args.review.read_bytes()).hexdigest(),
        reference_encoding="Recipe indices refer to recipe_ids; product indices refer to products. Scope ingredients/quantities/requirements are unchanged by fish timing-only refinement.",
        products=[], modes={})
    products = {}
    for mode, inventory in report["modes"].items():
        ids = [replacements.get(r["id"], r["id"]) for r in inventory["recipes"]]
        positions = {key: n for n, key in enumerate(ids)}
        shared = []
        for row in inventory["shared_inputs"]:
            out = {k: v for k, v in row.items() if k not in ("recipes", "examples")}
            out["recipe_indices"] = [positions[replacements.get(key, key)] for key in row["recipes"]]
            if "examples" in row:
                out["product_indices"] = []
                for product in row["examples"]:
                    key = json.dumps(product, ensure_ascii=False, sort_keys=True)
                    if key not in products:
                        products[key] = len(products)
                        result["products"].append(product)
                    out["product_indices"].append(products[key])
            shared.append(out)
        result["modes"][mode] = {"conditions": inventory["conditions"], "recipe_ids": ids,
            "before_resolved": inventory["before_resolved"], "after_resolved": inventory["after_resolved"],
            "newly_resolved_indices": [n for n, r in enumerate(inventory["recipes"]) if r["all_inputs_resolved"] and not r["before_all_inputs_resolved"]],
            "resolved_indices": [n for n, r in enumerate(inventory["recipes"]) if r["all_inputs_resolved"]],
            "shared_inputs": shared}
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print({"output_bytes": args.output.stat().st_size, "unique_product_examples": len(products)})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("input", "review", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    main(p.parse_args())
