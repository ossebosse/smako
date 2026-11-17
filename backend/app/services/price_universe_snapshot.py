"""Binary snapshot of a restored price universe (owner decision 2026-11-17).

Loading an area's prepared price universe from its JSON artifact parses and
validates every product (Malmö: 27 s) and then builds the meal-ready
projection and the product-search index (35 s). Every app start and every
activation did this for every configured city. A snapshot stores the finished,
already validated objects in Python's binary format, so the next load takes a
few seconds.

Trust and freshness:
- A snapshot belongs to one exact JSON artifact (its SHA-256, which also
  names the content-addressed artifact) and one exact code version (a digest
  of the model and service sources whose objects it holds). Any difference
  means the JSON is loaded and validated as before, and a new snapshot is
  written.
- The header records the digest of the binary payload, checked before it is
  read. The folder is the app's own runtime folder; only the app writes it.
- Caches, locks and process registrations are never stored: a loaded universe
  starts with empty caches, exactly as after a JSON load.

``SMAKO_PREPARED_SNAPSHOT_ROOT`` names the folder (unset: no snapshots).
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import pickle
import threading
from pathlib import Path
from types import MappingProxyType

FORMAT = "smako-prepared-universe-snapshot-v1"
_MAGIC = b"SMAKO-SNAPSHOT\n"
logger = logging.getLogger(__name__)
# Code and the data files read with it (reviewed facts, references): a
# release that changes any of them writes new snapshots on its first start.
_SOURCES = ("backend/app", "grocery_data/app")
_SKIP = ("__pycache__", "/static/")
_fingerprint: str | None = None


def snapshot_root() -> Path | None:
    raw = os.environ.get("SMAKO_PREPARED_SNAPSHOT_ROOT", "").strip()
    return Path(raw) if raw else None


def code_fingerprint() -> str:
    """Digest of the code and data files whose objects a snapshot can hold."""
    global _fingerprint
    if _fingerprint is None:
        root = Path(__file__).resolve().parents[3]
        digest = hashlib.sha256(FORMAT.encode())
        for folder in _SOURCES:
            for path in sorted((root / folder).rglob("*")):
                name = path.relative_to(root).as_posix()
                if not path.is_file() or any(part in f"/{name}" for part in _SKIP):
                    continue
                digest.update(name.encode())
                digest.update(path.read_bytes())
        _fingerprint = digest.hexdigest()
    return _fingerprint


def snapshot_path(root: Path, source_sha256: str, *, kind: str = "universe") -> Path:
    prefix = "" if kind == "universe" else f"{kind}-"
    return root / f"{prefix}{source_sha256}-{code_fingerprint()[:24]}.pickle"


def read_only(values: dict) -> MappingProxyType:
    """Rebuilds a read-only view from a snapshot (pickle needs a named function)."""
    return MappingProxyType(values)


class _Pickler(pickle.Pickler):
    # Read-only views and locks are rebuilt, never stored.
    def reducer_override(self, obj):
        if type(obj) is MappingProxyType:
            return read_only, (dict(obj),)
        if isinstance(obj, type(threading.RLock())):
            return threading.RLock, ()
        if isinstance(obj, type(threading.Lock())):
            return threading.Lock, ()
        return NotImplemented


def write(prepared, path: Path, *, source_sha256: str) -> int:
    """Write atomically; returns the number of bytes."""
    buffer = io.BytesIO()
    _Pickler(buffer, protocol=pickle.HIGHEST_PROTOCOL).dump(prepared)
    payload = buffer.getvalue()
    header = json.dumps({"format": FORMAT, "source_sha256": source_sha256, "code": code_fingerprint(),
                         "payload_sha256": hashlib.sha256(payload).hexdigest(),
                         "payload_bytes": len(payload)}, sort_keys=True).encode() + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as out:
            out.write(_MAGIC)
            out.write(header)
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return len(payload)


def read(path: Path, *, source_sha256: str):
    """The restored universe, or None when the snapshot is absent or not this one."""
    try:
        with path.open("rb") as source:
            if source.readline() != _MAGIC:
                return None
            header = json.loads(source.readline())
            if (header.get("format") != FORMAT or header.get("source_sha256") != source_sha256
                    or header.get("code") != code_fingerprint()):
                return None
            payload = source.read()
    except (OSError, ValueError):
        return None
    if len(payload) != header.get("payload_bytes") or hashlib.sha256(payload).hexdigest() != header.get(
            "payload_sha256"):
        logger.warning("prepared_snapshot_rejected path=%s reason=digest", path.name)
        return None
    import gc
    enabled = gc.isenabled()
    gc.disable()  # millions of new objects: collections during the load only slow it
    try:
        return pickle.loads(payload)  # the app's own digest-checked file
    finally:
        if enabled:
            gc.enable()


def remove_others(root: Path, keep: set[Path]) -> None:
    """Drop universe snapshots of artifacts or code versions no longer loaded."""
    for path in root.glob("*.pickle"):
        if path not in keep and len(path.name.split("-")[0]) == 64:
            path.unlink(missing_ok=True)


def keep_newest(root: Path, kind: str, count: int = 8) -> None:
    """Snapshots of one other kind: the newest few (cities × recent sources)."""
    paths = sorted(root.glob(f"{kind}-*.pickle"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths[count:]:
        path.unlink(missing_ok=True)
