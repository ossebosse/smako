"""Owner 2026-11-17: speed for every area, not per-city fixes."""
from app.models.personal import MealSettings, TasteProfile
from app.services import menu_optimizer
from app.services.personal_planner import _qualification_meal


def test_the_stall_needs_both_time_and_priced_weeks(monkeypatch):
    monkeypatch.delenv("SMAKO_MENU_SEARCH_STALL_EVALUATIONS", raising=False)
    assert menu_optimizer._stall_evaluations() == 1000
    monkeypatch.setenv("SMAKO_MENU_SEARCH_STALL_EVALUATIONS", "x")
    assert menu_optimizer._stall_evaluations() == 1000
    monkeypatch.setenv("SMAKO_MENU_SEARCH_STALL_EVALUATIONS", "250")
    assert menu_optimizer._stall_evaluations() == 250


def test_week_only_choices_do_not_split_per_recipe_qualification():
    plain = MealSettings(meal_type="dinner", count=3, servings=2)
    other = MealSettings(meal_type="dinner", count=5, servings=2, max_same_base_meals=1,
                         profile=TasteProfile(likes=["kyckling"], dislikes=["lever"]))
    assert _qualification_meal(plain) == _qualification_meal(other)
    # What decides whether one recipe qualifies still separates.
    for changed in ({"servings": 4}, {"diet": "vegetarian"},
                    {"profile": TasteProfile(allergies=["mjölk"])}, {"profile": TasteProfile(exclusions=["lök"])}):
        assert _qualification_meal(plain) != _qualification_meal(plain.model_copy(update=changed))
    # With a distribution, the count bounds the categories and is kept.
    split = plain.model_copy(update={"distribution": {"vegetarian": 1}})
    assert _qualification_meal(split) != _qualification_meal(split.model_copy(update={"count": 5}))
