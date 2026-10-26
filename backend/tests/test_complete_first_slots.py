"""Whole-menu proposal correctness, soft stop and bounded private memory."""
from itertools import product as product_menus

import pytest
from app.errors import IncompleteBasketError
from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services.menu_optimizer import MenuOptimizer
from app.services.plan_jobs import PlanningDeadlineExceeded


def options(names, days=2):
    recipes=[Recipe(name=name,servings=1,
        ingredients=[RecipeIngredient(name='ris',quantity=i+1,unit='g')],instructions=['synthetic'])
        for i,name in enumerate(names)]
    return [[MealSlot(id=f'dinner-{d}',day=d,meal_type='dinner',recipe=r) for r in recipes]
            for d in range(1,days+1)]


def test_complete_proposals_reach_later_joint_variation_and_package_winner():
    groups=options('ABCD')
    valid={('A','B'),('C','D')}
    costs={('A','B'):20,('C','D'):5}
    trace=[];calls=[]
    def accepts(slots,final):return not final or tuple(s.recipe.name for s in slots) in valid
    def evaluate(slots,final):
        assert final and len(slots)==2
        names=tuple(s.recipe.name for s in slots);calls.append(names);return costs[names]
    chosen,cost=MenuOptimizer().optimize_slots(groups,complete_first=True,accepts=accepts,
        evaluate=evaluate,score=lambda slots,cost:cost,search_trace=trace)
    oracle=min(costs[tuple(s.recipe.name for s in m)] for m in product_menus(*groups) if accepts(m,True))
    assert cost==oracle==5 and tuple(s.recipe.name for s in chosen)==('C','D')
    assert calls==[('A','B'),('C','D')]
    assert trace[-1]['proposal_space_enumerated'] and trace[-1]['improvements']==2
    assert trace[-1]['first_valid_cost']=='20'


def test_joint_checkout_rejection_cannot_be_replaced_by_individual_price():
    groups=options('ABC')
    def evaluate(slots,final):
        assert final
        names={s.recipe.name for s in slots}
        if names!={'B','C'}:raise ValueError('Synthetic joint nutrition/organic failure')
        return 27
    chosen,cost=MenuOptimizer().optimize_slots(groups,complete_first=True,
        accepts=lambda slots,final:len({s.recipe.name for s in slots})==len(slots),
        evaluate=evaluate,score=lambda slots,cost:cost,candidate_priority=lambda slot:slot.recipe.name)
    assert cost==27 and {s.recipe.name for s in chosen}=={'B','C'}


def test_soft_reserve_returns_the_valid_incumbent_and_never_a_partial(monkeypatch):
    from app.services import plan_jobs
    remaining=[30.0]
    monkeypatch.setattr(plan_jobs,'remaining_planning_seconds',lambda:remaining[0])
    trace=[];calls=[]
    def evaluate(slots,final):
        calls.append((len(slots),final));remaining[0]=11.9;return 10
    _,cost=MenuOptimizer().optimize_slots(options('AB'),complete_first=True,
        accepts=lambda slots,final:True,evaluate=evaluate,score=lambda slots,cost:cost,search_trace=trace)
    assert cost==10 and calls==[(2,True)]
    assert trace[-1]['stop_reason']=='reserved_current_checkout_audit_save_time'
    assert trace[-1]['first_valid_request_seconds']==pytest.approx(48.1)
    with pytest.raises(PlanningDeadlineExceeded):
        MenuOptimizer().optimize_slots(options('AB'),complete_first=True,
            accepts=lambda slots,final:True,evaluate=evaluate,score=lambda slots,cost:cost)


def test_improvement_cancels_inside_checkout_and_restores_outer_audit_budget(monkeypatch):
    from app.services import plan_jobs
    now=[0.0];calls=[]
    monkeypatch.setattr(plan_jobs,'monotonic',lambda:now[0])
    def evaluate(slots,final):
        calls.append(1)
        now[0]=5 if len(calls)==1 else 49
        plan_jobs.check_cancelled()
        return 10
    with plan_jobs.planning_deadline(60):
        _,cost=MenuOptimizer().optimize_slots(options('AB'),complete_first=True,
            accepts=lambda slots,final:True,evaluate=evaluate,score=lambda slots,cost:cost)
        assert cost==10 and len(calls)==2
        assert plan_jobs.remaining_planning_seconds()==11
        plan_jobs.check_cancelled()  # The final current checkout still has its outer budget.


def test_broad_search_keeps_two_full_results_and_later_original_order_anchors(monkeypatch):
    import weakref

    from app.services import plan_jobs
    groups=options([f'{i:02d}' for i in range(65)],days=3)
    remaining=[30.0];live=[];peak=[0];seen=[]
    monkeypatch.setattr(plan_jobs,'remaining_planning_seconds',lambda:remaining[0])
    class Result:
        def __init__(self,cost):self.cost=cost
    def evaluate(slots,final):
        assert final and len(slots)==3
        names=tuple(s.recipe.name for s in slots);seen.append(names)
        result=Result(sum(int(n) for n in names));live.append(weakref.ref(result))
        peak[0]=max(peak[0],sum(r() is not None for r in live))
        if len(seen)>=80:remaining[0]=11
        return result
    trace=[]
    _,result=MenuOptimizer().optimize_slots(groups,complete_first=True,
        accepts=lambda slots,final:len({s.recipe.name for s in slots})==len(slots),
        evaluate=evaluate,score=lambda slots,result:result.cost,search_trace=trace,
        candidate_priority=lambda slot:-int(slot.recipe.name))
    assert result.cost<64+63+62
    assert peak[0]<=2
    assert any('00' in menu for menu in seen)
    assert trace[-1]['compact_seen_entries']<=4096
    assert trace[-1]['anchors_considered']<trace[-1]['anchors_total']==65
    assert trace[-1]['anchors_deferred']>0


def test_exhausted_proposals_never_invent_a_valid_result():
    with pytest.raises(IncompleteBasketError):
        MenuOptimizer().optimize_slots(options('AB'),complete_first=True,
            accepts=lambda slots,final:not final,evaluate=lambda slots,final:0,score=lambda slots,result:result)


@pytest.mark.parametrize('amount,expected', [(200,10),(400,17)])
def test_real_joint_checkout_keeps_nutrition_organic_and_package_alternatives(amount, expected):
    from app.config import Settings
    from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
    from app.models.plan import PlanRequest
    from app.services.personal_planner import PersonalPlanner
    from app.services.reviewed_cold_meals import STEPS

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state
    from backend.tests.test_personal_qualified_facts import facts

    products=[product('Kvarg Naturell 0,2%',q,'g',price,identity=identity).model_copy(update={'semantic_confidence':'low'})
        for q,price,identity in [(500,1,'cheap'),(500,10,'strong-small'),(1000,17,'strong-large')]]
    evidence={(p.store_id,p.product_id):facts(p,organic=p.product_id!='cheap',animal=True,
        ingredients=('Pastöriserad MJÖLK, mjölksyrakultur',),
        nutrition={'protein_g':1 if p.product_id=='cheap' else 10},nutrition_unit='g',
        nutrition_basis='per 100 g as sold') for p in products}
    meal=MealSettings(meal_type='breakfast',count=2,servings=1,limits=PortionLimits(min_protein_g=20))
    req=PlanRequest(recipes=0,max_stores=2,personal=PersonalPlanning(meals=[meal],organic_percent=100,use_pantry=False))
    planner=PersonalPlanner(req,Settings(price_provider='mock'),prepared(*products),state(),facts=evidence,now=NOW)
    recipes=[Recipe(name=n,servings=1,ingredients=[RecipeIngredient(name='kvarg',quantity=q,unit='g')],
        instructions=STEPS) for n,q in [('A',amount),('B',300)]]
    groups=[[MealSlot(id=f'breakfast-{d}',day=d,meal_type='breakfast',recipe=r) for r in recipes] for d in [1,2]]
    accepts=lambda slots,final:len({s.recipe.name for s in slots})==len(slots)
    evaluate=lambda slots,final:planner.basket(slots,final=final)
    oracle=min(evaluate(list(menu),True)['basket'].total for menu in product_menus(*groups) if accepts(menu,True))
    chosen,result=MenuOptimizer().optimize_slots(groups,complete_first=True,accepts=accepts,
        evaluate=evaluate,score=lambda slots,result:result['basket'].total)
    assert result['basket'].total==oracle==expected
    assert {s.recipe.name for s in chosen}=={'A','B'}
    assert result['audit'].passed and result['checks']['organic_cost_percent']==100
    assert all(row['values']['protein_g']>=20 for row in result['checks']['nutrition'])
    assert all(i.product_id.startswith('strong') for store in result['basket'].stores for i in store.items)
