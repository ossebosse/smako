from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from grocery_data.app.domain.physical_price import DigitalPriceCandidate
from grocery_data.app.storage.repositories import (
    ExternalPriceCandidateRepository,
    ExternalPriceSnapshotImport,
)


class CredentialFreeExternalPriceSnapshot(BaseModel):
    """Closed file envelope for an already licensed provider snapshot.

    Every nested candidate also has ``extra='forbid'``. Credential, cookie,
    session, header, or arbitrary transport data therefore fails validation
    instead of being silently retained.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["external-price-candidates-v1"] = Field(alias="schema")
    candidates: tuple[DigitalPriceCandidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def one_closed_snapshot_scope(self) -> CredentialFreeExternalPriceSnapshot:
        first = self.candidates[0]
        scope = (
            first.physical_store_id,
            first.source_provider,
            first.grocery_context_id,
            first.source_snapshot_id,
        )
        if any(
            (
                candidate.physical_store_id,
                candidate.source_provider,
                candidate.grocery_context_id,
                candidate.source_snapshot_id,
            )
            != scope
            for candidate in self.candidates
        ):
            raise ValueError("external price import must contain one exact snapshot scope")
        return self


class ExternalPriceSnapshotImportService:
    """Import sanitized provider data into the local validation cache only."""

    def __init__(self, session: Session) -> None:
        self.repository = ExternalPriceCandidateRepository(session)

    def import_payload(
        self,
        payload: CredentialFreeExternalPriceSnapshot | Mapping[str, Any],
    ) -> ExternalPriceSnapshotImport:
        envelope = (
            payload
            if isinstance(payload, CredentialFreeExternalPriceSnapshot)
            else CredentialFreeExternalPriceSnapshot.model_validate(payload)
        )
        return self.repository.import_snapshot(envelope.candidates)

    def import_file(
        self,
        path: Path,
        *,
        max_bytes: int = 100_000_000,
    ) -> ExternalPriceSnapshotImport:
        """Read one bounded UTF-8 JSON export; never contacts a provider."""

        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        size = path.stat().st_size
        if size > max_bytes:
            raise ValueError("external price snapshot exceeds configured file-size limit")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("external price snapshot must be readable UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise TypeError("external price snapshot root must be an object")
        return self.import_payload(payload)


__all__ = [
    "CredentialFreeExternalPriceSnapshot",
    "ExternalPriceSnapshotImportService",
]
