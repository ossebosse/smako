"""Prebuilt, snapshot-bound product indexes and request-safe calculation caches.

The price universe is deliberately a pure local-data abstraction.  Building or
querying one can never call a grocery chain or provider.  Collection code owns
snapshot promotion; this module turns an already eligible product sequence into
an immutable, deterministic search surface which can be atomically activated.

The caches in this module are opt-in building blocks.  Their keys retain the
universe identity and every checkout-relevant input, so a caller cannot reuse
semantic, package or basket work across a changed snapshot or pricing context.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from time import perf_counter
from types import MappingProxyType

from app.models.basket import OptimizedBasket
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    Product,
    ProductCandidate,
    SaleModel,
    SemanticConfidence,
)
from app.services.basket_calculator import BasketItemQuote
from app.services.ingredient_normalizer import (
    CANONICAL_ALIASES,
    RECIPE_CANONICAL_TO_MATCHER_CANONICAL,
    canonicalize_ingredient_name,
    normalize_quantity,
)
from app.services.performance_trace import (
    increment_performance_counter,
    performance_span,
)
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

_CONFIDENCE_RANK = {
    SemanticConfidence.REJECTED: 0,
    SemanticConfidence.LOW: 1,
    SemanticConfidence.MEDIUM: 2,
    SemanticConfidence.HIGH: 3,
    SemanticConfidence.EXACT: 4,
}
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+/-]{0,127}$")
_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
_KNOWN_CANONICAL_KEYS = frozenset(
    {
        *(canonicalize_ingredient_name(value) for value in CANONICAL_ALIASES),
        *(
            canonicalize_ingredient_name(value)
            for value in RECIPE_CANONICAL_TO_MATCHER_CANONICAL.values()
        ),
    }
)


class PriceUniverseError(RuntimeError):
    """Base error for an invalid or unsafe universe operation."""


class IneligibleMemberPriceError(PriceUniverseError):
    """A disabled membership appears to drive a product's checkout price."""


class PriceUniverseValidationError(PriceUniverseError):
    """A candidate universe failed validation and was not activated."""


class MembershipSetting(BaseModel):
    """One normalized membership bit used in the universe identity."""

    model_config = ConfigDict(frozen=True)

    chain: str = Field(min_length=1)
    enabled: bool = False

    @field_validator("chain")
    @classmethod
    def normalize_chain(cls, value: str) -> str:
        normalized = value.casefold().strip()
        if not normalized:
            raise ValueError("chain must not be blank")
        return normalized


class PriceUniverseKey(BaseModel):
    """Every input which can change a prebuilt price universe.

    Snapshot identifiers are intentionally part of the key instead of their
    ages.  Freshness decides whether a snapshot is eligible *before* a build;
    time passing must not mutate an already built universe's identity.
    """

    model_config = ConfigDict(frozen=True)

    city: str = Field(min_length=1)
    postal_codes: tuple[str, ...] = ()
    snapshot_ids: tuple[str, ...] = Field(min_length=1)
    memberships: tuple[MembershipSetting, ...] = Field(
        default=(),
        description=(
            "Deprecated compatibility vector. New shared artifacts keep this "
            "all-false and retain member contracts for request-time resolution."
        ),
    )
    source_strategy_version: str = Field(min_length=1)
    normalizer_version: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        normalized = " ".join(value.casefold().split())
        if not normalized:
            raise ValueError("city must not be blank")
        return normalized

    @field_validator("postal_codes")
    @classmethod
    def normalize_postal_codes(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = {
            re.sub(r"\s+", "", str(value)).casefold() for value in values if str(value).strip()
        }
        return tuple(sorted(normalized))

    @field_validator("snapshot_ids")
    @classmethod
    def normalize_snapshots(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = {str(value).strip() for value in values if str(value).strip()}
        if not normalized:
            raise ValueError("at least one snapshot_id is required")
        return tuple(sorted(normalized))

    @field_validator("memberships")
    @classmethod
    def normalize_memberships(
        cls, values: tuple[MembershipSetting, ...]
    ) -> tuple[MembershipSetting, ...]:
        by_chain: dict[str, MembershipSetting] = {}
        for value in values:
            if value.chain in by_chain:
                raise ValueError(f"duplicate membership setting for {value.chain}")
            by_chain[value.chain] = value
        return tuple(by_chain[key] for key in sorted(by_chain))

    @field_validator(
        "source_strategy_version",
        "normalizer_version",
        "taxonomy_version",
    )
    @classmethod
    def validate_version(cls, value: str) -> str:
        normalized = value.strip()
        if not _VERSION_PATTERN.fullmatch(normalized):
            raise ValueError("version must be a short stable identifier")
        return normalized

    @classmethod
    def create(
        cls,
        *,
        city: str,
        snapshot_ids: Iterable[str],
        memberships: Mapping[str, bool] | None = None,
        source_strategy_version: str,
        normalizer_version: str,
        taxonomy_version: str,
        postal_codes: Iterable[str] = (),
    ) -> PriceUniverseKey:
        return cls(
            city=city,
            postal_codes=tuple(postal_codes),
            snapshot_ids=tuple(snapshot_ids),
            memberships=tuple(
                MembershipSetting(chain=chain, enabled=enabled)
                for chain, enabled in (memberships or {}).items()
            ),
            source_strategy_version=source_strategy_version,
            normalizer_version=normalizer_version,
            taxonomy_version=taxonomy_version,
        )

    @property
    def scope_id(self) -> str:
        """Operational area slot used for atomic activation and status lookup."""

        return f"city:{self.city}"

    @property
    def geographic_scope_id(self) -> str:
        """Diagnostic city/postal scope; postal codes remain in the identity digest."""

        postal = ",".join(self.postal_codes) or "*"
        return f"city:{self.city}|postal:{postal}"

    @property
    def scope(self) -> str:
        """Compatibility alias used by refresh composition hooks."""

        return self.scope_id

    @property
    def membership_map(self) -> Mapping[str, bool]:
        return {row.chain: row.enabled for row in self.memberships}

    def membership_enabled(self, chain: str | None) -> bool:
        return self.membership_map.get((chain or "").casefold().strip(), False)

    def identity_payload(self) -> dict[str, object]:
        return {
            "city": self.city,
            "postal_codes": list(self.postal_codes),
            "snapshot_ids": list(self.snapshot_ids),
            "memberships": [
                {"chain": row.chain, "enabled": row.enabled} for row in self.memberships
            ],
            "source_strategy_version": self.source_strategy_version,
            "normalizer_version": self.normalizer_version,
            "taxonomy_version": self.taxonomy_version,
        }

    @property
    def digest(self) -> str:
        return _json_digest(self.identity_payload())

    @property
    def universe_id(self) -> str:
        return f"price-universe:{self.digest}"


class IndexEntry(BaseModel):
    """Serialization-friendly immutable entry in a product index."""

    model_config = ConfigDict(frozen=True)

    key: str = Field(min_length=1)
    product_indexes: tuple[int, ...]

    @field_validator("product_indexes")
    @classmethod
    def validate_indexes(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        normalized = tuple(sorted(set(values)))
        if any(value < 0 for value in normalized):
            raise ValueError("product indexes must not be negative")
        return normalized


class StoreAvailabilityEntry(BaseModel):
    """Bitset of contexts which can satisfy one canonical ingredient."""

    model_config = ConfigDict(frozen=True)

    canonical: str = Field(min_length=1)
    context_mask: int = Field(ge=0)


class PriceUniverseIndexes(BaseModel):
    """Compact indexes containing positions in ``PriceUniverse.products``."""

    model_config = ConfigDict(frozen=True)

    canonical: tuple[IndexEntry, ...] = ()
    gtin: tuple[IndexEntry, ...] = ()
    chain: tuple[IndexEntry, ...] = ()
    context: tuple[IndexEntry, ...] = ()
    category: tuple[IndexEntry, ...] = ()
    role: tuple[IndexEntry, ...] = ()
    purchase_model: tuple[IndexEntry, ...] = ()
    name_token: tuple[IndexEntry, ...] = ()
    context_order: tuple[str, ...] = ()
    store_availability: tuple[StoreAvailabilityEntry, ...] = ()
    _lookups: Mapping[str, Mapping[str, tuple[int, ...]]] = PrivateAttr()
    _availability_lookup: Mapping[str, int] = PrivateAttr()

    def model_post_init(self, _context: object) -> None:
        lookups = {
            field_name: MappingProxyType(
                {entry.key: entry.product_indexes for entry in getattr(self, field_name)}
            )
            for field_name in (
                "canonical",
                "gtin",
                "chain",
                "context",
                "category",
                "role",
                "purchase_model",
                "name_token",
            )
        }
        self._lookups = MappingProxyType(lookups)
        self._availability_lookup = MappingProxyType(
            {entry.canonical: entry.context_mask for entry in self.store_availability}
        )

    @model_validator(mode="after")
    def validate_unique_keys(self) -> PriceUniverseIndexes:
        for field_name in (
            "canonical",
            "gtin",
            "chain",
            "context",
            "category",
            "role",
            "purchase_model",
            "name_token",
        ):
            entries = getattr(self, field_name)
            keys = [entry.key for entry in entries]
            if keys != sorted(set(keys)):
                raise ValueError(f"{field_name} index keys must be unique and sorted")
        canonical = [entry.canonical for entry in self.store_availability]
        if canonical != sorted(set(canonical)):
            raise ValueError("store availability keys must be unique and sorted")
        if self.context_order != tuple(sorted(set(self.context_order))):
            raise ValueError("context_order must be unique and sorted")
        return self

    def positions(self, index_name: str, key: str) -> tuple[int, ...]:
        try:
            return self._lookups[index_name].get(key, ())
        except KeyError as exc:
            raise ValueError(f"unknown product index {index_name!r}") from exc

    def availability_mask(self, canonical: str) -> int:
        return self._availability_lookup.get(canonical, 0)


class PriceUniverseBuildStats(BaseModel):
    """Auditable build and pruning metrics."""

    model_config = ConfigDict(frozen=True)

    raw_products: int = Field(ge=0)
    eligible_products: int = Field(ge=0)
    canonical_mappings_before_pruning: int = Field(ge=0)
    canonical_mappings: int = Field(ge=0)
    canonical_index_count: int = Field(ge=0)
    dominance_pruned: int = Field(ge=0)
    per_context_top_k_pruned: int = Field(ge=0)
    global_top_k_pruned: int = Field(ge=0)
    products_without_canonical: int = Field(ge=0)
    build_time_ms: float = Field(ge=0)

    @property
    def post_pruning_products(self) -> int:
        """Compatibility/readability alias for operational status adapters."""

        return self.canonical_mappings


class PriceUniverse(BaseModel):
    """A deterministic, locally serializable product search surface."""

    model_config = ConfigDict(frozen=True)

    universe_id: str = Field(min_length=1)
    key: PriceUniverseKey
    built_at: datetime
    products_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    products: tuple[Product, ...]
    indexes: PriceUniverseIndexes
    stats: PriceUniverseBuildStats

    @property
    def by_canonical(self) -> Mapping[str, tuple[Product, ...]]:
        """Read-only-style compatibility projection for composition/status code."""

        return {
            entry.key: self.products_at(entry.product_indexes) for entry in self.indexes.canonical
        }

    @model_validator(mode="after")
    def validate_integrity(self) -> PriceUniverse:
        if self.universe_id != self.key.universe_id:
            raise ValueError("universe_id does not match its key")
        if self.built_at.tzinfo is None or self.built_at.utcoffset() is None:
            raise ValueError("built_at must be timezone-aware")
        product_count = len(self.products)
        for field_name in (
            "canonical",
            "gtin",
            "chain",
            "context",
            "category",
            "role",
            "purchase_model",
            "name_token",
        ):
            for entry in getattr(self.indexes, field_name):
                if any(index >= product_count for index in entry.product_indexes):
                    raise ValueError(f"{field_name} index points outside products")
        if self.products_digest != _products_digest(self.products):
            raise ValueError("products_digest does not match universe products")
        return self

    def products_at(self, positions: Iterable[int]) -> tuple[Product, ...]:
        return tuple(self.products[index] for index in positions)

    def products_for_canonical(
        self,
        canonical_ingredient: str,
        *,
        allowed_context_ids: Iterable[str] | None = None,
    ) -> tuple[Product, ...]:
        canonical = _canonical_key(canonical_ingredient)
        positions = self.indexes.positions("canonical", canonical)
        if allowed_context_ids is None:
            return self.products_at(positions)
        allowed = set(allowed_context_ids)
        return tuple(self.products[index] for index in positions if self.products[index].store_id in allowed)

    def products_for_gtin(self, gtin: str) -> tuple[Product, ...]:
        return self.products_at(self.indexes.positions("gtin", gtin.strip()))

    def products_for_context(self, context_id: str) -> tuple[Product, ...]:
        return self.products_at(self.indexes.positions("context", context_id))

    def semantic_prefilter(
        self,
        canonical_ingredient: str,
        *,
        allowed_context_ids: Iterable[str] | None = None,
        lexical_terms: Iterable[str] = (),
    ) -> tuple[Product, ...]:
        """Return a bounded hard-filter surface before fuzzy matching.

        A structured canonical mapping wins.  Token lookup is only a fallback
        for products whose source did not provide a canonical identity; it
        intersects query tokens to avoid broad OR scans.
        """

        canonical = _canonical_key(canonical_ingredient)
        positions = set(self.indexes.positions("canonical", canonical))
        tokens = sorted(
            set(_name_tokens(" ".join((canonical_ingredient, *tuple(lexical_terms)))))
        )
        token_sets = [set(self.indexes.positions("name_token", token)) for token in tokens]
        lexical_positions = (
            set.intersection(*token_sets) if token_sets and all(token_sets) else set()
        )
        # Include lexical rows only when their source lacked a known structured
        # taxonomy identity.  This preserves legacy coverage without bringing
        # every deliberately top-K-pruned structured row back into the pool.
        positions.update(
            index
            for index in lexical_positions
            if not self.products[index].canonical_food
            or _canonical_key(self.products[index].canonical_food) not in _KNOWN_CANONICAL_KEYS
        )
        allowed = set(allowed_context_ids) if allowed_context_ids is not None else None
        return tuple(
            self.products[index]
            for index in sorted(positions)
            if allowed is None or self.products[index].store_id in allowed
        )

    def contexts_for_canonical(self, canonical_ingredient: str) -> tuple[str, ...]:
        canonical = _canonical_key(canonical_ingredient)
        mask = self.indexes.availability_mask(canonical)
        return tuple(
            context_id
            for position, context_id in enumerate(self.indexes.context_order)
            if mask & (1 << position)
        )

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize a local-cache artifact without implementation-only fields."""

        return self.model_dump_json(indent=indent, exclude_computed_fields=True)

    @classmethod
    def from_json(cls, payload: str | bytes) -> PriceUniverse:
        return cls.model_validate_json(payload)


class PriceUniverseBuildConfig(BaseModel):
    """Deterministic pruning limits; ``None`` disables the corresponding cap."""

    model_config = ConfigDict(frozen=True)

    max_products_per_canonical_per_context: int | None = Field(default=10, ge=1)
    max_products_per_canonical_global: int | None = Field(default=50, ge=1)
    dominance_pruning: bool = True
    fail_on_ineligible_member_price: bool = True
    require_provenance: bool = True


class PriceUniverseBuilder:
    """Build all indexes once for one promoted snapshot set."""

    def __init__(self, config: PriceUniverseBuildConfig | None = None) -> None:
        self.config = config or PriceUniverseBuildConfig()

    def build(
        self,
        key: PriceUniverseKey,
        products: Iterable[Product],
        *,
        built_at: datetime | None = None,
    ) -> PriceUniverse:
        with performance_span("build_price_universe"):
            universe = self._build(key, products, built_at=built_at)
        increment_performance_counter("price_universe_raw_products", universe.stats.raw_products)
        increment_performance_counter(
            "price_universe_eligible_products", universe.stats.eligible_products
        )
        increment_performance_counter(
            "price_universe_canonical_mappings", universe.stats.canonical_mappings
        )
        increment_performance_counter(
            "price_universe_products_post_pruning", universe.stats.canonical_mappings
        )
        increment_performance_counter(
            "price_universe_products_pruned",
            universe.stats.dominance_pruned
            + universe.stats.per_context_top_k_pruned
            + universe.stats.global_top_k_pruned,
        )
        return universe

    def _build(
        self,
        key: PriceUniverseKey,
        products: Iterable[Product],
        *,
        built_at: datetime | None = None,
    ) -> PriceUniverse:
        started = perf_counter()
        ordered = tuple(sorted(products, key=_product_sort_key))
        if self.config.require_provenance:
            for product in ordered:
                _validate_product_provenance(key, product)
        if self.config.fail_on_ineligible_member_price:
            for product in ordered:
                if _uses_disabled_member_price(key, product):
                    raise IneligibleMemberPriceError(
                        f"disabled membership appears to drive {product.store_id}/"
                        f"{product.product_id} checkout price"
                    )

        raw_canonical: dict[str, list[int]] = defaultdict(list)
        for index, product in enumerate(ordered):
            if product.canonical_food:
                canonical = _canonical_key(product.canonical_food)
                # Product's backward-compatible model fills a missing source
                # canonical with canonical_name.  Only taxonomy identities are
                # safe for the direct index; arbitrary names remain available
                # through the lexical-token fallback and the semantic gate.
                if canonical in _KNOWN_CANONICAL_KEYS:
                    raw_canonical[canonical].append(index)

        selected_canonical: dict[str, tuple[int, ...]] = {}
        dominance_pruned = 0
        context_pruned = 0
        global_pruned = 0
        for canonical in sorted(raw_canonical):
            positions = tuple(raw_canonical[canonical])
            if self.config.dominance_pruning:
                positions, removed = _dominance_prune(ordered, canonical, positions)
                dominance_pruned += removed

            by_context: dict[str, list[int]] = defaultdict(list)
            for position in positions:
                by_context[ordered[position].store_id].append(position)
            context_selected: list[int] = []
            for context_id in sorted(by_context):
                before = tuple(by_context[context_id])
                after = _stratified_top_k(
                    ordered,
                    before,
                    self.config.max_products_per_canonical_per_context,
                    include_context=False,
                )
                context_pruned += len(before) - len(after)
                context_selected.extend(after)
            before_global = tuple(sorted(context_selected))
            after_global = _stratified_top_k(
                ordered,
                before_global,
                self.config.max_products_per_canonical_global,
                include_context=True,
            )
            global_pruned += len(before_global) - len(after_global)
            selected_canonical[canonical] = tuple(sorted(after_global))

        mappings: dict[str, dict[str, list[int]]] = {
            "gtin": defaultdict(list),
            "chain": defaultdict(list),
            "context": defaultdict(list),
            "category": defaultdict(list),
            "role": defaultdict(list),
            "purchase_model": defaultdict(list),
            "name_token": defaultdict(list),
        }
        for index, product in enumerate(ordered):
            if product.gtin:
                mappings["gtin"][product.gtin].append(index)
            if product.chain:
                mappings["chain"][product.chain.casefold().strip()].append(index)
            mappings["context"][product.store_id].append(index)
            mappings["purchase_model"][product.sale_model.value].append(index)
            if product.category:
                mappings["category"][_index_key(product.category)].append(index)
            if product.product_role:
                mappings["role"][_index_key(product.product_role)].append(index)
            for token in _name_tokens(
                " ".join(
                    value
                    for value in (
                        product.name,
                        product.canonical_name,
                        product.brand or "",
                    )
                    if value
                )
            ):
                mappings["name_token"][token].append(index)

        contexts = tuple(sorted(mappings["context"]))
        context_bits = {context_id: 1 << index for index, context_id in enumerate(contexts)}
        availability = tuple(
            StoreAvailabilityEntry(
                canonical=canonical,
                context_mask=sum(
                    {
                        context_bits[ordered[position].store_id]
                        for position in selected_canonical[canonical]
                    }
                ),
            )
            for canonical in sorted(selected_canonical)
        )
        indexes = PriceUniverseIndexes(
            canonical=_index_entries(selected_canonical),
            gtin=_index_entries(mappings["gtin"]),
            chain=_index_entries(mappings["chain"]),
            context=_index_entries(mappings["context"]),
            category=_index_entries(mappings["category"]),
            role=_index_entries(mappings["role"]),
            purchase_model=_index_entries(mappings["purchase_model"]),
            name_token=_index_entries(mappings["name_token"]),
            context_order=contexts,
            store_availability=availability,
        )
        elapsed_ms = (perf_counter() - started) * 1000
        canonical_before = sum(len(rows) for rows in raw_canonical.values())
        canonical_after = sum(len(rows) for rows in selected_canonical.values())
        timestamp = built_at or datetime.now(tz=UTC)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("built_at must be timezone-aware")
        return PriceUniverse(
            universe_id=key.universe_id,
            key=key,
            built_at=timestamp.astimezone(UTC),
            products_digest=_products_digest(ordered),
            products=ordered,
            indexes=indexes,
            stats=PriceUniverseBuildStats(
                raw_products=len(ordered),
                eligible_products=canonical_before,
                canonical_mappings_before_pruning=canonical_before,
                canonical_mappings=canonical_after,
                canonical_index_count=len(selected_canonical),
                dominance_pruned=dominance_pruned,
                per_context_top_k_pruned=context_pruned,
                global_top_k_pruned=global_pruned,
                products_without_canonical=len(ordered) - canonical_before,
                build_time_ms=round(elapsed_ms, 3),
            ),
        )


class PriceUniverseStatus(BaseModel):
    """Consumer-safe status returned by an injected universe manager."""

    model_config = ConfigDict(frozen=True)

    scope_id: str
    active: bool
    universe_id: str | None = None
    built_at: datetime | None = None
    snapshot_ids: tuple[str, ...] = ()
    product_count: int = 0
    canonical_index_count: int = 0


class PriceUniverseManager:
    """Thread-safe active-universe registry with build-before-swap semantics."""

    def __init__(self, builder: PriceUniverseBuilder | None = None) -> None:
        self.builder = builder or PriceUniverseBuilder()
        self._lock = RLock()
        self._active: dict[str, PriceUniverse] = {}

    def get_active(self, scope_id: str) -> PriceUniverse | None:
        with self._lock:
            return self._active.get(scope_id)

    def activate(self, universe: PriceUniverse) -> PriceUniverse | None:
        """Atomically replace one scope and return its previous universe."""

        with self._lock:
            previous = self._active.get(universe.key.scope_id)
            self._active[universe.key.scope_id] = universe
            return previous

    def build_and_activate(
        self,
        key: PriceUniverseKey,
        products: Iterable[Product],
        *,
        validator: Callable[[PriceUniverse], bool | None] | None = None,
        built_at: datetime | None = None,
    ) -> PriceUniverse:
        """Build/validate outside the critical section, then swap one pointer.

        Any builder or validator exception leaves the active universe intact.
        A validator may either raise or return ``False`` to reject a candidate.
        """

        with self._lock:
            current = self._active.get(key.scope_id)
            if current is not None and current.universe_id == key.universe_id:
                return current
        candidate = self.builder.build(key, products, built_at=built_at)
        if validator is not None and validator(candidate) is False:
            raise PriceUniverseValidationError("candidate universe failed validation")
        with self._lock:
            # Another thread may have completed the identical build while this
            # one validated.  Reuse its active immutable object.
            current = self._active.get(key.scope_id)
            if current is not None and current.universe_id == key.universe_id:
                return current
            self._active[key.scope_id] = candidate
            return candidate

    def status(self, scope_id: str) -> PriceUniverseStatus:
        universe = self.get_active(scope_id)
        if universe is None:
            return PriceUniverseStatus(scope_id=scope_id, active=False)
        return PriceUniverseStatus(
            scope_id=scope_id,
            active=True,
            universe_id=universe.universe_id,
            built_at=universe.built_at,
            snapshot_ids=universe.key.snapshot_ids,
            product_count=len(universe.products),
            canonical_index_count=universe.stats.canonical_index_count,
        )


class CacheStats(BaseModel):
    """A point-in-time cache counter snapshot."""

    model_config = ConfigDict(frozen=True)

    hits: int = Field(ge=0)
    misses: int = Field(ge=0)
    evictions: int = Field(ge=0)
    entries: int = Field(ge=0)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0


class _ThreadSafeLru[Key, Value]:
    def __init__(self, *, max_entries: int, metric_prefix: str) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least one")
        self.max_entries = max_entries
        self.metric_prefix = metric_prefix
        self._lock = RLock()
        self._values: OrderedDict[Key, Value] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get_or_compute(self, key: Key, factory: Callable[[], Value]) -> Value:
        # Compute under the re-entrant lock.  Cache loaders in this module are
        # CPU-local and bounded; serializing equal-key misses prevents a costly
        # first-request stampede after an atomic universe swap.
        with self._lock:
            if key in self._values:
                self._hits += 1
                increment_performance_counter(f"{self.metric_prefix}_hits")
                increment_performance_counter("cache_hits")
                value = self._values.pop(key)
                self._values[key] = value
                return value
            self._misses += 1
            increment_performance_counter(f"{self.metric_prefix}_misses")
            increment_performance_counter("cache_misses")
            value = factory()
            self._values[key] = value
            if len(self._values) > self.max_entries:
                self._values.popitem(last=False)
                self._evictions += 1
            return value

    @property
    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._hits,
                misses=self._misses,
                evictions=self._evictions,
                entries=len(self._values),
            )

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


@dataclass(frozen=True, slots=True)
class SemanticCandidateCacheKey:
    universe_id: str
    canonical_ingredient: str
    allowed_context_ids: tuple[str, ...]
    matcher_version: str


class SemanticCandidateCache:
    """Cache quantity-independent product semantics per universe/context set."""

    def __init__(self, *, max_entries: int = 2048) -> None:
        self._cache: _ThreadSafeLru[
            SemanticCandidateCacheKey, tuple[ProductCandidate, ...]
        ] = _ThreadSafeLru(max_entries=max_entries, metric_prefix="semantic_cache")

    def get_or_compute(
        self,
        universe: PriceUniverse,
        canonical_ingredient: str,
        *,
        allowed_context_ids: Iterable[str] = (),
        matcher_version: str,
        factory: Callable[[], Sequence[ProductCandidate]],
    ) -> tuple[ProductCandidate, ...]:
        key = SemanticCandidateCacheKey(
            universe_id=universe.universe_id,
            canonical_ingredient=_canonical_key(canonical_ingredient),
            allowed_context_ids=tuple(sorted(set(allowed_context_ids))),
            matcher_version=matcher_version,
        )
        return self._cache.get_or_compute(key, lambda: tuple(factory()))

    @property
    def stats(self) -> CacheStats:
        return self._cache.stats

    def clear(self) -> None:
        self._cache.clear()


@dataclass(frozen=True, slots=True)
class PackageCostCacheKey:
    universe_id: str
    candidate_digest: str
    required_quantity: str
    required_unit: str
    calculator_version: str


class PackageCostCache:
    """Cache exact package/promotion checkout quotes for normalized quantities."""

    def __init__(self, *, max_entries: int = 16384) -> None:
        self._cache: _ThreadSafeLru[PackageCostCacheKey, BasketItemQuote] = _ThreadSafeLru(
            max_entries=max_entries,
            metric_prefix="package_cache",
        )
        self._max_fingerprints = max_entries
        self._fingerprint_lock = RLock()
        self._candidate_digests: dict[int, tuple[ProductCandidate, str]] = {}

    def get_or_compute(
        self,
        universe: PriceUniverse,
        candidate: ProductCandidate,
        *,
        required_quantity: float,
        required_unit: str,
        calculator_version: str,
        factory: Callable[[], BasketItemQuote],
    ) -> BasketItemQuote:
        quantity, unit = normalize_quantity(required_quantity, required_unit)
        key = PackageCostCacheKey(
            universe_id=universe.universe_id,
            candidate_digest=self._candidate_digest(candidate),
            required_quantity=_decimal_text(quantity),
            required_unit=unit,
            calculator_version=calculator_version,
        )
        return self._cache.get_or_compute(key, factory)

    @property
    def stats(self) -> CacheStats:
        return self._cache.stats

    def clear(self) -> None:
        self._cache.clear()
        with self._fingerprint_lock:
            self._candidate_digests.clear()

    def _candidate_digest(self, candidate: ProductCandidate) -> str:
        candidate_id = id(candidate)
        with self._fingerprint_lock:
            cached = self._candidate_digests.get(candidate_id)
            if cached is not None and cached[0] is candidate:
                return cached[1]
            digest = _model_digest(candidate)
            # Retaining the immutable model prevents Python from reusing its
            # identity for a different checkout surface while the cache lives.
            if len(self._candidate_digests) >= self._max_fingerprints:
                self._candidate_digests.pop(next(iter(self._candidate_digests)))
            self._candidate_digests[candidate_id] = (candidate, digest)
            return digest


@dataclass(frozen=True, slots=True)
class BasketResultCacheKey:
    universe_id: str
    pricing_context_id: str
    requirement_hash: str
    allowed_context_ids: tuple[str, ...]
    max_stores: int | None
    optimizer_version: str


class BasketResultCache:
    """Cache a final basket for one exact normalized requirement multiset."""

    def __init__(self, *, max_entries: int = 32768) -> None:
        self._cache: _ThreadSafeLru[BasketResultCacheKey, OptimizedBasket] = _ThreadSafeLru(
            max_entries=max_entries,
            metric_prefix="basket_cache",
        )

    def get_or_compute(
        self,
        universe: PriceUniverse,
        requirements: Iterable[NormalizedIngredient | tuple[str, float, str]],
        *,
        allowed_context_ids: Iterable[str],
        max_stores: int | None,
        optimizer_version: str,
        pricing_context_id: str = "pricing-context:public",
        factory: Callable[[], OptimizedBasket],
    ) -> OptimizedBasket:
        if max_stores is not None and max_stores < 1:
            raise ValueError("max_stores must be at least one or None")
        key = BasketResultCacheKey(
            universe_id=universe.universe_id,
            pricing_context_id=pricing_context_id,
            requirement_hash=canonical_requirement_hash(requirements),
            allowed_context_ids=tuple(sorted(set(allowed_context_ids))),
            max_stores=max_stores,
            optimizer_version=optimizer_version,
        )
        return self._cache.get_or_compute(key, factory)

    @property
    def stats(self) -> CacheStats:
        return self._cache.stats

    def clear(self) -> None:
        self._cache.clear()


def canonical_requirement_items(
    requirements: Iterable[NormalizedIngredient | tuple[str, float, str]],
) -> tuple[tuple[str, str, str], ...]:
    """Aggregate, normalize and sort requirements for stable basket caching."""

    aggregated: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for requirement in requirements:
        if isinstance(requirement, NormalizedIngredient):
            name = requirement.canonical_name
            quantity = requirement.required_quantity
            unit = requirement.unit
        else:
            name, quantity, unit = requirement
        normalized_quantity, normalized_unit = normalize_quantity(quantity, unit)
        canonical = _canonical_key(name)
        aggregated[(canonical, normalized_unit)] += Decimal(str(normalized_quantity))
    return tuple(
        (canonical, _decimal_text(quantity), unit)
        for (canonical, unit), quantity in sorted(aggregated.items())
    )


def canonical_requirement_hash(
    requirements: Iterable[NormalizedIngredient | tuple[str, float, str]],
) -> str:
    return _json_digest(canonical_requirement_items(requirements))


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _model_digest(model: BaseModel) -> str:
    return _json_digest(model.model_dump(mode="json", exclude_computed_fields=True))


def _products_digest(products: Sequence[Product]) -> str:
    digest = hashlib.sha256()
    for product in products:
        payload = product.model_dump(mode="json", exclude_computed_fields=True)
        digest.update(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _canonical_key(value: str) -> str:
    return canonicalize_ingredient_name(value)


def _index_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _name_tokens(value: str) -> tuple[str, ...]:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return tuple(sorted({token for token in _TOKEN_PATTERN.findall(unaccented) if len(token) > 1}))


def _decimal_text(value: float | Decimal) -> str:
    decimal = Decimal(str(value))
    if not decimal.is_finite() or decimal <= 0:
        raise ValueError("quantity must be finite and greater than zero")
    return format(decimal.normalize(), "f")


def _product_sort_key(product: Product) -> tuple[object, ...]:
    provenance = product.source_provenance
    return (
        product.store_id,
        product.product_id,
        provenance.source_provider if provenance else "",
        provenance.source_snapshot_id if provenance else "",
        product.name.casefold(),
        product.price,
        product.effective_price,
    )


def _index_entries(mapping: Mapping[str, Iterable[int]]) -> tuple[IndexEntry, ...]:
    return tuple(
        IndexEntry(key=key, product_indexes=tuple(indexes))
        for key, indexes in sorted(mapping.items())
        if key
    )


def _offer_terms(offer: OfferMetadata) -> tuple[object, ...]:
    return (
        offer.kind.value,
        offer.required_packages,
        offer.max_quantity,
        offer.member_program,
        offer.valid_from.isoformat() if offer.valid_from else None,
        offer.valid_to.isoformat() if offer.valid_to else None,
    )


def _offer_order(offer: OfferMetadata) -> tuple[tuple[bool, object], ...]:
    # Optional terms remain None in the identity. Compare presence before value
    # so missing terms never compare directly with strings or numbers. The same
    # order must be used for the signature and its corresponding price vector.
    return tuple((value is not None, value) for value in _offer_terms(offer))


def _offer_structure(product: Product) -> tuple[tuple[object, ...], ...]:
    return tuple(_offer_terms(offer) for offer in sorted(product.offers, key=_offer_order))


def _offer_prices(product: Product) -> tuple[Decimal, ...]:
    return tuple(Decimal(str(offer.price)) for offer in sorted(product.offers, key=_offer_order))


def _dominance_signature(product: Product, canonical: str) -> tuple[object, ...]:
    provenance = product.source_provenance
    return (
        product.store_id,
        canonical,
        product.brand.casefold().strip() if product.brand else None,
        tuple(_name_tokens(product.name)),
        product.food_family,
        product.product_role,
        product.product_form,
        product.semantic_confidence,
        product.quantity_confidence,
        product.sale_model,
        product.package_quantity,
        product.package_unit,
        product.usable_quantity,
        product.usable_unit,
        product.estimated_piece_weight,
        product.estimated_piece_weight_unit,
        product.variable_weight,
        product.sale_unit,
        product.comparison_unit,
        product.price_context_type,
        product.coverage,
        provenance.source_provider if provenance else None,
        provenance.source_channel if provenance else None,
        provenance.fallback_used if provenance else None,
        _offer_structure(product),
    ) + (("maximum_purchase_units", provenance.maximum_purchase_units)
         if provenance and provenance.maximum_purchase_units is not None else ())


def _price_vector(product: Product) -> tuple[Decimal | None, ...]:
    return (
        Decimal(str(product.price)) if product.price is not None else None,
        Decimal(str(product.effective_price)),
        Decimal(str(product.sale_price)),
        Decimal(str(product.comparison_price)) if product.comparison_price is not None else None,
        Decimal(str(product.piece_price)) if product.piece_price is not None else None,
        *_offer_prices(product),
    )


def _dominates(cheaper: Product, dearer: Product) -> bool:
    left = _price_vector(cheaper)
    right = _price_vector(dearer)
    if len(left) != len(right):
        return False
    compared: list[tuple[Decimal, Decimal]] = []
    for left_price, right_price in zip(left, right, strict=True):
        if left_price is None and right_price is None:
            continue
        if left_price is None or right_price is None:
            return False
        compared.append((left_price, right_price))
    return all(a <= b for a, b in compared) and any(a < b for a, b in compared)


def _dominance_prune(
    products: Sequence[Product], canonical: str, positions: Sequence[int]
) -> tuple[tuple[int, ...], int]:
    groups: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for position in positions:
        groups[_dominance_signature(products[position], canonical)].append(position)
    retained: list[int] = []
    for signature in sorted(groups, key=repr):
        group = sorted(groups[signature], key=lambda index: _candidate_rank(products[index]))
        survivors: list[int] = []
        for position in group:
            product = products[position]
            if any(_dominates(products[kept], product) for kept in survivors):
                continue
            survivors = [kept for kept in survivors if not _dominates(product, products[kept])]
            survivors.append(position)
        retained.extend(survivors)
    unique = tuple(sorted(retained))
    return unique, len(positions) - len(unique)


def _size_stratum(product: Product) -> tuple[str, str]:
    quantity = product.usable_quantity or product.package_quantity
    unit = product.usable_unit or product.package_unit or "?"
    return (unit, _decimal_text(quantity) if quantity is not None else "unknown")


def _candidate_stratum(product: Product, *, include_context: bool) -> tuple[object, ...]:
    return (
        product.store_id if include_context else "",
        product.sale_model.value,
        _size_stratum(product),
        _offer_structure(product),
        product.product_role or "",
        product.product_form or "",
    )


def _candidate_rank(product: Product) -> tuple[object, ...]:
    unit_price = product.normalized_unit_price
    return (
        -_CONFIDENCE_RANK[product.semantic_confidence],
        -(1 if product.quantity_confidence.value in {"exact", "derived"} else 0),
        Decimal(str(unit_price if unit_price is not None else product.effective_price)),
        Decimal(str(product.effective_price)),
        product.name.casefold(),
        product.store_id,
        product.product_id,
    )


def _stratified_top_k(
    products: Sequence[Product],
    positions: Sequence[int],
    limit: int | None,
    *,
    include_context: bool,
) -> tuple[int, ...]:
    if limit is None or len(positions) <= limit:
        return tuple(sorted(positions))
    strata: dict[tuple[object, ...], list[int]] = defaultdict(list)
    for position in positions:
        strata[_candidate_stratum(products[position], include_context=include_context)].append(
            position
        )
    queues = [
        sorted(rows, key=lambda index: _candidate_rank(products[index]))
        for _key, rows in sorted(
            strata.items(),
            key=lambda item: (
                _candidate_rank(products[min(item[1], key=lambda index: _candidate_rank(products[index]))]),
                repr(item[0]),
            ),
        )
    ]
    selected: list[int] = []
    depth = 0
    while len(selected) < limit:
        added = False
        for queue in queues:
            if depth < len(queue):
                selected.append(queue[depth])
                added = True
                if len(selected) == limit:
                    break
        if not added:
            break
        depth += 1
    return tuple(sorted(selected))


def _uses_disabled_member_price(key: PriceUniverseKey, product: Product) -> bool:
    if key.membership_enabled(product.chain):
        return False
    if product.price is None and (product.sale_price is None or product.conditional_price_signal):
        # An offers-only ranking signal is not a public one-package checkout
        # price. The request's existing contract resolver checks eligibility.
        return False
    active_member_prices = {
        Decimal(str(offer.price))
        for offer in product.offers
        if offer.kind == OfferKind.MEMBER and offer.is_active()
    }
    if product.member_price is not None:
        active_member_prices.add(Decimal(str(product.member_price)))
    if not active_member_prices:
        return False
    active_public_prices = {
        Decimal(str(offer.price))
        for offer in product.offers
        if offer.kind != OfferKind.MEMBER
        and offer.required_packages == 1
        and offer.is_active()
    }
    if product.price is not None:
        # A separately observed ordinary price can equal a member campaign.
        # Equality alone is not proof of a membership leak. ICA flyer reference
        # labels never populate Product.price, so cannot take this path.
        active_public_prices.add(Decimal(str(product.price)))
    checkout_prices = {
        Decimal(str(value)) for value in (product.effective_price, product.sale_price)
        if value is not None
    }
    if product.sale_model == SaleModel.SOLD_BY_PIECE and product.piece_price is not None:
        checkout_prices.add(Decimal(str(product.piece_price)))
    leaked = checkout_prices & active_member_prices
    return bool(leaked - active_public_prices)


def _validate_product_provenance(key: PriceUniverseKey, product: Product) -> None:
    provenance = product.source_provenance
    if provenance is None:
        raise PriceUniverseError(
            f"product {product.store_id}/{product.product_id} is missing source provenance"
        )
    if provenance.source_snapshot_id not in key.snapshot_ids:
        raise PriceUniverseError(
            f"product {product.store_id}/{product.product_id} references snapshot "
            f"{provenance.source_snapshot_id!r} outside the universe key"
        )
    if provenance.store_id is not None and provenance.store_id != product.store_id:
        raise PriceUniverseError(
            f"product {product.product_id} context disagrees with source provenance"
        )
    if (
        product.chain is not None
        and provenance.chain is not None
        and product.chain.casefold().strip() != provenance.chain.casefold().strip()
    ):
        raise PriceUniverseError(
            f"product {product.store_id}/{product.product_id} chain disagrees with provenance"
        )


__all__ = [
    "BasketResultCache",
    "CacheStats",
    "IneligibleMemberPriceError",
    "MembershipSetting",
    "PackageCostCache",
    "PriceUniverse",
    "PriceUniverseBuildConfig",
    "PriceUniverseBuildStats",
    "PriceUniverseBuilder",
    "PriceUniverseError",
    "PriceUniverseIndexes",
    "PriceUniverseKey",
    "PriceUniverseManager",
    "PriceUniverseStatus",
    "PriceUniverseValidationError",
    "SemanticCandidateCache",
    "canonical_requirement_hash",
    "canonical_requirement_items",
]
