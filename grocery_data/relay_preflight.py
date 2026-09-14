"""Small scheduled-context probe. Never collects products or activates sources."""

import argparse
import ctypes
import json
import os
import socket
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep

import httpx

from grocery_data import source_cli  # noqa: F401 - verify collector dependency imports
from grocery_data.app.services.durable_files import atomic_write_bytes


def probe(workspace: Path):
    result = {"started_at": datetime.now(UTC).isoformat(), "checks": {}}
    checks = result["checks"]
    session = ctypes.c_ulong()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)):
        raise OSError("Unable to determine task session")
    result["windows_session_id"] = session.value
    result["worker_pid"] = os.getpid()
    checks["noninteractive_session"] = session.value == 0
    result["user"] = subprocess.run(
        ["whoami"], text=True, capture_output=True, check=True, timeout=10
    ).stdout.strip()
    checks["repository_and_dependencies"] = True
    with NamedTemporaryFile(dir=workspace, prefix=".preflight-", suffix=".tmp") as handle:
        handle.write(b"relay preflight, no product observations")
        handle.flush()
        os.fsync(handle.fileno())
        checks["workspace_write"] = True
    for name in ("config", "known_hosts", "smako_ed25519"):
        checks[f"ssh_{name}_accessible"] = os.access(Path.home() / ".ssh" / name, os.R_OK)
    checks["dns"] = bool(socket.getaddrinfo("www.willys.se", 443))
    with httpx.Client(timeout=20) as client:
        response = client.get("https://beta.smako.nu/ready")
        response.raise_for_status()
        checks["https"] = response.json()["status"] == "ready"
    remote = """from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
import os,json
from grocery_data import source_cli
p=Path('/srv/app/var/raw_snapshots/source-inbox/willys')
with NamedTemporaryFile(dir=p,prefix='.preflight-',suffix='.tmp') as f:
 f.write(b'relay preflight, no product observations');f.flush();os.fsync(f.fileno())
 assert p.is_dir()
print(json.dumps({'uid':os.getuid(),'inbox_write':True,'import_module':True}))
"""
    ssh = subprocess.run(
        [
            "ssh",
            "-oBatchMode=yes",
            "-oIdentityAgent=none",
            "-oConnectTimeout=15",
            "smako",
            "docker",
            "exec",
            "-i",
            "--user",
            "10001:10001",
            "smako-scheduler-1",
            "python",
            "-",
        ],
        input=remote,
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    )
    server = json.loads(ssh.stdout)
    checks["ssh_and_vps_upload_import_path"] = (
        server["uid"] == 10001 and server["inbox_write"] and server["import_module"]
    )
    result["status"] = "PASS" if all(checks.values()) else "FAIL"
    result["finished_at"] = datetime.now(UTC).isoformat()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = probe(args.workspace)
    except Exception as exc:  # noqa: BLE001 - redact SSH/runtime error bodies
        result = {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "finished_at": datetime.now(UTC).isoformat(),
        }
    atomic_write_bytes(
        args.output, json.dumps(result).encode(), validator=lambda p: json.loads(p.read_bytes())
    )
    hold = args.workspace / "preflight-hold.request"
    if hold.exists():
        hold.unlink()
        sleep(60)  # Bounded cancellation test, no collection or activation.
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
