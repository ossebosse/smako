"""Owner request 2026-11-22: the meal-planning rules can be fine-tuned on the admin page."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from app.services import planning_rules
from app.services.personal_policy import (
    animal_dinners_needed,
    cuisine_cap,
    fish_dinners_needed,
    meat_kind_cap,
    mixed_fish_needed,
    mixed_vegetarian_needed,
)
from app.services.plan_variation import per_dinner_kronor, variation_settings
from fastapi.testclient import TestClient

from tests.test_beta_release_observability import _application

TOKEN = "a" * 40


def test_defaults_are_the_owner_decisions_so_far():
    rules = planning_rules.PlanningRules()
    assert [animal_dinners_needed(n, rules) for n in range(1, 8)] == [1, 1, 1, 2, 2, 3, 3]
    assert [mixed_fish_needed(n, rules) for n in range(1, 8)] == [0, 0, 0, 1, 1, 1, 1]
    assert [mixed_vegetarian_needed(n, rules) for n in range(1, 8)] == [0, 1, 1, 1, 1, 1, 1]
    assert [fish_dinners_needed(n, rules) for n in range(1, 8)] == [1, 1, 1, 2, 2, 3, 3]
    assert [meat_kind_cap(n, rules) for n in range(2, 8)] == [1, 2, 2, 3, 3, 4]
    assert [cuisine_cap(n, rules) for n in range(2, 8)] == [1, 2, 2, 3, 3, 4]
    assert (rules.extra_store_min_saving_kr, rules.like_weight_kr, rules.like_missing_kr) == (10, 15, 1000)
    assert (rules.variation_percent, rules.member_avoid_recent_plans) == (10, 2)
    # Without a saved file the defaults apply.
    assert animal_dinners_needed(5) == 2 and cuisine_cap(7) == 4


def test_more_than_seven_dinners_keep_the_share_and_100_percent_turns_a_cap_off():
    rules = planning_rules.PlanningRules()
    assert animal_dinners_needed(14, rules) == 6
    assert meat_kind_cap(4, rules.model_copy(update={"meat_kind_max_percent": 100})) is None
    assert cuisine_cap(7, rules.model_copy(update={"cuisine_max_percent": 30})) == 3


@pytest.mark.parametrize("change, message", [
    ({"mixed_meat_min": [2, 1, 1, 2, 2, 3, 3]}, "mellan 0 och 1"),
    ({"mixed_meat_min": [1, 2, 2, 2, 2, 3, 3]}, "Allt med 2 middagar"),
    ({"mixed_meat_min": [1, 1, 1]}, "7"),
    ({"cuisine_max_percent": 0}, "greater than or equal to 1"),
])
def test_rules_that_cannot_be_met_are_refused(change, message):
    with pytest.raises(ValueError, match=message):
        planning_rules.PlanningRules.model_validate({**planning_rules.PlanningRules().model_dump(), **change})


def _client(tmp_path: Path):
    application, _, settings = _application(tmp_path)
    return TestClient(application), settings


def _basic():
    return {"Authorization": "Basic " + base64.b64encode(f"admin:{TOKEN}".encode()).decode()}


def test_admin_reads_saves_and_resets_the_rules(tmp_path):
    client, settings = _client(tmp_path)
    assert client.get("/api/admin/planning-rules").status_code == 401
    first = client.get("/api/admin/planning-rules", headers=_basic()).json()
    assert first["rules"] == first["defaults"] and first["updated_at"] is None

    rules = {**first["rules"], "mixed_meat_min": [1, 1, 2, 2, 3, 3, 4], "like_weight_kr": 25, "cuisine_max_percent": 100}
    saved = client.put("/api/admin/planning-rules", json={"rules": rules}, headers=_basic())
    assert saved.status_code == 200 and saved.json()["rules"]["like_weight_kr"] == 25
    assert (tmp_path / "planning-rules.json").exists()
    loaded = planning_rules.load(settings)
    assert animal_dinners_needed(7, loaded) == 4 and cuisine_cap(7, loaded) is None

    bad = client.put("/api/admin/planning-rules", json={"rules": {**rules, "mixed_meat_min": [9] * 7}}, headers=_basic())
    assert bad.status_code == 422 and "mellan 0 och 1" in bad.json()["detail"]
    assert planning_rules.load(settings).like_weight_kr == 25  # the refused change saved nothing

    other_site = client.put("/api/admin/planning-rules", json={"reset": True},
                            headers={**_basic(), "Origin": "https://evil.example"})
    assert other_site.status_code == 403
    reset = client.put("/api/admin/planning-rules", json={"reset": True}, headers=_basic())
    assert reset.json()["rules"] == reset.json()["defaults"]
    assert planning_rules.load(settings) == planning_rules.PlanningRules()


def test_the_planner_and_variation_read_the_saved_rules(tmp_path, monkeypatch):
    monkeypatch.setenv("PLAN_STORE_PATH", str(tmp_path / "plans.sqlite3"))
    from app.config import get_settings

    planning_rules.save(get_settings(), planning_rules.PlanningRules(
        mixed_fish_min=[0, 0, 1, 1, 1, 2, 2], variation_percent=20, member_avoid_recent_plans=4))
    assert mixed_fish_needed(7) == 2
    assert per_dinner_kronor([40.0, 40.0]) == pytest.approx(0.2 * 0.5 * 40)
    assert variation_settings({}).avoid_recent_plans == 4
    assert variation_settings({"variation": {"avoid_recent_plans": 1}}).avoid_recent_plans == 1

    from app.services.personal_planner import PersonalPlanner, extra_store_cost

    planner = PersonalPlanner.__new__(PersonalPlanner)
    assert planner.rules.variation_percent == 20
    assert extra_store_cost(type("B", (), {"store_count": 3})(), planner.rules) == 20


def test_a_broken_file_means_the_defaults(tmp_path):
    client, settings = _client(tmp_path)
    (tmp_path / "planning-rules.json").write_text("{not json", encoding="utf-8")
    assert planning_rules.load(settings) == planning_rules.PlanningRules()


def test_admin_page_has_the_planning_tab():
    static = Path(__file__).resolve().parents[1] / "app" / "static"
    html = (static / "admin.html").read_text(encoding="utf-8")
    assert 'id="tab-rules"' in html and "/static/admin-rules.js" in html
    script = (static / "admin-rules.js").read_text(encoding="utf-8")
    for key in planning_rules.PlanningRules.model_fields:
        assert f'"{key}"' in script, key
