from __future__ import annotations

import json
import os
from argparse import Namespace
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import grocery_data.__main__ as grocery_cli
from grocery_data.app.services.freshness import FreshnessPolicy, assess_freshness
from grocery_data.app.services.manual_refresh_operations import (
    REFRESH_PARENT_LOCK_NONCE_ENV,
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactMetadata,
    PreparedUniverseArtifactStore,
)


class _Engine:
    def dispose(self) -> None:
        return None


class _UniverseStore:
    def __init__(self, *, initial: dict[str, bytes] | None = None) -> None:
        self.manifests = dict(initial or {})
        self.activations: list[tuple[str, tuple[str, ...]]] = []

    def active_manifest_bytes(self, city: str) -> bytes | None:
        return self.manifests.get(city.casefold())

    def activate(
        self,
        candidate: Path,
        *,
        city: str,
        validator: object,
        expected_snapshot_ids: tuple[str, ...],
        freshness_policy: object,
    ) -> SimpleNamespace:
        del freshness_policy, validator
        assert candidate.is_file()
        self.activations.append((city, expected_snapshot_ids))
        self.manifests[city.casefold()] = candidate.read_bytes()
        return SimpleNamespace(status="active_from_prebuilt_artifact")


class _ExternalStore:
    def __init__(self) -> None:
        self.active: dict[str, Path] = {}
        self.manifests: dict[bytes, Path] = {}

    def active_manifest_bytes(self, city: str) -> bytes | None:
        path = self.active.get(city.casefold())
        return None if path is None else str(path).encode()

    def restore_active_manifest(self, city: str, previous: bytes | None) -> None:
        key = city.casefold()
        if previous is None:
            self.active.pop(key, None)
            return
        self.active[key] = self.manifests[previous]

    def activate(self, candidate: Path, *, city: str, **_kwargs: object) -> None:
        assert candidate.is_file()
        self.active[city.casefold()] = candidate
        self.manifests[str(candidate).encode()] = candidate

    def activate_validated(
        self,
        candidate: Path,
        *,
        city: str,
        validator: object,
        **_kwargs: object,
    ) -> tuple[object, dict[str, object]]:
        assert callable(validator)
        decision = validator(candidate)
        assert decision.accepted
        self.activate(candidate, city=city)
        return object(), decision.value

    def resolve_active(self, city: str, **_kwargs: object):  # type: ignore[no-untyped-def]
        path = self.active.get(city.casefold())
        if path is None:
            return None
        status = SimpleNamespace(
            usable=True,
            snapshot_ids=(f"primat-{city.casefold()}",),
            age_hours=1.0,
            stores=1,
            products=20,
        )
        return path, status, object()


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        database_url=f"sqlite:///{tmp_path / 'refresh.sqlite'}",
        price_age_warning_hours=36.0,
        max_price_age_hours=48.0,
        price_universe_cache_root=tmp_path / "universe-cache",
    )


def _args(
    tmp_path: Path,
    cities: list[str],
    *,
    dry_run: bool = False,
) -> Namespace:
    return Namespace(
        managed_pipeline=True,
        city=cities,
        chain=None,
        context_store_id=None,
        postal_code=None,
        dry_run=dry_run,
        no_external_refresh=False,
        no_promote=False,
        external_cache=None,
        price_universe_candidate=None,
        price_universe_cache_root=tmp_path / "universe-cache",
        report_dir=tmp_path / "reports",
        format="json",
    )


def _collection(cities: list[str], *, failed: bool = False) -> tuple[dict[str, Any], int]:
    rows: list[dict[str, object]] = []
    for city in cities:
        row: dict[str, object] = {
            "chain": "willys",
            "city": city,
            "roles": ("basket",),
            "status": "healthy",
            "promoted": True,
            "snapshot_id": f"snapshot-{city.casefold()}",
            "active_snapshot_age_hours": 1.0,
            "products": 100,
            "requests": 2,
        }
        rows.append(row)
    if failed:
        rows.append(
            {
                "chain": "hemkop",
                "city": cities[0],
                "roles": ("basket",),
                "status": "failed",
                "promoted": False,
                "active_snapshot_id": "snapshot-hemkop-lkg",
                "active_snapshot_age_hours": 4.0,
                "products": 0,
                "error_type": "RuntimeError",
            }
        )
    return (
        {
            "run_type": "daily_own_collection",
            "cities": cities,
            "results": rows,
            "summary": {},
        },
        2 if failed else 0,
    )


def _patch_managed_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    store: _UniverseStore,
    collection: tuple[dict[str, Any], int],
    build_calls: list[str],
    build_failure_city: str | None = None,
) -> list[dict[str, object]]:
    emitted: list[dict[str, object]] = []
    database = tmp_path / "db"
    database.touch()
    monkeypatch.setattr(
        grocery_cli.GroceryDataSettings,
        "from_env",
        staticmethod(lambda: _settings(tmp_path)),
    )
    monkeypatch.setattr(grocery_cli, "_sqlite_database_path", lambda _settings: database)

    async def collect(_args: Namespace) -> tuple[dict[str, Any], int]:
        return collection

    async def primat(**kwargs: object) -> dict[str, object]:
        output = Path(kwargs["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text('{"schema":"test-external-cache"}', encoding="utf-8")
        return {
            "status": "pass",
            "transport": {"requests": 1},
            "contexts": [{"context_id": "verified"}],
            "output": {"products": 20},
        }

    async def build(**kwargs: object) -> dict[str, object]:
        city = str(kwargs["city"])
        build_calls.append(city)
        if city == build_failure_city:
            raise RuntimeError("Authorization=Bearer must-never-appear")
        output = Path(kwargs["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"city": city}), encoding="utf-8")
        return {"status": "pass", "timing_ms": {"total": 12.0}}

    def active_status(
        active_store: _UniverseStore,
        city: str,
        **_kwargs: object,
    ) -> dict[str, object]:
        active = active_store.active_manifest_bytes(city) is not None
        return {
            "city": city,
            "status": "fresh" if active else "inactive",
            "usable": active,
            "active": active,
            "universe_id": f"universe-{city.casefold()}" if active else None,
            "product_count": 100 if active else 0,
            "artifact_mb": 0.001 if active else 0,
            "oldest_price_age_hours": 1.0 if active else None,
        }

    monkeypatch.setattr(grocery_cli, "_run_collect_all", collect)
    monkeypatch.setattr(grocery_cli, "_collect_production_primat_cache", primat)
    monkeypatch.setattr(grocery_cli, "_build_production_price_universe", build)
    monkeypatch.setattr(grocery_cli, "PreparedUniverseArtifactStore", lambda _root: store)
    monkeypatch.setattr(
        grocery_cli,
        "ClosedProviderCacheArtifactStore",
        lambda _root: _ExternalStore(),
    )
    monkeypatch.setattr(
        grocery_cli,
        "_validate_external_context_links",
        lambda _settings, _path: {
            "status": "activated",
            "activated": 1,
            "rejected": 0,
            "cache_stores": 1,
        },
    )
    monkeypatch.setattr(
        grocery_cli,
        "_activate_external_context_links",
        lambda _settings, _path: {
            "status": "activated",
            "activated": 1,
            "rejected": 0,
            "cache_stores": 1,
        },
    )
    monkeypatch.setattr(grocery_cli, "_active_universe_status", active_status)
    monkeypatch.setattr(
        grocery_cli,
        "_emit_refresh_result",
        lambda report, **_kwargs: emitted.append(report),
    )
    return emitted


@pytest.mark.asyncio
async def test_managed_dry_run_lund_malmo_never_collects_or_builds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(
        grocery_cli.GroceryDataSettings,
        "from_env",
        staticmethod(lambda: _settings(tmp_path)),
    )
    database = tmp_path / "refresh.sqlite"
    database.touch()
    monkeypatch.setattr(grocery_cli, "_sqlite_database_path", lambda _settings: database)
    monkeypatch.setattr(grocery_cli, "_runtime", lambda: (_settings(tmp_path), _Engine(), object()))
    monkeypatch.setattr(grocery_cli, "_collect_all_plan", lambda _cities: ([], []))
    monkeypatch.setattr(
        grocery_cli,
        "_hemkop_collect_all_contexts",
        lambda _factory, _cities: ([], [], 0),
    )

    async def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("dry-run attempted collection/build work")

    monkeypatch.setattr(grocery_cli, "_run_collect_all", forbidden)
    monkeypatch.setattr(grocery_cli, "_collect_production_primat_cache", forbidden)
    monkeypatch.setattr(grocery_cli, "_build_production_price_universe", forbidden)
    monkeypatch.setattr(
        grocery_cli,
        "_plan_production_primat_refresh",
        lambda **kwargs: {
            "city": kwargs["city"],
            "status": "planned",
            "contexts": [{"context_id": f"primat:{kwargs['city']}"}],
            "provider_requests_planned": 49,
        },
    )
    monkeypatch.setattr(
        grocery_cli,
        "_emit_refresh_result",
        lambda report, **_kwargs: emitted.append(report),
    )

    exit_code = await grocery_cli._daily_refresh(
        _args(tmp_path, ["Lund", "Malmö"], dry_run=True)
    )

    assert exit_code == 0
    assert emitted[0]["network_requests"] == 0
    assert emitted[0]["database_writes"] == 0
    assert [item["city"] for item in emitted[0]["price_universe"]] == [
        "Lund",
        "Malmö",
    ]


def test_targeted_own_dry_run_keeps_required_federated_provider_plan(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        grocery_cli.GroceryDataSettings,
        "from_env",
        staticmethod(lambda: _settings(tmp_path)),
    )
    database = tmp_path / "refresh.sqlite"
    database.touch()
    monkeypatch.setattr(grocery_cli, "_sqlite_database_path", lambda _settings: database)
    monkeypatch.setattr(grocery_cli, "_runtime", lambda: (_settings(tmp_path), _Engine(), object()))
    monkeypatch.setattr(
        grocery_cli,
        "_collect_all_plan",
        lambda _cities, *, selected_chains: ([], []),
    )
    monkeypatch.setattr(
        grocery_cli,
        "_hemkop_collect_all_contexts",
        lambda _factory, _cities: ([], [], 0),
    )
    planned_cities: list[str] = []

    def plan_primat(**kwargs: object) -> dict[str, object]:
        city = str(kwargs["city"])
        planned_cities.append(city)
        return {
            "city": city,
            "status": "planned",
            "contexts": [{"context_id": "primat:verified"}],
            "provider_requests_planned": 49,
        }

    monkeypatch.setattr(grocery_cli, "_plan_production_primat_refresh", plan_primat)
    args = _args(tmp_path, ["Lund"], dry_run=True)
    args.chain = ["hemkop"]

    report = grocery_cli._daily_refresh_dry_run(args)

    assert planned_cities == ["Lund"]
    external = report["external_provider"]
    assert external["status"] == "planned_from_verified_contexts"  # type: ignore[index]
    assert external["city_plans"][0]["provider_requests_planned"] == 49  # type: ignore[index]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cities",
    [["Lund"], ["Malmö"], ["Lund", "Malmö"]],
)
async def test_managed_refresh_builds_exactly_once_per_city(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cities: list[str],
) -> None:
    store = _UniverseStore()
    builds: list[str] = []
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=_collection(cities),
        build_calls=builds,
    )

    exit_code = await grocery_cli._daily_refresh(_args(tmp_path, cities))

    assert exit_code == 0
    assert builds == cities
    assert [city for city, _lineage in store.activations] == cities
    assert emitted[0]["summary"]["universe_builds"] == len(cities)  # type: ignore[index]
    assert emitted[0]["summary"]["universe_builds_per_city_max"] == 1  # type: ignore[index]


@pytest.mark.asyncio
async def test_long_managed_refresh_annotates_later_source_at_stage_completion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run_started_at = datetime(2026, 9, 7, 11, 49, tzinfo=UTC)
    source_observed_at = run_started_at + timedelta(minutes=75)
    stage_completed_at = run_started_at + timedelta(minutes=90)
    clock = {"now": run_started_at}

    class ManagedRefreshClock(datetime):
        @classmethod
        def now(cls, tz: object = None) -> datetime:
            value = clock["now"]
            return value if tz is None else value.astimezone(tz)  # type: ignore[arg-type]

    collection, collection_exit = _collection(["Lund"])
    collection["results"][0]["active_snapshot_observed_at"] = (
        source_observed_at.isoformat()
    )
    store = _UniverseStore()
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=(collection, collection_exit),
        build_calls=[],
    )

    async def collect(_args: Namespace) -> tuple[dict[str, Any], int]:
        clock["now"] = stage_completed_at
        return collection, collection_exit

    universe_evaluated_at: list[datetime | None] = []

    def active_status(
        _store: _UniverseStore,
        city: str,
        **kwargs: object,
    ) -> dict[str, object]:
        universe_evaluated_at.append(kwargs.get("now"))  # type: ignore[arg-type]
        return {
            "city": city,
            "status": "fresh",
            "usable": True,
            "active": True,
        }

    monkeypatch.setattr(grocery_cli, "datetime", ManagedRefreshClock)
    monkeypatch.setattr(grocery_cli, "_run_collect_all", collect)
    monkeypatch.setattr(grocery_cli, "_active_universe_status", active_status)

    assert await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"])) == 0

    report = emitted[0]
    own = report["own_collection"]["results"][0]  # type: ignore[index]
    assert report["started_at"] == run_started_at
    assert report["completed_at"] == stage_completed_at
    assert own["freshness"] == "fresh"
    assert own["snapshot_age_hours"] == pytest.approx(0.25)
    assert own["retry_required"] is False
    external = report["external_provider"][0]  # type: ignore[index]
    assert external["stale_at"] == stage_completed_at + timedelta(hours=47)
    assert universe_evaluated_at == [stage_completed_at]
    assert (
        assess_freshness(
            stage_completed_at + timedelta(minutes=61),
            now=stage_completed_at,
        ).state.value
        == "broken"
    )


@pytest.mark.asyncio
async def test_managed_refresh_accepts_only_live_parent_lock_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _UniverseStore()
    builds: list[str] = []
    _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=_collection(["Lund"]),
        build_calls=builds,
    )
    args = _args(tmp_path, ["Lund"])
    database = tmp_path / "db"
    parent = RefreshRunLock(
        production_refresh_lock_path(database, args.price_universe_cache_root)
    )
    info = parent.acquire()
    monkeypatch.setenv(REFRESH_PARENT_LOCK_NONCE_ENV, info.owner_nonce)
    monkeypatch.setattr(grocery_cli.os, "getppid", os.getpid)
    try:
        assert await grocery_cli._daily_refresh(args) == 0
    finally:
        parent.release()
    assert builds == ["Lund"]


@pytest.mark.asyncio
async def test_managed_refresh_rejects_replayed_parent_lock_nonce(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=_UniverseStore(),
        collection=_collection(["Lund"]),
        build_calls=[],
    )
    monkeypatch.setenv(REFRESH_PARENT_LOCK_NONCE_ENV, "replayed-or-forged")

    with pytest.raises(RuntimeError, match="invalid internal parent refresh-lock handoff"):
        await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"]))


@pytest.mark.asyncio
async def test_partial_connector_failure_uses_lkg_and_returns_degraded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _UniverseStore()
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=_collection(["Lund"], failed=True),
        build_calls=[],
    )

    exit_code = await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"]))

    assert exit_code == 2
    [failed] = [
        row
        for row in emitted[0]["own_collection"]["results"]  # type: ignore[index]
        if row["status"] == "failed"
    ]
    assert failed["lkg_used"] is True
    assert emitted[0]["price_universes"][0]["usable"] is True  # type: ignore[index]


@pytest.mark.asyncio
async def test_non_promoted_fresh_active_snapshot_is_reported_as_lkg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    collection, _collection_exit = _collection(["Lund"])
    healthy = collection["results"][0]
    healthy["active_snapshot_id"] = "snapshot-lund"
    collection["results"].extend(
        [
            {
                "chain": "hemkop",
                "city": "Lund",
                "roles": ("basket",),
                "status": "degraded",
                "promoted": False,
                "active_snapshot_id": "snapshot-degraded-lkg",
                "active_snapshot_age_hours": 2.0,
            },
            {
                "chain": "ica",
                "city": "Lund",
                "roles": ("basket",),
                "status": "degraded",
                "promoted": False,
                "active_snapshot_id": "snapshot-stale-lkg",
                "active_snapshot_age_hours": 48.0,
            },
        ]
    )
    store = _UniverseStore()
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=(collection, 2),
        build_calls=[],
    )

    assert await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"])) == 2

    rows = emitted[0]["own_collection"]["results"]  # type: ignore[index]
    assert [row["lkg_used"] for row in rows] == [False, True, False]
    assert rows[1]["freshness"] == "fresh"
    assert rows[2]["freshness"] == "stale"
    assert emitted[0]["summary"]["lkg_contexts"] == 1  # type: ignore[index]
    assert store.activations == [
        (
            "Lund",
            ("primat-lund", "snapshot-degraded-lkg", "snapshot-lund"),
        )
    ]


@pytest.mark.asyncio
async def test_ineligible_exact_context_skips_external_and_universe_work(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old = b'{"universe_id":"unchanged-active"}'
    store = _UniverseStore(initial={"lund": old})
    builds: list[str] = []
    collection = (
        {
            "run_type": "daily_own_collection",
            "cities": ["Lund"],
            "results": [
                {
                    "chain": "hemkop",
                    "city": "Lund",
                    "context_store_id": "4123",
                    "roles": ("basket", "offers"),
                    "status": "skipped",
                    "reason": (
                        "REVIEW source requires "
                        "HEMKOP_ALLOW_FULL_CRAWL=true"
                    ),
                }
            ],
            "summary": {"targets": 0, "skipped": 1},
        },
        2,
    )
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=collection,
        build_calls=builds,
    )

    async def forbidden_external(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("blocked exact target refreshed Primat")

    monkeypatch.setattr(
        grocery_cli,
        "_collect_production_primat_cache",
        forbidden_external,
    )
    args = _args(tmp_path, ["Lund"])
    args.chain = ["hemkop"]
    args.context_store_id = "4123"

    exit_code = await grocery_cli._daily_refresh(args)

    assert exit_code == 2
    assert builds == []
    assert store.active_manifest_bytes("Lund") == old
    assert store.activations == []
    [external] = emitted[0]["external_provider"]  # type: ignore[index]
    assert external["status"] == "not_run"
    assert external["provider_requests"] == 0
    [universe] = emitted[0]["price_universes"]  # type: ignore[index]
    assert universe["active_unchanged"] is True
    assert universe["build_skipped_reason"] == (
        "requested_own_context_not_eligible"
    )
    assert emitted[0]["summary"]["universe_builds"] == 0  # type: ignore[index]


@pytest.mark.asyncio
async def test_no_external_refresh_reuses_fresh_active_cache_explicitly(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _UniverseStore()
    builds: list[str] = []
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=_collection(["Lund"]),
        build_calls=builds,
    )
    external_store = _ExternalStore()
    prior = tmp_path / "primat-active.json"
    prior.write_text('{"cache":"fresh-active"}', encoding="utf-8")
    external_store.activate(prior, city="Lund")
    monkeypatch.setattr(
        grocery_cli,
        "ClosedProviderCacheArtifactStore",
        lambda _root: external_store,
    )

    async def forbidden_external(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("--no-external-refresh called Primat")

    monkeypatch.setattr(
        grocery_cli,
        "_collect_production_primat_cache",
        forbidden_external,
    )
    args = _args(tmp_path, ["Lund"])
    args.no_external_refresh = True

    exit_code = await grocery_cli._daily_refresh(args)

    assert exit_code == 0
    assert builds == ["Lund"]
    [external] = emitted[0]["external_provider"]  # type: ignore[index]
    assert external["status"] == "active_cache_reused"
    assert external["provider_requests"] == 0
    assert external["lkg_used"] is False


@pytest.mark.asyncio
async def test_build_failure_keeps_previous_active_manifest_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old = b'{"universe_id":"old-active"}'
    store = _UniverseStore(initial={"lund": old})
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=_collection(["Lund"]),
        build_calls=[],
        build_failure_city="Lund",
    )

    exit_code = await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"]))

    assert exit_code == 2
    assert store.active_manifest_bytes("Lund") == old
    assert store.activations == []
    universe = emitted[0]["price_universes"][0]  # type: ignore[index]
    assert universe["active_unchanged"] is True
    assert universe["build_error"] == "RuntimeError"
    assert "must-never-appear" not in json.dumps(emitted, default=str)


@pytest.mark.asyncio
async def test_missing_required_primat_contexts_never_publish_own_only_universe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    old = b'{"universe_id":"federated-lkg"}'
    store = _UniverseStore(initial={"lund": old})
    builds: list[str] = []
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=_collection(["Lund"]),
        build_calls=builds,
    )

    async def no_verified_contexts(**_kwargs: object) -> dict[str, object]:
        return {
            "status": "skipped",
            "reason_code": "no_verified_primat_primary_contexts",
            "transport": {"requests": 0},
            "contexts": [],
        }

    monkeypatch.setattr(
        grocery_cli,
        "_collect_production_primat_cache",
        no_verified_contexts,
    )

    exit_code = await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"]))

    assert exit_code == 2
    assert builds == []
    assert store.activations == []
    assert store.active_manifest_bytes("Lund") == old
    universe = emitted[0]["price_universes"][0]  # type: ignore[index]
    assert universe["build_error"] == "required_external_cache_unavailable"
    assert universe["active_unchanged"] is True


@pytest.mark.asyncio
async def test_stale_explicit_candidate_cannot_replace_fresh_active_lkg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = datetime.now(tz=UTC)
    store = PreparedUniverseArtifactStore(tmp_path / "managed-universe")
    fresh = tmp_path / "fresh.json"
    fresh.write_text('{"candidate":"fresh"}', encoding="utf-8")

    def fresh_metadata(_payload: object, city: str) -> PreparedUniverseArtifactMetadata:
        return PreparedUniverseArtifactMetadata(
            city=city,
            scope_id=f"city:{city}",
            universe_id="fresh-lkg",
            built_at=now,
            snapshot_ids=("old-snapshot",),
            product_count=100,
            canonical_index_count=20,
            oldest_observed_at=now - timedelta(hours=1),
        )

    store.activate(fresh, city="Lund", validator=fresh_metadata, activated_at=now)
    before = store.active_manifest_bytes("Lund")
    stale = tmp_path / "stale.json"
    stale.write_text('{"candidate":"stale"}', encoding="utf-8")
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,  # type: ignore[arg-type]
        collection=_collection(["Lund"]),
        build_calls=[],
    )

    def stale_metadata(_payload: object, city: str) -> PreparedUniverseArtifactMetadata:
        return PreparedUniverseArtifactMetadata(
            city=city,
            scope_id=f"city:{city}",
            universe_id="stale-candidate",
            built_at=now,
            snapshot_ids=("primat-lund", "snapshot-lund"),
            product_count=100,
            canonical_index_count=20,
            oldest_observed_at=now - timedelta(hours=72),
        )

    def active_status(
        active_store: PreparedUniverseArtifactStore,
        city: str,
        *,
        policy: object,
        **_kwargs: object,
    ) -> dict[str, object]:
        manifest = active_store.read_active(city)
        assert manifest is not None
        freshness = assess_freshness(manifest.oldest_observed_at, policy=policy)  # type: ignore[arg-type]
        return {
            "city": city,
            "status": freshness.state.value,
            "usable": freshness.usable,
            "active": True,
            "universe_id": manifest.universe_id,
        }

    monkeypatch.setattr(
        grocery_cli,
        "validate_backend_prepared_universe_artifact",
        stale_metadata,
    )
    monkeypatch.setattr(grocery_cli, "_active_universe_status", active_status)
    args = _args(tmp_path, ["Lund"])
    args.price_universe_candidate = stale

    exit_code = await grocery_cli._daily_refresh(args)

    assert exit_code == 2
    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund").universe_id == "fresh-lkg"  # type: ignore[union-attr]
    universe = emitted[0]["price_universes"][0]  # type: ignore[index]
    assert universe["active_unchanged"] is True


@pytest.mark.asyncio
async def test_relevant_skipped_basket_context_with_lkg_is_degraded(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    collection, _exit = _collection(["Lund"])
    collection["results"].append(  # type: ignore[union-attr]
        {
            "chain": "hemkop",
            "city": "Lund",
            "roles": ("basket",),
            "status": "skipped",
            "reason": "requested context is not an approved exact refresh target",
            "active_snapshot_id": "hemkop-lkg",
            "active_snapshot_age_hours": 2.0,
            "promoted": False,
        }
    )
    store = _UniverseStore()
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=(collection, 0),
        build_calls=[],
    )

    exit_code = await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"]))

    assert exit_code == 2
    skipped = emitted[0]["own_collection"]["results"][-1]  # type: ignore[index]
    assert skipped["lkg_used"] is True
    assert emitted[0]["summary"]["status"] == "degraded"  # type: ignore[index]


@pytest.mark.asyncio
async def test_verified_no_context_is_not_an_operational_degradation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    collection, collection_exit = _collection(["Lund"])
    collection["results"].append(  # type: ignore[union-attr]
        {
            "chain": "citygross",
            "city": "Lund",
            "roles": ("basket",),
            "status": "not_applicable",
            "reason": "no verified OWN source context for this geography",
        }
    )
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=_UniverseStore(),
        collection=(collection, collection_exit),
        build_calls=[],
    )

    exit_code = await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"]))

    assert exit_code == 0
    assert emitted[0]["summary"]["status"] == "complete"  # type: ignore[index]


@pytest.mark.asyncio
async def test_external_manifest_rolls_back_when_db_link_activation_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    universe_store = _UniverseStore()
    emitted = _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=universe_store,
        collection=_collection(["Lund"]),
        build_calls=[],
    )
    external_store = _ExternalStore()
    prior = tmp_path / "primat-prior.json"
    prior.write_text('{"cache":"prior"}', encoding="utf-8")
    external_store.activate(prior, city="Lund")
    prior_manifest = external_store.active_manifest_bytes("Lund")
    monkeypatch.setattr(
        grocery_cli,
        "ClosedProviderCacheArtifactStore",
        lambda _root: external_store,
    )

    def activate_links(_settings: object, path: Path) -> dict[str, object]:
        if path != prior:
            raise RuntimeError("simulated DB activation failure")
        return {"status": "activated", "activated": 1, "rejected": 0}

    monkeypatch.setattr(grocery_cli, "_activate_external_context_links", activate_links)

    exit_code = await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"]))

    assert exit_code == 2
    assert external_store.active_manifest_bytes("Lund") == prior_manifest
    assert external_store.active["lund"] == prior
    assert emitted[0]["external_provider"][0]["status"] == "lkg_retained"  # type: ignore[index]


@pytest.mark.asyncio
async def test_managed_refresh_refuses_second_live_lock_without_collecting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        grocery_cli.GroceryDataSettings,
        "from_env",
        staticmethod(lambda: _settings(tmp_path)),
    )
    database = tmp_path / "refresh.sqlite"
    database.touch()
    monkeypatch.setattr(grocery_cli, "_sqlite_database_path", lambda _settings: database)
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(
        grocery_cli,
        "_emit_refresh_result",
        lambda report, **_kwargs: emitted.append(report),
    )

    async def forbidden(_args: Namespace) -> object:
        raise AssertionError("locked refresh performed collection")

    monkeypatch.setattr(grocery_cli, "_run_collect_all", forbidden)
    args = _args(tmp_path, ["Lund"])
    lock = RefreshRunLock(
        production_refresh_lock_path(database, args.price_universe_cache_root)
    )
    lock.acquire()
    try:
        exit_code = await grocery_cli._daily_refresh(args)
    finally:
        lock.release()

    assert exit_code == 1
    assert emitted[0]["summary"]["status"] == "refresh_already_running"  # type: ignore[index]


@pytest.mark.asyncio
async def test_managed_refresh_lock_returns_degraded_when_active_lkg_is_usable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        grocery_cli.GroceryDataSettings,
        "from_env",
        staticmethod(lambda: _settings(tmp_path)),
    )
    database = tmp_path / "refresh.sqlite"
    database.touch()
    monkeypatch.setattr(grocery_cli, "_sqlite_database_path", lambda _settings: database)
    monkeypatch.setattr(
        grocery_cli,
        "_daily_refresh_lkg_status",
        lambda _settings, _root, cities: (
            True,
            [{"city": cities[0], "status": "fresh", "usable": True}],
        ),
    )
    emitted: list[dict[str, object]] = []
    monkeypatch.setattr(
        grocery_cli,
        "_emit_refresh_result",
        lambda report, **_kwargs: emitted.append(report),
    )
    args = _args(tmp_path, ["Lund"])
    lock = RefreshRunLock(
        production_refresh_lock_path(database, args.price_universe_cache_root)
    )
    lock.acquire()
    try:
        exit_code = await grocery_cli._daily_refresh(args)
    finally:
        lock.release()

    assert exit_code == 2
    assert emitted[0]["price_universes"][0]["usable"] is True  # type: ignore[index]


def test_active_universe_runtime_incompatibility_is_not_usable_lkg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    now = datetime.now(tz=UTC)
    manifest = SimpleNamespace(
        universe_id="incompatible-universe",
        built_at=now,
        activated_at=now,
        oldest_observed_at=now,
        snapshot_ids=("snapshot-1",),
        product_count=1,
        canonical_index_count=1,
        artifact_file="incompatible.json",
        artifact_bytes=2,
    )

    class IncompatibleStore:
        def read_active(self, city: str) -> object:
            assert city == "Lund"
            return manifest

        def resolve_active_artifact(self, city: str) -> Path:
            assert city == "Lund"
            return tmp_path / "incompatible.json"

    monkeypatch.setattr(
        grocery_cli,
        "_smoke_load_prepared_universe",
        lambda _artifact, _universe_id: (_ for _ in ()).throw(
            ValueError("unsupported artifact schema")
        ),
    )

    status = grocery_cli._active_universe_status(
        IncompatibleStore(),  # type: ignore[arg-type]
        "Lund",
        policy=FreshnessPolicy(warning_age_hours=36.0, stale_age_hours=48.0),
        smoke_load=True,
    )

    assert status["status"] == "broken"
    assert status["usable"] is False


def test_lkg_exit_check_requires_authoritative_runtime_load(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    smoke_flags: list[bool] = []
    monkeypatch.setattr(
        grocery_cli,
        "PreparedUniverseArtifactStore",
        lambda _root: object(),
    )

    def active_status(
        _store: object,
        city: str,
        *,
        policy: FreshnessPolicy,
        smoke_load: bool,
    ) -> dict[str, object]:
        del policy
        assert city == "Lund"
        smoke_flags.append(smoke_load)
        return {"city": city, "status": "broken", "usable": False}

    monkeypatch.setattr(grocery_cli, "_active_universe_status", active_status)

    usable, states = grocery_cli._daily_refresh_lkg_status(
        _settings(tmp_path),
        tmp_path / "universe-cache",
        ("Lund",),
    )

    assert usable is False
    assert states[0]["status"] == "broken"
    assert smoke_flags == [True]


@pytest.mark.asyncio
async def test_managed_report_json_redacts_collection_secrets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    collection, collection_exit = _collection(["Lund"])
    collection["results"][0]["authorization"] = "Bearer report-secret"  # type: ignore[index]
    store = _UniverseStore()
    _patch_managed_runtime(
        monkeypatch,
        tmp_path,
        store=store,
        collection=(collection, collection_exit),
        build_calls=[],
    )

    assert await grocery_cli._daily_refresh(_args(tmp_path, ["Lund"])) == 0

    [report_path] = (tmp_path / "reports").glob("refresh-report-*.json")
    encoded = report_path.read_text(encoding="utf-8")
    assert "report-secret" not in encoded
    assert json.loads(encoded)["own_collection"]["results"][0]["authorization"] == "[REDACTED]"


def test_status_reads_active_universe_without_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output: list[dict[str, object]] = []
    monkeypatch.setattr(
        grocery_cli.GroceryDataSettings,
        "from_env",
        staticmethod(lambda: _settings(tmp_path)),
    )
    monkeypatch.setattr(grocery_cli, "PreparedUniverseArtifactStore", lambda _root: object())
    monkeypatch.setattr(grocery_cli, "ClosedProviderCacheArtifactStore", lambda _root: _ExternalStore())
    monkeypatch.setattr(grocery_cli, "create_database_engine", lambda _url: _Engine())
    monkeypatch.setattr(grocery_cli, "create_session_factory", lambda _engine: object())

    @contextmanager
    def fake_session_scope(_factory: object):
        yield object()

    class Audit:
        def model_dump(self, *, mode: str) -> dict[str, int]:
            assert mode == "json"
            return {"basket_capable": 4, "stale": 0, "mapping_unresolved": 0}

    class Auditor:
        def __init__(self, _session: object, *, max_price_age_hours: float) -> None:
            assert max_price_age_hours == 48.0

        def audit(self, city: str) -> Audit:
            assert city == "Lund"
            return Audit()

    monkeypatch.setattr(grocery_cli, "session_scope", fake_session_scope)
    monkeypatch.setattr(grocery_cli, "PriceContextAuditor", Auditor)
    monkeypatch.setattr(
        grocery_cli,
        "_active_universe_status",
        lambda _store, city, **_kwargs: {
            "city": city,
            "status": "fresh",
            "usable": True,
            "active": True,
            "universe_id": "universe-active",
            "oldest_price_age_hours": 2.0,
        },
    )
    monkeypatch.setattr(grocery_cli, "_json", output.append)

    exit_code = grocery_cli._refresh_status(
        Namespace(city=["Lund"], postal_code=None, format="json")
    )

    assert exit_code == 0
    assert output[0]["status"] == "fresh"
    assert output[0]["cities"][0]["price_universe"]["universe_id"] == "universe-active"  # type: ignore[index]
    assert output[0]["live_provider_requests"] == 0
