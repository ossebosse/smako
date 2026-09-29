"""Official declarations, independent of campaigns and retailer prices.

Exact GTIN where present; otherwise a unique complete branded variant and fixed
package, never fuzzy title similarity. This registry cannot authorize prices.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from grocery_data.app.domain.identifiers import normalize_gtin

PATH = Path(__file__).parents[1] / "data/product_declarations.json"


def identity_text(value):
    # Printed separator glyphs, not synonyms, token subsets or word reordering.
    return " ".join(re.findall(r"\w+|%", unicodedata.normalize("NFKC", value).casefold()))


def parse_garant(body, acquisition):
    if (
        urlparse(acquisition["url"]).hostname != "www.garantskafferiet.se"
        or not urlparse(acquisition["url"]).path.startswith("/vara-produkter/")
        or acquisition.get("status", acquisition.get("http_status")) != 200
        or hashlib.sha256(body).hexdigest() != acquisition["sha256"]
        or not acquisition.get("observed_at")
    ):
        raise ValueError("official_declaration_acquisition_unverified")
    soup = BeautifulSoup(body, "html.parser")
    products = [
        j["itemOffered"]
        for node in soup.select('script[type="application/ld+json"]')
        if "itemOffered" in (j := json.loads(node.string or node.get_text()))
    ]
    if len(products) != 1:
        raise ValueError("declaration_product_identity_not_unique")
    p = products[0]
    gtin = normalize_gtin(p["gtin"]["value"]["@value"]).normalized_gtin
    names = [x["@value"] for x in p["productName"] if x.get("@language") == "sv"]
    brands = [x["@value"] for x in p["brand"]["brandName"] if x.get("@language") == "sv"]
    description = soup.find("meta", attrs={"name": "description"})["content"]
    packs = re.findall(r"(?<![\w.,])(\d+(?:[,.]\d+)?)\s+(gram|kg|ml|liter)\b", description)
    if len(names) != 1 or len(brands) != 1 or len(packs) != 1:
        raise ValueError("declaration_name_brand_package_not_unique")
    factor, unit = {"gram": (1, "g"), "kg": (1000, "g"), "ml": (1, "ml"), "liter": (1000, "ml")}[
        packs[0][1]
    ]
    quantity = float(packs[0][0].replace(",", ".")) * factor
    ingredients = soup.select_one("#ingredients-content")
    nutrition = soup.select_one("#nutrition-content")
    if not ingredients or not nutrition:
        raise ValueError("declaration_contents_missing")
    text = nutrition.get_text(" ", strip=True)
    if len(re.findall(r"\(per 100 g\)", text)) != 1 or re.search(
        r"tillagad|beredd|portion", text, re.IGNORECASE
    ):
        raise ValueError("declaration_basis_or_preparation_unverified")
    macros = {}
    for key, pattern in {
        "kcal": r"\b([\d.,]+)\s+kcal\b",
        "fat_g": r"\bFett\s+([\d.,]+)\s+g\b",
        "carbs_g": r"\bKolhydrat\s+([\d.,]+)\s+g\b",
        "protein_g": r"\bProtein\s+([\d.,]+)\s+g\b",
    }.items():
        values = re.findall(pattern, text)
        if len(values) != 1:
            raise ValueError("declaration_macronutrient_missing_or_ambiguous:" + key)
        macros[key] = float(values[0].replace(",", "."))
    if not all(math.isfinite(v) and v >= 0 for v in macros.values()):
        raise ValueError("invalid_declared_macronutrient")
    return {
        "gtin": gtin,
        "name": names[0],
        "brand": brands[0],
        "package_quantity": quantity,
        "package_unit": unit,
        "ingredients": ingredients.get_text(" ", strip=True),
        "nutrition": macros,
        "basis_quantity": 100,
        "basis_unit": "g",
        "preparation": "as_sold",
        "description": description.strip(),
        "nutrition_text": text,
        "source": dict(acquisition),
        "parser": "garant-explicit-gs1-declaration-v1",
    }


def parse_arla(body, acquisition):
    """Official JSON-LD identity plus explicit labelled declaration; no campaign data."""
    if (
        urlparse(acquisition["url"]).hostname != "www.arla.se"
        or not urlparse(acquisition["url"]).path.startswith("/produkter/")
        or acquisition.get("status") != 200
        or not acquisition.get("observed_at")
        or hashlib.sha256(body).hexdigest() != acquisition["sha256"]
    ):
        raise ValueError("official_declaration_acquisition_unverified")
    soup = BeautifulSoup(body, "html.parser")
    rows = []
    for node in soup.select('script[type="application/ld+json"]'):
        value = json.loads(node.get_text())
        rows.extend(value if isinstance(value, list) else [value])
    rows = [r for r in rows if r.get("@type") == "Product"]
    if len(rows) != 1:
        raise ValueError("declaration_product_identity_not_unique")
    row = rows[0]
    gtin = normalize_gtin(row["gtin13"]).normalized_gtin
    name = re.fullmatch(
        r"(.+?)\s+(\d+(?:[,.]\d+)?)%\s+ca\s*(\d+(?:[,.]\d+)?)\s*(kg|g)", row["name"]
    )
    if not name:
        raise ValueError("declaration_explicit_fat_and_approximate_pack_required")
    quantity = float(name[3].replace(",", ".")) * (1000 if name[4] == "kg" else 1)

    def labelled(label):
        headings = [h for h in soup.select("h3,h4") if h.get_text(" ", strip=True) == label]
        if len(headings) != 1:
            raise ValueError("declaration_label_not_unique:" + label)
        return headings[0].find_next_sibling("p").get_text(" ", strip=True)

    if labelled("Streckkod") != gtin or labelled("Vikt/volym") != f"{quantity:g} g":
        raise ValueError("declaration_identity_conflict")
    macros = {}
    texts = []
    for tr in soup.select("table.c-product-tab__nutrition-table tr"):
        key = tr.select_one("strong").get_text(" ", strip=True)
        if key not in {"Energi", "Fett", "Kolhydrat", "Protein"}:
            continue
        spans = [x.get_text(" ", strip=True) for x in tr.select("span")]
        if len(spans) != 2 or spans[0] != "pr. 100 g":
            raise ValueError("declaration_basis_unverified")
        amount = re.fullmatch(r"(?:[0-9.,]+ kJ / )?([0-9.,]+) (kcal|gram)", spans[1])
        if not amount or (key == "Energi") != (amount[2] == "kcal"):
            raise ValueError("declaration_value_unverified")
        field = {"Energi": "kcal", "Fett": "fat_g", "Kolhydrat": "carbs_g", "Protein": "protein_g"}[
            key
        ]
        if field in macros:
            raise ValueError("duplicate_macronutrient")
        macros[field] = float(amount[1].replace(",", "."))
        texts.append(tr.get_text(" ", strip=True))
    if len(macros) != 4 or not all(math.isfinite(v) and v >= 0 for v in macros.values()):
        raise ValueError("incomplete_macronutrients")
    return {
        "gtin": gtin,
        "name": name[1],
        "brand": row["brand"]["name"].replace("®", "").strip(),
        "package_quantity": quantity,
        "package_unit": "g",
        "identity_qualifiers": {
            "fat_percent": float(name[2].replace(",", ".")),
            "package_basis": "source_approximation",
        },
        "ingredients": labelled("Ingredienser"),
        "nutrition": macros,
        "basis_quantity": 100,
        "basis_unit": "g",
        "preparation": "as_sold",
        "description": row["description"],
        "nutrition_text": " ".join(texts),
        "source": dict(acquisition),
        "parser": "arla-jsonld-labelled-declaration-v1",
    }


def parse_declaration(body, acquisition):
    host = urlparse(acquisition["url"]).hostname
    if host == "www.dabas.com":
        return parse_dabas(body, acquisition)
    if host == "www.arla.se":
        return parse_arla(body, acquisition)
    return parse_garant(body, acquisition)


def parse_dabas(body, acquisition):
    """Supplier's consumer-level fields, never transport gross weight.

    A drained comparison quantity establishes quantity only, not the nutrient
    table's draining basis. Preserve both without silently equating them.
    """
    if (urlparse(acquisition["url"]).hostname != "www.dabas.com"
            or acquisition.get("status") != 200
            or hashlib.sha256(body).hexdigest() != acquisition["sha256"]
            or not acquisition.get("observed_at")):
        raise ValueError("unverified_dabas_source")
    soup = BeautifulSoup(body, "html.parser")
    headings = [h for h in soup.find_all("h2") if h.get_text().startswith("Basnivå")]
    if len(headings) != 1:
        raise ValueError("ambiguous_consumer_level")
    base = headings[0].find_next_sibling()

    def cells(node):
        pairs = []
        for row in node.select("tr"):
            h, d = row.find("th"), row.find("td")
            if h and d:
                pairs.append((h.get_text(" ", strip=True).rstrip(": "), d.get_text(" ", strip=True)))
        return pairs

    def field(pairs, label):
        values = {v for k, v in pairs if k == label}
        if len(values) != 1:
            raise ValueError("missing_or_conflicting_dabas_field:" + label)
        return values.pop()

    def amount(value):
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*(g|gr|gram|kg|ml|milliliter|dl|l)", value)
        if not match:
            raise ValueError("unsupported_dabas_quantity:" + value)
        multiplier, unit = {"g": (1, "g"), "gr": (1, "g"), "gram": (1, "g"),
                            "kg": (1000, "g"), "ml": (1, "ml"), "milliliter": (1, "ml"),
                            "dl": (100, "ml"), "l": (1000, "ml")}[match[2]]
        return float(match[1].replace(",", ".")) * multiplier, unit

    fields = cells(base)
    gtin = normalize_gtin(field(fields, "Artikelns identitet, GTIN")).normalized_gtin
    if (field(fields, "Målmarknadsområde") != "Sverige"
            or field(fields, "Konsumentartikel") not in {"Ja", "Nej"}
            or field(fields, "Är artikeln en logistisk enhet") != "Nej"
            or field(fields, "Variabelmåttsvara") != "Nej"
            or gtin != normalize_gtin(urlparse(acquisition["url"]).path.rstrip("/").split("/")[-1]).normalized_gtin):
        raise ValueError("unsupported_dabas_scope")
    pack, pack_unit = amount(field(fields, "Förpackningsstorlek"))
    # A base GTIN can be distributed to retail and food service. The consumer
    # flag does not change its explicitly declared net content. These rows may
    # only supplement an existing exact-GTIN/brand/package retail identity;
    # they must never enter name-based declaration matching or authorize price.
    quantities = {}
    for label, value in fields:
        if label != "Nettoinnehåll värde":
            continue
        quantity, quantity_unit = amount(value)
        if quantity_unit in quantities and quantities[quantity_unit] != quantity:
            raise ValueError("conflicting_dabas_net_quantity:" + quantity_unit)
        if quantity <= 0:
            raise ValueError("invalid_dabas_net_quantity")
        quantities[quantity_unit] = quantity
    if not quantities or (pack_unit in quantities and quantities[pack_unit] != pack):
        raise ValueError("dabas_package_net_quantity_mismatch")
    net_unit = "g" if "g" in quantities else "ml"
    net = quantities[net_unit]
    compared, compared_unit = amount(field(fields, "Jämförmängd färdigvara"))
    comparison_basis = field(fields, "Jämförmängd kod")
    if (comparison_basis in {"Per kilogram", "Per liter"}
            and compared_unit in quantities and compared != quantities[compared_unit]):
        raise ValueError("conflicting_dabas_comparison_and_net_quantity")
    h = [h for h in soup.find_all("h2") if h.get_text(strip=True) == "Näringsvärde"]
    if len(h) != 1:
        raise ValueError("ambiguous_dabas_nutrition")
    nutrients = cells(h[0].find_next_sibling())
    if field(nutrients, "Tillagningsstatus") != "Ej tillagad":
        raise ValueError("unsupported_dabas_preparation")
    basis, unit = amount(field(nutrients, "Basmängd").removeprefix("Per "))
    values = {}
    for label, key, value_unit in (("Energi", "kcal", "kcal"), ("Fett", "fat_g", "g"),
                                    ("Kolhydrat", "carbs_g", "g"), ("Protein", "protein_g", "g")):
        hits = [v for k, v in nutrients if k == label and v.endswith(" " + value_unit)]
        if len(hits) != 1 or not re.fullmatch(r"\d+(?:[.,]\d+)? " + value_unit, hits[0]):
            raise ValueError("unqualified_dabas_nutrient:" + key)
        values[key] = float(hits[0].split()[0].replace(",", ".")) * 100 / basis
    ingredient_headers = [h for h in soup.find_all("h2") if h.get_text(strip=True) == "Ingredienser"]
    ingredients = ingredient_headers[0].find_next_sibling().get_text(" ", strip=True) if len(ingredient_headers) == 1 else ""
    result = {"gtin": gtin, "name": field(fields, "Produktnamn"), "brand": field(fields, "Varumärke"),
            "package_quantity": pack, "package_unit": pack_unit,
            "net_quantity": net, "net_unit": net_unit,
            "comparison_quantity": compared, "comparison_unit": compared_unit,
            "comparison_basis": comparison_basis,
            "ingredients": ingredients, "nutrition": values, "basis_quantity": 100,
            "basis_unit": unit, "preparation": "as_sold_draining_unspecified" if comparison_basis == "Per avrunnen vikt" else "as_sold",
            "document_version": field(fields, "Dokumentets giltighetstidpunkt"),
            "source": dict(acquisition),
            "consumer_article": field(fields, "Konsumentartikel") == "Ja",
            "net_quantities": quantities,
            "binding_requirement": "existing_exact_gtin_brand_fixed_package",
            "parser": "dabas-base-quantity-v2"}
    if result["consumer_article"] and len(quantities) == 1:
        for key in ("consumer_article", "net_quantities", "binding_requirement"):
            result.pop(key)
        result["parser"] = "dabas-consumer-quantity-v1"
    return result



def declarations():
    return json.loads(PATH.read_bytes())["declarations"] if PATH.exists() else []


def exact_declaration(
    name, brand, quantity, unit, *, gtin=None, rows=None, identity_qualifiers=None
):
    if not brand or not quantity or unit not in {"g", "ml"}:
        return None
    candidates = [
        r
        for r in (declarations() if rows is None else rows)
        if r.get("parser") not in {"dabas-consumer-quantity-v1", "dabas-base-quantity-v2"}
        and identity_text(r["name"]) == identity_text(name)
        and identity_text(r["brand"]) == identity_text(brand)
        and r["package_quantity"] == float(quantity)
        and r["package_unit"] == unit
        and (not r.get("identity_qualifiers") or r["identity_qualifiers"] == identity_qualifiers)
    ]
    # Conflicting same-name variants cannot be resolved merely by cheap price.
    if gtin:
        candidates = [r for r in candidates if r["gtin"] == normalize_gtin(gtin).normalized_gtin]
    if len(candidates) != 1:
        return None
    return candidates[0]
