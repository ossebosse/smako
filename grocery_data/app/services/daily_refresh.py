from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.services.freshness import (
    FreshnessAssessment,
    FreshnessPolicy,
    FreshnessState,
    assess_freshness,
)
from grocery_data.app.services.plan_prewarm import (
    PlanPrewarmReport,
    PlanPrewarmStatusRegistry,
    StandardPlanPrewarmConfig,
    StandardPlanPrewarmRunner,
    prewarm_not_run_report,
    prewarm_standard_plans,
)


class RefreshTargetOutput(BaseModel):
    """Sanitized result returned by one independently executed refresh target."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    successful: bool
    promoted: bool = False
    snapshot_id: str | None = None
    observed_at: datetime | None = None
    products: int | None = Field(default=None, ge=0)
    requests: int = Field(default=0, ge=0)
    warnings: tuple[str, ...] = ()


class LastKnownGood(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: str | None = None
    observed_at: datetime | None = None


RefreshRunner = Callable[[], RefreshTargetOutput | Awaitable[RefreshTargetOutput]]
LastKnownGoodReader = Callable[[], LastKnownGood]


@dataclass(frozen=True, slots=True)
class RefreshTarget:
    """One context/source operation with its own failure boundary."""

    target_id: str
    chain: str
    context_name: str
    source_provider: str
    roles: tuple[str, ...]
    runner: RefreshRunner
    last_known_good: LastKnownGoodReader


class UniverseRefreshResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    status: str
    universe_id: str | None = None
    built_at: datetime | None = None
    product_count: int | None = Field(default=None, ge=0)
    canonical_index_count: int | None = Field(default=None, ge=0)
    active_unchanged: bool = False
    error_type: str | None = None


class UniverseRefreshHook(Protocol):
    """Composition seam for a build/validate/atomic-activate implementation."""

    def rebuild_and_activate(
        self,
        city: str,
    ) -> UniverseRefreshResult | Awaitable[UniverseRefreshResult]: ...


async def run_universe_refresh(
    city: str,
    *,
    promoted: bool,
    hook: UniverseRefreshHook | None,
) -> UniverseRefreshResult:
    """Run the optional post-promotion composition hook behind a safe boundary.

    The CLI can run without a backend composition root and reports that state
    explicitly. Hook exceptions are reduced to their allowlisted type; no
    exception text, credentials or provider state enter the daily report.
    """

    if hook is None:
        return UniverseRefreshResult(status="rebuild_unavailable", active_unchanged=True)
    if not promoted:
        return UniverseRefreshResult(
            status="not_rebuilt_no_promotions",
            active_unchanged=True,
        )
    try:
        result = await _resolve(hook.rebuild_and_activate(city.strip()))
        if not isinstance(result, UniverseRefreshResult):
            result = UniverseRefreshResult.model_validate(result)
        return result
    except Exception as exc:  # noqa: BLE001 - sanitized composition boundary
        return UniverseRefreshResult(
            status="rebuild_failed",
            active_unchanged=True,
            error_type=type(exc).__name__,
        )


class DailyRefreshItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_id: str
    chain: str
    context_name: str
    source_provider: str
    roles: tuple[str, ...]
    status: FreshnessState
    refresh_successful: bool
    promoted: bool
    snapshot_id: str | None = None
    observed_at: datetime | None = None
    age_hours: float | None = Field(default=None, ge=0)
    hours_until_stale: float | None = Field(default=None, ge=0)
    stale_at: datetime | None = None
    next_expected_source_refresh: datetime | None = None
    source_will_expire_before_next_refresh: bool = False
    retry_required: bool = False
    lkg_used: bool = False
    lkg_usable: bool = False
    products: int | None = Field(default=None, ge=0)
    requests: int = Field(default=0, ge=0)
    warnings: tuple[str, ...] = ()
    error_type: str | None = None


class DailyRefreshReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_type: str = "daily_refresh"
    city: str
    started_at: datetime
    finished_at: datetime
    warning_age_hours: float = Field(gt=0)
    stale_age_hours: float = Field(gt=0)
    items: tuple[DailyRefreshItem, ...]
    universe: UniverseRefreshResult
    prewarm: PlanPrewarmReport
    summary: dict[str, int]
    provider_requests_during_meal_generation: int = 0


async def _resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


class DailyRefreshOrchestrator:
    """Run independent refreshes, retain LKG, then atomically rebuild an area universe.

    The orchestrator owns no connector and performs no network call itself. Each
    target is isolated. A failed target is reported as ``BROKEN`` while its LKG
    remains explicitly usable only until the stale threshold.
    """

    def __init__(
        self,
        *,
        freshness_policy: FreshnessPolicy | None = None,
        universe_hook: UniverseRefreshHook | None = None,
        prewarm_config: StandardPlanPrewarmConfig | None = None,
        prewarm_runner: StandardPlanPrewarmRunner | None = None,
        prewarm_status_registry: PlanPrewarmStatusRegistry | None = None,
        is_universe_active: Callable[[str], bool] | None = None,
    ) -> None:
        self.freshness_policy = freshness_policy or FreshnessPolicy()
        self.universe_hook = universe_hook
        self.prewarm_config = prewarm_config or StandardPlanPrewarmConfig(enabled=False)
        self.prewarm_runner = prewarm_runner
        self.prewarm_status_registry = prewarm_status_registry
        self.is_universe_active = is_universe_active

    async def run(
        self,
        city: str,
        targets: Sequence[RefreshTarget],
        *,
        now: datetime | None = None,
    ) -> DailyRefreshReport:
        normalized_city = city.strip()
        if not normalized_city:
            raise ValueError("city is required")
        ids = [target.target_id for target in targets]
        if len(ids) != len(set(ids)):
            raise ValueError("daily refresh target IDs must be unique")
        started_at = now or datetime.now(tz=UTC)
        if started_at.tzinfo is None or started_at.utcoffset() is None:
            raise ValueError("daily refresh time must be timezone-aware")
        started_at = started_at.astimezone(UTC)
        items: list[DailyRefreshItem] = []
        promoted = 0
        for target in targets:
            try:
                output = await _resolve(target.runner())
                if not isinstance(output, RefreshTargetOutput):
                    output = RefreshTargetOutput.model_validate(output)
                if not output.successful:
                    raise RuntimeError("refresh target returned unsuccessful")
                evidence = output.observed_at
                freshness = assess_freshness(
                    evidence,
                    now=started_at,
                    policy=self.freshness_policy,
                )
                promoted += int(output.promoted)
                items.append(
                    self._item(
                        target,
                        output=output,
                        freshness=freshness,
                        lkg_used=False,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - independent sanitized boundary
                lkg = target.last_known_good()
                lkg_freshness = assess_freshness(
                    lkg.observed_at,
                    now=started_at,
                    policy=self.freshness_policy,
                )
                broken = assess_freshness(
                    lkg.observed_at,
                    now=started_at,
                    policy=self.freshness_policy,
                    broken=True,
                )
                items.append(
                    DailyRefreshItem(
                        target_id=target.target_id,
                        chain=target.chain,
                        context_name=target.context_name,
                        source_provider=target.source_provider,
                        roles=target.roles,
                        status=FreshnessState.BROKEN,
                        refresh_successful=False,
                        promoted=False,
                        snapshot_id=lkg.snapshot_id,
                        observed_at=lkg.observed_at,
                        age_hours=broken.age_hours,
                        hours_until_stale=broken.hours_until_stale,
                        stale_at=broken.stale_at,
                        retry_required="basket" in target.roles,
                        lkg_used=lkg.snapshot_id is not None,
                        lkg_usable=lkg_freshness.usable,
                        error_type=type(exc).__name__,
                    )
                )

        universe = await run_universe_refresh(
            normalized_city,
            promoted=bool(promoted),
            hook=self.universe_hook,
        )
        prewarm = await prewarm_standard_plans(
            universe_id=universe.universe_id,
            activated=universe_refresh_activated(universe),
            config=self.prewarm_config,
            runner=self.prewarm_runner,
            is_active=self.is_universe_active,
            now=started_at if now is not None else None,
        )
        if self.prewarm_status_registry is not None:
            self.prewarm_status_registry.publish(
                f"city:{normalized_city.casefold()}",
                prewarm,
            )

        finished_at = datetime.now(tz=UTC) if now is None else started_at
        return DailyRefreshReport(
            city=normalized_city,
            started_at=started_at,
            finished_at=finished_at,
            warning_age_hours=self.freshness_policy.warning_age_hours,
            stale_age_hours=self.freshness_policy.stale_age_hours,
            items=tuple(items),
            universe=universe,
            prewarm=prewarm,
            summary={
                "targets": len(items),
                "fresh": sum(item.status is FreshnessState.FRESH for item in items),
                "aging": sum(item.status is FreshnessState.AGING for item in items),
                "stale": sum(item.status is FreshnessState.STALE for item in items),
                "broken": sum(item.status is FreshnessState.BROKEN for item in items),
                "promoted": promoted,
                "lkg_used": sum(item.lkg_used for item in items),
                "lkg_usable": sum(item.lkg_usable for item in items),
            },
        )

    @staticmethod
    def _item(
        target: RefreshTarget,
        *,
        output: RefreshTargetOutput,
        freshness: FreshnessAssessment,
        lkg_used: bool,
    ) -> DailyRefreshItem:
        return DailyRefreshItem(
            target_id=target.target_id,
            chain=target.chain,
            context_name=target.context_name,
            source_provider=target.source_provider,
            roles=target.roles,
            status=freshness.state,
            refresh_successful=True,
            promoted=output.promoted,
            snapshot_id=output.snapshot_id,
            observed_at=output.observed_at,
            age_hours=freshness.age_hours,
            hours_until_stale=freshness.hours_until_stale,
            stale_at=freshness.stale_at,
            lkg_used=lkg_used,
            lkg_usable=lkg_used and freshness.usable,
            products=output.products,
            requests=output.requests,
            warnings=output.warnings,
        )


class AtomicPriceUniverseRefreshHook:
    """Adapt an injected PriceUniverseManager without importing backend internals.

    Product/key loading and validation happen through explicit callables. The
    manager's ``build_and_activate`` contract performs build/validation before
    its short atomic swap. If anything raises, the previous active object must
    remain object-identical; this adapter verifies that invariant.
    """

    def __init__(
        self,
        manager: Any,
        *,
        key_loader: Callable[[str], Any],
        products_loader: Callable[[str], Sequence[Any]],
        validator: Callable[[Any], bool | None] | None = None,
    ) -> None:
        self.manager = manager
        self.key_loader = key_loader
        self.products_loader = products_loader
        self.validator = validator

    def rebuild_and_activate(self, city: str) -> UniverseRefreshResult:
        key = self.key_loader(city)
        scope = str(key.scope_id)
        before = self.manager.get_active(scope)
        try:
            universe = self.manager.build_and_activate(
                key,
                self.products_loader(city),
                validator=self.validator,
            )
        except Exception:
            if self.manager.get_active(scope) is not before:
                raise RuntimeError("active PriceUniverse changed after failed rebuild") from None
            raise
        stats = getattr(universe, "stats", None)
        return UniverseRefreshResult(
            status="active",
            universe_id=str(universe.universe_id),
            built_at=universe.built_at,
            product_count=len(getattr(universe, "products", ())),
            canonical_index_count=(
                getattr(stats, "canonical_index_count", None)
                if stats is not None
                else len(getattr(getattr(universe, "indexes", None), "canonical", {}))
            ),
            active_unchanged=False,
        )


def report_from_collection_results(
    city: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    policy: FreshnessPolicy,
    now: datetime | None = None,
    universe: UniverseRefreshResult | None = None,
    prewarm: PlanPrewarmReport | None = None,
) -> DailyRefreshReport:
    """Project the existing isolated ``collect-all`` result into daily status.

    This adapter is intentionally network-free and is also useful to schedulers
    that execute connector jobs outside this process.
    """

    evaluated_at = now or datetime.now(tz=UTC)
    items: list[DailyRefreshItem] = []
    for index, row in enumerate(rows):
        raw_status = str(row.get("status") or "failed")
        successful = raw_status == "healthy"
        observed_at = row.get("observed_at")
        if observed_at is None:
            observed_at = row.get("active_snapshot_observed_at")
        if isinstance(observed_at, str):
            observed_at = datetime.fromisoformat(observed_at)
        if observed_at is None and row.get("active_snapshot_age_hours") is not None:
            from datetime import timedelta

            observed_at = evaluated_at - timedelta(
                hours=float(row["active_snapshot_age_hours"])
            )
        assessment = assess_freshness(
            observed_at,
            now=evaluated_at,
            policy=policy,
            broken=not successful and raw_status != "skipped",
            broken_reason="latest isolated refresh did not complete",
        )
        snapshot_id = row.get("snapshot_id") if successful else row.get("active_snapshot_id")
        lkg_used = not successful and bool(snapshot_id)
        natural = assess_freshness(observed_at, now=evaluated_at, policy=policy)
        items.append(
            DailyRefreshItem(
                target_id=str(
                    row.get("scope_key")
                    or row.get("grocery_context_id")
                    or f"{row.get('chain', 'unknown')}:{row.get('city', city)}:{index}"
                ),
                chain=str(row.get("chain") or "unknown"),
                context_name=str(
                    row.get("grocery_context_id")
                    or row.get("context_store_id")
                    or row.get("city")
                    or city
                ),
                source_provider=str(row.get("source_provider") or "own"),
                roles=tuple(str(value) for value in row.get("roles") or ()),
                status=assessment.state,
                refresh_successful=successful,
                promoted=bool(row.get("promoted")),
                snapshot_id=str(snapshot_id) if snapshot_id else None,
                observed_at=observed_at,
                age_hours=assessment.age_hours,
                hours_until_stale=assessment.hours_until_stale,
                stale_at=assessment.stale_at,
                retry_required=(
                    "basket" in {str(role).casefold() for role in row.get("roles") or ()}
                    and (
                        not successful
                        or natural.state
                        in {FreshnessState.AGING, FreshnessState.STALE, FreshnessState.BROKEN}
                    )
                ),
                lkg_used=lkg_used,
                lkg_usable=lkg_used and natural.usable,
                products=(int(row["products"]) if row.get("products") is not None else None),
                requests=int(row.get("requests") or 0),
                warnings=tuple(str(value) for value in row.get("warnings") or ()),
                error_type=(str(row["error_type"]) if row.get("error_type") else None),
            )
        )
    active_universe = universe or UniverseRefreshResult(
        status="not_configured",
        active_unchanged=True,
    )
    prewarm_status = prewarm or prewarm_not_run_report(
        "disabled",
        universe_id=active_universe.universe_id,
        profiles_requested=0,
        now=evaluated_at,
    )
    return DailyRefreshReport(
        city=city.strip(),
        started_at=evaluated_at,
        finished_at=evaluated_at,
        warning_age_hours=policy.warning_age_hours,
        stale_age_hours=policy.stale_age_hours,
        items=tuple(items),
        universe=active_universe,
        prewarm=prewarm_status,
        summary={
            "targets": len(items),
            "fresh": sum(item.status is FreshnessState.FRESH for item in items),
            "aging": sum(item.status is FreshnessState.AGING for item in items),
            "stale": sum(item.status is FreshnessState.STALE for item in items),
            "broken": sum(item.status is FreshnessState.BROKEN for item in items),
            "promoted": sum(item.promoted for item in items),
            "lkg_used": sum(item.lkg_used for item in items),
            "lkg_usable": sum(item.lkg_usable for item in items),
        },
    )


def universe_refresh_activated(result: UniverseRefreshResult) -> bool:
    """Recognize only a completed new activation as eligible for prewarming."""

    return bool(
        result.universe_id
        and not result.active_unchanged
        and result.status in {"active", "active_from_prebuilt_artifact"}
    )


__all__ = [
    "AtomicPriceUniverseRefreshHook",
    "DailyRefreshItem",
    "DailyRefreshOrchestrator",
    "DailyRefreshReport",
    "LastKnownGood",
    "RefreshTarget",
    "RefreshTargetOutput",
    "UniverseRefreshHook",
    "UniverseRefreshResult",
    "report_from_collection_results",
    "run_universe_refresh",
    "universe_refresh_activated",
]
