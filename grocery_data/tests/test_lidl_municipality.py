"""Retained public evidence, with explicitly injected identity/scope failures."""
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from grocery_data.app.connectors.lidl.municipal_offers import (
    MunicipalLidlOfferConnector,
    review_document,
)
from grocery_data.app.connectors.lidl.municipality_inventory import (
    approved_lidl_stores,
    build_inventory,
)
from grocery_data.app.domain import GeographicArea, RawBatch, RawFetch
from grocery_data.app.services import lidl_municipal_job as job

ROOT = Path(__file__).parents[2] / "reports/lidl-municipality-20260923"


def inventory(code="1281"):
    return json.loads((ROOT / f"inventory-{code}/inventory.json").read_bytes())


def parse(mutate=None):
    inv = inventory()
    batch = RawBatch.model_validate_json((ROOT / "offer-probe-combined.json").read_bytes())
    if mutate:
        docs = []
        for document in batch.documents:
            payload = document.json_payload()
            for item in payload["items"]:
                if str(item.get("gridbox", {}).get("data", {}).get("productId")) == "11214016":
                    mutate(item["gridbox"]["data"])
            docs.append(document.model_copy(update={"payload": json.dumps(payload).encode()}))
        batch = batch.model_copy(update={"documents": tuple(docs)})
    adapter = MunicipalLidlOfferConnector(store=approved_lidl_stores(inv)["0163"], registry=inv["registry"],
        catalog=batch, publication=RawFetch.model_validate_json((ROOT / "current-publication.json").read_bytes()),
        pdf=(ROOT / "current-national.pdf").read_bytes())
    parsed = adapter.parse_catalog(batch, [f"replay:{n}" for n in range(len(batch.documents))], adapter.store)
    return parsed, adapter


@pytest.mark.parametrize(("code", "count"), [("1281", 2), ("1280", 8)])
def test_complete_official_inventory_same_geometry(code, count):
    inv = inventory(code)
    assert len(inv["stores"]) == 212
    assert len(approved_lidl_stores(inv)) == count
    assert all(r["geographic_evidence"]["status"] in {"inside", "outside", "unknown"} for r in inv["stores"])
    altered = copy.deepcopy(inv)
    altered["selected_store_ids"].append("unproven-neighbour")
    with pytest.raises(ValueError):
        approved_lidl_stores(altered)


def test_failed_official_detail_remains_unknown_and_visible():
    inv = inventory()
    registry = copy.deepcopy(inv["registry"])
    registry["details"][0] = {"url": registry["details"][0]["url"], "status": "failed", "reason": "injected_timeout"}
    rebuilt = build_inventory(GeographicArea.model_validate(inv["area"]), registry, inv["boundary"])
    row = next(r for r in rebuilt["stores"] if r["collection_reason"] == "injected_timeout")
    assert row["geographic_evidence"]["status"] == "unknown" and not row["collection_selected"]
    assert len(rebuilt["stores"]) == len(inv["stores"])


def test_bound_rows_no_ordinary_prices_and_original_observation():
    parsed, adapter = parse()
    assert len(parsed.products) == 26 and len(parsed.failures) == 354
    assert not adapter.row_acceptance["shared_blockers"]
    for p in parsed.products:
        assert p.regular_price is p.sale_price is p.member_price is None
        assert p.offers[0].source_payload["campaign_evidence"]["observed_current_at"] == p.fetched_at.isoformat().replace("+00:00", "Z")
        assert p.store_external_id == "0163"
    capped = next(p for p in parsed.products if p.external_product_id == "11214016")
    assert capped.offers[0].max_quantity == 2
    assert capped.offers[0].source_payload["price_contract_id"].startswith("lidl:household:")


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(fullTitle="Different variant with same price"),
    lambda r: r["keyfacts"].update(description=r["keyfacts"]["description"] + " Aktivera personlig kupong"),
    lambda r: r["keyfacts"].update(description=r["keyfacts"]["description"].replace("Max 2", "Max 3")),
    lambda r: r["brand"].update(name="Other brand"),
])
def test_uncertain_row_is_quarantined_while_independent_rows_continue(mutation):
    parsed, _ = parse(mutation)
    assert "11214016" not in {p.external_product_id for p in parsed.products}
    assert {"11137878", "11218552"}.issubset({p.external_product_id for p in parsed.products})
    assert len(parsed.products) == 25
    assert len(parsed.failures) == 355


def test_changed_document_or_regional_publication_not_nationalized():
    publication = RawFetch.model_validate_json((ROOT / "current-publication.json").read_bytes())
    pdf = (ROOT / "current-national.pdf").read_bytes()
    with pytest.raises(ValueError, match="review_required"):
        review_document(publication, pdf + b"changed")
    payload = publication.json_payload()
    payload["flyer"]["subcategory"] = "Reklamblad för din valda butik"
    with pytest.raises(ValueError, match="review_required"):
        review_document(publication.model_copy(update={"payload": json.dumps(payload).encode()}), pdf)


def test_shorter_source_days_preserved_and_intraday_end_quarantined():
    parsed, _ = parse(lambda r: r.update(storeEndDate=int(datetime(2026, 9, 23, 21, 59, 59, tzinfo=UTC).timestamp())))
    product = next(p for p in parsed.products if p.external_product_id == "11214016")
    assert product.offers[0].valid_to.isoformat() == "2026-09-23"
    parsed, _ = parse(lambda r: r.update(storeEndDate=int(datetime(2026, 9, 23, 18, tzinfo=UTC).timestamp())))
    assert "11214016" not in {p.external_product_id for p in parsed.products}


def test_optional_persistent_municipality_schedule_and_failure_retains_success(tmp_path):
    env = {"GROCERY_DATABASE_URL": "sqlite:///unused.sqlite", "LIDL_MUNICIPAL_ROOT": str(tmp_path),
           "LIDL_MUNICIPAL_ENABLED": "true", "LIDL_MUNICIPALITY_CODE": "1281"}
    root, config = job.configuration(env)
    job.write(root / "config.json", config)
    assert job.configuration({"LIDL_MUNICIPAL_ROOT": str(root)})[1] == config
    now = datetime(2026, 9, 23, 16, tzinfo=UTC)
    inv = inventory()
    outcomes = {i: {"status": "success", "observed_at": now.isoformat(),
        "windows": [{"valid_from": "2026-09-21", "valid_to": "2026-09-27"}]} for i in inv["selected_store_ids"]}
    selection = job.update_selection(inv, outcomes, now=now)
    selected = [r for r in selection["stores"] if r["selected"]]
    assert all(datetime.fromisoformat(r["next_fetch_at"]) == now + timedelta(hours=35) for r in selected)
    failed = job.update_selection(inv, {i: {"status": "failed"} for i in outcomes}, previous=selection, now=now)
    assert all(r["last_success"] == now.isoformat() and r["reason"] == "bounded_failure_retry"
               for r in failed["stores"] if r["selected"])
