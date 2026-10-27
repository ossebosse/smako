"""Actual supplier base-unit document, plus deliberate negative mutations."""

import hashlib
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from grocery_data.app.services.product_declarations import exact_declaration, parse_declaration

SOURCES = Path(__file__).resolve().parents[2] / "reports/recipe-search-20260927/sources"


def source(gtin="07310867003841"):
    return (SOURCES / (gtin + ".html")).read_bytes(), json.loads(
        (SOURCES / (gtin + ".acquisition.json")).read_bytes()
    )


def test_explicit_paired_net_quantities_not_assumed_density():
    row = parse_declaration(*source())
    assert row["net_quantities"] == {"g": 200, "ml": 200}
    assert row["package_quantity"] == row["net_quantity"] == 200
    assert row["nutrition"]["protein_g"] == 2.9
    assert row["consumer_article"] is False
    assert row["binding_requirement"] == "existing_exact_gtin_brand_fixed_package"
    assert exact_declaration(row["name"], row["brand"], 200, "ml", rows=[row]) is None
    lactose_free = parse_declaration(*source("07310867523868"))
    assert lactose_free["net_unit"] == "ml"  # Its 100 g table proves no package mass.


def test_uppercase_declared_units_preserve_quantity_and_density_rules():
    body, acquisition = source()
    soup = BeautifulSoup(body, "html.parser")
    base = next(h for h in soup.find_all("h2") if h.get_text().startswith("Basnivå")).find_next_sibling()
    for row in base.select("tr"):
        header, cell = row.find("th"), row.find("td")
        if header and cell and header.get_text(" ", strip=True).rstrip(": ") in {
                "Förpackningsstorlek", "Nettoinnehåll värde", "Jämförmängd färdigvara"}:
            cell.string = cell.get_text(" ", strip=True).upper()
    changed = str(soup).encode()
    result = parse_declaration(changed, {**acquisition, "sha256": hashlib.sha256(changed).hexdigest()})
    assert result["net_quantities"] == {"g": 200, "ml": 200}
    assert result["binding_requirement"] == "existing_exact_gtin_brand_fixed_package"


@pytest.mark.parametrize(
    "label,value",
    [
        ("Är artikeln en logistisk enhet", "Ja"),
        ("Variabelmåttsvara", "Ja"),
        ("Målmarknadsområde", "Danmark"),
        ("Artikelns identitet, GTIN", "07310867523868"),
        ("Förpackningsstorlek", "5 dl"),
        ("Jämförmängd färdigvara", "250 gram"),
    ],
)
def test_transport_wrong_identity_market_or_pack_are_blocked(label, value):
    body, acquisition = source()
    soup = BeautifulSoup(body, "html.parser")
    base = next(
        h for h in soup.find_all("h2") if h.get_text().startswith("Basnivå")
    ).find_next_sibling()
    cell = next(
        tr.find("td")
        for tr in base.select("tr")
        if tr.find("th") and tr.find("th").get_text(" ", strip=True).rstrip(": ") == label
    )
    cell.string = value
    changed = str(soup).encode()
    with pytest.raises(ValueError):
        parse_declaration(changed, {**acquisition, "sha256": hashlib.sha256(changed).hexdigest()})
