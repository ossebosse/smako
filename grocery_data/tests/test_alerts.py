import io
import json

import pytest
from pydantic import ValidationError

from grocery_data.app.domain.enums import Chain, ConnectorStatus
from grocery_data.app.monitoring.alerts import (
    Alert,
    AlertSeverity,
    AlertSink,
    ConsoleAlertSink,
    alerts_from_assessment,
)
from grocery_data.app.monitoring.anomaly_detection import (
    AnomalyCode,
    AnomalySeverity,
    DetectedAnomaly,
    HealthAssessment,
)


def test_console_sink_outputs_allowlisted_json_and_redacts_secrets() -> None:
    stream = io.StringIO()
    sink = ConsoleAlertSink(stream)
    alert = Alert(
        code="schema_changed",
        severity=AlertSeverity.WARNING,
        summary="authorization=Bearer-supersecret api_key=topsecret sk-abcdefghijk",
        chain=Chain.WILLYS,
        snapshot_id="snapshot-1",
    )

    sink.send(alert)
    record = json.loads(stream.getvalue())

    assert isinstance(sink, AlertSink)
    assert record["event"] == "connector_alert"
    assert record["chain"] == "willys"
    assert "topsecret" not in stream.getvalue()
    assert "abcdefghijk" not in stream.getvalue()
    assert "raw_payload" not in record


def test_alert_model_rejects_arbitrary_payload() -> None:
    with pytest.raises(ValidationError):
        Alert(
            code="broken",
            severity=AlertSeverity.CRITICAL,
            summary="connector failed",
            raw_payload={"token": "secret"},  # type: ignore[call-arg]
        )


def test_assessment_converts_to_alerts_without_raw_context() -> None:
    assessment = HealthAssessment(
        status=ConnectorStatus.BROKEN,
        anomalies=(
            DetectedAnomaly(
                code=AnomalyCode.PRODUCT_COUNT_DROP,
                severity=AnomalySeverity.CRITICAL,
                message="product count dropped by 80.0%",
                observed_value=0.8,
                threshold=0.7,
            ),
        ),
    )

    alerts = alerts_from_assessment(assessment, chain=Chain.WILLYS)

    assert len(alerts) == 1
    assert alerts[0].severity == AlertSeverity.CRITICAL
    assert alerts[0].observed_value == 0.8
