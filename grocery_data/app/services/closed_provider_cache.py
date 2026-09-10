from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from grocery_data.app.services.freshness import FreshnessPolicy, FreshnessState, assess_freshness

_FORBIDDEN_KEYS = frozenset(
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
_FORBIDDEN_KEY_MARKERS = (
    "api_key",
    "authorization",
    "cookie",
    "csrf",
    "page_view_id",
    "password",
    "secret",
    "session",
    "token",
    "tracking_id",
)


class ClosedProviderCacheStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    file: str
    bytes: int = Field(ge=1)
    captured_at: datetime
    age_hours: float = Field(ge=0)
    freshness: FreshnessState
    usable: bool
    postal_code: str
    stores: int = Field(ge=1)
    products: int = Field(ge=1)
    snapshot_ids: tuple[str, ...] = ()
    credentials_included: bool = False
    raw_transport_included: bool = False
    provider_requests: int = 0


class ClosedProviderCacheDocument(BaseModel):
    """Credential-free parsed cache envelope used by local refresh services."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str
    postal_code: str = Field(pattern=r"^\d{5}$")
    captured_at: datetime
    stores: tuple[dict[str, Any], ...] = Field(min_length=1)
    products: tuple[dict[str, Any], ...] = Field(min_length=1)

    @field_validator("captured_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("frozen provider cache timestamp must be timezone-aware")
        return value.astimezone(UTC)


def _normalized_key(value: object) -> str:
    return str(value).casefold().strip().replace("-", "_").replace(" ", "_")


def _assert_closed(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = _normalized_key(key)
            if normalized in _FORBIDDEN_KEYS or any(
                marker in normalized for marker in _FORBIDDEN_KEY_MARKERS
            ):
                raise ValueError("frozen provider cache contains forbidden transport material")
            _assert_closed(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_closed(nested)


def load_closed_provider_cache(
    path: Path,
    *,
    max_bytes: int = 100_000_000,
) -> tuple[ClosedProviderCacheDocument, int, Path]:
    """Read one bounded closed cache without constructing a provider client."""

    if max_bytes <= 0:
        raise ValueError("max_bytes must be greater than zero")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("frozen provider cache must be a regular file")
    size = resolved.stat().st_size
    if size <= 0 or size > max_bytes:
        raise ValueError("frozen provider cache has an invalid bounded size")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("frozen provider cache must be readable UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise TypeError("frozen provider cache root must be an object")
    _assert_closed(payload)
    try:
        document = ClosedProviderCacheDocument.model_validate(payload)
    except ValueError as exc:
        raise ValueError("frozen provider cache envelope is not closed") from exc
    if document.schema_version != "lund-frozen-external-v1":
        raise ValueError("unsupported frozen provider cache schema")
    return document, size, resolved


def inspect_closed_provider_cache(
    path: Path,
    *,
    policy: FreshnessPolicy,
    now: datetime | None = None,
    max_bytes: int = 100_000_000,
) -> ClosedProviderCacheStatus:
    """Validate the closed frozen-cache envelope without provider construction."""

    document, size, resolved = load_closed_provider_cache(path, max_bytes=max_bytes)
    stores = document.stores
    products = document.products
    snapshot_ids = tuple(
        sorted(
            {
                str(snapshot_id).strip()
                for row in (*stores, *products)
                if isinstance(row.get("source_provenance"), dict)
                and (snapshot_id := row["source_provenance"].get("source_snapshot_id"))
                and str(snapshot_id).strip()
            }
        )
    )
    captured_at = document.captured_at
    freshness = assess_freshness(captured_at, now=now, policy=policy)
    return ClosedProviderCacheStatus(
        schema_version=document.schema_version,
        file=resolved.name,
        bytes=size,
        captured_at=captured_at.astimezone(UTC),
        age_hours=freshness.age_hours or 0,
        freshness=freshness.state,
        usable=freshness.usable,
        postal_code=document.postal_code,
        stores=len(stores),
        products=len(products),
        snapshot_ids=snapshot_ids,
    )


__all__ = [
    "ClosedProviderCacheDocument",
    "ClosedProviderCacheStatus",
    "inspect_closed_provider_cache",
    "load_closed_provider_cache",
]
