from decimal import Decimal

import pytest

from grocery_data.app.domain.enums import ConnectorStatus
from grocery_data.app.domain.health import RunMetrics
from grocery_data.app.monitoring.anomaly_detection import (
    AnomalyCode,
    AnomalyThresholds,
    PriceSanityClassification,
    PriceSanityIssueCode,
    assess_run_health,
    check_price_sanity,
)
from grocery_data.app.monitoring.schema_fingerprint import diff_json_schemas


def _metrics(
    *,
    fetched: int,
    parsed: int | None = None,
    quarantined: int = 0,
    with_price: int | None = None,
) -> RunMetrics:
    parsed = fetched if parsed is None else parsed
    with_price = parsed if with_price is None else with_price
    return RunMetrics(
        products_fetched=fetched,
        products_parsed=parsed,
        products_quarantined=quarantined,
        products_with_price=with_price,
    )


@pytest.mark.parametrize(
    ("current_count", "expected"),
    [(690, ConnectorStatus.DEGRADED), (290, ConnectorStatus.BROKEN)],
)
def test_product_count_drop_thresholds(current_count: int, expected: ConnectorStatus) -> None:
    result = assess_run_health(
        _metrics(fetched=current_count),
        baseline=_metrics(fetched=1000),
    )

    assert result.status == expected
    assert any(item.code == AnomalyCode.PRODUCT_COUNT_DROP for item in result.anomalies)


@pytest.mark.parametrize(
    ("parsed", "quarantined", "expected"),
    [(94, 6, ConnectorStatus.DEGRADED), (69, 31, ConnectorStatus.BROKEN)],
)
def test_parse_success_thresholds(
    parsed: int,
    quarantined: int,
    expected: ConnectorStatus,
) -> None:
    result = assess_run_health(_metrics(fetched=100, parsed=parsed, quarantined=quarantined))

    assert result.status == expected
    assert any(item.code == AnomalyCode.PARSE_SUCCESS_RATE_LOW for item in result.anomalies)


def test_more_than_twenty_percent_missing_prices_degrades_health() -> None:
    result = assess_run_health(_metrics(fetched=100, with_price=79))

    assert result.status == ConnectorStatus.DEGRADED
    assert any(item.code == AnomalyCode.MISSING_PRICE_RATE_HIGH for item in result.anomalies)


def test_thresholds_are_configurable() -> None:
    thresholds = AnomalyThresholds(
        degraded_product_drop_fraction=0.10,
        broken_product_drop_fraction=0.20,
    )
    result = assess_run_health(
        _metrics(fetched=850),
        baseline=_metrics(fetched=1000),
        thresholds=thresholds,
    )

    assert result.status == ConnectorStatus.DEGRADED


def test_schema_change_is_visible_in_health() -> None:
    schema_diff = diff_json_schemas({"price": 20}, {"salesPrice": {"value": 20}})
    result = assess_run_health(_metrics(fetched=10), schema_diff=schema_diff)

    assert result.status == ConnectorStatus.DEGRADED
    anomaly = next(item for item in result.anomalies if item.code == AnomalyCode.SCHEMA_CHANGED)
    assert "added" in anomaly.message
    assert "removed" in anomaly.message


@pytest.mark.parametrize("value", [Decimal(-1), Decimal(0), "NaN", True])
def test_impossible_prices_are_quarantined(value: object) -> None:
    result = check_price_sanity(value)  # type: ignore[arg-type]

    assert result.classification == PriceSanityClassification.QUARANTINE


@pytest.mark.parametrize(
    ("unit_price", "issue"),
    [
        (Decimal("0.01"), PriceSanityIssueCode.IMPLAUSIBLY_LOW_UNIT_PRICE),
        (Decimal(10000), PriceSanityIssueCode.IMPLAUSIBLY_HIGH_UNIT_PRICE),
    ],
)
def test_extreme_unit_prices_are_warnings(
    unit_price: Decimal,
    issue: PriceSanityIssueCode,
) -> None:
    result = check_price_sanity(Decimal(20), unit_price=unit_price)

    assert result.classification == PriceSanityClassification.WARNING
    assert issue in {item.code for item in result.issues}


def test_normal_price_is_accepted_and_missing_price_warns() -> None:
    assert check_price_sanity(Decimal("39.90"), unit_price=Decimal("79.80")).classification == (
        PriceSanityClassification.ACCEPT
    )
    missing = check_price_sanity(None)
    assert missing.classification == PriceSanityClassification.WARNING
    assert missing.issues[0].code == PriceSanityIssueCode.MISSING_PRICE
