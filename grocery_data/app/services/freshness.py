from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FreshnessState(StrEnum):
    """Operational data-age state shared by refresh, API and UI surfaces."""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    BROKEN = "broken"


class FreshnessPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    warning_age_hours: float = Field(default=36.0, gt=0)
    stale_age_hours: float = Field(default=48.0, gt=0)

    @model_validator(mode="after")
    def warning_precedes_stale(self) -> FreshnessPolicy:
        if not isfinite(self.warning_age_hours) or not isfinite(self.stale_age_hours):
            raise ValueError("freshness thresholds must be finite")
        if self.warning_age_hours >= self.stale_age_hours:
            raise ValueError("warning threshold must be below stale threshold")
        return self


class FreshnessAssessment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: FreshnessState
    observed_at: datetime | None = None
    evaluated_at: datetime
    age_hours: float | None = Field(default=None, ge=0)
    hours_until_stale: float | None = Field(default=None, ge=0)
    stale_at: datetime | None = None
    warning_age_hours: float = Field(gt=0)
    stale_age_hours: float = Field(gt=0)
    usable: bool
    warning: bool
    reason: str


class SourceFreshnessProjection(BaseModel):
    """Freshness plus the next scheduled recovery boundary for one source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    freshness: FreshnessAssessment
    next_expected_source_refresh: datetime | None = None
    source_will_expire_before_next_refresh: bool = False
    retry_required: bool = False


def assess_freshness(
    observed_at: datetime | None,
    *,
    now: datetime | None = None,
    policy: FreshnessPolicy | None = None,
    broken: bool = False,
    broken_reason: str | None = None,
) -> FreshnessAssessment:
    """Classify one persisted observation without contacting its source.

    A failed refresh can be ``BROKEN`` while its LKG timestamp remains visible.
    Callers decide independently whether that LKG is still usable.
    """

    active_policy = policy or FreshnessPolicy()
    evaluated_at = now or datetime.now(tz=UTC)
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("freshness evaluation time must be timezone-aware")
    evaluated_at = evaluated_at.astimezone(UTC)
    normalized_observed: datetime | None = None
    age_hours: float | None = None
    if observed_at is not None:
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        normalized_observed = observed_at.astimezone(UTC)
        raw_age = (evaluated_at - normalized_observed).total_seconds() / 3600
        if raw_age < -1:
            broken = True
            broken_reason = broken_reason or "observation timestamp is in the future"
        age_hours = max(0.0, raw_age)

    if broken:
        state = FreshnessState.BROKEN
        reason = broken_reason or "latest refresh failed"
    elif age_hours is None:
        state = FreshnessState.BROKEN
        reason = "no persisted observation is available"
    elif age_hours >= active_policy.stale_age_hours:
        state = FreshnessState.STALE
        reason = "persisted observation exceeds the stale threshold"
    elif age_hours >= active_policy.warning_age_hours:
        state = FreshnessState.AGING
        reason = "persisted observation is approaching the stale threshold"
    else:
        state = FreshnessState.FRESH
        reason = "persisted observation is within the fresh window"

    stale_at = (
        normalized_observed + timedelta(hours=active_policy.stale_age_hours)
        if normalized_observed is not None
        else None
    )
    hours_until_stale = (
        max(0.0, active_policy.stale_age_hours - age_hours)
        if age_hours is not None
        else None
    )
    return FreshnessAssessment(
        state=state,
        observed_at=normalized_observed,
        evaluated_at=evaluated_at,
        age_hours=age_hours,
        hours_until_stale=hours_until_stale,
        stale_at=stale_at,
        warning_age_hours=active_policy.warning_age_hours,
        stale_age_hours=active_policy.stale_age_hours,
        usable=age_hours is not None and age_hours < active_policy.stale_age_hours,
        warning=state in {FreshnessState.AGING, FreshnessState.STALE, FreshnessState.BROKEN},
        reason=reason,
    )


def next_scheduled_refresh(
    schedule: str | None,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """Resolve the next ``HH:MM Europe/Stockholm`` operational schedule."""

    if not schedule:
        return None
    parts = schedule.strip().split()
    if len(parts) != 2:
        return None
    clock, zone_name = parts
    clock_parts = clock.split(":")
    if len(clock_parts) != 2 or not all(value.isdigit() for value in clock_parts):
        return None
    hour, minute = (int(value) for value in clock_parts)
    if hour > 23 or minute > 59:
        return None
    try:
        zone = ZoneInfo(zone_name)
    except ZoneInfoNotFoundError:
        return None
    evaluated_at = now or datetime.now(tz=UTC)
    if evaluated_at.tzinfo is None or evaluated_at.utcoffset() is None:
        raise ValueError("freshness evaluation time must be timezone-aware")
    local_now = evaluated_at.astimezone(zone)
    candidate = datetime(
        local_now.year,
        local_now.month,
        local_now.day,
        hour,
        minute,
        tzinfo=zone,
    )
    if candidate <= local_now:
        next_date = local_now.date() + timedelta(days=1)
        candidate = datetime(
            next_date.year,
            next_date.month,
            next_date.day,
            hour,
            minute,
            tzinfo=zone,
        )
    return candidate.astimezone(UTC)


def project_source_freshness(
    observed_at: datetime | None,
    *,
    now: datetime | None = None,
    policy: FreshnessPolicy | None = None,
    next_expected_source_refresh: datetime | None = None,
    basket_critical: bool = False,
    refresh_successful: bool = True,
) -> SourceFreshnessProjection:
    """Project whether current source evidence survives until the next run.

    An AGING snapshot stays usable.  The projection only raises an operational
    recovery signal; it never weakens the hard stale gate or fabricates a new
    observation time.
    """

    assessment = assess_freshness(observed_at, now=now, policy=policy)
    normalized_next: datetime | None = None
    if next_expected_source_refresh is not None:
        if (
            next_expected_source_refresh.tzinfo is None
            or next_expected_source_refresh.utcoffset() is None
        ):
            raise ValueError("next source refresh time must be timezone-aware")
        normalized_next = next_expected_source_refresh.astimezone(UTC)
    will_expire = bool(
        assessment.stale_at is not None
        and normalized_next is not None
        and normalized_next > assessment.stale_at
    )
    # The hard usability boundary remains ``stale_age_hours``.  Operationally,
    # however, a basket-critical source that will cross that boundary before
    # its next scheduled run is already AGING and needs early recovery.  Keep
    # the original observation time/age and usable flag truthful while making
    # that production risk visible before it becomes an outage.
    if basket_critical and will_expire and assessment.state is FreshnessState.FRESH:
        assessment = assessment.model_copy(
            update={
                "state": FreshnessState.AGING,
                "warning": True,
                "reason": "source will exceed the stale threshold before its next refresh",
            }
        )
    retry_required = bool(
        basket_critical
        and (
            not refresh_successful
            or assessment.state
            in {FreshnessState.AGING, FreshnessState.STALE, FreshnessState.BROKEN}
            or will_expire
        )
    )
    return SourceFreshnessProjection(
        freshness=assessment,
        next_expected_source_refresh=normalized_next,
        source_will_expire_before_next_refresh=will_expire,
        retry_required=retry_required,
    )


__all__ = [
    "FreshnessAssessment",
    "FreshnessPolicy",
    "FreshnessState",
    "SourceFreshnessProjection",
    "assess_freshness",
    "next_scheduled_refresh",
    "project_source_freshness",
]
