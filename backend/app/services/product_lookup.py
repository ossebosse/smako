"""Exact barcode lookup against an already active local PriceUniverse."""

from __future__ import annotations

from collections.abc import Iterable

from app.models import (
    Product,
    ProductLookupIdentity,
    ProductLookupPrice,
    ProductLookupResponse,
)
from app.services.price_universe_runtime import PreparedPriceUniverse

from grocery_data.app.domain.identifiers import normalize_gtin
from grocery_data.app.domain.promotion_pricing import MembershipProgram


def _package_description(product: Product) -> str | None:
    quantity = product.package_quantity or product.usable_quantity
    unit = product.package_unit or product.usable_unit
    if quantity is None or unit is None:
        return None
    rendered = f"{quantity:g}" if float(quantity).is_integer() else str(quantity)
    return f"{rendered} {unit}"


def _membership_program(product: Product) -> MembershipProgram | None:
    """Bind an explicit generic member price to its stable chain program."""

    if product.member_price is None or product.chain is None:
        return None
    try:
        return MembershipProgram.from_value(product.chain)
    except ValueError:
        # Preserve the source price without inventing a program identity. Such
        # a row remains informational and cannot be unlocked by a user flag.
        return None


def _current_public_price(product: Product) -> float | None:
    """Resolve the best unconditional public one-package display price.

    A legacy membership-profiled artifact may have flattened a member price
    into ``effective_price``. Reconstructing the public projection from the
    ordinary price and explicit public single-package offers prevents that
    restricted amount from being mislabeled as a public campaign.
    """

    candidates = [product.price] if product.price is not None else []
    candidates.extend(
        offer.price
        for offer in product.active_offers()
        if offer.member_program is None and offer.required_packages == 1
    )
    return min(candidates) if candidates else None


def lookup_gtin(
    prepared: PreparedPriceUniverse,
    raw_gtin: str,
    *,
    allowed_context_ids: Iterable[str] | None = None,
) -> ProductLookupResponse:
    normalized = normalize_gtin(raw_gtin).normalized_gtin
    allowed = set(allowed_context_ids) if allowed_context_ids is not None else None
    products = sorted(
        (
            product
            for product in prepared.universe.products_for_gtin(normalized)
            if allowed is None or product.store_id in allowed
        ),
        key=lambda row: (row.name.casefold(), row.store_name.casefold(), row.product_id),
    )
    if not products:
        return ProductLookupResponse(
            found=False,
            gtin=normalized,
            price_universe_id=prepared.universe.universe_id,
        )

    identities_by_key: dict[tuple[str, str, str], ProductLookupIdentity] = {}
    for product in products:
        identity = ProductLookupIdentity(
            product_id=product.product_id,
            name=product.name,
            brand=product.brand,
            package_description=_package_description(product),
            gtin=normalized,
        )
        key = (
            identity.name.casefold(),
            (identity.brand or "").casefold(),
            (identity.package_description or "").casefold(),
        )
        identities_by_key.setdefault(key, identity)
    identities = list(identities_by_key.values())

    prices = []
    for product in products:
        provenance = product.source_provenance
        current_public_price = _current_public_price(product)
        if current_public_price is None:
            continue
        prices.append(
            ProductLookupPrice(
                product_id=product.product_id,
                grocery_context_id=product.store_id,
                # A grocery price context is not an internal PhysicalStore
                # identity.  This remains unknown until an exact registry
                # relation is supplied alongside the universe.
                physical_store_id=None,
                store_display_name=product.store_name,
                chain=product.chain,
                regular_price=product.price,
                effective_price=current_public_price,
                current_public_price=current_public_price,
                member_price=product.member_price,
                membership_program=_membership_program(product),
                offers=product.active_offers(),
                price_context_type=product.price_context_type,
                availability_label=(
                    "Online-sortiment"
                    if (product.price_context_type or "").casefold()
                    not in {"physical_store", "physical-store"}
                    else "Källrapporterad butikskatalog; inte lagerbesked"
                ),
                source_provider=(provenance.source_provider if provenance else None),
                source_channel=(provenance.source_channel if provenance else None),
                source_snapshot_id=(provenance.source_snapshot_id if provenance else None),
                source_observed_at=(provenance.source_observed_at if provenance else None),
            )
        )
    return ProductLookupResponse(
        found=True,
        gtin=normalized,
        product=identities[0] if len(identities) == 1 else None,
        identities=identities,
        prices=prices,
        ambiguous_identity=len(identities) > 1,
        price_universe_id=prepared.universe.universe_id,
    )


__all__ = ["lookup_gtin"]
