"""The shared cost cache is bounded and never carries a plan approval."""
from datetime import timedelta

import pytest
from app.config import Settings
from app.models.personal import TasteProfile
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.price_universe import PackageCostCache

from backend.tests.test_optimizer import product
from backend.tests.test_personal_planning_v2 import NOW, state
from backend.tests.test_promotion_groups import catalog, extras, group, request


def test_package_fingerprint_retention_is_bounded_and_recomputes_evicted_value():
    cache=PackageCostCache(max_entries=2)
    rows=[product('ris',str(n),'shop',500,10+n) for n in range(4)]
    for row in rows:cache._candidate_digest(row)
    assert len(cache._candidate_digests)==2
    changed=rows[0].model_copy(update={'price':99,'effective_price':99})
    assert cache._candidate_digest(rows[0])!=cache._candidate_digest(changed)
    assert len(cache._candidate_digests)==2


@pytest.mark.parametrize('grouped',[False,True])
def test_new_owner_reuses_only_exact_cost_parts_and_new_day_invalidates_them(grouped,monkeypatch):
    seen=[]
    original=PackageCostCache.get_or_compute
    def observe(self,*args,**kwargs):
        value=original(self,*args,**kwargs)
        seen.append(value.ingredient)
        return value
    monkeypatch.setattr(PackageCostCache,'get_or_compute',observe)
    p=catalog(group()) if grouped else catalog()
    expected=75 if grouped else 90
    settings=Settings(price_provider='mock',library_search_policy='smako-current-library-v2')
    def execute(owner,now):
        private=state();private['id']=owner
        return PersonalPlanner(request(extras=extras()),settings,p,private,now=now).create()
    first=execute('owner-one',NOW);before=p.package_cache.stats
    second=execute('owner-two',NOW);after=p.package_cache.stats
    assert first.optimized_basket.model_dump()==second.optimized_basket.model_dump()
    assert first.optimized_basket.total==expected
    if grouped:
        assert before.entries==after.entries==0  # Coupled groups retain joint checkout.
    else:
        assert after.hits>before.hits
    again=execute('owner-three',NOW+timedelta(days=1));last=p.package_cache.stats
    assert again.optimized_basket.total==expected
    if grouped:
        assert last.entries==0
    else:
        assert last.misses>after.misses
    assert again.personal.checks['checkout_audit']['passed']
    assert seen==[] if grouped else seen and set(seen)=={''}


def test_shared_cost_hit_is_never_a_new_owners_allergy_approval():
    p=catalog();settings=Settings(price_provider='mock',library_search_policy='smako-current-library-v2')
    req=request(extras=extras())
    PersonalPlanner(req,settings,p,state(),now=NOW).create()
    req.personal.profile=TasteProfile(allergies=['mjölk'])
    with pytest.raises(PolicyConflict):
        PersonalPlanner(req,settings,p,state(),now=NOW).create()
