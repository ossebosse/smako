import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from app.errors import IncompleteBasketError
from app.services import library_publications

from backend.tests.test_complete_scope_incumbents import fixture, planner


def driver():
    path = (Path(__file__).parents[2] / 'docs/reviews/integration-scaling-20261023/run_reader_matrix.py')
    spec = importlib.util.spec_from_file_location('reader_matrix_reaudit_test', path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        # The serializer shim is only needed in the separate old reader image.
        sys.modules['app.services.library_publications'] = library_publications
    return module


def test_reader_validation_reaudits_old_menu_with_new_facts_and_rejects_invalid_nutrition():
    harness = driver()
    request, universe, facts, pantry = fixture()
    original = planner(request, universe, facts, pantry).create()
    menu = harness.slots_record(original.personal.slots)
    changed = {k: replace(v, nutrition={n: amount * 2 for n, amount in v.nutrition.items()})
               for k, v in facts.items()}
    audited = harness.replay_old_menu(planner(request, universe, changed, pantry), menu)
    assert audited.personal.checks['checkout_audit']['passed']
    assert audited.personal.checks['nutrition'] != original.personal.checks['nutrition']
    assert harness.slots_record(audited.personal.slots) == menu
    invalid = {k: replace(v, nutrition={'protein_g': 0}) for k, v in facts.items()}
    with pytest.raises((ValueError, IncompleteBasketError)):
        harness.replay_old_menu(planner(request, universe, invalid, pantry), menu)
