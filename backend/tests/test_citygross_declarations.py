"""City Gross catalogue rows carry GS1 declarations; they become product facts."""
import hashlib
import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from app.services.personal_source_facts import project_raw_facts

FIXTURE = (Path(__file__).parents[2] / "grocery_data/tests/fixtures/citygross"
           / "municipal-promotion-evidence-20260923.json")


def rows():
    items = json.loads(FIXTURE.read_text(encoding="utf-8"))["items"]
    return {key: value["row"] for key, value in items.items()}


def fact(raw, product_id="p"):
    return project_raw_facts(raw, chain="citygross", product_id=product_id, snapshot_id="s",
                             source_reference="citygross:page#items[0]:hash",
                             observed_at="2026-09-23T08:04:51Z")


def test_pasta_uses_the_as_sold_per_100_declaration_not_the_serving():
    f = fact(rows()["100058571_ST"])
    assert f.nutrition == {"kcal": 359, "protein_g": 13, "carbs_g": 71, "fat_g": 2}
    assert f.nutrition_unit == "g" and f.nutrition_preparation == "as_sold"
    assert f.nutrition_basis == "Produktdeklaration per 100 g; omräknad till 100 g"
    assert f.ingredients == ("Ingredienser: DURUMVETE. Kan innehålla spår av SOJA, ÄGG och SENAP.",)
    assert f.retailer_product_id == "100058571_ST" and not f.conflicts
    assert f.field_sources["nutrition.kcal"][0]["source_product_id"] == "100058571_ST"
    # The ingredient list is evidence, never an allergen-absence proof.
    assert not f.ingredients_complete and not f.allergens_checked


def test_sausage_reads_meat_marking_and_ingredients_as_animal():
    f = fact(rows()["100308301_ST"])
    assert f.animal is True and f.nutrition["kcal"] == 250 and f.nutrition["protein_g"] == 9.5
    assert f.organic is None


def test_non_food_has_no_declaration_and_no_conflict():
    f = fact(rows()["101615621_ST"])
    assert not f.nutrition and not f.ingredients and not f.conflicts


def test_less_than_line_is_a_limit_not_a_value():
    raw = deepcopy(rows()["100308301_ST"])
    nutrients = raw["foodAndBeverageExtension"]["nutrientInformations"][0]["nutrients"]
    for row in nutrients:
        if row["typeCode"] == "PRO-":
            row["measurementPrecision"] = 1
    f = fact(raw)
    assert "protein_g" not in f.nutrition and f.nutrition["kcal"] == 250
    assert f.field_sources["nutrition_limits"][0]["field"] == "protein_g"


def test_serving_only_declaration_is_rescaled_to_100():
    raw = deepcopy(rows()["100058571_ST"])
    info = raw["foodAndBeverageExtension"]["nutrientInformations"]
    info[:] = [i for i in info if i["nutrientBasisQuantity"] == 42]
    f = fact(raw)
    assert round(f.nutrition["kcal"]) == 360 and f.nutrition_basis.startswith("Produktdeklaration per 42 g")


@pytest.mark.parametrize("change", ["prepared", "two_hundreds", "energy_mismatch", "unit", "too_much_energy"])
def test_ambiguous_or_contradictory_declarations_stay_unknown(change):
    raw = deepcopy(rows()["100058571_ST"])
    info = raw["foodAndBeverageExtension"]["nutrientInformations"]
    hundred = next(i for i in info if i["nutrientBasisQuantity"] == 100)
    if change == "prepared":
        for i in info:
            i["preparationState"] = 1
    elif change == "two_hundreds":
        info.append(deepcopy(hundred))
    elif change == "unit":
        info[:] = [hundred]
        hundred["nutrientBasisQuantityUnit"] = "styck"
    else:
        for row in hundred["nutrients"]:
            if row["unitOfMeasure"] == "kilokalori":
                row["value"] = 1200 if change == "too_much_energy" else 250
            if row["unitOfMeasure"] == "kilojoule" and change == "too_much_energy":
                row["value"] = 1200 * 4.184
    f = fact(raw)
    assert "kcal" not in f.nutrition
    assert f.conflicts


def test_organic_marking_is_the_same_gs1_code_as_coop():
    raw = deepcopy(rows()["100058571_ST"])
    raw["markings"] = [{"code": "KRAV_MARK"}]
    assert fact(raw).organic is True


def test_retained_citygross_catalogue_rows_reach_the_planner_facts(tmp_path):
    from app.models.provenance import SourceProvenance
    from app.services.personal_source_facts import _load_retained_catalog_facts

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    row = rows()["100058571_ST"]
    content = json.dumps({"items": [row]}).encode()
    (raw_root / "page.json").write_bytes(content)
    database = tmp_path / "grocery.sqlite"
    with sqlite3.connect(database) as db:
        db.executescript("CREATE TABLE products(id,chain,external_product_id,store_external_id,raw_reference,"
                         "raw_snapshot_id,catalog_snapshot_id); CREATE TABLE raw_snapshots(id,payload_hash,"
                         "payload_location,catalog_snapshot_id);")
        db.execute("INSERT INTO products VALUES (?,?,?,?,?,?,?)", ("lasagne", "citygross", "100058571_ST",
                   "3211", "raw:raw-id#items[0]", "raw-id", "v2-frozen"))
        db.execute("INSERT INTO raw_snapshots VALUES (?,?,?,?)",
                   ("raw-id", hashlib.sha256(content).hexdigest(), "page.json", "v2-frozen"))
    db.close()
    base = product("lasagne", 500, "g", 25)
    universe = prepared(base.model_copy(update={"chain": "citygross", "source_provenance": SourceProvenance(
        source_provider="own", source_channel="catalog", source_snapshot_id="v2-frozen",
        source_observed_at=NOW, provider_store_id="3211")}))
    facts = _load_retained_catalog_facts(universe, database=database, raw_root=raw_root)
    f = facts[(base.store_id, "lasagne")]
    assert f.nutrition["protein_g"] == 13 and f.ingredients
    # A row whose retained id differs from the catalogue identity is ignored.
    with sqlite3.connect(database) as db:
        db.execute("UPDATE products SET external_product_id='other'")
    db.close()
    assert (base.store_id, "lasagne") not in _load_retained_catalog_facts(
        universe, database=database, raw_root=raw_root)
