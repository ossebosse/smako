"""Summarize actual resolve traces; accepted here is not nutrition approval."""
import json
from pathlib import Path

R = Path(__file__).parent
result = {}
for arm in ("before", "after"):
    raw = json.loads((R / "profile" / f"diagnose-{arm}.json").read_bytes())
    products = {
        (r["product"]["store_id"], r["product"]["product_id"]): r["product"]
        for r in raw["products"]
    }
    rows = []
    for query in raw["queries"]:
        accepted = []
        for candidate in query.get("accepted", []):
            product = products.get((candidate["store_id"], candidate["product_id"]), {})
            accepted.append({
                "id": candidate["product_id"], "store": candidate["store_id"],
                "store_name": candidate["store_name"], "name": candidate["product_name"],
                "brand": product.get("brand"), "gtin": candidate.get("gtin"),
                "package": [candidate.get("package_quantity"), candidate.get("package_unit")],
                "usable": [candidate.get("usable_quantity"), candidate.get("usable_unit")],
                "source_snapshot": candidate.get("source_provenance", {}).get("source_snapshot_id"),
                "quantity_confidence": candidate.get("quantity_confidence"),
                "qualification_scope": "resolve: recipe identity, usable unit and purchase price; nutrition assessed separately",
            })
        first_stops = {}
        for trace in query["trace"]:
            if trace["outcome"] == "stopped":
                first_stops.setdefault((trace["store"], trace["id"]), trace)
        rows.append({"ingredient": query["name"], "unit": query["unit"],
                     "accepted": accepted, "first_stops": list(first_stops.values())})
    result[arm] = rows
(R / "candidate-review.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
print(json.dumps({arm: [{"ingredient": q["ingredient"], "unit": q["unit"],
                        "accepted": len(q["accepted"]), "stopped": len(q["first_stops"])}
                       for q in rows] for arm, rows in result.items()}, ensure_ascii=False))
