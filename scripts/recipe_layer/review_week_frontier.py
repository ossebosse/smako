"""Bounded non-price diagnosis of the exact recipes observed in one failed B.

Use only through budgeted_check. A structural witness is not a bought,
nutrition-audited or saved menu and cannot count as successful user latency.
"""
import argparse
import hashlib
import json
from collections import Counter
from itertools import combinations

from app.config import Settings
from app.models import PlanRequest
from app.services.complete_recipes import diversity_policy
from app.services.meal_plan_optimizer import MealPlanService
from app.services.personal_planner import personal_policy_request
from app.services.personal_policy import protein_category
from app.services.product_planning_trace import recipe_identity
from app.services.recipe_library import _registered_portions
from app.services.recipe_week_variation import accepts_week


def main(args):
    source = args.probe.read_bytes()
    probe = json.loads(source)
    request = PlanRequest.model_validate(probe['request'])
    assert probe['case'] == 'B' and probe['diagnostics']['singleton_passed'] == 29
    observed = {row['recipe']['id'] for row in probe['diagnostics']['product_decisions']['recipe_search']}
    candidates = [r for r in _registered_portions(4) if recipe_identity(r)['id'] in observed]
    assert len(candidates) == len(observed) == 29
    meal = next(m for m in request.personal.meals if m.meal_type == 'dinner')
    assert meal.count == 5 and meal.distribution == {'chicken': 3, 'fish': 0, 'meat': 0, 'vegetarian': 2}
    service = MealPlanService(Settings(price_provider='mock', complete_recipes_enabled=True))
    policy = diversity_policy(request, service._diversity_policy_for(personal_policy_request(request, 5), request.diversity_mode))
    constraints = service._culinary_constraints(candidates, policy)
    categories = {id(r): protein_category(r) for r in candidates}
    chicken = [r for r in candidates if categories[id(r)] == 'chicken']
    vegetarian = [r for r in candidates if categories[id(r)] == 'vegetarian']
    rejected = Counter()
    checked = 0
    witness = None
    for meat in combinations(chicken, 3):
        for veg in combinations(vegetarian, 2):
            checked += 1
            recipes = [*meat, *veg]
            if len({r.design.base_id for r in recipes}) != 5:
                rejected['duplicate_base'] += 1
            elif not accepts_week(recipes, request.recipe_preferences, dinner_count=5, final=True):
                rejected['explicit_week_variation'] += 1
            elif not service.menu_optimizer.accepts_recipes(recipes, constraints):
                rejected['culinary_variation'] += 1
            else:
                witness = [{'id': recipe_identity(r)['id'], 'name': r.name} for r in recipes]
                break
        if witness:
            break
    result = {'scope': 'Exact observed singleton-qualified B pool; existing final structural predicates only. No checkout, nutrition approval, saved plan or user-latency success.',
        'probe_sha256': hashlib.sha256(source).hexdigest(), 'categories': dict(Counter(categories.values())),
        'candidates': [{'id': recipe_identity(r)['id'], 'name': r.name, 'base_id': r.design.base_id, 'category': categories[id(r)]} for r in candidates],
        'policy': policy.model_dump(mode='json'), 'combinations_checked': checked,
        'rejected': dict(rejected), 'structural_witness': witness, 'exhausted': witness is None}
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print({k: v for k, v in result.items() if k not in {'candidates', 'policy', 'scope'}})


if __name__ == '__main__':
    from pathlib import Path
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    main(p.parse_args())
