"""Small operator primitives for a manually scheduled production refresh.

This module deliberately owns no connector, database session or PriceUniverse
manager.  It only provides the cross-process safety and reporting boundary a
shell/Task Scheduler composition root needs around those existing services.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO, Self
from uuid import uuid4

from grocery_data.app.services.durable_files import atomic_write_bytes

_LOCK_SCHEMA = "manual-refresh-lock-v2"
_LEGACY_LOCK_SCHEMA = "manual-refresh-lock-v1"
_PRODUCTION_LOCK_KEY_SCHEMA = "production-refresh-lock-key-v1"
REFRESH_PARENT_LOCK_NONCE_ENV = "GROCERY_DATA_REFRESH_PARENT_LOCK_NONCE"
_REDACTED = "[REDACTED]"
_SAFE_PREFIX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_SENSITIVE_KEY_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "browser_storage",
    "cookie",
    "credential",
    "csrf",
    "database_url",
    "header",
    "page_view_id",
    "password",
    "refresh_token",
    "secret",
    "session",
    "token",
)
_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"(?i)\b(?:sk|primat_live)_[A-Za-z0-9_-]+"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|authorization|cookie|csrf|password|secret|token)"
        r"\s*[:=]\s*[^\s,;]+"
    ),
)


class RefreshLockError(RuntimeError):
    """Base class for refresh lock failures."""


class RefreshAlreadyRunningError(RefreshLockError):
    """Raised when a live process owns the refresh lock."""


def production_refresh_lock_path(
    database: Path,
    price_universe_root: Path,
    *,
    allow_missing_database: bool = False,
) -> Path:
    """Return the stable cross-process lock path for one production data plane.

    Reports are incidental output and may be redirected, so they must never
    define refresh mutual exclusion. The lock identity instead consists of the
    canonical SQLite database and PriceUniverse root used by the refresh. Only
    their digest is placed in the filename; local filesystem paths are not
    persisted in lock contents or exposed in ordinary operator output.

    ``database`` normally must already exist. Disaster restore may opt into an
    absent exact target; in that case its existing parent is resolved strictly
    and the final filename is appended without following a missing/symlinked
    target. The universe root may be created by the caller later, but is
    resolved before hashing so ``.``/``..`` aliases cannot create independent
    locks for the same data plane.
    """

    try:
        resolved_database = database.resolve(strict=True)
    except FileNotFoundError:
        if not allow_missing_database:
            raise
        resolved_database = database.resolve(strict=False)
        existing_parent = resolved_database.parent
        while not existing_parent.exists() and existing_parent != existing_parent.parent:
            existing_parent = existing_parent.parent
        if not existing_parent.is_dir():
            raise ValueError("refresh lock database parent must be a directory")
    if resolved_database.exists() and not resolved_database.is_file():
        raise ValueError("refresh lock database must be a regular file")
    resolved_universe_root = price_universe_root.resolve()
    if resolved_universe_root.exists() and not resolved_universe_root.is_dir():
        raise ValueError("PriceUniverse root must be a directory")

    def canonical(value: Path) -> str:
        # normcase preserves case-sensitive identities on POSIX and collapses
        # harmless case aliases on Windows. POSIX separators make the encoded
        # key stable without leaking either path into the resulting filename.
        return os.path.normcase(str(value)).replace("\\", "/")

    material = json.dumps(
        {
            "schema_version": _PRODUCTION_LOCK_KEY_SCHEMA,
            "database": canonical(resolved_database),
            "price_universe_root": canonical(resolved_universe_root),
        },
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(material).hexdigest()
    return resolved_universe_root / ".refresh-locks" / f"daily-refresh-{digest}.lock"


@dataclass(frozen=True, slots=True)
class RefreshLockInfo:
    """Credential-free ownership identity persisted in one lock file."""

    pid: int
    acquired_at: datetime
    owner_nonce: str
    process_identity: str | None = None

    def payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": _LOCK_SCHEMA,
            "pid": self.pid,
            "acquired_at": self.acquired_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
            "owner_nonce": self.owner_nonce,
        }
        if self.process_identity is not None:
            payload["process_identity"] = self.process_identity
        return payload


def _utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("refresh operation timestamps must be timezone-aware")
    return value.astimezone(UTC)


def _windows_process_is_alive(pid: int) -> bool:
    """Check a Windows PID without sending it a signal.

    Access denied is treated conservatively as alive: another account may own
    the process and that is not authority to steal its refresh lock.
    """

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    kernel32.SetLastError(0)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return kernel32.GetLastError() == 5  # ERROR_ACCESS_DENIED
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def process_is_alive(pid: int) -> bool:
    """Return whether ``pid`` currently denotes a live process."""

    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        return _windows_process_is_alive(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _linux_process_identity(pid: int) -> str | None:
    """Return a boot-scoped Linux process-start identity without exposing it."""

    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        # The command name is parenthesized and may itself contain spaces or
        # parentheses. Everything after the final ')' starts at field 3; Linux
        # process start time is field 22, hence offset 19 below.
        command_end = stat.rfind(")")
        fields = stat[command_end + 1 :].split()
        if command_end < 1 or len(fields) <= 19:
            return None
        start_ticks = fields[19]
        boot_id_path = Path("/proc/sys/kernel/random/boot_id")
        boot_id = (
            boot_id_path.read_text(encoding="ascii").strip()
            if boot_id_path.is_file()
            else "unknown-boot"
        )
    except (OSError, UnicodeError, ValueError):
        return None
    material = f"{boot_id}:{start_ticks}".encode("ascii", errors="strict")
    return f"linux:{hashlib.sha256(material).hexdigest()}"


def _windows_process_identity(pid: int) -> str | None:
    """Return a Windows creation-time identity for one process, if readable."""

    process_query_limited_information = 0x1000
    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        creation = ctypes.c_ulonglong()
        exit_time = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        return f"windows:{creation.value:016x}"
    finally:
        kernel32.CloseHandle(handle)


def process_identity(pid: int) -> str | None:
    """Return an opaque identity that changes when a PID is reused.

    Linux combines kernel boot identity with ``/proc`` process start ticks.
    Windows uses the process creation FILETIME. Unsupported or inaccessible
    platforms return ``None`` and the lock falls back to its bounded stale
    policy while remaining conservative for the supported two-hour refresh.
    """

    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    if os.name == "nt":
        return _windows_process_identity(pid)
    if Path("/proc").is_dir():
        return _linux_process_identity(pid)
    return None


def _parse_lock(raw: bytes) -> RefreshLockInfo | None:
    try:
        if raw.startswith(b"\0"):
            raw = raw[1:]
        payload = json.loads(raw)
        if not isinstance(payload, Mapping) or payload.get("schema_version") not in {
            _LOCK_SCHEMA,
            _LEGACY_LOCK_SCHEMA,
        }:
            return None
        pid = payload.get("pid")
        acquired_raw = payload.get("acquired_at")
        nonce = payload.get("owner_nonce")
        identity = payload.get("process_identity")
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            return None
        if not isinstance(acquired_raw, str) or not isinstance(nonce, str) or not nonce:
            return None
        if identity is not None and (not isinstance(identity, str) or not identity):
            return None
        acquired_at = datetime.fromisoformat(acquired_raw)
        return RefreshLockInfo(
            pid=pid,
            acquired_at=_aware_utc(acquired_at),
            owner_nonce=nonce,
            process_identity=identity,
        )
    except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return None


def refresh_lock_owned_by_process(path: Path, *, nonce: str, pid: int) -> bool:
    """Validate the internal parent-lock handoff used by the refresh wrapper."""

    if not nonce or isinstance(pid, bool) or pid <= 0:
        return False
    try:
        with path.resolve().open("rb") as handle:
            handle.seek(1)
            owner = _parse_lock(handle.read())
    except OSError:
        return False
    if owner is None or owner.owner_nonce != nonce or owner.pid != pid:
        return False
    if owner.process_identity is None:
        identity_matches = process_is_alive(pid)
    else:
        current = process_identity(pid)
        identity_matches = current is not None and current == owner.process_identity
    if not identity_matches:
        return False
    # Metadata alone is replayable after the kernel releases a crashed owner.
    # The parent handoff is valid only while some process still owns the real
    # advisory lease.
    try:
        handle = path.resolve().open("r+b", buffering=0)
    except OSError:
        return False
    try:
        try:
            _acquire_advisory_lock(handle)
        except BlockingIOError:
            return True
        _release_advisory_lock(handle)
        return False
    finally:
        handle.close()


def _acquire_advisory_lock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise BlockingIOError from exc
        return
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise BlockingIOError from exc


def _release_advisory_lock(handle: BinaryIO) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class RefreshRunLock:
    """Exclusive cross-process lock held by an operating-system file lease.

    Linux ``flock`` and Windows byte-range locks are released by the kernel if
    a process or container exits. The lock file itself intentionally persists:
    its PID, nonce and boot/process-start identity are diagnostic metadata only,
    never authority for stealing a live kernel lock. This avoids PID namespace
    and PID-reuse errors across the scheduler, backup and restore containers.
    """

    def __init__(
        self,
        path: Path,
        *,
        stale_after: timedelta = timedelta(hours=6),
        pid: int | None = None,
        clock: Callable[[], datetime] = _utc_now,
        pid_is_alive: Callable[[int], bool] = process_is_alive,
        pid_identity: Callable[[int], str | None] = process_identity,
    ) -> None:
        if stale_after.total_seconds() <= 0:
            raise ValueError("stale_after must be positive")
        self.path = path.resolve()
        self.stale_after = stale_after
        self.pid = os.getpid() if pid is None else pid
        if isinstance(self.pid, bool) or not isinstance(self.pid, int) or self.pid <= 0:
            raise ValueError("refresh lock PID must be a positive integer")
        self.clock = clock
        self.pid_is_alive = pid_is_alive
        self.pid_identity = pid_identity
        self.info: RefreshLockInfo | None = None
        self._handle: BinaryIO | None = None

    @property
    def acquired(self) -> bool:
        return self.info is not None

    def _owner_info(self, now: datetime) -> RefreshLockInfo:
        try:
            identity = self.pid_identity(self.pid)
        except Exception:  # noqa: BLE001 - optional identity must fail closed
            identity = None
        if not isinstance(identity, str) or not identity:
            identity = None
        info = RefreshLockInfo(
            pid=self.pid,
            acquired_at=now,
            owner_nonce=uuid4().hex,
            process_identity=identity,
        )
        return info

    def acquire(self) -> RefreshLockInfo:
        if self.info is not None:
            raise RefreshLockError("refresh lock is already acquired by this object")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            if os.name != "nt":
                raise
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_RDWR,
                0o600,
            )
        except FileExistsError:
            descriptor = -1
        else:
            try:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        try:
            self.path.chmod(0o600)
        except OSError:
            if os.name != "nt":
                raise
        handle = self.path.open("r+b", buffering=0)
        try:
            _acquire_advisory_lock(handle)
        except BlockingIOError:
            handle.close()
            raise RefreshAlreadyRunningError("refresh operation lock is already held") from None
        now = _aware_utc(self.clock())
        try:
            info = self._owner_info(now)
            payload = json.dumps(
                info.payload(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            # Byte zero remains the stable Windows byte-range lock. Metadata
            # begins at byte one so the validated child handoff may read it
            # without touching the locked range.
            handle.seek(1)
            handle.truncate()
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        except Exception:
            try:
                _release_advisory_lock(handle)
            finally:
                handle.close()
            raise
        self._handle = handle
        self.info = info
        return info

    def release(self) -> None:
        handle = self._handle
        self._handle = None
        self.info = None
        if handle is None:
            return
        try:
            _release_advisory_lock(handle)
        finally:
            handle.close()

    def __enter__(self) -> Self:
        self.acquire()
        return self

    def __exit__(self, _type: object, _value: object, _traceback: object) -> None:
        self.release()


def _normalized_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).casefold()).strip("_")


def _sensitive_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _sanitize_text(value: str) -> str:
    result = value
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        result = pattern.sub(_REDACTED, result)
    return result


def credential_safe_report(value: Any) -> Any:
    """Return a JSON-compatible copy with transport credentials removed."""

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        value = model_dump(mode="json")
    elif is_dataclass(value) and not isinstance(value, type):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {
            str(key): _REDACTED if _sensitive_key(key) else credential_safe_report(child)
            for key, child in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [credential_safe_report(child) for child in value]
    if isinstance(value, (set, frozenset)):
        return [credential_safe_report(child) for child in sorted(value, key=repr)]
    if isinstance(value, datetime):
        return _aware_utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return value.name
    if isinstance(value, Enum):
        return credential_safe_report(value.value)
    if isinstance(value, BaseException):
        return {"error_type": type(value).__name__}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_text(value)
    return {"value_type": type(value).__name__}


def _atomic_write(path: Path, payload: bytes) -> None:
    def validate_json(candidate: Path) -> None:
        json.loads(candidate.read_bytes())

    atomic_write_bytes(path, payload, validator=validate_json)


def write_refresh_report(
    report: Any,
    report_dir: Path,
    *,
    prefix: str = "daily-refresh",
    now: datetime | None = None,
) -> Path:
    """Atomically write one timestamped, credential-safe JSON report."""

    normalized_prefix = prefix.casefold().strip()
    if not _SAFE_PREFIX.fullmatch(normalized_prefix):
        raise ValueError("report prefix must be a safe lowercase filename component")
    timestamp = _aware_utc(now or _utc_now())
    stamp = timestamp.strftime("%Y%m%dT%H%M%S.%fZ")
    directory = report_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{normalized_prefix}-{stamp}-{uuid4().hex[:8]}.json"
    sanitized = credential_safe_report(report)
    payload = (
        json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _atomic_write(destination, payload)
    return destination


def _text(value: object, fallback: str = "-") -> str:
    return fallback if value is None or value == "" else str(value)


def _first_daily_report(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    reports = payload.get("reports")
    if isinstance(reports, Sequence) and not isinstance(reports, (str, bytes)) and reports:
        first = reports[0]
        if isinstance(first, Mapping):
            return first
    return payload


def render_daily_refresh_report(report: Any) -> str:
    """Render the stable operational subset of a daily-refresh result."""

    payload = credential_safe_report(report)
    if not isinstance(payload, Mapping):
        raise TypeError("daily refresh report must be a mapping or Pydantic model")
    daily = _first_daily_report(payload)
    city = _text(daily.get("city"), "unknown")
    summary = daily.get("summary") if isinstance(daily.get("summary"), Mapping) else {}
    lines = [f"{city.upper()} DAILY REFRESH"]
    items = daily.get("items")
    if isinstance(items, Sequence) and not isinstance(items, (str, bytes)):
        lines.append("CHAIN      CONTEXT                    STATUS   PRODUCTS  AGE(h)  LKG")
        for raw in items:
            if not isinstance(raw, Mapping):
                continue
            chain = _text(raw.get("chain"), "unknown")[:10]
            context = _text(raw.get("context_name"), "unknown")[:26]
            status = _text(raw.get("status"), "unknown")[:8]
            products = _text(raw.get("products"))
            age = raw.get("age_hours")
            age_text = f"{float(age):.1f}" if isinstance(age, (int, float)) else "-"
            lkg = "YES" if raw.get("lkg_used") else "NO"
            lines.append(
                f"{chain:<10} {context:<26} {status:<8} {products:>8} {age_text:>7}  {lkg}"
            )
    universe = daily.get("universe")
    if isinstance(universe, Mapping):
        lines.append(
            "PriceUniverse: "
            f"{_text(universe.get('status'), 'unknown')} "
            f"({_text(universe.get('universe_id'), 'no active ID')})"
        )
    if summary:
        lines.append(
            "Summary: "
            + ", ".join(
                f"{key}={summary[key]}"
                for key in ("fresh", "aging", "stale", "broken", "promoted", "lkg_used")
                if key in summary
            )
        )
    return "\n".join(lines)


def render_refresh_status(status: Any) -> str:
    """Render the local `/operations/daily-refresh/status` response."""

    payload = credential_safe_report(status)
    if not isinstance(payload, Mapping):
        raise TypeError("refresh status must be a mapping or Pydantic model")
    city = _text(payload.get("city"), "unknown")
    lines = [
        f"{city.upper()} REFRESH STATUS: {_text(payload.get('status'), 'unknown').upper()}",
        (
            "Basket contexts: "
            f"{_text(payload.get('basket_capable'), '0')}; "
            f"oldest age: {_text(payload.get('oldest_basket_price_age_hours'))} h"
        ),
    ]
    chains = payload.get("chains")
    if isinstance(chains, Mapping):
        for chain, raw in sorted(chains.items(), key=lambda item: str(item[0])):
            if not isinstance(raw, Mapping):
                continue
            lines.append(
                f"{str(chain).upper():<10} "
                f"fresh={_text(raw.get('fresh_full_basket_contexts'), '0')} "
                f"aging={_text(raw.get('aging_full_basket_contexts'), '0')} "
                f"stale/broken={_text(raw.get('stale_or_broken'), '0')}"
            )
    return "\n".join(lines)


__all__ = [
    "REFRESH_PARENT_LOCK_NONCE_ENV",
    "RefreshAlreadyRunningError",
    "RefreshLockError",
    "RefreshLockInfo",
    "RefreshRunLock",
    "credential_safe_report",
    "process_identity",
    "process_is_alive",
    "production_refresh_lock_path",
    "refresh_lock_owned_by_process",
    "render_daily_refresh_report",
    "render_refresh_status",
    "write_refresh_report",
]
