import json
import subprocess
from pathlib import Path

import pytest

from grocery_data import local_relay as relay
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock
from grocery_data.tests.test_source_artifact import artifact


def pending(root):
    destination = root / "completed"
    destination.mkdir()
    return artifact(destination)


def forbidden(*args):
    raise AssertionError("unexpected collection or server mutation")


def test_pending_success_receipt_duplicate_does_not_recrawl(tmp_path):
    p = pending(tmp_path)
    calls = []
    assert (
        relay.run(
            tmp_path,
            collect=forbidden,
            push=lambda a: calls.append(a.artifact),
            activate=lambda h: {"activation": "already_active"},
        )
        == 0
    )
    receipt = json.loads((tmp_path / "last-success.json").read_bytes())
    assert receipt["artifact"] == str(p)
    assert relay.run(tmp_path, collect=forbidden, push=forbidden, activate=forbidden) == 0
    assert calls == [p]


def test_new_collection_automatically_validates_pushes_and_activates(tmp_path):
    calls = []

    async def collect(args):
        calls.append("collect")
        p = pending(args.workspace)
        return {"status": "complete", "artifact": str(p), "requests": 15, "rows": 200}

    def push(args):
        assert args.artifact.is_file()
        calls.append("push")

    def activate(digest):
        assert len(digest) == 64
        calls.append("activate")
        return {"activation": "normal_managed_refresh"}

    assert relay.run(tmp_path, collect=collect, push=push, activate=activate) == 0
    assert calls == ["collect", "push", "activate"]
    assert (
        json.loads((tmp_path / "last-success.json").read_bytes())["server"]["activation"]
        == "normal_managed_refresh"
    )


def test_local_workflow_lock_blocks_duplicate(tmp_path):
    with RefreshRunLock(tmp_path / "local-workflow.lock"):
        assert relay.run(tmp_path, collect=forbidden, push=forbidden, activate=forbidden) == 0
    assert "already_running" in next((tmp_path / "logs").glob("*.jsonl")).read_text()


def test_failed_ssh_is_bounded_and_later_recovers_without_recrawl(tmp_path):
    p = pending(tmp_path)
    before = p.read_bytes()
    delays = []

    def failed(args):
        raise subprocess.CalledProcessError(255, "ssh", stderr="secret must not be logged")

    assert (
        relay.run(tmp_path, collect=forbidden, push=failed, activate=forbidden, delay=delays.append)
        == 1
    )
    assert delays == [30, 120]
    assert not (tmp_path / "last-success.json").exists()
    assert p.read_bytes() == before
    assert (
        relay.run(
            tmp_path,
            collect=forbidden,
            push=lambda a: None,
            activate=lambda h: {"activation": "normal_managed_refresh"},
        )
        == 0
    )
    assert all("secret must not" not in x.read_text() for x in (tmp_path / "logs").glob("*"))


def test_server_validation_rejection_is_not_retried(tmp_path):
    pending(tmp_path)

    def reject(digest):
        raise subprocess.CalledProcessError(1, "import")

    assert (
        relay.run(
            tmp_path, collect=forbidden, push=lambda a: None, activate=reject, delay=forbidden
        )
        == 1
    )
    assert not (tmp_path / "last-success.json").exists()


def test_interrupted_collection_keeps_previous_artifact_and_does_not_upload(tmp_path):
    previous = tmp_path / "previous.smako-source"
    previous.write_bytes(b"previous valid file remains untouched")

    async def interrupt(args):
        (tmp_path / "unfinished.partial").write_bytes(b"incomplete")
        raise InterruptedError()

    assert relay.run(tmp_path, collect=interrupt, push=forbidden, activate=forbidden) == 1
    assert previous.read_bytes() == b"previous valid file remains untouched"
    assert not (tmp_path / "last-success.json").exists()


def test_tampered_pending_never_uploads(tmp_path):
    p = pending(tmp_path)
    p.write_bytes(p.read_bytes()[:-100])

    async def fail(args):
        raise InterruptedError()

    assert relay.run(tmp_path, collect=fail, push=forbidden, activate=forbidden) == 1


def test_remote_activation_command_and_safe_result(monkeypatch):
    def execute(command, **kwargs):
        assert command[-1].endswith("/" + "a" * 64 + ".smako-source")
        assert "-oBatchMode=yes" in command and "10001:10001" in command
        assert "docker" in command and "smako-scheduler-1" in command
        assert "/opt/smako/compose" not in command
        assert kwargs["capture_output"] and kwargs["timeout"] == 2700
        return subprocess.CompletedProcess(
            command, 0, 'other output\n{"activation":"already_active","secret":"not returned"}'
        )

    monkeypatch.setattr(relay.subprocess, "run", execute)
    assert relay.remote_activate("a" * 64) == {"activation": "already_active"}


def test_upload_uses_running_container_without_reading_protected_compose_env(tmp_path, monkeypatch):
    artifact = pending(tmp_path)

    def execute(command, **kwargs):
        assert "/opt/smako/compose" not in command
        assert command[-8:] == [
            "docker",
            "exec",
            "-i",
            "--user",
            "10001:10001",
            "smako-scheduler-1",
            "python",
            "-",
        ]
        assert kwargs["check"] and kwargs["capture_output"]
        assert "transport hash mismatch" in kwargs["input"]
        assert "inbox artifact cannot be a symlink" in kwargs["input"]
        return subprocess.CompletedProcess(command, 0, "uploaded_to_inbox_only\n")

    monkeypatch.setattr(relay.source_cli.subprocess, "run", execute)
    from types import SimpleNamespace

    assert (
        relay.source_cli.push(SimpleNamespace(artifact=artifact, host="smako"))["status"]
        == "uploaded"
    )


def test_task_script_has_correct_limited_wake_and_manual_password_boundary():
    script = Path("deploy/scripts/install_willys_task.ps1").read_text(encoding="utf-8-sig")
    for value in (
        "-MultipleInstances IgnoreNew",
        "-StartWhenAvailable",
        "-WakeToRun",
        "-LogonType Interactive",
        "-RunLevel Limited",
        "Get-ScheduledTaskInfo",
        "Get-ScheduledTask",
        "collect_willys_local.ps1",
        "-NonInteractive",
        "-WorkingDirectory",
    ):
        assert value in script
    assert "-Password" not in script and "-RestartCount" not in script


@pytest.mark.parametrize("code", [1, 2, 23])
def test_non_transport_failure_no_retry(code):
    def action():
        raise subprocess.CalledProcessError(code, "server")

    with pytest.raises(subprocess.CalledProcessError):
        relay.transient_retry(action, lambda *a, **k: None, delay=forbidden)
