from __future__ import annotations

from grocery_data.app.connectors.lidl.client import LidlClient
from grocery_data.app.connectors.lidl.models import reviewed_lidl_schema_diff
from grocery_data.app.connectors.lidl.parser import LidlParser
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
from grocery_data.app.monitoring.schema_fingerprint import SchemaDiff


class LidlConnector:
    """Lidl public regional offer surface; never a full basket catalog."""

    chain = Chain.LIDL
    coverage = CoverageLevel.OFFERS_ONLY
    source_policy = SourcePolicy.ALLOW
    technical_capability = SourceTechnicalCapability.OFFERS_ONLY
    connector_version = "lidl-v1"
    parser_version = "lidl-parser-v4"

    @staticmethod
    def review_schema_diff(diff: SchemaDiff) -> SchemaDiff:
        return reviewed_lidl_schema_diff(diff)

    def __init__(
        self,
        *,
        client: LidlClient | None = None,
        parser: LidlParser | None = None,
    ) -> None:
        self.client = client or LidlClient()
        self.parser = parser or LidlParser()
        self.connector_version = getattr(self.client, "connector_version", self.connector_version)
        self.parser_version = self.parser.parser_version

    @classmethod
    def for_bounded_discovery(cls, *, page_size: int = 5) -> LidlConnector:
        return cls(client=LidlClient(page_size=page_size, max_pages=1))

    def collection_policy_audit(self) -> SourceCollectionAudit:
        return SourceCollectionAudit(
            source_policy=self.source_policy,
            operator_opt_in=False,
            requests_per_second=self.client.requests_per_second,
            max_concurrency=self.client.max_concurrency,
        )

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        return await self.client.fetch_stores(area)

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        return self.parser.parse_stores(raw, references, area)

    def catalog_eligible(self, store: SourceStore) -> bool:
        return (
            store.external_id == LidlClient.public_offer_context_id
            and store.coverage == CoverageLevel.OFFERS_ONLY
            and store.source_fields.get("store_price_verified") is False
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
