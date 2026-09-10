"""Credential-free Phase-C exports from one bounded Primat request scope.

The live provider owns authentication.  This module receives parsed ``Store``
and ``Product`` domain rows only, maps selected customer contexts to the
official physical-store registry without fuzzy names, and writes two closed
replay artefacts:

* ``grocery-context-evidence-bundle-v1`` for store/context reconciliation;
* ``lund-frozen-external-v1`` for the socket-disabled Lund benchmark.

No request headers, cookies, URL parameters, API credentials or raw responses
are accepted by the export models.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from app.errors import PriceProviderError
from app.models import Product, SourceProvenance, Store
from app.providers.primat import PrimatPriceProvider
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from grocery_data.app.domain import Chain, ConnectorStatus, CoverageLevel, PriceContextType
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.domain.store import PhysicalStore
from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.store_context_reconciliation import (
    CredentialFreeContextBundle as ContextEvidenceBundle,
)
from grocery_data.app.services.store_context_reconciliation import (
    CredentialFreeContextExport,
    CredentialFreePhysicalIdentity,
    PhysicalIdentityBasis,
)

TARGET_EXTERNAL_CHAINS = frozenset({Chain.ICA, Chain.COOP, Chain.LIDL})
_FULL_COVERAGE_VALUES = frozenset(
    {
        "full",
        CoverageLevel.FULL_CATALOG.value,
        CoverageLevel.FULL_ONLINE_CATALOG.value,
    }
)
_FORBIDDEN_KEY = re.compile(
    r"(?:authorization|cookie|set[_-]?cookie|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|session|clearance)",
    flags=re.IGNORECASE,
)


class PrimatPhaseCInvariant(StrEnum):
    """Closed diagnostic vocabulary; values cannot contain provider payload data."""

    REGISTRY_TIMESTAMP_NAIVE = "registry_timestamp_naive"
    REGISTRY_ALIASES_INVALID = "registry_aliases_invalid"
    REGISTRY_SCHEMA_MISSING = "registry_schema_missing"
    CONTEXTS_NOT_RESOLVED = "contexts_not_resolved"
    RESOLVE_REENTRY = "resolve_reentry"
    REQUIRED_CHAIN_MISSING = "required_chain_missing"
    IDENTITY_ID_AMBIGUOUS = "identity_id_ambiguous"
    IDENTITY_ADDRESS_AMBIGUOUS = "identity_address_ambiguous"
    IDENTITY_COORDINATES_AMBIGUOUS = "identity_coordinates_ambiguous"
    IDENTITY_NO_EXACT_MATCH = "identity_no_exact_match"
    PHYSICAL_CONTEXT_DUPLICATE = "physical_context_duplicate"
    COVERAGE_NOT_FULL = "coverage_not_full"
    PRICE_CONTEXT_TYPE_UNKNOWN = "price_context_type_unknown"
    CATALOG_PROVENANCE_INVALID = "catalog_provenance_invalid"
    CONTEXT_SCHEMA_INVALID = "context_schema_invalid"
    BUNDLE_SCHEMA_INVALID = "bundle_schema_invalid"
    CACHE_PRODUCTS_MISSING = "cache_products_missing"
    CACHE_PRODUCT_PROVENANCE_INVALID = "cache_product_provenance_invalid"
    CACHE_PRODUCT_SCOPE_MISMATCH = "cache_product_scope_mismatch"
    SANITIZATION_FORBIDDEN_KEY = "sanitization_forbidden_key"
    SANITIZATION_CREDENTIAL_VALUE = "sanitization_credential_value"
    EXPLICIT_OPT_IN_MISSING = "explicit_opt_in_missing"
    TRANSPORT_CONTRACT_INVALID = "transport_contract_invalid"
    IMMUTABLE_DATABASE_CHANGED = "immutable_database_changed"


class PrimatPhaseCExportError(PriceProviderError):
    """The bounded export could not prove a closed, exact snapshot."""

    def __init__(
        self,
        message: str,
        *,
        invariant: PrimatPhaseCInvariant,
        chain: Chain | None = None,
    ) -> None:
        super().__init__(message)
        self.invariant = invariant
        self.chain = chain

    @property
    def safe_error_code(self) -> str:
        """Return an allowlisted diagnostic containing no source identifiers."""

        suffix = f"_{self.chain.value}" if self.chain is not None else ""
        return f"export_contract_{self.invariant.value}{suffix}"


class FrozenExternalCacheBundle(BaseModel):
    """Closed benchmark cache containing parsed, consumer-safe domain rows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["lund-frozen-external-v1"] = "lund-frozen-external-v1"
    postal_code: str = Field(pattern=r"^\d{5}$")
    captured_at: datetime
    stores: tuple[Store, ...]
    products: tuple[Product, ...]


@dataclass(frozen=True, slots=True)
class ExactPrimatContext:
    """One selected provider context with independently verified identity."""

    store: Store
    physical_store: PhysicalStore
    identity: CredentialFreePhysicalIdentity
    export: CredentialFreeContextExport


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def _normalized_address(value: str | None) -> str:
    return re.sub(r"[^0-9a-zåäö]+", " ", (value or "").casefold()).strip()


def _aware(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        raise PrimatPhaseCExportError(
            "physical-store registry has a naive timestamp",
            invariant=PrimatPhaseCInvariant.REGISTRY_TIMESTAMP_NAIVE,
        )
    return parsed.astimezone(UTC)


def _aliases(value: object) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    parsed = json.loads(str(value)) if isinstance(value, str) else value
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise PrimatPhaseCExportError(
            "physical-store registry has invalid external aliases",
            invariant=PrimatPhaseCInvariant.REGISTRY_ALIASES_INVALID,
        )
    return tuple(parsed)


def load_active_physical_stores(
    database: Path,
    *,
    city: str = "Lund",
) -> tuple[PhysicalStore, ...]:
    """Read the official registry through immutable, query-only SQLite."""

    resolved = database.resolve(strict=True)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(physical_stores)")}
        required = {
            "id",
            "chain",
            "external_store_id",
            "external_store_aliases",
            "name",
            "address",
            "postal_code",
            "city",
            "latitude",
            "longitude",
            "official_source",
            "discovered_at",
            "last_seen_at",
            "is_active",
            "lifecycle_state",
            "not_seen_at",
        }
        missing = sorted(required - columns)
        if missing:
            raise PrimatPhaseCExportError(
                "physical-store registry is missing columns: " + ", ".join(missing),
                invariant=PrimatPhaseCInvariant.REGISTRY_SCHEMA_MISSING,
            )
        rows = connection.execute(
            """
            SELECT id, chain, external_store_id, external_store_aliases, name,
                   address, postal_code, city, latitude, longitude,
                   official_source, discovered_at, last_seen_at, is_active,
                   lifecycle_state, not_seen_at
            FROM physical_stores
            WHERE is_active = 1 AND lower(trim(city)) = lower(trim(?))
            ORDER BY chain, name, id
            """,
            (city,),
        )
        return tuple(
            PhysicalStore(
                id=str(row["id"]),
                chain=Chain(str(row["chain"])),
                external_store_id=(
                    str(row["external_store_id"]) if row["external_store_id"] is not None else None
                ),
                external_store_aliases=_aliases(row["external_store_aliases"]),
                name=str(row["name"]),
                address=str(row["address"]) if row["address"] is not None else None,
                postal_code=(str(row["postal_code"]) if row["postal_code"] is not None else None),
                city=str(row["city"]) if row["city"] is not None else None,
                latitude=(Decimal(str(row["latitude"])) if row["latitude"] is not None else None),
                longitude=(
                    Decimal(str(row["longitude"])) if row["longitude"] is not None else None
                ),
                official_source=str(row["official_source"]),
                discovered_at=_aware(row["discovered_at"]),
                last_seen_at=_aware(row["last_seen_at"]),
                active=True,
                lifecycle_state=str(row["lifecycle_state"]),
                not_seen_at=(
                    _aware(row["not_seen_at"]) if row["not_seen_at"] is not None else None
                ),
            )
            for row in rows
        )
    finally:
        connection.close()


def _provider_native_ids(store: Store) -> frozenset[str]:
    provenance = store.source_provenance
    values = {
        store.source_store_id,
        provenance.provider_store_id if provenance is not None else None,
    }
    if ":" in store.store_id:
        values.add(store.store_id.rsplit(":", 1)[-1])
    else:
        values.add(store.store_id)
    return frozenset(value for value in values if value)


def _physical_ids(store: PhysicalStore) -> frozenset[str]:
    return frozenset(
        value for value in (store.external_store_id, *store.external_store_aliases) if value
    )


def _exact_identity(
    store: Store,
    candidates: Sequence[PhysicalStore],
    *,
    chain: Chain,
) -> tuple[PhysicalStore, CredentialFreePhysicalIdentity]:
    """Select one physical site using structured facts; names are never read."""

    native_ids = _provider_native_ids(store)
    id_matches = [row for row in candidates if native_ids & _physical_ids(row)]
    if len(id_matches) == 1:
        matched_id = min(native_ids & _physical_ids(id_matches[0]))
        return id_matches[0], CredentialFreePhysicalIdentity(
            basis=PhysicalIdentityBasis.OFFICIAL_EXTERNAL_ID,
            official_external_store_id=matched_id,
        )
    if len(id_matches) > 1:
        raise PrimatPhaseCExportError(
            f"ambiguous official store ID for Primat context {store.store_id}",
            invariant=PrimatPhaseCInvariant.IDENTITY_ID_AMBIGUOUS,
            chain=chain,
        )

    address = _normalized_address(store.address)
    postal_code = _digits(store.postal_code or "")
    if address and len(postal_code) == 5:
        address_matches = [
            row
            for row in candidates
            if _normalized_address(row.address) == address
            and _digits(row.postal_code or "") == postal_code
        ]
        if len(address_matches) == 1:
            physical = address_matches[0]
            return physical, CredentialFreePhysicalIdentity(
                basis=PhysicalIdentityBasis.OFFICIAL_ADDRESS_POSTAL_CODE,
                address=physical.address,
                postal_code=physical.postal_code,
            )
        if len(address_matches) > 1:
            raise PrimatPhaseCExportError(
                f"ambiguous exact address for Primat context {store.store_id}",
                invariant=PrimatPhaseCInvariant.IDENTITY_ADDRESS_AMBIGUOUS,
                chain=chain,
            )

    if store.latitude is not None and store.longitude is not None:
        latitude = Decimal(str(store.latitude))
        longitude = Decimal(str(store.longitude))
        coordinate_matches = [
            row for row in candidates if row.latitude == latitude and row.longitude == longitude
        ]
        if len(coordinate_matches) == 1:
            physical = coordinate_matches[0]
            return physical, CredentialFreePhysicalIdentity(
                basis=PhysicalIdentityBasis.OFFICIAL_COORDINATES,
                latitude=physical.latitude,
                longitude=physical.longitude,
            )
        if len(coordinate_matches) > 1:
            raise PrimatPhaseCExportError(
                f"ambiguous exact coordinates for Primat context {store.store_id}",
                invariant=PrimatPhaseCInvariant.IDENTITY_COORDINATES_AMBIGUOUS,
                chain=chain,
            )
    raise PrimatPhaseCExportError(
        f"Primat context {store.store_id} has no exact official Lund identity",
        invariant=PrimatPhaseCInvariant.IDENTITY_NO_EXACT_MATCH,
        chain=chain,
    )


def _full_coverage(store: Store, *, chain: Chain) -> CoverageLevel:
    value = str(store.coverage or store.tier or "").strip().casefold()
    if value not in _FULL_COVERAGE_VALUES:
        raise PrimatPhaseCExportError(
            f"Primat context {store.store_id} does not declare full catalog coverage",
            invariant=PrimatPhaseCInvariant.COVERAGE_NOT_FULL,
            chain=chain,
        )
    return (
        CoverageLevel.FULL_ONLINE_CATALOG
        if value == CoverageLevel.FULL_ONLINE_CATALOG.value
        else CoverageLevel.FULL_CATALOG
    )


def _context_type(store: Store, *, chain: Chain) -> PriceContextType:
    if store.price_context_type:
        try:
            return PriceContextType(store.price_context_type)
        except ValueError as exc:
            raise PrimatPhaseCExportError(
                f"Primat context {store.store_id} has an unknown price context type",
                invariant=PrimatPhaseCInvariant.PRICE_CONTEXT_TYPE_UNKNOWN,
                chain=chain,
            ) from exc
    # /stores/resolve returned a selected, exact store-scoped catalog context.
    # This classifies that provider context; it does not claim online parity or
    # manufacture a shelf-price observation for another physical site.
    return PriceContextType.PHYSICAL_STORE


def _verified_provenance(store: Store, *, chain: Chain) -> SourceProvenance:
    provenance = store.source_provenance
    if (
        provenance is None
        or provenance.source_provider != SourceProvider.PRIMAT.value
        or provenance.source_channel != SourceChannel.CATALOG.value
        or provenance.source_observed_at.tzinfo is None
        or provenance.chain != store.chain.casefold()
        or provenance.store_id != store.store_id
        or provenance.provider_store_id not in _provider_native_ids(store)
    ):
        raise PrimatPhaseCExportError(
            f"Primat context {store.store_id} lacks replayable catalog provenance",
            invariant=PrimatPhaseCInvariant.CATALOG_PROVENANCE_INVALID,
            chain=chain,
        )
    return provenance


class BoundedPrimatPhaseCExporter:
    """Resolve once, map exactly, then freeze only the request-local cache."""

    def __init__(
        self,
        provider: PrimatPriceProvider,
        physical_stores: Sequence[PhysicalStore],
        *,
        postal_code: str = "22350",
        required_chains: frozenset[Chain] = TARGET_EXTERNAL_CHAINS,
    ) -> None:
        digits = _digits(postal_code)
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        self.provider = provider
        self.postal_code = digits
        self.required_chains = required_chains
        self._physical_stores = tuple(
            row
            for row in physical_stores
            if row.active and row.chain in required_chains and (row.city or "").casefold() == "lund"
        )
        self._resolve_attempted = False
        self._contexts: tuple[ExactPrimatContext, ...] | None = None

    @property
    def resolve_requests(self) -> int:
        return int(self._resolve_attempted)

    @property
    def contexts(self) -> tuple[ExactPrimatContext, ...]:
        if self._contexts is None:
            raise PrimatPhaseCExportError(
                "Primat contexts have not been resolved",
                invariant=PrimatPhaseCInvariant.CONTEXTS_NOT_RESOLVED,
            )
        return self._contexts

    async def resolve_once(self) -> tuple[ExactPrimatContext, ...]:
        if self._contexts is not None:
            return self._contexts
        if self._resolve_attempted:
            raise PrimatPhaseCExportError(
                "Primat context resolve already failed; retry refused",
                invariant=PrimatPhaseCInvariant.RESOLVE_REENTRY,
            )
        self._resolve_attempted = True
        stores = await self.provider.find_stores(self.postal_code)
        selected: list[Store] = []
        for store in stores:
            try:
                chain = Chain(store.chain.casefold())
            except ValueError:
                continue
            if chain in self.required_chains:
                selected.append(store)
        present_chains = {Chain(store.chain.casefold()) for store in selected}
        missing_chains = sorted(chain.value for chain in self.required_chains - present_chains)
        if missing_chains:
            missing_chain = Chain(missing_chains[0])
            raise PrimatPhaseCExportError(
                "selected Primat contexts are missing required chains: "
                + ", ".join(missing_chains),
                invariant=PrimatPhaseCInvariant.REQUIRED_CHAIN_MISSING,
                chain=missing_chain,
            )

        contexts: list[ExactPrimatContext] = []
        used_physical_ids: set[str] = set()
        for store in sorted(selected, key=lambda row: (row.chain.casefold(), row.store_id)):
            chain = Chain(store.chain.casefold())
            candidates = [row for row in self._physical_stores if row.chain == chain]
            physical, identity = _exact_identity(store, candidates, chain=chain)
            if physical.id in used_physical_ids:
                raise PrimatPhaseCExportError(
                    f"multiple selected Primat contexts map to {physical.id}",
                    invariant=PrimatPhaseCInvariant.PHYSICAL_CONTEXT_DUPLICATE,
                    chain=chain,
                )
            used_physical_ids.add(physical.id)
            provenance = _verified_provenance(store, chain=chain)
            context_id = (
                store.store_id
                if store.store_id.startswith("primat:")
                else f"primat:{store.store_id}"
            )
            try:
                export = CredentialFreeContextExport(
                    schema_version="grocery-context-evidence-v1",
                    provider=SourceProvider.PRIMAT,
                    source_channel=SourceChannel.CATALOG,
                    context_id=context_id,
                    chain=chain,
                    name=store.name,
                    city=physical.city,
                    price_context_type=_context_type(store, chain=chain),
                    coverage=_full_coverage(store, chain=chain),
                    source_snapshot_id=provenance.source_snapshot_id,
                    source_observed_at=provenance.source_observed_at,
                    connector_status=ConnectorStatus.HEALTHY,
                    active=True,
                    physical_identity=identity,
                )
            except ValidationError as exc:
                raise PrimatPhaseCExportError(
                    "mapped Primat context does not satisfy the closed export schema",
                    invariant=PrimatPhaseCInvariant.CONTEXT_SCHEMA_INVALID,
                    chain=chain,
                ) from exc
            contexts.append(
                ExactPrimatContext(
                    store=store,
                    physical_store=physical,
                    identity=identity,
                    export=export,
                )
            )
        self._contexts = tuple(contexts)
        return self._contexts

    def context_bundle(self) -> ContextEvidenceBundle:
        contexts = self.contexts
        captured_at = max(
            item.export.source_observed_at for item in contexts if item.export.source_observed_at
        )
        try:
            return ContextEvidenceBundle(
                schema_version="grocery-context-evidence-bundle-v1",
                postal_code=self.postal_code,
                captured_at=captured_at,
                items=tuple(item.export for item in contexts),
            )
        except ValidationError as exc:
            raise PrimatPhaseCExportError(
                "mapped Primat contexts do not satisfy the closed bundle schema",
                invariant=PrimatPhaseCInvariant.BUNDLE_SCHEMA_INVALID,
            ) from exc

    def frozen_external_cache(self) -> FrozenExternalCacheBundle:
        contexts = self.contexts
        by_store_id = {item.store.store_id: item for item in contexts}
        products = tuple(
            self._normalized_product(product, by_store_id[product.store_id])
            for product in self.provider.request_scoped_product_snapshot()
            if product.store_id in by_store_id
        )
        if not products:
            raise PrimatPhaseCExportError(
                "Primat request cache contains no mapped products",
                invariant=PrimatPhaseCInvariant.CACHE_PRODUCTS_MISSING,
            )
        stores = tuple(self._normalized_store(item) for item in contexts)
        captured_at = max(
            item.source_provenance.source_observed_at
            for item in stores
            if item.source_provenance is not None
        )
        return FrozenExternalCacheBundle(
            postal_code=self.postal_code,
            captured_at=captured_at,
            stores=stores,
            products=products,
        )

    @staticmethod
    def _normalized_store(context: ExactPrimatContext) -> Store:
        store = context.store
        chain = context.export.chain
        provenance = _verified_provenance(store, chain=chain).model_copy(
            update={
                "coverage": context.export.coverage.value,
                "price_context": _context_type(store, chain=chain).value,
                "store_id": store.store_id,
            }
        )
        return store.model_copy(
            update={
                "coverage": context.export.coverage.value,
                "tier": context.export.coverage.value,
                "price_context_type": _context_type(store, chain=chain).value,
                "physical_store_external_id": context.physical_store.external_store_id,
                "source_provenance": provenance,
            }
        )

    @staticmethod
    def _normalized_product(product: Product, context: ExactPrimatContext) -> Product:
        provenance = product.source_provenance
        if (
            provenance is None
            or provenance.source_provider != SourceProvider.PRIMAT.value
            or provenance.source_channel != SourceChannel.CATALOG.value
        ):
            raise PrimatPhaseCExportError(
                f"cached product {product.product_id} lacks Primat catalog provenance",
                invariant=PrimatPhaseCInvariant.CACHE_PRODUCT_PROVENANCE_INVALID,
                chain=context.export.chain,
            )
        context_provenance = _verified_provenance(
            context.store,
            chain=context.export.chain,
        )
        if provenance.source_snapshot_id != context_provenance.source_snapshot_id:
            raise PrimatPhaseCExportError(
                f"cached product {product.product_id} belongs to another request scope",
                invariant=PrimatPhaseCInvariant.CACHE_PRODUCT_SCOPE_MISMATCH,
                chain=context.export.chain,
            )
        normalized_provenance = provenance.model_copy(
            update={
                "coverage": context.export.coverage.value,
                "price_context": _context_type(
                    context.store,
                    chain=context.export.chain,
                ).value,
            }
        )
        return product.model_copy(
            update={
                "coverage": context.export.coverage.value,
                "price_context_type": _context_type(
                    context.store,
                    chain=context.export.chain,
                ).value,
                "source_provenance": normalized_provenance,
            }
        )


def _assert_sanitized(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if _FORBIDDEN_KEY.search(key_text):
                raise PrimatPhaseCExportError(
                    f"forbidden export key at {path}.{key_text}",
                    invariant=PrimatPhaseCInvariant.SANITIZATION_FORBIDDEN_KEY,
                )
            _assert_sanitized(nested, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _assert_sanitized(nested, path=f"{path}[{index}]")
    elif isinstance(value, str) and "bearer " in value.casefold():
        raise PrimatPhaseCExportError(
            f"credential-shaped value at {path}",
            invariant=PrimatPhaseCInvariant.SANITIZATION_CREDENTIAL_VALUE,
        )


def write_closed_json(path: Path, bundle: BaseModel) -> dict[str, Any]:
    """Validate, write atomically, and return credential-free file metrics."""

    payload = bundle.model_dump(mode="json", by_alias=True)
    _assert_sanitized(payload)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    destination = path.resolve()
    atomic_write_bytes(
        destination,
        encoded,
        reserve_bytes=64 * 1024 * 1024,
        validator=lambda candidate: json.loads(candidate.read_bytes()),
    )
    return {
        "path": str(destination),
        "bytes": len(encoded),
        "credentials_included": False,
        "headers_included": False,
        "cookies_included": False,
        "raw_responses_included": False,
    }


__all__ = [
    "TARGET_EXTERNAL_CHAINS",
    "BoundedPrimatPhaseCExporter",
    "ContextEvidenceBundle",
    "ExactPrimatContext",
    "FrozenExternalCacheBundle",
    "PrimatPhaseCExportError",
    "PrimatPhaseCInvariant",
    "load_active_physical_stores",
    "write_closed_json",
]
