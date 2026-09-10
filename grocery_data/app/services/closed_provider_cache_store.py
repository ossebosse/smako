from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.services.closed_provider_cache import (
    ClosedProviderCacheStatus,
    inspect_closed_provider_cache,
    load_closed_provider_cache,
)
from grocery_data.app.services.durable_files import atomic_write_bytes, require_free_space
from grocery_data.app.services.freshness import FreshnessPolicy

_SAFE_SCOPE_PART = re.compile(r"[^0-9a-zåäö]+")
_ARTIFACT_FREE_SPACE_RESERVE_BYTES = 64 * 1024 * 1024
_ValidationResult = TypeVar("_ValidationResult")


def _city_key(city: str) -> str:
    normalized = " ".join(city.casefold().split())
    if not normalized:
        raise ValueError("city is required")
    return normalized


def _city_file(city: str) -> str:
    safe = _SAFE_SCOPE_PART.sub("-", _city_key(city)).strip("-")
    if not safe:
        raise ValueError("city cannot be represented as a safe filename")
    return f"city-{safe}.json"


def _atomic_write(path: Path, payload: bytes) -> None:
    atomic_write_bytes(path, payload)


class ActiveClosedProviderCacheManifest(BaseModel):
    """Durable pointer to one sanitized, immutable licensed-provider cache."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "active-closed-provider-cache-v1"
    city: str = Field(min_length=1)
    postal_code: str = Field(pattern=r"^\d{5}$")
    captured_at: datetime
    activated_at: datetime
    stores: int = Field(gt=0)
    products: int = Field(gt=0)
    snapshot_ids: tuple[str, ...] = ()
    artifact_file: str = Field(pattern=r"^artifacts/[0-9a-f]{64}\.json$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_bytes: int = Field(gt=0)

    @field_validator("captured_at", "activated_at")
    @classmethod
    def aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider-cache timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def safe_artifact_path(self) -> ActiveClosedProviderCacheManifest:
        path = PurePosixPath(self.artifact_file)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("provider-cache artifact path must stay inside its store")
        return self


class StagedClosedProviderCacheArtifact(BaseModel):
    """Immutable descriptor for a sanitized candidate awaiting identity checks."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "staged-closed-provider-cache-v1"
    city: str = Field(min_length=1)
    postal_code: str = Field(pattern=r"^\d{5}$")
    captured_at: datetime
    stores: int = Field(gt=0)
    products: int = Field(gt=0)
    snapshot_ids: tuple[str, ...] = ()
    artifact_file: str = Field(pattern=r"^artifacts/[0-9a-f]{64}\.json$")
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_bytes: int = Field(gt=0)

    @field_validator("captured_at")
    @classmethod
    def aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider-cache timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def safe_artifact_path(self) -> StagedClosedProviderCacheArtifact:
        path = PurePosixPath(self.artifact_file)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("provider-cache artifact path must stay inside its store")
        return self


class ClosedProviderCacheValidationDecision[ValidationValue](BaseModel):
    """Explicit accept/reject result returned by an external identity validator."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted: bool
    value: ValidationValue
    reason_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]+$")

    @model_validator(mode="after")
    def rejection_has_reason(self) -> ClosedProviderCacheValidationDecision[ValidationValue]:
        if not self.accepted and not self.reason_code:
            raise ValueError("rejected provider-cache validation requires a reason code")
        return self


class ClosedProviderCacheValidationRejected(ValueError):
    """Safe rejection raised before the active manifest can be replaced."""

    def __init__(self, reason_code: str) -> None:
        super().__init__("provider-cache identity validation rejected candidate")
        self.reason_code = reason_code


class ClosedProviderCacheArtifactStore:
    """Content-addressed LKG storage for closed external-provider caches.

    Collection writes a new immutable cache first. Only a fully parsed, fresh,
    credential-free document can replace the small active city manifest. The
    previous manifest therefore remains usable after collection or validation
    failure, and meal requests never contact the licensed provider.
    """

    def __init__(self, root: Path, *, max_bytes: int = 100_000_000) -> None:
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def active_manifest_path(self, city: str) -> Path:
        return self.root / "active" / _city_file(city)

    def active_manifest_bytes(self, city: str) -> bytes | None:
        path = self.active_manifest_path(city)
        return path.read_bytes() if path.is_file() else None

    def restore_active_manifest(self, city: str, previous: bytes | None) -> None:
        """Restore one previously captured active pointer after a later commit fails.

        Provider-cache bytes are immutable and content-addressed, but their DB
        identity links are committed separately.  The refresh orchestrator can
        therefore use this narrow rollback seam when link activation fails
        after the manifest swap.  A supplied manifest is fully revalidated
        against its stored artifact before it is restored.
        """

        city_name = city.strip()
        path = self.active_manifest_path(city_name)
        if previous is None:
            path.unlink(missing_ok=True)
            return
        try:
            manifest = ActiveClosedProviderCacheManifest.model_validate_json(previous)
        except (UnicodeError, ValueError) as exc:
            raise ValueError("previous provider-cache manifest is invalid") from exc
        if _city_key(manifest.city) != _city_key(city_name):
            raise ValueError("previous provider-cache manifest has the wrong city")
        artifact = self._artifact_path(manifest.artifact_file)
        if not artifact.is_file() or artifact.stat().st_size != manifest.artifact_bytes:
            raise ValueError("previous provider-cache artifact is missing or truncated")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != manifest.artifact_sha256:
            raise ValueError("previous provider-cache artifact hash mismatch")
        _atomic_write(path, previous)

    def read_active(
        self,
        city: str,
        *,
        verify_hash: bool = True,
    ) -> ActiveClosedProviderCacheManifest | None:
        path = self.active_manifest_path(city)
        if not path.exists():
            return None
        if not path.is_file():
            raise ValueError("active provider-cache manifest is not a regular file")
        try:
            manifest = ActiveClosedProviderCacheManifest.model_validate_json(path.read_bytes())
        except (OSError, UnicodeError, ValueError) as exc:
            raise ValueError("active provider-cache manifest is invalid") from exc
        if _city_key(manifest.city) != _city_key(city):
            raise ValueError("active provider-cache manifest has the wrong city")
        artifact = (self.root / PurePosixPath(manifest.artifact_file)).resolve()
        try:
            artifact.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("active provider-cache artifact escapes its store") from exc
        if not artifact.is_file() or artifact.stat().st_size != manifest.artifact_bytes:
            raise ValueError("active provider-cache artifact is missing or truncated")
        if verify_hash and hashlib.sha256(artifact.read_bytes()).hexdigest() != (
            manifest.artifact_sha256
        ):
            raise ValueError("active provider-cache artifact hash mismatch")
        return manifest

    def resolve_active(
        self,
        city: str,
        *,
        policy: FreshnessPolicy,
        now: datetime | None = None,
    ) -> tuple[Path, ClosedProviderCacheStatus, ActiveClosedProviderCacheManifest] | None:
        manifest = self.read_active(city)
        if manifest is None:
            return None
        artifact = (self.root / PurePosixPath(manifest.artifact_file)).resolve()
        status = inspect_closed_provider_cache(artifact, policy=policy, now=now)
        return artifact, status, manifest

    def _artifact_path(self, artifact_file: str) -> Path:
        artifact = (self.root / PurePosixPath(artifact_file)).resolve()
        try:
            artifact.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("provider-cache artifact escapes its store") from exc
        return artifact

    def _verify_staged(
        self,
        staged: StagedClosedProviderCacheArtifact,
        *,
        policy: FreshnessPolicy,
        now: datetime | None,
    ) -> tuple[Path, ClosedProviderCacheStatus]:
        artifact = self._artifact_path(staged.artifact_file)
        if not artifact.is_file() or artifact.stat().st_size != staged.artifact_bytes:
            raise ValueError("staged provider-cache artifact is missing or truncated")
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != staged.artifact_sha256:
            raise ValueError("staged provider-cache artifact hash mismatch")
        document, size, _ = load_closed_provider_cache(
            artifact,
            max_bytes=self.max_bytes,
        )
        status = inspect_closed_provider_cache(
            artifact,
            policy=policy,
            now=now,
            max_bytes=self.max_bytes,
        )
        if not status.usable:
            raise ValueError("provider-cache candidate is stale at activation")
        if (
            size != staged.artifact_bytes
            or document.postal_code != staged.postal_code
            or document.captured_at != staged.captured_at
            or status.stores != staged.stores
            or status.products != staged.products
            or status.snapshot_ids != staged.snapshot_ids
        ):
            raise ValueError("staged provider-cache descriptor does not match its artifact")
        return artifact, status

    def stage(
        self,
        candidate: Path,
        *,
        city: str,
        policy: FreshnessPolicy,
        evaluated_at: datetime | None = None,
    ) -> StagedClosedProviderCacheArtifact:
        """Persist one closed candidate without changing the active LKG pointer.

        The returned content-addressed artifact is safe to pass to a database
        identity validator. Staging performs closed-envelope, credential,
        freshness, hash and stored-byte validation, but never activates data.
        """

        city_name = city.strip()
        before = self.active_manifest_bytes(city_name)
        try:
            document, size, resolved = load_closed_provider_cache(
                candidate,
                max_bytes=self.max_bytes,
            )
            status = inspect_closed_provider_cache(
                resolved,
                policy=policy,
                now=evaluated_at,
                max_bytes=self.max_bytes,
            )
            if not status.usable:
                raise ValueError("provider-cache candidate is stale at activation")
            payload = resolved.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            relative = PurePosixPath("artifacts") / f"{digest}.json"
            artifact = self.root / Path(*relative.parts)
            if artifact.exists():
                if (
                    not artifact.is_file()
                    or artifact.stat().st_size != size
                    or hashlib.sha256(artifact.read_bytes()).hexdigest() != digest
                ):
                    raise ValueError("content-addressed provider-cache artifact conflicts")
            else:
                require_free_space(
                    artifact.parent,
                    required_bytes=len(payload),
                    reserve_bytes=_ARTIFACT_FREE_SPACE_RESERVE_BYTES,
                )
                _atomic_write(artifact, payload)

            stored_document, stored_size, _ = load_closed_provider_cache(
                artifact,
                max_bytes=self.max_bytes,
            )
            if stored_document != document or stored_size != size:
                raise ValueError("stored provider-cache artifact changed during staging")
            staged = StagedClosedProviderCacheArtifact(
                city=city_name,
                postal_code=document.postal_code,
                captured_at=document.captured_at,
                stores=status.stores,
                products=status.products,
                snapshot_ids=status.snapshot_ids,
                artifact_file=relative.as_posix(),
                artifact_sha256=digest,
                artifact_bytes=size,
            )
            self._verify_staged(staged, policy=policy, now=evaluated_at)
        except Exception:
            if self.active_manifest_bytes(city_name) != before:
                raise RuntimeError(
                    "active provider-cache manifest changed after failed staging"
                ) from None
            raise
        return staged

    def activate_staged(
        self,
        staged: StagedClosedProviderCacheArtifact,
        *,
        policy: FreshnessPolicy,
        validator: Callable[[Path], ClosedProviderCacheValidationDecision[_ValidationResult]],
        activated_at: datetime | None = None,
    ) -> tuple[ActiveClosedProviderCacheManifest, _ValidationResult]:
        """Validate DB identity first, then atomically swap the active pointer.

        ``validator`` receives the sanitized immutable artifact and returns an
        explicit decision. Rejections and raised validation errors leave the
        active manifest untouched. The artifact is reverified after validation
        so a validator cannot activate bytes other than those it inspected.
        """

        before = self.active_manifest_bytes(staged.city)
        try:
            artifact, _ = self._verify_staged(
                staged,
                policy=policy,
                now=activated_at,
            )
            decision = validator(artifact)
            if not isinstance(decision, ClosedProviderCacheValidationDecision):
                raise TypeError("provider-cache validator must return an explicit decision")
            if not decision.accepted:
                raise ClosedProviderCacheValidationRejected(str(decision.reason_code))
            _artifact, status = self._verify_staged(
                staged,
                policy=policy,
                now=activated_at,
            )
            timestamp = activated_at or datetime.now(tz=UTC)
            manifest = ActiveClosedProviderCacheManifest(
                city=staged.city,
                postal_code=staged.postal_code,
                captured_at=staged.captured_at,
                activated_at=timestamp,
                stores=status.stores,
                products=status.products,
                snapshot_ids=status.snapshot_ids,
                artifact_file=staged.artifact_file,
                artifact_sha256=staged.artifact_sha256,
                artifact_bytes=staged.artifact_bytes,
            )
            encoded = json.dumps(
                manifest.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            ActiveClosedProviderCacheManifest.model_validate_json(encoded)
            _atomic_write(self.active_manifest_path(staged.city), encoded)
        except Exception:
            if self.active_manifest_bytes(staged.city) != before:
                raise RuntimeError(
                    "active provider-cache manifest changed after failed validation"
                ) from None
            raise
        return manifest, decision.value

    def activate_validated(
        self,
        candidate: Path,
        *,
        city: str,
        policy: FreshnessPolicy,
        validator: Callable[[Path], ClosedProviderCacheValidationDecision[_ValidationResult]],
        activated_at: datetime | None = None,
    ) -> tuple[ActiveClosedProviderCacheManifest, _ValidationResult]:
        """Stage a candidate, validate DB identity, and activate on acceptance."""

        staged = self.stage(
            candidate,
            city=city,
            policy=policy,
            evaluated_at=activated_at,
        )
        return self.activate_staged(
            staged,
            policy=policy,
            validator=validator,
            activated_at=activated_at,
        )

    def activate(
        self,
        candidate: Path,
        *,
        city: str,
        policy: FreshnessPolicy,
        activated_at: datetime | None = None,
    ) -> ActiveClosedProviderCacheManifest:
        manifest, _ = self.activate_validated(
            candidate,
            city=city,
            policy=policy,
            validator=lambda _artifact: ClosedProviderCacheValidationDecision(
                accepted=True,
                value=None,
            ),
            activated_at=activated_at,
        )
        return manifest


__all__ = [
    "ActiveClosedProviderCacheManifest",
    "ClosedProviderCacheArtifactStore",
    "ClosedProviderCacheValidationDecision",
    "ClosedProviderCacheValidationRejected",
    "StagedClosedProviderCacheArtifact",
]
