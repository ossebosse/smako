from __future__ import annotations

from grocery_data.app.connectors.coop.client import CoopClient
from grocery_data.app.connectors.coop.parser import CoopParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    SourcePolicy,
    SourceStore,
)


class CoopConnector:
    """Coop public physical-store offers; broad online catalog remains unproven."""

    chain = Chain.COOP
    coverage = CoverageLevel.OFFERS_ONLY
    connector_version = "coop-v1"
    parser_version = "coop-parser-v5"
    source_policy = SourcePolicy.ALLOW

    def __init__(
        self,
        *,
        client: CoopClient | None = None,
        parser: CoopParser | None = None,
    ) -> None:
        self.client = client or CoopClient()
        self.parser = parser or CoopParser()
        self.parser_version = self.parser.parser_version

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        return await self.client.fetch_stores(area)

    async def fetch_physical_stores(self, area: GeographicArea) -> RawBatch:
        return await self.client.fetch_physical_stores(area)

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        return self.parser.parse_stores(raw, references, area)

    def parse_physical_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        return self.parser.parse_physical_stores(raw, references, area)

    def catalog_eligible(self, store: SourceStore) -> bool:
        return (
            store.coverage == CoverageLevel.OFFERS_ONLY
            and bool(store.source_fields.get("store_page_path"))
            and store.source_fields.get("disable_store_offers_flyer") is not True
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
        return await self.client.fetch_offers(store)

    async def aclose(self) -> None:
        await self.client.aclose()


class CoopRowApprovedOfferConnector(CoopConnector):
    """Explicit single-store partial contract over retained, actual raw fetches.

    Uses the normal collector/OWN repository; never an online price context.
    No networking during replay, no observation-time rewriting.
    """
    def __init__(self, *, store, locator, offers):
        self.parser = CoopParser()
        self.parser_version = self.parser.parser_version
        self.store, self.locator, self.offers = store, locator, offers
        self.row_acceptance = None

    async def fetch_stores(self, area):
        return self.locator

    def parse_stores(self, raw, references, area):
        return [self.store]

    async def fetch_catalog(self, store):
        return self.offers

    def parse_catalog(self, raw, references, store):
        from grocery_data.app.services.offer_rows import qualify_rows
        self.extracted = self.parser.parse_catalog(raw, references, store)
        result, self.row_acceptance = qualify_rows(self.extracted, store=store,
            observed_at=max(d.fetched_at for d in raw.documents))
        return result

    async def aclose(self):
        pass
