"""Closed product/price smoke evidence for already mapped Primat contexts."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal

from app.models import Product
from app.providers.primat import PrimatStoreResolution

from grocery_data.app.domain import CoverageLevel
from grocery_data.app.services.provider_store_identity import (
    PrimatCatalogSmokeRequest,
    PrimatContextSmokeBundle,
    PrimatContextSmokeEvidence,
    PrimatSmokeProductSample,
)

from .primat_store_discovery_export import primat_store_discovery_bundle


def primat_context_smoke_bundle(
    resolution: PrimatStoreResolution,
    products: Sequence[Product],
    *,
    requested_context_ids: frozenset[str],
    mapping_discovery_response_sha256: str,
    product_response: Mapping[str, object],
    query_label: str = "common-packaged-food",
) -> PrimatContextSmokeBundle:
    """Validate scope/provenance and export per-context priced-row counts."""

    if not requested_context_ids or len(requested_context_ids) > 100:
        raise ValueError("catalog smoke requires 1..100 explicitly mapped contexts")
    discovery = primat_store_discovery_bundle(resolution)
    candidates = {row.provider_context_id: row for row in discovery.items}
    missing = sorted(requested_context_ids - candidates.keys())
    if missing:
        raise ValueError("catalog smoke requested a context absent from current resolution")

    by_context: defaultdict[str, list[Product]] = defaultdict(list)
    for product in products:
        context_id = (
            product.store_id
            if product.store_id.startswith("primat:")
            else f"primat:{product.store_id}"
        )
        if context_id not in requested_context_ids:
            continue
        provenance = product.source_provenance
        if (
            provenance is None
            or provenance.source_provider != "primat"
            or provenance.source_channel != "catalog"
            or provenance.source_snapshot_id != resolution.source_snapshot_id
            or provenance.source_observed_at != resolution.observed_at
            or provenance.store_id != product.store_id
        ):
            raise ValueError("Primat smoke product lacks request-scoped catalog provenance")
        by_context[context_id].append(product)

    try:
        product_request = PrimatCatalogSmokeRequest(
            method=str(product_response["method"]),
            host=str(product_response["host"]),
            path=str(product_response["path"]),
            status=int(product_response["status"]),
            content_type=str(product_response["content_type"]),
            response_sha256=str(product_response["response_sha256"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Primat smoke lacks closed product transport metadata") from exc

    items: list[PrimatContextSmokeEvidence] = []
    for context_id in sorted(requested_context_ids):
        candidate = candidates[context_id]
        rows = by_context.get(context_id, [])
        priced = [row for row in rows if row.effective_price is not None and row.effective_price > 0]
        coverage = candidate.coverage
        if coverage not in {
            CoverageLevel.FULL_CATALOG,
            CoverageLevel.FULL_ONLINE_CATALOG,
        }:
            # Preserve the negative smoke outcome without manufacturing full
            # coverage. Activation will reject the row explicitly.
            coverage = coverage or CoverageLevel.UNAVAILABLE
        items.append(
            PrimatContextSmokeEvidence(
                provider_context_id=context_id,
                provider_store_id=candidate.provider_store_id,
                chain=candidate.chain,
                coverage=coverage,
                source_snapshot_id=resolution.source_snapshot_id,
                observed_at=resolution.observed_at,
                product_rows=len(rows),
                priced_product_rows=len(priced),
                provenance_valid=True,
                samples=tuple(
                    PrimatSmokeProductSample(
                        product_id=row.product_id,
                        name=row.name,
                        current_price=Decimal(str(row.effective_price)),
                    )
                    for row in sorted(priced, key=lambda item: (item.store_id, item.product_id))[:5]
                ),
                raw_reference=(
                    f"response:{product_request.response_sha256}:context:{context_id}"
                ),
            )
        )
    return PrimatContextSmokeBundle(
        schema_version="primat-context-smoke-bundle-v1",
        city=discovery.city,
        postal_code=discovery.postal_code,
        captured_at=resolution.observed_at,
        store_discovery_response_sha256=mapping_discovery_response_sha256,
        resolve_request=discovery.request,
        product_request=product_request,
        identity_revalidated=True,
        query_label=query_label,
        items=tuple(items),
    )


__all__ = ["primat_context_smoke_bundle"]
