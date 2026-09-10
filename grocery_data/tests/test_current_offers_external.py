from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import grocery_data.__main__ as grocery_cli
from grocery_data.app.domain.promotion_pricing import PromotionMechanism
from grocery_data.app.services.current_offers_external import (
    ExternalStoreOfferBinding,
    load_closed_primat_current_offers,
    parse_explicit_multibuy,
)

NOW = datetime(2026, 8, 30, 10, tzinfo=UTC)


def _binding(**overrides: str) -> ExternalStoreOfferBinding:
    values = {
        "physical_store_id": "physical:ica:1088004",
        "physical_store_external_id": "1088004",
        "store_display_name": "Maxi ICA Stormarknad Gunnesbo",
        "chain": "ica",
        "grocery_context_id": "primat:ica:1088004",
        "provider_store_id": "primat-store-gunnesbo",
    }
    values.update(overrides)
    return ExternalStoreOfferBinding.model_validate(values)


def _offer(
    *,
    description: str = "Kampanjpris",
    kind: str = "campaign",
    price: object = 19.9,
    required_packages: int = 1,
    valid_from: str | None = "2026-08-29",
    valid_to: str | None = "2026-08-31",
    member_program: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "description": description,
        "kind": kind,
        "price": price,
        "required_packages": required_packages,
        "valid_from": valid_from,
        "valid_to": valid_to,
    }
    if member_program is not None:
        row["member_program"] = member_program
    return row


def _product(
    *,
    product_id: str,
    name: str,
    offers: list[dict[str, object]],
    provider_store_id: str = "primat-store-gunnesbo",
    snapshot_id: str = "primat-snapshot-1",
    regular_price: object | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "product_id": product_id,
        "name": name,
        "chain": "ica",
        "gtin": f"73100000000{product_id[-2:]}",
        "brand": "Fixture",
        "package_description": "1 st",
        "comparison_price": 19.9,
        "comparison_unit": "st",
        "semantic_confidence": "high",
        "quantity_confidence": "exact",
        "offers": offers,
        "source_provenance": {
            "source_provider": "primat",
            "source_channel": "catalog",
            "provider_store_id": provider_store_id,
            "source_snapshot_id": snapshot_id,
            "source_observed_at": "2026-08-30T08:00:00+00:00",
        },
    }
    if regular_price is not None:
        row["regular_price"] = regular_price
    return row


def _write_cache(
    path: Path,
    *,
    products: list[dict[str, object]],
    captured_at: datetime = NOW - timedelta(hours=2),
    provider_store_id: str = "primat-store-gunnesbo",
    physical_store_external_id: str = "1088004",
    chain: str = "ica",
    snapshot_id: str = "primat-snapshot-1",
) -> Path:
    payload = {
        "schema_version": "lund-frozen-external-v1",
        "postal_code": "22350",
        "captured_at": captured_at.isoformat(),
        "stores": [
            {
                "store_id": provider_store_id,
                "chain": chain,
                "physical_store_external_id": physical_store_external_id,
                "price_context_type": "physical_store",
                "source_provenance": {
                    "source_provider": "primat",
                    "source_channel": "catalog",
                    "provider_store_id": provider_store_id,
                    "source_snapshot_id": snapshot_id,
                    "source_observed_at": captured_at.isoformat(),
                },
            }
        ],
        "products": products,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_external_offers_require_exact_provider_and_physical_store_binding(
    tmp_path: Path,
) -> None:
    path = _write_cache(
        tmp_path / "cache.json",
        products=[_product(product_id="p01", name="Mjölk", offers=[_offer()])],
    )

    exact = load_closed_primat_current_offers(path, (_binding(),), now=NOW)
    wrong_physical = load_closed_primat_current_offers(
        path,
        (_binding(physical_store_external_id="different-store"),),
        now=NOW,
    )
    wrong_provider = load_closed_primat_current_offers(
        path,
        (_binding(provider_store_id="different-provider-context"),),
        now=NOW,
    )

    assert len(exact.offers) == 1
    assert exact.offers[0].physical_store_id == "physical:ica:1088004"
    assert exact.offers[0].grocery_context_id == "primat:ica:1088004"
    assert wrong_physical.offers == ()
    assert wrong_physical.diagnostics["invalid_store_rows"] == 1
    assert wrong_provider.offers == ()
    assert wrong_provider.source_statuses[0].reason == (
        "exact provider context is absent from the active closed cache"
    )


def test_expired_and_future_external_offers_are_excluded(tmp_path: Path) -> None:
    path = _write_cache(
        tmp_path / "cache.json",
        products=[
            _product(
                product_id="p01",
                name="Active",
                offers=[_offer(valid_from="2026-08-30", valid_to="2026-08-30")],
            ),
            _product(
                product_id="p02",
                name="Expired",
                offers=[_offer(valid_from="2026-08-20", valid_to="2026-08-29")],
            ),
            _product(
                product_id="p03",
                name="Future",
                offers=[_offer(valid_from="2026-08-31", valid_to="2026-09-02")],
            ),
        ],
    )

    result = load_closed_primat_current_offers(path, (_binding(),), now=NOW)

    assert [row.product_name for row in result.offers] == ["Active"]
    assert result.diagnostics["expired_offers_excluded"] == 1
    assert result.diagnostics["future_offers_excluded"] == 1
    assert result.offers[0].validity_confidence == "explicit_period"


def test_strict_n_for_x_source_text_restores_the_multibuy_contract(
    tmp_path: Path,
) -> None:
    assert parse_explicit_multibuy("15 för 100kr") == (15, Decimal("100.00"))
    assert parse_explicit_multibuy("Spara 15 kr") is None
    assert parse_explicit_multibuy("15 x 100 kr") is None

    path = _write_cache(
        tmp_path / "cache.json",
        products=[
            _product(
                product_id="p01",
                name="Fifteen pack offer",
                offers=[
                    _offer(
                        description="15 för 100kr",
                        kind="campaign",
                        price=6.67,
                        required_packages=1,
                    )
                ],
            )
        ],
    )

    result = load_closed_primat_current_offers(path, (_binding(),), now=NOW)

    [row] = result.offers
    assert row.mechanism is PromotionMechanism.MULTIBUY
    assert row.required_quantity == 15
    assert row.multibuy_total == Decimal("100.00")
    assert row.derived_unit_price == Decimal("6.67")
    assert row.derived_unit_price_is_conditional is True
    assert row.active_offer_price is None
    assert row.promotion_confidence == "explicit_source_text"


def test_conflicting_structured_and_text_multibuy_fails_closed(tmp_path: Path) -> None:
    path = _write_cache(
        tmp_path / "cache.json",
        products=[
            _product(
                product_id="p01",
                name="Conflicting offer",
                offers=[
                    _offer(
                        description="2 för 30 kr",
                        kind="multibuy",
                        price=30,
                        required_packages=3,
                    )
                ],
            )
        ],
    )

    result = load_closed_primat_current_offers(path, (_binding(),), now=NOW)

    assert result.offers == ()
    assert result.diagnostics["invalid_contracts_excluded"] == 1


def test_external_offer_without_dedicated_regular_price_has_no_savings(
    tmp_path: Path,
) -> None:
    path = _write_cache(
        tmp_path / "cache.json",
        products=[
            _product(
                product_id="p01",
                name="No baseline",
                offers=[_offer(price=10)],
            )
        ],
    )

    result = load_closed_primat_current_offers(path, (_binding(),), now=NOW)

    [row] = result.offers
    assert row.regular_price is None
    assert row.savings_amount is None
    assert row.savings_percent is None


def test_stale_external_cache_is_excluded_by_default_and_marked_when_included(
    tmp_path: Path,
) -> None:
    path = _write_cache(
        tmp_path / "cache.json",
        captured_at=NOW - timedelta(hours=30),
        products=[_product(product_id="p01", name="Stale", offers=[_offer()])],
    )

    excluded = load_closed_primat_current_offers(
        path,
        (_binding(),),
        now=NOW,
        max_age_hours=24,
    )
    included = load_closed_primat_current_offers(
        path,
        (_binding(),),
        now=NOW,
        max_age_hours=24,
        include_stale=True,
    )

    assert excluded.offers == ()
    assert excluded.fresh is False
    assert excluded.source_statuses[0].fresh is False
    assert excluded.source_statuses[0].lkg_used is True
    assert "freshness limit" in (excluded.source_statuses[0].reason or "")
    assert len(included.offers) == 1
    assert included.offers[0].stale is True
    assert included.offers[0].lkg_used is True


def test_current_offers_cli_parser_supports_store_preset_filters_and_refresh() -> None:
    args = grocery_cli._parser().parse_args(
        [
            "current-offers-report",
            "--city",
            "Lund",
            "--preset",
            "lund-selected-stores",
            "--store",
            "Hemköp Karhögstorg",
            "--refresh-if-stale",
            "--member-only",
            "--include-stale",
            "--sort",
            "name",
            "--format",
            "json",
        ]
    )

    assert args.command == "current-offers-report"
    assert args.city == "Lund"
    assert args.preset == "lund-selected-stores"
    assert args.store == ["Hemköp Karhögstorg"]
    assert args.refresh_if_stale is True
    assert args.member_only is True
    assert args.public_only is False
    assert args.multibuy_only is False
    assert args.include_stale is True
    assert args.sort == "name"
    assert args.format == "json"
