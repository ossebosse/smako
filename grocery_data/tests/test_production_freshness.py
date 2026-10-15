from __future__ import annotations

import json
from argparse import Namespace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import grocery_data.__main__ as grocery_cli
from grocery_data.app.domain.enums import Confidence, SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalPriceObservation,
    PhysicalSampleConfidence,
)
from grocery_data.app.services import prepared_universe_activation as prepared_module
from grocery_data.app.services.closed_provider_cache import inspect_closed_provider_cache
from grocery_data.app.services.daily_refresh import (
    AtomicPriceUniverseRefreshHook,
    DailyRefreshOrchestrator,
    LastKnownGood,
    RefreshTarget,
    RefreshTargetOutput,
)
from grocery_data.app.services.durable_files import (
    InsufficientStorageError,
    StoragePreflight,
)
from grocery_data.app.services.freshness import (
    FreshnessPolicy,
    FreshnessState,
    assess_freshness,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalVerificationSuggestionSampler,
    build_accuracy_report,
)
from grocery_data.app.services.plan_prewarm import StandardPlanPrewarmConfig
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactMetadata,
    PreparedUniverseArtifactStore,
)

NOW = datetime(2026, 8, 24, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (0, FreshnessState.FRESH),
        (35.99, FreshnessState.FRESH),
        (36, FreshnessState.AGING),
        (47.99, FreshnessState.AGING),
        (48, FreshnessState.STALE),
    ],
)
def test_freshness_policy_has_warning_before_stale(
    age: float,
    expected: FreshnessState,
) -> None:
    result = assess_freshness(
        NOW - timedelta(hours=age),
        now=NOW,
        policy=FreshnessPolicy(warning_age_hours=36, stale_age_hours=48),
    )

    assert result.state is expected
    assert result.usable is (age < 48)
    assert result.retained_observation_usable is True
    assert result.warning is (age >= 36)


@pytest.mark.parametrize("observation", [None, NOW + timedelta(hours=2)])
def test_retention_rejects_unknown_or_future_observation(observation):
    assert not assess_freshness(observation, now=NOW).retained_observation_usable


@pytest.mark.asyncio
async def test_daily_refresh_isolates_failure_and_keeps_fresh_lkg() -> None:
    calls: list[str] = []

    async def healthy() -> RefreshTargetOutput:
        calls.append("healthy")
        return RefreshTargetOutput(
            successful=True,
            promoted=True,
            snapshot_id="snapshot-new",
            observed_at=NOW - timedelta(hours=1),
            products=100,
            requests=2,
        )

    async def broken() -> RefreshTargetOutput:
        calls.append("broken")
        raise RuntimeError("secret-bearing source error must not escape")

    class UniverseHook:
        called = 0

        def rebuild_and_activate(self, city: str):  # type: ignore[no-untyped-def]
            self.called += 1
            return {
                "status": "active",
                "universe_id": f"universe:{city.casefold()}",
                "built_at": NOW,
                "product_count": 90,
                "canonical_index_count": 10,
            }

    hook = UniverseHook()
    report = await DailyRefreshOrchestrator(
        freshness_policy=FreshnessPolicy(warning_age_hours=36, stale_age_hours=48),
        universe_hook=hook,
    ).run(
        "Lund",
        (
            RefreshTarget(
                target_id="willys:2176",
                chain="willys",
                context_name="Willys Lund",
                source_provider="own",
                roles=("basket",),
                runner=healthy,
                last_known_good=lambda: LastKnownGood(),
            ),
            RefreshTarget(
                target_id="hemkop:4123",
                chain="hemkop",
                context_name="Hemköp Karhögstorg",
                source_provider="own",
                roles=("basket",),
                runner=broken,
                last_known_good=lambda: LastKnownGood(
                    snapshot_id="snapshot-lkg",
                    observed_at=NOW - timedelta(hours=12),
                ),
            ),
        ),
        now=NOW,
    )

    assert calls == ["healthy", "broken"]
    assert report.items[0].status is FreshnessState.FRESH
    assert report.items[1].status is FreshnessState.BROKEN
    assert report.items[1].lkg_used is True
    assert report.items[1].lkg_usable is True
    assert report.items[1].error_type == "RuntimeError"
    assert "secret" not in report.model_dump_json()
    assert report.summary == {
        "targets": 2,
        "fresh": 1,
        "aging": 0,
        "stale": 0,
        "broken": 1,
        "promoted": 1,
        "lkg_used": 1,
        "lkg_usable": 1,
    }
    assert report.universe.status == "active"
    assert hook.called == 1


@pytest.mark.asyncio
async def test_daily_refresh_keeps_activated_universe_when_prewarm_fails() -> None:
    active = {"universe_id": None}

    async def collect() -> RefreshTargetOutput:
        return RefreshTargetOutput(
            successful=True,
            promoted=True,
            snapshot_id="snapshot-new",
            observed_at=NOW,
            products=10,
        )

    class UniverseHook:
        def rebuild_and_activate(self, _city: str):  # type: ignore[no-untyped-def]
            active["universe_id"] = "universe-1"
            return {
                "status": "active",
                "universe_id": "universe-1",
                "built_at": NOW,
                "product_count": 10,
                "canonical_index_count": 2,
            }

    async def failing_prewarm(_profile):  # type: ignore[no-untyped-def]
        raise RuntimeError("secret prewarm failure")

    report = await DailyRefreshOrchestrator(
        universe_hook=UniverseHook(),
        prewarm_config=StandardPlanPrewarmConfig(
            enabled=True,
            modes=("balanced",),
            max_stores=(2,),
        ),
        prewarm_runner=failing_prewarm,
        is_universe_active=lambda universe_id: active["universe_id"] == universe_id,
    ).run(
        "Lund",
        (
            RefreshTarget(
                target_id="hemkop:4123",
                chain="hemkop",
                context_name="Hemköp Karhögstorg",
                source_provider="own",
                roles=("basket",),
                runner=collect,
                last_known_good=lambda: LastKnownGood(),
            ),
        ),
        now=NOW,
    )

    assert report.universe.status == "active"
    assert active["universe_id"] == "universe-1"
    assert report.prewarm.status == "failed"
    assert report.prewarm.profiles_failed == 1
    assert report.prewarm.universe_remained_active is True
    assert "secret prewarm" not in report.model_dump_json()


def test_atomic_universe_hook_keeps_previous_active_on_broken_rebuild() -> None:
    active = object()

    class Key:
        scope_id = "city:lund"

    class Manager:
        current = active

        def get_active(self, scope: str):  # type: ignore[no-untyped-def]
            assert scope == "city:lund"
            return self.current

        def build_and_activate(self, key, products, *, validator):  # type: ignore[no-untyped-def]
            del key, products, validator
            raise ValueError("validation failed")

    manager = Manager()
    hook = AtomicPriceUniverseRefreshHook(
        manager,
        key_loader=lambda _city: Key(),
        products_loader=lambda _city: ("product",),
    )

    with pytest.raises(ValueError, match="validation failed"):
        hook.rebuild_and_activate("Lund")
    assert manager.current is active


def test_atomic_universe_hook_projects_active_status() -> None:
    class Key:
        scope_id = "city:lund"

    class Stats:
        canonical_index_count = 12

    class Universe:
        universe_id = "universe-1"
        built_at = NOW
        products = ("one", "two", "three")
        stats = Stats()

    class Manager:
        current = None

        def get_active(self, _scope: str):  # type: ignore[no-untyped-def]
            return self.current

        def build_and_activate(self, key, products, *, validator):  # type: ignore[no-untyped-def]
            assert key.scope_id == "city:lund"
            assert products == ("one", "two", "three")
            assert validator is None
            self.current = Universe()
            return self.current

    result = AtomicPriceUniverseRefreshHook(
        Manager(),
        key_loader=lambda _city: Key(),
        products_loader=lambda _city: ("one", "two", "three"),
    ).rebuild_and_activate("Lund")

    assert result.status == "active"
    assert result.universe_id == "universe-1"
    assert result.product_count == 3
    assert result.canonical_index_count == 12
    assert result.active_unchanged is False


def test_physical_accuracy_is_not_displayed_below_minimum_sample() -> None:
    observations = tuple(
        PhysicalPriceObservation(
            id=f"observation-{index}",
            physical_store_id="physical:hemkop:4123",
            gtin="7310865004703",
            shelf_price=Decimal("29.90"),
            observed_at=NOW,
            confidence=Confidence.HIGH,
        )
        for index in range(19)
    )

    limited = build_accuracy_report(
        observations,
        (),
        scope_label="Hemköp Karhögstorg",
        minimum_sample=20,
    )
    good = build_accuracy_report(
        (*observations, observations[0].model_copy(update={"id": "observation-19"})),
        (),
        scope_label="Hemköp Karhögstorg",
        minimum_sample=20,
    )

    assert limited.score_eligible is False
    assert limited.sample_confidence is PhysicalSampleConfidence.LIMITED_SAMPLE
    assert good.score_eligible is True
    assert good.sample_confidence is PhysicalSampleConfidence.GOOD_SAMPLE


@pytest.mark.asyncio
async def test_daily_refresh_cli_projects_isolated_collection_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output: list[dict[str, object]] = []

    async def closed_collection(_args: Namespace):  # type: ignore[no-untyped-def]
        return (
            {
                "run_type": "daily_own_collection",
                "cities": ["Lund"],
                "results": [
                    {
                        "chain": "willys",
                        "city": "Lund",
                        "scope_key": "lund:willys:2176",
                        "roles": ("basket",),
                        "source_provider": "own",
                        "status": "healthy",
                        "promoted": True,
                        "snapshot_id": "snapshot-1",
                        "active_snapshot_age_hours": 1,
                        "products": 100,
                        "requests": 5,
                    }
                ],
                "summary": {},
            },
            0,
        )

    monkeypatch.setattr(grocery_cli, "_run_collect_all", closed_collection)
    monkeypatch.setattr(grocery_cli, "_json", output.append)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    exit_code = await grocery_cli._daily_refresh(
        Namespace(
            city=["Lund"],
            no_promote=False,
            external_cache=None,
            price_universe_candidate=None,
            price_universe_cache_root=None,
        )
    )

    assert exit_code == 0
    assert output[0]["meal_generation_live_requests"] == 0
    assert output[0]["external_provider"] == {
        "status": "not_requested",
        "provider_requests": 0,
        "reason": "no closed external cache path supplied",
    }
    [report] = output[0]["reports"]
    assert report["items"][0]["status"] == "fresh"
    assert report["universe"]["status"] == "rebuild_unavailable"
    assert report["universe"]["active_unchanged"] is True


def _artifact_metadata(
    _payload: object,
    city: str,
    *,
    snapshot_ids: tuple[str, ...] = ("snapshot-1",),
) -> PreparedUniverseArtifactMetadata:
    return PreparedUniverseArtifactMetadata(
        city=city,
        scope_id=f"city:{city}",
        universe_id="universe-1",
        built_at=NOW,
        snapshot_ids=snapshot_ids,
        product_count=321,
        canonical_index_count=48,
        oldest_observed_at=NOW - timedelta(hours=1),
    )


def test_prepared_universe_artifact_activation_is_content_addressed_and_atomic(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text(
        json.dumps({"schema_version": "prepared-price-universe-v1", "rows": [1]}),
        encoding="utf-8",
    )
    store = PreparedUniverseArtifactStore(tmp_path / "managed")

    result = store.activate(
        candidate,
        city="Lund",
        validator=lambda payload, city: _artifact_metadata(payload, city),
        expected_snapshot_ids=("snapshot-1",),
        activated_at=NOW,
    )

    manifest = store.read_active("Lund")
    assert manifest is not None
    assert result.status == "active_from_prebuilt_artifact"
    assert result.provider_requests == 0
    assert manifest.universe_id == "universe-1"
    assert manifest.snapshot_ids == ("snapshot-1",)
    assert (store.root / manifest.artifact_file).read_bytes() == candidate.read_bytes()
    assert store.resolve_active_artifact("Lund") == store.root / manifest.artifact_file


def test_broken_prepared_universe_rebuild_leaves_active_manifest_byte_identical(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"value": "first"}), encoding="utf-8")
    store = PreparedUniverseArtifactStore(tmp_path / "managed")
    store.activate(
        candidate,
        city="Lund",
        validator=lambda payload, city: _artifact_metadata(payload, city),
        activated_at=NOW,
    )
    before = store.active_manifest_bytes("Lund")
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"value": "second"}), encoding="utf-8")
    calls = 0

    def breaks_after_copy(payload, city):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("stored artifact validation failed")
        return _artifact_metadata(payload, city, snapshot_ids=("snapshot-2",))

    with pytest.raises(ValueError, match="stored artifact validation failed"):
        store.activate(
            broken,
            city="Lund",
            validator=breaks_after_copy,
            expected_snapshot_ids=("snapshot-2",),
            activated_at=NOW,
        )

    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund").universe_id == "universe-1"  # type: ignore[union-attr]


def test_prepared_universe_enospc_preflight_preserves_active_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = PreparedUniverseArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    current.write_text(json.dumps({"value": "current"}), encoding="utf-8")
    store.activate(
        current,
        city="Lund",
        validator=lambda payload, city: _artifact_metadata(payload, city),
        activated_at=NOW,
    )
    before = store.active_manifest_bytes("Lund")
    replacement = tmp_path / "replacement.json"
    replacement.write_text(json.dumps({"value": "replacement"}), encoding="utf-8")

    def no_space(*_args: object, **_kwargs: object) -> StoragePreflight:
        raise InsufficientStorageError(StoragePreflight(10, 20, 64))

    monkeypatch.setattr(prepared_module, "require_free_space", no_space)

    with pytest.raises(InsufficientStorageError):
        store.activate(
            replacement,
            city="Lund",
            validator=lambda payload, city: _artifact_metadata(
                payload,
                city,
                snapshot_ids=("snapshot-2",),
            ),
            activated_at=NOW + timedelta(minutes=1),
        )

    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") is not None
    assert not list((store.root / "artifacts").glob(".*.tmp"))


def test_active_artifact_resolver_detects_same_size_tampering(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"value": "first"}), encoding="utf-8")
    store = PreparedUniverseArtifactStore(tmp_path / "managed")
    store.activate(
        candidate,
        city="Lund",
        validator=lambda payload, city: _artifact_metadata(payload, city),
        activated_at=NOW,
    )
    artifact = store.resolve_active_artifact("Lund")
    assert artifact is not None
    artifact.write_bytes(b"x" * artifact.stat().st_size)

    with pytest.raises(ValueError, match="hash mismatch"):
        store.resolve_active_artifact("Lund")


def test_prepared_universe_restart_pointer_can_rollback_with_compare_guard(
    tmp_path: Path,
) -> None:
    store = PreparedUniverseArtifactStore(tmp_path / "managed")
    first = tmp_path / "first.json"
    first.write_text(json.dumps({"value": "first"}), encoding="utf-8")
    store.activate(
        first,
        city="Lund",
        validator=lambda payload, city: _artifact_metadata(payload, city),
        activated_at=NOW,
    )
    previous = store.active_manifest_bytes("Lund")
    second = tmp_path / "second.json"
    second.write_text(json.dumps({"value": "second"}), encoding="utf-8")
    store.activate(
        second,
        city="Lund",
        validator=lambda payload, city: _artifact_metadata(
            payload,
            city,
            snapshot_ids=("snapshot-2",),
        ),
        activated_at=NOW + timedelta(minutes=1),
    )
    promoted = store.active_manifest_bytes("Lund")
    assert promoted != previous

    store.restore_active_manifest(
        "Lund",
        previous,
        expected_current=promoted,
    )

    assert store.active_manifest_bytes("Lund") == previous
    assert store.resolve_active_artifact("Lund") is not None
    with pytest.raises(RuntimeError, match="changed before rollback"):
        store.restore_active_manifest(
            "Lund",
            promoted,
            expected_current=promoted,
        )
    assert store.active_manifest_bytes("Lund") == previous


def test_prepared_artifact_requires_current_promoted_snapshot_lineage(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"value": "stale"}), encoding="utf-8")
    store = PreparedUniverseArtifactStore(tmp_path / "managed")

    with pytest.raises(ValueError, match="lacks promoted snapshot lineage"):
        store.activate(
            candidate,
            city="Lund",
            validator=lambda payload, city: _artifact_metadata(payload, city),
            expected_snapshot_ids=("snapshot-new",),
            activated_at=NOW,
        )

    assert store.active_manifest_bytes("Lund") is None


def test_prepared_artifact_rejects_credentials_before_activation(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"authorization": "secret"}), encoding="utf-8")
    store = PreparedUniverseArtifactStore(tmp_path / "managed")

    with pytest.raises(ValueError, match="forbidden transport"):
        store.activate(
            candidate,
            city="Lund",
            validator=lambda payload, city: _artifact_metadata(payload, city),
            activated_at=NOW,
        )

    assert store.active_manifest_bytes("Lund") is None


@pytest.mark.asyncio
async def test_daily_refresh_cli_activates_explicit_local_candidate_without_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output: list[dict[str, object]] = []
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"value": "closed-local"}), encoding="utf-8")

    async def closed_collection(_args: Namespace):  # type: ignore[no-untyped-def]
        return (
            {
                "run_type": "daily_own_collection",
                "cities": ["Lund"],
                "results": [
                    {
                        "chain": "willys",
                        "city": "Lund",
                        "scope_key": "lund:willys:2176",
                        "roles": ("basket",),
                        "source_provider": "own",
                        "status": "healthy",
                        "promoted": True,
                        "snapshot_id": "snapshot-1",
                        "active_snapshot_age_hours": 1,
                        "products": 100,
                        "requests": 5,
                    }
                ],
                "summary": {},
            },
            0,
        )

    monkeypatch.setattr(grocery_cli, "_run_collect_all", closed_collection)
    monkeypatch.setattr(grocery_cli, "_json", output.append)
    monkeypatch.setattr(grocery_cli, "_ensure_backend_import_path", lambda: None)
    monkeypatch.setattr(
        grocery_cli,
        "validate_backend_prepared_universe_artifact",
        lambda payload, city: _artifact_metadata(payload, city),
    )
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    exit_code = await grocery_cli._daily_refresh(
        Namespace(
            city=["Lund"],
            no_promote=False,
            external_cache=None,
            price_universe_candidate=candidate,
            price_universe_cache_root=tmp_path / "active",
        )
    )

    assert exit_code == 0
    [report] = output[0]["reports"]
    assert report["universe"]["status"] == "active_from_prebuilt_artifact"
    assert report["universe"]["universe_id"] == "universe-1"
    assert report["universe"]["provider_requests"] == 0
    assert PreparedUniverseArtifactStore(tmp_path / "active").read_active("Lund") is not None


@pytest.mark.asyncio
async def test_daily_refresh_reports_injected_rebuild_failure_without_leaking_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output: list[dict[str, object]] = []

    async def closed_collection(_args: Namespace):  # type: ignore[no-untyped-def]
        return (
            {
                "cities": ["Lund"],
                "results": [
                    {
                        "chain": "willys",
                        "city": "Lund",
                        "roles": ("basket",),
                        "status": "healthy",
                        "promoted": True,
                        "snapshot_id": "snapshot-1",
                        "active_snapshot_age_hours": 1,
                    }
                ],
                "summary": {},
            },
            0,
        )

    class BrokenHook:
        def rebuild_and_activate(self, _city: str):  # type: ignore[no-untyped-def]
            raise RuntimeError("secret-bearing rebuild detail")

    monkeypatch.setattr(grocery_cli, "_run_collect_all", closed_collection)
    monkeypatch.setattr(grocery_cli, "_json", output.append)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    exit_code = await grocery_cli._daily_refresh(
        Namespace(
            city=["Lund"],
            no_promote=False,
            external_cache=None,
            price_universe_candidate=None,
            price_universe_cache_root=None,
        ),
        universe_hook=BrokenHook(),
    )

    assert exit_code == 2
    [report] = output[0]["reports"]
    assert report["universe"] == {
        "status": "rebuild_failed",
        "universe_id": None,
        "built_at": None,
        "product_count": None,
        "canonical_index_count": None,
        "active_unchanged": True,
        "error_type": "RuntimeError",
    }
    assert "secret-bearing" not in json.dumps(output)


def test_activate_price_universe_command_is_closed_and_persistent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output: list[dict[str, object]] = []
    candidate = tmp_path / "candidate.json"
    candidate.write_text(json.dumps({"value": "closed-local"}), encoding="utf-8")
    observed_at = datetime.now(tz=UTC)
    monkeypatch.setattr(grocery_cli, "_ensure_backend_import_path", lambda: None)
    monkeypatch.setattr(
        grocery_cli,
        "validate_backend_prepared_universe_artifact",
        lambda _payload, city: PreparedUniverseArtifactMetadata(
            city=city,
            scope_id=f"city:{city}",
            universe_id="universe-1",
            built_at=observed_at,
            snapshot_ids=("snapshot-1",),
            product_count=321,
            canonical_index_count=48,
            oldest_observed_at=observed_at,
        ),
    )
    monkeypatch.setattr(grocery_cli, "_json", output.append)

    exit_code = grocery_cli._activate_price_universe(
        Namespace(
            city="Lund",
            candidate=candidate,
            cache_root=tmp_path / "active",
            expected_snapshot_id=["snapshot-1"],
        )
    )

    assert exit_code == 0
    assert output[0]["run_type"] == "activate_prepared_price_universe"
    assert output[0]["city"] == "Lund"
    assert output[0]["live_provider_requests"] == 0
    result = output[0]["result"]
    assert result["status"] == "active_from_prebuilt_artifact"
    assert result["universe_id"] == "universe-1"
    assert result["product_count"] == 321
    assert result["snapshot_ids"] == ["snapshot-1"]
    assert result["provider_requests"] == 0


def test_closed_provider_cache_is_fresh_and_rejects_transport_material(
    tmp_path: Path,
) -> None:
    cache = tmp_path / "lund-cache.json"
    payload = {
        "schema_version": "lund-frozen-external-v1",
        "postal_code": "22350",
        "captured_at": (NOW - timedelta(hours=2)).isoformat(),
        "stores": [{"store_id": "ica:1"}],
        "products": [{"product_id": "rice", "source_provider": "primat"}],
    }
    cache.write_text(json.dumps(payload), encoding="utf-8")

    status = inspect_closed_provider_cache(
        cache,
        policy=FreshnessPolicy(warning_age_hours=36, stale_age_hours=48),
        now=NOW,
    )

    assert status.freshness is FreshnessState.FRESH
    assert status.usable is True
    assert status.provider_requests == 0
    payload["products"][0]["authorization"] = "must-not-survive"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden transport"):
        inspect_closed_provider_cache(
            cache,
            policy=FreshnessPolicy(warning_age_hours=36, stale_age_hours=48),
            now=NOW,
        )


def test_physical_suggestions_prioritize_large_recent_price_change() -> None:
    candidates = (
        DigitalPriceCandidate(
            physical_store_id="physical:hemkop:4123",
            grocery_context_id="own:hemkop:4123",
            source_provider="own",
            source_snapshot_id="snapshot-new",
            observed_at=NOW,
            product_id="changed",
            product_name="Changed product",
            current_price=Decimal("29.90"),
            sale_model=SaleModel.FIXED_PACKAGE,
            recent_price_change=Decimal("5.00"),
        ),
        DigitalPriceCandidate(
            physical_store_id="physical:hemkop:4123",
            grocery_context_id="own:hemkop:4123",
            source_provider="own",
            source_snapshot_id="snapshot-new",
            observed_at=NOW,
            product_id="stable",
            product_name="Stable product",
            current_price=Decimal("10.00"),
            sale_model=SaleModel.FIXED_PACKAGE,
        ),
    )

    suggestions = PhysicalVerificationSuggestionSampler().suggest(
        candidates,
        physical_store_id="physical:hemkop:4123",
        limit=2,
    )

    assert suggestions[0].product_id == "changed"
    assert "large_recent_price_change" in suggestions[0].reasons
