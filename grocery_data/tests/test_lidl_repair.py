from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.connectors.lidl import LidlParser
from grocery_data.app.connectors.lidl.models import reviewed_lidl_schema_diff
from grocery_data.app.domain import Chain, PromotionType, RawBatch, RawFetch
from grocery_data.app.monitoring.schema_fingerprint import JsonType, SchemaDiff, SchemaTypeChange
from grocery_data.app.normalization import ProductNormalizer

FIXTURE = Path(__file__).parents[1] / "app/connectors/lidl/fixtures/repair_20260914.json"
OBSERVED = datetime(2026, 9, 14, 1, 47, 2, tzinfo=UTC)


def _row(product_id: int = 11216407) -> dict:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return next(
        item for item in fixture["items"] if item["gridbox"]["data"]["productId"] == product_id
    )


def _parse(row: dict, *, observed: datetime = OBSERVED):
    parser = LidlParser()
    payload = {
        "type": "search",
        "resultType": "search",
        "offset": 0,
        "numFound": 1,
        "fetchsize": 1,
        "items": [row],
    }
    batch = RawBatch(
        chain=Chain.LIDL,
        documents=(
            RawFetch(
                chain=Chain.LIDL,
                kind="offer_page",
                method="GET",
                url="https://www.lidl.se/q/api/search",
                query={"offset": "0"},
                fetched_at=observed,
                http_status=200,
                payload=json.dumps(payload).encode(),
                connector_version="lidl-v1",
            ),
        ),
    )
    return parser.parse_catalog(
        batch,
        ["raw:golden"],
        parser._regional_offer_context(reference="raw:context", requested_city="Sverige"),
    )


def test_saved_highlight_only_baguette_multibuy_is_never_single_member_price():
    result = _parse(_row(11208821))
    assert not result.failures
    row = result.products[0]
    assert row.sale_price is row.regular_price is row.member_price is None
    assert row.offers[0].type is PromotionType.MULTIBUY
    assert row.offers[0].quantity == 4
    assert row.offers[0].price == 22
    assert row.package_quantity == 165
    assert row.package_unit == "g"
    assert row.comparison_price == Decimal("33.33")


def test_deleted_price_is_only_reference_and_future_store_window_wins():
    row = _parse(_row(11006571)).products[0]
    assert row.offers[0].quantity == 12
    assert row.offers[0].price == 159
    assert row.sale_price is row.regular_price is row.member_price is None
    assert row.source_fields["deleted_price"] == "15.99"
    assert row.offers[0].valid_from == date(2026, 9, 21)
    assert row.offers[0].valid_to == date(2026, 9, 27)
    assert not row.source_fields["price_valid_at_observation"]


def test_expired_price_never_falls_back_to_old_price_after_rebuild():
    result = _parse(_row(), observed=datetime(2026, 9, 21, 1, tzinfo=UTC))
    row = result.products[0]
    assert row.offers[0].price == Decimal("12.9")
    assert row.sale_price is row.regular_price is None
    assert not row.source_fields["price_valid_at_observation"]
    canonical = ProductNormalizer().normalize(row, parser_version=LidlParser.parser_version)
    assert canonical.observed_at == datetime(2026, 9, 21, 1, tzinfo=UTC)
    assert canonical.sale_price is None


def test_replay_preserves_original_observation_not_build_clock():
    row = _parse(_row()).products[0]
    first = ProductNormalizer().normalize(row, parser_version=LidlParser.parser_version)
    second = ProductNormalizer().normalize(row, parser_version=LidlParser.parser_version)
    assert first.observed_at == second.observed_at == OBSERVED


@pytest.mark.parametrize("value", [None, 0, -1, True, "NaN", "Infinity", "free", {"amount": 12.9}])
def test_missing_ambiguous_nonfinite_price_is_quarantined(value):
    item = _row()
    item["gridbox"]["data"]["regionsPrices"]["1"]["currentPrice"]["price"] = value
    result = _parse(item)
    assert result.products == []
    assert len(result.failures) == 1
    assert "price" in result.failures[0].error_message


@pytest.mark.parametrize(
    "patch",
    [
        {"packaging": {"text": {"value": "1 l"}}},
        {"variantsHaveDifferentPrices": True},
        {"specialTaxes": [{"type": "deposit", "value": 2}]},
        {"specialTaxes": "2 kr"},
        {"currencyCode": "EUR"},
        {"newPriceCondition": "subscription"},
        {"startDate": "not-a-date"},
        {"endDate": "2026-09-20T23:59:59"},
        {"discount": {"showFrom": True}},
    ],
)
def test_schema_conditions_and_deposit_fail_closed(patch):
    item = _row()
    item["gridbox"]["data"]["regionsPrices"]["1"]["currentPrice"].update(patch)
    assert _parse(item).products == []
    assert len(_parse(item).failures) == 1


def test_contradictory_multibuy_labels_are_rejected():
    item = _row(11208821)
    item["gridbox"]["data"]["regionsPrices"]["1"]["currentLidlPlusPrice"]["price"]["discount"][
        "discountText"
    ] = "3 för:"
    assert _parse(item).products == []


def test_saved_coupon_and_personal_or_activated_text_never_become_shared_prices():
    for text in ("Kupong -20%", "Din personliga rabatt", "Aktivera i appen"):
        item = _row(11220148)
        member = item["gridbox"]["data"]["regionsPrices"]["1"]["currentLidlPlusPrice"]
        member["highlightText"] = text
        member["price"]["discount"]["discountText"] = text
        row = _parse(item).products[0]
        assert row.sale_price is row.member_price is row.regular_price is None
        assert not row.offers[0].source_payload["shared_price_universe_eligible"]


def test_fixed_multipack_quantity_keeps_total_contents_and_mixed_size_unknown():
    fixed = _parse(_row(11039253)).products[0]
    assert fixed.package_quantity == 200
    assert fixed.package_unit == "g"
    assert fixed.source_fields["package_count"] == 2
    mixed = _parse(_row(11219307)).products[0]
    assert mixed.package_quantity is mixed.package_unit is None


def test_purchase_limit_and_geographic_exceptions_remain_visible():
    item = _row(11123848)
    item["gridbox"]["data"]["disclaimers"].append(
        {"type": "TEXT", "value": "Max 4 förpackningar per hushåll"}
    )
    row = _parse(item).products[0]
    assert row.offers[0].max_quantity == 4
    assert "Max 4" in row.offers[0].description
    assert "Danderyd" in row.source_fields["conditions_text"]
    assert row.source_fields["store_price_verified"] is False


def test_changed_default_region_cannot_relabel_prices():
    item = _row()
    item["gridbox"]["data"]["regionsV2"]["1"]["regionPriceId"] = "2"
    result = _parse(item)
    assert not result.products
    assert "region" in result.failures[0].error_message


def test_unknown_campaign_window_never_becomes_shared_time_unlimited_price():
    item = _row()
    data = item["gridbox"]["data"]
    data.pop("storeStartDate", None)
    data.pop("storeEndDate", None)
    price = data["regionsPrices"]["1"]["currentPrice"]
    for field in ("startDate", "endDate", "endDateExclusive"):
        price.pop(field, None)
    row = _parse(item).products[0]
    assert row.sale_price is row.member_price is None
    assert not row.source_fields["shared_price_universe_eligible"]
    assert not row.offers[0].source_payload["shared_price_universe_eligible"]


def test_date_boundaries_follow_stockholm_midnight_inclusive_end():
    item = _row()
    last_second = _parse(
        deepcopy(item), observed=datetime(2026, 9, 20, 21, 59, 59, tzinfo=UTC)
    ).products[0]
    midnight = _parse(item, observed=datetime(2026, 9, 20, 22, tzinfo=UTC)).products[0]
    assert last_second.sale_price == Decimal("12.9")
    assert midnight.sale_price is None
    assert last_second.offers[0].valid_to == date(2026, 9, 20)
    winter = _row()
    data = winter["gridbox"]["data"]
    data["storeStartDate"] = int(datetime(2026, 10, 25, 23, tzinfo=UTC).timestamp())
    data["storeEndDate"] = int(datetime(2026, 11, 1, 22, 59, 59, tzinfo=UTC).timestamp())
    price = data["regionsPrices"]["1"]["currentPrice"]
    price.update(
        startDate="2026-10-20T10:00:00Z",
        endDate="2026-11-01T22:59:59Z",
        endDateExclusive="2026-11-01T23:00:00Z",
    )
    row = _parse(winter, observed=datetime(2026, 10, 26, 0, tzinfo=UTC)).products[0]
    assert row.offers[0].valid_from == date(2026, 10, 26)
    assert row.offers[0].valid_to == date(2026, 11, 1)


def test_schema_review_is_directional_and_preserves_unknown_or_type_changes():
    optional = "offer_context_probe:$[].items[].gridbox.data.storeEndDate"
    required = 'public-default-region:offer_page:$[].items[].gridbox.data.regionsPrices["1"].currentPrice.price'
    type_change = SchemaTypeChange(
        path=optional, old_types=(JsonType.NUMBER,), new_types=(JsonType.STRING,)
    )
    reviewed = reviewed_lidl_schema_diff(
        SchemaDiff(
            added=(optional, "unknownField"),
            removed=(optional, required),
            type_changed=(type_change,),
        )
    )
    assert reviewed.added == ("unknownField",)
    assert reviewed.removed == (optional, required)
    assert reviewed.type_changed == (type_change,)


@pytest.mark.parametrize("limit", ["Max 2 kg per hushåll", "Max 2 köp", "Max två förpackningar"])
def test_weight_or_unknown_purchase_limit_is_not_a_package_limit(limit):
    item = _row()
    item["gridbox"]["data"]["disclaimers"].append({"type": "TEXT", "value": limit})
    result = _parse(item)
    assert not result.products
    assert len(result.failures) == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"basePrice": {"text": "12.90-19.90 kr/kg"}},
        {"discount": {"customerSpecific": True}},
        {"discount": {"discountText": "Köp 3 betala för 2"}},
        {"discount": {"percentageDiscount": float("nan")}},
        {"packaging": {"text": "2 x 0 g"}},
    ],
)
def test_reviewed_cross_connector_repros_fail_closed_per_row(patch):
    item = _row()
    item["gridbox"]["data"]["regionsPrices"]["1"]["currentPrice"].update(patch)
    result = _parse(item)
    assert result.products == []
    assert len(result.failures) == 1


def test_approximate_weight_in_base_price_is_not_approximate_price():
    item = _row()
    price = item["gridbox"]["data"]["regionsPrices"]["1"]["currentPrice"]
    price.pop("packaging")
    price["basePrice"] = {"text": "/kg (Ca 650 g)"}
    result = _parse(item)
    assert not result.failures
    row = result.products[0]
    assert row.sale_price == Decimal("12.9")
    assert row.sale_unit == "kg"
    assert row.package_quantity is None
    assert row.average_weight_kg == Decimal("0.65")
    canonical = ProductNormalizer().normalize(row, parser_version=LidlParser.parser_version)
    assert canonical.sale_model.value == "variable_weight_package"
    assert canonical.quantity_confidence.value == "estimated"


def test_saved_additional_region_does_not_relabel_or_override_selected_price():
    fixture = json.loads(FIXTURE.with_name("region2_20260914.json").read_text(encoding="utf-8"))
    item = fixture["items"][0]
    item["gridbox"]["data"]["regionsPrices"]["2"]["currentPrice"]["price"] = 199
    product = _parse(item, observed=datetime(2026, 9, 24, 10, tzinfo=UTC)).products[0]
    assert product.sale_price == 179
    assert product.offers[0].price == 179
    assert product.source_fields["price_region_id"] == "1"
    item["gridbox"]["data"]["regionsPrices"].pop("1")
    assert not _parse(item).products


def test_additional_region_unknown_price_condition_still_quarantined():
    fixture = json.loads(FIXTURE.with_name("region2_20260914.json").read_text(encoding="utf-8"))
    item = fixture["items"][0]
    item["gridbox"]["data"]["regionsPrices"]["2"]["currentPrice"]["customerSpecific"] = True
    assert not _parse(item).products


def test_additional_region_schema_review_is_exact_addition_only():
    path = 'public-default-region:offer_page:$[].items[].gridbox.data.regionsPrices["2"].currentPrice.price'
    unknown = path + "Condition"
    difference = SchemaDiff(added=(path, unknown), removed=(path,))
    assert reviewed_lidl_schema_diff(difference) == SchemaDiff(added=(unknown,), removed=(path,))
