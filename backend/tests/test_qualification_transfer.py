"""Cheap request-local topology checks; synthetic prices are not latency evidence."""
from collections import OrderedDict

import pytest
from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services.menu_optimizer import MenuOptimizer
from app.services.recipe_candidate_validator import recipe_id


@pytest.mark.parametrize('order', ['original', 'reverse', 'rotate'])
@pytest.mark.parametrize('ties', [False, True])
def test_reserved_qualifications_survive_more_than_256_earlier_misses(order, ties):
    recipes=[Recipe(name=f'Dish {i:03d}',servings=1,
        ingredients=[RecipeIngredient(name='ris',quantity=i+1,unit='g')],instructions=['synthetic']) for i in range(300)]
    first=[MealSlot(id='d1',day=1,meal_type='dinner',recipe=r) for r in recipes]
    tail=MealSlot(id='d2',day=2,meal_type='dinner',recipe=recipes[0])
    value=lambda slots: 1 if ties else sum(int(s.recipe.name.split()[-1]) for s in slots)
    seeds=OrderedDict((((s.id,recipe_id(s.recipe)),),value([s])) for s in first[-256:])
    if order=='reverse':first.reverse()
    if order=='rotate':first=first[150:]+first[:150]
    calls=[];trace=[]
    def evaluate(slots,final):
        calls.append((len(slots),final));return value(slots)
    kwargs={'evaluate':evaluate,'accepts':lambda slots,final:True,
        'score':lambda slots,result:result,'beam_width':3}
    chosen,result=MenuOptimizer().optimize_slots([first,[tail]],initial_evaluations=seeds,search_trace=trace,**kwargs)
    assert not seeds
    assert calls.count((1,False))==44
    assert trace[0]['qualification_cache_hits']==256
    assert all(r['full_result_cache_entries_peak']<=256 for r in trace)
    baseline=MenuOptimizer().optimize_slots([first,[tail]],**kwargs)
    assert ([s.recipe.name for s in chosen],result)==([s.recipe.name for s in baseline[0]],baseline[1])


def test_changed_slot_identity_cannot_consume_a_qualification():
    recipe=Recipe(name='Rice',servings=1,ingredients=[RecipeIngredient(name='ris',quantity=1,unit='g')],instructions=['synthetic'])
    slots=[[MealSlot(id=f'd{i}',day=i,meal_type='dinner',recipe=recipe)] for i in [1,2]]
    seeds={(("old-owner-slot",recipe_id(recipe)),):-999}
    calls=[]
    def evaluate(chosen,final):calls.append((len(chosen),final));return 10
    _,result=MenuOptimizer().optimize_slots(slots,initial_evaluations=seeds,evaluate=evaluate,
        accepts=lambda slots,final:True,score=lambda slots,result:result)
    assert result==10 and calls==[(1,False),(2,True)] and not seeds
