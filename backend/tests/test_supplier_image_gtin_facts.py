"""A supplier declaration needs an exact retained product image identity."""

from app.services.complete_recipes import _requirements_compatible, _whole_food_identity
from app.services.official_product_facts import supplement_catalog_facts
from app.services.personal_source_facts import project_raw_facts

from backend.tests.test_personal_planning_v2 import product


def test_supplier_submitted_nutrition_binds_only_to_exact_image_ean():
    p = product("Nordiska Ärtor", 1000, "g", 34.92, identity="peas", store="willys",
                brand="Apetit")
    raw = {"code": "101698397_ST", "name": p.name, "manufacturer": p.brand,
           "labels": ["keyhole", "frozen"],
           "image": {"url": "https://assets.axfood.se/image/upload/f_auto,t_200/06430104920418_C1N1_s01"}}
    fact = project_raw_facts(raw, chain="willys", product_id=p.product_id,
                             snapshot_id=p.source_provenance.source_snapshot_id,
                             source_reference="hash-verified-retained-raw")
    selected = supplement_catalog_facts([p], {(p.store_id, p.product_id): fact})[(p.store_id, p.product_id)]
    assert selected.nutrition == {"kcal": 75, "fat_g": 0.8, "carbs_g": 9.5, "protein_g": 5.6}
    assert selected.field_sources["supplier_declaration"][0]["retailer_image_identity"]["gtin"] == "06430104920418"
    assert selected.product_classification == ("frozen",)
    assert _whole_food_identity("ärtor", "as_sold", p, selected, ("plain", "frozen"))
    assert _requirements_compatible("ärtor", ("plain", "frozen"), p, selected)
    assert not selected.allergens_checked

    for image in ("06430104920425_C1N1_s01", "nonsense_C1N1_s01"):
        changed = {**raw, "image": {"url": "https://assets.axfood.se/image/upload/f_auto,t_200/" + image}}
        incompatible = project_raw_facts(changed, chain="willys", product_id=p.product_id,
                                         snapshot_id=p.source_provenance.source_snapshot_id,
                                         source_reference="hash-verified-retained-raw")
        stopped = supplement_catalog_facts([p], {(p.store_id, p.product_id): incompatible})[(p.store_id, p.product_id)]
        assert not stopped.nutrition
