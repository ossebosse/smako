import pytest

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.services.connector_acceptance import (
    BASE_REQUIRED,
    CATALOG_REQUIRED,
    AcceptanceCheck,
    ConnectorAcceptanceContract,
    assess_parser_health,
)


def test_full_catalog_requires_proven_complete_pagination() -> None:
    contract = ConnectorAcceptanceContract(
        chain=Chain.COOP,
        declared_coverage=CoverageLevel.FULL_CATALOG,
        source_supports_member_prices=True,
    )
    passed = set(BASE_REQUIRED | CATALOG_REQUIRED)
    passed.update(
        {
            AcceptanceCheck.PROMOTION_SEMANTICS,
            AcceptanceCheck.MEMBER_PRICE_SEPARATION,
        }
    )

    report = contract.assess(passed)
    assert report.contract_passed is False
    assert report.missing_required == (AcceptanceCheck.PAGINATION_COMPLETE,)
    with pytest.raises(RuntimeError, match="pagination_complete"):
        report.require_implemented()

    accepted = contract.assess({*passed, AcceptanceCheck.PAGINATION_COMPLETE})
    assert accepted.contract_passed is True
    assert accepted.implementation_eligible is True


def test_partial_catalog_is_truthful_without_claiming_complete_pagination() -> None:
    contract = ConnectorAcceptanceContract(
        chain=Chain.COOP,
        declared_coverage=CoverageLevel.PARTIAL_CATALOG,
        source_supports_promotions=False,
    )
    report = contract.assess(set(BASE_REQUIRED | CATALOG_REQUIRED))

    assert AcceptanceCheck.PAGINATION_COMPLETE not in report.required_checks
    assert report.implementation_eligible is True


def test_offers_only_contract_does_not_require_catalog_fetch() -> None:
    contract = ConnectorAcceptanceContract(
        chain=Chain.ICA,
        declared_coverage=CoverageLevel.OFFERS_ONLY,
    )
    passed = {
        *BASE_REQUIRED,
        AcceptanceCheck.OFFERS_FETCH,
        AcceptanceCheck.PROMOTION_SEMANTICS,
    }
    report = contract.assess(passed)

    assert AcceptanceCheck.CATALOG_FETCH not in report.required_checks
    assert AcceptanceCheck.PAGINATION_COMPLETE not in report.required_checks
    assert report.implementation_eligible is True


def test_unavailable_can_pass_truthfulness_contract_but_is_not_implemented() -> None:
    contract = ConnectorAcceptanceContract(
        chain=Chain.COOP,
        declared_coverage=CoverageLevel.UNAVAILABLE,
    )
    report = contract.assess(
        {
            AcceptanceCheck.STORE_DISCOVERY,
            AcceptanceCheck.ACCESS_POLICY_RESPECTED,
            AcceptanceCheck.COVERAGE_DECLARED,
            AcceptanceCheck.OFFLINE_TESTS,
        }
    )

    assert report.contract_passed is True
    assert report.implementation_eligible is False


def test_parser_health_acceptance_fails_closed_for_mostly_quarantined_canary() -> None:
    parser_health = assess_parser_health(products_parsed=14, products_quarantined=38)

    assert parser_health.parse_success_rate == pytest.approx(14 / 52)
    assert parser_health.minimum_parse_success_rate == 0.95
    assert parser_health.status.value == "broken"
    assert parser_health.accepted is False

    contract = ConnectorAcceptanceContract(
        chain=Chain.COOP,
        declared_coverage=CoverageLevel.OFFERS_ONLY,
        source_supports_member_prices=True,
    )
    passed = set(contract.required_checks())
    report = contract.assess(passed, parser_health=parser_health)

    assert report.contract_passed is False
    assert report.implementation_eligible is False
    assert report.missing_required == (AcceptanceCheck.PARSER_HEALTH,)


def test_parser_health_acceptance_includes_exact_ninety_five_percent() -> None:
    parser_health = assess_parser_health(products_parsed=95, products_quarantined=5)

    assert parser_health.parse_success_rate == pytest.approx(0.95)
    assert parser_health.status.value == "healthy"
    assert parser_health.accepted is True
