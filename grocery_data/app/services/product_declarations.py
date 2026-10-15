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
from urllib.parse import urljoin, urlparse

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
    bases = re.findall(r"\(per 100 (g|ml)\)", text)
    if len(bases) != 1 or re.search(
        r"tillagad|beredd|portion", text, re.IGNORECASE
    ):
        raise ValueError("declaration_basis_or_preparation_unverified")
    basis_unit = bases[0]
    if basis_unit == 'ml' and unit != 'ml':
        raise ValueError('declaration_volume_basis_requires_volume_package')
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
    identity_names = [names[0]]
    # Manufacturer explicitly calls the whole named product a durum-wheat
    # pasta. The retailer may append that exact category noun; never remove
    # flavours, ingredients, qualifiers or arbitrary words from its identity.
    if re.fullmatch(re.escape(names[0].strip()) + r"\. Pasta gjord på durumvete\. \d+ gram\.", description.strip(), re.IGNORECASE):
        identity_names.append(names[0].strip() + ' Pasta')
    return {
        "gtin": gtin,
        "name": names[0],
        "brand": brands[0],
        "package_quantity": quantity,
        "package_unit": unit,
        "ingredients": ingredients.get_text(" ", strip=True),
        "nutrition": macros,
        "basis_quantity": 100,
        "basis_unit": basis_unit,
        "preparation": "as_sold",
        "description": description.strip(),
        "nutrition_text": text,
        "source": dict(acquisition),
        "parser": "garant-explicit-gs1-declaration-v1",
        **({"identity_names": identity_names,
            "binding_requirement": "unique_exact_complete_brand_variant_fixed_pack",
            "identity_source": dict(acquisition)} if len(identity_names) > 1 or (basis_unit == 'ml' and unit == 'ml') else {}),
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


def parse_gogreen(body, acquisition, identity_body, identity_acquisition):
    """Complete named product plus independently linked official package size.

    GoGreen's page does not publish a GTIN. Keep it unknown: the manufacturer's
    exact product-index link supplies the fixed package without interpreting a
    filename or borrowing the size of a neighbouring cooked product.
    """
    for document, source in ((body, acquisition), (identity_body, identity_acquisition)):
        if (not document or not source or urlparse(source["url"]).hostname != "www.gogreen.se"
                or source.get("status") != 200 or not source.get("observed_at")
                or hashlib.sha256(document).hexdigest() != source.get("sha256")
                or source.get("resolved_url", source["url"]) != source["url"]):
            raise ValueError("unverified_gogreen_source")
    if urlparse(identity_acquisition["url"]).path != "/produkter/":
        raise ValueError("unverified_gogreen_product_index")
    soup = BeautifulSoup(body, "html.parser")
    index = BeautifulSoup(identity_body, "html.parser")
    headings = soup.find_all("h1")
    brands = soup.find_all("meta", attrs={"property": "og:site_name"})
    structured = [json.loads(node.get_text()) for node in soup.select('script[type="application/ld+json"]')]
    structured = [row for row in structured if str(row.get("@type", "")).lower() == "product"]
    if len(headings) != 1 or len(brands) != 1 or len(structured) != 1:
        raise ValueError("gogreen_product_identity_not_unique")
    name = headings[0].get_text(" ", strip=True)
    brand = brands[0].get("content")
    if brand != "GoGreen" or identity_text(structured[0]["name"]) != identity_text(name):
        raise ValueError("gogreen_product_identity_conflict")
    links = [a for a in index.select("a.callout-link[href]")
             if urljoin(identity_acquisition["url"], a["href"]) == acquisition["url"]]
    if len(links) != 1:
        raise ValueError("gogreen_package_identity_not_unique")
    title = links[0].select_one(".callout-title")
    measure = links[0].select_one(".callout-measure")
    if not title or not measure or identity_text(title.get_text(" ", strip=True)) != identity_text(name):
        raise ValueError("gogreen_package_variant_conflict")
    pack = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*g", measure.get_text(" ", strip=True))
    if not pack:
        raise ValueError("gogreen_fixed_gram_package_unverified")
    ingredients_node = soup.select_one(".content-productcontents")
    if not ingredients_node:
        raise ValueError("gogreen_ingredients_missing")
    # Ingredient list is the labelled paragraph, not the site's generic allergy
    # guidance or country-of-origin paragraph following it.
    ingredient_paragraphs = ingredients_node.find_all("p", recursive=False)
    if not ingredient_paragraphs:
        raise ValueError("gogreen_ingredients_missing")
    ingredients = ingredient_paragraphs[0].get_text(" ", strip=True)
    nutrient_headers = [h for h in soup.find_all("h2") if h.get_text(strip=True) == "Näringsvärde per 100 g"]
    if len(nutrient_headers) != 1:
        raise ValueError("gogreen_nutrition_basis_unverified")
    table = nutrient_headers[0].find_next_sibling("table")
    if table is None:
        raise ValueError("gogreen_nutrition_missing")
    values = {}
    for row in table.select("tr"):
        cells = row.find_all("td")
        if len(cells) != 2:
            continue
        label, value = (cell.get_text(" ", strip=True) for cell in cells)
        key = {"Energi": "kcal", "Fett": "fat_g", "Kolhydrat": "carbs_g", "Protein": "protein_g"}.get(label)
        if key is None:
            continue
        pattern = r"[\d,.]+\s*kJ/\s*([\d,.]+)\s*kcal" if key == "kcal" else r"([\d,.]+)\s*g"
        match = re.fullmatch(pattern, value)
        if not match or key in values:
            raise ValueError("gogreen_nutrition_value_unverified")
        values[key] = float(match[1].replace(",", "."))
    if len(values) != 4 or not all(math.isfinite(v) and v >= 0 for v in values.values()):
        raise ValueError("gogreen_nutrition_incomplete")
    forms = []
    if identity_text(ingredients) == "torkade skalade och delade röda linser":
        forms.append("red_split")
    return {"gtin": None, "name": name, "brand": brand,
            "package_quantity": float(pack[1].replace(",", ".")), "package_unit": "g",
            "ingredients": ingredients, "nutrition": values, "basis_quantity": 100,
            "basis_unit": "g", "preparation": "as_sold", "culinary_forms": forms,
            "source": dict(acquisition), "identity_source": dict(identity_acquisition),
            "binding_requirement": "unique_exact_complete_brand_variant_fixed_pack",
            "parser": "gogreen-linked-product-declaration-v1"}


def parse_declaration(body, acquisition, *, identity_body=None, identity_acquisition=None):
    host = urlparse(acquisition["url"]).hostname
    if host == "www.gogreen.se":
        return parse_gogreen(body, acquisition, identity_body, identity_acquisition)
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



def parse_fontana_corroboration(body, acquisition, identity_row):
    """Retain a second official table for the same complete name and fixed pack.

    This cannot supply a GTIN or override an existing declaration. The caller
    attaches it to the already verified Dabas identity and preserves conflicts.
    """
    if (urlparse(acquisition["url"]).hostname != "www.fontana.se"
            or not urlparse(acquisition["url"]).path.startswith("/produkt/")
            or acquisition.get("status") != 200 or not acquisition.get("observed_at")
            or hashlib.sha256(body).hexdigest() != acquisition["sha256"]
            or identity_row.get("parser") not in {"dabas-consumer-quantity-v1", "dabas-base-quantity-v2"}
            or identity_text(identity_row["brand"]) != "fontana"):
        raise ValueError("official_corroboration_acquisition_unverified")
    soup = BeautifulSoup(body, "html.parser")
    headings = soup.select("h1")
    text = soup.get_text(" ", strip=True)
    packs = re.findall(r"Tillgänglig i (\d+(?:[,.]\d+)?) (g|ml)\b", text)
    if (len(headings) != 1 or identity_text(headings[0].get_text(" ", strip=True)) != identity_text(identity_row["name"])
            or len(packs) != 1
            or (float(packs[0][0].replace(",", ".")), packs[0][1]) != (identity_row["package_quantity"], identity_row["package_unit"])):
        raise ValueError("official_corroboration_identity_mismatch")
    tables = [h for h in soup.select("h2") if h.get_text(" ", strip=True) == "Näringsvärden per 100g"]
    if len(tables) != 1:
        raise ValueError("official_corroboration_basis_unverified")
    nutrition_text = text.split("Näringsvärden per 100g", 1)[1].split("Köp denna produkt", 1)[0]
    macros = {}
    for key, pattern in {"kcal": r"([\d.,]+) kcal", "fat_g": r"\bFett ([\d.,]+) g",
                         "carbs_g": r"\bKolhydrater ([\d.,]+) g", "protein_g": r"\bProtein ([\d.,]+) g"}.items():
        values = re.findall(pattern, nutrition_text)
        if len(values) != 1:
            raise ValueError("official_corroboration_nutrition_ambiguous")
        macros[key] = float(values[0].replace(",", "."))
    return {"name": identity_row["name"], "brand": identity_row["brand"],
            "package_quantity": identity_row["package_quantity"], "package_unit": identity_row["package_unit"],
            "nutrition": macros, "basis_quantity": 100, "basis_unit": "g",
            "nutrition_text": nutrition_text.strip(), "source": dict(acquisition),
            "identity_source": identity_row["source"],
            "identity_method": "exact_complete_manufacturer_name_fixed_package_linked_dabas_identity",
            "parser": "fontana-labelled-corroboration-v1"}


def parse_zeinas_juice(body, acquisition):
    """Read one manufacturer's complete juice variant; retain the stated unit.

    The page gives a volume pack and nutrients per gram. It supplies no density,
    GTIN or per-volume nutrient table, so none is synthesized.
    """
    url = acquisition.get('url')
    if (url != 'https://zeinas.se/produkter/citronjuice/'
            or acquisition.get('status') != 200 or not acquisition.get('observed_at')
            or hashlib.sha256(body).hexdigest() != acquisition.get('sha256')):
        raise ValueError('unverified_zeinas_source')
    soup = BeautifulSoup(body, 'html.parser')
    titles = soup.select('h1.product_title')
    descriptions = soup.select('.woocommerce-product-details__short-description')
    panels = soup.select('#tab-description')
    if len(titles) != 1 or len(descriptions) != 1 or len(panels) != 1:
        raise ValueError('ambiguous_zeinas_product')
    name = titles[0].get_text(' ', strip=True)
    description = descriptions[0].get_text(' ', strip=True)
    packs = re.findall(r'FÖRPACKNINGSSTORLEK:\s*(\d+)\s*ML\b', description)
    if name != 'Citronjuice' or 'Zeinas Citronjuice' not in description or len(packs) != 1:
        raise ValueError('unqualified_zeinas_identity')
    headings = panels[0].select('h3')
    ingredients = [h.find_next_sibling('p') for h in headings if h.get_text(strip=True) == 'INGREDIENSER:']
    nutrients = [h.find_next_sibling('table') for h in headings if h.get_text(strip=True) == 'NÄRINGSVÄRDE PER 100G:']
    if len(ingredients) != 1 or ingredients[0] is None or len(nutrients) != 1 or nutrients[0] is None:
        raise ValueError('unqualified_zeinas_declaration')
    values = {}
    keys = {'Energi': ('kcal', r'\d+(?:[,.]\d+)? kJ / (\d+(?:[,.]\d+)?) kcal'),
            'Fett': ('fat_g', r'(\d+(?:[,.]\d+)?) g'),
            'Kolhydrat': ('carbs_g', r'(\d+(?:[,.]\d+)?) g'),
            'Protein': ('protein_g', r'(\d+(?:[,.]\d+)?) g')}
    for tr in nutrients[0].select('tr'):
        cells = [c.get_text(' ', strip=True) for c in tr.select('td')]
        if len(cells) != 2 or cells[0] not in keys:
            continue
        key, pattern = keys[cells[0]]
        match = re.fullmatch(pattern, cells[1])
        if not match or key in values:
            raise ValueError('unqualified_zeinas_nutrient')
        values[key] = float(match[1].replace(',', '.'))
    if set(values) != {v[0] for v in keys.values()}:
        raise ValueError('missing_zeinas_nutrient')
    return {'name': name, 'brand': 'Zeinas', 'gtin': None,
            'package_quantity': float(packs[0]), 'package_unit': 'ml',
            'ingredients': ingredients[0].get_text(' ', strip=True),
            'nutrition': values, 'basis_unit': 'g', 'basis_quantity': 100,
            'source': dict(acquisition), 'identity_source': dict(acquisition),
            'binding_requirement': 'unique_exact_complete_brand_variant_fixed_pack',
            'parser': 'zeinas-explicit-juice-declaration-v1'}


def declarations():
    return json.loads(PATH.read_bytes())["declarations"] if PATH.exists() else []


def culinary_declarations():
    """Positive manufacturer attributes, separate from nutrient declarations."""
    return json.loads(PATH.read_bytes()).get("culinary_declarations", []) if PATH.exists() else []


def parse_santa_maria_culinary(body, acquisition):
    """Bind explicit mildness to one complete named variant and declared unit pack.

    This document may omit ingredients/nutrients. It supplies neither of them,
    no GTIN, no price and no allergen assurance. A case count is retained and
    never multiplied into the independently priced consumer package.
    """
    if (urlparse(acquisition["url"]).hostname != "www.santamariaworld.com"
            or not urlparse(acquisition["url"]).path.startswith("/se/produkter/")
            or acquisition.get("status") != 200 or not acquisition.get("observed_at")
            or hashlib.sha256(body).hexdigest() != acquisition["sha256"]):
        raise ValueError("unverified_manufacturer_culinary_source")
    soup = BeautifulSoup(body, "html.parser")
    main = soup.find("main")
    if main is None:
        raise ValueError("manufacturer_product_content_missing")
    headings = {h.get_text(" ", strip=True) for h in main.select("h1")}
    if len(headings) != 1:
        raise ValueError("manufacturer_product_identity_ambiguous")
    match = re.fullmatch(r"(.+?)\s+(\d+(?:[.,]\d+)?)Gx(\d+)", headings.pop())
    if not match:
        raise ValueError("manufacturer_consumer_pack_unspecified")
    text = main.get_text(" ", strip=True)
    # A statement about THIS spice, not a recipe suggestion or a heat number
    # whose interpretation is not declared. Keep this parser conservative.
    if identity_text(match[1]) != "paprikapulver" or "Paprika är mild och smakrik." not in text:
        raise ValueError("manufacturer_mild_spice_not_declared")
    return {"name": match[1], "brand": "Santa Maria", "gtin": None,
            "package_quantity": float(match[2].replace(",", ".")), "package_unit": "g",
            "declared_case_units": int(match[3]), "culinary_forms": ["mild_spice"],
            "evidence": {"heading": match[0], "statement": "Paprika är mild och smakrik."},
            "source": dict(acquisition),
            "binding_requirement": "unique_exact_complete_brand_variant_fixed_pack",
            "parser": "santa-maria-explicit-culinary-v1"}


def exact_declaration(
    name, brand, quantity, unit, *, gtin=None, rows=None, identity_qualifiers=None
):
    if not brand or not quantity or unit not in {"g", "ml"}:
        return None
    candidates = [
        r
        for r in (declarations() if rows is None else rows)
        if r.get("parser") not in {"dabas-consumer-quantity-v1", "dabas-base-quantity-v2"}
        and identity_text(name) in {identity_text(n) for n in r.get("identity_names", [r["name"]])}
        and identity_text(r["brand"]) == identity_text(brand)
        and r["package_quantity"] == float(quantity)
        and r["package_unit"] == unit
        and (not r.get("identity_qualifiers") or r["identity_qualifiers"] == identity_qualifiers)
    ]
    # Conflicting same-name variants cannot be resolved merely by cheap price.
    if gtin:
        expected = normalize_gtin(gtin).normalized_gtin.zfill(14)
        candidates = [r for r in candidates if r.get("gtin") and normalize_gtin(r["gtin"]).normalized_gtin.zfill(14) == expected]
    if len(candidates) != 1:
        return None
    return candidates[0]
