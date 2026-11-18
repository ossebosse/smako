from types import SimpleNamespace

from app.models.personal import MealSettings, PortionLimits
from app.services.personal_planner import (
    _QUALIFICATION_MEMORY,
    PersonalPlanner,
    _qualification_meal,
)
from app.services.planner_context import content_digest


def test_a_nutrition_requirement_keeps_what_the_ordinary_choices_rejected(monkeypatch):
    monkeypatch.setattr(_QUALIFICATION_MEMORY, "rows", type(_QUALIFICATION_MEMORY.rows)())
    planner = SimpleNamespace(_qualification_context=lambda: {"stores": ["a"]},
                              diagnostics=SimpleNamespace(pools=[{"raw": 4}]))
    ordinary = MealSettings(count=3, servings=2)
    limited = ordinary.model_copy(update={"limits": PortionLimits(min_protein_g=30)})
    rejected = {"status": "rejected", "reason": "Ingen vara", "stage": "product_qualification", "code": "DATA_BLOCKED"}
    choices = {"status": "rejected", "reason": "x", "stage": "policy_taste", "code": "RECIPE_CHOICES_CONFLICT"}
    _QUALIFICATION_MEMORY.put(content_digest([{"stores": ["a"]}, _qualification_meal(ordinary), ()]), {"rows": {
        "r1": rejected, "r2": {"status": "passed", "evidence": None}, "r3": choices, "r4": rejected}})
    own = {"status": "rejected", "reason": "protein", "stage": "nutrition", "code": "NUTRITION_TARGET_NOT_MET"}
    rows = PersonalPlanner._with_ordinary_rejections(planner, limited, (), {"r4": own})
    # Rejections carry over; a passed recipe and content-filter decisions are
    # qualified again; the requirement's own rows win.
    assert rows == {"r1": rejected, "r4": own}
    assert planner.diagnostics.pools[-1]["ordinary_rejections_reused"] == 1
    # Other stores: nothing to reuse.
    other = SimpleNamespace(_qualification_context=lambda: {"stores": ["b"]}, diagnostics=SimpleNamespace(pools=[{}]))
    assert PersonalPlanner._with_ordinary_rejections(other, limited, (), {}) == {}
