"""Connector-run anomaly and price-sanity classification."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grocery_data.app.domain.enums import ConnectorStatus
from grocery_data.app.domain.health import RunMetrics
from grocery_data.app.monitoring.schema_fingerprint import SchemaDiff


class AnomalySeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


class AnomalyCode(StrEnum):
    PRODUCT_COUNT_DROP = "product_count_drop"
    PARSE_SUCCESS_RATE_LOW = "parse_success_rate_low"
    MISSING_PRICE_RATE_HIGH = "missing_price_rate_high"
    SCHEMA_CHANGED = "schema_changed"


class DetectedAnomaly(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: AnomalyCode
    severity: AnomalySeverity
    message: str
    observed_value: float | int | None = None
    threshold: float | int | None = None


class AnomalyThresholds(BaseModel):
    """Thresholds are fractions, not percentages."""

    model_config = ConfigDict(frozen=True)

    degraded_product_drop_fraction: float = Field(default=0.30, ge=0, le=1)
    broken_product_drop_fraction: float = Field(default=0.70, ge=0, le=1)
    degraded_parse_success_rate: float = Field(default=0.95, ge=0, le=1)
    broken_parse_success_rate: float = Field(default=0.70, ge=0, le=1)
    degraded_missing_price_fraction: float = Field(default=0.20, ge=0, le=1)
    broken_missing_price_fraction: float | None = Field(default=None, ge=0, le=1)
    schema_change_status: ConnectorStatus = ConnectorStatus.DEGRADED

    @model_validator(mode="after")
    def validate_ordering(self) -> AnomalyThresholds:
        if self.broken_product_drop_fraction < self.degraded_product_drop_fraction:
            raise ValueError("broken product-drop threshold must be at least degraded threshold")
        if self.broken_parse_success_rate > self.degraded_parse_success_rate:
            raise ValueError("broken parse-rate threshold must not exceed degraded threshold")
        if (
            self.broken_missing_price_fraction is not None
            and self.broken_missing_price_fraction < self.degraded_missing_price_fraction
        ):
            raise ValueError("broken missing-price threshold must be at least degraded threshold")
        if self.schema_change_status not in {
            ConnectorStatus.HEALTHY,
            ConnectorStatus.DEGRADED,
            ConnectorStatus.BROKEN,
        }:
            raise ValueError("schema change status must be healthy, degraded, or broken")
        return self


class HealthAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: ConnectorStatus
    anomalies: tuple[DetectedAnomaly, ...] = ()

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(anomaly.message for anomaly in self.anomalies)


_STATUS_RANK = {
    ConnectorStatus.HEALTHY: 0,
    ConnectorStatus.UNKNOWN: 0,
    ConnectorStatus.STALE: 1,
    ConnectorStatus.DEGRADED: 2,
    ConnectorStatus.BROKEN: 3,
}


def _max_status(current: ConnectorStatus, candidate: ConnectorStatus) -> ConnectorStatus:
    return candidate if _STATUS_RANK[candidate] > _STATUS_RANK[current] else current


def _product_count(metrics: RunMetrics) -> int:
    """Prefer source count; support parser-only fixtures and historical rows."""

    if metrics.products_fetched:
        return metrics.products_fetched
    return metrics.products_parsed + metrics.products_quarantined


def assess_run_health(
    current: RunMetrics,
    *,
    baseline: RunMetrics | None = None,
    schema_diff: SchemaDiff | None = None,
    thresholds: AnomalyThresholds | None = None,
) -> HealthAssessment:
    """Evaluate a run against its last known good baseline."""

    policy = thresholds or AnomalyThresholds()
    status = ConnectorStatus.HEALTHY
    anomalies: list[DetectedAnomaly] = []

    if baseline is not None:
        previous_count = _product_count(baseline)
        current_count = _product_count(current)
        if previous_count > 0:
            drop = max(0.0, (previous_count - current_count) / previous_count)
            if drop > policy.broken_product_drop_fraction:
                status = _max_status(status, ConnectorStatus.BROKEN)
                anomalies.append(
                    DetectedAnomaly(
                        code=AnomalyCode.PRODUCT_COUNT_DROP,
                        severity=AnomalySeverity.CRITICAL,
                        message=f"product count dropped by {drop:.1%}",
                        observed_value=drop,
                        threshold=policy.broken_product_drop_fraction,
                    )
                )
            elif drop > policy.degraded_product_drop_fraction:
                status = _max_status(status, ConnectorStatus.DEGRADED)
                anomalies.append(
                    DetectedAnomaly(
                        code=AnomalyCode.PRODUCT_COUNT_DROP,
                        severity=AnomalySeverity.WARNING,
                        message=f"product count dropped by {drop:.1%}",
                        observed_value=drop,
                        threshold=policy.degraded_product_drop_fraction,
                    )
                )

    parsed_total = current.products_parsed + current.products_quarantined
    if parsed_total:
        parse_rate = current.parse_success_rate
        if parse_rate < policy.broken_parse_success_rate:
            status = _max_status(status, ConnectorStatus.BROKEN)
            anomalies.append(
                DetectedAnomaly(
                    code=AnomalyCode.PARSE_SUCCESS_RATE_LOW,
                    severity=AnomalySeverity.CRITICAL,
                    message=f"parse success rate is {parse_rate:.1%}",
                    observed_value=parse_rate,
                    threshold=policy.broken_parse_success_rate,
                )
            )
        elif parse_rate < policy.degraded_parse_success_rate:
            status = _max_status(status, ConnectorStatus.DEGRADED)
            anomalies.append(
                DetectedAnomaly(
                    code=AnomalyCode.PARSE_SUCCESS_RATE_LOW,
                    severity=AnomalySeverity.WARNING,
                    message=f"parse success rate is {parse_rate:.1%}",
                    observed_value=parse_rate,
                    threshold=policy.degraded_parse_success_rate,
                )
            )

    if current.products_parsed:
        missing_price_rate = max(0.0, 1.0 - current.price_coverage)
        if (
            policy.broken_missing_price_fraction is not None
            and missing_price_rate > policy.broken_missing_price_fraction
        ):
            status = _max_status(status, ConnectorStatus.BROKEN)
            anomalies.append(
                DetectedAnomaly(
                    code=AnomalyCode.MISSING_PRICE_RATE_HIGH,
                    severity=AnomalySeverity.CRITICAL,
                    message=f"missing price rate is {missing_price_rate:.1%}",
                    observed_value=missing_price_rate,
                    threshold=policy.broken_missing_price_fraction,
                )
            )
        elif missing_price_rate > policy.degraded_missing_price_fraction:
            status = _max_status(status, ConnectorStatus.DEGRADED)
            anomalies.append(
                DetectedAnomaly(
                    code=AnomalyCode.MISSING_PRICE_RATE_HIGH,
                    severity=AnomalySeverity.WARNING,
                    message=f"missing price rate is {missing_price_rate:.1%}",
                    observed_value=missing_price_rate,
                    threshold=policy.degraded_missing_price_fraction,
                )
            )

    if schema_diff is not None and schema_diff.has_changes:
        schema_status = policy.schema_change_status
        status = _max_status(status, schema_status)
        severity = (
            AnomalySeverity.CRITICAL
            if schema_status == ConnectorStatus.BROKEN
            else AnomalySeverity.WARNING
        )
        anomalies.append(
            DetectedAnomaly(
                code=AnomalyCode.SCHEMA_CHANGED,
                severity=severity,
                message=(
                    "schema changed: "
                    f"{len(schema_diff.added)} added, "
                    f"{len(schema_diff.removed)} removed, "
                    f"{len(schema_diff.type_changed)} type changed"
                ),
            )
        )

    return HealthAssessment(status=status, anomalies=tuple(anomalies))


class PriceSanityClassification(StrEnum):
    ACCEPT = "accept"
    WARNING = "warning"
    QUARANTINE = "quarantine"


class PriceSanityIssueCode(StrEnum):
    MISSING_PRICE = "missing_price"
    INVALID_NUMBER = "invalid_number"
    NEGATIVE_PRICE = "negative_price"
    ZERO_PRICE = "zero_price"
    IMPLAUSIBLY_LOW_UNIT_PRICE = "implausibly_low_unit_price"
    IMPLAUSIBLY_HIGH_UNIT_PRICE = "implausibly_high_unit_price"
    IMPLAUSIBLY_HIGH_SALE_PRICE = "implausibly_high_sale_price"


class PriceSanityIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: PriceSanityIssueCode
    message: str


class PriceSanityResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    classification: PriceSanityClassification
    issues: tuple[PriceSanityIssue, ...] = ()


class PriceSanityPolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    min_reasonable_unit_price: Decimal = Field(default=Decimal("0.05"), gt=0)
    max_reasonable_unit_price: Decimal = Field(default=Decimal(5000), gt=0)
    max_reasonable_sale_price: Decimal = Field(default=Decimal(100000), gt=0)

    @model_validator(mode="after")
    def validate_bounds(self) -> PriceSanityPolicy:
        if self.max_reasonable_unit_price <= self.min_reasonable_unit_price:
            raise ValueError("maximum unit price must exceed minimum unit price")
        return self


def _decimal(value: Decimal | float | str | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TypeError("boolean is not a price")
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("price is not a finite decimal") from exc
    if not result.is_finite():
        raise ValueError("price is not a finite decimal")
    return result


def check_price_sanity(
    sale_price: Decimal | float | str | None,
    *,
    unit_price: Decimal | float | str | None = None,
    allow_free: bool = False,
    policy: PriceSanityPolicy | None = None,
) -> PriceSanityResult:
    """Classify impossible prices for quarantine and extremes for review."""

    bounds = policy or PriceSanityPolicy()
    issues: list[PriceSanityIssue] = []
    quarantine = False

    try:
        parsed_sale = _decimal(sale_price)
        parsed_unit = _decimal(unit_price)
    except (TypeError, ValueError):
        return PriceSanityResult(
            classification=PriceSanityClassification.QUARANTINE,
            issues=(
                PriceSanityIssue(
                    code=PriceSanityIssueCode.INVALID_NUMBER,
                    message="price is not a finite decimal",
                ),
            ),
        )

    if parsed_sale is None and parsed_unit is None:
        issues.append(
            PriceSanityIssue(
                code=PriceSanityIssueCode.MISSING_PRICE,
                message="record has no sale or unit price",
            )
        )

    for label, value in (("sale", parsed_sale), ("unit", parsed_unit)):
        if value is None:
            continue
        if value < 0:
            quarantine = True
            issues.append(
                PriceSanityIssue(
                    code=PriceSanityIssueCode.NEGATIVE_PRICE,
                    message=f"{label} price is negative",
                )
            )
        elif value == 0 and not allow_free:
            quarantine = True
            issues.append(
                PriceSanityIssue(
                    code=PriceSanityIssueCode.ZERO_PRICE,
                    message=f"{label} price is zero without a free-item marker",
                )
            )

    if parsed_unit is not None and parsed_unit > 0:
        if parsed_unit < bounds.min_reasonable_unit_price:
            issues.append(
                PriceSanityIssue(
                    code=PriceSanityIssueCode.IMPLAUSIBLY_LOW_UNIT_PRICE,
                    message="unit price is implausibly low",
                )
            )
        elif parsed_unit > bounds.max_reasonable_unit_price:
            issues.append(
                PriceSanityIssue(
                    code=PriceSanityIssueCode.IMPLAUSIBLY_HIGH_UNIT_PRICE,
                    message="unit price is implausibly high",
                )
            )

    if parsed_sale is not None and parsed_sale > bounds.max_reasonable_sale_price:
        issues.append(
            PriceSanityIssue(
                code=PriceSanityIssueCode.IMPLAUSIBLY_HIGH_SALE_PRICE,
                message="sale price is implausibly high",
            )
        )

    if quarantine:
        classification = PriceSanityClassification.QUARANTINE
    elif issues:
        classification = PriceSanityClassification.WARNING
    else:
        classification = PriceSanityClassification.ACCEPT
    return PriceSanityResult(classification=classification, issues=tuple(issues))


detect_anomalies = assess_run_health
classify_price_sanity = check_price_sanity
