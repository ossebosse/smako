"""Document B2's sole intent change and test structural capacity, not checkout.

Run only through budgeted_check. The old observed pool is a diagnostic witness
source, never the candidate domain used by the actual new API search.
"""
import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.diversity import VariationField
from app.services.complete_recipes import diversity_policy, prepare_request
from app.services.meal_plan_optimizer import MealPlanService
from app.services.personal_planner import personal_policy_request
from app.services.personal_policy import protein_category
from app.services.product_planning_trace import recipe_identity
from app.services.recipe_library import _registered_portions
from app.services.recipe_week_variation import accepts_week
from app.services.variation_intent import resolve_current_variation


def main(args):
    from typing import get_args
    source=Path('docs/reviews/recipe-quality-and-planning-20261026/requests.json')
    data=json.loads(source.read_bytes())
    original=data['B']
    b2={**original,'variation_intent':{'version':'explicit-over-default-v2',
        'field_origins':{k:('default' if k=='max_same_primary_ingredient_meals' else 'unknown') for k in get_args(VariationField)}}}
    assert {k:v for k,v in b2.items() if k!='variation_intent'}==original
    data['B2']=b2
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'requests.json').write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    raw=Path('docs/reviews/week-search-and-cache-20261026/B-frontier-review.json').read_bytes()
    observed=json.loads(raw)
    ids={r['id'] for r in observed['candidates']}
    recipes=[r for r in _registered_portions(4) if recipe_identity(r)['id'] in ids]
    assert len(recipes)==len(ids)==29
    settings=Settings(complete_recipes_enabled=True,library_search_policy='smako-current-library-v2')
    service=MealPlanService(Settings(price_provider='mock'))
    def resolved_initial(payload):
        req=prepare_request(PlanRequest.model_validate(payload),settings)
        policy=diversity_policy(req,service._diversity_policy_for(personal_policy_request(req,5),req.diversity_mode))
        return req,policy
    before_request,before=resolved_initial(original)
    req,initial=resolved_initial(b2)
    policy,constraints,resolution=resolve_current_variation(req,initial,service._culinary_constraints(recipes,initial),recipes)
    changed=[k for k,v in before.model_dump().items() if policy.model_dump()[k]!=v]
    assert changed==['max_same_primary_ingredient_meals'] and policy.max_same_primary_ingredient_meals==3
    chicken=[r for r in recipes if protein_category(r)=='chicken']
    veg=[r for r in recipes if protein_category(r)=='vegetarian']
    checked=0;rejections=Counter();witness=None
    for a in combinations(chicken,3):
        for b in combinations(veg,2):
            checked+=1;selected=[*a,*b]
            if len({r.design.base_id for r in selected})!=5:rejections['duplicate_base']+=1
            elif not accepts_week(selected,req.recipe_preferences,dinner_count=5,final=True):rejections['explicit_week_variation']+=1
            elif not service.menu_optimizer.accepts_recipes(selected,constraints):rejections['culinary_variation']+=1
            else:
                witness=[{'id':recipe_identity(r)['id'],'name':r.name,'base_id':r.design.base_id} for r in selected]
                break
        if witness:break
    report={'scope':'Structural capacity in old observed qualified pool only. Actual B2 searches the entire current eligible library again. No checkout/nutrition/save approval.',
        'source_requests_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_frontier_sha256':hashlib.sha256(raw).hexdigest(),
        'raw_B_unchanged':True,'raw_B2_added_field':'variation_intent',
        'effective_policy_changed_fields':changed,'before_effective_policy':before.model_dump(mode='json'),
        'B2_effective_policy':policy.model_dump(mode='json'),'variation_resolution':resolution,
        'B_normalized_request':before_request.model_dump(mode='json'),'B2_normalized_request':req.model_dump(mode='json'),
        'combinations_checked':checked,'rejections':dict(rejections),'structural_witness':witness,
        'current_singleton_domain_reused_for_actual_API':False}
    (args.output/'B2-definition-and-capacity.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print({'changed_policy_fields':changed,'combinations_checked':checked,'structural_witness':witness})
    if witness is None:raise SystemExit(2)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
