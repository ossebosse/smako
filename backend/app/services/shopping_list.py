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
    explicit consent for grouped matching product choices. Stores are selected
    later in the basket; every member retains its exact key.
    """
    groups = {}
    for raw in result["results"]:
        row = {key: raw.get(key) for key in (
            "product_key", "name", "brand", "package", "package_quantity", "package_unit", "identity_basis"
        )}
        row["purchase_units"] = bool(raw.get("prices")) and all(p.get("purchase_usage") == "sales_unit_only" for p in raw["prices"])
        row["campaign_choice"] = bool(raw.get("prices")) and all(p.get("purchase_usage") == "variant_selection_required" for p in raw["prices"])
        row["selectable"] = row["purchase_units"] or row["campaign_choice"] or bool(row["package_quantity"] and row["package_unit"] in {"g", "ml", "st"})
        row["package"] = "Köpförpackning – innehållsmängd okänd" if row["purchase_units"] else row["package"] or "Förpackningsstorlek saknas"
        brand = row["brand"] or ""
        row["display_name"] = (brand + " " + row["name"]) if brand.casefold() not in row["name"].casefold() else row["name"]
        label = (row["name"], brand, row["package_quantity"], row["package_unit"], row["package"], row["purchase_units"], row["campaign_choice"], row["product_key"] if row["campaign_choice"] or row["purchase_units"] else None)
        if label not in groups:
            groups[label] = {**row, "matches": []}
        group = groups[label]
        if row["product_key"] not in {member["product_key"] for member in group["matches"]}:
            group["matches"].append(row)
    return sorted(groups.values(), key=lambda row: not row["selectable"])


def generic_positions(prepared, query):
    """Products a generic query retrieves, as the planner retrieves them.

    Reuses the canonical index and the ingredient search; no name similarity
    is added, so a product only falls under a generic it could be bought for.
    The plain (not library-alias) search keeps add-time and plan-time checks equal.
    """
    from app.services.ingredient_normalizer import canonicalize_ingredient_name
    from app.services.meal_prepared_artifacts import ingredient_search_positions

    canonical = canonicalize_ingredient_name(query)
    positions = set(ingredient_search_positions(prepared, query, complete=False))
    for entry in prepared.universe.indexes.canonical:
        if entry.key == canonical:
            positions.update(entry.product_indexes)
    return positions


def falls_under(prepared, product_keys, generic):
    """Every exact identity has a product retrieved by the generic and matching its properties."""
    from app.services.personal_policy import properties_match

    members = generic_positions(prepared, generic["query"])
    products = prepared.universe.products
    return bool(product_keys) and all(
        any(i in members and properties_match(products[i], generic["properties"])
            for i in prepared.product_search_index.groups.get(key, ()))
        for key in product_keys
    )


def classify_products(prepared, query, product_keys):
    """The first curated, then the typed generic that all chosen products fall under."""
    name, _amount, _unit = parse_quantity(query)
    candidates = [{"name": row["name"], "query": row["query"], "properties": row["properties"]}
                  for row in generic_suggestions(name)]
    typed = name.strip()
    if typed and typed.casefold() not in {row["query"].casefold() for row in candidates}:
        candidates.append({"name": typed[:1].upper() + typed[1:], "query": typed,
                           "properties": interpretation(typed)})
    for candidate in candidates:
        if falls_under(prepared, product_keys, candidate):
            return candidate
    return None
