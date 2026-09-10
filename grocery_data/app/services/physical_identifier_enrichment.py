from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from grocery_data.app.connectors.hemkop.client import HemkopClient
from grocery_data.app.connectors.hemkop.parser import HemkopParser
from grocery_data.app.domain.enums import Chain, Confidence, CoverageLevel, PriceContextType
from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
from grocery_data.app.domain.physical_price import (
    ProductIdentifierEvidence,
    ProductIdentifierEvidenceSource,
    ProductIdentifierType,
)
from grocery_data.app.domain.raw import RawBatch
from grocery_data.app.domain.store import SourceStore
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore


@dataclass(frozen=True, slots=True)
class IdentifierEnrichmentTarget:
    chain: Chain
    source_provider: str
    physical_store_id: str
    store_external_id: str
    source_product_id: str
    external_product_id: str
    product_name: str


@dataclass(frozen=True, slots=True)
class IdentifierEnrichmentResult:
    evidence: ProductIdentifierEvidence | None
    requests: int
    status: str
    reason: str | None = None


class PhysicalProductIdentifierEnricher(Protocol):
    async def enrich(
        self,
        target: IdentifierEnrichmentTarget,
    ) -> IdentifierEnrichmentResult: ...


class HemkopProductDetailIdentifierEnricher:
    """One exact Hemköp detail request, with anonymous activation and raw-first capture."""

    def __init__(self, *, raw_root: Path) -> None:
        self.raw_store = FilesystemRawSnapshotStore(raw_root / "identifier_enrichment")

    async def enrich(
        self,
        target: IdentifierEnrichmentTarget,
    ) -> IdentifierEnrichmentResult:
        if target.chain is not Chain.HEMKOP or target.source_provider != "own":
            return IdentifierEnrichmentResult(
                evidence=None,
                requests=0,
                status="unavailable",
                reason="no approved detail enricher for source",
            )
        source_store = SourceStore(
            chain=Chain.HEMKOP,
            external_id=target.store_external_id,
            name=target.physical_store_id,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
            price_context_type=PriceContextType.ONLINE_STORE,
            physical_store_external_id=target.store_external_id,
            raw_reference="physical-validation:exact-store-context",
        )
        client = HemkopClient(
            max_categories=1,
            max_pages_per_category=1,
            detail_enrichment_limit=0,
            allowed_store_ids={target.store_external_id},
        )
        try:
            raw = await client.fetch_validation_product_details(
                source_store,
                (target.external_product_id,),
                max_products=1,
            )
        finally:
            await client.aclose()

        snapshot_key = f"physical_identifier_{uuid4().hex}"
        stored = self.raw_store.save_batch(raw, snapshot_id=snapshot_key)
        sanitized_documents = tuple(
            document.model_copy(update={"payload": self.raw_store.load(record)})
            for document, record in zip(raw.documents, stored, strict=True)
        )
        sanitized = RawBatch(
            chain=raw.chain,
            documents=sanitized_documents,
            transport=raw.transport,
            catalog_completion=raw.catalog_completion,
        )
        references = [f"raw:{record.document_id}" for record in stored]
        parsed = HemkopParser().parse_catalog(sanitized, references, source_store)
        if parsed.failures:
            return IdentifierEnrichmentResult(
                evidence=None,
                requests=raw.transport.request_count,
                status="error",
                reason="Hemköp product-detail parser rejected the source response",
            )
        matches = tuple(
            product
            for product in parsed.products
            if product.external_product_id == target.external_product_id
        )
        if len(matches) != 1:
            return IdentifierEnrichmentResult(
                evidence=None,
                requests=raw.transport.request_count,
                status="error",
                reason="Hemköp detail did not reconcile the exact source product",
            )
        product = matches[0]
        if not product.gtin:
            return IdentifierEnrichmentResult(
                evidence=None,
                requests=raw.transport.request_count,
                status="unavailable",
                reason="Hemköp detail has no explicit EAN",
            )
        try:
            normalized = normalize_gtin(product.gtin).normalized_gtin
        except InvalidGtinError:
            return IdentifierEnrichmentResult(
                evidence=None,
                requests=raw.transport.request_count,
                status="error",
                reason="Hemköp detail exposed a checksum-invalid EAN",
            )
        detail_index = next(
            index
            for index, document in enumerate(sanitized.documents)
            if document.kind == "product_detail"
        )
        detail_record = stored[detail_index]
        evidence = ProductIdentifierEvidence(
            id=uuid4().hex,
            chain=Chain.HEMKOP,
            source_provider="own",
            scope_key=target.store_external_id,
            source_product_id=target.source_product_id,
            external_product_id=target.external_product_id,
            identifier_type=ProductIdentifierType.GTIN,
            identifier_value=normalized,
            evidence_source=ProductIdentifierEvidenceSource.PRODUCT_DETAIL,
            evidence_reference=f"raw:{detail_record.relative_path}#ean",
            evidence_payload_sha256=detail_record.payload_hash,
            observed_at=product.fetched_at,
            confidence=Confidence.HIGH,
        )
        return IdentifierEnrichmentResult(
            evidence=evidence,
            requests=raw.transport.request_count,
            status="enriched",
        )


__all__ = [
    "HemkopProductDetailIdentifierEnricher",
    "IdentifierEnrichmentResult",
    "IdentifierEnrichmentTarget",
    "PhysicalProductIdentifierEnricher",
]
