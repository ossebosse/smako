from types import SimpleNamespace

from app.models.diversity import DiversityMode
from app.services.complete_recipes import diversity_policy
from app.services.diversity_policy import create_diversity_policy
from app.services.same_protein_variety import same_protein_week_policy


def authored_balanced():
    request = SimpleNamespace(recipe_preferences=SimpleNamespace(mode="complete"), recipe_diversity_overrides=None)
    policy = create_diversity_policy(DiversityMode.BALANCED)
    try:
        return diversity_policy(request, policy)
    except Exception:
        return policy.model_copy(update={"min_cooking_methods": 0, "max_same_cooking_method_meals": None,
                                         "max_same_carbohydrate_meals": None})


def test_five_chicken_dinners_are_allowed_but_must_be_cooked_differently():
    policy = same_protein_week_policy(authored_balanced(), SimpleNamespace(distribution={"chicken": 5}))
    assert policy.max_same_primary_ingredient_meals == 5
    assert policy.max_same_recipe_family == 1
    assert policy.max_same_carbohydrate_meals == 2
    assert policy.max_same_cooking_method_meals == 2
    assert policy.min_cooking_methods == 3


def test_three_of_one_kind_needs_two_methods():
    policy = same_protein_week_policy(authored_balanced(), SimpleNamespace(distribution={"chicken": 3, "fish": 2}))
    assert policy.max_same_primary_ingredient_meals == 3 and policy.min_cooking_methods >= 2


def test_ordinary_weeks_and_cheapest_are_unchanged():
    base = authored_balanced()
    assert same_protein_week_policy(base, SimpleNamespace(distribution={"chicken": 2, "fish": 2, "meat": 1})) is base
    assert same_protein_week_policy(base, SimpleNamespace(distribution={})) is base
    assert same_protein_week_policy(base, None) is base

    cheapest = create_diversity_policy(DiversityMode.CHEAPEST)
    assert same_protein_week_policy(cheapest, SimpleNamespace(distribution={"chicken": 5})) is cheapest


def test_a_fish_or_meat_week_varies_but_keeps_the_main_ingredient_cap():
    for kind in ("fish", "meat"):
        policy = same_protein_week_policy(authored_balanced(), SimpleNamespace(distribution={kind: 5}))
        assert policy.max_same_primary_ingredient_meals == 2
        assert policy.max_same_recipe_family == 1 and policy.max_same_carbohydrate_meals == 2
        assert policy.max_same_cooking_method_meals == 2 and policy.min_cooking_methods == 3
