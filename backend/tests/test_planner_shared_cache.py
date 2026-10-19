"""Cross-request reuse returns exactly what a fresh request computes."""
from contextlib import suppress
from copy import deepcopy

import pytest
from app.errors import IncompleteBasketError
from app.services.planner_shared_cache import SHARED_RESOLUTION

from backend.tests.test_complete_scope_incumbents import fixture, planner


def outcome(request, universe, facts, pantry):
    p = planner(request, universe, facts, deepcopy(pantry))
    plan = p.create()
    return p, {
        "basket": plan.optimized_basket.model_dump(mode="json"),
        "slots": [s.model_dump(mode="json") for s in plan.personal.slots],
        "allocations": plan.personal.allocations,
        "nutrition": plan.personal.checks["nutrition"],
        "audit": plan.personal.checks["checkout_audit"],
        "trace": (p.product_trace.products, p.product_trace.omitted_events, p.product_trace.context_count),
    }


def hits(cache):
    return sum(s["hits"] for s in cache.stats())


@pytest.fixture
def isolated(monkeypatch):
    SHARED_RESOLUTION.clear()
    yield
    SHARED_RESOLUTION.clear()


def test_identical_request_reuses_and_equals_a_fresh_calculation(isolated, monkeypatch):
    request, universe, facts, pantry = fixture()
    monkeypatch.setenv("SMAKO_PLANNER_SHARED_RESOLUTION", "0")
    _, fresh = outcome(request, universe, facts, pantry)
    monkeypatch.delenv("SMAKO_PLANNER_SHARED_RESOLUTION")
    _, first = outcome(request, universe, facts, pantry)
    assert hits(SHARED_RESOLUTION) == 0
    _, second = outcome(request, universe, facts, pantry)
    assert hits(SHARED_RESOLUTION) > 0
    assert fresh == first == second


def test_other_purchase_mode_or_stores_get_their_own_resolution_scope(isolated):
    request, universe, facts, pantry = fixture()
    outcome(request, universe, facts, pantry)
    estimated = request.model_copy(update={"purchase_planning_mode": "estimated"})
    # The outcome is irrelevant here; only the scope its resolutions use matters.
    with suppress(ValueError, IncompleteBasketError):
        planner(estimated, universe, facts, deepcopy(pantry)).create()
    assert len(SHARED_RESOLUTION.stats()) == 2


def test_disabled_reuse_keeps_nothing(isolated, monkeypatch):
    monkeypatch.setenv("SMAKO_PLANNER_SHARED_RESOLUTION", "0")
    request, universe, facts, pantry = fixture()
    outcome(request, universe, facts, pantry)
    assert SHARED_RESOLUTION.stats() == []
