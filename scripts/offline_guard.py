"""Source isolation and retailer-network block for offline verification.

``verify_offline.py`` installs the guard in its own process. With pytest-xdist
the tests run in worker processes, so the root ``conftest.py`` installs the
same guard in each worker when ``SMAKO_OFFLINE_GUARD_LABEL`` is set. Every
process writes its own access record; ``merge`` combines them afterwards.
"""

import atexit
import ipaddress
import json
import os
import pathlib
import sys

ENV_LABEL = "SMAKO_OFFLINE_GUARD_LABEL"
ENV_ROOT = "SMAKO_OFFLINE_GUARD_ROOT"


def _out(root):
    out = root / ".local/verification"
    out.mkdir(parents=True, exist_ok=True)
    return out


def install(root, label, *, suffix="", register=True):
    root = pathlib.Path(root).resolve()
    out = _out(root)
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
                rel = p.relative_to(root).as_posix()
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

    def save():
        (out / f"{label}-access{suffix}.json").write_text(
            json.dumps({"report_reads": sorted(reads), "blocked": blocked}, indent=2),
            encoding="utf8",
        )

    if register:
        atexit.register(save)
    return save


def merge(root, label):
    """Fold worker records into ``<label>-access.json`` and remove them."""
    out = _out(pathlib.Path(root).resolve())
    main = out / f"{label}-access.json"
    reads, blocked = set(), []
    parts = sorted(out.glob(f"{label}-access-gw*.json"))
    for path in [main, *parts]:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf8"))
            reads.update(data["report_reads"])
            blocked.extend(data["blocked"])
    main.write_text(json.dumps({"report_reads": sorted(reads), "blocked": blocked}, indent=2),
                    encoding="utf8")
    for path in parts:
        path.unlink()
