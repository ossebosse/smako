"""Price-free suggestions over the existing product index and curated generics."""
import json
import re
from pathlib import Path

from app.services.personal_policy import interpretation, is_nonfood
from app.services.product_search import search_text

GENERICS = json.loads((Path(__file__).parents[1] / "data/shopping_generics.json").read_text(encoding="utf8"))
AMOUNT = re.compile(r"^(.*?)\s+(\d+(?:[.,]\d+)?)\s*(kg|g|ml|cl|dl|l|st)\s*$", re.IGNORECASE)


def parse_quantity(query):
    match = AMOUNT.fullmatch(query.strip())
    name = match[1] if match else query.strip()
    amount, unit = None, None
    if match:
        quantity, source_unit = float(match[2].replace(",", ".")), match[3].lower()
        factor, unit = {"kg": (1000, "g"), "g": (1, "g"), "ml": (1, "ml"),
                        "cl": (10, "ml"), "dl": (100, "ml"), "l": (1000, "ml"), "st": (1, "st")}[source_unit]
        amount = quantity * factor
        if not 0 < amount <= 100000:
            raise ValueError("Ange en mängd större än noll, högst 100 000 g/ml/st.")
    return name, amount, unit


def generic_suggestions(query):
    name, amount, unit = parse_quantity(query)
    needle = search_text(name)
    matches = [row for row in GENERICS if not needle or any(
        needle in search_text(value) for value in [row["name"], row["query"], *row.get("aliases", [])])]
    result = []
    for row in matches[:12]:
        if unit and unit != row["unit"]:
            continue  # No hidden mass/volume/count conversion.
        result.append({"name": row["name"], "query": row["query"], "kind": "generic",
                       "quantity": amount or row["quantity"], "unit": row["unit"],
                       "properties": list(dict.fromkeys(row["properties"] + interpretation(row["query"]))),
                       "food": not is_nonfood(row["query"])})
    # Explicit free text remains available in the existing reviewed-entry dialog.
    return result


def price_free_products(result):
    """Deduplicate display labels, NEVER infer product identity from a name.

    The existing index already groups verified GTIN/package identities. Identical
    labels without that evidence are a presentation group: the UI must ask for
    an exact member or explicit either/or consent. Every member retains its key.
    """
    groups = {}
    for raw in result["results"]:
        row = {key: raw.get(key) for key in (
            "product_key", "name", "brand", "package", "package_quantity", "package_unit", "identity_basis"
        )}
        brand = row["brand"] or ""
        row["display_name"] = (brand + " " + row["name"]) if brand.casefold() not in row["name"].casefold() else row["name"]
        row["source_label"] = " / ".join(dict.fromkeys(p["store_name"] for p in raw.get("prices", []) if p.get("store_name")))
        label = (row["name"], brand, row["package_quantity"], row["package_unit"], row["package"])
        if label not in groups:
            groups[label] = {**row, "matches": []}
        group = groups[label]
        if row["product_key"] not in {member["product_key"] for member in group["matches"]}:
            group["matches"].append(row)
    return list(groups.values())
