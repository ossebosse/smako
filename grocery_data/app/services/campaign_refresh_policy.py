"""Persistent due-time policy used by the existing refresh runner.

No network, collection or activation here. Campaigns retain their original
source dates. Explicit mon_thu deployments collect twice weekly; legacy
deployments retain their 35 h timer. Both still warn at 36/48 h.
Qualified base prices remain usable until replaced.
"""
import os
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo('Europe/Stockholm')


def twice_weekly(environment=None) -> bool:
    env = os.environ if environment is None else environment
    value = env.get('PRICE_COLLECTION_CADENCE', 'legacy').strip()
    if value not in {'legacy', 'mon_thu'}:
        raise ValueError('PRICE_COLLECTION_CADENCE must be legacy or mon_thu')
    return value == 'mon_thu'


def collection_slots(now: datetime) -> tuple[datetime, datetime]:
    """Previous and next Monday/Thursday 03:17, in Swedish civil time."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('aware clock required')
    local = now.astimezone(STOCKHOLM)
    slots = [datetime.combine(local.date() + timedelta(days=offset), time(3, 17), STOCKHOLM)
             .astimezone(UTC) for offset in range(-7, 8)
             if (local.date() + timedelta(days=offset)).weekday() in {0, 3}]
    return max(s for s in slots if s <= now), min(s for s in slots if s > now)


def scheduled_fetch_due(observed_at: datetime | None, *, now: datetime) -> datetime:
    """Two collection nights; bounded retries share their three-hour window.

    Local expiry/publication work may still run between these windows. Missing
    sources never authorize an extra daytime collection or a renewed timestamp.
    """
    previous, following = collection_slots(now)
    if (observed_at is None or observed_at < previous) and now < previous + timedelta(hours=3):
        return now
    return following


def scheduled_source_times(rows, *, state, now, environment=None):
    """Project persisted legacy offer timers into the explicitly selected cadence."""
    if not twice_weekly(environment):
        return None
    for row in rows:
        stamp = row.get('last_success_at') or row.get('last_success')
        if not stamp and not row.get('failed_attempts'):
            stamp = row.get('last_attempt_at') or row.get('last_attempt')
        due = scheduled_fetch_due(datetime.fromisoformat(stamp) if stamp else None, now=now)
        # Preserve provider backoff within a collection night. A future legacy
        # timer must not skip Thursday's complete collection after Monday.
        if row.get('failed_attempts') and row.get('next_fetch_at'):
            retry = datetime.fromisoformat(row['next_fetch_at'])
            previous, following = collection_slots(now)
            if previous <= retry < following:
                due = max(due, retry) if retry < previous + timedelta(hours=3) else following
        row['next_fetch_at'] = due.isoformat()
        row['reason'] = 'mon_thu_collection'
    checked = (state.get('inventory_status') or {}).get('checked_at') or state.get('inventory_checked_at')
    return scheduled_fetch_due(datetime.fromisoformat(checked) if checked else None, now=now)


def campaign_schedule(windows: list[dict], *, now: datetime, failed_attempts: int = 0) -> dict:
    if now.tzinfo is None:
        raise ValueError('aware clock required')
    boundaries = set()
    expired_boundaries = set()
    for window in windows:
        for key, days in [('valid_from', 0), ('valid_to', 1)]:
            if window.get(key):
                boundary = datetime.combine(date.fromisoformat(window[key]) + timedelta(days=days),
                                            time.min, STOCKHOLM).astimezone(UTC)
                if boundary > now:
                    boundaries.add(boundary)
                elif key == 'valid_to':
                    expired_boundaries.add(boundary)
    transition = min(boundaries) if boundaries else None
    if failed_attempts:
        due = now + timedelta(minutes=min(360, 15 * 2 ** min(failed_attempts - 1, 5)))
        reason = 'bounded_failure_retry'
    elif not windows or any(not w.get('valid_to') for w in windows):
        due, reason = now + timedelta(hours=12), 'empty_or_unbounded_fallback'
    elif transition is not None:
        lead = transition - timedelta(hours=1)
        due = lead if lead > now else transition + timedelta(minutes=15)
        due = min(due, now + timedelta(hours=72))
        reason = 'campaign_boundary_or_72h_source_check'
    else:
        due, reason = now + timedelta(hours=12), 'expired_source_fallback'
    # Retailers may still serve last week's rows just after local midnight.
    # A surviving long-running offer must not hide that rollover behind the
    # next future boundary (or the 72-hour cap). Recheck hourly during the
    # first day; stale historical rows then use the existing 12-hour fallback.
    # Failed requests retain their separate bounded backoff.
    if expired_boundaries and not failed_attempts:
        recent = now - max(expired_boundaries) < timedelta(hours=24)
        retry = now + timedelta(hours=1 if recent else 12)
        if retry < due:
            due = retry
            reason = 'campaign_rollover_retry' if recent else 'expired_source_fallback'
    if twice_weekly():
        _, following = collection_slots(now)
        due = min(due, following) if failed_attempts else following
        if failed_attempts and due < following:
            previous, _ = collection_slots(now)
            if due >= previous + timedelta(hours=3):
                due = following
        reason = 'bounded_failure_retry' if failed_attempts else 'mon_thu_collection'
    return {'next_fetch_at': due.isoformat(), 'reason': reason,
            'next_transition_at': transition.isoformat() if transition else None}


def base_fetch_due(observed_at: datetime | None, *, now: datetime,
                   campaign_at: datetime | None = None, environment=None) -> datetime:
    if twice_weekly(environment):
        return scheduled_fetch_due(observed_at, now=now)
    if observed_at is None:
        return now
    due = observed_at + timedelta(hours=35)
    # Coalesce with campaign work only once base data is at least 24 h old;
    # several stores never multiply requests to the same base source.
    if campaign_at and campaign_at >= observed_at + timedelta(hours=24):
        due = min(due, campaign_at)
    return max(now, due)
