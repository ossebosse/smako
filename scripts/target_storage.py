"""Run reviewed storage retention through the installed scheduler and its lease.

The same entry point is used by beta_release before building/updating a target.
No files or timers are installed on the host. Default is a read-only inventory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def maintain_target(host, *, apply=False):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", host):
        raise ValueError("Invalid SSH host")
    sources = {
        "deploy.scripts.storage_maintenance": (ROOT / "deploy/scripts/storage_maintenance.py").read_text(encoding="utf8"),
        "grocery_data.app.services.snapshot_retention": (ROOT / "grocery_data/app/services/snapshot_retention.py").read_text(encoding="utf8"),
        "deploy.scripts.municipal_backup": (ROOT / "deploy/scripts/municipal_backup.py").read_text(encoding="utf8"),
        "deploy.scripts.municipal_retention": (ROOT / "deploy/scripts/municipal_retention.py").read_text(encoding="utf8"),
    }
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    code = (
        "import sys,types\nsys.argv=['storage_maintenance']"
        + ("+['--apply']" if apply else "")
        + "\nsources=" + repr(sources)
        + "\nfor name,source in sources.items():\n"
        + " module=types.ModuleType(name);sys.modules[name]=module\n"
        + " exec(compile(source,'reviewed-'+name,'exec'),module.__dict__)\n"
        + "sys.modules['deploy.scripts.storage_maintenance'].main()\n"
    )
    response = subprocess.check_output(
        ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=15", host,
         "sudo", "-n", "docker", "exec", "-i", "--user", "10001:10001",
         "smako-scheduler-1", "python", "-"],
        input=code.encode(),
    )
    result = json.loads(response)
    result["maintenance_code_sha256"] = digest
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="smako")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = maintain_target(args.host, apply=args.apply)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
