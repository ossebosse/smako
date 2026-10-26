"""Write bounded structural evidence and a concrete, prioritized blocker list."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from app.services.intake_product_links import entries
from app.services.meal_library_content import ROOT, encoded, identity, import_pack, manifest_entries
from app.services.recipe_library import current_recipes

REPORT = ROOT.parents[3] / "docs/reviews/recipe-integration-all-20261026"
KNOWN_GAPS = {
    "limejuice|as_sold": "Fullständig ingrediensdeklaration som styrker ren limejuice; namn och ml-förpackning räcker inte för pure_juice.",
    "ingefära|raw_edible": "Källbelagd rå ätlig mängd efter putsning; hel rot, inlagd och torkad ingefära är olika insatser.",
    "majs|as_sold": "Belägg frysta ätliga majskorn och exakt användbar mängd för författarformen; lag-/avrunnen konserv är en annan form.",
    "fläskkött|raw_edible": "Belägg rätt benfri rå styckdetalj och köpbar förpackningsmängd; uppskattad vikt kräver uttryckligt estimated-val.",
    "kvarg|as_sold": "Fullständig deklaration som styrker naturell kvarg; smaksatt kvarg eller enbart ordet kvarg räcker inte.",
    "kapris|preserved_drained": "Deklarerad avrunnen mängd bunden till aktuell produkt och snapshot; nettovikt inklusive lag räcker inte.",
    "keso|as_sold": "Belägg naturell cottage cheese och efterfrågad fetthalt 1–4 procent med aktuell deklaration.",
    "kokosflingor|dry": "Granska och koppla exakt torr kokosprodukt även när butiken skriver Kokos Riven; fastställ torr form och ren sammansättning före sök-/matchningsändring.",
    "nötkött|raw_edible": "Belägg den styckdetalj som varje exakt scope kräver och användbar rå mängd; uppskattade viktpaket får bara prövas med estimated-val.",
    "rödbeta|raw_edible": "Belägg rå ätlig mängd; inlagda/kokta rödbetor får inte prissätta rå vikt.",
    "jordnötssmör|as_sold": "Fullständig sammansättning för rent jordnötssmör enligt plain-kravet; varunamnet styrker inte frånvaro av socker/salt/olja.",
    "lammkött|raw_edible": "Belägg benfri styckdetalj för faktisk tillagning och rå mängd; uppskattade viktpaket kräver estimated-val.",
    "tonfisk|cooked_drained": "Belägg tonfisk i vatten samt deklarerad avrunnen fiskmängd; lag och nettovikt får inte räknas som fisk.",
    "pepparrot|raw_edible": "Belägg rå ätlig pepparrotsmassa efter putsning; färskost och beredd kryddblandning är andra produkter.",
    "gnocchi|as_sold": "Fullständig sammansättning som styrker ofylld potatisgnocchi; gnocchi kan även vara torr vetepasta.",
}


def main():
    records = json.loads((REPORT / "all-recipes.json").read_bytes())["recipes"]
    current = {identity(r): r for r in current_recipes()}
    manifest = manifest_entries()
    before = (ROOT / "library-manifest.json").read_bytes()
    paths = [*sorted((ROOT / "reviewed-all-20261026").glob("batch-*/standardized.json")),
             ROOT / "reviewed-all-20261026/cut-refinement/standardized.json"]
    for path in paths:
        import_pack(path)
    assert (ROOT / "library-manifest.json").read_bytes() == before
    source = ROOT / "incoming/authoring-800-20261025"
    original = json.loads((source / "SOURCE-MANIFEST.json").read_bytes())
    for row in original["preserved_files"]:
        assert hashlib.sha256((source / row["path"]).read_bytes()).hexdigest() == row["sha256"]
    assert all(r["runtime_id"] in current and not r["blockers"] for r in records)
    assert len({r["runtime_id"] for r in records}) == 2200
    original_rows = current_recipes(13)
    assert len(original_rows) == 262
    assert all(current[identity(r)].model_dump() == r.model_dump() for r in original_rows)
    assert len(manifest["current"]) + len(manifest["history"]) <= 128
    assert all((ROOT / r["file"]).stat().st_size < 16*1024*1024 for r in manifest["current"])
    selected = [current[r["runtime_id"]] for r in records]
    exceptions, dinner_bases = [], {}
    for record, recipe in zip(records, selected, strict=True):
        if recipe.design.meal_types[0] != "dinner":
            continue
        count = recipe.design.ingredient_count
        dinner_bases.setdefault(recipe.design.base_id, []).append(count)
        low, high = {"simple": (5, 7), "standard": (8, 11), "extended": (12, 15)}[record["source_id"].rsplit(":", 1)[1]]
        if not low <= count <= high:
            exceptions.append({"source_id": record["source_id"], "runtime_id": record["runtime_id"], "count": count,
                "reason": "Complete culinary construction retained; no filler ingredients or silent default changes."})
    summary = {"source_variants": len(records), "active_variants": len(current),
        "active_bases": len({r.design.base_id for r in current.values()}),
        "unchanged_original_variants": len(original_rows), "source_original_files_byte_identical": 166,
        "active_generations": len(manifest["current"]), "historical_generations": len(manifest["history"]),
        "manifest_sha256": hashlib.sha256(before).hexdigest(), "reimport_idempotent": True,
        "max_published_bytes": max((ROOT / e["file"]).stat().st_size for e in manifest["current"]),
        "source_meal_types": dict(Counter(r.design.meal_types[0] for r in selected)),
        "source_cuisines": dict(Counter(c for r in selected for c in r.design.cuisines)),
        "new_exact_product_identities": sum(r["kind"] != "definition_only" for r in entries().values()),
        "new_product_references": sum(len(r["evidence"]) for r in entries().values() if r["kind"] != "definition_only"),
        "additional_definition_only_identities": sum(r["kind"] == "definition_only" for r in entries().values()),
        "variant_count_exceptions": exceptions,
        "dinner_bases_without_10_15": [base for base, counts in dinner_bases.items() if not any(10 <= n <= 15 for n in counts)],
        "claims": "Imported content only. Not cooking-tested, not all purchase-qualified, no V2 latency claim."}
    (REPORT / "structural-summary.json").write_bytes(encoded(summary))
    inventory_path = REPORT / "product-inputs.json"
    if not inventory_path.exists():
        print({k: v for k, v in summary.items() if not isinstance(v, (list, dict))})
        return
    inventory = json.loads(inventory_path.read_bytes())
    estimated_path = REPORT / "product-inputs-estimated.json"
    estimated = json.loads(estimated_path.read_bytes()) if estimated_path.exists() else None
    estimated_blocks = {}
    if estimated:
        for row in estimated["shared_inputs"]:
            if row["status"] == "blocked_product_input":
                estimated_blocks.setdefault(row["identity"], set()).update(row["recipes"])
    research_path = Path(".local/recipes/all-ingredient-research-catalog.json")
    research = {r["identity"]: r for r in json.loads(research_path.read_bytes())["identities"]}
    known_research = Path(".local/recipes/known-input-product-research.json")
    if known_research.exists():
        research.update({r["identity"]: r for r in json.loads(known_research.read_bytes())["identities"]})
    grouped = {}
    for row in inventory["shared_inputs"]:
        if row["status"] != "blocked_product_input":
            continue
        key = row["identity"]
        group = grouped.setdefault(key, {"identity": key, "runtime_ids": set(), "scopes": [],
            "next_action": "Supply/review exact source product identity, required form, package and usable quantity; rerun ordinary qualification. No source collection performed."})
        group["runtime_ids"].update(row["recipes"])
        group["scopes"].append({k: v for k, v in row.items() if k != "recipes"})
    blockers = []
    for key, group in grouped.items():
        group["runtime_ids"] = sorted(group["runtime_ids"])
        group["affected_variants"] = len(group["runtime_ids"])
        if estimated:
            group["estimated_mode_affected_variants"] = len(estimated_blocks.get(key, ()))
        group["unapproved_source_suggestions"] = []
        definition = next((r for r in entries().values() if r["name"] + "|" + r["form"] == key), None)
        if definition and definition["kind"] == "definition_only":
            group["definition"] = definition["definition"]
            group["missing_proof"] = definition["required_classification"] + "; exact source-bound usable quantity and basis"
            group["next_action"] = "Review manufacturer/retained source documentation for this exact food, form and usable amount; bind the actual product/store/snapshot. " + definition["definition"]
        elif key in KNOWN_GAPS:
            group["definition"] = KNOWN_GAPS[key]
            group["next_action"] = KNOWN_GAPS[key]
        for candidate in research.get(key, {}).get("candidates", [])[:5]:
            p, f = candidate["product"], candidate["facts"]
            group["unapproved_source_suggestions"].append({
                **{k: p.get(k) for k in ("name", "product_id", "store_id", "gtin", "package_quantity", "package_unit", "usable_quantity", "usable_unit", "quantity_confidence", "source_provenance")},
                "facts_present": f is not None, "ingredients_complete": (f or {}).get("ingredients_complete"),
                "status": "Research suggestion only; identity/form/edible/drained/unit evidence not approved for this input."})
        blockers.append(group)
    blockers.sort(key=lambda r: (-r["affected_variants"], r["identity"]))
    counts = Counter(r["status"] for r in inventory["recipes"])
    result = {"source_scope": inventory["scope"], "clock": inventory["clock"], "runtime_commit": inventory["runtime_commit"],
        "universe_sha256": inventory["universe_sha256"], "facts_sha256": inventory["facts_sha256"],
        "conditions": inventory["conditions"], "variant_statuses": dict(counts), "blockers": blockers,
        "qualification": "Product-input coverage only; no joint basket, nutrition, allergen or organic approval."}
    if estimated:
        result["explicit_estimated_mode_statuses"] = dict(Counter(r["status"] for r in estimated["recipes"]))
    (REPORT / "purchase-blockers.json").write_bytes(encoded(result))
    lines = ["# Konkreta köphinder efter full receptimport", "",
        f"Alla 2 200 källvarianter är importerade. Fryst produktprov: {dict(counts)}.",
        "Enskilt lösta insatser är inte en godkänd gemensam inköpslista. Historiskt Malmöunderlag 23 oktober, inga nya priser insamlade.", "",
        "Varje rad nedan har exakta recept-ID:n, krav, mängder, avslagsorsaker och högst fem uttryckligen ogodkända källförslag i `purchase-blockers.json`.", "",
        "Uppskattat köpläge är ett separat uttryckligt val; det ändrar inga användarprofiler eller krav automatiskt.", "",
        "| Ingrediens/form | Blockerade, exakt | Blockerade efter aktivt estimated-val | Nästa komplettering |", "|---|---:|---:|---|"]
    for row in blockers:
        lines.append(f"| {row['identity'].replace('|', ' / ')} | {row['affected_variants']} | {row.get('estimated_mode_affected_variants', 'Ej mätt')} | {row.get('definition', row['next_action'])} |")
    (REPORT / "HINDER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"variant_statuses": dict(counts), "blocked_identities": len(blockers)})


if __name__ == "__main__":
    main()
