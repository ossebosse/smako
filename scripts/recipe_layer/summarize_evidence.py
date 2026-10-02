"""Publish only nonprivate recipe/purchase evidence from the isolated replay."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_plan(plan):
    checks = plan["personal"]["checks"]
    nutrition = checks.get("nutrition", [])
    meals = []
    for index, recipe in enumerate(plan["recipes"]):
        design = recipe["design"]
        n = nutrition[index] if index < len(nutrition) else {}
        meals.append({"name": recipe["name"], "base_id": design["base_id"],
            "version": design["version"], "variant": design["variant_id"],
            "content_sha256": design["content_sha256"], "servings": recipe["servings"],
            "ingredients": design["ingredient_count"], "estimated_minutes": design["estimated_minutes"],
            "nutrition_status": n.get("status", "UNKNOWN"), "per_portion": n.get("values"),
            "source_ids": sorted({s.get("product_id", "") for s in n.get("sources", [])})})
    shopping = []
    fields = ("ingredient", "product_id", "gtin", "product_name", "price_context_type",
              "required_quantity", "unit", "packages_needed", "package_quantity", "package_unit",
              "usable_quantity", "purchased_quantity", "purchased_usable_quantity", "waste_quantity",
              "total_price", "deposit_total", "membership_required", "membership_program",
              "quantity_confidence", "verification_status", "applied_offer", "group_applications",
              "source_provenance", "price_contract_id")
    for store in plan["optimized_basket"]["stores"]:
        for item in store["items"]:
            shopping.append({"store": store["store_name"], "store_id": store["store_id"],
                             **{key: item.get(key) for key in fields}})
    return {"checkout_total": plan["optimized_basket"]["total"],
            "purchase_status": checks.get("purchase"), "checks": {
                k: v for k, v in checks.items() if k in {"used_ingredient_cost", "new_purchase_used_cost",
                    "used_cost_unknown", "purchase_planning_mode", "allergy"}},
            "recipes": meals, "shopping": shopping,
            "optimization": plan.get("optimization")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--menus", type=Path, required=True)
    parser.add_argument("--qualification", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    report = {"interpretation": "Historical frozen-source replay; costs are not current offers. "
              "Found qualified solutions are not proved global optima. No physical cooking tests.",
              "menus": {}, "qualification": {}}
    for path in sorted(args.menus.glob("*.json")):
        if path.name.endswith("-plan.json"):
            continue
        record = read(path)
        case = record["case"]
        entry = {key: record.get(key) for key in ("status", "seconds", "cpu_seconds", "peak_rss_kib",
                                                 "request", "clock", "resources", "reason", "code")}
        entry["evidence_sha256"] = digest(path)
        entry["source_commit"] = record.get("stage", {}).get("commit")
        plan_path = args.menus / (case + "-plan.json")
        if record["status"] == "qualified":
            entry["plan_sha256"] = digest(plan_path)
            entry["plan"] = compact_plan(read(plan_path))
        report["menus"][case] = entry
    qual = read(args.qualification)
    by_cuisine = defaultdict(lambda: {"base_ids": set(), "qualified_base_ids": set(),
                                     "qualified_variants": 0, "first_stops": []})
    for recipe in qual["recipes"]:
        cuisine = by_cuisine[recipe["cuisine"]]
        cuisine["base_ids"].add(recipe["id"])
        if recipe["status"] == "qualified":
            cuisine["qualified_base_ids"].add(recipe["id"])
            cuisine["qualified_variants"] += 1
        else:
            cuisine["first_stops"].append({k: recipe.get(k) for k in
                ("id", "variant", "name", "stage", "code", "reason")})
    report["qualification"] = {"library": qual["library"], "source_commit": qual["stage"]["commit"],
        "evidence_sha256": digest(args.qualification), "by_cuisine": {
            name: {**data, "base_ids": sorted(data["base_ids"]),
                   "qualified_base_ids": sorted(data["qualified_base_ids"])}
            for name, data in sorted(by_cuisine.items())}}
    (args.output / "evidence.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    lines = ["# Autentiska menyer och inköp", "", "Fryst publicerat prisunderlag från 2026-10-02. "
             "Beloppen är historiska replayresultat och inga nya prisutfästelser. "
             "Fullständiga underlag med källor och receptversioner finns i evidence.json.", ""]
    for case, entry in report["menus"].items():
        lines.extend([f"## {case}", ""])
        if "plan" not in entry:
            lines.extend([f"Stopp: {entry['code']} — {entry['reason']}", ""])
            continue
        plan = entry["plan"]
        lines.extend([f"Inköp **{plan['checkout_total']:.2f} kr**, {entry['seconds']:.2f} sekunder. "
                      "Fem middagar för två personer, högst två inköpsställen. "
                      "Lägsta hittade inköpskostnad inom valen; global optimalitet är inte bevisad.", "",
                      "| Rätt | Ingredienser | Uppskattad tid | Protein / kolhydrat / fett / kcal per portion | Näringsstatus |",
                      "|---|---:|---:|---|---|"])
        for meal in plan["recipes"]:
            vals = meal["per_portion"] or {}
            values = " / ".join(f"{vals[k]:.2f}" if isinstance(vals.get(k), (int, float)) else "okänt"
                                for k in ("protein_g", "carbs_g", "fat_g", "kcal"))
            lines.append(f"| {meal['name']} | {meal['ingredients']} | {meal['estimated_minutes']} min | {values} | {meal['nutrition_status']} |")
        lines.extend(["", "| Inköpsställe / kanal | Produkt | Behov | Köp | Planerad rest | Betala | Villkor / status |",
                      "|---|---|---:|---:|---:|---:|---|"])
        for item in plan["shopping"]:
            flags = [item["verification_status"] or "okänd"]
            if item["membership_required"]:
                flags.append("medlem " + str(item["membership_program"]))
            if item["applied_offer"] or item["group_applications"]:
                flags.append("kampanj")
            if item["deposit_total"]:
                flags.append(f"pant {item['deposit_total']} kr")
            lines.append(f"| {item['store']} / {item['price_context_type']} | {item['product_name']} | "
                f"{item['required_quantity']:g} {item['unit']} | {item['packages_needed']:g} × "
                f"{item['package_quantity']:g} {item['package_unit']} | {item['waste_quantity']:g} {item['unit']} | "
                f"{item['total_price']:.2f} kr | {', '.join(flags)} |")
        lines.extend(["", "Resterna är planerade mängder och bokförs inte som uppmätt skafferi. "
                      "Vid avrunnen vara avser användning/rest ätbar avrunnen mängd, medan förpackningen kan ange totalvikt.", ""])
    (args.output / "MENUS.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    print(json.dumps({"menus": len(report["menus"]), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
