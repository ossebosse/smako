"""Authentic imported declarations, synthetic negative identity boundaries."""


import pytest
from app.services.official_product_facts import project_usable_quantity, supplement_catalog_facts

from backend.tests.test_personal_planning_v2 import product
from backend.tests.test_personal_qualified_facts import facts
from grocery_data.app.services.product_declarations import declarations


def red_lentils(**changes):
    return product("Röda Linser", 400, "g", 25, brand="Gogreen").model_copy(update=changes)


def test_complete_manufacturer_variant_reaches_catalog_without_inventing_gtin_or_price():
    p = red_lentils()
    before = p.model_dump_json()
    f = supplement_catalog_facts([p], {})[(p.store_id, p.product_id)]
    assert f.nutrition == {"kcal": 349.0, "fat_g": 1.8, "carbs_g": 51.0, "protein_g": 26.0}
    assert f.product_classification == ("red_split",)
    assert f.ingredients == ("Torkade, skalade och delade röda linser.",)
    assert f.ingredients_complete
    assert not f.allergens_checked
    proof = f.field_sources["product_classification"][0]
    assert proof["identity_method"] == "unique_exact_complete_brand_variant_fixed_pack"
    assert proof["supplier_gtin"] is None and p.gtin is None
    assert proof["bound_product_id"] == p.product_id
    assert proof["bound_store_id"] == p.store_id
    assert proof["bound_snapshot_id"] == p.source_provenance.source_snapshot_id
    assert proof["source_package_quantity"] == 400
    assert proof["sha256"] and proof["identity_source"]["sha256"]
    assert p.model_dump_json() == before


@pytest.mark.parametrize("changes", [
    {"name": "Röda Linser Färdigkokta"}, {"brand": "Other"},
    {"package_quantity": 380}, {"package_unit": "ml"}, {"gtin": "7310130009716"},
    {"source_provenance": None}, {"sale_model": "unknown"},
])
def test_named_facts_never_cross_variant_package_or_explicit_gtin(changes):
    p = red_lentils(**changes)
    assert (p.store_id, p.product_id) not in supplement_catalog_facts([p], {})


def test_conflicting_nutrition_remains_blocked():
    p = red_lentils()
    prior = facts(p, nutrition={"protein_g": 99}, nutrition_unit="g", nutrition_basis="per 100 g")
    f = supplement_catalog_facts([p], {(p.store_id, p.product_id): prior})[(p.store_id, p.product_id)]
    assert f.nutrition == prior.nutrition
    assert "supplier_nutrition_conflict" in f.conflicts


def test_indexed_declarations_preserve_aliases_ambiguity_and_current_rows(monkeypatch):
    from copy import deepcopy

    from grocery_data.app.services import product_declarations as registry

    row = deepcopy(next(r for r in declarations() if r.get("parser") == "gogreen-linked-product-declaration-v1"))
    # Two printed aliases with the same normalized spelling are one declaration.
    row["identity_names"] = ["Röda speciallinser", "RÖDA  SPECIALLINSER"]
    rows = [row]
    monkeypatch.setattr(registry, "declarations", lambda: rows)
    p = red_lentils(name="Röda speciallinser")
    key = (p.store_id, p.product_id)
    assert supplement_catalog_facts([p], {})[key].nutrition == row["nutrition"]
    assert not supplement_catalog_facts([red_lentils()], {})
    rows.append(deepcopy(row))
    assert key not in supplement_catalog_facts([p], {})  # duplicate remains ambiguous
    rows.pop()
    rows[0]["identity_names"] = ["En annan variant"]
    assert key not in supplement_catalog_facts([p], {})  # no stale name decision


def test_indexed_supplier_gtin_keeps_duplicate_declarations_ambiguous(monkeypatch):
    from copy import deepcopy

    from grocery_data.app.services import product_declarations as registry

    p = product("Kefir Naturell", 1000, "g", 30, brand="Skånemejerier", gtin="7310867511407")
    rows = [deepcopy(r) for r in declarations() if (r.get("gtin") or "").zfill(14) == p.gtin.zfill(14)]
    assert rows
    monkeypatch.setattr(registry, "declarations", lambda: rows)
    key = (p.store_id, p.product_id)
    assert key in supplement_catalog_facts([p], {})
    rows.extend(deepcopy(rows))
    assert key not in supplement_catalog_facts([p], {})


def test_zeta_480g_drained_quantity_does_not_certify_drained_nutrients():
    p = product("Vita Bönor Stora", 480, "g", 19.95, brand="Zeta", gtin="7350027796831")
    f = supplement_catalog_facts([p], {})[(p.store_id, p.product_id)]
    projected = project_usable_quantity(p, f, required_unit="g")
    assert projected.usable_quantity == 290
    assert projected.package_quantity == 480
    assert projected.price == p.price
    assert f.nutrition_preparation == "draining_unspecified"
    assert not f.allergens_checked
    assert f.field_sources["usable_quantity"][0]["source"].endswith("07350027796831")
    changed = p.model_copy(update={"store_id": "other"})
    assert project_usable_quantity(changed, f, required_unit="g") == changed


def test_imported_source_rows_are_unique_and_gtin_unknown_is_explicit():
    rows = [r for r in declarations() if r.get("parser") == "gogreen-linked-product-declaration-v1"]
    assert len(rows) == 1
    assert rows[0]["gtin"] is None
    assert rows[0]["source"]["url"] == "https://www.gogreen.se/produkter/roda-linser/"
    assert rows[0]["identity_source"]["url"] == "https://www.gogreen.se/produkter/"


@pytest.mark.parametrize("gtin,brand,package,drained", [
    ("7316150775242", "Fontana", 220, 110),
    ("7316150777093", "Fontana", 360, 180),
    ("7316150770346", "Fontana", 290, 130),
    ("7350002405543", "Zeta", 370, 170),
    ("8410159044077", "Figaro", 240, 110),
])
def test_official_pitted_olive_quantity_has_exact_package_and_separate_nutrient_basis(
    gtin, brand, package, drained,
):
    p = product("Oliver urkärnade", package, "g", 25, brand=brand, gtin=gtin)
    f = supplement_catalog_facts([p], {})[(p.store_id, p.product_id)]
    projected = project_usable_quantity(p, f, required_unit="g")
    if gtin == "7316150770346":
        assert projected.usable_quantity == drained  # Quantity and nutrition are separate.
        assert "supplier_nutrition_conflict" in f.conflicts
        assert {r['original_nutrition']['kcal'] for r in f.field_sources['supplier_nutrition_conflict']} == {271, 278}
    else:
        assert projected.usable_quantity == drained
    assert projected.package_quantity == package
    assert projected.price == p.price
    assert f.nutrition_preparation == "draining_unspecified"
    assert not f.allergens_checked
    proof = f.field_sources["usable_quantity"][0]
    assert proof["basis"] == "drained"
    assert proof["gtin"].zfill(14) == gtin.zfill(14)
    assert proof["source_package_quantity"] == package
    changed = p.model_copy(update={"package_quantity": package + 10})
    assert (changed.store_id, changed.product_id) not in supplement_catalog_facts([changed], {})
    assert project_usable_quantity(changed, f, required_unit="g") == changed
