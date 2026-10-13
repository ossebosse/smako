"""Retry a due daily backup within the existing serialized refresh worker."""
import json
import logging
import os
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from grocery_data.app.services.durable_files import atomic_write_bytes


def state_path():
    return Path(os.environ['PRICE_UNIVERSE_CACHE_ROOT']).parent / 'reports/operations/backup-status.json'


def record(status, **fields):
    try:
        path = state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, json.dumps({'status': status, 'observed_at': datetime.now(UTC).isoformat(),
                                            **fields}, sort_keys=True).encode())
        path.chmod(0o600)
    except (KeyError, OSError) as exc:
        logging.getLogger(__name__).warning('backup_status_unavailable error_type=%s', type(exc).__name__)


def due(*, now=None):
    now = now or datetime.now(UTC)
    local = now.astimezone(ZoneInfo('Europe/Stockholm'))
    cron = os.getenv('DAILY_BACKUP_CRON', '47 02 * * *').split()
    if len(cron) != 5 or cron[2:] != ['*', '*', '*']:
        raise ValueError('backup recovery requires the configured daily schedule')
    scheduled = datetime.combine(local.date(), time(int(cron[1]), int(cron[0])), local.tzinfo)
    if local < scheduled:
        scheduled -= timedelta(days=1)
    root = Path(os.getenv('BACKUP_ROOT', '/srv/app/var/backups'))
    # Only completion manifests count. A leftover staging directory never does.
    for candidate in sorted(root.glob('[0-9]*Z'), reverse=True):
        try:
            stamp = datetime.strptime(candidate.name, '%Y%m%dT%H%M%SZ').replace(tzinfo=UTC)
            if stamp < scheduled:
                break
            if stamp > now:
                continue
            data = json.loads((candidate / 'manifest.json').read_bytes())
            from deploy.scripts.backup_sqlite import _sha256
            from grocery_data.app.services.municipal_rollout import registry_path
            registry = registry_path()
            digest = _sha256(registry) if registry.exists() else None
            if (data.get('schema_version') == 'grocery-beta-backup-v1' and data.get('files')
                    and data.get('recovery_scope_version') == 2
                    and data.get('municipal_registry_sha256') == digest):
                return False
        except (OSError, ValueError, TypeError):
            continue
    path = state_path()
    state = json.loads(path.read_bytes()) if path.exists() else {}
    retry = state.get('retry_at')
    return not retry or datetime.fromisoformat(retry) <= now


def run_due_locked(*, now=None):
    """Caller already owns the production operation lease; no second timer."""
    now = now or datetime.now(UTC)
    from deploy.scripts.backup_sqlite import _create_backup_locked
    try:
        if not due(now=now):
            return None
        bundle = _create_backup_locked(now=now)
    except Exception as exc:  # noqa: BLE001 - do not block healthy source work
        record('failed', error_type=type(exc).__name__, retry_at=(now + timedelta(minutes=30)).isoformat())
        return {'status': 'failed', 'error_type': type(exc).__name__}
    record('complete', bundle=bundle.name, completed_at=datetime.now(UTC).isoformat())
    return {'status': 'complete', 'bundle': bundle.name}
