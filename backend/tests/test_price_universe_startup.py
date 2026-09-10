from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import app.main as main_module
import pytest
from app.config import Settings


class _Manager:
    def __init__(self) -> None:
        self.loaded: list[Path] = []

    def load_file_and_activate(self, path: Path) -> object:
        self.loaded.append(path)
        return object()


def test_startup_skips_artifact_resolution_in_compatibility_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _Manager()

    class UnexpectedStore:
        def __init__(self, _root: Path) -> None:
            raise AssertionError("compatibility startup must not touch artifact storage")

    monkeypatch.setattr(
        "grocery_data.app.services.prepared_universe_activation.PreparedUniverseArtifactStore",
        UnexpectedStore,
    )

    result = main_module.load_configured_price_universe(
        Settings(price_universe_required=False),
        manager=manager,  # type: ignore[arg-type]
    )

    assert result is None
    assert manager.loaded == []


def test_strict_startup_resolves_hash_verified_active_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "prepared.json"
    artifact.touch()
    manager = _Manager()
    calls: list[tuple[Path, str]] = []

    class Store:
        def __init__(self, root: Path) -> None:
            self.root = root

        def resolve_active_artifact(self, city: str) -> Path:
            calls.append((self.root, city))
            return artifact

    monkeypatch.setattr(
        "grocery_data.app.services.prepared_universe_activation.PreparedUniverseArtifactStore",
        Store,
    )

    result = main_module.load_configured_price_universe(
        Settings(
            price_universe_required=True,
            price_universe_cache_root=tmp_path / "cache",
            price_universe_city="Lund",
        ),
        manager=manager,  # type: ignore[arg-type]
    )

    assert result is not None
    assert calls == [((tmp_path / "cache"), "Lund")]
    assert manager.loaded == [artifact]


def test_strict_startup_fails_closed_when_no_active_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class EmptyStore:
        def __init__(self, _root: Path) -> None:
            pass

        def resolve_active_artifact(self, _city: str) -> None:
            return None

    monkeypatch.setattr(
        "grocery_data.app.services.prepared_universe_activation.PreparedUniverseArtifactStore",
        EmptyStore,
    )

    with pytest.raises(RuntimeError, match="required active PriceUniverse"):
        main_module.load_configured_price_universe(
            Settings(
                price_universe_required=True,
                price_universe_cache_root=tmp_path,
            ),
            manager=_Manager(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_lifespan_loads_before_optional_process_local_prewarm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    settings = Settings(price_universe_prewarm_enabled=False)

    def load(received: Settings) -> object:
        assert received is settings
        events.append("load")
        return object()

    async def prewarm(received: Settings) -> object:
        assert received is settings
        events.append("prewarm")
        return SimpleNamespace(status="disabled")

    def pricing_projection(received: Settings, prepared: object) -> object:
        assert received is settings
        assert prepared is loaded
        events.append("pricing_projection")
        return SimpleNamespace(status="miss_filled")

    loaded = object()

    monkeypatch.setattr(main_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        main_module,
        "load_configured_price_universe",
        lambda received: (load(received), loaded)[1],
    )
    monkeypatch.setattr(main_module, "precompute_pricing_semantics", pricing_projection)
    monkeypatch.setattr(main_module, "prewarm_active_price_universe", prewarm)
    application = SimpleNamespace(state=SimpleNamespace())

    async with main_module.lifespan(application):  # type: ignore[arg-type]
        assert events == ["load", "pricing_projection", "prewarm"]
        assert application.state.pricing_projection_prewarm.status == "miss_filled"
        assert application.state.plan_prewarm.status == "disabled"
