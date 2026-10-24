from __future__ import annotations

import errno
from pathlib import Path
from types import SimpleNamespace

import pytest

from grocery_data.app.services import durable_files
from grocery_data.app.services.durable_files import (
    InsufficientStorageError,
    atomic_write_bytes,
)


def test_atomic_write_enospc_preserves_previous_file_and_cleans_scratch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    destination = tmp_path / "critical.json"
    destination.write_bytes(b'{"status":"last-good"}')

    def disk_full(_descriptor: int) -> None:
        raise OSError(errno.ENOSPC, "fault injection")

    monkeypatch.setattr(durable_files.os, "fsync", disk_full)

    with pytest.raises(OSError) as error:
        atomic_write_bytes(destination, b'{"status":"replacement"}')

    assert error.value.errno == errno.ENOSPC
    assert destination.read_bytes() == b'{"status":"last-good"}'
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_write_validation_failure_preserves_previous_file(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "critical.json"
    destination.write_bytes(b"last-good")

    def reject(_candidate: Path) -> None:
        raise ValueError("candidate rejected")

    with pytest.raises(ValueError, match="candidate rejected"):
        atomic_write_bytes(destination, b"complete-but-invalid", validator=reject)

    assert destination.read_bytes() == b"last-good"
    assert not list(tmp_path.glob(".*.tmp"))


def test_storage_preflight_fails_before_scratch_creation_with_structured_counts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        durable_files.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(total=100, used=80, free=20),
    )
    destination = tmp_path / "large-artifact.json"

    with pytest.raises(InsufficientStorageError) as error:
        atomic_write_bytes(destination, b"x" * 16, reserve_bytes=8)

    assert error.value.errno == errno.ENOSPC
    assert error.value.status() == {
        "status": "failed",
        "reason": "insufficient_storage",
        "free_bytes": 20,
        "required_bytes": 16,
        "reserve_bytes": 8,
    }
    assert not destination.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_atomic_write_releases_input_before_validator_builds_another_graph(tmp_path):
    released = []

    class TrackedBytes(bytes):
        def __del__(self):
            released.append(True)

    destination = tmp_path / 'bounded.json'

    def validate(candidate):
        assert released == [True]
        assert candidate.read_bytes() == b'complete-payload'

    atomic_write_bytes(destination, TrackedBytes(b'complete-payload'), validator=validate)
    assert destination.read_bytes() == b'complete-payload'

