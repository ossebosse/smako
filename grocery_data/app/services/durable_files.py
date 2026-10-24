"""Small durability primitives for critical replace-on-success files."""

from __future__ import annotations

import errno
import hashlib
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class StoragePreflight:
    """Observed capacity for one bounded write on its actual filesystem."""

    free_bytes: int
    required_bytes: int
    reserve_bytes: int

    @property
    def available_for_write_bytes(self) -> int:
        return max(0, self.free_bytes - self.reserve_bytes)


class InsufficientStorageError(OSError):
    """Fail a known heavy write before creating a partial destination."""

    def __init__(self, preflight: StoragePreflight) -> None:
        self.preflight = preflight
        super().__init__(
            errno.ENOSPC,
            "insufficient free space for bounded write while preserving reserve",
        )

    def status(self) -> dict[str, int | str]:
        return {
            "status": "failed",
            "reason": "insufficient_storage",
            "free_bytes": self.preflight.free_bytes,
            "required_bytes": self.preflight.required_bytes,
            "reserve_bytes": self.preflight.reserve_bytes,
        }


def require_free_space(
    directory: Path,
    *,
    required_bytes: int,
    reserve_bytes: int = 0,
) -> StoragePreflight:
    """Check free bytes on the filesystem that will receive a heavy write."""

    for name, value in (
        ("required_bytes", required_bytes),
        ("reserve_bytes", reserve_bytes),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{name} must be a non-negative integer")
    resolved = directory.resolve()
    resolved.mkdir(parents=True, exist_ok=True)
    free = int(shutil.disk_usage(resolved).free)
    observed = StoragePreflight(
        free_bytes=free,
        required_bytes=required_bytes,
        reserve_bytes=reserve_bytes,
    )
    if free < required_bytes + reserve_bytes:
        raise InsufficientStorageError(observed)
    return observed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_directory(directory: Path) -> None:
    """Persist a completed rename on platforms that support directory fsync."""

    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(
    path: Path,
    payload: bytes,
    *,
    mode: int = 0o600,
    reserve_bytes: int = 0,
    validator: Callable[[Path], None] | None = None,
) -> None:
    """Write, flush and validate same-directory scratch before atomic replace.

    The prior destination is never opened for writing. Any short write,
    validation error, ENOSPC, interruption before ``os.replace`` or failed swap
    therefore leaves it byte-identical. Scratch names are unique and cleaned on
    every handled failure.
    """

    if not isinstance(payload, bytes):
        raise TypeError("atomic payload must be bytes")
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if reserve_bytes:
        require_free_space(
            destination.parent,
            required_bytes=len(payload),
            reserve_bytes=reserve_bytes,
        )
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    descriptor = -1
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = -1
            written = handle.write(payload)
            if written != len(payload):
                raise OSError(errno.EIO, "short critical-file write")
            handle.flush()
            os.fsync(handle.fileno())
        if temporary.stat().st_size != len(payload):
            raise OSError(errno.EIO, "critical-file size verification failed")
        if _sha256(temporary) != hashlib.sha256(payload).hexdigest():
            raise OSError(errno.EIO, "critical-file hash verification failed")
        # The scratch file has the verified payload. Release the potentially
        # large input before a validator materializes its own parsed graph.
        del payload
        if validator is not None:
            validator(temporary)
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary.unlink()
        except OSError:
            # A leftover uniquely named dot-file is never an active candidate.
            pass


__all__ = [
    "InsufficientStorageError",
    "StoragePreflight",
    "atomic_write_bytes",
    "require_free_space",
]
