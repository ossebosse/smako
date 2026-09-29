import json
from copy import deepcopy
from pathlib import Path

import pytest

from grocery_data.app.services.ica_browser_price_evaluation import parse_public_browser_prices


def fixture():
    return json.loads((Path(__file__).parents[1] / "app/connectors/ica/fixtures/"
                       "browser_public_prices_20260915.json").read_text(encoding="utf8"))


def test_saved_public_prices_keep_online_scope_and_source_time():
    result = parse_public_browser_prices(fixture())
    assert result["accepted_count"] == 50
    assert result["rejected_count"] == 0
    assert not result["catalog_complete"]
    assert result["search_total_ids"] == 232
    first = result["products"][0]
    assert first["regular_price"] == "15.90"
    assert first["package_quantity"] == "1500.0"
    assert first["package_unit"] == "ml"
    assert first["gtin"] is None
    assert first["fetched_at"].startswith("2026-09-15T05:50:37")
    assert first["source_fields"]["price_semantics"] == "online_price"
    assert not first["source_fields"]["shared_candidate_approved"]


@pytest.mark.parametrize("amount", [None, "NaN", "0", "-1", True, "2 for 15"])
def test_unknown_or_invalid_purchase_price_never_becomes_zero(amount):
    doc = fixture()
    doc["products"][0]["price"]["current"]["amount"] = amount
    assert parse_public_browser_prices(doc)["rejected_count"] == 1


@pytest.mark.parametrize("field,value", [
    ("featuredProductCampaign", {}), ("promotions", []),
    ("memberPrice", "10"), ("newPriceSchema", {}), ("available", False),
    ("isInCurrentCatalog", None), ("size", {"value": "ca 1 kg"}),
])
def test_unreviewed_conditions_or_package_fail_closed(field, value):
    doc = fixture()
    doc["products"][0][field] = value
    assert parse_public_browser_prices(doc)["rejected_count"] == 1


def test_rebuild_does_not_rejuvenate_source_observation():
    doc = fixture()
    before = parse_public_browser_prices(doc)
    doc["capturedAt"] = "2026-09-20T10:00:00Z"
    after = parse_public_browser_prices(doc)
    assert before["observed_at"] == after["observed_at"]
    assert before["products"][0]["fetched_at"] == after["products"][0]["fetched_at"]


@pytest.mark.parametrize("mutation", ["store", "channel", "duplicate", "future"])
def test_scope_and_identity_block_whole_projection(mutation):
    doc = fixture()
    if mutation == "store":
        doc["storeId"] = "1004409"
    elif mutation == "channel":
        doc["channel"] = "physical_store"
    elif mutation == "duplicate":
        doc["products"].append(deepcopy(doc["products"][0]))
    else:
        doc["capturedAt"] = "2026-09-14T00:00:00Z"
    with pytest.raises(ValueError):
        parse_public_browser_prices(doc)
