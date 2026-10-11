"""Measured admission check for the existing municipality registration command."""
import json
import math
from datetime import UTC, datetime, timedelta
from hashlib import sha256

FIELDS = ('store_count', 'requests', 'collection_seconds', 'build_seconds',
          'peak_memory_bytes', 'database_growth_bytes', 'build_copy_bytes',
          'artifact_bytes', 'queue_growth_bytes', 'backup_bytes', 'restore_bytes',
          'existing_cycle_seconds', 'available_cycle_seconds', 'available_memory_bytes')


def capacity_report(evidence, *, municipality, postal_code, sources, free_bytes, now=None):
    """Unknown measurements fail closed. Evidence describes one complete pilot.

    The caller supplies current free disk space, not yesterday's free-space claim.
    Memory/cycle availability must be measured for the shared sequential worker.
    """
    now = now or datetime.now(UTC)
    reasons = []
    if (evidence.get('municipality_code') != municipality or evidence.get('postal_code') != postal_code
            or evidence.get('sources') != sorted(sources) or evidence.get('pilot_complete') is not True):
        reasons.append('complete_scope_matched_pilot_required')
    try:
        observed = datetime.fromisoformat(evidence['measured_at'])
        if observed.tzinfo is None or not timedelta(0) <= now - observed < timedelta(days=7):
            reasons.append('pilot_expired_or_invalid_time')
    except (ValueError, TypeError, KeyError):
        reasons.append('pilot_time_unknown')
    missing = [key for key in FIELDS if isinstance(evidence.get(key), bool)
               or not isinstance(evidence.get(key), (float, int))
               or not math.isfinite(evidence[key]) or evidence[key] < 0]
    if missing:
        reasons.append('measurements_unknown')
    required_bytes = cycle = None
    if not missing:
        if any(evidence[k] <= 0 for k in ('store_count', 'requests', 'collection_seconds',
                                          'build_seconds', 'peak_memory_bytes', 'build_copy_bytes',
                                          'artifact_bytes', 'backup_bytes', 'restore_bytes')):
            reasons.append('positive_pilot_measurements_required')
        required_bytes = math.ceil(1.25 * (evidence['database_growth_bytes'] + evidence['build_copy_bytes']
            + 2 * evidence['artifact_bytes'] + evidence['queue_growth_bytes']
            + evidence['backup_bytes'] + evidence['restore_bytes'])) + 512 * 1024**2
        cycle = evidence['existing_cycle_seconds'] + evidence['collection_seconds'] + evidence['build_seconds']
        if free_bytes < required_bytes:
            reasons.append('insufficient_disk_including_recovery')
        if evidence['peak_memory_bytes'] * 1.25 > evidence['available_memory_bytes']:
            reasons.append('insufficient_memory')
        if cycle * 1.25 > min(35 * 3600, evidence['available_cycle_seconds']):
            reasons.append('insufficient_freshness_window')
    return {'status': 'PASS' if not reasons else 'BLOCKED', 'municipality_code': municipality,
            'checked_at': now.isoformat(), 'reasons': reasons, 'missing_measurements': missing,
            'free_bytes': free_bytes, 'required_bytes': required_bytes, 'cycle_seconds': cycle,
            'evidence_sha256': sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()}
