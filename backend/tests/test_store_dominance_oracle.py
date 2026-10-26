"""Exhaustive small baskets prove exact dominance and coupled-offer isolation."""
from itertools import product as combinations
from random import Random

import pytest
from app.models.ingredient import NormalizedIngredient
from app.services.basket_optimizer import BasketOptimizer
from app.services.performance_trace import activate_performance_trace

from backend.tests.test_optimizer import product, store


def purchase(rows,required,cap,prune):
    optimizer=BasketOptimizer(prune_dominated_stores=prune)
    with optimizer.quote_cache():
        return optimizer.optimize(required,rows,[store(s) for s in ['a','b','c','d']],cap)


@pytest.mark.parametrize('seed',range(10))
@pytest.mark.parametrize('cap',[1,2,3])
def test_full_checkout_winner_matches_unpruned_store_oracle(seed,cap):
    rng=Random(seed)
    names=['linser','ris','bröd']
    rows={n:tuple(product(n,f'{n}-{s}-{q}',s,q,rng.randint(5,30)) for s in ['a','b','c','d'] for q in [250,500]) for n in names}
    required=[NormalizedIngredient(canonical_name=n,required_quantity=q,unit='g') for n,q in zip(names,[400,650,200],strict=True)]
    assert purchase(rows,required,cap,True).model_dump()==purchase(rows,required,cap,False).model_dump()


def test_shared_ingredients_reduce_subsets_without_changing_package_winner():
    required=[NormalizedIngredient(canonical_name='linser',required_quantity=700,unit='g')]
    rows={'linser':tuple(product('linser',f'{s}-{q}',s,q,price) for s in ['a','b','c','d'] for q,price in [(250,10),(1000,25)])}
    with activate_performance_trace() as trace:
        actual=purchase(rows,required,2,True)
    assert actual.model_dump()==purchase(rows,required,2,False).model_dump()
    counts=trace.snapshot().operation_counters
    assert counts['store_contexts_pruned_dominated']==3
    assert counts['store_subsets_avoided_by_dominance']==9
    assert actual.total==25 and actual.stores[0].items[0].packages_needed==1


def test_forced_nutrition_and_organic_alternatives_keep_exact_best_qualified_basket():
    required=[NormalizedIngredient(canonical_name=n,required_quantity=500,unit='g') for n in ['linser','ris']]
    choices={n:[product(n,f'{n}-low','a',500,10),product(n,f'{n}-high','b',500,18)] for n in ['linser','ris']}
    facts={p.product_id:{'protein':10 if p.store_id=='a' else 25,'organic':p.store_id=='b'} for rows in choices.values() for p in rows}
    winners=[]
    for prune in [False,True]:
        valid=[]
        for selected in combinations(*choices.values()):
            basket=purchase({n:(p,) for n,p in zip(choices,selected,strict=True)},required,2,prune)
            items=[i for s in basket.stores for i in s.items]
            protein=sum(facts[i.product_id]['protein'] for i in items)
            organic=sum(i.total_price for i in items if facts[i.product_id]['organic'])/basket.total
            if protein>=35 and organic>=.5:valid.append(basket)
        winners.append(min(valid,key=lambda b:b.total).model_dump())
    assert winners[0]==winners[1] and winners[0]['total']==28


def test_coupled_campaign_never_uses_independent_dominance(monkeypatch):
    from app.config import Settings
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_personal_planning_v2 import NOW, state
    from backend.tests.test_promotion_groups import catalog, extras, group, request
    monkeypatch.setattr(BasketOptimizer,'_undominated_store_ids',lambda *args:pytest.fail('coupled checkout must remain joint'))
    p=catalog(group())
    result=PersonalPlanner(request(extras=extras()),Settings(price_provider='mock',library_search_policy='smako-current-library-v2'),p,state(),now=NOW).create()
    assert result.optimized_basket.total==75 and result.personal.checks['checkout_audit']['passed']


def test_extra_better_rank_coverage_cannot_hide_a_cheaper_mixed_rank_basket():
    from backend.tests.test_optimizer_verification import _candidate
    def q(name,shop,cost,confidence):
        return _candidate(name+shop,cost,ingredient=name,quantity_confidence=confidence).model_copy(update={'store_id':shop,'store_name':shop})
    rows={'x':(q('x','a',1,'exact'),q('x','b',1,'exact')),
          'y':(q('y','a',20,'exact'),q('y','c',1,'estimated')),
          'z':(q('z','c',1,'estimated'),)}
    required=[NormalizedIngredient(canonical_name=n,required_quantity=500,unit='g') for n in rows]
    old=purchase(rows,required,2,False)
    new=purchase(rows,required,2,True)
    assert old.total==new.total==3
    assert old.model_dump()==new.model_dump()
