"""A partial input diagnostic cannot become a recipe or basket approval."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def diagnostic(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    import screen_pending_recipe_inputs
    return screen_pending_recipe_inputs


@pytest.fixture
def draft():
    return {'base_id': 'test-pending', 'variant_id': 'simple', 'version': '1.0.0',
            'name': 'Unapproved draft', 'servings': 1, 'meal_type': 'snack', 'cuisine': 'thai',
            'family': 'test', 'primary': 'rismjöl', 'method': 'pot', 'side': 'none',
            'flavor': ['test'], 'equipment': ['kastrull'], 'steps': [],
            'components': [{'id': 'main', 'name': 'Main', 'ingredients': [
                {'name': 'rismjöl', 'form': 'dry', 'quantity': 17, 'unit': 'g', 'role': 'primary'},
                {'name': 'missing ingredient', 'form': 'as_sold', 'quantity': 5, 'unit': 'g', 'role': 'flavour'}]}]}


def test_probe_preserves_amount_and_review_requirements_without_editing_source(diagnostic, draft):
    before = copy.deepcopy(draft)
    recipe, unknown = diagnostic.known_input_probe(draft, {'rismjöl|dry': ('g', ['pack:intake_test'])})
    assert draft == before and unknown == ['missing ingredient|as_sold']
    assert recipe.design.base_id == 'smako-diagnostic-test-pending'
    assert recipe.preparation is not None
    ingredient, = recipe.ingredients
    assert (ingredient.canonical_name, ingredient.quantity, ingredient.unit) == ('rismjöl', 17, 'g')
    assert ingredient.product_requirements == ('pack:intake_test',)


def test_empty_known_subset_is_never_a_success_or_a_planner_call(diagnostic, draft):
    result = diagnostic.screen(draft, {}, None)
    assert result['status'] == 'no_known_inputs'
    assert result['known_input_count'] == 0
    assert len(result['unknown_identities']) == 2
    assert not result['recipe_approved'] and not result['basket_checked']


def test_one_missing_known_product_is_reported_beside_unknown_names(diagnostic, draft):
    calls = []

    def missing(name, quantity, unit, **kwargs):
        calls.append((name, quantity, unit))
        raise ValueError('No verified glutinous product; ordinary flour is different')

    planner = SimpleNamespace(meals={'snack': object()}, _merged_profile=lambda _: object(), resolve=missing)
    result = diagnostic.screen(draft, {'rismjöl|dry': ('g', [])}, planner)
    assert calls == [('rismjöl', 17, 'g')]
    assert result['status'] == 'known_inputs_blocked' and len(result['input_blocks']) == 1
    assert result['unknown_identities'] == ['missing ingredient|as_sold']
    assert not result['recipe_approved'] and not result['basket_checked']


def test_resolved_partial_inputs_are_not_called_verified(diagnostic, draft):
    planner = SimpleNamespace(meals={'snack': object()}, _merged_profile=lambda _: object(),
                              resolve=lambda *args, **kwargs: object())
    result = diagnostic.screen(draft, {'rismjöl|dry': ('g', [])}, planner)
    assert result['status'] == 'known_inputs_resolved_only'
    assert result['unknown_identities'] and not result['input_blocks']
    assert not result['recipe_approved'] and not result['basket_checked']


def test_raw_audit_and_reviewed_pending_decisions_are_both_screened(diagnostic):
    statuses = ['blocked', 'native_compatible_not_approved', 'pending_qualified_input',
                'pending_register_or_authoring', 'imported_reviewed_version']
    rows = [{'source_id': str(i), 'status': s} for i, s in enumerate(statuses)]
    assert diagnostic.pending_entries({'variants': rows}) == rows[:4]


def test_unknown_queue_decision_cannot_silently_drop_a_recipe(diagnostic):
    with pytest.raises(ValueError, match='Unknown queue decision'):
        diagnostic.pending_entries({'variants': [{'status': 'new_unhandled_state'}]})


def test_saved_screen_covers_exactly_the_pending_queue_without_approvals(diagnostic):
    root = Path('docs/reviews/recipe-unblock-round2-20261101')
    raw = (root / 'queue.json').read_bytes()
    queue = json.loads(raw)
    report = json.loads((root / 'pending-known-inputs.json').read_bytes())
    assert report['queue_sha256'] == hashlib.sha256(raw).hexdigest()
    expected = {r['source_id'] for r in queue['variants'] if r['status'].startswith('pending_')}
    assert len(report['variants']) == len(expected) == 141
    assert {r['source_id'] for r in report['variants']} == expected
    assert not report['recipe_approved'] and not report['basket_checked']
    assert diagnostic.summarize(copy.deepcopy(report)) == report
    combined = {r['identity']: r for r in report['ranked_combined_blocks']}
    assert combined['tamarindpasta|as_sold']['variants'] == 11
    assert combined['klibbigt rismjöl|dry']['variants'] == 2
    for row in report['variants']:
        assert not row['recipe_approved'] and not row['basket_checked']
        assert row['status'] in {'known_inputs_blocked', 'known_inputs_resolved_only', 'no_known_inputs'}
