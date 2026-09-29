import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from grocery_data.app.services.lidl_national_offer_evaluation import (
    qualify_national_offers,
    require_within_purchase_limits,
)


@pytest.fixture
def inputs():
    path = Path(__file__).parents[1] / "app/connectors/lidl/fixtures/national_flyer_20260915.json"
    data = json.loads(path.read_text(encoding="utf8"))
    for key in ("purchase_at", "evaluated_at"):
        data[key] = datetime.fromisoformat(data[key])
    return data


def test_saved_national_matches_keep_source_age_and_physical_destination(inputs):
    result = qualify_national_offers(**inputs)
    assert result["accepted_count"] == 3
    assert not result["promoted"]
    for row in result["products"]:
        source = next(p for p in inputs["live"]["products"] if p["id"] == row["id"])
        assert row["observed_at"] == source["observed_at"]
        assert row["physical_store"]["external_id"] == "0303"
        assert not row["stock_verified"]
        assert not row["ordinary_price_verified"]
        assert row["coverage"] == "offers_only"


def test_same_price_unreviewed_product_never_gets_national_scope(inputs):
    other = deepcopy(inputs["live"]["products"][0])
    other["id"] = "unreviewed"
    inputs["live"]["products"].append(other)
    result = qualify_national_offers(**inputs)
    assert result["accepted_count"] == 3
    assert result["excluded"] == [{"id": "unreviewed", "reason": "not_in_reviewed_flyer_set"}]


@pytest.mark.parametrize("field,value", [
    ("gtin", "7332489005324"), ("name", "Andra ekologiska ägg 15-pack"),
    ("package_quantity", "12"), ("sale_price", "0"), ("sale_price", "NaN"),
    ("quantity_confidence", "estimated"),
])
def test_identity_quantity_and_price_changes_quarantine_only_affected_row(inputs, field, value):
    inputs["live"]["products"][0][field] = value
    assert qualify_national_offers(**inputs)["accepted_count"] == 2


@pytest.mark.parametrize("field,value", [
    ("geographic_restrictions", ["Gäller ej Lund"]),
    ("member_offer_scope", "user_specific"), ("activation_required", True),
])
def test_local_exceptions_and_private_terms_fail_closed(inputs, field, value):
    inputs["live"]["products"][0]["source_fields"][field] = value
    assert qualify_national_offers(**inputs)["accepted_count"] == 2


def test_new_pack_image_requires_new_identity_review(inputs):
    inputs["raw_rows"][0]["raw"]["gridbox"]["data"]["image"] = "different.png"
    assert qualify_national_offers(**inputs)["accepted_count"] == 2


def test_product_level_purchase_limit_cannot_disappear_or_change(inputs):
    data = inputs["raw_rows"][0]["raw"]["gridbox"]["data"]
    data["keyfacts"]["description"] = "Stl: M. Max 2 förp./hushåll"
    result = qualify_national_offers(**inputs)
    assert result["accepted_count"] == 2
    assert "limits_disagree" in result["excluded"][0]["reason"]


@pytest.mark.parametrize("days", [-2, 6])
def test_future_or_expired_offer_is_decided_by_purchase_day(inputs, days):
    inputs["purchase_at"] += timedelta(days=days)
    assert qualify_national_offers(**inputs)["accepted_count"] == 0


def test_rebuild_does_not_rejuvenate_source(inputs):
    inputs["evaluated_at"] += timedelta(hours=48)
    assert qualify_national_offers(**inputs)["accepted_count"] == 0


@pytest.mark.parametrize("change", ["local", "partial", "duplicates", "wrong_store"])
def test_invalid_source_or_context_blocks_whole_candidate(inputs, change):
    if change == "local":
        inputs["flyer"]["subcategory"] = "Lokala reklamblad"
    elif change == "partial":
        inputs["live"]["completion"][0]["complete"] = False
    elif change == "duplicates":
        inputs["live"]["products"].append(deepcopy(inputs["live"]["products"][0]))
    else:
        inputs["store"]["city"] = "Malmö"
    with pytest.raises(ValueError):
        qualify_national_offers(**inputs)


def test_no_regular_price_fallback_after_three_packs(inputs):
    candidate = qualify_national_offers(**inputs)
    require_within_purchase_limits(candidate, {"11215364": 3, "11919135": 3})
    with pytest.raises(ValueError, match="no regular fallback"):
        require_within_purchase_limits(candidate, {"11215364": 4})


@pytest.mark.parametrize("count", [0, -1, True, 1.5, "2", None])
def test_purchase_counts_require_positive_whole_packages(inputs, count):
    candidate = qualify_national_offers(**inputs)
    with pytest.raises(ValueError, match="identity/count"):
        require_within_purchase_limits(candidate, {"11215364": count})


@pytest.mark.parametrize("field", ["ean", "fullTitle", "observed_at"])
def test_raw_identity_and_observation_must_match_normalized_row(inputs, field):
    raw = inputs["raw_rows"][0]
    if field == "observed_at":
        raw[field] = "2026-09-14T05:00:00Z"
    else:
        raw["raw"]["gridbox"]["meta"][field] = "different"
    assert qualify_national_offers(**inputs)["accepted_count"] == 2


def test_next_campaign_cannot_inherit_prior_manual_review(inputs):
    inputs["flyer"]["id"] = "next-week-new-campaign"
    result = qualify_national_offers(**inputs)
    assert result["accepted_count"] == 0
    assert all("flyer_page_identity_changed" in row["reason"] for row in result["excluded"])
