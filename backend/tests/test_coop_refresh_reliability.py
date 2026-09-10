from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from deploy.scripts import run_daily_refresh
from deploy.scripts.run_source_retry import (
    build_source_retry_command,
    full_runner_failed_after_report,
    retry_needed,
)
from deploy.scripts.start_cron import (
    _coop_preflight_event,
    _validate_display_schedule,
)
from grocery_data.app.services.coop_refresh_configuration import (
    CoopRefreshConfigurationError,
    assess_coop_refresh_configuration,
    require_coop_refresh_configuration,
)
from grocery_data.app.services.freshness import (
    FreshnessPolicy,
    FreshnessState,
    next_scheduled_refresh,
    project_source_freshness,
)

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 2, 3, 20, tzinfo=UTC)
POLICY = FreshnessPolicy(warning_age_hours=36, stale_age_hours=48)


def test_production_configuration_narrowly_enables_only_coop_730400() -> None:
    template = (ROOT / "deploy/.env.production.example").read_text(encoding="utf-8")
    compose = (ROOT / "deploy/compose.yaml").read_text(encoding="utf-8")

    assert "COOP_ALLOW_FULL_CRAWL=true" in template
    assert "COOP_ONLINE_CONTEXT_IDS=730400" in template
    assert "COOP_ALLOW_FULL_CRAWL:-false" not in compose
    assert "COOP_ONLINE_CONTEXT_IDS:-" not in compose
    assert "set COOP_ALLOW_FULL_CRAWL=true" in compose
    assert "set COOP_ONLINE_CONTEXT_IDS=730400" in compose
    assert "COOP_RETRY_CRON=17 06 * * *" in template
    assert "run_source_retry.py" in (
        ROOT / "deploy/scripts/start_cron.py"
    ).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("environment", "code"),
    [
        ({"COOP_ALLOW_FULL_CRAWL": "false", "COOP_ONLINE_CONTEXT_IDS": "730400"},
         "coop_full_catalog_disabled"),
        ({"COOP_ALLOW_FULL_CRAWL": "true", "COOP_ONLINE_CONTEXT_IDS": ""},
         "coop_online_context_not_allowlisted"),
        ({"COOP_ALLOW_FULL_CRAWL": "true", "COOP_ONLINE_CONTEXT_IDS": "730400,999"},
         "coop_online_context_allowlist_too_broad"),
    ],
)
def test_coop_scheduler_configuration_fails_closed(
    environment: dict[str, str],
    code: str,
) -> None:
    result = assess_coop_refresh_configuration(environment)

    assert result.valid is False
    assert result.diagnostic_code == code
    with pytest.raises(CoopRefreshConfigurationError, match=code):
        require_coop_refresh_configuration(environment)


def test_bad_coop_config_is_visible_without_disabling_whole_scheduler() -> None:
    event = _coop_preflight_event(
        {
            "COOP_ALLOW_FULL_CRAWL": "false",
            "COOP_ONLINE_CONTEXT_IDS": "730400",
        }
    )

    assert event is not None
    assert {
        key: event[key]
        for key in (
            "event",
            "severity",
            "valid",
            "diagnostic_code",
            "operator_opt_in",
            "configured_context_ids",
            "required_context_id",
            "scope",
            "price_semantics",
        )
    } == {
        "event": "scheduler_configuration_warning",
        "severity": "error",
        "valid": False,
        "diagnostic_code": "coop_full_catalog_disabled",
        "operator_opt_in": False,
        "configured_context_ids": ["730400"],
        "required_context_id": "730400",
        "scope": "online_fulfillment",
        "price_semantics": "online_price",
    }


def test_source_freshness_projects_expiry_before_next_normal_refresh() -> None:
    next_refresh = next_scheduled_refresh(
        "03:17 Europe/Stockholm",
        now=NOW,
    )
    projection = project_source_freshness(
        NOW - timedelta(hours=37),
        now=NOW,
        policy=POLICY,
        next_expected_source_refresh=next_refresh,
        basket_critical=True,
        refresh_successful=False,
    )

    assert projection.freshness.state is FreshnessState.AGING
    assert projection.freshness.hours_until_stale == pytest.approx(11)
    assert projection.source_will_expire_before_next_refresh is True
    assert projection.retry_required is True


def test_fresh_source_is_operationally_aging_if_it_expires_before_next_run() -> None:
    projection = project_source_freshness(
        NOW - timedelta(hours=30),
        now=NOW,
        policy=POLICY,
        next_expected_source_refresh=NOW + timedelta(hours=24),
        basket_critical=True,
        refresh_successful=True,
    )

    assert projection.freshness.state is FreshnessState.AGING
    assert projection.freshness.usable is True
    assert projection.freshness.age_hours == pytest.approx(30)
    assert projection.freshness.hours_until_stale == pytest.approx(18)
    assert projection.source_will_expire_before_next_refresh is True
    assert projection.retry_required is True


def test_fresh_source_does_not_require_recovery_retry() -> None:
    projection = project_source_freshness(
        NOW - timedelta(hours=1),
        now=NOW,
        policy=POLICY,
        next_expected_source_refresh=NOW + timedelta(hours=20),
        basket_critical=True,
        refresh_successful=True,
    )

    assert projection.freshness.state is FreshnessState.FRESH
    assert projection.source_will_expire_before_next_refresh is False
    assert projection.retry_required is False


def test_source_retry_command_is_exact_coop_online_and_reuses_external_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFRESH_CITY", "Lund")
    monkeypatch.setenv("REFRESH_POSTAL_CODE", "22350")
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", "/srv/price-universes")

    command = build_source_retry_command()

    assert command[1:4] == ["-m", "grocery_data", "daily-refresh"]
    assert command[command.index("--chain") + 1] == "coop"
    assert command[command.index("--context-store-id") + 1] == "730400"
    assert "--no-external-refresh" in command
    assert "offers" not in command


def test_bounded_retry_runs_only_after_failed_or_aging_full_catalog() -> None:
    healthy = {
        "run_type": "daily_refresh",
        "own_collection": {
            "results": [
                {
                    "chain": "coop",
                    "context_store_id": "730400",
                    "roles": ["basket"],
                    "status": "healthy",
                    "promoted": True,
                    "freshness": "fresh",
                    "retry_required": False,
                    "active_snapshot_observed_at": NOW.isoformat(),
                }
            ]
        },
    }
    failed = json.loads(json.dumps(healthy))
    failed["own_collection"]["results"][0].update(  # type: ignore[index]
        {"status": "failed", "promoted": False, "retry_required": True}
    )

    assert retry_needed(healthy, now=NOW) == (False, "coop_full_catalog_fresh")
    assert retry_needed(failed, now=NOW)[0] is True
    assert retry_needed(None, now=NOW) == (
        True,
        "coop_full_catalog_status_missing",
    )


def test_candidate_validation_failure_schedules_one_recovery_rebuild() -> None:
    report = {
        "summary": {"status": "degraded", "exit_code": 2},
        "own_collection": {
            "results": [
                {
                    "chain": "coop",
                    "context_store_id": "730400",
                    "roles": ["basket"],
                    "status": "healthy",
                    "promoted": True,
                    "active_snapshot_observed_at": NOW.isoformat(),
                }
            ]
        },
        "price_universes": [
            {
                "build_error": "PreparedArtifactValidationError",
                "active_unchanged": True,
                "usable": True,
            }
        ],
    }

    assert retry_needed(report, now=NOW) == (
        True,
        "price_universe_rebuild_required",
    )


def test_old_report_fresh_flag_cannot_suppress_aging_recovery() -> None:
    report = {
        "run_type": "daily_refresh",
        "completed_at": NOW.isoformat(),
        "own_collection": {
            "results": [
                {
                    "chain": "coop",
                    "context_store_id": "730400",
                    "roles": ["basket"],
                    "status": "healthy",
                    "promoted": True,
                    "freshness": "fresh",
                    "retry_required": False,
                    "active_snapshot_observed_at": NOW.isoformat(),
                }
            ]
        },
    }

    assert retry_needed(report, now=NOW + timedelta(hours=37)) == (
        True,
        "coop_full_catalog_aging",
    )


def test_aborted_full_runner_after_old_report_forces_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    report = {"completed_at": NOW.isoformat()}
    status = tmp_path / "runner.json"
    status.write_text(
        json.dumps(
            {
                "schema_version": "production-refresh-runner-v1",
                "started_at": (NOW + timedelta(hours=24)).isoformat(),
                "exit_code": 1,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("REFRESH_RUNNER_STATUS_PATH", str(status))

    assert full_runner_failed_after_report(report) is True


def test_display_schedule_must_match_actual_cron() -> None:
    _validate_display_schedule(
        "17 03 * * *",
        "03:17 Europe/Stockholm",
        name="DAILY_REFRESH_SCHEDULE",
    )
    with pytest.raises(ValueError, match="must match"):
        _validate_display_schedule(
            "17 04 * * *",
            "03:17 Europe/Stockholm",
            name="DAILY_REFRESH_SCHEDULE",
        )


def test_bad_coop_config_does_not_preempt_managed_lkg_classification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Lock:
        def acquire(self) -> None:
            pass

        def release(self) -> None:
            pass

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("COOP_ALLOW_FULL_CRAWL", "false")
    monkeypatch.setenv("COOP_ONLINE_CONTEXT_IDS", "730400")
    monkeypatch.setattr(run_daily_refresh, "_operations_lock", Lock)
    monkeypatch.setattr(run_daily_refresh, "_run_locked", lambda *args, **kwargs: 2)

    assert run_daily_refresh.main() == 2


def test_executed_source_retry_writes_retry_schema_and_top_level_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Lock:
        info = type("Info", (), {"owner_nonce": "nonce"})()

    class Store:
        def active_manifest_bytes(self, city: str) -> None:
            return None

    captured: list[dict[str, object]] = []
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", str(ROOT / "price_universes"))
    monkeypatch.setattr(run_daily_refresh, "_artifact_store", Store)
    monkeypatch.setattr(
        run_daily_refresh.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0})(),
    )
    monkeypatch.setattr(
        run_daily_refresh,
        "_reload_runtime",
        lambda: {"status": "complete"},
    )

    result = run_daily_refresh._run_locked(
        Lock(),  # type: ignore[arg-type]
        started_at=NOW,
        command=["python", "worker", "--city", "Lund"],
        run_kind="coop_source_retry",
        status_writer=captured.append,
    )

    assert result == 0
    assert captured[0]["schema_version"] == "source-retry-runner-v1"
    assert captured[0]["run_kind"] == "coop_source_retry"
    assert captured[0]["status"] == "complete"
    with pytest.raises(ValueError, match="fixed daily"):
        _validate_display_schedule(
            "17 03 * * 1",
            "03:17 Europe/Stockholm",
            name="DAILY_REFRESH_SCHEDULE",
        )
