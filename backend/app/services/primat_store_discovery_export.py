"""Closed credential-free export of one bounded Primat store resolution."""

from __future__ import annotations

from typing import Any

from app.providers.primat import PrimatStoreResolution
from pydantic import ValidationError

from grocery_data.app.domain import Chain, CoverageLevel, PriceContextType
from grocery_data.app.services.provider_store_identity import (
    PrimatStoreCandidate,
    PrimatStoreDiscoveryBundle,
    PrimatStoreDiscoveryRequest,
)

_TARGET_CHAINS = frozenset({Chain.ICA, Chain.COOP, Chain.LIDL})


def _coverage(value: str | None) -> CoverageLevel | None:
    normalized = (value or "").casefold().strip()
    aliases = {
        "full": CoverageLevel.FULL_CATALOG,
        "full_catalog": CoverageLevel.FULL_CATALOG,
        "full_online_catalog": CoverageLevel.FULL_ONLINE_CATALOG,
        "offers_only": CoverageLevel.OFFERS_ONLY,
        "partial_catalog": CoverageLevel.PARTIAL_CATALOG,
    }
    return aliases.get(normalized)


def primat_store_discovery_bundle(
    resolution: PrimatStoreResolution,
) -> PrimatStoreDiscoveryBundle:
    """Project parsed public store facts; never accept transport credentials."""

    items: list[PrimatStoreCandidate] = []
    for index, store in enumerate(resolution.stores):
        try:
            chain = Chain(store.chain.casefold())
        except ValueError:
            continue
        if chain not in _TARGET_CHAINS:
            continue
        provenance = store.source_provenance
        if (
            provenance is None
            or provenance.source_provider != "primat"
            or provenance.source_channel != "catalog"
            or provenance.source_snapshot_id != resolution.source_snapshot_id
            or provenance.source_observed_at != resolution.observed_at
            or provenance.provider_store_id != store.source_store_id
        ):
            raise ValueError("Primat store candidate lacks request-scoped catalog provenance")
        context_id = (
            store.store_id
            if store.store_id.startswith("primat:")
            else f"primat:{store.store_id}"
        )
        try:
            context_type = (
                PriceContextType(store.price_context_type)
                if store.price_context_type
                else PriceContextType.PHYSICAL_STORE
            )
        except ValueError as exc:
            raise ValueError("Primat store candidate has unknown price context type") from exc
        items.append(
            PrimatStoreCandidate(
                provider_context_id=context_id,
                provider_store_id=store.source_store_id or provenance.provider_store_id,
                chain=chain,
                name=store.name,
                address=store.address,
                postal_code=store.postal_code,
                city=store.city,
                latitude=store.latitude,
                longitude=store.longitude,
                tier=store.tier,
                coverage=_coverage(store.coverage or store.tier),
                price_context_type=context_type,
                selected=store.store_id in resolution.selected_context_ids,
                customer_facing=True,
                source_snapshot_id=resolution.source_snapshot_id,
                observed_at=resolution.observed_at,
                raw_reference=(
                    f"response:{resolution.response_sha256}:normalized-stores[{index}]"
                ),
            )
        )
    try:
        return PrimatStoreDiscoveryBundle(
            schema_version="primat-store-discovery-bundle-v1",
            city=resolution.place_city or "Lund",
            postal_code=resolution.postal_code,
            captured_at=resolution.observed_at,
            request=PrimatStoreDiscoveryRequest(
                host=resolution.response_host,
                path=resolution.response_path,
                status=resolution.response_status,
                content_type=resolution.response_content_type,
                response_sha256=resolution.response_sha256,
            ),
            raw_rows=resolution.raw_rows,
            items=tuple(items),
        )
    except ValidationError as exc:
        raise ValueError("Primat store discovery does not satisfy closed export schema") from exc


def store_discovery_output_summary(bundle: PrimatStoreDiscoveryBundle) -> dict[str, Any]:
    chains: dict[str, int] = {}
    for item in bundle.items:
        chains[item.chain.value] = chains.get(item.chain.value, 0) + 1
    return {
        "schema": bundle.schema_version,
        "city": bundle.city,
        "postal_code": bundle.postal_code,
        "raw_rows": bundle.raw_rows,
        "public_target_contexts": len(bundle.items),
        "chains": dict(sorted(chains.items())),
        "response_sha256": bundle.request.response_sha256,
        "credentials_included": False,
        "headers_included": False,
        "cookies_included": False,
        "raw_response_body_included": False,
    }


__all__ = ["primat_store_discovery_bundle", "store_discovery_output_summary"]
