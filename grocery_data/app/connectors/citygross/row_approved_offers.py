"""Partial online promotions from retained, store-bound City Gross pages.

This does not claim a complete catalog or physical-store campaign validity.
It reuses the ordinary parser, row qualification, collector and OWN contracts.
"""
from __future__ import annotations

import hashlib
import json

from grocery_data.app.connectors.citygross.connector import CityGrossConnector
from grocery_data.app.connectors.citygross.parser import CityGrossParser
from grocery_data.app.domain import (
    CoverageLevel,
    ProductParseResult,
    PromotionType,
    RawBatch,
    TransportMetrics,
)
from grocery_data.app.services.offer_rows import CITYGROSS_POLICY, qualify_rows


class CityGrossRowApprovedOfferConnector(CityGrossConnector):
    coverage = CoverageLevel.OFFERS_ONLY

    def __init__(self, *, store, locator: RawBatch, catalog: RawBatch):
        self.parser = CityGrossParser()
        self.parser_version = self.parser.parser_version
        self.store = store.model_copy(update={
            "coverage": CoverageLevel.OFFERS_ONLY,
            "source_fields": {**store.source_fields, "offer_policy": CITYGROSS_POLICY},
        })
        # A replay has no new network attempts. Original transport/completion
        # remains in the row evidence and the rejected full collection.
        self.locator = locator.model_copy(update={"transport": TransportMetrics()})
        self.catalog = catalog.model_copy(update={
            "documents": tuple(d for d in catalog.documents if d.kind == "catalog_page"),
            "transport": TransportMetrics(),
            "catalog_completion": None,
        })
        if not self.catalog.documents:
            raise ValueError("City Gross partial offers require actual catalog page evidence")
        self.original_catalog = catalog
        self.row_acceptance = None

    def collection_policy_audit(self):
        from grocery_data.app.domain import SourceCollectionAudit

        # Instantiating this explicit retained-only adapter opts in to parsing
        # these exact captured pages; it has no transport or live crawl client.
        return SourceCollectionAudit(source_policy=self.source_policy, operator_opt_in=True,
                                     store_allowlist=(self.store.external_id,))

    async def fetch_stores(self, area):
        return self.locator

    def parse_stores(self, raw, references, area):
        return [self.store]

    def catalog_eligible(self, store):
        return (store.external_id == self.store.external_id
                and store.coverage == CoverageLevel.OFFERS_ONLY)

    async def fetch_catalog(self, store):
        return self.catalog

    def parse_catalog(self, raw, references, store):
        extracted = self.parser.parse_catalog(raw, references, store)
        candidates = []
        for product in extracted.products:
            # Only an explicitly active, bounded contract is independently
            # usable when the ordinary catalog cannot be established.
            offers = tuple(o for o in product.offers
                           if o.source_payload.get("active") is True)
            blockers = []
            if len(offers) != 1:
                blockers.append("single_active_promotion_unverified")
            for offer in offers:
                blockers.extend(offer.source_payload.get("purchase_blockers", []))
                if offer.type not in {
                    PromotionType.MULTIBUY, PromotionType.SALE_PRICE, PromotionType.MEMBER_PRICE,
                }:
                    blockers.append("promotion_mechanism_unsupported")
                if offer.source_payload.get("price_unit") != "PCE":
                    blockers.append("promotion_package_price_unverified")
            candidates.append(product.model_copy(update={
                "sale_price": None, "regular_price": None, "member_price": None,
                "offers": offers,
                "source_fields": {**product.source_fields,
                    "citygross_offer_policy": CITYGROSS_POLICY,
                    "verified_store_scope": product.store_external_id == store.external_id,
                    "regular_price_current_verified": False,
                    "catalog_ordinary_price_reference": str(product.regular_price)
                        if product.regular_price is not None else None,
                    "purchase_blockers": blockers,
                },
            }))
        parsed = ProductParseResult(products=candidates, failures=extracted.failures)
        self.extracted = extracted
        result, self.row_acceptance = qualify_rows(
            parsed, store=store,
            observed_at=max(d.fetched_at for d in raw.documents),
            original_parsed=extracted,
        )
        self.row_acceptance.update({
            "replayed_without_network": True,
            "original_transport": self.original_catalog.transport.model_dump(mode="json"),
            "original_catalog_completion": (
                self.original_catalog.catalog_completion.model_dump(mode="json")
                if self.original_catalog.catalog_completion is not None else None),
        })
        self.row_acceptance.pop("evidence_sha256", None)
        self.row_acceptance["evidence_sha256"] = hashlib.sha256(
            json.dumps(self.row_acceptance, sort_keys=True).encode()).hexdigest()
        return result

    async def aclose(self):
        pass
