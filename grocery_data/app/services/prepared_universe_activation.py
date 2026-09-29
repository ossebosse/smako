from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.services.daily_refresh import UniverseRefreshResult
from grocery_data.app.services.durable_files import atomic_write_bytes, require_free_space
from grocery_data.app.services.freshness import FreshnessPolicy, assess_freshness

_MAX_ARTIFACT_BYTES = 250_000_000
_ARTIFACT_FREE_SPACE_RESERVE_BYTES = 64 * 1024 * 1024
_SAFE_SCOPE_PART = re.compile(r"[^0-9a-zåäö]+")
_FORBIDDEN_ARTIFACT_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "cookies",
        "headers",
        "password",
        "raw_body",
        "raw_response",
        "request_headers",
        "response_headers",
        "session",
        "session_data",
        "set_cookie",
        "token",
    }
)


def _normalized_key(value: object) -> str:
    return str(value).casefold().strip().replace("-", "_").replace(" ", "_")


def _assert_credential_free(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if _normalized_key(key) in _FORBIDDEN_ARTIFACT_KEYS:
                raise ValueError("prepared universe contains forbidden transport material")
            _assert_credential_free(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_credential_free(nested)


def _scope_id(city: str) -> str:
    normalized = " ".join(city.casefold().split())
    if not normalized:
        raise ValueError("city is required")
    return f"city:{normalized}"


def _scope_filename(city: str) -> str:
    normalized = _SAFE_SCOPE_PART.sub("-", " ".join(city.casefold().split())).strip("-")
    if not normalized:
        raise ValueError("city cannot be represented as a safe scope")
    return f"city-{normalized}.json"


class PreparedUniverseArtifactMetadata(BaseModel):
    """Allowlisted identity extracted by the authoritative artifact validator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    city: str = Field(min_length=1)
    scope_id: str = Field(pattern=r"^city:.+")
    universe_id: str = Field(min_length=1)
    built_at: datetime
    snapshot_ids: tuple[str, ...] = Field(min_length=1)
    product_count: int = Field(gt=0)
    canonical_index_count: int = Field(gt=0)
    oldest_observed_at: datetime
    oldest_base_observed_at: datetime | None = Field(default=None, exclude_if=lambda value: value is None)

    @field_validator("snapshot_ids")
    @classmethod
    def normalize_snapshot_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(sorted({value.strip() for value in values if value.strip()}))
        if not normalized:
            raise ValueError("artifact requires snapshot lineage")
        return normalized

    @field_validator("built_at", "oldest_observed_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("artifact timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("oldest_base_observed_at")
    @classmethod
    def require_aware_base_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("base observation must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def validate_scope(self) -> PreparedUniverseArtifactMetadata:
        if self.scope_id != _scope_id(self.city):
            raise ValueError("artifact city and scope disagree")
        return self


PreparedArtifactValidator = Callable[
    [Mapping[str, Any], str],
    PreparedUniverseArtifactMetadata,
]


class ActivePreparedUniverseManifest(BaseModel):
    """Small durable pointer swapped only after a closed artifact validates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["active-prepared-price-universe-v1"] = (
        "active-prepared-price-universe-v1"
    )
    city: str = Field(min_length=1)
    scope_id: str = Field(pattern=r"^city:.+")
    universe_id: str = Field(min_length=1)
    built_at: datetime
    activated_at: datetime
    snapshot_ids: tuple[str, ...] = Field(min_length=1)
    product_count: int = Field(gt=0)
    canonical_index_count: int = Field(gt=0)
    oldest_observed_at: datetime
    oldest_base_observed_at: datetime | None = Field(default=None, exclude_if=lambda value: value is None)
    artifact_file: str = Field(pattern=r"^artifacts/[0-9a-f]{64}\.json$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_bytes: int = Field(gt=0)
    provider_requests: int = 0

    @field_validator("built_at", "activated_at", "oldest_observed_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("manifest timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("oldest_base_observed_at")
    @classmethod
    def require_aware_base_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("base observation must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def validate_identity(self) -> ActivePreparedUniverseManifest:
        if self.scope_id != _scope_id(self.city):
            raise ValueError("manifest city and scope disagree")
        if tuple(self.snapshot_ids) != tuple(sorted(set(self.snapshot_ids))):
            raise ValueError("manifest snapshot lineage must be unique and sorted")
        if (
            PurePosixPath(self.artifact_file).is_absolute()
            or ".." in PurePosixPath(self.artifact_file).parts
        ):
            raise ValueError("manifest artifact path must stay within its cache root")
        return self


def _read_candidate(path: Path, *, max_bytes: int) -> tuple[bytes, Mapping[str, Any]]:
    if max_bytes <= 0:
        raise ValueError("max artifact bytes must be greater than zero")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("prepared universe candidate must be a regular file")
    size = resolved.stat().st_size
    if size <= 0 or size > max_bytes:
        raise ValueError("prepared universe candidate has an invalid bounded size")
    try:
        payload_bytes = resolved.read_bytes()
        payload = json.loads(payload_bytes)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("prepared universe candidate must be readable UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise TypeError("prepared universe candidate root must be an object")
    _assert_credential_free(payload)
    return payload_bytes, payload


def _atomic_write(path: Path, payload: bytes) -> None:
    atomic_write_bytes(path, payload)


class PreparedUniverseArtifactStore:
    """Credential-free, cross-process handoff for prepared PriceUniverse artifacts.

    Candidate data is immutable and content-addressed. The active state is one
    small manifest, replaced atomically only after schema, lineage, size and a
    second stored-copy validation pass. A failed candidate may leave an
    unreferenced immutable blob, but it cannot change the active manifest.
    """

    def __init__(self, root: Path, *, max_artifact_bytes: int = _MAX_ARTIFACT_BYTES) -> None:
        self.root = root.resolve()
        self.max_artifact_bytes = max_artifact_bytes

    def active_manifest_path(self, city: str) -> Path:
        return self.root / "active" / _scope_filename(city)

    def read_active(self, city: str) -> ActivePreparedUniverseManifest | None:
        path = self.active_manifest_path(city)
        if not path.exists():
            return None
        if not path.is_file():
            raise ValueError("active prepared-universe manifest is not a regular file")
        try:
            manifest = ActivePreparedUniverseManifest.model_validate_json(path.read_bytes())
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("active prepared-universe manifest is invalid") from exc
        if manifest.scope_id != _scope_id(city):
            raise ValueError("active prepared-universe manifest has the wrong scope")
        artifact = (self.root / PurePosixPath(manifest.artifact_file)).resolve()
        try:
            artifact.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("active artifact escapes its cache root") from exc
        if not artifact.is_file() or artifact.stat().st_size != manifest.artifact_bytes:
            raise ValueError("active prepared-universe artifact is missing or truncated")
        return manifest

    def active_manifest_bytes(self, city: str) -> bytes | None:
        path = self.active_manifest_path(city)
        return path.read_bytes() if path.is_file() else None

    def restore_active_manifest(
        self,
        city: str,
        previous: bytes | None,
        *,
        expected_current: bytes | None,
    ) -> None:
        """Restore a captured active pointer after a later runtime commit fails.

        Artifacts are immutable, so rollback changes only the small active
        manifest.  The expected-current guard prevents this wrapper from
        overwriting a manifest installed by a newer refresh between promotion
        and rollback.
        """

        normalized_city = " ".join(city.casefold().split())
        path = self.active_manifest_path(normalized_city)
        if self.active_manifest_bytes(normalized_city) != expected_current:
            raise RuntimeError("active prepared-universe manifest changed before rollback")
        if previous is None:
            path.unlink(missing_ok=True)
            return
        try:
            manifest = ActivePreparedUniverseManifest.model_validate_json(previous)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("previous prepared-universe manifest is invalid") from exc
        if manifest.scope_id != _scope_id(normalized_city):
            raise ValueError("previous prepared-universe manifest has the wrong scope")
        artifact = (self.root / PurePosixPath(manifest.artifact_file)).resolve()
        try:
            artifact.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("previous prepared-universe artifact escapes cache root") from exc
        if not artifact.is_file() or artifact.stat().st_size != manifest.artifact_bytes:
            raise ValueError("previous prepared-universe artifact is missing or truncated")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != manifest.artifact_sha256:
            raise ValueError("previous prepared-universe artifact hash mismatch")
        _atomic_write(path, previous)

    def resolve_active_artifact(self, city: str, *, verify_hash: bool = True) -> Path | None:
        """Resolve the restart artifact selected by the active city manifest.

        A long-lived composition root calls this once during startup/reload and
        then passes the returned path to its authoritative runtime loader. Hash
        verification is on by default; the lightweight status endpoint only
        reads manifest metadata and never uses this as a meal-request hot path.
        """

        manifest = self.read_active(city)
        if manifest is None:
            return None
        artifact = (self.root / PurePosixPath(manifest.artifact_file)).resolve()
        try:
            artifact.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("active artifact escapes its cache root") from exc
        if verify_hash and hashlib.sha256(artifact.read_bytes()).hexdigest() != (
            manifest.artifact_sha256
        ):
            raise ValueError("active prepared-universe artifact hash mismatch")
        return artifact

    def activate(
        self,
        candidate: Path,
        *,
        city: str,
        validator: PreparedArtifactValidator,
        expected_snapshot_ids: Sequence[str] = (),
        activated_at: datetime | None = None,
        freshness_policy: FreshnessPolicy | None = None,
    ) -> UniverseRefreshResult:
        normalized_city = " ".join(city.casefold().split())
        scope = _scope_id(normalized_city)
        before = self.active_manifest_bytes(normalized_city)
        try:
            candidate_bytes, payload = _read_candidate(
                candidate,
                max_bytes=self.max_artifact_bytes,
            )
            metadata = validator(payload, normalized_city)
            if metadata.scope_id != scope:
                raise ValueError("prepared universe candidate has the wrong scope")
            expected = {value.strip() for value in expected_snapshot_ids if value.strip()}
            missing = expected.difference(metadata.snapshot_ids)
            if missing:
                raise ValueError("prepared universe candidate lacks promoted snapshot lineage")

            timestamp = activated_at or datetime.now(tz=UTC)
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("activation time must be timezone-aware")
            timestamp = timestamp.astimezone(UTC)
            if freshness_policy is not None:
                freshness = assess_freshness(
                    metadata.oldest_base_observed_at or metadata.oldest_observed_at,
                    policy=freshness_policy,
                    now=timestamp,
                )
                if not freshness.usable:
                    raise ValueError("prepared universe candidate is stale at activation")

            digest = hashlib.sha256(candidate_bytes).hexdigest()
            artifact_relative = PurePosixPath("artifacts") / f"{digest}.json"
            artifact_path = self.root / Path(*artifact_relative.parts)
            if artifact_path.exists():
                if (
                    not artifact_path.is_file()
                    or artifact_path.stat().st_size != len(candidate_bytes)
                    or hashlib.sha256(artifact_path.read_bytes()).hexdigest() != digest
                ):
                    raise ValueError("content-addressed prepared universe artifact conflicts")
            else:
                require_free_space(
                    artifact_path.parent,
                    required_bytes=len(candidate_bytes),
                    reserve_bytes=_ARTIFACT_FREE_SPACE_RESERVE_BYTES,
                )
                _atomic_write(artifact_path, candidate_bytes)

            # Validate the exact stored bytes, not merely the caller's source path.
            stored_bytes, stored_payload = _read_candidate(
                artifact_path,
                max_bytes=self.max_artifact_bytes,
            )
            if hashlib.sha256(stored_bytes).hexdigest() != digest:
                raise ValueError("stored prepared universe artifact hash mismatch")
            stored_metadata = validator(stored_payload, normalized_city)
            if stored_metadata != metadata:
                raise ValueError("stored prepared universe artifact changed during activation")

            manifest = ActivePreparedUniverseManifest(
                city=metadata.city,
                scope_id=metadata.scope_id,
                universe_id=metadata.universe_id,
                built_at=metadata.built_at,
                activated_at=timestamp,
                snapshot_ids=metadata.snapshot_ids,
                product_count=metadata.product_count,
                canonical_index_count=metadata.canonical_index_count,
                oldest_observed_at=metadata.oldest_observed_at,
                oldest_base_observed_at=metadata.oldest_base_observed_at,
                artifact_file=artifact_relative.as_posix(),
                artifact_sha256=digest,
                artifact_bytes=len(candidate_bytes),
            )
            manifest_bytes = json.dumps(
                manifest.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            # A final round-trip guarantees the small pointer is closed before swap.
            ActivePreparedUniverseManifest.model_validate_json(manifest_bytes)
            _atomic_write(self.active_manifest_path(normalized_city), manifest_bytes)
        except Exception:
            if self.active_manifest_bytes(normalized_city) != before:
                raise RuntimeError(
                    "active prepared-universe manifest changed after failed activation"
                ) from None
            raise

        return UniverseRefreshResult(
            status="active_from_prebuilt_artifact",
            universe_id=manifest.universe_id,
            built_at=manifest.built_at,
            product_count=manifest.product_count,
            canonical_index_count=manifest.canonical_index_count,
            active_unchanged=False,
            artifact_file=manifest.artifact_file,
            snapshot_ids=manifest.snapshot_ids,
            provider_requests=0,
        )


class PreparedUniverseArtifactRefreshHook:
    """Daily-refresh hook for an explicitly prebuilt local candidate artifact."""

    def __init__(
        self,
        store: PreparedUniverseArtifactStore,
        *,
        candidate_loader: Callable[[str], Path],
        validator: PreparedArtifactValidator,
        expected_snapshot_ids_loader: Callable[[str], Sequence[str]] | None = None,
    ) -> None:
        self.store = store
        self.candidate_loader = candidate_loader
        self.validator = validator
        self.expected_snapshot_ids_loader = expected_snapshot_ids_loader or (lambda _city: ())

    def rebuild_and_activate(self, city: str) -> UniverseRefreshResult:
        return self.store.activate(
            self.candidate_loader(city),
            city=city,
            validator=self.validator,
            expected_snapshot_ids=self.expected_snapshot_ids_loader(city),
        )


def validate_backend_prepared_universe_artifact(
    payload: Mapping[str, Any],
    city: str,
    *,
    required_context_ids: tuple[str, ...] = (),
    max_price_age_hours: float = 48.0,
) -> PreparedUniverseArtifactMetadata:
    """Validate with the authoritative backend model, imported only on demand.

    This function performs no provider construction and no I/O. The caller must
    make the backend package importable in its composition root.
    """

    from app.services.basket_optimizer import BasketOptimizer
    from app.services.price_universe_runtime import (
        PRECOMPUTED_CANONICAL_REQUIREMENTS,
        PreparedPriceUniverseArtifact,
    )

    artifact = PreparedPriceUniverseArtifact.model_validate(payload)
    prepared = artifact.restore()
    if required_context_ids:
        usable, _stale, _ages = prepared._context_partition(
            now=datetime.now(UTC), stale_age_hours=max_price_age_hours
        )
        missing = set(required_context_ids) - set(usable)
        if missing:
            raise ValueError(
                "prepared universe lacks required usable contexts: " + ",".join(sorted(missing))
            )
    basket = BasketOptimizer(memoize_store_subsets=True).optimize(
        PRECOMPUTED_CANONICAL_REQUIREMENTS,
        prepared.economic_pool.matched_candidates_by_name,
        prepared.stores,
        max_stores=3,
        calculate_savings=False,
    )
    if sum(len(store.items) for store in basket.stores) != len(PRECOMPUTED_CANONICAL_REQUIREMENTS):
        raise ValueError("prepared universe representative basket is incomplete")
    universe = artifact.universe
    expected_scope = _scope_id(city)
    if universe.key.scope_id != expected_scope:
        raise ValueError("prepared universe artifact city does not match requested city")
    from grocery_data.app.domain.campaign_validity import is_campaign_only
    base_observations = [p.source_provenance.source_observed_at for p in artifact.universe.products
        if p.source_provenance is not None and not is_campaign_only(p)]
    return PreparedUniverseArtifactMetadata(
        city=universe.key.city,
        scope_id=universe.key.scope_id,
        universe_id=universe.universe_id,
        built_at=universe.built_at,
        snapshot_ids=universe.key.snapshot_ids,
        product_count=universe.stats.post_pruning_products,
        canonical_index_count=universe.stats.canonical_index_count,
        oldest_observed_at=artifact.oldest_observed_at,
        oldest_base_observed_at=min(base_observations) if base_observations else None,
    )


__all__ = [
    "ActivePreparedUniverseManifest",
    "PreparedArtifactValidator",
    "PreparedUniverseArtifactMetadata",
    "PreparedUniverseArtifactRefreshHook",
    "PreparedUniverseArtifactStore",
    "validate_backend_prepared_universe_artifact",
]
