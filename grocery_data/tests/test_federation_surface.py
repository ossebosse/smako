from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from grocery_data import __main__ as cli
from grocery_data.app.connectors import ConnectorRegistry
from grocery_data.app.domain import Chain
from grocery_data.app.services.source_disagreement import (
    ProviderPriceObservation,
    SourceDisagreementService,
)


def _observation(
    provider: str,
    name: str,
    price: str,
    *,
    gtin: str | None = None,
    external_product_id: str | None = None,
) -> ProviderPriceObservation:
    return ProviderPriceObservation(
        chain="ica",
        logical_context_id="ica-gunnesbo",
        source_provider=provider,
        source_snapshot_id=f"{provider}-snapshot",
        observed_at=datetime(2026, 8, 23, tzinfo=UTC),
        name=name,
        sale_price=Decimal(price),
        gtin=gtin,
        external_product_id=external_product_id,
    )


def test_source_disagreement_report_is_diagnostic_and_never_averages() -> None:
    primary = [
        _observation("own", "Mjölk", "20.00", gtin="4006381333931"),
        _observation("own", "Pasta", "30.00", external_product_id="pasta-1"),
        _observation("own", "Ägg", "40.00", external_product_id="eggs-1"),
        _observation("own", "Bara egen", "10.00", external_product_id="own-only"),
    ]
    secondary = [
        _observation("primat", "Mjölk", "20.00", gtin="4006381333931"),
        _observation("primat", "Pasta", "30.80", external_product_id="pasta-1"),
        _observation("primat", "Ägg", "42.00", external_product_id="eggs-1"),
        _observation("primat", "Bara Primat", "11.00", external_product_id="primat-only"),
    ]

    report = SourceDisagreementService().compare(
        primary,
        secondary,
        chain="ica",
        logical_context_id="ica-gunnesbo",
    )

    assert report.products_compared == 3
    assert report.matched_by_gtin == 1
    assert report.matched_by_external_product_id == 2
    assert report.same_price == 1
    assert report.within_one_sek == 1
    assert report.over_one_sek == 1
    assert report.same_price_percent == Decimal("33.33")
    assert report.only_primary == 1
    assert report.only_secondary == 1
    assert {sample.primary_price for sample in report.samples} == {
        Decimal("30.00"),
        Decimal("40.00"),
    }
    assert "never averaged" in report.note


def test_collect_all_plan_uses_only_explicit_own_roles_and_verified_geography() -> None:
    targets, skipped = cli._collect_all_plan(["Lund", "Malmö"], ConnectorRegistry())

    assert (Chain.WILLYS, "Lund", ("basket", "offers")) in targets
    assert (Chain.ICA, "Lund", ("offers", "enrichment")) in targets
    assert (Chain.COOP, "Malmö", ("offers",)) in targets
    assert (Chain.COOP, "Lund", ("offers",)) in targets
    coop_basket_targets = [
        target for target in targets if target[0] is Chain.COOP and target[2] == ("basket",)
    ]
    assert coop_basket_targets == [(Chain.COOP, "Lund", ("basket",))]
    assert not any(
        target[0] is Chain.COOP and set(target[2]) == {"basket", "offers"}
        for target in targets
    )
    assert (Chain.CITY_GROSS, "Malmö", ("basket", "offers")) in targets
    assert (Chain.CITY_GROSS, "Lund", ("basket", "offers")) not in targets
    assert (Chain.HEMKOP, "Malmö", ("basket", "offers")) not in targets
    assert (Chain.HEMKOP, "Lund", ("basket", "offers")) not in targets
    assert any(
        item["chain"] == "citygross"
        and item["city"] == "Lund"
        and "geography" in str(item["reason"])
        for item in skipped
    )
    assert any(
        item["chain"] == "hemkop" and item["city"] == "Lund" and "geography" in str(item["reason"])
        for item in skipped
    )
    assert any(
        item["chain"] == "hemkop"
        and item["city"] == "Malmö"
        and "geography" in str(item["reason"])
        for item in skipped
    )
    lidl_targets = [target for target in targets if target[0] is Chain.LIDL]
    assert len(lidl_targets) <= 1
    if lidl_targets:
        assert lidl_targets[0][1] == "Sverige"


def test_coop_exact_scope_is_regional_and_not_city_qualified() -> None:
    assert cli._exact_collection_scope(Chain.COOP, "Lund", "730400") == (
        "coop:online:730400"
    )
    assert cli._exact_collection_scope(Chain.COOP, "Malmö", "730400") == (
        "coop:online:730400"
    )
    assert cli._exact_collection_scope(Chain.HEMKOP, "Lund", "4123") == (
        "lund:hemkop:4123"
    )


def test_daily_lidl_collection_uses_complete_offer_traversal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = object()
    monkeypatch.setattr(cli, "LidlConnector", lambda: marker)

    assert cli._collection_connector(Chain.LIDL) is marker


@pytest.mark.asyncio
async def test_collect_all_isolates_failure_and_reports_last_known_good(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("HEMKOP_STORE_EXTERNAL_IDS", "test-context")
    class FakeEngine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    class FakeMetrics:
        products_parsed = 5
        request_count = 2

        def model_dump(self, *, mode: str) -> dict[str, int]:
            assert mode == "json"
            return {"products_parsed": 5, "request_count": 2}

    class FakeCollector:
        def __init__(self, *_: object) -> None:
            pass

        async def collect_area(self, connector, area, *, auto_promote: bool):  # type: ignore[no-untyped-def]
            assert auto_promote is True
            if connector.chain is Chain.WILLYS:
                raise RuntimeError("secret should not be emitted")
            return SimpleNamespace(
                scope_key=area.city.casefold(),
                snapshot_id="hemkop-candidate",
                active_snapshot_id="hemkop-active",
                status=SimpleNamespace(value="healthy"),
                promoted=True,
                stores=[object()],
                metrics=FakeMetrics(),
                warnings=(),
                source_policy_audit=None,
            )

    engine = FakeEngine()
    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: (SimpleNamespace(raw_snapshot_root=tmp_path), engine, object()),
    )
    monkeypatch.setattr(
        cli,
        "_collect_all_plan",
        lambda _cities: (
            [
                (Chain.WILLYS, "Malmö", ("basket",)),
                (Chain.HEMKOP, "Malmö", ("basket", "offers")),
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        cli,
        "_hemkop_collect_all_contexts",
        lambda _factory, _cities: ([], [], 0),
    )
    monkeypatch.setattr(
        cli,
        "_collection_connector",
        lambda chain: SimpleNamespace(chain=chain),
    )
    monkeypatch.setattr(cli, "GroceryCollector", FakeCollector)
    monkeypatch.setattr(
        cli,
        "_last_known_good",
        lambda _factory, chain, _city: {
            "active_snapshot_id": f"{chain.value}-lkg",
            "active_snapshot_age_hours": 3.0,
            "active_snapshot_coverage": "full_catalog",
        },
    )

    exit_code = await cli._collect_all(SimpleNamespace(city=["Malmö"], no_promote=False))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert engine.disposed is True
    assert payload["summary"] == {
        "targets": 2,
        "completed": 1,
        "failed": 1,
        "skipped": 0,
        "external_provider_requests": 0,
        "fallbacks_used": 0,
    }
    assert payload["results"][0]["error_type"] == "RuntimeError"
    assert payload["results"][0]["active_snapshot_id"] == "willys-lkg"
    assert "secret" not in json.dumps(payload)
    assert payload["results"][1]["chain"] == "hemkop"
    assert payload["results"][1]["promoted"] is True


@pytest.mark.asyncio
async def test_coop_regional_catalog_failure_isolated_from_city_offers_and_peers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("COOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("COOP_ONLINE_CONTEXT_IDS", "730400")
    class FakeEngine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    class FakeMetrics:
        products_parsed = 5
        request_count = 2

        def model_dump(self, *, mode: str) -> dict[str, int]:
            assert mode == "json"
            return {"products_parsed": 5, "request_count": 2}

    closed: list[str] = []

    class FakeConnector:
        def __init__(self, chain: Chain, label: str) -> None:
            self.chain = chain
            self.label = label

        async def aclose(self) -> None:
            closed.append(self.label)

    class FakeCollector:
        def __init__(self, *_: object) -> None:
            pass

        async def collect_area(
            self,
            connector: FakeConnector,
            area,
            *,
            auto_promote: bool,
            scope_key: str | None = None,
        ):  # type: ignore[no-untyped-def]
            assert auto_promote is True
            assert scope_key is None
            return SimpleNamespace(
                scope_key=area.city.casefold(),
                snapshot_id=f"snapshot:{connector.label}",
                status=SimpleNamespace(value="healthy"),
                promoted=True,
                stores=(object(),),
                metrics=FakeMetrics(),
                warnings=(),
                source_policy_audit=None,
            )

    engine = FakeEngine()
    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: (SimpleNamespace(raw_snapshot_root=tmp_path), engine, object()),
    )
    monkeypatch.setattr(
        cli,
        "_collect_all_plan",
        lambda _cities: (
            [
                (Chain.COOP, "Lund", ("offers",)),
                (Chain.COOP, "Lund", ("basket",)),
                (Chain.WILLYS, "Lund", ("basket",)),
            ],
            [],
        ),
    )
    monkeypatch.setattr(
        cli,
        "_hemkop_collect_all_contexts",
        lambda _factory, _cities: ([], [], 0),
    )
    monkeypatch.setattr(
        cli,
        "_collection_connector",
        lambda chain: FakeConnector(chain, f"{chain.value}:bounded"),
    )

    def blocked_exact(chain: Chain, context_id: str):
        assert chain is Chain.COOP
        assert context_id == "730400"
        raise RuntimeError("private upstream detail must not be emitted")

    monkeypatch.setattr(cli, "_exact_collection_connector", blocked_exact)
    monkeypatch.setattr(cli, "GroceryCollector", FakeCollector)
    lkg_scopes: list[str] = []

    def fake_lkg(_factory, chain: Chain, scope: str) -> dict[str, object]:
        lkg_scopes.append(scope)
        return {
            "active_snapshot_id": f"lkg:{chain.value}:{scope}",
            "active_snapshot_age_hours": 2.0,
            "active_snapshot_coverage": "full_online_catalog",
        }

    monkeypatch.setattr(cli, "_last_known_good", fake_lkg)

    report, exit_code = await cli._run_collect_all(
        SimpleNamespace(city=["Lund", "Malmö"], no_promote=False)
    )

    assert exit_code == 2
    assert engine.disposed is True
    assert closed == ["coop:bounded", "willys:bounded"]
    assert lkg_scopes == ["Lund", "coop:online:730400", "Lund"]
    assert report["summary"] == {
        "targets": 3,
        "completed": 2,
        "failed": 1,
        "skipped": 0,
        "external_provider_requests": 0,
        "fallbacks_used": 0,
    }
    online = next(
        row
        for row in report["results"]
        if row.get("scope_key") == "coop:online:730400"
    )
    assert online["status"] == "failed"
    assert online["active_snapshot_id"] == "lkg:coop:coop:online:730400"
    assert online["served_cities"] == ("Lund", "Malmö")
    assert online["roles"] == ("basket",)
    assert "private upstream detail" not in json.dumps(report)


def test_collect_all_cli_contract_is_daily_and_bounded_by_explicit_cities() -> None:
    args = cli._parser().parse_args(
        ["collect-all", "--city", "Lund", "--city", "Malmö", "--no-promote"]
    )

    assert args.command == "collect-all"
    assert args.city == ["Lund", "Malmö"]
    assert args.no_promote is True
