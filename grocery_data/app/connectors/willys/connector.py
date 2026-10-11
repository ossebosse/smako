from __future__ import annotations

import os
from collections.abc import Iterable

from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
)


class WillysConnector:
    chain = Chain.WILLYS
    coverage = CoverageLevel.FULL_CATALOG
    connector_version = "willys-v1"
    parser_version = WillysParser.parser_version
    source_policy = SourcePolicy.ALLOW

    def __init__(
        self,
        *,
        client: WillysClient | None = None,
        parser: WillysParser | None = None,
        allowed_store_ids: Iterable[str] | None = None,
        municipality_boundary: dict | None = None,
    ) -> None:
        self.client = client or WillysClient()
        self.parser = parser or WillysParser()
        self.parser_version = self.parser.parser_version
        self.municipality_boundary = municipality_boundary
        self.municipality_inventory = None
        self.checkpoints = None
        self.discovery = None
        if allowed_store_ids is None:
            configured = frozenset(
                value.strip()
                for value in os.getenv("WILLYS_STORE_EXTERNAL_IDS", "").split(",")
                if value.strip()
            )
            self.allowed_store_ids: frozenset[str] | None = configured or None
        else:
            # An explicitly empty iterable intentionally denies every store;
            # this is safer than silently expanding a mistyped operator target
            # into a multi-store collection.
            self.allowed_store_ids = frozenset(
                value.strip() for value in allowed_store_ids if value.strip()
            )

    def collection_policy_audit(self) -> SourceCollectionAudit:
        """Return the exact, sanitized guardrails used by this collection."""

        return SourceCollectionAudit(
            source_policy=self.source_policy,
            operator_opt_in=False,
            store_allowlist=tuple(sorted(self.allowed_store_ids or ())),
            requests_per_second=self.client.requests_per_second,
            max_concurrency=self.client.max_concurrency,
        )

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        if area.mode == "municipality" and self.municipality_boundary is None:
            from grocery_data.app.services.municipality_geometry import fetch_boundary

            self.municipality_boundary = await fetch_boundary(area.municipality_code)
        self.discovery = await self.client.fetch_stores()
        return self.discovery

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        if area.mode == "municipality":
            from grocery_data.app.connectors.willys.municipality_inventory import build_inventory

            if self.municipality_boundary is None:
                raise ValueError("municipal collection requires verified boundary evidence")
            self.municipality_inventory = build_inventory(area, raw, references, self.municipality_boundary)
            stores = [SourceStore.model_validate(row["store"]) for row in self.municipality_inventory["stores"]
                      if row["collection_selected"]]
        else:
            stores = self.parser.parse_stores(raw, references, area)
        if self.allowed_store_ids is None:
            return stores
        # A targeted collection must persist/reconcile only its explicitly
        # selected checkout contexts. Leaving other discovered FULL stores in
        # the candidate would make them look basket-eligible without any
        # products in that snapshot.
        return [store for store in stores if store.external_id in self.allowed_store_ids]

    def catalog_eligible(self, store: SourceStore) -> bool:
        # Willys' verified catalog source requires an activatable online-store
        # context. Physical stores remain discoverable, but must not be treated
        # as if a full local catalog had been observed.
        return (
            store.online_shopping is True
            and store.coverage == CoverageLevel.FULL_CATALOG
            and (self.allowed_store_ids is None or store.external_id in self.allowed_store_ids)
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        if self.checkpoints is not None:
            return await self.checkpoints.fetch(store, self.discovery, self.client.fetch_catalog)
        return await self.client.fetch_catalog(store)

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        return self.parser.parse_catalog(raw, references, store)

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        # Willys includes structured potentialPromotions on each catalog row.
        # Returning an empty batch prevents a second full-catalog fetch; the
        # collector persists promotions from ``fetch_catalog``.
        return RawBatch(chain=self.chain, documents=())

    async def aclose(self) -> None:
        await self.client.aclose()
