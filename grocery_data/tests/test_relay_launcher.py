import os
import subprocess
import time
from pathlib import Path

import pytest


@pytest.mark.skipif(os.name != "nt", reason="Windows task process-lifetime contract")
def test_launcher_exit_kills_child_process(tmp_path):
    lifetime = Path("deploy/scripts/relay_process_lifetime.ps1").resolve()
    child_script = tmp_path / "child.py"
    child_script.write_text("import time\ntime.sleep(60)\n")
    pid_file = tmp_path / "child.pid"
    launcher = tmp_path / "launcher.ps1"
    launcher.write_text(
        "$ErrorActionPreference='Stop'\n"
        f". '{lifetime.as_posix()}'\n"
        f"$child=Start-Process py -ArgumentList @('-3.12','{child_script.as_posix()}') "
        "-WindowStyle Hidden -PassThru\n"
        f"$child.Id | Set-Content '{pid_file.as_posix()}'\n"
        "$child.WaitForExit()\n"
    )
    parent = subprocess.Popen(
        ["pwsh", "-NoProfile", "-NonInteractive", "-File", str(launcher)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 15
        while not pid_file.exists() and time.monotonic() < deadline:
            assert parent.poll() is None
            time.sleep(0.1)
        assert pid_file.exists()
        child_pid = int(pid_file.read_text(encoding="utf-8-sig").strip())
        from grocery_data.app.services.manual_refresh_operations import process_is_alive

        assert process_is_alive(child_pid)
        parent.terminate()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 5
        while process_is_alive(child_pid) and time.monotonic() < deadline:
            time.sleep(0.1)
        assert not process_is_alive(child_pid)
    finally:
        if parent.poll() is None:
            parent.terminate()
            parent.wait(timeout=5)


def test_preflight_is_explicit_one_shot_and_normal_relay_is_default():
    script = Path("deploy/scripts/collect_willys_local.ps1").read_text(encoding="utf-8")
    assert "relay_process_lifetime.ps1" in script
    assert "preflight.request" in script and "preflight.consumed" in script
    assert script.index("Move-Item") < script.index("grocery_data.relay_preflight")
    assert "grocery_data.local_relay --workspace" in script
    assert "-Password" not in script and "-RunLevel Highest" not in script
