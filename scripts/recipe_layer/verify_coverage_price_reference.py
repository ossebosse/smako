"""Recheck a public benchmark recipe proposal in the current checkout, not a new search."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSlot
from app.services.personal_planner import PersonalPlanner
from app.services.plan_jobs import planning_deadline
from app.services.recipe_library import current_recipes
from coverage_reference import digest, file_sha, load_reference


def main(args):
    prepared, facts, _references, _recipes, scope = load_reference(args)
    before = json.loads(args.reference.read_bytes())
    payload = json.loads(args.requests.read_bytes())[args.case]
    assert before['request'] == payload
    assert before['universe_sha256'] == scope['universe_sha256']
    assert before['library_manifest_sha256'] == scope['manifest_sha256']
    recipes = []
    for name in before['recipe_names']:
        matches = [r for r in current_recipes() if r.name == name]
        assert len(matches) == 1, name
        recipes.append(matches[0])
    planner = PersonalPlanner(PlanRequest.model_validate(payload),
        Settings(price_provider='mock', complete_recipes_enabled=True), prepared,
        {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, facts=facts,
        now=datetime.fromisoformat(scope['clock']))
    slots = [MealSlot(id=f'dinner-{n}', day=n, meal_type='dinner', recipe=r) for n, r in enumerate(recipes, 1)]
    with planning_deadline(25):
        result = planner.basket(slots, final=True)
    evidence = {'basket': result['basket'].model_dump(mode='json'), 'audit': result['audit'].model_dump(mode='json'),
                'checks': result['checks']}
    assert result['audit'].passed
    row = {'scope': scope, 'reference_sha256': file_sha(args.reference), 'raw_request_unchanged': True,
           'recipe_names': before['recipe_names'], 'previous_total': before['total'],
           'current_checkout_total': result['basket'].total, 'evidence': evidence,
           'evidence_sha256': digest(evidence),
           'meaning': 'Current checkout/audit of the previous recipe proposal; not a newly saved cold-search plan or a global optimum proof.'}
    args.output.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding='utf-8')
    print({k: row[k] for k in ['previous_total', 'current_checkout_total', 'raw_request_unchanged']}, flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['universe', 'facts', 'reference', 'requests', 'output']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--clock', required=True)
    p.add_argument('--case', required=True)
    main(p.parse_args())
