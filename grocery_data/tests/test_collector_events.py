import io
import json

import pytest
from pydantic import ValidationError

from grocery_data.app.domain import Chain, ConnectorStatus
from grocery_data.app.monitoring import (
    CollectorEvent,
    CollectorEventSink,
    CollectorEventType,
    ConsoleCollectorEventSink,
)


def test_console_collector_event_is_allowlisted_structured_json() -> None:
    stream = io.StringIO()
    sink = ConsoleCollectorEventSink(stream)
    event = CollectorEvent(
        event=CollectorEventType.FINISHED,
        chain=Chain.WILLYS,
        scope="lund",
        snapshot_id="snapshot-1",
        products=12_821,
        errors=4,
        request_count=42,
        runtime_ms=31_902,
        status=ConnectorStatus.HEALTHY,
    )

    sink.emit(event)
    record = json.loads(stream.getvalue())

    assert isinstance(sink, CollectorEventSink)
    assert record == {
        "chain": "willys",
        "created_at": event.model_dump(mode="json")["created_at"],
        "errors": 4,
        "event": "collector_finished",
        "products": 12_821,
        "request_count": 42,
        "runtime_ms": 31_902,
        "scope": "lund",
        "snapshot_id": "snapshot-1",
        "status": "healthy",
    }


def test_collector_event_rejects_arbitrary_secret_context() -> None:
    with pytest.raises(ValidationError):
        CollectorEvent(
            event=CollectorEventType.FAILED,
            chain=Chain.WILLYS,
            scope="lund",
            snapshot_id="snapshot-1",
            status=ConnectorStatus.BROKEN,
            exception_message="postgresql://user:secret@example/db",  # type: ignore[call-arg]
        )


def test_console_collector_event_redacts_dsn_in_identifier_field() -> None:
    stream = io.StringIO()
    ConsoleCollectorEventSink(stream).emit(
        CollectorEvent(
            event=CollectorEventType.STARTED,
            chain=Chain.WILLYS,
            scope="postgresql://user:secret@example/db",
            snapshot_id="snapshot-1",
        )
    )

    assert json.loads(stream.getvalue())["scope"] == "[REDACTED]"
    assert "secret" not in stream.getvalue()
