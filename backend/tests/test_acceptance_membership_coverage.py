from __future__ import annotations

import pytest
from scripts.acceptance_membership_coverage import (
    _assert_monotonic,
    _top_timings,
    _validity_bucket,
)

from grocery_data.app.domain.promotion_pricing import (
    PriceContract,
    PromotionEligibility,
    PromotionMechanism,
)
from scripts import acceptance_membership_coverage as acceptance


def test_top_timings_is_descending_bounded_and_stable() -> None:
    assert _top_timings(
        {"small": 1.0, "same_b": 2, "same_a": 2.0, "metadata": "ignored"},
        limit=3,
    ) == [
        {"operation": "same_a", "milliseconds": 2.0},
        {"operation": "same_b", "milliseconds": 2.0},
        {"operation": "small", "milliseconds": 1.0},
    ]


def test_fixed_menu_monotonicity_accepts_equal_or_cheaper_membership_baskets() -> None:
    _assert_monotonic(
        {
            "NO_MEMBERSHIPS": {"total": 100.0},
            "ICA_ONLY": {"total": 100.0},
            "ALL_MEMBERSHIPS": {"total": 92.5},
        }
    )


def test_fixed_menu_monotonicity_rejects_more_expensive_membership_basket() -> None:
    with pytest.raises(AssertionError, match="monotonicity failed"):
        _assert_monotonic(
            {
                "NO_MEMBERSHIPS": {"total": 100.0},
                "ALL_MEMBERSHIPS": {"total": 100.01},
            }
        )


def test_contract_validity_buckets_are_mutually_exclusive() -> None:
    base = {
        "eligibility": PromotionEligibility.PUBLIC,
        "mechanism": PromotionMechanism.REGULAR,
        "description": "Ordinarie pris",
        "price": 10,
    }
    current = PriceContract(reference="current", **base)
    expired = PriceContract(reference="expired", valid_to="2026-08-30", **base)
    future = PriceContract(reference="future", valid_from="2026-09-01", **base)

    from datetime import date

    evaluated = date(2026, 8, 31)
    assert _validity_bucket(current, pricing_date=evaluated) == "active_now"
    assert _validity_bucket(expired, pricing_date=evaluated) == "expired"
    assert _validity_bucket(future, pricing_date=evaluated) == "future"


def test_artifact_report_path_is_repository_relative(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    artifact = repository / "price_universes" / "artifacts" / "digest.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(acceptance, "REPOSITORY_ROOT", repository)

    assert acceptance._safe_artifact_report_path(artifact) == (
        "price_universes/artifacts/digest.json"
    )


def test_artifact_report_path_rejects_user_directory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    outside = tmp_path / "user-name" / "artifact.json"
    outside.parent.mkdir()
    outside.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(acceptance, "REPOSITORY_ROOT", repository)

    with pytest.raises(ValueError, match="inside the repository"):
        acceptance._safe_artifact_report_path(outside)
