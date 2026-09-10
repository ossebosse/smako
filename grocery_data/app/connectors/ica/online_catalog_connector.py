from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from grocery_data.app.connectors.ica.online_catalog_client import (
    IcaOnlineCatalogClient,
    IcaOnlineOperatorCrawlPolicy,
    IcaOnlineSourcePolicyError,
)
from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_CATEGORY_TREE_KIND,
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    ICA_STORE_CONTEXT_KIND,
    ICA_STORE_MAPPING_KIND,
    IcaCategoryTree,
    IcaOnlineSchemaError,
    purchase_semantic_fingerprint,
)
from grocery_data.app.connectors.ica.online_catalog_parser import IcaOnlineCatalogParser
from grocery_data.app.connectors.ica.online_catalog_transport import (
    IcaOnlineCollectionTransport,
)
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    CoverageLevel,
    GeographicArea,
    ParseFailure,
    PriceContextType,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
    SourceTechnicalCapability,
)
from grocery_data.app.domain.raw import TransportMetrics


class IcaOnlineCatalogConnector:
    """Production boundary for ICA's current region-scoped online catalogue.

    This connector is deliberately separate from :class:`IcaConnector`, which
    remains the accepted physical-store offers feed.  A region UUID is an
    online price context and a numeric retailer route is only exact relation
    evidence; neither identity is silently promoted to physical shelf price.
    """

    chain = Chain.ICA
    coverage = CoverageLevel.PARTIAL_CATALOG
    technical_capability = SourceTechnicalCapability.LIKELY_FULL_ONLINE_CATALOG
    source_policy = SourcePolicy.REVIEW
    connector_version = IcaOnlineCatalogClient.connector_version
    parser_version = IcaOnlineCatalogParser.parser_version
    # This is a collapse guard, not a claim about the as-yet uncompleted live
    # Gunnesbo traversal.  Promotion still requires exact source completion,
    # parser health and all shared full-catalog quality gates.
    minimum_full_catalog_products = 5_000

    _VERIFIED_CONTEXTS: ClassVar[dict[str, dict[str, str]]] = {
        "92198f17-b02f-4fae-ad41-228bcc725420": {
            "retailer_region_id": "1088004",
            "name": "ICA Online Gunnesbo",
            "city": "Lund",
            # Exact current public category route observed in the Gunnesbo
            # frontend. SSR navigation nodes need not expose productCount, so
            # a canary must not guess its target by a count heuristic.
            "canary_category_id": "ea243faf-2eca-47d7-af07-1dc61dd7693a",
        },
    }

    def __init__(
        self,
        *,
        client: IcaOnlineCollectionTransport | None,
        context_mappings: Mapping[str, str | None],
        parser: IcaOnlineCatalogParser | None = None,
        coverage: CoverageLevel = CoverageLevel.PARTIAL_CATALOG,
        replay_only: bool = False,
    ) -> None:
        if coverage not in {
            CoverageLevel.PARTIAL_CATALOG,
            CoverageLevel.FULL_ONLINE_CATALOG,
        }:
            raise ValueError("ICA online supports PARTIAL or FULL_ONLINE catalog mode")
        if not context_mappings:
            raise ValueError("ICA online connector requires exact context identities")
        mappings = {
            self._canonical_region_id(region_id): (
                str(retailer_id).strip() if retailer_id is not None else None
            )
            for region_id, retailer_id in context_mappings.items()
        }
        if any(not region_id for region_id in mappings):
            raise ValueError("ICA online context ID must not be blank")
        if not replay_only and client is None:
            raise ValueError("live ICA online connector requires a client")
        if replay_only and client is not None:
            raise ValueError("ICA replay connector must not own a network client")
        self.coverage = coverage
        self.client = client
        self.context_mappings = mappings
        self.replay_only = replay_only
        self.parser = parser or IcaOnlineCatalogParser()
        self.parser_version = self.parser.parser_version
        self._context_cache: dict[str, RawBatch] = {}

    @staticmethod
    def _canonical_region_id(value: object) -> str:
        text = str(value).strip().casefold()
        try:
            parsed = UUID(text)
        except (AttributeError, ValueError) as exc:
            raise ValueError("ICA online context ID must be a UUID") from exc
        if str(parsed) != text:
            raise ValueError("ICA online context ID must use canonical UUID form")
        return text

    @classmethod
    def _resolve_verified_context(cls, value: str) -> tuple[str, str]:
        normalized = value.strip().casefold()
        direct = cls._VERIFIED_CONTEXTS.get(normalized)
        if direct is not None:
            return normalized, direct["retailer_region_id"]
        matches = [
            (region_id, evidence["retailer_region_id"])
            for region_id, evidence in cls._VERIFIED_CONTEXTS.items()
            if evidence["retailer_region_id"] == value.strip()
        ]
        if len(matches) != 1:
            raise IcaOnlineSourcePolicyError(
                "ICA canary requires an exact verified region or retailer route"
            )
        return matches[0]

    @classmethod
    def for_bounded_discovery(
        cls,
        store_or_context: str,
        *,
        parser: IcaOnlineCatalogParser | None = None,
    ) -> IcaOnlineCatalogConnector:
        """Build one context/page/five-product-batch canary.

        Five UUIDs is an intentionally tiny bounded diagnostic request.  It is
        not represented as the browser-verified production batch size and can
        therefore never grant full-crawl authority.
        """

        region_id, retailer_id = cls._resolve_verified_context(store_or_context)
        client = IcaOnlineCatalogClient(
            context_mappings={region_id: retailer_id},
            max_categories=1,
            max_pages_per_category=1,
            max_batches_per_page=1,
            product_batch_size=5,
            allow_full_crawl=False,
            allowed_context_ids=(region_id,),
            max_concurrency=1,
        )
        return cls(
            client=client,
            context_mappings={region_id: retailer_id},
            parser=parser,
            coverage=CoverageLevel.PARTIAL_CATALOG,
        )

    @classmethod
    def for_bounded_browser_discovery(
        cls,
        store_or_context: str,
        *,
        parser: IcaOnlineCatalogParser | None = None,
    ) -> IcaOnlineCatalogConnector:
        """Build the same bounded canary over a fresh anonymous browser."""

        from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
            IcaOnlineBrowserTransport,
        )

        region_id, retailer_id = cls._resolve_verified_context(store_or_context)
        client = IcaOnlineBrowserTransport(
            context_mappings={region_id: retailer_id},
            max_categories=1,
            max_pages_per_category=1,
            max_batches_per_page=1,
            product_batch_size=5,
            allow_full_crawl=False,
            allowed_context_ids=(region_id,),
            max_concurrency=1,
        )
        return cls(
            client=client,
            context_mappings={region_id: retailer_id},
            parser=parser,
            coverage=CoverageLevel.PARTIAL_CATALOG,
        )

    @classmethod
    def for_browser_category_proof(
        cls,
        store_or_context: str,
        *,
        parser: IcaOnlineCatalogParser | None = None,
    ) -> IcaOnlineCatalogConnector:
        """Build one complete-category proof with separate REVIEW authority."""

        from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
            IcaOnlineBrowserTransport,
        )

        region_id, retailer_id = cls._resolve_verified_context(store_or_context)
        policy = IcaOnlineOperatorCrawlPolicy.from_environment()
        if region_id not in policy.allowed_context_ids:
            raise IcaOnlineSourcePolicyError(
                "ICA category proof context is outside ICA_ONLINE_CONTEXT_IDS"
            )
        client = IcaOnlineBrowserTransport(
            context_mappings={region_id: retailer_id},
            max_categories=1,
            max_pages_per_category=1,
            max_batches_per_page=1,
            # Category proof observes ICA's own frontend PUT arrays and derives
            # their actual size. Only a later full crawl consumes the explicit
            # ICA_PRODUCT_BATCH_SIZE gate.
            product_batch_size=None,
            allow_full_crawl=False,
            allowed_context_ids=(region_id,),
            max_concurrency=1,
            # The transport reads ICA_ALLOW_BROWSER_CATEGORY_PROOF here. The
            # CLI command name alone must not silently grant REVIEW authority.
            allow_category_proof=None,
        )
        return cls(
            client=client,
            context_mappings={region_id: retailer_id},
            parser=parser,
            coverage=CoverageLevel.PARTIAL_CATALOG,
        )

    @classmethod
    def for_full_collection(
        cls,
        *,
        client: IcaOnlineCollectionTransport,
        parser: IcaOnlineCatalogParser | None = None,
    ) -> IcaOnlineCatalogConnector:
        if (
            client.allow_full_crawl is not True
            or client.max_categories is not None
            or client.max_pages_per_category is not None
            or client.max_batches_per_page is not None
            or client.product_batch_size is None
        ):
            raise ValueError(
                "ICA full collection requires unlimited traversal and an explicit "
                "browser-verified batch size"
            )
        if not client.allowed_context_ids:
            raise ValueError("ICA full collection requires an exact context allowlist")
        return cls(
            client=client,
            context_mappings=client.context_mappings,
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        )

    @classmethod
    def for_exact_full_collection(
        cls,
        region_id: str,
        *,
        policy: IcaOnlineOperatorCrawlPolicy | None = None,
        parser: IcaOnlineCatalogParser | None = None,
    ) -> IcaOnlineCatalogConnector:
        region_id, retailer_id = cls._resolve_verified_context(region_id)
        configured = IcaOnlineOperatorCrawlPolicy.from_environment()
        target = configured.require(region_id)
        if policy is not None:
            policy.require(target)
        assert configured.product_batch_size is not None
        return cls.for_full_collection(
            client=IcaOnlineCatalogClient(
                context_mappings={target: retailer_id},
                max_categories=None,
                max_pages_per_category=None,
                max_batches_per_page=None,
                product_batch_size=configured.product_batch_size,
                allow_full_crawl=True,
                allowed_context_ids=(target,),
                max_concurrency=1,
            ),
            parser=parser,
        )

    @classmethod
    def for_exact_browser_full_collection(
        cls,
        region_id: str,
        *,
        policy: IcaOnlineOperatorCrawlPolicy | None = None,
        parser: IcaOnlineCatalogParser | None = None,
    ) -> IcaOnlineCatalogConnector:
        """Build an exact full collector over a fresh anonymous browser."""

        from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
            IcaOnlineBrowserTransport,
        )

        region_id, retailer_id = cls._resolve_verified_context(region_id)
        configured = IcaOnlineOperatorCrawlPolicy.from_environment()
        target = configured.require(region_id)
        if policy is not None:
            policy.require(target)
        assert configured.product_batch_size is not None
        return cls.for_full_collection(
            client=IcaOnlineBrowserTransport(
                context_mappings={target: retailer_id},
                max_categories=None,
                max_pages_per_category=None,
                max_batches_per_page=None,
                product_batch_size=configured.product_batch_size,
                allow_full_crawl=True,
                allowed_context_ids=(target,),
                max_concurrency=1,
            ),
            parser=parser,
        )

    @classmethod
    def for_replay(
        cls,
        *,
        context_ids: tuple[str, ...],
        parser: IcaOnlineCatalogParser | None = None,
    ) -> IcaOnlineCatalogConnector:
        captured = tuple(
            dict.fromkeys(
                cls._canonical_region_id(value) for value in context_ids if value.strip()
            )
        )
        if not captured:
            raise ValueError("ICA online replay requires captured context identities")
        return cls(
            client=None,
            context_mappings={context_id: None for context_id in captured},
            parser=parser,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
            replay_only=True,
        )

    @property
    def allowed_context_ids(self) -> frozenset[str]:
        return frozenset(self.context_mappings)

    def collection_policy_audit(self) -> SourceCollectionAudit:
        client = self.client
        full_authority = (
            self.coverage is CoverageLevel.FULL_ONLINE_CATALOG
            and client is not None
            and client.allow_full_crawl is True
            and client.max_categories is None
            and client.max_pages_per_category is None
            and client.max_batches_per_page is None
            and client.product_batch_size is not None
        )
        return SourceCollectionAudit(
            source_policy=self.source_policy,
            operator_opt_in=full_authority,
            store_allowlist=tuple(sorted(self.allowed_context_ids)),
            requests_per_second=(client.requests_per_second if client is not None else None),
            max_concurrency=(client.max_concurrency if client is not None else None),
        )

    def _require_live_client(self) -> IcaOnlineCollectionTransport:
        if self.client is None or self.replay_only:
            raise RuntimeError("ICA replay connector cannot make network requests")
        return self.client

    @staticmethod
    def _sum_transport(*values: TransportMetrics) -> TransportMetrics:
        return TransportMetrics(
            request_count=sum(value.request_count for value in values),
            http_error_count=sum(value.http_error_count for value in values),
            rate_limit_count=sum(value.rate_limit_count for value in values),
        )

    def _mapping_document(self, context_batch: RawBatch, region_id: str) -> RawFetch:
        context = next(
            (
                document
                for document in context_batch.documents
                if document.kind == ICA_STORE_CONTEXT_KIND
            ),
            None,
        )
        if context is None:
            raise IcaOnlineSchemaError("ICA context readback lacks the sanitized context row")
        payload = context.json_payload()
        if not isinstance(payload, dict):
            raise IcaOnlineSchemaError("ICA sanitized context row is not an object")
        retailer_id = str(payload.get("retailerRegionId") or "").strip()
        if not retailer_id or str(payload.get("regionId") or "").casefold() != region_id:
            raise IcaOnlineSchemaError("ICA context mapping does not match exact readback")
        expected = self.context_mappings.get(region_id)
        if expected is not None and retailer_id != expected:
            raise IcaOnlineSchemaError("ICA retailer route changed for verified context")
        evidence = self._VERIFIED_CONTEXTS.get(region_id, {})
        mapping = {
            "schema": "ica-online-store-mapping-v1",
            "regionId": region_id,
            "retailerRegionId": retailer_id,
            "name": evidence.get("name", f"ICA Online {region_id}"),
            "city": evidence.get("city"),
            "priceSemantics": "online_price",
            "relationEvidence": "exact_public_ssr_readback",
        }
        return RawFetch(
            chain=Chain.ICA,
            store_external_id=None,
            kind=ICA_STORE_MAPPING_KIND,
            method="GET",
            url=context.url,
            query={"region_id": region_id, "retailer_region_id": retailer_id},
            fetched_at=context.fetched_at,
            http_status=200,
            content_type="application/json; profile=sanitized-ica-store-mapping-v1",
            payload=json.dumps(
                mapping,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode(),
            connector_version=self.connector_version,
        )

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        client = self._require_live_client()
        documents: list[RawFetch] = []
        transports: list[TransportMetrics] = []
        for region_id in sorted(self.allowed_context_ids):
            context = await client.fetch_context(region_id)
            self._context_cache[region_id] = context
            documents.append(self._mapping_document(context, region_id))
            transports.append(context.transport)
        return RawBatch(
            chain=Chain.ICA,
            documents=tuple(documents),
            transport=self._sum_transport(*transports),
        )

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        stores: list[SourceStore] = []
        for (document, reference) in raw.with_references(references):
            if document.kind != ICA_STORE_MAPPING_KIND:
                continue
            payload = document.json_payload()
            if not isinstance(payload, dict) or payload.get("schema") != (
                "ica-online-store-mapping-v1"
            ):
                raise IcaOnlineSchemaError("ICA store mapping schema changed")
            try:
                region_id = self._canonical_region_id(payload.get("regionId"))
            except ValueError as exc:
                raise IcaOnlineSchemaError("ICA store mapping region ID is invalid") from exc
            retailer_id = str(payload.get("retailerRegionId") or "").strip()
            if region_id not in self.allowed_context_ids or not retailer_id:
                raise IcaOnlineSchemaError("ICA store mapping is outside exact contexts")
            expected = self.context_mappings.get(region_id)
            if expected is not None and retailer_id != expected:
                raise IcaOnlineSchemaError("ICA store mapping conflicts with verified route")
            if payload.get("priceSemantics") != "online_price":
                raise IcaOnlineSchemaError("ICA store mapping lacks online-price semantics")
            context_city = str(payload.get("city") or area.city).strip()
            verified = self._VERIFIED_CONTEXTS.get(region_id)
            if verified is not None and context_city.casefold() != area.city.casefold():
                raise IcaOnlineSchemaError("ICA exact context is outside requested city")
            stores.append(
                SourceStore(
                    chain=Chain.ICA,
                    external_id=region_id,
                    name=str(payload.get("name") or f"ICA Online {region_id}").strip(),
                    city=context_city,
                    online_shopping=True,
                    coverage=self.coverage,
                    price_context_type=PriceContextType.ONLINE_STORE,
                    physical_store_external_id=retailer_id,
                    raw_reference=reference,
                    source_fields={
                        "retailer_region_id": retailer_id,
                        "context_identity_verified": True,
                        "price_context_verified": True,
                        "price_semantics": "online_price",
                        "physical_price_verified": False,
                        "relation_evidence": payload.get("relationEvidence"),
                    },
                )
            )
        if not stores:
            raise IcaOnlineSchemaError("ICA online discovery found no exact context")
        return stores

    def catalog_eligible(self, store: SourceStore) -> bool:
        return (
            store.chain is Chain.ICA
            and store.external_id.casefold() in self.allowed_context_ids
            and store.online_shopping is True
            and store.coverage is self.coverage
            and store.price_context_type is PriceContextType.ONLINE_STORE
            and store.source_fields.get("price_context_verified") is True
            and store.source_fields.get("price_semantics") == "online_price"
        )

    async def _fetch_bounded_catalog(self, store: SourceStore) -> RawBatch:
        client = self._require_live_client()
        context = self._context_cache.pop(store.external_id, None)
        if context is None:
            context = await client.fetch_context(store.external_id)
        category_document = next(
            (
                document
                for document in context.documents
                if document.kind == ICA_CATEGORY_TREE_KIND
            ),
            None,
        )
        if category_document is None:
            raise IcaOnlineSchemaError("ICA bounded canary lacks category tree")
        tree = IcaCategoryTree.from_payload(category_document.json_payload())
        evidence = self._VERIFIED_CONTEXTS.get(store.external_id, {})
        category_id = evidence.get("canary_category_id")
        category = next(
            (node for node in tree.all_nodes if node.category_id == category_id),
            None,
        )
        if category is None:
            raise IcaOnlineSchemaError(
                "ICA bounded canary category is absent from current context navigation"
            )
        page_raw, page = await client.fetch_product_page(
            store.external_id,
            category.category_id,
            page_index=0,
        )
        if not page.other_product_ids or client.product_batch_size is None:
            raise IcaOnlineSchemaError("ICA bounded canary did not expose batch decoration IDs")
        requested = page.other_product_ids[: client.product_batch_size]
        batch_raw, _ = await client.fetch_product_batch(
            store.external_id,
            requested,
            category_id=category.category_id,
            page_index=0,
            batch_index=0,
        )
        documents = (*context.documents, page_raw, batch_raw)
        return RawBatch(
            chain=Chain.ICA,
            documents=documents,
            transport=self._sum_transport(
                context.transport,
                TransportMetrics(request_count=2),
            ),
            catalog_completion=CatalogCompletion(
                complete=False,
                limited=True,
                expected_categories=tree.terminal_count,
                completed_categories=0,
                pages_fetched=1,
                products_observed=len(page.decorated_products) + len(requested),
                reason="source policy REVIEW: one category/page/batch canary",
            ),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        if not self.catalog_eligible(store):
            raise IcaOnlineSchemaError("ICA online context is not catalog eligible")
        if self.coverage is CoverageLevel.FULL_ONLINE_CATALOG:
            return await self._require_live_client().fetch_catalog(store.external_id)
        return await self._fetch_bounded_catalog(store)

    def _parse_bounded_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        products: dict[str, Any] = {}
        fingerprints: dict[str, str] = {}
        source_rows: list[tuple[dict[str, Any], str, datetime]] = []
        try:
            for document, reference in raw.with_references(references):
                rows: tuple[dict[str, Any], ...]
                if document.kind == ICA_PRODUCT_PAGE_KIND:
                    rows = self.parser.parse_product_page(
                        document,
                        store=store,
                    ).decorated_products
                elif document.kind == ICA_PRODUCT_BATCH_KIND:
                    rows = self.parser.parse_product_batch(
                        document,
                        store=store,
                    ).products
                else:
                    continue
                for index, row in enumerate(rows):
                    product_id = str(row.get("productId") or "")
                    fingerprint = purchase_semantic_fingerprint(row)
                    if product_id in products:
                        if fingerprints[product_id] != fingerprint:
                            raise IcaOnlineSchemaError(
                                "ICA bounded canary contains conflicting product semantics"
                            )
                        continue
                    products[product_id] = row
                    fingerprints[product_id] = fingerprint
                    source_rows.append(
                        (row, f"{reference}#products[{index}]", document.fetched_at)
                    )
            if not source_rows:
                raise IcaOnlineSchemaError("ICA bounded canary parsed no products")
            parsed = [
                self.parser.parse_product(
                    row,
                    store=store,
                    reference=reference,
                    fetched_at=fetched_at,
                )
                for row, reference, fetched_at in source_rows
            ]
            return ProductParseResult(products=parsed)
        except (IcaOnlineSchemaError, ValueError) as exc:
            return ProductParseResult(
                failures=[
                    ParseFailure(
                        raw_record_reference=(references[0] if references else "raw:ica-canary"),
                        error_code="schema_changed",
                        error_message=str(exc)[:300],
                        parser_version=self.parser_version,
                    )
                ]
            )

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        if self.coverage is CoverageLevel.FULL_ONLINE_CATALOG:
            return self.parser.parse_catalog(raw, references, store)
        return self._parse_bounded_catalog(raw, references, store)

    def reconcile_replay_catalog_completion(
        self,
        raw: RawBatch,
        store: SourceStore,
    ) -> RawBatch:
        references = [f"raw:ica-replay:{index}" for index in range(len(raw.documents))]
        reconciliation = self.parser.reconcile_catalog(raw, references, store)
        return raw.model_copy(update={"catalog_completion": reconciliation.completion})

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        del store
        # Resolved online promotions belong to product observations. The
        # accepted legacy ICA connector remains the independent offers source.
        return RawBatch(chain=Chain.ICA, documents=())

    async def aclose(self) -> None:
        self._context_cache.clear()
        if self.client is not None:
            await self.client.aclose()


__all__ = ["IcaOnlineCatalogConnector"]
