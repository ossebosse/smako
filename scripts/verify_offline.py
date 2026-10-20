"""Run existing pytest tests with source isolation and no retailer network."""

import atexit
import ipaddress
import json
import os
import pathlib
import sys

ROOT = pathlib.Path.cwd().resolve()
OUT = ROOT / ".local/verification"
OUT.mkdir(parents=True, exist_ok=True)
# Keep test databases and subprocess scratch on the workspace volume. A small
# Windows system disk must not fill while the repository has ample capacity.
# Pytest rotates its numbered directories here using its normal retention.
scratch = OUT / "tmp"
scratch.mkdir(exist_ok=True)
os.environ.update(TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
label = os.getenv("SMAKO_VERIFY_LABEL", "tests")
reads = set()
blocked = []
forbidden = ["c:/users/ossia/documents/codex/"]
forbidden += [
    pathlib.Path(p).resolve().as_posix().lower().rstrip("/") + "/"
    for p in os.getenv("SMAKO_FORBIDDEN_ROOTS", "").split(";")
    if p
]


def audit(event, args):
    if (
        event in {"open", "sqlite3.connect"}
        and args
        and isinstance(args[0], (str, bytes, os.PathLike))
    ):
        name = os.fsdecode(args[0])
        if name == ":memory:":
            return
        p = pathlib.Path(name).resolve()
        lower = p.as_posix().lower()
        if any(lower.startswith(prefix) for prefix in forbidden):
            blocked.append({"event": "old_source_read", "path": str(p)})
            raise RuntimeError("Old dated source dependency blocked: " + str(p))
        try:
            rel = p.relative_to(ROOT).as_posix()
            if rel.startswith("reports/"):
                reads.add(rel)
        except ValueError:
            pass
    if event == "socket.connect":
        address = args[1]
        if isinstance(address, tuple):
            host = address[0]
            try:
                allowed = ipaddress.ip_address(host).is_loopback
            except ValueError:
                allowed = host in {"localhost"}
            if not allowed:
                blocked.append({"event": "external_network_blocked"})
                raise RuntimeError("External network disabled for consolidation verification")


sys.addaudithook(audit)
os.environ.update(PYTHON_DOTENV_DISABLED="1", PYTHONDONTWRITEBYTECODE="1")


def save():
    (OUT / (label + "-access.json")).write_text(
        json.dumps({"report_reads": sorted(reads), "blocked": blocked}, indent=2), encoding="utf8"
    )


atexit.register(save)
import pytest

raise SystemExit(pytest.main(sys.argv[1:]))
