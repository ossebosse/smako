"""A complete tiny week has a known optimum using pooled package demand."""
from collections import defaultdict
from itertools import product as menus

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services.basket_optimizer import BasketOptimizer
from app.services.menu_optimizer import MenuOptimizer

from backend.tests.test_optimizer import product, store


@pytest.mark.parametrize('complete_first', [False, True])
def test_current_week_search_and_shared_checkout_match_all_complete_menus(complete_first):
    recipes=[Recipe(name=name,servings=1,ingredients=[RecipeIngredient(name=n,quantity=q,unit='g') for n,q in amounts],instructions=['Tillaga och servera.'])
        for name,amounts in [('A',[('linser',400),('ris',100)]),('B',[('linser',100),('ris',400)]),('C',[('bröd',400),('ris',50)])]]
    rows={n:tuple(product(n,f'{n}-{s}-{q}',s,q,cost) for s,q,cost in [('a',500,10),('b',1000,17)]) for n in ['linser','ris']}
    rows['bröd']=(product('bröd','bread-a','a',500,25),product('bröd','bread-b','b',500,8))
    options=[[MealSlot(id=f'dinner-{day}',day=day,meal_type='dinner',recipe=r) for r in recipes] for day in [1,2]]
    def accepts(slots,final=False):return len({s.recipe.name for s in slots})==len(slots)
    results=[]
    for prune in [False,True]:
        checkout=BasketOptimizer(prune_dominated_stores=prune)
        def evaluate(slots,final=False,checkout=checkout):
            amounts=defaultdict(float)
            for slot in slots:
                for i in slot.recipe.ingredients:amounts[i.name]+=i.quantity
            ingredients=[NormalizedIngredient(canonical_name=n,required_quantity=q,unit='g') for n,q in amounts.items()]
            return {'basket':checkout.optimize(ingredients,rows,[store('a'),store('b')],2)}
        with checkout.quote_cache():
            oracle=min(evaluate(list(m))['basket'].total for m in menus(*options) if accepts(m))
            chosen,result=MenuOptimizer().optimize_slots(options,evaluate=evaluate,accepts=accepts,
                score=lambda chosen,result:(result['basket'].total,tuple(s.recipe.name for s in chosen)),beam_width=8,
                complete_first=complete_first)
        assert oracle==result['basket'].total==20
        assert {s.recipe.name for s in chosen}=={'A','B'}
        results.append(result['basket'].model_dump())
    assert results[0]==results[1]


def test_complete_proposals_keep_a_joint_campaign_that_beats_cheaper_individual_meals():
    from app.models import ProductCandidate

    from backend.tests.test_promotion_groups import catalog, group

    p=catalog(group(amount=35))
    rows={v.name:(ProductCandidate.from_product(v,match_score=1),) for v in p.universe.products}
    def recipe(name,amounts):
        return Recipe(name=name,servings=1,ingredients=[RecipeIngredient(name=n,quantity=q,unit=u)
            for n,q,u in amounts],instructions=['Synthetic checkout fixture.'])
    first=[recipe('A',[('mjölk',1000,'ml')]),recipe('C',[('ris',1000,'g')])]
    second=[recipe('B',[('bröd',1000,'g'),('ris',1000,'g')]),recipe('D',[('ris',1000,'g')])]
    options=[[MealSlot(id=f'd{d}',day=d,meal_type='dinner',recipe=r) for r in recipes]
             for d,recipes in [(1,first),(2,second)]]
    checkout=BasketOptimizer()
    def evaluate(slots,final):
        quantities=defaultdict(float)
        for slot in slots:
            for item in slot.recipe.ingredients:quantities[(item.name,item.unit)]+=item.quantity
        needs=[NormalizedIngredient(canonical_name=n,required_quantity=q,unit=u) for (n,u),q in quantities.items()]
        return {'basket':checkout.optimize(needs,rows,p.stores,max_stores=1)}
    with checkout.quote_cache():
        oracle=min(evaluate(list(menu),True)['basket'].total for menu in menus(*options))
        chosen,result=MenuOptimizer().optimize_slots(options,complete_first=True,
            accepts=lambda slots,final:True,evaluate=evaluate,score=lambda slots,result:result['basket'].total,
            candidate_priority=lambda slot:60 if slot.recipe.name=='B' else 30)
    assert result['basket'].total==oracle==35
    assert chosen[1].recipe.name=='B'
