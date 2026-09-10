from __future__ import annotations

from argparse import Namespace
from decimal import Decimal

import pytest

from grocery_data import __main__ as cli
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ParseFailure,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SourceProduct,
    SourceStore,
)


def _raw(kind: str) -> RawBatch:
    return RawBatch(
        chain=Chain.COOP,
        documents=(
            RawFetch(
                chain=Chain.COOP,
                store_external_id="coop-test",
                kind=kind,
                method="GET",
                url=f"https://example.invalid/{kind}",
                http_status=200,
                content_type="application/json",
                payload=b"{}",
                connector_version="test-v1",
            ),
        ),
    )


class _MostlyFailingConnector:
    chain = Chain.COOP
    coverage = CoverageLevel.OFFERS_ONLY
    connector_version = "test-v1"
    parser_version = "test-parser-v1"

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        del area
        return _raw("stores")

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        del raw, area
        return [
            SourceStore(
                chain=Chain.COOP,
                external_id="coop-test",
                name="Coop Test",
                city="Lund",
                online_shopping=False,
                coverage=CoverageLevel.OFFERS_ONLY,
                raw_reference=references[0],
            )
        ]

    def catalog_eligible(self, store: SourceStore) -> bool:
        del store
        return True

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        del store
        return _raw("offers")

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        del raw
        products = [
            SourceProduct(
                chain=Chain.COOP,
                store_external_id=store.external_id,
                external_product_id=f"product-{index}",
                name=f"Product {index}",
                sale_price=Decimal("10.00"),
                raw_reference=references[0],
            )
            for index in range(14)
        ]
        failures = [
            ParseFailure(
                raw_record_reference=references[0],
                error_code="invalid_price",
                error_message="test failure",
                parser_version=self.parser_version,
            )
            for _ in range(38)
        ]
        return ProductParseResult(products=products, failures=failures)

    async def aclose(self) -> None:
        return None


def test_citygross_canary_factory_is_bounded_and_does_not_use_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def client_factory(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(cli, "CityGrossClient", client_factory)
    monkeypatch.setattr(cli, "CityGrossConnector", lambda *, client: client)

    connector = cli._canary_connector(Chain.CITY_GROSS)

    assert connector is not None
    assert captured == {"page_size": 5, "max_pages": 1, "allow_full_crawl": False}


@pytest.mark.asyncio
async def test_canary_does_not_report_healthy_when_most_records_fail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    connector = _MostlyFailingConnector()
    settings = GroceryDataSettings(
        database_url="sqlite+pysqlite:///:memory:",
        raw_snapshot_root=tmp_path,
        user_agent="test",
    )
    output: list[dict[str, object]] = []

    class _Registry:
        def create(self, chain: Chain) -> _MostlyFailingConnector:
            assert chain == Chain.COOP
            return connector

    class _Settings:
        @classmethod
        def from_env(cls) -> GroceryDataSettings:
            return settings

    monkeypatch.setattr(cli, "ConnectorRegistry", _Registry)
    monkeypatch.setattr(cli, "GroceryDataSettings", _Settings)
    monkeypatch.setattr(cli, "_json", output.append)

    exit_code = await cli._canary(Namespace(chain="coop", city="Lund"))

    assert exit_code == 2
    assert output[0]["status"] == "broken"
    assert output[0]["parse_success_rate"] == pytest.approx(14 / 52)
    assert output[0]["minimum_parse_success_rate"] == 0.95
    assert output[0]["parser_health_passed"] is False
