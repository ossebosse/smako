from __future__ import annotations

from typing import ClassVar

from grocery_data.app.connectors.coop.models import CoopSchemaError
from grocery_data.app.connectors.coop.online_catalog_client import (
    COOP_FULFILLMENT_MAPPING_KIND,
    CoopOnlineCatalogClient,
    CoopOnlineOperatorCrawlPolicy,
    reconcile_saved_catalog_completion,
)
from grocery_data.app.connectors.coop.online_catalog_parser import CoopOnlineCatalogParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    PriceContextType,
    ProductParseResult,
    RawBatch,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
    SourceTechnicalCapability,
)


class CoopOnlineCatalogConnector:
    """Separate adapter for Coop's regional online fulfillment catalogue.

    The existing :class:`CoopConnector` remains the physical-store offer
    source. This connector owns online production-unit contexts only; a pickup
    point is evidence for a many-to-one relationship and never becomes a
    duplicate price context or a physical-shelf-price claim.
    """

    chain = Chain.COOP
    coverage = CoverageLevel.PARTIAL_CATALOG
    technical_capability = SourceTechnicalCapability.LIKELY_FULL_ONLINE_CATALOG
    source_policy = SourcePolicy.REVIEW
    connector_version = CoopOnlineCatalogClient.connector_version
    parser_version = CoopOnlineCatalogParser.parser_version
    # The first exact 730400 traversal on 2026-08-25 produced 11,175 unique
    # priced products.  Keep an absolute floor as a first-run/cold-baseline
    # collapse guard; subsequent runs are additionally compared with their
    # promoted baseline by the shared health assessment.
    minimum_full_catalog_products = 8_000
    full_catalog_page_size = 48
    _VERIFIED_CONTEXT_LABELS: ClassVar[dict[str, str]] = {
        "730400": "Coop Online Syd",
    }

    def __init__(
        self,
        *,
        client: CoopOnlineCatalogClient | None = None,
        parser: CoopOnlineCatalogParser | None = None,
        coverage: CoverageLevel = CoverageLevel.PARTIAL_CATALOG,
    ) -> None:
        if coverage not in {
            CoverageLevel.PARTIAL_CATALOG,
            CoverageLevel.FULL_ONLINE_CATALOG,
        }:
            raise ValueError("Coop online supports PARTIAL or FULL_ONLINE catalog mode")
        self.coverage = coverage
        self.client = client or CoopOnlineCatalogClient()
        self.parser = parser or CoopOnlineCatalogParser()
        self.parser_version = self.parser.parser_version

    def collection_policy_audit(self) -> SourceCollectionAudit:
        full_authority = (
            self.coverage is CoverageLevel.FULL_ONLINE_CATALOG
            and self.client.allow_full_crawl is True
            and self.client.max_categories is None
            and self.client.max_pages_per_category is None
        )
        return SourceCollectionAudit(
            source_policy=self.source_policy,
            operator_opt_in=full_authority,
            store_allowlist=tuple(sorted(self.client.allowed_context_ids)),
            requests_per_second=self.client.requests_per_second,
            max_concurrency=self.client.max_concurrency,
        )

    @classmethod
    def for_bounded_discovery(
        cls,
        context_id: str,
        *,
        parser: CoopOnlineCatalogParser | None = None,
    ) -> CoopOnlineCatalogConnector:
        normalized = context_id.strip()
        if not normalized:
            raise ValueError("Coop online bounded discovery requires a context ID")
        return cls(
            client=CoopOnlineCatalogClient(
                category_page_size=cls.full_catalog_page_size,
                search_page_size=24,
                max_categories=1,
                max_pages_per_category=1,
                allow_full_crawl=False,
                allowed_context_ids=(normalized,),
            ),
            parser=parser,
            coverage=CoverageLevel.PARTIAL_CATALOG,
        )

    @classmethod
    def for_full_collection(
        cls,
        *,
        client: CoopOnlineCatalogClient | None = None,
        parser: CoopOnlineCatalogParser | None = None,
    ) -> CoopOnlineCatalogConnector:
        full_client = client or CoopOnlineCatalogClient(
            category_page_size=cls.full_catalog_page_size,
            search_page_size=24,
            max_categories=None,
            max_pages_per_category=None,
        )
        if (
            full_client.allow_full_crawl is not True
            or full_client.max_categories is not None
            or full_client.max_pages_per_category is not None
        ):
            raise ValueError(
                "Coop full collection requires an unlimited explicitly allowed client"
            )
        if not full_client.allowed_context_ids:
            raise ValueError("Coop full collection requires an exact online-context allowlist")
        return cls(
            client=full_client,
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        )

    @classmethod
    def for_exact_full_collection(
        cls,
        context_id: str,
        *,
        policy: CoopOnlineOperatorCrawlPolicy | None = None,
        parser: CoopOnlineCatalogParser | None = None,
    ) -> CoopOnlineCatalogConnector:
        configured_policy = CoopOnlineOperatorCrawlPolicy.from_environment()
        target = configured_policy.require(context_id)
        if policy is not None:
            policy.require(target)
        return cls.for_full_collection(
            client=CoopOnlineCatalogClient(
                category_page_size=cls.full_catalog_page_size,
                search_page_size=24,
                max_categories=None,
                max_pages_per_category=None,
                allow_full_crawl=True,
                allowed_context_ids=(target,),
            ),
            parser=parser,
        )

    @classmethod
    def for_replay(
        cls,
        *,
        context_ids: tuple[str, ...],
        parser: CoopOnlineCatalogParser | None = None,
    ) -> CoopOnlineCatalogConnector:
        if not context_ids:
            raise ValueError("Coop online replay requires captured context identities")
        captured = tuple(dict.fromkeys(value.strip() for value in context_ids if value.strip()))
        if not captured:
            raise ValueError("Coop online replay requires non-blank context identities")
        return cls(
            client=CoopOnlineCatalogClient(
                category_page_size=1,
                search_page_size=1,
                max_categories=1,
                max_pages_per_category=1,
                allow_full_crawl=False,
                allowed_context_ids=captured,
            ),
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        )

    @classmethod
    def source_store(
        cls,
        context_id: str,
        *,
        coverage: CoverageLevel,
        raw_reference: str,
    ) -> SourceStore:
        """Build one neutral online context, never a physical-store identity."""

        normalized = context_id.strip()
        if not normalized:
            raise ValueError("Coop online context ID must not be blank")
        return SourceStore(
            chain=Chain.COOP,
            external_id=normalized,
            name=cls._VERIFIED_CONTEXT_LABELS.get(normalized, f"Coop Online {normalized}"),
            online_shopping=True,
            coverage=coverage,
            price_context_type=PriceContextType.ONLINE_FULFILLMENT,
            physical_store_external_id=None,
            raw_reference=raw_reference,
            source_fields={
                "customer_group": "CUSTOMER_PRIVATE",
                "customer_group_semantics": "private_b2c_not_membership",
                "price_context_verified": True,
                "price_semantics": "online_price",
                "scope": "regional_online_fulfillment",
            },
        )

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        # This is a bounded pickup search. It does not crawl the product
        # catalogue and does not turn pickup IDs into catalogue context IDs.
        return await self.client.fetch_point_of_services(area.city)

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        del area
        pairs = raw.with_references(references)
        contexts: dict[str, str] = {}
        for document, reference in pairs:
            if document.kind != COOP_FULFILLMENT_MAPPING_KIND:
                continue
            payload = document.json_payload()
            if not isinstance(payload, dict) or not isinstance(payload.get("stores"), list):
                raise CoopSchemaError("Coop pickup discovery lacks a stores array")
            for row in payload["stores"]:
                if not isinstance(row, dict):
                    raise CoopSchemaError("Coop pickup discovery contains a non-object row")
                # `name` is the pickup point; `storeId` is the distinct online
                # assortment/price context. Keep those namespaces separate.
                pickup_id = str(row.get("name") or "").strip()
                context_id = str(row.get("storeId") or "").strip()
                display_name = str(row.get("displayName") or "").strip()
                if not pickup_id or not context_id or not display_name:
                    raise CoopSchemaError("Coop pickup row lacks point/context identity")
                if context_id in self.client.allowed_context_ids:
                    contexts.setdefault(context_id, reference)
        if not contexts:
            raise CoopSchemaError("Coop pickup discovery found no allowlisted online context")
        return [
            self.source_store(
                context_id,
                coverage=self.coverage,
                raw_reference=f"{reference}#storeId={context_id}",
            )
            for context_id, reference in sorted(contexts.items())
        ]

    def catalog_eligible(self, store: SourceStore) -> bool:
        return (
            store.chain is Chain.COOP
            and store.online_shopping is True
            and store.coverage is self.coverage
            and store.price_context_type is PriceContextType.ONLINE_FULFILLMENT
            and store.physical_store_external_id is None
            and store.source_fields.get("price_context_verified") is True
            and self.client.context_allowed(store.external_id)
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        if not self.catalog_eligible(store):
            raise CoopSchemaError("Coop online store is not eligible for this connector")
        return await self.client.fetch_catalog(store.external_id)

    async def fetch_search(
        self,
        store: SourceStore,
        query: str,
        *,
        max_pages: int | None = 1,
    ) -> RawBatch:
        if not self.catalog_eligible(store):
            raise CoopSchemaError("Coop online store is not eligible for search")
        return await self.client.fetch_search(
            store.external_id,
            query,
            max_pages=max_pages,
        )

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        return self.parser.parse_catalog(raw, references, store)

    def reconcile_replay_catalog_completion(
        self,
        raw: RawBatch,
        store: SourceStore,
    ) -> RawBatch:
        if raw.catalog_completion is not None and raw.catalog_completion.is_full_traversal:
            return raw
        completion = reconcile_saved_catalog_completion(
            raw,
            expected_context_id=store.external_id,
        )
        return raw.model_copy(update={"catalog_completion": completion})

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        del store
        # Online promotions are already embedded in product rows. The existing
        # CoopConnector remains the physical-store offers source.
        return RawBatch(chain=self.chain, documents=())

    async def aclose(self) -> None:
        await self.client.aclose()
