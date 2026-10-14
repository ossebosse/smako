"""Persistent due-time policy used by the existing refresh runner.

No network, collection or activation here. Campaigns retain their original
source dates; base sources refresh at 35 h, warning 36 h, hard stop 48 h.
"""
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo('Europe/Stockholm')


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
    return {'next_fetch_at': due.isoformat(), 'reason': reason,
            'next_transition_at': transition.isoformat() if transition else None}


def base_fetch_due(observed_at: datetime, *, now: datetime, campaign_at: datetime | None = None) -> datetime:
    due = observed_at + timedelta(hours=35)
    # Coalesce with campaign work only once base data is at least 24 h old;
    # several stores never multiply requests to the same base source.
    if campaign_at and campaign_at >= observed_at + timedelta(hours=24):
        due = min(due, campaign_at)
    return max(now, due)
