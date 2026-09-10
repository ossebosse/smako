from __future__ import annotations

from grocery_data.app.connectors.ica.client import IcaClient
from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    SourcePolicy,
    SourceStore,
)


class IcaConnector:
    chain = Chain.ICA
    coverage = CoverageLevel.OFFERS_ONLY
    connector_version = "ica-v2"
    parser_version = "ica-parser-v3"
    source_policy = SourcePolicy.ALLOW

    def __init__(self, *, client: IcaClient | None = None, parser: IcaParser | None = None) -> None:
        self.client = client or IcaClient()
        self.parser = parser or IcaParser()
        self.parser_version = self.parser.parser_version

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        return await self.client.fetch_stores(area)

    async def fetch_physical_stores(self, area: GeographicArea) -> RawBatch:
        return await self.client.fetch_physical_stores(area)

    def parse_stores(
        self, raw: RawBatch, references: list[str], area: GeographicArea
    ) -> list[SourceStore]:
        return self.parser.parse_stores(raw, references, area)

    def parse_physical_stores(
        self, raw: RawBatch, references: list[str], area: GeographicArea
    ) -> list[SourceStore]:
        return self.parser.parse_physical_stores(raw, references, area)

    def catalog_eligible(self, store: SourceStore) -> bool:
        return store.coverage == CoverageLevel.OFFERS_ONLY and bool(
            store.source_fields.get("offers_url")
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        return await self.client.fetch_catalog(store)

    def parse_catalog(
        self, raw: RawBatch, references: list[str], store: SourceStore
    ) -> ProductParseResult:
        return self.parser.parse_catalog(raw, references, store)

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        # The offers page is already the connector's declared data surface.
        return RawBatch(chain=Chain.ICA, documents=())

    async def aclose(self) -> None:
        await self.client.aclose()
