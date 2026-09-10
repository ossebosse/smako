from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain import (
    Chain,
    ConnectorStatus,
    CoverageLevel,
    RunMetrics,
    is_complete_catalog_coverage,
)
from grocery_data.app.monitoring.anomaly_detection import AnomalyThresholds, assess_run_health


class ParserHealthAcceptance(BaseModel):
    """Runtime evidence for the parser-health acceptance check."""

    model_config = ConfigDict(frozen=True)

    status: ConnectorStatus
    products_parsed: int = Field(ge=0)
    products_quarantined: int = Field(ge=0)
    parse_success_rate: float = Field(ge=0, le=1)
    minimum_parse_success_rate: float = Field(ge=0, le=1)

    @property
    def accepted(self) -> bool:
        return self.status == ConnectorStatus.HEALTHY


def assess_parser_health(
    *,
    products_parsed: int,
    products_quarantined: int,
    thresholds: AnomalyThresholds | None = None,
) -> ParserHealthAcceptance:
    """Apply the shared health thresholds without unrelated price-rate signals.

    A canary with no successfully parsed records fails closed. Otherwise the
    shared anomaly policy classifies parse rates below 95% as degraded and
    below 70% as broken by default.
    """

    policy = thresholds or AnomalyThresholds()
    metrics = RunMetrics(
        products_fetched=products_parsed + products_quarantined,
        products_parsed=products_parsed,
        products_quarantined=products_quarantined,
        # Parser health is intentionally isolated from the separate price gate.
        products_with_price=products_parsed,
    )
    assessment = assess_run_health(metrics, thresholds=policy)
    status = assessment.status if products_parsed else ConnectorStatus.BROKEN
    return ParserHealthAcceptance(
        status=status,
        products_parsed=products_parsed,
        products_quarantined=products_quarantined,
        parse_success_rate=metrics.parse_success_rate,
        minimum_parse_success_rate=policy.degraded_parse_success_rate,
    )


class AcceptanceCheck(StrEnum):
    STORE_DISCOVERY = "store_discovery"
    ACCESS_POLICY_RESPECTED = "access_policy_respected"
    RAW_PERSISTENCE = "raw_persistence"
    PARSER = "parser"
    SOURCE_NORMALIZATION = "source_normalization"
    PRICE_SEMANTICS = "price_semantics"
    PURCHASE_QUANTITY_SEMANTICS = "purchase_quantity_semantics"
    NO_FABRICATED_QUANTITY = "no_fabricated_quantity"
    COVERAGE_DECLARED = "coverage_declared"
    PARSER_HEALTH = "parser_health"
    SCHEMA_FINGERPRINT = "schema_fingerprint"
    ATOMIC_PROMOTION = "atomic_promotion"
    LAST_KNOWN_GOOD = "last_known_good"
    OFFLINE_REPLAY = "offline_replay"
    ZERO_NETWORK_REPLAY = "zero_network_replay"
    SIMULATED_BREAK = "simulated_break"
    CONNECTOR_LOCAL_REPAIR = "connector_local_repair"
    GENERIC_API = "generic_api"
    OWN_PROVIDER = "own_provider"
    OFFLINE_TESTS = "offline_tests"
    CATALOG_FETCH = "catalog_fetch"
    CATALOG_SCOPE_DEFINED = "catalog_scope_defined"
    PAGINATION_FAIL_CLOSED = "pagination_fail_closed"
    PAGINATION_COMPLETE = "pagination_complete"
    OFFERS_FETCH = "offers_fetch"
    PROMOTION_SEMANTICS = "promotion_semantics"
    MEMBER_PRICE_SEPARATION = "member_price_separation"


BASE_REQUIRED = frozenset(
    {
        AcceptanceCheck.STORE_DISCOVERY,
        AcceptanceCheck.ACCESS_POLICY_RESPECTED,
        AcceptanceCheck.RAW_PERSISTENCE,
        AcceptanceCheck.PARSER,
        AcceptanceCheck.SOURCE_NORMALIZATION,
        AcceptanceCheck.NO_FABRICATED_QUANTITY,
        AcceptanceCheck.COVERAGE_DECLARED,
        AcceptanceCheck.PARSER_HEALTH,
        AcceptanceCheck.SCHEMA_FINGERPRINT,
        AcceptanceCheck.ATOMIC_PROMOTION,
        AcceptanceCheck.LAST_KNOWN_GOOD,
        AcceptanceCheck.OFFLINE_REPLAY,
        AcceptanceCheck.ZERO_NETWORK_REPLAY,
        AcceptanceCheck.SIMULATED_BREAK,
        AcceptanceCheck.CONNECTOR_LOCAL_REPAIR,
        AcceptanceCheck.GENERIC_API,
        AcceptanceCheck.OWN_PROVIDER,
        AcceptanceCheck.OFFLINE_TESTS,
    }
)
CATALOG_REQUIRED = frozenset(
    {
        AcceptanceCheck.CATALOG_FETCH,
        AcceptanceCheck.CATALOG_SCOPE_DEFINED,
        AcceptanceCheck.PRICE_SEMANTICS,
        AcceptanceCheck.PURCHASE_QUANTITY_SEMANTICS,
        AcceptanceCheck.PAGINATION_FAIL_CLOSED,
    }
)
OFFER_REQUIRED = frozenset(
    {
        AcceptanceCheck.OFFERS_FETCH,
        AcceptanceCheck.PROMOTION_SEMANTICS,
        AcceptanceCheck.MEMBER_PRICE_SEPARATION,
    }
)


class ConnectorAcceptanceContract(BaseModel):
    """Coverage-aware contract shared by every connector implementation."""

    model_config = ConfigDict(frozen=True)

    chain: Chain
    declared_coverage: CoverageLevel
    source_supports_promotions: bool = True
    source_supports_member_prices: bool = False

    def required_checks(self) -> frozenset[AcceptanceCheck]:
        if self.declared_coverage == CoverageLevel.UNAVAILABLE:
            return frozenset(
                {
                    AcceptanceCheck.STORE_DISCOVERY,
                    AcceptanceCheck.ACCESS_POLICY_RESPECTED,
                    AcceptanceCheck.COVERAGE_DECLARED,
                    AcceptanceCheck.OFFLINE_TESTS,
                }
            )
        required = set(BASE_REQUIRED)
        if self.declared_coverage == CoverageLevel.PARTIAL_CATALOG or is_complete_catalog_coverage(
            self.declared_coverage
        ):
            required.update(CATALOG_REQUIRED)
        if is_complete_catalog_coverage(self.declared_coverage):
            required.add(AcceptanceCheck.PAGINATION_COMPLETE)
        if self.declared_coverage == CoverageLevel.OFFERS_ONLY:
            required.add(AcceptanceCheck.OFFERS_FETCH)
        if self.source_supports_promotions:
            required.add(AcceptanceCheck.PROMOTION_SEMANTICS)
        if self.source_supports_member_prices:
            required.add(AcceptanceCheck.MEMBER_PRICE_SEPARATION)
        return frozenset(required)

    def assess(
        self,
        passed_checks: set[AcceptanceCheck],
        *,
        parser_health: ParserHealthAcceptance | None = None,
    ) -> ConnectorAcceptanceReport:
        required = self.required_checks()
        effective_passed = set(passed_checks)
        if parser_health is not None and not parser_health.accepted:
            effective_passed.discard(AcceptanceCheck.PARSER_HEALTH)
        missing = tuple(sorted(required - effective_passed, key=lambda item: item.value))
        return ConnectorAcceptanceReport(
            chain=self.chain,
            declared_coverage=self.declared_coverage,
            required_checks=tuple(sorted(required, key=lambda item: item.value)),
            passed_checks=tuple(sorted(effective_passed & required, key=lambda item: item.value)),
            missing_required=missing,
            contract_passed=not missing,
            implementation_eligible=(
                not missing and self.declared_coverage != CoverageLevel.UNAVAILABLE
            ),
        )


class ConnectorAcceptanceReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    declared_coverage: CoverageLevel
    required_checks: tuple[AcceptanceCheck, ...]
    passed_checks: tuple[AcceptanceCheck, ...]
    missing_required: tuple[AcceptanceCheck, ...]
    contract_passed: bool
    implementation_eligible: bool

    def require_implemented(self) -> None:
        if not self.implementation_eligible:
            missing = ", ".join(check.value for check in self.missing_required) or "unavailable"
            raise RuntimeError(
                f"{self.chain.value} is not accepted for {self.declared_coverage.value}: {missing}"
            )
