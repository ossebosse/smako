"""A necessary capacity bound must never discard a feasible menu."""
from dataclasses import replace
from itertools import combinations_with_replacement, product

from app.models.recipe import Recipe, RecipeIngredient
from app.services.menu_optimizer import DiversityConstraints, MenuOptimizer


def recipes(count):
    return [Recipe(name=f"Recipe {index}", servings=2,
                   ingredients=[RecipeIngredient(name="ris", quantity=100, unit="g")],
                   instructions=["Koka riset."]) for index in range(count)]


def constraints(forms, limit, count):
    return DiversityConstraints(target_recipe_count=count, dish_forms=forms, max_same_dish_form=limit,
        max_same_primary_ingredient_meals=None, max_same_recipe_family=None,
        max_same_carbohydrate_meals=None, max_pairwise_recipe_similarity=None)


def test_capacity_proves_the_large_single_form_pool_impossible():
    pool=recipes(852);policy=constraints({r.name:"plated_meal" for r in pool},2,3)
    proof=MenuOptimizer().dish_form_capacity_conflict(pool,policy,3)
    assert proof=={"dimension":"dish_form","available_values":["plated_meal"],
                   "limit_per_value":2,"maximum_slots":2,"required_slots":3}


def test_capacity_bound_against_every_small_form_assignment_and_complete_menu():
    optimizer=MenuOptimizer();pool=recipes(3)
    for assignment in product(("plate","soup",None),repeat=len(pool)):
        forms={r.name:form for r,form in zip(pool,assignment,strict=True) if form is not None}
        for limit in (1,2,None):
            for count in (1,2,3,4):
                policy=constraints(forms,limit,count)
                proof=optimizer.dish_form_capacity_conflict(pool,policy,count)
                if proof is not None:
                    assert all(not optimizer.accepts_recipes(menu,policy)
                               for menu in combinations_with_replacement(pool,count)),(assignment,limit,count)


def test_unknown_form_is_not_a_capacity_rejection():
    pool=recipes(3);policy=constraints({pool[0].name:"plate",pool[1].name:"plate"},2,3)
    optimizer=MenuOptimizer()
    assert optimizer.dish_form_capacity_conflict(pool,policy,3) is None
    assert optimizer.accepts_recipes(pool,policy)


def test_mapping_uses_the_same_casefolding_and_whitespace_as_acceptance():
    pool=recipes(3);policy=constraints({r.name.upper():" PLATE " for r in pool},2,3)
    optimizer=MenuOptimizer()
    assert optimizer.dish_form_capacity_conflict(pool,policy,3)["maximum_slots"]==2
    assert not optimizer.accepts_recipes(pool,policy)


def test_custom_resolver_and_optimizer_keep_their_existing_call_behavior():
    pool=recipes(3);policy=constraints({r.name:"plate" for r in pool},2,3)
    calls=[]
    policy_with_resolver=replace(policy,dish_form_resolver=lambda r:calls.append(r))
    assert MenuOptimizer().dish_form_capacity_conflict(pool,policy_with_resolver,3) is None
    class Custom(MenuOptimizer):
        pass
    assert Custom().dish_form_capacity_conflict(pool,policy,3) is None
    assert calls==[]
