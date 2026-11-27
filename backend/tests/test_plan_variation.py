"""Owner decision 2026-11-21: new plans vary a little (app/services/plan_variation.py)."""
import json
import sqlite3
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from app.models.personal import MealSettings, PersonalPlanning, VariationSettings
from app.services import plan_variation as V
from app.services.personal_planner import PersonalPlanner
from app.services.recipe_library import current_recipes

OWNER = "a" * 64


class Store:
    """The two consumer_plan_revisions columns the variation reads."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute("CREATE TABLE consumer_plan_revisions (plan_id TEXT, revision INT, created_at TEXT, "
                        "owner_actor_hash TEXT, response_json TEXT)")

    def add(self, plan_id, created, bases, revision=1, owner=OWNER):
        slots = [{"meal_type": "dinner", "recipe": {"design": {"base_id": b}}} for b in bases]
        self.db.execute("INSERT INTO consumer_plan_revisions VALUES (?,?,?,?,?)",
                        (plan_id, revision, created, owner, json.dumps({"personal": {"slots": slots}})))

    @contextmanager
    def _connect(self):
        yield self.db

    def _validate_owner_actor_hash(self, owner):
        assert len(owner) == 64


def request(**personal):
    from app.models import PlanRequest

    return PlanRequest(recipes=3, personal=PersonalPlanning(meals=[MealSettings(count=3, servings=2)], **personal))


def test_recent_dinners_are_the_latest_revisions_of_the_newest_plans_with_dinners():
    store = Store()
    store.add("p1", "2026-11-01", ["a", "b"])
    store.add("p2", "2026-11-02", [])            # A store search without recipes.
    store.add("p3", "2026-11-03", ["c", "d"])
    store.add("p3", "2026-11-03", ["c", "e"], revision=2)  # "Byt rätt" changed d to e.
    store.add("x", "2026-11-04", ["z"], owner="b" * 64)
    assert V.recent_dinners(store, OWNER, 1) == [["c", "e"]]
    assert V.recent_dinners(store, OWNER, 5) == [["c", "e"], ["a", "b"]]
    assert V.recent_dinners(store, OWNER, 0) == []


def test_a_member_avoids_recent_dinners_and_gets_a_stable_seed():
    store = Store()
    store.add("p1", "2026-11-01", ["a", "b"])
    store.add("p2", "2026-11-02", ["b", "c"])
    state = {"variation": {"avoid_recent_plans": 2, "random_variation": True}}
    first = V.apply_variation(request(), store=store, owner=OWNER, state=state, member=True)
    assert first.personal.avoid_recipes == ["b", "c", "a"]  # Newest plan first.
    again = V.apply_variation(request(), store=store, owner=OWNER, state=state, member=True)
    assert again.personal.variation_seed == first.personal.variation_seed  # A retry joins the same job.
    store.add("p3", "2026-11-03", ["d"])
    later = V.apply_variation(request(), store=store, owner=OWNER, state=state, member=True)
    assert later.personal.variation_seed != first.personal.variation_seed
    assert later.personal.avoid_recipes == ["d", "b", "c"]


def test_guests_get_the_random_preference_only_and_settings_can_turn_both_off():
    store = Store()
    store.add("p1", "2026-11-01", ["a"])
    guest = V.apply_variation(request(), store=store, owner=OWNER, state={}, member=False)
    assert guest.personal.variation_seed is not None and guest.personal.avoid_recipes == []
    off = {"variation": {"avoid_recent_plans": 0, "random_variation": False}}
    assert V.apply_variation(request(), store=store, owner=OWNER, state=off, member=True) == request()
    assert V.variation_settings({}) == VariationSettings(avoid_recent_plans=2, random_variation=True)


def test_existing_plan_slots_and_requests_without_dinners_are_unchanged():
    store = Store()
    from app.models import PlanRequest

    plain = PlanRequest(recipes=0, personal=PersonalPlanning(meals=[]))
    assert V.apply_variation(plain, store=store, owner=OWNER, state={}, member=True) == plain
    assert "variation_seed" not in request().personal.model_dump()
    assert "avoid_recipes" not in request().personal.model_dump()


def test_random_preference_is_bounded_and_stable():
    assert V.per_dinner_kronor([40, 50, 60, float("inf"), None]) == pytest.approx(2.5)
    assert V.per_dinner_kronor([]) == 0.0
    recipes = [r for r in current_recipes() if r.design][:3]
    slots = [SimpleNamespace(meal_type="dinner", recipe=r) for r in recipes]
    planner = SimpleNamespace(spec=SimpleNamespace(variation_seed=7), _variation_kr=5.0)
    cost = PersonalPlanner._variation_cost(planner, slots)
    assert 0 <= cost < 15 and cost == PersonalPlanner._variation_cost(planner, slots)
    planner.spec.variation_seed = None
    assert PersonalPlanner._variation_cost(planner, slots) == 0.0


def test_no_fitting_week_allows_the_oldest_plans_dinners_again_first(monkeypatch):
    tried = []

    def create(self, **kwargs):
        tried.append(sorted(self._avoid))
        if len(tried) < 3:
            raise ValueError("Ingen vecka")
        return SimpleNamespace(personal=SimpleNamespace(checks={}))

    planner = SimpleNamespace(spec=SimpleNamespace(avoid_recipes=["new1", "new2", "old1", "old2"], variation_seed=None),
                              complete=True, _variation_kr=0.0)
    planner._create = lambda **kw: create(planner, **kw)
    result = PersonalPlanner._create_avoiding_recent(planner)
    assert tried == [["new1", "new2", "old1", "old2"], ["new1", "new2"], []]
    assert result.personal.checks["plan_variation"]["avoided_dinners"] == 0
    tried.clear()
    planner._create = lambda **kw: create(planner, **kw)
    with pytest.raises(ValueError):
        PersonalPlanner._create_avoiding_recent(planner, replace_slot="d1")  # "Byt rätt" relaxes per slot instead.
    assert tried == [["new1", "new2", "old1", "old2"]]


def test_only_members_can_change_the_settings(tmp_path, monkeypatch):
    from app.api import personal
    from fastapi.testclient import TestClient

    from backend.tests.test_privacy_erasure import _application

    application, _, settings = _application(tmp_path, price_provider="mock")
    monkeypatch.setattr(personal, "get_settings", lambda: settings)
    application.include_router(personal.router)
    client = TestClient(application)
    state = client.get("/api/personal/state").json()
    assert state["variation"] == {"avoid_recent_plans": 2, "random_variation": True}
    denied = client.put("/api/personal/variation", json={"revision": state["revision"],
                        "variation": {"avoid_recent_plans": 5, "random_variation": False}})
    assert denied.status_code == 403
    monkeypatch.setattr("app.api.account.verified_owner", lambda request: "c" * 64)
    state = client.get("/api/personal/state").json()
    saved = client.put("/api/personal/variation", json={"revision": state["revision"],
                       "variation": {"avoid_recent_plans": 5, "random_variation": False}})
    assert saved.status_code == 200, saved.text
    assert saved.json()["variation"] == {"avoid_recent_plans": 5, "random_variation": False}
