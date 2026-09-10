import json
import subprocess

from grocery_data import relay_status


def test_interrupted_log_does_not_claim_success_or_renew_receipt(tmp_path):
    receipt = {
        "observed_from": "2026-09-09T20:52:10Z",
        "sha256": "a" * 64,
        "artifact": "previous.smako-source",
    }
    path = tmp_path / "last-success.json"
    path.write_text(json.dumps(receipt))
    before = path.read_bytes()
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "run.jsonl").write_text(
        '{"event":"task_start","at":"2026-09-10T06:10:51Z"}\n'
        '{"event":"collection_start"}\n{"interrupted":'
    )
    result = relay_status.local_status(tmp_path)
    assert result["outcome"] == "INCOMPLETE_OR_RUNNING"
    assert result["last_success_observed_from"] == receipt["observed_from"]
    assert result["phases"]["collection_complete"] is None
    assert result["multi_day_reliability"] == "UNOBSERVED"
    assert path.read_bytes() == before


def test_confirmed_server_phases_are_not_fabricated_separate_timestamps(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "run.jsonl").write_text(
        '{"event":"server_activation_pass","activation":"normal_managed_refresh","at":"actual"}\n'
        '{"event":"task_success"}\n{"event":"task_end","at":"end"}\n'
    )
    result = relay_status.local_status(tmp_path)
    assert result["outcome"] == "SUCCESS"
    assert result["phases"]["server_activation_acknowledged"] == "actual"
    assert "confirmed together" in result["vps_validation_activation_index"]


def test_status_ssh_is_read_only_bounded_and_redacts_failure(monkeypatch):
    def execute(command, **kwargs):
        assert "-oBatchMode=yes" in command
        assert "10001:10001" in command
        assert kwargs["timeout"] == 60
        assert "verify_hash=True" in kwargs["input"]
        assert "source_cli import" not in kwargs["input"]
        raise subprocess.CalledProcessError(255, command, stderr="private error details")

    monkeypatch.setattr(relay_status.subprocess, "run", execute)
    result = relay_status.vps_status()
    assert result == {"status": "UNAVAILABLE", "error_type": "CalledProcessError"}
