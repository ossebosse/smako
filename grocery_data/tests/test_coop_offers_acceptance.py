from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from app.errors import PriceProviderError
from app.providers.own import OwnGroceryPriceProvider
from fastapi import FastAPI
from sqlalchemy import func, select

from grocery_data.app.api import catalog_router, health_router
from grocery_data.app.connectors.coop import CoopParser
from grocery_data.app.domain import (
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SourceStore,
)
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.connector_acceptance import (
    AcceptanceCheck,
    ConnectorAcceptanceContract,
    assess_parser_health,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import (
    ConnectorHealthRepository,
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    ParserFailureModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreModel,
)

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "coop" / "fixtures"


class _FixtureCoopOffersConnector:
    """Raw-first Coop transport double; parsing remains the production parser."""

    chain = Chain.COOP
    coverage = CoverageLevel.OFFERS_ONLY
    connector_version = "coop-fixture-v1"

    def __init__(
        self,
        offer_fixture: str,
        *,
        parser: CoopParser | None = None,
    ) -> None:
        self.offer_fixture = offer_fixture
        self.parser = parser or CoopParser()
        self.parser_version = self.parser.parser_version
        self.fetch_calls = 0
        self.offers_fetch_calls = 0
        self.closed = False

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        self.fetch_calls += 1
        del area
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    kind="store_page",
                    method="GET",
                    url="https://public.example/coop/stora-coop-lund",
                    http_status=200,
                    content_type="text/html",
                    payload=(FIXTURES / "store_lund.html").read_bytes(),
                    connector_version=self.connector_version,
                ),
            ),
        )

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        return self.parser.parse_stores(raw, references, area)

    def catalog_eligible(self, store: SourceStore) -> bool:
        return store.source_fields.get("disable_store_offers_flyer") is False

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        self.fetch_calls += 1
        self.offers_fetch_calls += 1
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    store_external_id=store.external_id,
                    kind="rendered_offers_page",
                    method="GET",
                    url="https://public.example/coop/stora-coop-lund/offers",
                    http_status=200,
                    content_type="text/html",
                    payload=(FIXTURES / self.offer_fixture).read_bytes(),
                    connector_version=self.connector_version,
                ),
            ),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        # OFFERS_ONLY still uses the collector's generic per-store processing hook.
        return await self.fetch_offers(store)

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        return self.parser.parse_catalog(raw, references, store)

    async def aclose(self) -> None:
        self.closed = True


class _RepairedFixtureParser(CoopParser):
    """Test-local representation of a connector-local parser repair."""

    parser_version = "coop-parser-v2-repair-test"

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        repaired_documents = tuple(
            document.model_copy(
                update={
                    "payload": document.payload.replace(
                        b"Current amount unavailable",
                        (
                            b"Medlemspris 39 kronor styck, Max 2 styck per hushall, "
                            b"Ordinarie pris 59 kronor och 57 ore styck"
                        ),
                    )
                }
            )
            for document in raw.documents
        )
        return super().parse_catalog(
            raw.model_copy(update={"documents": repaired_documents}),
            references,
            store,
        )


def _test_api(factory) -> FastAPI:  # type: ignore[no-untyped-def]
    application = FastAPI()
    application.state.session_factory = factory
    application.include_router(catalog_router)
    application.include_router(health_router)
    return application


@pytest.mark.asyncio
async def test_coop_offers_db_lkg_replay_api_provider_and_acceptance(
    tmp_path: Path,
) -> None:
    """Prove the OFFERS_ONLY operational contract from raw fixture to consumer."""

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    collector = GroceryCollector(factory, raw_store)

    good_connector = _FixtureCoopOffersConnector("member_price.html")
    good = await collector.collect_area(good_connector, GeographicArea(city="Lund"))

    assert good.status == ConnectorStatus.HEALTHY
    assert good.promoted is True
    assert good.active_snapshot_id == good.snapshot_id
    assert good.metrics.products_parsed == 1
    assert good.metrics.products_quarantined == 0
    assert good_connector.fetch_calls == 2
    assert good_connector.offers_fetch_calls == 1
    assert good_connector.closed is True
    parser_health = assess_parser_health(
        products_parsed=good.metrics.products_parsed,
        products_quarantined=good.metrics.products_quarantined,
    )
    assert parser_health.accepted is True

    with session_scope(factory) as session:
        good_snapshot = SnapshotRepository(session).get(good.snapshot_id)
        assert good_snapshot is not None
        assert good_snapshot.state == "promoted"
        assert good_snapshot.coverage == "offers_only"
        assert good_snapshot.schema_fingerprint
        store = session.scalar(select(StoreModel).where(StoreModel.external_id == "2696"))
        assert store is not None
        assert store.coverage == "offers_only"
        store_id = store.id
        assert session.scalar(select(func.count()).select_from(RawSnapshotModel)) == 2
        source = session.scalar(
            select(SourceProductModel).where(
                SourceProductModel.catalog_snapshot_id == good.snapshot_id
            )
        )
        product = session.scalar(
            select(ProductModel).where(ProductModel.catalog_snapshot_id == good.snapshot_id)
        )
        price = session.scalar(
            select(PriceObservationModel).where(
                PriceObservationModel.catalog_snapshot_id == good.snapshot_id
            )
        )
        promotion = session.scalar(
            select(PromotionModel).where(PromotionModel.catalog_snapshot_id == good.snapshot_id)
        )
        assert source is not None and product is not None and price is not None
        assert source.gtin is None  # URL identity is not fabricated into GTIN.
        assert product.sale_model == "fixed_package"
        assert product.quantity_confidence == "exact"
        assert price.sale_price == source.regular_price
        assert source.member_price == 39
        assert promotion is not None
        assert promotion.type == "member_price"
        assert promotion.member_only is True
        assert promotion.max_quantity == 2

    offline_connector = _FixtureCoopOffersConnector("member_price.html")
    replay = await DatabaseReplayService(factory, raw_store).replay_snapshot(
        offline_connector,
        good.snapshot_id,
        promote=False,
    )
    assert replay.network_requests == 0
    assert replay.products_parsed == 1
    assert replay.products_quarantined == 0
    assert replay.status == ConnectorStatus.HEALTHY
    assert offline_connector.fetch_calls == 0
    assert offline_connector.offers_fetch_calls == 0

    broken_connector = _FixtureCoopOffersConnector("schema_changed.html")
    broken = await collector.collect_area(broken_connector, GeographicArea(city="Lund"))

    assert broken.status == ConnectorStatus.BROKEN
    assert broken.promoted is False
    assert broken.active_snapshot_id == good.snapshot_id
    assert broken.metrics.products_parsed == 0
    assert broken.metrics.products_quarantined == 1
    with session_scope(factory) as session:
        snapshots = SnapshotRepository(session)
        assert snapshots.active(Chain.COOP, scope_key="lund").id == good.snapshot_id
        rejected = snapshots.get(broken.snapshot_id)
        assert rejected is not None
        assert rejected.state == "rejected"
        assert rejected.is_active is False
        assert rejected.rejection_reason is not None
        assert "parse success rate is 0.0%" in rejected.rejection_reason
        health = ConnectorHealthRepository(session).get(Chain.COOP)
        assert health is not None
        assert health.status == "broken"
        assert health.active_snapshot_id == good.snapshot_id
        assert (
            session.scalar(
                select(func.count())
                .select_from(ParserFailureModel)
                .where(ParserFailureModel.catalog_snapshot_id == broken.snapshot_id)
            )
            == 1
        )

    application = _test_api(factory)
    transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://grocery-data.test/",
    ) as client:
        health_response = await client.get("/health/connectors/coop")
        stores_response = await client.get("/stores", params={"chain": "coop", "city": "Lund"})
        offers_response = await client.get("/offers", params={"store_id": store_id})
        search_response = await client.get(
            "/products/search",
            params={"q": "Smör", "store_id": store_id},
        )
        catalog_response = await client.get(f"/catalog/{store_id}")

        assert health_response.status_code == 200
        assert health_response.json()["status"] == "broken"
        assert health_response.json()["latest_run_status"] == "broken"
        assert health_response.json()["snapshot_id"] == good.snapshot_id
        assert stores_response.status_code == 200
        assert stores_response.json()["stores"][0]["coverage"] == "offers_only"
        assert stores_response.json()["stores"][0]["source_channel"] == "offers"
        assert offers_response.status_code == 200
        assert offers_response.json()["count"] == 1
        assert offers_response.json()["offers"][0]["source_channel"] == "offers"
        assert offers_response.json()["offers"][0]["max_quantity"] == 2
        assert offers_response.json()["offers"][0]["product"]["source_channel"] == "offers"
        assert search_response.status_code == 200
        assert search_response.json()["count"] == 1
        assert search_response.json()["products"][0]["source_channel"] == "offers"
        assert catalog_response.status_code == 409
        assert "offers-only store has no verified catalog" in catalog_response.json()["detail"]

    default_transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=default_transport,
        base_url="http://grocery-data.test/",
    ) as client:
        provider = OwnGroceryPriceProvider(
            "http://grocery-data.test/",
            client=client,
        )
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22660")
        with pytest.raises(PriceProviderError, match="explicit opt-in"):
            await provider.get_offers(store_id)

    opted_in_transport = httpx.ASGITransport(app=application)
    async with httpx.AsyncClient(
        transport=opted_in_transport,
        base_url="http://grocery-data.test/",
    ) as client:
        provider = OwnGroceryPriceProvider(
            "http://grocery-data.test/",
            use_member_prices=True,
            include_offers_only=True,
            client=client,
        )
        with pytest.raises(PriceProviderError, match="inga användbara butiker"):
            await provider.find_stores("22660")
        stores = await provider.find_offer_stores("22660")
        products = await provider.search_products("Smör", [store_id])
        offers = await provider.get_offers(store_id)

        with pytest.raises(PriceProviderError, match="saknar verifierad katalog"):
            await provider.get_store_products(store_id)

        assert len(stores) == 1
        assert stores[0].tier == "offers_only"
        assert stores[0].source_provenance is not None
        assert stores[0].source_provenance.source_channel == "offers"
        assert products == []
        assert len(offers) == 1
        assert offers[0].source_provenance is not None
        assert offers[0].source_provenance.source_channel == "offers"
        assert offers[0].offers[0].max_quantity == 2

    repaired_connector = _FixtureCoopOffersConnector(
        "schema_changed.html",
        parser=_RepairedFixtureParser(),
    )
    repaired = await DatabaseReplayService(factory, raw_store).replay_snapshot(
        repaired_connector,
        broken.snapshot_id,
        promote=True,
        accept_schema_change=True,
    )
    assert repaired.network_requests == 0
    assert repaired_connector.fetch_calls == 0
    assert repaired.products_parsed == 1
    assert repaired.status == ConnectorStatus.HEALTHY
    assert repaired.promoted is True
    with session_scope(factory) as session:
        assert (
            SnapshotRepository(session).active(Chain.COOP, scope_key="lund").id
            == repaired.replay_snapshot_id
        )

    evidence = {
        AcceptanceCheck.STORE_DISCOVERY: bool(good.stores),
        AcceptanceCheck.ACCESS_POLICY_RESPECTED: good_connector.fetch_calls == 2,
        AcceptanceCheck.RAW_PERSISTENCE: good.raw_documents == 2,
        AcceptanceCheck.PARSER: good.metrics.products_parsed == 1,
        AcceptanceCheck.SOURCE_NORMALIZATION: product is not None,
        AcceptanceCheck.NO_FABRICATED_QUANTITY: source is not None and source.gtin is None,
        AcceptanceCheck.COVERAGE_DECLARED: good.stores[0].coverage == CoverageLevel.OFFERS_ONLY,
        AcceptanceCheck.PARSER_HEALTH: parser_health.accepted,
        AcceptanceCheck.SCHEMA_FINGERPRINT: bool(good_snapshot.schema_fingerprint),
        AcceptanceCheck.ATOMIC_PROMOTION: good.promoted and not broken.promoted,
        AcceptanceCheck.LAST_KNOWN_GOOD: broken.active_snapshot_id == good.snapshot_id,
        AcceptanceCheck.OFFLINE_REPLAY: replay.products_parsed == 1,
        AcceptanceCheck.ZERO_NETWORK_REPLAY: replay.network_requests == 0,
        AcceptanceCheck.SIMULATED_BREAK: broken.status == ConnectorStatus.BROKEN,
        AcceptanceCheck.CONNECTOR_LOCAL_REPAIR: repaired.promoted,
        AcceptanceCheck.GENERIC_API: offers_response.status_code == 200,
        AcceptanceCheck.OWN_PROVIDER: bool(offers),
        AcceptanceCheck.OFFLINE_TESTS: offline_connector.fetch_calls == 0,
        AcceptanceCheck.OFFERS_FETCH: good_connector.offers_fetch_calls == 1,
        AcceptanceCheck.PROMOTION_SEMANTICS: promotion is not None,
        AcceptanceCheck.MEMBER_PRICE_SEPARATION: (
            source is not None and source.member_price != source.regular_price
        ),
    }
    assert all(evidence.values())
    contract = ConnectorAcceptanceContract(
        chain=Chain.COOP,
        declared_coverage=CoverageLevel.OFFERS_ONLY,
        source_supports_promotions=True,
        source_supports_member_prices=True,
    )
    acceptance = contract.assess(
        {check for check, proven in evidence.items() if proven},
        parser_health=parser_health,
    )
    assert acceptance.contract_passed is True
    assert acceptance.implementation_eligible is True
    assert acceptance.missing_required == ()

    engine.dispose()
