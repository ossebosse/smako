"""Explicit week choices stay separate from the existing economic modes."""

import pytest
from app.models.plan import PlanRequest
from app.models.recipe_preferences import RecipePreferences
from app.services.recipe_library import candidates
from app.services.recipe_week_variation import (
    CLASSIFICATION_VERSION,
    accepts_week,
    main_protein_sources,
    week_summary,
)


def _recipe(cuisine, base_fragment):
    matches = [r for r in candidates(RecipePreferences(mode="complete", cuisines=(cuisine,)), 4)
               if base_fragment in r.design.base_id]
    return matches[0]


def test_request_rejects_more_required_cuisines_than_dinners():
    with pytest.raises(ValueError, match="fler obligatoriska matkök"):
        PlanRequest(recipes=2, recipe_preferences=RecipePreferences(
            mode="complete", cuisines=("greek", "italian", "indian"),
            cuisine_distribution="each_selected"))
    with pytest.raises(ValueError, match="fler obligatoriska matkök"):
        PlanRequest(recipes=2, recipe_preferences=RecipePreferences(
            mode="complete", cuisine_distribution="minimum", min_distinct_cuisines=3))


def test_omitted_choices_keep_old_free_behavior():
    request = PlanRequest(recipes=5, recipe_preferences=RecipePreferences(
        mode="complete", cuisines=("greek", "indian")))
    assert request.recipe_preferences.cuisine_distribution == "free"
    assert request.recipe_preferences.max_same_main_protein_dinners is None
    assert "cuisine_distribution" not in request.model_dump_json()
    indian = _recipe("indian", "palak-tofu")
    assert accepts_week([indian], request.recipe_preferences, dinner_count=5, final=True)


def test_cuisine_requirement_prunes_only_unreachable_partials():
    indian = _recipe("indian", "palak-tofu")
    prefs = RecipePreferences(mode="complete", cuisines=("greek", "italian", "indian"),
                              cuisine_distribution="each_selected")
    assert accepts_week([indian], prefs, dinner_count=3, final=False)
    assert not accepts_week([indian], prefs, dinner_count=3, final=True)
    assert not accepts_week([indian, indian], prefs, dinner_count=3, final=False)


def test_mixed_dinner_counts_each_real_primary_once():
    dal = _recipe("indian", "tofu-dal")
    tofu = _recipe("indian", "palak-tofu")
    sources = main_protein_sources(dal)
    assert {"tofu", "linser"} <= sources
    prefs = RecipePreferences(mode="complete", max_same_main_protein_dinners=1)
    assert not accepts_week([dal, tofu], prefs, dinner_count=2, final=True)
    summary = week_summary([dal, tofu])
    assert summary["classification_version"] == CLASSIFICATION_VERSION
    assert summary["main_proteins"]["tofu"] == 2
    assert summary["dinner_count"] == 2
