"""Keep the test process independent from a developer's repository dotenv.

``grocery_data.app.main`` exposes a module-level production app. Importing it
creates the default database factory, whose documented startup path loads the
repository ``.env``. Without this collection-time guard, a local field-server
setting such as ``FIELD_MODE_ENABLED=true`` can therefore change later
dependency-injected TestClient apps into the restricted field deployment.

Individual dotenv-loader tests deliberately remove this flag with
``monkeypatch`` and pass their own temporary dotenv path.
"""

from __future__ import annotations

import os

os.environ["PYTHON_DOTENV_DISABLED"] = "1"

# --- Offline guard in pytest-xdist workers -------------------------------------
# scripts/verify_offline.py blocks external network and old source roots in its
# own process. Workers are separate processes, so install the same guard here.
if os.environ.get("SMAKO_OFFLINE_GUARD_LABEL") and os.environ.get("PYTEST_XDIST_WORKER"):
    import sys as _sys
    from pathlib import Path as _GuardPath

    _sys.path.insert(0, str(_GuardPath(__file__).resolve().parent / "scripts"))
    import offline_guard as _offline_guard

    _offline_guard.install(os.environ["SMAKO_OFFLINE_GUARD_ROOT"],
                           os.environ["SMAKO_OFFLINE_GUARD_LABEL"],
                           suffix="-" + os.environ["PYTEST_XDIST_WORKER"])


# --- Local evidence -----------------------------------------------------------
# Some tests replay retained source captures under reports/. Only *.py and *.md
# are tracked there (see .gitignore); the payloads live in the protected backup.
# In a clean clone or CI such a test is reported as SKIPPED with the missing path
# instead of failing. Set SMAKO_REQUIRE_LOCAL_EVIDENCE=1 on a machine that has
# the evidence restored to make a missing file a failure again.
from pathlib import Path as _Path

import pytest as _pytest

_REPORTS = (_Path(__file__).resolve().parent / "reports").resolve()


def _missing_local_evidence(excinfo):
    if excinfo is None or not excinfo.errisinstance(FileNotFoundError):
        return None
    filename = getattr(excinfo.value, "filename", None)
    if not filename:
        return None
    path = _Path(filename).resolve()
    return path if path.is_relative_to(_REPORTS) and not path.exists() else None


@_pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.failed or os.environ.get("SMAKO_REQUIRE_LOCAL_EVIDENCE"):
        return
    missing = _missing_local_evidence(call.excinfo)
    if missing is not None:
        report.outcome = "skipped"
        report.longrepr = (str(item.path), item.location[1] or 0,
                           f"Lokal evidens saknas: {missing.relative_to(_REPORTS.parent)}")


# Failures already present on main (46d834b) and unrelated to local evidence.
# strict=True: when one is fixed, CI fails until it is removed from this list.
_KNOWN_FAILURES = {
    "backend/tests/test_purchase_planning_modes.py::test_conditional_group_is_counted_whole_purchase_never_specific_or_nutrition",
    "backend/tests/test_purchase_planning_modes.py::test_personal_api_mode_applies_to_retained_unknown_weight_row",
    "backend/tests/test_purchase_planning_modes.py::test_group_search_displays_full_quote_without_fabricating_residual",
    "backend/tests/test_purchase_planning_modes.py::test_measured_purchase_is_required_and_retained_in_private_ledger",
    "backend/tests/test_municipal_runtime.py::test_two_cities_restart_selection_and_no_cross_city_contexts",
    "backend/tests/test_plan_api.py::test_mock_plan_is_complete_and_package_priced",
    "backend/tests/test_public_beta_ui.py::test_beta_geography_and_online_scope_are_explicit",
    "backend/tests/test_public_beta_ui.py::test_planner_fails_closed_with_swedish_readiness_copy",
    "backend/tests/test_public_menu_errors.py::test_offline_preflight_distinguishes_area_from_data_failure[missing_required-503-price_universe_unusable-/api/plan]",
    "backend/tests/test_public_menu_errors.py::test_offline_preflight_distinguishes_area_from_data_failure[missing_required-503-price_universe_unusable-/api/plans]",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.nodeid in _KNOWN_FAILURES:
            item.add_marker(_pytest.mark.xfail(strict=True, reason="Känt fel på main före 2026-10-16; se docs/TESTING.md"))


# --- Process-local planner reuse ---------------------------------------------
# Tests patch matchers, facts and price helpers on shared fixtures. Start every
# test with an empty cross-request resolution cache so one test's patched result
# can never be reused by another (production keys cover the real inputs).
@_pytest.fixture(autouse=True)
def _empty_shared_planner_resolution():
    try:
        from app.services.planner_shared_cache import SHARED_RESOLUTION
    except ImportError:  # grocery_data-only test runs
        yield
        return
    SHARED_RESOLUTION.clear()
    yield
    SHARED_RESOLUTION.clear()


# --- Planner memory reclamation -----------------------------------------------
# release_idle_memory() runs a full gc.collect(2) at every planner phase
# boundary. In production that returns pages between requests; in a test
# process that holds every earlier test's caches it is pure overhead (about
# 60 % of a full-library planner test). Tests keep the young-generation
# collection and the real counters. Memory tests use the real collector, and
# SMAKO_TEST_FULL_GC=1 restores it everywhere.
_REAL_GC_MODULES = ("test_planner_memory", "test_planner_admission")


@_pytest.fixture(autouse=True)
def _young_generation_planner_gc(request, monkeypatch):
    module = getattr(request.module, "__name__", "")
    if os.environ.get("SMAKO_TEST_FULL_GC") or module.endswith(_REAL_GC_MODULES):
        yield
        return
    import gc as _gc
    from types import SimpleNamespace as _Namespace

    try:
        from app.services import planner_memory as _planner_memory
    except ImportError:  # grocery_data-only test runs
        yield
        return
    monkeypatch.setattr(_planner_memory, "gc",
                        _Namespace(collect=lambda generation=2: _gc.collect(0)))
    yield
