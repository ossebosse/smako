import json
import sqlite3
import subprocess

import pytest

from grocery_data.app.services.failure_diagnostics import failure_details
from grocery_data.local_relay import remote_activate
from grocery_data.relay_config import RelayTransport, load_transport


def test_legacy_transport_defaults_and_explicit_isolated_target(tmp_path, monkeypatch):
    assert load_transport(None) == RelayTransport()
    path = tmp_path / "test-config.json"
    path.write_text(json.dumps({"schema": "smako-relay-config-v1", "ssh_host": "smako",
        "container": "smako-release-test-receiver", "inbox": "/work/raw/source-inbox/willys"}))
    config = load_transport(path)
    commands = []
    def execute(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, '{"activation":"already_active"}')
    monkeypatch.setattr(subprocess, "run", execute)
    assert remote_activate("a" * 64, config) == {"activation": "already_active"}
    assert "smako-scheduler-1" not in commands[0]
    assert "smako-release-test-receiver" in commands[0]
    assert commands[0][-1] == "/work/raw/source-inbox/willys/" + "a" * 64 + ".smako-source"


@pytest.mark.parametrize("patch", [{"ssh_host":"-oProxyCommand=x"}, {"container":"x;touch /tmp/a"},
    {"inbox":"/work/../production"}, {"inbox":"relative"}, {"token":"not-supported"}])
def test_invalid_or_secret_configuration_fails_closed(tmp_path, patch):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema":"smako-relay-config-v1", **patch}))
    with pytest.raises((ValueError, TypeError)):
        load_transport(path)


def test_sqlite_root_cause_is_retained_without_sqlalchemy_parameters():
    from sqlalchemy.exc import OperationalError
    try:
        with sqlite3.connect(":memory:") as db:
            db.execute("select * from missing_release_table")
    except sqlite3.Error as inner:
        outer = OperationalError("INSERT private", {"token":"do-not-log"}, inner)
        rows = failure_details(outer)
    assert rows[-1]["reason"] == "no such table: missing_release_table"
    assert rows[-1]["sqlite_errorname"] == "SQLITE_ERROR"
    assert rows[-1]["frames"]
    assert "do-not-log" not in json.dumps(rows)
    assert "INSERT private" not in json.dumps(rows)


async def test_database_failure_keeps_inbox_bytes_queued(tmp_path, monkeypatch):
    from hashlib import sha256

    from grocery_data.app.services import source_artifact
    # Explicit fault injection before source parsing; not a retailer fixture.
    payload = b"synthetic transport envelope for SQLite failure injection"
    path = tmp_path / (sha256(payload).hexdigest() + ".smako-source")
    path.write_bytes(payload)
    async def broken(*args, **kwargs):
        with sqlite3.connect(":memory:") as db:
            db.execute("select * from missing_release_table")
    monkeypatch.setattr(source_artifact, "import_source_candidate", broken)
    reports = await source_artifact.import_source_inbox(None, None, tmp_path)
    assert reports[0]["status"] == "deferred"
    assert reports[0]["causes"][-1]["reason"] == "no such table: missing_release_table"
    assert path.read_bytes() == payload
    assert not (tmp_path / "rejected").exists()
