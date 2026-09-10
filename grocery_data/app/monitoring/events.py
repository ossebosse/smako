"""Secret-safe structured lifecycle events for collector runs."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, TextIO, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain.enums import Chain, ConnectorStatus
from grocery_data.app.monitoring.alerts import redact_secrets

_SAFE_IDENTIFIER = re.compile(r"^[\w .-]+$", re.UNICODE)


def _safe_identifier(value: str) -> str:
    redacted = redact_secrets(value)
    if redacted != value or not _SAFE_IDENTIFIER.fullmatch(redacted):
        return "[REDACTED]"
    return redacted


class CollectorEventType(StrEnum):
    STARTED = "collector_started"
    FINISHED = "collector_finished"
    FAILED = "collector_failed"


class CollectorEvent(BaseModel):
    """An intentionally closed schema that cannot carry source or secret data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event: CollectorEventType
    chain: Chain
    scope: str = Field(min_length=1, max_length=200)
    snapshot_id: str = Field(min_length=1, max_length=200)
    products: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    request_count: int = Field(default=0, ge=0)
    runtime_ms: int = Field(default=0, ge=0)
    status: ConnectorStatus = ConnectorStatus.UNKNOWN
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


@runtime_checkable
class CollectorEventSink(Protocol):
    def emit(self, event: CollectorEvent) -> None: ...


class ConsoleCollectorEventSink:
    """Write one allow-listed JSON object per collector lifecycle event."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def emit(self, event: CollectorEvent) -> None:
        record = event.model_dump(mode="json")
        record["scope"] = _safe_identifier(event.scope)
        record["snapshot_id"] = _safe_identifier(event.snapshot_id)
        self._stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self._stream.flush()
