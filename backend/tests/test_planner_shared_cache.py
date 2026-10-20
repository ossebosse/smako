"""Cross-request reuse returns exactly what a fresh request computes."""
from contextlib import suppress
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta

import pytest
from app.errors import IncompleteBasketError
from app.models.personal import TasteProfile
from app.services.personal_policy import PolicyConflict
from app.services.personal_source_facts import FactsCollection
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


def test_changed_facts_reject_a_previously_accepted_allergen_free_product(isolated):
    request, universe, facts, pantry = fixture()
    product = next(p for p in universe.universe.products if p.name == "nötfärs")
    key = product.store_id, product.product_id
    facts[key] = replace(facts[key], allergens_checked=("mjölk",))
    profile = TasteProfile(allergies=["mjölk"])
    first = planner(request, universe, FactsCollection(facts), deepcopy(pantry))
    assert first.resolve("nötfärs", 300, "g", profile=profile)
    facts[key] = replace(facts[key], allergens_present=("mjölk",))
    second = planner(request, universe, FactsCollection(facts), deepcopy(pantry))
    with pytest.raises(PolicyConflict):
        second.resolve("nötfärs", 300, "g", profile=profile)
    assert hits(SHARED_RESOLUTION) == 0


def test_membership_and_campaign_day_never_reuse_a_discount_from_another_scope(isolated):
    from backend.tests.test_personal_planning_v2 import NOW

    request, universe, facts, pantry = fixture()
    member = planner(request, universe, facts, deepcopy(pantry))
    kwargs = {"profile": TasteProfile()}
    discounted = member.resolve("nötfärs", 300, "g", **kwargs)[0][1]
    nonmember_request = request.model_copy(update={"memberships": {"coop": False}})
    nonmember = planner(nonmember_request, universe, facts, deepcopy(pantry))
    regular = nonmember.resolve("nötfärs", 300, "g", **kwargs)[0][1]
    expired = type(member)(request, member.settings, universe, deepcopy(pantry),
                           facts=facts, now=NOW + timedelta(days=10))
    after_campaign = expired.resolve("nötfärs", 300, "g", **kwargs)[0][1]
    assert discounted.effective_price < regular.effective_price == after_campaign.effective_price
    assert hits(SHARED_RESOLUTION) == 0


def test_shared_failure_is_recreated_without_other_requests_annotations(isolated):
    request, universe, facts, pantry = fixture()
    first = planner(request, universe, facts, deepcopy(pantry))
    kwargs = {"profile": TasteProfile(exclusions=["nötfärs"])}
    with pytest.raises(PolicyConflict) as original:
        first.resolve("nötfärs", 300, "g", **kwargs)
    original.value.stage = "annotated-by-first-request"
    original.value.conflicts.append("private-first-request-note")
    second = planner(request, universe, facts, deepcopy(pantry))
    with pytest.raises(PolicyConflict) as reused:
        second.resolve("nötfärs", 300, "g", **kwargs)
    assert hits(SHARED_RESOLUTION) > 0
    assert reused.value is not original.value
    assert reused.value.stage != original.value.stage
    assert "private-first-request-note" not in reused.value.conflicts
