"""Summarize actual saved run data; never create test results."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from app.models.recipe import Recipe
from app.services.product_planning_trace import recipe_identity

R = Path(__file__).parent
load = lambda p: json.loads(p.read_bytes())
before = load(R / "baseline/all-84.json")
after = load(R / "profile/all-84.json")
before_diag = load(R / "baseline/all-84-diagnostics.json")
after_diag = load(R / "profile/all-84-diagnostics.json")
assert len(before) == len(after) == 84

def search_for(diag, name):
    return [s for s in diag["nutrition_searches"] if len(s["recipes"]) == 1 and s["recipes"][0]["name"] == name]

def actual_protein(row):
    n = row.get("checks", {}).get("nutrition", [])
    if n: return n[0]["values"]["protein_g"]
    hit = re.search(r"protein_g ([0-9.]+) per portion", row.get("stop", {}).get("reason", ""))
    return float(hit[1]) if hit else None

rows = []
for old, new in zip(before, after, strict=True):
    assert old["adapted"] == new["adapted"]
    recipe = Recipe.model_validate(new["adapted"])
    identity = recipe_identity(recipe)
    bs, ns = search_for(before_diag, recipe.name), search_for(after_diag, recipe.name)
    bound = next((v for s in ns for v in s.get("proven_bounds", []) if v["nutrient"] == "protein_g"), None)
    ingredients = []
    independent_upper = 0
    for e in new["ingredient_evidence"]:
        qualified = e["qualified"]
        assert qualified
        candidates = [{k: c[k] for k in ("product_id", "store_id", "name", "source_snapshot_id", "usable_quantity", "package_quantity")} | {
            "protein_g_per100": c["facts"]["nutrition"]["protein_g"],
            "nutrition_unit": c["facts"]["nutrition_unit"], "nutrition_source": c["facts"]["source"],
            "field_sources": c["facts"].get("field_sources", {})} for c in qualified]
        independent_upper += max(c["protein_g_per100"] for c in candidates) * e["quantity"] / 100 / recipe.servings
        ingredients.append({"name": e["name"], "used_quantity": e["quantity"], "unit": e["unit"], "candidates": candidates})
    if bound: assert abs(independent_upper - bound["upper"]) < 1e-8
    rows.append({**identity, "recipe_version": recipe.preparation.version,
        "original_sha256": new["original_hash"], "unchanged_recipe": True,
        "before_passed": bool(old.get("nutrition_basket_passed")), "after_passed": bool(new.get("nutrition_basket_passed")),
        "target_protein_g": {"dinner":40,"breakfast":30,"snack":20}[new["meal_type"]],
        "before_actual_example_protein_g": actual_protein(old),
        "after_actual_protein_g": actual_protein(new), "after_independent_upper_g": independent_upper,
        "upper_is_not_a_purchasable_basket": True,
        "before_first_stop": old.get("stop"), "after_first_stop": new.get("stop"),
        "before_searches": bs, "after_searches": ns, "protein_bound_proof": bound,
        "ingredients": ingredients})
(R / "recipe-first-stops.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf8")

summary = {"denominator":84,"historical_purchase_clock":"2026-09-24T21:16:35.494010+00:00",
    "before_passed":sum(r["before_passed"] for r in rows), "after_passed":sum(r["after_passed"] for r in rows),
    "newly_passed":[r["name"] for r in rows if r["after_passed"] and not r["before_passed"]],
    "revoked_previous":[r["name"] for r in rows if r["before_passed"] and not r["after_passed"]],
    "before_budget_stops":sum(any(s["budget_exhausted"] for s in r["before_searches"]) for r in rows if not r["before_passed"]),
    "after_stops":dict(Counter(r["after_first_stop"]["stage"] for r in rows if not r["after_passed"])),
    "probe_recipe_seconds_before":sum(r["seconds"] for r in before),
    "probe_recipe_seconds_after":sum(r["seconds"] for r in after),
    "probe_timing_excludes_prepared_restore_and_initial_fact_loading":True,
    "profiles":[]}
versions = set()
for member in ("public", "plus"):
    for mode in ("exact", "estimated"):
        filename = f"after-edible-input-v1-{member}-{mode}-restored-original.json"
        b, a = load(R/"baseline"/filename), load(R/"profile"/filename)
        assert a["status"] == "PASS" and a["request"] == b["request"]
        versions.add(a["facts_version"])
        plan = load(R/"profile"/filename.replace(".json","-plan.json"))
        basket = plan["optimized_basket"]
        items = [i for s in basket["stores"] for i in s["items"]]
        selected_84 = [s["recipe"]["name"] for s in plan["personal"]["slots"] if s.get("recipe") and s["recipe"]["name"] in {r["name"] for r in rows}]
        summary["profiles"].append({"membership":member,"mode":mode,"cost_before":b["cost"],"cost_after":a["cost"],
            "seconds_before":b["seconds"],"seconds_after":a["seconds"],"verification":a["verification"],
            "stores":[{"id":s["store_id"],"name":s["store_name"],"channels":sorted({i["price_context_type"] for i in s["items"]})} for s in basket["stores"]],
            "purchase_rows":dict(Counter(i["verification_status"] for i in items)),
            "nutrition_statuses":dict(Counter(n["status"] for n in plan["personal"]["checks"]["nutrition"])),
            "selected_of_84":selected_84,"stage_timings_inclusive":a["stage_timings_inclusive"],"cache_state":a["cache_state"]})
assert len(versions)==1, "Do not mix unfinished run files with prior iteration results"
summary["facts_version"] = versions.pop()
summary["http"] = load(R/"profile/http-rescued-after-integration.json")
summary["reference_current_29"] = load(R/"profile/reference-current-29.json")
assert len(summary["reference_current_29"])==29
code_only = load(R/"profile/final-code-only-all-84.json")
summary["final_code_only_passed"] = sum(bool(r.get("nutrition_basket_passed")) for r in code_only)
(R/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf8")

lines = ["# Samtliga 84 recept: första stopp och näringsgränser", "",
 "Samma oförändrade v1-recept, mängder, portioner och 40/30/20-mål. Köpklocka 24 september 2026. Full kandidat- och källspårning: `recipe-first-stops.json`; råa körningar: `baseline/` och `profile/`.", "",
 "Föreprotein är ett faktiskt sparat beräknat exempel, inte maximum av alla försök. Eftergränsen är en oberoende optimistisk övre gräns ur kvalificerade kandidater, inte en köpt varukorg. Den relaxerar gemensamma produkt- och butiksvillkor och kan därför endast utesluta, aldrig godkänna ett köp. Inga saknade näringsfält har fyllts med noll.", "",
 "| Recept / ID | Mål g | Före: exempel g / prövade | Efter: uppnått eller övre gräns g | Första stopp efter |", "|---|---:|---:|---:|---|"]
for r in rows:
    evaluated = sum(s['evaluated'] for s in r['before_searches'])
    value = r['after_actual_protein_g'] if r['after_passed'] else r['after_independent_upper_g']
    label = "Godkänt köp + audit" if r['after_passed'] else "Bevisad proteinbrist inom underlaget"
    lines.append(f"| {r['name']} · `{r['id']}` | {r['target_protein_g']} | {r['before_actual_example_protein_g']} / {evaluated} | {'Uppnått' if r['after_passed'] else 'Högst'} {value:.4f} | {label} |")
(R/"RECIPE-RESULTS.md").write_text("\n".join(lines)+"\n",encoding="utf8")
print({k:summary[k] for k in ('before_passed','after_passed','newly_passed','revoked_previous','final_code_only_passed')})
