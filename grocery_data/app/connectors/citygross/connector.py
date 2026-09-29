from __future__ import annotations

from grocery_data.app.connectors.citygross.client import CityGrossClient
from grocery_data.app.connectors.citygross.parser import CityGrossParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
    SourceTechnicalCapability,
)


class CityGrossConnector:
    """City Gross adapter with an explicit bounded or complete-online mode.

    The ordinary constructor remains a one-page ``PARTIAL_CATALOG`` adapter.
    A complete traversal is created deliberately through
    :meth:`for_full_collection`; offline replay uses :meth:`for_replay` and
    therefore never needs live crawl authority.
    """

    chain = Chain.CITY_GROSS
    coverage = CoverageLevel.PARTIAL_CATALOG
    technical_capability = SourceTechnicalCapability.LIKELY_FULL_ONLINE_CATALOG
    source_policy = SourcePolicy.REVIEW
    connector_version = "citygross-v1"
    parser_version = "citygross-parser-v4"
    minimum_full_catalog_products = 10_000

    def __init__(
        self,
        *,
        client: CityGrossClient | None = None,
        parser: CityGrossParser | None = None,
        coverage: CoverageLevel = CoverageLevel.PARTIAL_CATALOG,
    ) -> None:
        if coverage not in {
            CoverageLevel.PARTIAL_CATALOG,
            CoverageLevel.FULL_ONLINE_CATALOG,
        }:
            raise ValueError("City Gross supports PARTIAL or FULL_ONLINE catalog mode")
        self.coverage = coverage
        self.client = client or CityGrossClient()
        self.parser = parser or CityGrossParser()
        self.parser_version = self.parser.parser_version

    def collection_policy_audit(self) -> SourceCollectionAudit:
        """Return non-secret REVIEW evidence for persistence and operator logs."""

        full_authority = (
            self.coverage is CoverageLevel.FULL_ONLINE_CATALOG
            and getattr(self.client, "allow_full_crawl", False) is True
            and getattr(self.client, "max_pages", 1) is None
        )
        allowed_store_ids = getattr(self.client, "allowed_store_ids", ())
        return SourceCollectionAudit(
            source_policy=self.source_policy,
            operator_opt_in=full_authority,
            store_allowlist=tuple(sorted(allowed_store_ids)),
            requests_per_second=getattr(self.client, "requests_per_second", None),
            max_concurrency=getattr(self.client, "max_concurrency", None),
        )

    @classmethod
    def for_bounded_discovery(
        cls,
        *,
        page_size: int = 100,
        parser: CityGrossParser | None = None,
    ) -> CityGrossConnector:
        """Create an inert one-page adapter independent of operator crawl env."""

        return cls(
            client=CityGrossClient(
                page_size=page_size,
                max_pages=1,
                allow_full_crawl=False,
            ),
            parser=parser,
        )

    @classmethod
    def for_full_collection(
        cls,
        *,
        client: CityGrossClient | None = None,
        parser: CityGrossParser | None = None,
    ) -> CityGrossConnector:
        """Create the explicitly opted-in live full-online connector."""

        full_client = client or CityGrossClient(page_size=100, max_pages=None)
        if full_client.max_pages is not None or full_client.allow_full_crawl is not True:
            raise ValueError(
                "City Gross full collection requires an unlimited explicitly allowed client"
            )
        if not full_client.allowed_store_ids:
            raise ValueError("City Gross full collection requires an exact store allowlist")
        return cls(
            client=full_client,
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        )

    @classmethod
    def for_replay(
        cls,
        *,
        store_external_ids: tuple[str, ...],
        parser: CityGrossParser | None = None,
    ) -> CityGrossConnector:
        """Create a parser-only full connector with a bounded inert transport.

        Database replay never calls transport methods.  Keeping this client in
        one-page REVIEW mode proves that replay cannot accidentally inherit
        live crawl permission while still preserving the exact source context
        allowlist used by the captured snapshot.
        """

        if not store_external_ids:
            raise ValueError("City Gross replay requires captured store identities")
        replay_client = CityGrossClient(
            page_size=1,
            max_pages=1,
            allow_full_crawl=False,
            allowed_store_ids=store_external_ids,
        )
        return cls(
            client=replay_client,
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        )

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        del area
        return await self.client.fetch_stores()

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        stores = self.parser.parse_stores(raw, references, area)
        if self.coverage != CoverageLevel.FULL_ONLINE_CATALOG:
            return stores
        upgraded: list[SourceStore] = []
        for store in stores:
            verified = store.source_fields.get("price_context_verified") is True
            if verified and self.client.store_allowed(store.external_id):
                store = store.model_copy(update={"coverage": CoverageLevel.FULL_ONLINE_CATALOG})
            upgraded.append(store)
        return upgraded

    def catalog_eligible(self, store: SourceStore) -> bool:
        store_allowed = getattr(self.client, "store_allowed", lambda _store_id: True)
        return (
            store.online_shopping is True
            and store.coverage == self.coverage
            and store.source_fields.get("price_context_verified") is True
            and store_allowed(store.external_id)
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        return await self.client.fetch_catalog(store)

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        return self.parser.parse_catalog(raw, references, store)

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        del store
        # Structured promotions are embedded in each Loop54 product row.
        return RawBatch(chain=self.chain, documents=())

    async def aclose(self) -> None:
        await self.client.aclose()
