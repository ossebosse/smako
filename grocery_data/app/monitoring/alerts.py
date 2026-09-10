"""Small, secret-safe alert abstraction for connector monitoring."""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol, TextIO, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain.enums import Chain
from grocery_data.app.monitoring.anomaly_detection import (
    AnomalySeverity,
    HealthAssessment,
)


class AlertSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Alert(BaseModel):
    """Deliberately narrow: no arbitrary payload, headers, or context mapping."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(min_length=1, max_length=100)
    severity: AlertSeverity
    summary: str = Field(min_length=1, max_length=500)
    chain: Chain | None = None
    store_external_id: str | None = Field(default=None, max_length=100)
    snapshot_id: str | None = Field(default=None, max_length=200)
    observed_value: float | int | None = None
    threshold: float | int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


@runtime_checkable
class AlertSink(Protocol):
    def send(self, alert: Alert) -> None: ...


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(authorization|api[-_ ]?key|token|password|cookie)\s*[:=]\s*"
    r"(?:bearer\s+)?[^\s,;]+"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/=]{8,}")
_OPENAI_STYLE_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b")


def redact_secrets(text: str) -> str:
    redacted = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    redacted = _BEARER.sub("Bearer [REDACTED]", redacted)
    return _OPENAI_STYLE_KEY.sub("[REDACTED]", redacted)


class ConsoleAlertSink:
    """Emit one allow-listed structured JSON event per alert."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = stream or sys.stdout

    def send(self, alert: Alert) -> None:
        record = {
            "event": "connector_alert",
            "code": alert.code,
            "severity": alert.severity.value,
            "summary": redact_secrets(alert.summary),
            "created_at": alert.created_at.isoformat(),
        }
        if alert.chain is not None:
            record["chain"] = alert.chain.value
        if alert.store_external_id is not None:
            record["store_external_id"] = alert.store_external_id
        if alert.snapshot_id is not None:
            record["snapshot_id"] = alert.snapshot_id
        if alert.observed_value is not None:
            record["observed_value"] = alert.observed_value
        if alert.threshold is not None:
            record["threshold"] = alert.threshold
        self._stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        self._stream.flush()


def alerts_from_assessment(
    assessment: HealthAssessment,
    *,
    chain: Chain | None = None,
    snapshot_id: str | None = None,
) -> tuple[Alert, ...]:
    alerts: list[Alert] = []
    for anomaly in assessment.anomalies:
        severity = (
            AlertSeverity.CRITICAL
            if anomaly.severity == AnomalySeverity.CRITICAL
            else AlertSeverity.WARNING
        )
        alerts.append(
            Alert(
                code=anomaly.code.value,
                severity=severity,
                summary=anomaly.message,
                chain=chain,
                snapshot_id=snapshot_id,
                observed_value=anomaly.observed_value,
                threshold=anomaly.threshold,
            )
        )
    return tuple(alerts)
