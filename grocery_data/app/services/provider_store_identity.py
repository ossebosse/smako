"""Replayable, evidence-gated mapping of external price contexts to stores.

The input is a closed projection of one bounded provider response.  It cannot
contain request headers, cookies, credentials or arbitrary provider payload.
Display-name similarity is useful for operator suggestions but can never
activate a production mapping.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    CoverageLevel,
    PriceContextType,
    ProviderStoreMappingStatus,
    StoreContextRelationType,
    StoreIdentityMatchConfidence,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.price_context_evidence import PriceContextEvidence
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.domain.store import ProviderStoreIdentityMapping, StoreContextLink
from grocery_data.app.storage.models import PhysicalStoreModel
from grocery_data.app.storage.repositories import (
    ProviderStoreIdentityMappingRepository,
    StoreContextLinkRepository,
)

_SECRET_KEY = re.compile(
    r"(?:authorization|cookie|set[_-]?cookie|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|session|clearance)",
    flags=re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?:\bauthorization\s*[:=]|\bbearer\s+[a-z0-9._~-]+|"
    r"\bcookie\s*[:=]|\bsessionid\s*=)",
    flags=re.IGNORECASE,
)
_STRONG_CONFIDENCE = frozenset(
    {
        StoreIdentityMatchConfidence.EXACT_ID,
        StoreIdentityMatchConfidence.EXACT_ADDRESS,
        StoreIdentityMatchConfidence.EXACT_NAME_AND_POSTAL,
        StoreIdentityMatchConfidence.STRONG_GEO,
    }
)


def _text(value: str | None) -> str:
    return re.sub(r"[^0-9a-zåäö]+", " ", (value or "").casefold()).strip()


def _postal(value: str | None) -> str:
    return "".join(character for character in (value or "") if character.isdigit())


def _physical_ids(row: PhysicalStoreModel) -> frozenset[str]:
    aliases = row.external_store_aliases or []
    return frozenset(
        str(value).strip()
        for value in (row.external_store_id, *aliases)
        if value is not None and str(value).strip()
    )


def _distance_m(
    latitude_a: Decimal | None,
    longitude_a: Decimal | None,
    latitude_b: Decimal | None,
    longitude_b: Decimal | None,
) -> Decimal | None:
    if None in {latitude_a, longitude_a, latitude_b, longitude_b}:
        return None
    lat1 = math.radians(float(latitude_a))
    lat2 = math.radians(float(latitude_b))
    delta_lat = lat2 - lat1
    delta_lon = math.radians(float(longitude_b) - float(longitude_a))
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return Decimal(str(2 * 6_371_000 * math.asin(math.sqrt(haversine)))).quantize(
        Decimal("0.01")
    )


class PrimatStoreDiscoveryRequest(BaseModel):
    """Sanitized transport facts for exactly one store-resolution response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["GET"] = "GET"
    host: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1, max_length=500)
    status: Literal[200] = 200
    content_type: str = Field(min_length=1, max_length=255)
    request_count: Literal[1] = 1
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sanitized: Literal[True] = True

    @model_validator(mode="after")
    def require_official_json_endpoint(self) -> PrimatStoreDiscoveryRequest:
        host = self.host.casefold().strip().rstrip(".")
        if host != "primat.nu" and not host.endswith(".primat.nu"):
            raise ValueError("store discovery must come from an official primat.nu host")
        if not self.path.startswith("/") or not self.path.rstrip("/").endswith(
            "/stores/resolve"
        ):
            raise ValueError("store discovery path must end in /stores/resolve")
        if "json" not in self.content_type.casefold():
            raise ValueError("store discovery must be JSON")
        return self


class PrimatStoreCandidate(BaseModel):
    """Whitelisted public identity fields from one provider store row."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    provider_context_id: str = Field(min_length=1, max_length=255)
    provider_store_id: str = Field(min_length=1, max_length=255)
    chain: Chain
    name: str = Field(min_length=1, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    postal_code: str | None = None
    city: str | None = Field(default=None, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    tier: str | None = Field(default=None, max_length=100)
    coverage: CoverageLevel | None = None
    price_context_type: PriceContextType = PriceContextType.PHYSICAL_STORE
    price_context_evidence: PriceContextEvidence | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    selected: bool = False
    customer_facing: bool = True
    source_snapshot_id: str = Field(min_length=1, max_length=255)
    observed_at: datetime
    raw_reference: str = Field(min_length=1, max_length=500)

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal_code(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        digits = _postal(str(value))
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        return digits

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_safe_customer_context(self) -> PrimatStoreCandidate:
        if self.chain not in {Chain.ICA, Chain.COOP, Chain.LIDL}:
            raise ValueError("only Lund external-basket chains belong in this bundle")
        if not self.customer_facing:
            raise ValueError("non-customer contexts cannot enter store identity mapping")
        if not self.provider_context_id.startswith("primat:"):
            raise ValueError("provider_context_id must use the primat: namespace")
        return self

    @property
    def identity_fingerprint(self) -> str:
        payload = {
            "provider_context_id": self.provider_context_id,
            "provider_store_id": self.provider_store_id,
            "chain": self.chain.value,
            "name": _text(self.name),
            "address": _text(self.address),
            "postal_code": _postal(self.postal_code),
            "city": _text(self.city),
            "latitude": str(self.latitude) if self.latitude is not None else None,
            "longitude": str(self.longitude) if self.longitude is not None else None,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


class PrimatStoreDiscoveryBundle(BaseModel):
    """Closed replay envelope produced by one bounded Primat resolve call."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_version: Literal["primat-store-discovery-bundle-v1"] = Field(alias="schema")
    provider: Literal["primat"] = "primat"
    city: str = Field(min_length=1, max_length=255)
    postal_code: str = Field(pattern=r"^\d{5}$")
    captured_at: datetime
    request: PrimatStoreDiscoveryRequest
    raw_rows: int = Field(ge=0, le=10_000)
    items: tuple[PrimatStoreCandidate, ...] = Field(max_length=10_000)

    @field_validator("captured_at")
    @classmethod
    def require_aware_capture(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_consistent_snapshot(self) -> PrimatStoreDiscoveryBundle:
        keys: set[tuple[Chain, str]] = set()
        for item in self.items:
            key = (item.chain, item.provider_context_id)
            if key in keys:
                raise ValueError("duplicate provider context in discovery bundle")
            keys.add(key)
            if item.observed_at != self.captured_at:
                raise ValueError("store rows must share the bundle capture timestamp")
            if self.request.response_sha256 not in item.raw_reference:
                raise ValueError("raw_reference must bind to the response hash")
        if self.raw_rows < len(self.items):
            raise ValueError("raw_rows cannot be smaller than sanitized item count")
        return self


class PrimatCatalogSmokeRequest(BaseModel):
    """Sanitized facts for the single product request in a context smoke."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: Literal["GET"] = "GET"
    host: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1, max_length=500)
    status: Literal[200] = 200
    content_type: str = Field(min_length=1, max_length=255)
    request_count: Literal[1] = 1
    response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sanitized: Literal[True] = True

    @model_validator(mode="after")
    def require_official_products_endpoint(self) -> PrimatCatalogSmokeRequest:
        host = self.host.casefold().strip().rstrip(".")
        if host != "primat.nu" and not host.endswith(".primat.nu"):
            raise ValueError("catalog smoke must come from an official primat.nu host")
        if not self.path.startswith("/") or not self.path.rstrip("/").endswith("/products"):
            raise ValueError("catalog smoke path must end in /products")
        if "json" not in self.content_type.casefold():
            raise ValueError("catalog smoke must be JSON")
        return self


class PrimatSmokeProductSample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    product_id: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=1000)
    current_price: Decimal = Field(gt=0)


class PrimatContextSmokeEvidence(BaseModel):
    """One context's product/price proof from a single bounded search."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_context_id: str = Field(min_length=1, max_length=255)
    provider_store_id: str = Field(min_length=1, max_length=255)
    chain: Chain
    coverage: CoverageLevel
    source_snapshot_id: str = Field(min_length=1, max_length=255)
    observed_at: datetime
    product_rows: int = Field(ge=0, le=1000)
    priced_product_rows: int = Field(ge=0, le=1000)
    provenance_valid: Literal[True] = True
    samples: tuple[PrimatSmokeProductSample, ...] = Field(max_length=10)
    raw_reference: str = Field(min_length=1, max_length=500)

    @field_validator("observed_at")
    @classmethod
    def require_aware_smoke_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("smoke observed_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_coherent_smoke(self) -> PrimatContextSmokeEvidence:
        if not self.provider_context_id.startswith("primat:"):
            raise ValueError("smoke context must use the primat: namespace")
        if self.priced_product_rows > self.product_rows:
            raise ValueError("priced product rows cannot exceed all product rows")
        if len(self.samples) > self.priced_product_rows:
            raise ValueError("smoke samples cannot exceed priced product rows")
        return self


class PrimatContextSmokeBundle(BaseModel):
    """Closed two-request proof: resolve once, then one multi-store product query."""

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    schema_version: Literal["primat-context-smoke-bundle-v1"] = Field(alias="schema")
    provider: Literal["primat"] = "primat"
    city: str = Field(min_length=1, max_length=255)
    postal_code: str = Field(pattern=r"^\d{5}$")
    captured_at: datetime
    store_discovery_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    resolve_request: PrimatStoreDiscoveryRequest
    product_request: PrimatCatalogSmokeRequest
    identity_revalidated: Literal[True] = True
    query_label: str = Field(min_length=1, max_length=100)
    items: tuple[PrimatContextSmokeEvidence, ...] = Field(max_length=100)

    @field_validator("captured_at")
    @classmethod
    def require_aware_smoke_capture(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("smoke captured_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_closed_smoke_scope(self) -> PrimatContextSmokeBundle:
        keys: set[tuple[Chain, str]] = set()
        snapshots: set[str] = set()
        for item in self.items:
            key = (item.chain, item.provider_context_id)
            if key in keys:
                raise ValueError("duplicate context smoke evidence")
            keys.add(key)
            snapshots.add(item.source_snapshot_id)
            if item.observed_at != self.captured_at:
                raise ValueError("smoke rows must share bundle capture time")
            if self.product_request.response_sha256 not in item.raw_reference:
                raise ValueError("smoke raw reference must bind to product response")
        if len(snapshots) > 1:
            raise ValueError("smoke rows must share one provider request snapshot")
        return self


def read_primat_store_discovery_bundle(
    path: Path,
    *,
    max_bytes: int = 5_000_000,
) -> PrimatStoreDiscoveryBundle:
    """Read one bounded closed replay envelope and reject secret-shaped data."""

    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("Primat store discovery input must be a regular file")
    encoded = resolved.read_bytes()
    if not encoded or len(encoded) > max_bytes:
        raise ValueError("Primat store discovery input is empty or exceeds 5 MB")

    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Primat store discovery contains duplicate key: {key}")
            if _SECRET_KEY.search(key):
                raise ValueError("Primat store discovery contains a forbidden key")
            result[key] = value
        return result

    payload = json.loads(encoded.decode("utf-8"), object_pairs_hook=closed_object)

    def reject_secret_value(value: object) -> None:
        if isinstance(value, Mapping):
            for nested in value.values():
                reject_secret_value(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_secret_value(nested)
        elif isinstance(value, str) and _SECRET_VALUE.search(value):
            raise ValueError("Primat store discovery contains a credential-shaped value")

    reject_secret_value(payload)
    return PrimatStoreDiscoveryBundle.model_validate(payload)


def read_primat_context_smoke_bundle(
    path: Path,
    *,
    max_bytes: int = 5_000_000,
) -> PrimatContextSmokeBundle:
    """Read one bounded closed smoke proof without accepting loose fields."""

    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("Primat context smoke input must be a regular file")
    encoded = resolved.read_bytes()
    if not encoded or len(encoded) > max_bytes:
        raise ValueError("Primat context smoke input is empty or exceeds 5 MB")

    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Primat context smoke contains duplicate key: {key}")
            if _SECRET_KEY.search(key):
                raise ValueError("Primat context smoke contains a forbidden key")
            result[key] = value
        return result

    payload = json.loads(encoded.decode("utf-8"), object_pairs_hook=closed_object)

    def reject_secret_value(value: object) -> None:
        if isinstance(value, Mapping):
            for nested in value.values():
                reject_secret_value(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_secret_value(nested)
        elif isinstance(value, str) and _SECRET_VALUE.search(value):
            raise ValueError("Primat context smoke contains a credential-shaped value")

    reject_secret_value(payload)
    return PrimatContextSmokeBundle.model_validate(payload)


class ProviderStoreSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_context_id: str
    provider_store_id: str
    name: str
    confidence: StoreIdentityMatchConfidence
    evidence: str
    name_similarity: Decimal = Field(ge=0, le=1)
    distance_m: Decimal | None = Field(default=None, ge=0)


class ProviderStoreMappingDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    physical_store_id: str
    chain: Chain
    physical_store_name: str
    status: ProviderStoreMappingStatus
    confidence: StoreIdentityMatchConfidence
    provider_context_id: str | None = None
    provider_store_id: str | None = None
    evidence: str
    persisted: bool = False
    store_context_link_written: bool = False
    lkg_retained: bool = False
    suggestions: tuple[ProviderStoreSuggestion, ...] = ()


class ProviderStoreMappingReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str
    provider: Literal["primat"] = "primat"
    captured_at: datetime
    physical_stores: int = Field(ge=0)
    provider_contexts: int = Field(ge=0)
    verified: int = Field(ge=0)
    unresolved: int = Field(ge=0)
    mapping_drift: int = Field(ge=0)
    automatic_links: int = Field(ge=0)
    fuzzy_links: Literal[0] = 0
    network_requests: Literal[0] = 0
    decisions: tuple[ProviderStoreMappingDecision, ...]


class ProviderContextSmokeDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_context_id: str
    physical_store_id: str | None = None
    activated: bool
    reason: str
    product_rows: int = Field(ge=0)
    priced_product_rows: int = Field(ge=0)


class ProviderContextSmokeReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str
    provider: Literal["primat"] = "primat"
    contexts_considered: int = Field(ge=0)
    contexts_activated: int = Field(ge=0)
    contexts_rejected: int = Field(ge=0)
    persisted: bool
    network_requests: Literal[0] = 0
    decisions: tuple[ProviderContextSmokeDecision, ...]


class _Match(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate: PrimatStoreCandidate | None
    confidence: StoreIdentityMatchConfidence
    evidence: str
    suggestions: tuple[ProviderStoreSuggestion, ...] = ()


class ProviderStoreIdentityMatcher:
    """Deterministic strong matching plus non-binding fuzzy suggestions."""

    def __init__(self, *, strong_geo_meters: Decimal = Decimal(75)) -> None:
        if strong_geo_meters <= 0 or strong_geo_meters > 250:
            raise ValueError("strong_geo_meters must be in (0, 250]")
        self.strong_geo_meters = strong_geo_meters

    def match(
        self,
        physical: PhysicalStoreModel,
        candidates: Sequence[PrimatStoreCandidate],
    ) -> _Match:
        scoped = tuple(row for row in candidates if row.chain.value == physical.chain)
        tiers: tuple[
            tuple[StoreIdentityMatchConfidence, str, list[PrimatStoreCandidate]], ...
        ] = (
            (
                StoreIdentityMatchConfidence.EXACT_ID,
                "provider_store_id intersects official primary/alias ID",
                [row for row in scoped if row.provider_store_id in _physical_ids(physical)],
            ),
            (
                StoreIdentityMatchConfidence.EXACT_ADDRESS,
                "exact normalized street address and chain",
                [row for row in scoped if self._exact_address(physical, row)],
            ),
            (
                StoreIdentityMatchConfidence.EXACT_NAME_AND_POSTAL,
                "exact normalized name and postal code",
                [row for row in scoped if self._exact_name_postal(physical, row)],
            ),
            (
                StoreIdentityMatchConfidence.STRONG_GEO,
                f"unique coordinates within {self.strong_geo_meters} metres",
                [row for row in scoped if self._strong_geo(physical, row)],
            ),
        )
        for confidence, evidence, matches in tiers:
            if len(matches) == 1:
                candidate = matches[0]
                return _Match(
                    candidate=candidate,
                    confidence=confidence,
                    evidence=evidence,
                    suggestions=self._suggestions(physical, scoped),
                )
            if len(matches) > 1:
                return _Match(
                    candidate=None,
                    confidence=StoreIdentityMatchConfidence.AMBIGUOUS,
                    evidence=f"{len(matches)} contexts share strongest evidence: {evidence}",
                    suggestions=tuple(
                        self._suggestion(physical, row, StoreIdentityMatchConfidence.AMBIGUOUS)
                        for row in sorted(matches, key=lambda item: item.provider_context_id)
                    ),
                )
        suggestions = self._suggestions(physical, scoped)
        if suggestions:
            return _Match(
                candidate=None,
                confidence=StoreIdentityMatchConfidence.PROBABLE,
                evidence="name similarity is suggestion-only and cannot auto-link",
                suggestions=suggestions,
            )
        return _Match(
            candidate=None,
            confidence=StoreIdentityMatchConfidence.NONE,
            evidence="no strong provider identity evidence",
        )

    @staticmethod
    def _exact_address(
        physical: PhysicalStoreModel,
        candidate: PrimatStoreCandidate,
    ) -> bool:
        address = _text(physical.address)
        if not address or address != _text(candidate.address):
            return False
        physical_postal = _postal(physical.postal_code)
        candidate_postal = _postal(candidate.postal_code)
        return not (physical_postal and candidate_postal and physical_postal != candidate_postal)

    @staticmethod
    def _exact_name_postal(
        physical: PhysicalStoreModel,
        candidate: PrimatStoreCandidate,
    ) -> bool:
        postal = _postal(physical.postal_code)
        return bool(
            postal
            and postal == _postal(candidate.postal_code)
            and _text(physical.name)
            and _text(physical.name) == _text(candidate.name)
        )

    def _strong_geo(
        self,
        physical: PhysicalStoreModel,
        candidate: PrimatStoreCandidate,
    ) -> bool:
        distance = _distance_m(
            physical.latitude,
            physical.longitude,
            candidate.latitude,
            candidate.longitude,
        )
        return distance is not None and distance <= self.strong_geo_meters

    def _suggestions(
        self,
        physical: PhysicalStoreModel,
        candidates: Sequence[PrimatStoreCandidate],
    ) -> tuple[ProviderStoreSuggestion, ...]:
        rows = [
            self._suggestion(physical, row, StoreIdentityMatchConfidence.PROBABLE)
            for row in candidates
        ]
        rows = [row for row in rows if row.name_similarity >= Decimal("0.60")]
        return tuple(
            sorted(
                rows,
                key=lambda row: (
                    -row.name_similarity,
                    row.distance_m if row.distance_m is not None else Decimal(999999999),
                    row.provider_context_id,
                ),
            )[:5]
        )

    @staticmethod
    def _suggestion(
        physical: PhysicalStoreModel,
        candidate: PrimatStoreCandidate,
        confidence: StoreIdentityMatchConfidence,
    ) -> ProviderStoreSuggestion:
        similarity = Decimal(
            str(SequenceMatcher(None, _text(physical.name), _text(candidate.name)).ratio())
        ).quantize(Decimal("0.0001"))
        distance = _distance_m(
            physical.latitude,
            physical.longitude,
            candidate.latitude,
            candidate.longitude,
        )
        return ProviderStoreSuggestion(
            provider_context_id=candidate.provider_context_id,
            provider_store_id=candidate.provider_store_id,
            name=candidate.name,
            confidence=confidence,
            evidence="operator suggestion only",
            name_similarity=similarity,
            distance_m=distance,
        )


class ProviderStoreIdentityMappingService:
    """Reconcile one replay bundle while retaining verified LKG on drift."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.matcher = ProviderStoreIdentityMatcher()

    def reconcile(
        self,
        bundle: PrimatStoreDiscoveryBundle,
        *,
        city: str,
        persist: bool = False,
        chains: frozenset[Chain] = frozenset({Chain.ICA, Chain.COOP, Chain.LIDL}),
    ) -> ProviderStoreMappingReport:
        city_key = city.casefold().strip()
        if not city_key or _text(bundle.city) != _text(city):
            raise ValueError("Primat store discovery city does not match mapping city")
        physical = list(
            self.session.scalars(
                select(PhysicalStoreModel)
                .where(
                    PhysicalStoreModel.is_active.is_(True),
                    func.lower(func.trim(PhysicalStoreModel.city)) == city_key,
                    PhysicalStoreModel.chain.in_(chain.value for chain in chains),
                )
                .order_by(PhysicalStoreModel.chain, PhysicalStoreModel.name)
            )
        )
        candidates = tuple(row for row in bundle.items if row.chain in chains)
        matches = {row.id: self.matcher.match(row, candidates) for row in physical}

        # A provider context cannot be auto-linked to two physical stores even
        # when each local comparison looked independently strong.
        claims: defaultdict[str, list[str]] = defaultdict(list)
        for store_id, match in matches.items():
            if match.candidate is not None and match.confidence in _STRONG_CONFIDENCE:
                claims[match.candidate.provider_context_id].append(store_id)
        for stores in claims.values():
            if len(stores) <= 1:
                continue
            for store_id in stores:
                previous = matches[store_id]
                candidate = previous.candidate
                assert candidate is not None
                matches[store_id] = _Match(
                    candidate=None,
                    confidence=StoreIdentityMatchConfidence.AMBIGUOUS,
                    evidence="one provider context strongly matches multiple physical stores",
                    suggestions=(
                        self.matcher._suggestion(
                            next(row for row in physical if row.id == store_id),
                            candidate,
                            StoreIdentityMatchConfidence.AMBIGUOUS,
                        ),
                    ),
                )

        mappings = ProviderStoreIdentityMappingRepository(self.session)
        links = StoreContextLinkRepository(self.session)
        decisions: list[ProviderStoreMappingDecision] = []
        for store in physical:
            match = matches[store.id]
            existing = mappings.get(store.id, provider=SourceProvider.PRIMAT)
            mapping, linked, retained = self._mapping_for(
                store,
                match,
                existing=existing,
                checked_at=bundle.captured_at,
            )
            if persist:
                mappings.upsert(mapping)
                if mapping.status == ProviderStoreMappingStatus.VERIFIED:
                    candidate = match.candidate
                    assert candidate is not None
                    links.upsert(self._context_link(store, candidate, mapping))
                    linked = True
            decisions.append(
                ProviderStoreMappingDecision(
                    physical_store_id=store.id,
                    chain=Chain(store.chain),
                    physical_store_name=store.name,
                    status=mapping.status,
                    confidence=mapping.confidence,
                    provider_context_id=(
                        match.candidate.provider_context_id
                        if match.candidate is not None
                        else mapping.provider_context_id
                    ),
                    provider_store_id=(
                        match.candidate.provider_store_id
                        if match.candidate is not None
                        else mapping.provider_store_id
                    ),
                    evidence=mapping.evidence or match.evidence,
                    persisted=persist,
                    store_context_link_written=bool(persist and linked),
                    lkg_retained=retained,
                    suggestions=match.suggestions,
                )
            )
        counts = defaultdict(int)
        for row in decisions:
            counts[row.status.value] += 1
        return ProviderStoreMappingReport(
            city=city.strip(),
            captured_at=bundle.captured_at,
            physical_stores=len(physical),
            provider_contexts=len(candidates),
            verified=counts[ProviderStoreMappingStatus.VERIFIED.value],
            unresolved=counts[ProviderStoreMappingStatus.UNRESOLVED.value],
            mapping_drift=counts[ProviderStoreMappingStatus.MAPPING_DRIFT.value],
            automatic_links=sum(
                row.status == ProviderStoreMappingStatus.VERIFIED for row in decisions
            ),
            decisions=tuple(decisions),
        )

    def _mapping_for(
        self,
        physical: PhysicalStoreModel,
        match: _Match,
        *,
        existing: Any,
        checked_at: datetime,
    ) -> tuple[ProviderStoreIdentityMapping, bool, bool]:
        if match.candidate is not None and match.confidence in _STRONG_CONFIDENCE:
            candidate = match.candidate
            fingerprint = candidate.identity_fingerprint
            if existing is not None and existing.provider_context_id is not None:
                changed = (
                    existing.provider_context_id != candidate.provider_context_id
                    or existing.verified_identity_fingerprint != fingerprint
                )
                if changed:
                    return (
                        ProviderStoreIdentityMapping(
                            physical_store_id=physical.id,
                            provider=SourceProvider.PRIMAT,
                            provider_context_id=existing.provider_context_id,
                            provider_store_id=existing.provider_store_id,
                            confidence=StoreIdentityMatchConfidence(existing.confidence),
                            status=ProviderStoreMappingStatus.MAPPING_DRIFT,
                            evidence="strong provider identity differs from verified LKG",
                            verified_identity_fingerprint=(
                                existing.verified_identity_fingerprint
                            ),
                            observed_identity_fingerprint=fingerprint,
                            candidate_context_id=candidate.provider_context_id,
                            verified_at=existing.verified_at,
                            last_checked_at=checked_at,
                            drift_detected_at=existing.drift_detected_at or checked_at,
                        ),
                        False,
                        True,
                    )
            return (
                ProviderStoreIdentityMapping(
                    physical_store_id=physical.id,
                    provider=SourceProvider.PRIMAT,
                    provider_context_id=candidate.provider_context_id,
                    provider_store_id=candidate.provider_store_id,
                    confidence=match.confidence,
                    status=ProviderStoreMappingStatus.VERIFIED,
                    evidence=match.evidence,
                    verified_identity_fingerprint=fingerprint,
                    observed_identity_fingerprint=fingerprint,
                    verified_at=(
                        existing.verified_at
                        if existing is not None and existing.verified_at is not None
                        else checked_at
                    ),
                    last_checked_at=checked_at,
                ),
                False,
                False,
            )

        if existing is not None and existing.provider_context_id is not None:
            # Absence or fuzzy evidence cannot retire a verified mapping. Keep
            # the persisted row untouched and make the current report explicit.
            return (
                ProviderStoreIdentityMapping(
                    physical_store_id=physical.id,
                    provider=SourceProvider.PRIMAT,
                    provider_context_id=existing.provider_context_id,
                    provider_store_id=existing.provider_store_id,
                    confidence=StoreIdentityMatchConfidence(existing.confidence),
                    status=ProviderStoreMappingStatus(existing.status),
                    evidence=existing.evidence,
                    verified_identity_fingerprint=existing.verified_identity_fingerprint,
                    observed_identity_fingerprint=existing.observed_identity_fingerprint,
                    candidate_context_id=existing.candidate_context_id,
                    verified_at=existing.verified_at,
                    last_checked_at=existing.last_checked_at,
                    drift_detected_at=existing.drift_detected_at,
                    active=existing.is_active,
                ),
                False,
                True,
            )
        suggestion = match.suggestions[0] if match.suggestions else None
        return (
            ProviderStoreIdentityMapping(
                physical_store_id=physical.id,
                provider=SourceProvider.PRIMAT,
                provider_store_id=(suggestion.provider_store_id if suggestion else None),
                confidence=match.confidence,
                status=ProviderStoreMappingStatus.UNRESOLVED,
                evidence=match.evidence,
                observed_identity_fingerprint=None,
                candidate_context_id=(suggestion.provider_context_id if suggestion else None),
                last_checked_at=checked_at,
            ),
            False,
            False,
        )

    @staticmethod
    def _context_link(
        physical: PhysicalStoreModel,
        candidate: PrimatStoreCandidate,
        mapping: ProviderStoreIdentityMapping,
    ) -> StoreContextLink:
        generic_confidence = (
            Confidence.EXACT
            if mapping.confidence
            in {
                StoreIdentityMatchConfidence.EXACT_ID,
                StoreIdentityMatchConfidence.EXACT_ADDRESS,
            }
            else Confidence.HIGH
        )
        # Store resolution establishes identity, not current product/price
        # availability. A later catalog smoke may promote basket_eligible.
        return StoreContextLink(
            physical_store_id=physical.id,
            grocery_context_id=candidate.provider_context_id,
            source_provider=SourceProvider.PRIMAT,
            source_channel=SourceChannel.CATALOG,
            grocery_context_name=candidate.name,
            price_context_type=candidate.price_context_type,
            coverage=candidate.coverage,
            relation_type=StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT,
            confidence=generic_confidence,
            evidence=(
                f"primat identity {mapping.confidence.value}; catalog smoke pending"
            ),
            basket_eligible=False,
            offers_only=False,
            snapshot_id=candidate.source_snapshot_id,
            observed_at=candidate.observed_at,
            linked_at=mapping.verified_at or mapping.last_checked_at,
            last_verified_at=mapping.last_checked_at,
            active=True,
        )


class ProviderContextSmokeActivationService:
    """Promote identity-only links after replayed product/price evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def activate(
        self,
        bundle: PrimatContextSmokeBundle,
        *,
        city: str,
        persist: bool = False,
    ) -> ProviderContextSmokeReport:
        if _text(bundle.city) != _text(city):
            raise ValueError("Primat context smoke city does not match activation city")
        mappings = ProviderStoreIdentityMappingRepository(self.session).list_for_city(
            city,
            provider=SourceProvider.PRIMAT,
        )
        by_context: defaultdict[str, list[Any]] = defaultdict(list)
        for mapping in mappings:
            if mapping.provider_context_id is not None:
                by_context[mapping.provider_context_id].append(mapping)
        link_repository = StoreContextLinkRepository(self.session)
        decisions: list[ProviderContextSmokeDecision] = []
        for evidence in bundle.items:
            mapping_rows = by_context.get(evidence.provider_context_id, [])
            mapping = mapping_rows[0] if len(mapping_rows) == 1 else None
            reason: str | None = None
            link = None
            if mapping is None:
                reason = "no unique persisted provider mapping"
            elif mapping.status != ProviderStoreMappingStatus.VERIFIED.value:
                reason = "provider mapping is unresolved or drifted"
            elif mapping.provider_store_id != evidence.provider_store_id:
                reason = "smoke provider store ID differs from verified mapping"
            else:
                link = link_repository.get(
                    mapping.physical_store_id,
                    source_provider=SourceProvider.PRIMAT.value,
                    grocery_context_id=evidence.provider_context_id,
                )
                if link is None or not link.is_active:
                    reason = "verified identity link is missing or inactive"
                elif not is_complete_catalog_coverage(CoverageLevel(link.coverage)):
                    reason = "mapped discovery context is not complete-catalog"
                elif not is_complete_catalog_coverage(evidence.coverage):
                    reason = "smoke does not prove complete catalog coverage"
                elif evidence.product_rows < 1 or evidence.priced_product_rows < 1:
                    reason = "smoke returned no priced product for this context"
            activated = reason is None and mapping is not None and link is not None
            if activated and persist:
                assert mapping is not None and link is not None
                link_repository.upsert(
                    StoreContextLink(
                        physical_store_id=mapping.physical_store_id,
                        grocery_context_id=evidence.provider_context_id,
                        source_provider=SourceProvider.PRIMAT,
                        source_channel=SourceChannel.CATALOG,
                        grocery_context_name=link.grocery_context_name,
                        price_context_type=(
                            PriceContextType(link.price_context_type)
                            if link.price_context_type is not None
                            else PriceContextType.PHYSICAL_STORE
                        ),
                        coverage=evidence.coverage,
                        relation_type=StoreContextRelationType(link.relation_type),
                        confidence=Confidence(link.confidence),
                        evidence=(
                            "verified Primat identity + bounded catalog product/price smoke"
                        ),
                        basket_eligible=True,
                        offers_only=False,
                        snapshot_id=evidence.source_snapshot_id,
                        observed_at=evidence.observed_at,
                        linked_at=link.linked_at,
                        last_verified_at=bundle.captured_at,
                        active=True,
                    )
                )
            decisions.append(
                ProviderContextSmokeDecision(
                    provider_context_id=evidence.provider_context_id,
                    physical_store_id=(mapping.physical_store_id if mapping is not None else None),
                    activated=activated,
                    reason=reason or "priced product smoke and provenance verified",
                    product_rows=evidence.product_rows,
                    priced_product_rows=evidence.priced_product_rows,
                )
            )
        activated_count = sum(row.activated for row in decisions)
        return ProviderContextSmokeReport(
            city=city.strip(),
            contexts_considered=len(decisions),
            contexts_activated=activated_count,
            contexts_rejected=len(decisions) - activated_count,
            persisted=persist,
            decisions=tuple(decisions),
        )


__all__ = [
    "PrimatCatalogSmokeRequest",
    "PrimatContextSmokeBundle",
    "PrimatContextSmokeEvidence",
    "PrimatSmokeProductSample",
    "PrimatStoreCandidate",
    "PrimatStoreDiscoveryBundle",
    "PrimatStoreDiscoveryRequest",
    "ProviderContextSmokeActivationService",
    "ProviderContextSmokeDecision",
    "ProviderContextSmokeReport",
    "ProviderStoreIdentityMappingService",
    "ProviderStoreIdentityMatcher",
    "ProviderStoreMappingDecision",
    "ProviderStoreMappingReport",
    "ProviderStoreSuggestion",
    "read_primat_context_smoke_bundle",
    "read_primat_store_discovery_bundle",
]
