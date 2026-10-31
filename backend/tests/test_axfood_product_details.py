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


@pytest.mark.parametrize("protein,conflict", [(11, False), (12, True), (13, True)])
@pytest.mark.parametrize("accuracy", ["LT", "<"])
def test_detail_bound_vetoes_contradictory_old_point_and_preserves_evidence(tmp_path, protein, conflict, accuracy):
    from dataclasses import replace

    raw = detail()
    raw["nutrientHeaders"][0]["nutrientDetails"] = [
        {"nutrientTypeCode": "protein", "quantityContained": "12", "measurementUnitCode": "gram",
         "measurementPrecisionCode": accuracy}]
    store(tmp_path, "willys", raw)
    original = replace(catalogue_fact(), nutrition={"protein_g": protein}, nutrition_unit="g",
                       nutrition_basis="Officiell produktdeklaration per 100 g som såld")
    facts = {("s1", "p1"): original}
    merge_axfood_details([_Product("willys", raw["ean"])], facts, tmp_path)
    result = facts[("s1", "p1")]
    assert ("nutrition.protein_g" in result.conflicts) is conflict
    assert result.nutrition == original.nutrition
    assert result.field_sources["nutrition_limits"][0]["accuracy"] == accuracy
    assert result.field_sources["nutrition_limits"][0]["payload_sha256"]


def test_new_point_cannot_override_existing_strict_bound(tmp_path):
    raw = detail()
    original = project(detail(precision="LT"))
    store(tmp_path, "willys", raw)
    facts = {("s1", "p1"): original}
    merge_axfood_details([_Product("willys", raw["ean"])], facts, tmp_path)
    result = facts[("s1", "p1")]
    assert "nutrition.protein_g" in result.conflicts
    assert result.field_sources["nutrition_limits"] == original.field_sources["nutrition_limits"]


@pytest.mark.parametrize("precision", [[], {}])
def test_malformed_precision_is_a_visible_conflict_not_a_projection_crash(tmp_path, precision):
    raw = detail()
    raw["nutrientHeaders"][0]["nutrientDetails"][4]["measurementPrecisionCode"] = precision
    store(tmp_path, 'willys', raw)
    facts = {('s1', 'p1'): catalogue_fact()}
    merge_axfood_details([_Product('willys', raw['ean'])], facts, tmp_path)
    assert 'nutrition.protein_g' in facts[('s1', 'p1')].conflicts


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
        "code": raw["code"], "chain": chain,
        "url": f"https://www.{chain}.se/axfood/rest/p/{raw['code']}",
        "fetched_at": "2026-10-22T19:00:00+00:00", "http_status": 200,
        "payload_sha256": hashlib.sha256(payload).hexdigest()}))


def catalogue_fact():
    return ProductFacts(source="cat", source_product_id="p1", source_snapshot_id="snap",
                        retailer_product_id="101548687_ST", organic=False)


@pytest.mark.parametrize("has_document", [False, True])
def test_completed_source_projection_has_a_current_version_without_mutating_catalogue(
    tmp_path, monkeypatch, has_document
):
    from app.services import personal_source_facts as source

    from backend.tests.test_personal_planning_v2 import prepared, product
    from grocery_data.app.services.axfood_detail_archive import publish_release

    raw = detail()
    staging = tmp_path / "staging" / "projection"
    staging.mkdir(parents=True)
    store(staging, "willys", raw if has_document else detail(code="999_ST"))
    release = publish_release(tmp_path, "projection")
    monkeypatch.setenv("AXFOOD_PRODUCT_DETAIL_ROOT", str(release))
    pool = prepared(product("Fusilli", 500, "g", 20, store="willys", identity="p1", gtin=raw["ean"]))
    key = ("willys", "p1")
    catalogue = source.FactsCollection({key: catalogue_fact()})
    catalogue_version = catalogue.version
    monkeypatch.setattr(source, "_load_retained_catalog_facts", lambda *a, **kw: catalogue)

    result = source.load_retained_facts(pool)
    assert isinstance(result, source.FactsCollection)
    assert result.version == source.facts_version(result)
    assert result[key].nutrition == (project(raw).nutrition if has_document else {})
    assert catalogue[key] == catalogue_fact() and catalogue.version == catalogue_version

    if has_document:
        # A later read still checks actual bytes even with a cached manifest.
        (release / "willys" / (raw["code"] + ".json")).write_text("{}")
        rechecked = source.load_retained_facts(pool)
        assert rechecked[key].nutrition == {}
        assert rechecked.version == source.facts_version(rechecked) != result.version
        assert catalogue[key] == catalogue_fact() and catalogue.version == catalogue_version


def test_equal_lentil_declarations_do_not_conflict_on_projector_wording(tmp_path):
    # The frozen 2026-10-23 comparison found these equal values blocked solely
    # by the official/Axfood projector labels. This is an identity/unit fixture,
    # not a reproduction of the unrelated historical 361.81/340.64 menu case.
    raw = detail(code="100046442_ST", ean="7312787710182", kcal="349", kj="1460",
                 ingredients="Röda linser.")
    for row, value in zip(raw["nutrientHeaders"][0]["nutrientDetails"][2:], ("1.8", "51", "26"), strict=True):
        row["quantityContained"] = value
    store(tmp_path, "willys", raw)
    original = ProductFacts(source="official", source_product_id="p1", source_snapshot_id="snap",
        retailer_product_id=raw["code"], nutrition_unit="g",
        nutrition_basis="Officiell produktdeklaration per 100 g som såld",
        nutrition={"kcal": 349.0, "fat_g": 1.8, "carbs_g": 51.0, "protein_g": 26.0})
    facts = {("s1", "p1"): original}
    merge_axfood_details([_Product("willys", raw["ean"])], facts, tmp_path)
    assert facts[("s1", "p1")].conflicts == ()
    assert facts[("s1", "p1")].nutrition == original.nutrition
    assert facts[("s1", "p1")].nutrition_basis == original.nutrition_basis


@pytest.mark.parametrize("change, conflict", [
    ({"nutrition_basis": "Per portion med 100 g produkt"}, "nutrition_basis"),
    ({"nutrition_unit": "ml"}, "nutrition_basis"),
    ({"nutrition_preparation": "cooked_drained"}, "nutrition_basis"),
    ({"nutrition": {"protein_g": 13.0}}, "nutrition.protein_g"),
])
def test_basis_wording_normalization_keeps_real_conflicts(tmp_path, change, conflict):
    from dataclasses import replace

    raw = detail()
    store(tmp_path, "willys", raw)
    original = replace(catalogue_fact(), nutrition=project(raw).nutrition, nutrition_unit="g",
                       nutrition_basis="Officiell produktdeklaration per 100 g som såld")
    facts = {("s1", "p1"): replace(original, **change)}
    merge_axfood_details([_Product("willys")], facts, tmp_path)
    assert conflict in facts[("s1", "p1")].conflicts


@pytest.mark.parametrize("cache_bytes, expected_reads", [(32 * 1024 * 1024, 1), (1, 2)])
def test_projection_document_reuse_is_bounded_and_never_crosses_calls(
        tmp_path, monkeypatch, cache_bytes, expected_reads):
    from app.services import axfood_product_details as reader

    raw = detail()
    store(tmp_path, "willys", raw)
    products = [_Product("willys"), _Product("willys")]
    products[1].store_id = "s2"
    calls, original = [], reader.read_document

    def read(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)

    monkeypatch.setattr(reader, "read_document", read)
    monkeypatch.setattr(reader, "DETAIL_READ_MAX_BYTES", cache_bytes)
    facts = {(p.store_id, p.product_id): catalogue_fact() for p in products}
    assert reader.merge_axfood_details(products, facts, tmp_path)["own_document"] == 2
    assert len(calls) == expected_reads
    (tmp_path / "willys" / (raw["code"] + ".json")).write_text("{}")
    fresh = {(p.store_id, p.product_id): catalogue_fact() for p in products}
    stats = reader.merge_axfood_details(products, fresh, tmp_path)
    assert stats["own_document"] == 0 and stats["rejected_own_document"] == 2
    assert len(calls) == 2 * expected_reads


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
