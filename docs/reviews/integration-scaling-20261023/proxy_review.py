"""Advisory prequalification experiment; all retained recipes use normal gates.

Run after the final matrix, against the same frozen library/data and method.
An optional request-local memo reuses minima only for the same actual frozen
candidate objects, ingredient, quantity and unit. --verify-rows recomputes
every memo hit through the original quote function. No production hook.
"""
import hashlib
import math
import sys
import time
from collections import defaultdict
from functools import wraps
from pathlib import Path
from unittest.mock import patch

from app.models.ingredient import NormalizedIngredient
from app.models.personal import MealSlot
from app.services import recipe_library
from app.services.meal_library_content import identity
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict

from backend.scripts import planner_acceptance_matrix as matrix

index=sys.argv.index('--proxy-limit');limit=int(sys.argv[index+1]);del sys.argv[index:index+2]
assert limit>0
memo_enabled='--proxy-memo' in sys.argv
verify='--verify-rows' in sys.argv
for flag in ('--proxy-memo','--verify-rows'):
    if flag in sys.argv:sys.argv.remove(flag)
assert not verify or memo_enabled
assert '--uncapped' not in sys.argv and '--uncapped-reference' not in sys.argv
assert len(recipe_library.current_recipes(13))==262,'pinned base library required'
original=PersonalPlanner._candidates;original_meals=recipe_library.meal_candidates;original_quality=matrix.quality
rows=[]


@wraps(original)
def candidates(self,meal,*args,**kwargs):
    shared_results=kwargs.get("qualified_results")
    def ranked(*arguments,**options):
        started=time.perf_counter();full=original_meals(*arguments,**options)
        generations=recipe_library.current_recipe_generations(self.library_generation)
        retained=set();buckets=defaultdict(list);rejected=0;memo={};hits=misses=0
        for position,recipe in enumerate(full):
            generation=generations.get(identity(recipe),0)
            if generation<=13:
                retained.add(position);continue
            try:
                cleaned=self.clean_recipe(recipe,meal)
                slot=MealSlot(id=f'{meal.meal_type}-1',day=1,meal_type=meal.meal_type,recipe=cleaned)
                proxy=0.0
                for need in self._need_rows([slot]):
                    if need['quantity']<=0:continue
                    resolved=self.resolve_choices(need['name'],need['quantity'],need['unit'],product_key=need['product_key'],alternatives=need.get('alternatives',()),properties=need['properties'],profile=need['profile'],organic_animals=need['organic_animals'],food=need['food'],campaign_choice=need.get('campaign_choice',False),purchase_units=need.get('purchase_units',False),recipe=cleaned)
                    ingredient=NormalizedIngredient(canonical_name=need['name'],required_quantity=need['quantity'],unit=need['unit'])
                    pool=tuple(c for _,c in resolved)
                    key=(need['name'],need['quantity'],need['unit'],tuple(id(c) for c in pool))
                    cached=memo.get(key) if memo_enabled else None
                    if cached is not None:
                        assert len(cached[0])==len(pool) and all(a is b for a,b in zip(cached[0],pool,strict=True))
                        value=cached[1];hits+=1
                        if verify:
                            exact=float(min((q.total_price for q in self.optimizer._candidate_quotes(ingredient,pool)),default=float('inf')))
                            assert value==exact or math.isclose(value,exact,rel_tol=0,abs_tol=1e-9)
                    else:
                        value=float(min((q.total_price for q in self.optimizer._candidate_quotes(ingredient,pool)),default=float('inf')))
                        misses+=1
                        if memo_enabled:memo[key]=(pool,value)
                    proxy+=value
                buckets[(generation,meal.meal_type,self._protein_category(cleaned))].append((proxy,position))
            except (PolicyConflict,ValueError):rejected+=1
        for bucket in buckets.values():retained.update(position for _,position in sorted(bucket)[:limit])
        selected=[r for i,r in enumerate(full) if i in retained]
        rows.append({'meal_type':meal.meal_type,'available':len(full),'retained':len(selected),
                     'first_slot_qualified_result_handoff':shared_results is not None,
                     'policy_or_source_rejected':rejected,'proxy_limit_per_generation_category':limit,
                     'proxy_seconds':time.perf_counter()-started,'row_quote_memo':memo_enabled,
                     'row_quote_memo_hits':hits,'row_quote_memo_misses':misses,'verified_every_hit':verify,
                     'retained_identity_sha256':matrix.digest([identity(r) for r in selected])})
        return selected
    with patch.object(recipe_library,'meal_candidates',ranked):
        result=original(self,meal,*args,**kwargs)
    if shared_results is not None:
        rows[-1]["qualification_results_handed_back"]=len(shared_results)
    return result


def quality(plan,request):
    return {**original_quality(plan,request),
            'qualification_pool':'experimental proxy-ranked additions; entire262base retained',
            'runtime_experiment_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'proxy_review':list(rows)}


PersonalPlanner._candidates=candidates
matrix.quality=quality
matrix.main()
