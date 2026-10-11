from __future__ import annotations

import os
from typing import ClassVar

from grocery_data.app.connectors.hemkop.client import (
    HemkopClient,
    HemkopOperatorCrawlPolicy,
    reconcile_saved_catalog_completion,
)
from grocery_data.app.connectors.hemkop.parser import HemkopParser
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


class HemkopConnector:
    """Separate Hemköp adapter with bounded, full-live and replay modes.

    Registry creation is always bounded and environment-independent. Live full
    collection is available only through :meth:`for_full_collection` after the
    accepted coverage contract and still requires REVIEW opt-in plus an exact
    allowlist; replay uses an inert captured-identity transport.
    """

    chain = Chain.HEMKOP
    coverage = CoverageLevel.PARTIAL_CATALOG
    technical_capability = SourceTechnicalCapability.LIKELY_FULL_ONLINE_CATALOG
    source_policy = SourcePolicy.REVIEW
    connector_version = "hemkop-v1"
    parser_version = "hemkop-parser-v1"
    # The first exact Malmö traversal observed 9,002 unique products. Keep a
    # conservative chain-local floor so a structurally complete but collapsed
    # future response cannot be promoted or accepted during offline replay.
    minimum_full_catalog_products = 8_000
    # Karhögstorg is a materially smaller, independently scoped online
    # assortment. The first exact 2026-08-23 traversal observed 6,068 unique
    # IDs plus one unresolved pagination-shift row. A 5,000 floor preserves a
    # substantial collapse guard without importing Malmö's larger baseline.
    verified_store_minimum_products: ClassVar[dict[str, int]] = {
        "4123": 5_000,
        "4224": 4_500,
        # Repeated exact 2026-10-10/11 traversals: Värnhem 7,066–7,171,
        # Elinegård 6,459–6,475 unique products; all 20 categories reconcile.
        # Store-local collapse floors; full pagination and price gates remain.
        "4199": 6_300,
        "4212": 5_800,
    }
    # Live category proof verified that the public backend honours 100 rows.
    # Keep bounded discovery at 30, but avoid tripling a REVIEW-approved full
    # traversal's request volume while the 0.1 req/s policy remains unchanged.
    full_catalog_page_size = 100

    def __init__(
        self,
        *,
        client: HemkopClient | None = None,
        parser: HemkopParser | None = None,
        coverage: CoverageLevel = CoverageLevel.PARTIAL_CATALOG,
        minimum_full_catalog_products: int | None = None,
    ) -> None:
        if coverage not in {
            CoverageLevel.PARTIAL_CATALOG,
            CoverageLevel.FULL_ONLINE_CATALOG,
        }:
            raise ValueError("Hemköp supports PARTIAL or FULL_ONLINE catalog mode")
        self.coverage = coverage
        minimum = (
            type(self).minimum_full_catalog_products
            if minimum_full_catalog_products is None
            else minimum_full_catalog_products
        )
        if isinstance(minimum, bool) or minimum <= 0:
            raise ValueError("minimum_full_catalog_products must be a positive integer")
        self.minimum_full_catalog_products = minimum
        self.client = client or HemkopClient()
        self.parser = parser or HemkopParser()
        self.parser_version = self.parser.parser_version

    def collection_policy_audit(self) -> SourceCollectionAudit:
        full_authority = (
            self.coverage is CoverageLevel.FULL_ONLINE_CATALOG
            and getattr(self.client, "allow_full_crawl", False) is True
            and getattr(self.client, "max_categories", 1) is None
            and getattr(self.client, "max_pages_per_category", 1) is None
        )
        return SourceCollectionAudit(
            source_policy=self.source_policy,
            operator_opt_in=full_authority,
            store_allowlist=tuple(sorted(getattr(self.client, "allowed_store_ids", ()))),
            requests_per_second=getattr(self.client, "requests_per_second", None),
            max_concurrency=getattr(self.client, "max_concurrency", None),
        )

    @classmethod
    def for_bounded_discovery(
        cls,
        *,
        page_size: int = 30,
        parser: HemkopParser | None = None,
    ) -> HemkopConnector:
        """Build a one-category/one-page adapter independent of crawl env."""

        return cls(
            client=HemkopClient(
                page_size=page_size,
                max_categories=1,
                max_pages_per_category=1,
                allow_full_crawl=False,
                allowed_store_ids=(),
            ),
            parser=parser,
            coverage=CoverageLevel.PARTIAL_CATALOG,
        )

    @classmethod
    def for_full_collection(
        cls,
        *,
        client: HemkopClient | None = None,
        parser: HemkopParser | None = None,
    ) -> HemkopConnector:
        """Build the explicitly opted-in complete online-store adapter."""

        full_client = client or HemkopClient(
            page_size=cls.full_catalog_page_size,
            max_categories=None,
            max_pages_per_category=None,
        )
        if (
            full_client.allow_full_crawl is not True
            or full_client.max_categories is not None
            or full_client.max_pages_per_category is not None
        ):
            raise ValueError(
                "Hemköp full collection requires an unlimited explicitly allowed client"
            )
        if not full_client.allowed_store_ids:
            raise ValueError("Hemköp full collection requires an exact store allowlist")
        return cls(
            client=full_client,
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        )

    @classmethod
    def for_exact_full_collection(
        cls,
        store_external_id: str,
        *,
        policy: HemkopOperatorCrawlPolicy | None = None,
        parser: HemkopParser | None = None,
    ) -> HemkopConnector:
        """Build one independently scoped transport after exact REVIEW consent.

        The environment allowlist is checked before the client is constructed.
        The resulting connector contains exactly one store even when the
        operator has opted in to several stores for a daily multi-context run.
        """

        # Re-read the current authority at transport construction. Registered
        # municipal operations derive the same exact IDs as the planner from
        # verified inventory; an injected policy can only narrow that set.
        from grocery_data.app.services.municipal_rollout import hemkop_policy

        configured_policy = HemkopOperatorCrawlPolicy.from_environment()
        configured_policy = hemkop_policy(
            os.getenv("REFRESH_CITY", "Lund"), configured_policy
        )
        target = configured_policy.require(store_external_id)
        if policy is not None:
            policy.require(target)
        connector = cls.for_full_collection(
            client=HemkopClient(
                page_size=cls.full_catalog_page_size,
                max_categories=None,
                max_pages_per_category=None,
                allow_full_crawl=True,
                allowed_store_ids=(target,),
            ),
            parser=parser,
        )
        connector.minimum_full_catalog_products = cls.verified_store_minimum_products.get(
            target,
            cls.minimum_full_catalog_products,
        )
        return connector

    @classmethod
    def for_replay(
        cls,
        *,
        store_external_ids: tuple[str, ...],
        parser: HemkopParser | None = None,
    ) -> HemkopConnector:
        """Build a full parser with inert bounded transport and no live authority."""

        if not store_external_ids:
            raise ValueError("Hemköp replay requires captured store identities")
        captured_ids = tuple(dict.fromkeys(store_external_ids))
        scoped_minimum = (
            cls.verified_store_minimum_products.get(
                captured_ids[0],
                cls.minimum_full_catalog_products,
            )
            if len(captured_ids) == 1
            else cls.minimum_full_catalog_products
        )
        return cls(
            client=HemkopClient(
                page_size=1,
                max_categories=1,
                max_pages_per_category=1,
                allow_full_crawl=False,
                allowed_store_ids=captured_ids,
            ),
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
            minimum_full_catalog_products=scoped_minimum,
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
        selected: list[SourceStore] = []
        for store in stores:
            if not self.client.store_allowed(store.external_id):
                continue
            if self.coverage is CoverageLevel.PARTIAL_CATALOG:
                store = store.model_copy(update={"coverage": CoverageLevel.PARTIAL_CATALOG})
            selected.append(store)
        return selected

    def catalog_eligible(self, store: SourceStore) -> bool:
        return (
            store.online_shopping is True
            and store.coverage is self.coverage
            and store.price_context_type is not None
            and store.source_fields.get("price_context_activation_required") is True
            and self.client.store_allowed(store.external_id)
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        return await self.client.fetch_catalog(store)

    async def fetch_category(
        self,
        store: SourceStore,
        category_path: str,
        *,
        max_pages: int | None = 1,
    ) -> RawBatch:
        """Expose the guarded one-category proof without broadening the protocol."""

        return await self.client.fetch_category(
            store,
            category_path,
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
        """Rebuild traversal evidence after a connector-local offline repair.

        Saved response bodies remain immutable. Only the derived completion
        evidence is recomputed, with the same exact store/page/duplicate gates
        used by a live Hemköp traversal.
        """

        # Already-valid evidence needs no repair and remains authoritative.
        # Older synthetic and legacy captures may also predate a saved complete
        # category tree. Never guess a tree from product-page labels.
        if (
            raw.catalog_completion is None
            or raw.catalog_completion.is_full_traversal
            or not any(document.kind == "category_tree" for document in raw.documents)
        ):
            return raw
        completion = reconcile_saved_catalog_completion(
            raw,
            expected_store_id=store.external_id,
        )
        return raw.model_copy(update={"catalog_completion": completion})

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        del store
        # Structured potentialPromotions are embedded in catalog rows.
        return RawBatch(chain=self.chain, documents=())

    async def aclose(self) -> None:
        await self.client.aclose()
