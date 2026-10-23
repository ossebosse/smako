import hashlib
import json

import pytest
from app.services.axfood_product_details import merge_axfood_details
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import project_raw_facts


def detail(code="101548687_ST", ean="7311043008346", precision="CA", kcal="351", kj="1488", unit="gram",
           ingredients="INGREDIENSER DURUMVETE. Kan innehålla spår av ÄGG."):
    def row(kind, value, measure):
        return {"nutrientTypeCode": kind, "quantityContained": value, "measurementUnitCode": measure,
                "measurementPrecisionCode": precision}
    return {"code": code, "ean": ean, "name": "Fusilli", "ingredients": ingredients,
            "nutrientHeaders": [{"preparationStateCode": None, "nutrientBasisQuantity": "100",
                                 "nutrientBasisQuantityMeasurementUnitCode": unit,
                                 "nutrientBasisQuantityTypeCode": "BY_MEASURE",
                                 "nutrientDetails": [row("energi", kj, "kilojoule"), row("energi", kcal, "kilokalori"),
                                                     row("fett", "1.4", "gram"), row("kolhydrat", "71", "gram"),
                                                     row("protein", "12", "gram")]}]}


def project(raw, chain="willys"):
    return project_raw_facts(raw, chain=chain, product_id="p", snapshot_id="s", source_reference="ref")


def test_detail_document_gives_ingredients_and_declared_nutrition():
    fact = project(detail())
    assert fact.ingredients == ("INGREDIENSER DURUMVETE. Kan innehålla spår av ÄGG.",)
    assert fact.nutrition == {"kcal": 351.0, "fat_g": 1.4, "carbs_g": 71.0, "protein_g": 12.0}
    assert fact.nutrition_unit == "g" and not fact.conflicts
    assert fact.retailer_product_id == "101548687_ST"


def test_threshold_values_are_limits_not_amounts():
    raw = detail()
    raw["nutrientHeaders"][0]["nutrientDetails"][4]["measurementPrecisionCode"] = "LT"
    fact = project(raw)
    assert "protein_g" not in fact.nutrition
    assert fact.field_sources["nutrition_limits"][0]["field"] == "protein_g"


@pytest.mark.parametrize("change, conflict", [
    ({"kj": "1488", "kcal": "500"}, "nutrition.kcal"),
    ({"unit": "portion"}, "nutrition_basis"),
])
def test_inconsistent_or_unusable_declarations_are_conflicts(change, conflict):
    fact = project(detail(**change))
    assert conflict in fact.conflicts


def test_catalogue_rows_without_detail_fields_are_unchanged():
    fact = project({"code": "1_ST", "name": "Fusilli", "labels": ["krav"]})
    assert fact.ingredients == () and fact.nutrition == {} and fact.organic is True


class _Prov:
    source_snapshot_id = "snap"


class _Product:
    def __init__(self, chain, gtin=None):
        self.chain, self.store_id, self.product_id, self.gtin = chain, "s1", "p1", gtin
        self.source_provenance = _Prov()


def store(root, chain, raw):
    payload = json.dumps(raw).encode()
    (root / chain).mkdir(parents=True, exist_ok=True)
    (root / chain / f"{raw['code']}.json").write_bytes(payload)
    (root / chain / f"{raw['code']}.meta.json").write_text(json.dumps({
        "chain": chain, "url": "u", "fetched_at": "2026-10-22T19:00:00+00:00", "http_status": 200,
        "payload_sha256": hashlib.sha256(payload).hexdigest()}))


def catalogue_fact():
    return ProductFacts(source="cat", source_product_id="p1", source_snapshot_id="snap",
                        retailer_product_id="101548687_ST", organic=False)


def test_merge_binds_by_exact_code_and_keeps_catalogue_evidence(tmp_path):
    store(tmp_path, "willys", detail())
    facts = {("s1", "p1"): catalogue_fact()}
    stats = merge_axfood_details([_Product("willys")], facts, tmp_path)
    merged = facts[("s1", "p1")]
    assert stats["own_document"] == 1 and merged.organic is False
    assert merged.nutrition["protein_g"] == 12.0 and merged.ingredients
    (evidence,) = merged.field_sources["nutrition.protein_g"]
    assert evidence["binding"] == "exact_retailer_article_code" and evidence["payload_sha256"]


def test_hemkop_may_use_the_shared_willys_article_but_not_a_different_gtin(tmp_path):
    store(tmp_path, "willys", detail())
    facts = {("s1", "p1"): catalogue_fact()}
    assert merge_axfood_details([_Product("hemkop")], facts, tmp_path)["shared_document"] == 1
    assert facts[("s1", "p1")].field_sources["ingredients"][0]["binding"] == "axfood_shared_article_code"
    facts = {("s1", "p1"): catalogue_fact()}
    assert merge_axfood_details([_Product("hemkop", gtin="7310000000000")], facts, tmp_path)["gtin_mismatch"] == 1
    assert not facts[("s1", "p1")].ingredients


def test_tampered_document_is_ignored(tmp_path):
    store(tmp_path, "willys", detail())
    (tmp_path / "willys" / "101548687_ST.json").write_text(json.dumps(detail(kcal="999")))
    facts = {("s1", "p1"): catalogue_fact()}
    assert merge_axfood_details([_Product("willys")], facts, tmp_path)["no_document"] == 1
    assert facts[("s1", "p1")].nutrition == {}


def test_the_per_hundred_header_is_used_beside_a_serving_header():
    raw = detail()
    serving = {**raw["nutrientHeaders"][0], "nutrientBasisQuantity": "250"}
    raw["nutrientHeaders"] = [serving, raw["nutrientHeaders"][0]]
    fact = project(raw)
    assert fact.nutrition["protein_g"] == 12.0 and "nutrition_basis" not in fact.conflicts


def test_two_per_hundred_headers_are_ambiguous():
    raw = detail()
    raw["nutrientHeaders"] = raw["nutrientHeaders"] * 2
    assert "nutrition_basis" in project(raw).conflicts


def test_energy_rounding_within_the_coop_integrity_screen_is_accepted():
    # 1488 kJ against 351 kcal (1468.6 kJ): within max(8 kJ, 8 %).
    assert "nutrition.kcal" not in project(detail(kj="1488", kcal="351")).conflicts
