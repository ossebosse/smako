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


def test_content_filters_only_choose_candidates():
    from app.models.personal import MealRecipeChoices

    plain = MealSettings(meal_type="dinner", count=3, servings=2, recipe_choices=MealRecipeChoices())
    filtered = plain.model_copy(update={"recipe_choices": MealRecipeChoices(min_ingredients=5, max_ingredients=9,
                                                                            max_active_minutes=30)})
    assert _qualification_meal(plain) == _qualification_meal(filtered)
    assert _qualification_meal(plain) != _qualification_meal(plain.model_copy(update={"recipe_choices": None}))


def test_shared_quote_cache_grows_to_the_area_but_not_without_bound(monkeypatch):
    from types import SimpleNamespace

    from app.services import price_universe as pu

    cache = pu.PackageCostCache()
    monkeypatch.setattr(cache, "_candidate_digest", lambda candidate: str(id(candidate)))
    assert cache._cache.max_entries == 16384
    area = SimpleNamespace(universe_id="u", products=range(98_000))
    cache.get_or_compute(area, object(), required_quantity=1, required_unit="g", calculator_version="v",
                         factory=lambda: "quote")
    assert cache._cache.max_entries == 98_000
    cache.get_or_compute(SimpleNamespace(universe_id="u", products=range(10**6)), object(), required_quantity=1,
                         required_unit="g", calculator_version="v", factory=lambda: "quote")
    assert cache._cache.max_entries == pu._PACKAGE_CACHE_MAX
