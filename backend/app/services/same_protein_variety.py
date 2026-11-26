"""Variety for a week that repeats one kind of dinner (owner request 2026-11-26).

The balanced and varied presets allow at most two dinners with the same main
ingredient. A user who asks for five chicken dinners (a distribution of
{"chicken": 5}) then got no menu at all, although Lund has more than two
hundred chicken dinners. When the user's own distribution asks for more
chicken dinners than that cap, the cap follows the request.

Whenever three or more dinners of one kind are asked for, the week must vary
in how they are cooked instead: no dish family twice, at most two dinners on
the same carbohydrate or the same cooking method, and two or three cooking
methods. A five-fish week was otherwise five rice dishes. Everything else
(pairwise similarity, dish form, prices) is unchanged.

Only chicken is one main ingredient for a whole category. Meat and fish weeks
already have many main ingredients (pork, beef, mince, salmon, cod, tuna...);
raising their cap would only allow three sardine dinners in one week.
"""

SINGLE_MAIN_CATEGORIES = ("chicken",)


def same_protein_week_policy(policy, meal):
    if meal is None or not getattr(meal, "distribution", None):
        return policy
    cap = policy.max_same_primary_ingredient_meals
    need = max(meal.distribution.values(), default=0)
    if cap is None or need < 3:
        return policy
    carb, method = policy.max_same_carbohydrate_meals, policy.max_same_cooking_method_meals
    single = max((meal.distribution.get(c, 0) for c in SINGLE_MAIN_CATEGORIES), default=0)
    return policy.model_copy(update={
        "max_same_primary_ingredient_meals": max(cap, single),
        "max_same_recipe_family": 1,
        "max_same_carbohydrate_meals": 2 if carb is None else min(carb, 2),
        "max_same_cooking_method_meals": 2 if method is None else min(method, 2),
        "min_cooking_methods": max(policy.min_cooking_methods, 2 if need == 3 else 3),
    })
