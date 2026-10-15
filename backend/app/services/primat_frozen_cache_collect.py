"""Eligibility, query-surface and export gates for a frozen Primat cache.

This module is deliberately independent of the meal and basket optimizers.  It
reads already verified context lineage from an immutable SQLite database,
revalidates those identities against one bounded store resolution, and exports
only parsed consumer-domain rows through the existing
``lund-frozen-external-v1`` schema.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from pathlib import Path

from app.models import Product, SourceProvenance, Store
from app.providers.primat import PrimatStoreResolution
from app.services.ingredient_normalizer import _search_text as _provider_search_key
from app.services.primat_phase_c_export import FrozenExternalCacheBundle
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    PriceContextType,
    StoreIdentityMatchConfidence,
    is_complete_catalog_coverage,
)
from grocery_data.app.services.catalog_recipe_coverage import (
    REPRESENTATIVE_RECIPE_BASKET,
    CatalogRecipeCoverageBenchmark,
)

_STRONG_MAPPING_CONFIDENCE = frozenset(
    {
        StoreIdentityMatchConfidence.EXACT_ID,
        StoreIdentityMatchConfidence.EXACT_ADDRESS,
        StoreIdentityMatchConfidence.EXACT_NAME_AND_POSTAL,
        StoreIdentityMatchConfidence.STRONG_GEO,
    }
)


class CanonicalIngredientQuery(BaseModel):
    """One deterministic provider query for one canonical benchmark identity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    canonical: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=200)


class CanonicalIngredientQuerySurface(BaseModel):
    """Versioned 48-query projection of CatalogRecipeCoverageBenchmark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "catalog-recipe-coverage-query-surface-v1"
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: tuple[CanonicalIngredientQuery, ...]
    representative_basket: tuple[str, ...]

    @model_validator(mode="after")
    def require_complete_unique_surface(self) -> CanonicalIngredientQuerySurface:
        if len(self.items) != 48:
            raise ValueError("canonical recipe query surface must contain exactly 48 rows")
        canonicals = [row.canonical for row in self.items]
        query_keys = [_query_key(row.query) for row in self.items]
        if len(set(canonicals)) != len(canonicals):
            raise ValueError("canonical recipe query surface contains duplicate identities")
        if len(set(query_keys)) != len(query_keys):
            raise ValueError("canonical recipe query surface must spend one request per row")
        if not set(self.representative_basket).issubset(canonicals):
            raise ValueError("representative basket is absent from the canonical query surface")
        return self


class EligiblePrimatContext(BaseModel):
    """One fresh full context backed by strong persisted identity evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    physical_store_id: str = Field(min_length=1, max_length=255)
    physical_store_external_id: str = Field(min_length=1, max_length=255)
    provider_context_id: str = Field(min_length=1, max_length=255)
    provider_store_id: str = Field(min_length=1, max_length=255)
    chain: Chain
    coverage: CoverageLevel
    price_context_type: PriceContextType
    confidence: StoreIdentityMatchConfidence
    verified_identity_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_id: str = Field(min_length=1, max_length=255)
    observed_at: datetime
    data_age_hours: Decimal = Field(ge=0)

    @field_validator("observed_at")
    @classmethod
    def require_aware_observation(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("eligible context observation must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_strong_full_context(self) -> EligiblePrimatContext:
        if not self.provider_context_id.startswith("primat:"):
            raise ValueError("eligible context must use the primat: namespace")
        if self.confidence not in _STRONG_MAPPING_CONFIDENCE:
            raise ValueError("eligible context lacks strong mapping evidence")
        if not is_complete_catalog_coverage(self.coverage):
            raise ValueError("eligible context does not declare complete catalog coverage")
        return self


@dataclass(frozen=True, slots=True)
class RevalidatedPrimatContext:
    """Persisted eligibility paired with the current request-scoped store."""

    eligible: EligiblePrimatContext
    store: Store


def _query_key(value: str) -> str:
    # This is the exact key used by PrimatPriceProvider's request-local cache.
    return _provider_search_key(value)


def canonical_ingredient_query_surface() -> CanonicalIngredientQuerySurface:
    """Select one unique declared alias for every versioned canonical row.

    Query uniqueness matters operationally because the Primat adapter caches an
    identical search.  A duplicate alias would otherwise make a nominal
    48-row surface spend only 47 HTTP requests.
    """

    ingredient_set = CatalogRecipeCoverageBenchmark.ingredient_set
    used_queries: set[str] = set()
    items: list[CanonicalIngredientQuery] = []
    for ingredient in ingredient_set:
        selected: str | None = None
        for alias in ingredient.queries:
            key = _query_key(alias)
            if key and key not in used_queries:
                selected = alias
                used_queries.add(key)
                break
        if selected is None:
            raise ValueError(
                "canonical ingredient has no unique declared provider-query alias"
            )
        items.append(
            CanonicalIngredientQuery(
                canonical=ingredient.canonical,
                query=selected,
            )
        )
    serialized = json.dumps(
        [row.model_dump(mode="json") for row in items],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return CanonicalIngredientQuerySurface(
        sha256=hashlib.sha256(serialized).hexdigest(),
        items=tuple(items),
        representative_basket=REPRESENTATIVE_RECIPE_BASKET,
    )


def _aware_timestamp(value: object) -> datetime:
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("eligible Primat link has an invalid observation timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("eligible Primat link has a naive observation timestamp")
    return parsed.astimezone(UTC)


def _required_schema(connection: sqlite3.Connection) -> None:
    required = {
        "physical_stores": {
            "id",
            "chain",
            "external_store_id",
            "city",
            "is_active",
        },
        "provider_store_identity_mappings": {
            "physical_store_id",
            "provider",
            "provider_context_id",
            "provider_store_id",
            "confidence",
            "status",
            "verified_identity_fingerprint",
            "is_active",
        },
        "store_context_links": {
            "physical_store_id",
            "grocery_context_id",
            "source_provider",
            "source_channel",
            "price_context_type",
            "coverage",
            "relation_type",
            "basket_eligible",
            "offers_only",
            "snapshot_id",
            "observed_at",
            "is_active",
        },
    }
    tables = {
        str(row[0])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    if not set(required).issubset(tables):
        raise ValueError("explicit database lacks the required Primat mapping tables")
    for table, columns in required.items():
        available = {
            str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")
        }
        if not columns.issubset(available):
            raise ValueError("explicit database lacks required Primat mapping columns")


def load_eligible_primat_contexts(
    database: Path,
    *,
    city: str = "Lund",
    max_age_hours: float = 48.0,
    now: datetime | None = None,
    chains: frozenset[Chain] = frozenset({Chain.ICA}),
    allow_stale_identity_seed: bool = False,
) -> tuple[EligiblePrimatContext, ...]:
    """Read active, strong, full links through immutable SQLite.

    Qualified catalog observations remain usable as they age. Before a live
    collection, callers must still revalidate the exact provider identity.
    The legacy allow_stale_identity_seed argument remains API-compatible;
    source ages are retained for operational diagnostics.
    """

    if not chains:
        raise ValueError("eligible Primat context collection requires at least one chain")
    if not isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_age_hours must be finite and positive")
    evaluated_at = now or datetime.now(tz=UTC)
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("freshness evaluation time must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    resolved = database.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("explicit database must be a regular SQLite file")
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        _required_schema(connection)
        chain_values = tuple(sorted(chain.value for chain in chains))
        placeholders = ",".join("?" for _ in chain_values)
        rows = connection.execute(
            f"""
            SELECT p.id AS physical_store_id,
                   p.external_store_id AS physical_store_external_id,
                   p.chain,
                   m.provider_context_id,
                   m.provider_store_id,
                   m.confidence,
                   m.verified_identity_fingerprint,
                   l.coverage,
                   l.price_context_type,
                   l.snapshot_id,
                   l.observed_at
            FROM provider_store_identity_mappings AS m
            JOIN physical_stores AS p
              ON p.id = m.physical_store_id
            JOIN store_context_links AS l
              ON l.physical_store_id = m.physical_store_id
             AND l.grocery_context_id = m.provider_context_id
             AND l.source_provider = m.provider
            WHERE lower(trim(p.city)) = lower(trim(?))
              AND p.chain IN ({placeholders})
              AND p.is_active = 1
              AND m.provider = 'primat'
              AND m.status = 'verified'
              AND m.confidence IN (
                  'exact_id', 'exact_address', 'exact_name_and_postal', 'strong_geo'
              )
              AND m.is_active = 1
              AND l.source_provider = 'primat'
              AND l.source_channel = 'catalog'
              AND l.relation_type = 'exact_store_online_context'
              AND l.coverage IN ('full_catalog', 'full_online_catalog')
              AND l.basket_eligible = 1
              AND l.offers_only = 0
              AND l.is_active = 1
            ORDER BY p.chain, p.external_store_id, m.provider_context_id
            """,
            (city.strip(), *chain_values),
        )
        contexts: list[EligiblePrimatContext] = []
        for row in rows:
            observed_at = _aware_timestamp(row["observed_at"])
            age_hours = Decimal(
                str((evaluated_at - observed_at).total_seconds() / 3600)
            )
            if age_hours < 0:
                continue
            contexts.append(
                EligiblePrimatContext(
                    physical_store_id=str(row["physical_store_id"]),
                    physical_store_external_id=str(
                        row["physical_store_external_id"] or ""
                    ),
                    provider_context_id=str(row["provider_context_id"] or ""),
                    provider_store_id=str(row["provider_store_id"] or ""),
                    chain=Chain(str(row["chain"])),
                    coverage=CoverageLevel(str(row["coverage"])),
                    price_context_type=PriceContextType(str(row["price_context_type"])),
                    confidence=StoreIdentityMatchConfidence(str(row["confidence"])),
                    verified_identity_fingerprint=str(
                        row["verified_identity_fingerprint"] or ""
                    ),
                    snapshot_id=str(row["snapshot_id"] or ""),
                    observed_at=observed_at,
                    data_age_hours=age_hours,
                )
            )
    finally:
        connection.close()
    context_ids = [row.provider_context_id for row in contexts]
    physical_ids = [row.physical_store_id for row in contexts]
    if len(set(context_ids)) != len(context_ids) or len(set(physical_ids)) != len(
        physical_ids
    ):
        raise ValueError("eligible Primat context scope contains duplicate identities")
    return tuple(contexts)


def revalidate_primat_contexts(
    resolution: PrimatStoreResolution,
    eligible: Sequence[EligiblePrimatContext],
    *,
    city: str = "Lund",
) -> tuple[RevalidatedPrimatContext, ...]:
    """Bind persisted eligibility to current request facts without fuzzy matching."""

    if not eligible:
        raise ValueError("no eligible Primat contexts were supplied")
    if (resolution.place_city or "").casefold().strip() != city.casefold().strip():
        raise ValueError("current Primat resolution does not prove the requested city")
    discovery = primat_store_discovery_bundle(resolution)
    candidates = {row.provider_context_id: row for row in discovery.items}
    current_stores: dict[str, Store] = {}
    for store in resolution.stores:
        context_id = (
            store.store_id
            if store.store_id.startswith("primat:")
            else f"primat:{store.store_id}"
        )
        if context_id in current_stores:
            raise ValueError("current Primat resolution contains a duplicate context")
        current_stores[context_id] = store

    revalidated: list[RevalidatedPrimatContext] = []
    for persisted in eligible:
        candidate = candidates.get(persisted.provider_context_id)
        store = current_stores.get(persisted.provider_context_id)
        if candidate is None or store is None:
            raise ValueError("eligible Primat context disappeared from current resolution")
        if (
            candidate.chain != persisted.chain
            or candidate.provider_store_id != persisted.provider_store_id
            or candidate.identity_fingerprint
            != persisted.verified_identity_fingerprint
            or candidate.coverage != persisted.coverage
            or candidate.price_context_type != persisted.price_context_type
            or not is_complete_catalog_coverage(candidate.coverage or "")
        ):
            raise ValueError("eligible Primat context drifted or lost full coverage")
        provenance = store.source_provenance
        if (
            store.source_store_id != persisted.provider_store_id
            or provenance is None
            or provenance.source_provider != "primat"
            or provenance.source_channel != "catalog"
            or provenance.source_snapshot_id != resolution.source_snapshot_id
            or provenance.source_observed_at != resolution.observed_at
            or provenance.store_id != store.store_id
        ):
            raise ValueError("current Primat context lacks request-scoped provenance")
        revalidated.append(RevalidatedPrimatContext(eligible=persisted, store=store))
    return tuple(revalidated)


def _normalized_store(
    context: RevalidatedPrimatContext,
) -> Store:
    persisted = context.eligible
    store = context.store
    provenance = store.source_provenance
    assert provenance is not None
    normalized_provenance = provenance.model_copy(
        update={
            "coverage": persisted.coverage.value,
            "price_context": persisted.price_context_type.value,
            "price_context_evidence": provenance.price_context_evidence.assigned(
                "persisted_grocery_context") if provenance.price_context_evidence else None,
            "store_id": store.store_id,
        }
    )
    return store.model_copy(
        update={
            "coverage": persisted.coverage.value,
            "tier": persisted.coverage.value,
            "price_context_type": persisted.price_context_type.value,
            "physical_store_external_id": persisted.physical_store_external_id,
            "source_provenance": normalized_provenance,
        }
    )


def _normalized_product(
    product: Product,
    *,
    context: RevalidatedPrimatContext,
    resolution: PrimatStoreResolution,
) -> Product:
    persisted = context.eligible
    provenance = product.source_provenance
    expected_store = context.store
    if (
        product.store_id != expected_store.store_id
        or product.chain != persisted.chain.value
        or provenance is None
        or provenance.source_provider != "primat"
        or provenance.source_channel != "catalog"
        or provenance.source_snapshot_id != resolution.source_snapshot_id
        or provenance.source_observed_at != resolution.observed_at
        or provenance.store_id != product.store_id
        or provenance.provider_store_id != persisted.provider_store_id
    ):
        raise ValueError("Primat cache product lacks request-scoped context provenance")
    normalized_provenance: SourceProvenance = provenance.model_copy(
        update={
            "coverage": persisted.coverage.value,
            "price_context": persisted.price_context_type.value,
            "price_context_evidence": provenance.price_context_evidence.assigned(
                "persisted_grocery_context") if provenance.price_context_evidence else None,
        }
    )
    return product.model_copy(
        update={
            "coverage": persisted.coverage.value,
            "price_context_type": persisted.price_context_type.value,
            "source_provenance": normalized_provenance,
        }
    )


def build_frozen_external_cache(
    resolution: PrimatStoreResolution,
    contexts: Sequence[RevalidatedPrimatContext],
    products: Sequence[Product],
) -> FrozenExternalCacheBundle:
    """Deduplicate an exact request scope and emit the existing closed schema."""

    if not contexts:
        raise ValueError("frozen external cache requires at least one context")
    by_native_store = {row.store.store_id: row for row in contexts}
    if len(by_native_store) != len(contexts):
        raise ValueError("frozen external cache contains duplicate stores")
    normalized: dict[tuple[str, str], Product] = {}
    serialized: dict[tuple[str, str], str] = {}
    for product in products:
        context = by_native_store.get(product.store_id)
        if context is None:
            raise ValueError("Primat cache product falls outside the eligible context scope")
        row = _normalized_product(product, context=context, resolution=resolution)
        key = (row.store_id, row.product_id)
        payload = json.dumps(
            row.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        previous = serialized.get(key)
        if previous is not None and previous != payload:
            raise ValueError("same Primat product changed during bounded collection")
        serialized[key] = payload
        normalized[key] = row
    if not normalized:
        raise ValueError("bounded Primat ingredient collection returned no products")
    represented = {store_id for store_id, _product_id in normalized}
    if represented != set(by_native_store):
        raise ValueError("bounded Primat collection returned no products for one context")
    return FrozenExternalCacheBundle(
        postal_code=resolution.postal_code,
        captured_at=resolution.observed_at,
        stores=tuple(
            _normalized_store(row)
            for row in sorted(contexts, key=lambda item: item.store.store_id)
        ),
        products=tuple(normalized[key] for key in sorted(normalized)),
    )


__all__ = [
    "CanonicalIngredientQuery",
    "CanonicalIngredientQuerySurface",
    "EligiblePrimatContext",
    "RevalidatedPrimatContext",
    "build_frozen_external_cache",
    "canonical_ingredient_query_surface",
    "load_eligible_primat_contexts",
    "revalidate_primat_contexts",
]
