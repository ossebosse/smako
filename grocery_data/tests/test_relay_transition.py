import hashlib
import json

import pytest

from grocery_data.app.services.manual_refresh_operations import (
    RefreshAlreadyRunningError,
    RefreshRunLock,
)
from grocery_data.relay_transition import preserve
from grocery_data.tests.test_source_artifact import artifact


def test_transition_resume_retains_unpublished_and_receipts(tmp_path):
    root = tmp_path / "old"
    root.mkdir()
    candidate = artifact(root)
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    archive = tmp_path / "archive"
    first = preserve(workspace=root, archive=archive)
    assert (
        next(v for v in first["files"].values() if v["kind"] == "artifact")["status"]
        == "pending_delivery"
    )
    assert preserve(workspace=root, archive=archive) == first
    assert candidate.read_bytes() == (archive / "objects" / digest).read_bytes()
    (root / "last-success.json").write_text(
        json.dumps({"sha256": digest, "server": {"activation": "normal_managed_refresh"}})
    )
    second = preserve(workspace=root, archive=archive)
    assert (
        next(v for v in second["files"].values() if v["kind"] == "artifact")["status"]
        == "acknowledged"
    )
    assert len(list((archive / "inventories").glob("*.json"))) == 2


def test_transition_obeys_active_relay_lock(tmp_path):
    root = tmp_path / "old"
    root.mkdir()
    with RefreshRunLock(root / "local-workflow.lock"), pytest.raises(RefreshAlreadyRunningError):
        preserve(workspace=root, archive=tmp_path / "archive")
    assert not (tmp_path / "archive").exists()
