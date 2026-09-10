from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from threading import RLock
from time import perf_counter
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PrewarmMode = Literal["cheapest", "balanced", "varied"]
CacheOutcome = Literal["hit", "miss_filled", "unchanged"]


class StandardPlanPrewarmProfile(BaseModel):
    """One deterministic request shape whose process-local caches are prefilled."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: PrewarmMode
    max_stores: int = Field(ge=1, le=4)
    recipes: int = Field(default=5, ge=1, le=7)
    servings: int = Field(default=4, ge=1, le=12)
    postal_code: str = Field(default="22350", pattern=r"^\d{5}$")
    candidate_recipe_count: int = Field(default=80, ge=10, le=300)
    candidate_search_limit: int | None = Field(default=None, ge=5, le=300)
    beam_width: int = Field(default=30, ge=5, le=100)

    @property
    def profile_id(self) -> str:
        search_limit = self.candidate_search_limit or 0
        return (
            f"{self.mode}:stores-{self.max_stores}:r-{self.recipes}:s-{self.servings}:"
            f"c-{self.candidate_recipe_count}:l-{search_limit}:b-{self.beam_width}"
        )


class StandardPlanPrewarmConfig(BaseModel):
    """Bounded profile matrix shared by refresh and application startup."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Prewarming can consume meaningful CPU after a refresh.  It is an
    # operator-controlled production optimization, never an implicit startup
    # side effect (and in particular must stay off while a BEFORE baseline is
    # being captured).
    enabled: bool = False
    modes: tuple[PrewarmMode, ...] = ("cheapest", "balanced", "varied")
    max_stores: tuple[int, ...] = (1, 2)
    recipes: int = Field(default=5, ge=1, le=7)
    servings: int = Field(default=4, ge=1, le=12)
    postal_code: str = Field(default="22350", pattern=r"^\d{5}$")
    candidate_recipe_count: int = Field(default=80, ge=10, le=300)
    candidate_search_limit: int | None = Field(default=None, ge=5, le=300)
    beam_width: int = Field(default=30, ge=5, le=100)

    @field_validator("modes")
    @classmethod
    def require_unique_modes(cls, values: tuple[PrewarmMode, ...]) -> tuple[PrewarmMode, ...]:
        normalized = tuple(dict.fromkeys(values))
        if not normalized:
            raise ValueError("at least one prewarm mode is required")
        return normalized

    @field_validator("max_stores")
    @classmethod
    def normalize_store_limits(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        normalized = tuple(sorted(set(values)))
        if not normalized or any(value < 1 or value > 4 for value in normalized):
            raise ValueError("prewarm max_stores values must be between one and four")
        return normalized

    @model_validator(mode="after")
    def validate_search_limit(self) -> StandardPlanPrewarmConfig:
        if (
            self.candidate_search_limit is not None
            and self.candidate_search_limit > self.candidate_recipe_count
        ):
            raise ValueError("prewarm candidate search limit cannot exceed candidate count")
        return self

    def profiles(self) -> tuple[StandardPlanPrewarmProfile, ...]:
        return tuple(
            StandardPlanPrewarmProfile(
                mode=mode,
                max_stores=max_stores,
                recipes=self.recipes,
                servings=self.servings,
                postal_code=self.postal_code,
                candidate_recipe_count=self.candidate_recipe_count,
                candidate_search_limit=self.candidate_search_limit,
                beam_width=self.beam_width,
            )
            for max_stores in self.max_stores
            for mode in self.modes
        )


class PlanPrewarmExecution(BaseModel):
    """Allowlisted outcome returned by one local prepared-universe runner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cache_outcome: CacheOutcome
    verified: bool = True
    live_provider_requests: Literal[0] = 0


class StandardPlanPrewarmRunner(Protocol):
    def __call__(
        self,
        profile: StandardPlanPrewarmProfile,
    ) -> PlanPrewarmExecution | Awaitable[PlanPrewarmExecution]: ...


class PlanPrewarmItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: StandardPlanPrewarmProfile
    profile_id: str = Field(min_length=1)
    status: Literal["success", "failed"]
    cache_outcome: CacheOutcome | None = None
    verified: bool = False
    duration_ms: float = Field(ge=0)
    error_type: str | None = None
    live_provider_requests: Literal[0] = 0


class PlanPrewarmReport(BaseModel):
    """Sanitized post-activation status; it contains no result payload or error text."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal[
        "disabled",
        "skipped_universe_not_activated",
        "runner_unavailable",
        "complete",
        "partial_failure",
        "failed",
    ]
    universe_id: str | None = None
    started_at: datetime
    finished_at: datetime
    profiles_requested: int = Field(ge=0)
    profiles_succeeded: int = Field(ge=0)
    profiles_failed: int = Field(ge=0)
    cache_hits: int = Field(ge=0)
    cache_misses_filled: int = Field(ge=0)
    cache_unchanged: int = Field(ge=0)
    items: tuple[PlanPrewarmItem, ...] = ()
    universe_remained_active: bool
    live_provider_requests: Literal[0] = 0

    @field_validator("started_at", "finished_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("prewarm report timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_counts(self) -> PlanPrewarmReport:
        if self.profiles_succeeded + self.profiles_failed != len(self.items):
            raise ValueError("prewarm item counts disagree")
        if self.profiles_requested < len(self.items):
            raise ValueError("prewarm executed more profiles than requested")
        return self


def prewarm_not_run_report(
    status: Literal["disabled", "skipped_universe_not_activated", "runner_unavailable"],
    *,
    universe_id: str | None,
    profiles_requested: int,
    now: datetime,
) -> PlanPrewarmReport:
    return PlanPrewarmReport(
        status=status,
        universe_id=universe_id,
        started_at=now,
        finished_at=now,
        profiles_requested=profiles_requested,
        profiles_succeeded=0,
        profiles_failed=0,
        cache_hits=0,
        cache_misses_filled=0,
        cache_unchanged=0,
        universe_remained_active=universe_id is not None,
    )


async def prewarm_standard_plans(
    *,
    universe_id: str | None,
    activated: bool,
    config: StandardPlanPrewarmConfig,
    runner: StandardPlanPrewarmRunner | None,
    is_active: Callable[[str], bool] | None = None,
    now: datetime | None = None,
) -> PlanPrewarmReport:
    """Fill standard plan caches after activation, never changing the active universe.

    Profiles run sequentially to keep refresh CPU/memory bounded. Every failure
    is isolated and reduced to its exception type. The runner contract forbids
    live provider requests, and the coordinator never receives result payloads.
    """

    started_at = now or datetime.now(tz=UTC)
    if started_at.tzinfo is None or started_at.utcoffset() is None:
        raise ValueError("prewarm start time must be timezone-aware")
    started_at = started_at.astimezone(UTC)
    profiles = config.profiles()
    if not config.enabled:
        return prewarm_not_run_report(
            "disabled",
            universe_id=universe_id,
            profiles_requested=len(profiles),
            now=started_at,
        )
    if not activated or universe_id is None:
        return prewarm_not_run_report(
            "skipped_universe_not_activated",
            universe_id=universe_id,
            profiles_requested=len(profiles),
            now=started_at,
        )
    if runner is None:
        return prewarm_not_run_report(
            "runner_unavailable",
            universe_id=universe_id,
            profiles_requested=len(profiles),
            now=started_at,
        )

    items: list[PlanPrewarmItem] = []
    for profile in profiles:
        item_started = perf_counter()
        try:
            execution = runner(profile)
            if inspect.isawaitable(execution):
                execution = await execution
            if not isinstance(execution, PlanPrewarmExecution):
                execution = PlanPrewarmExecution.model_validate(execution)
            if not execution.verified:
                raise ValueError("prewarm result did not pass verification")
            items.append(
                PlanPrewarmItem(
                    profile=profile,
                    profile_id=profile.profile_id,
                    status="success",
                    cache_outcome=execution.cache_outcome,
                    verified=True,
                    duration_ms=round((perf_counter() - item_started) * 1000, 3),
                )
            )
        except Exception as exc:  # noqa: BLE001 - sanitized independent profile boundary
            items.append(
                PlanPrewarmItem(
                    profile=profile,
                    profile_id=profile.profile_id,
                    status="failed",
                    duration_ms=round((perf_counter() - item_started) * 1000, 3),
                    error_type=type(exc).__name__,
                )
            )

    succeeded = sum(item.status == "success" for item in items)
    failed = len(items) - succeeded
    if failed == 0:
        status = "complete"
    elif succeeded:
        status = "partial_failure"
    else:
        status = "failed"
    remained_active = is_active(universe_id) if is_active is not None else True
    finished_at = started_at if now is not None else datetime.now(tz=UTC)
    return PlanPrewarmReport(
        status=status,
        universe_id=universe_id,
        started_at=started_at,
        finished_at=finished_at,
        profiles_requested=len(profiles),
        profiles_succeeded=succeeded,
        profiles_failed=failed,
        cache_hits=sum(item.cache_outcome == "hit" for item in items),
        cache_misses_filled=sum(item.cache_outcome == "miss_filled" for item in items),
        cache_unchanged=sum(item.cache_outcome == "unchanged" for item in items),
        items=tuple(items),
        universe_remained_active=remained_active,
    )


class PlanPrewarmStatusRegistry:
    """Thread-safe process-local operational status, separate from price data."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._reports: dict[str, PlanPrewarmReport] = {}

    def publish(self, scope_id: str, report: PlanPrewarmReport) -> None:
        normalized = scope_id.casefold().strip()
        if not normalized.startswith("city:"):
            raise ValueError("prewarm status scope must be a city scope")
        with self._lock:
            self._reports[normalized] = report

    def get(self, scope_id: str) -> PlanPrewarmReport | None:
        with self._lock:
            return self._reports.get(scope_id.casefold().strip())


GLOBAL_PLAN_PREWARM_STATUS = PlanPrewarmStatusRegistry()


__all__ = [
    "GLOBAL_PLAN_PREWARM_STATUS",
    "PlanPrewarmExecution",
    "PlanPrewarmItem",
    "PlanPrewarmReport",
    "PlanPrewarmStatusRegistry",
    "StandardPlanPrewarmConfig",
    "StandardPlanPrewarmProfile",
    "StandardPlanPrewarmRunner",
    "prewarm_not_run_report",
    "prewarm_standard_plans",
]
