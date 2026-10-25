"""Native DTO/store contracts for the external frozen history-arrival probe."""
import hashlib
import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from app.services.personal_store import PersonalStore
from app.services.plan_store import PlanStore
from app.services.planner_context import planner_context

from backend.scripts.planner_acceptance_matrix import matrix_request
from backend.tests.test_complete_scope_incumbents import fixture, planner


@pytest.fixture
def entry(monkeypatch):
    folder = Path(__file__).resolve().parents[2]/'docs/reviews/preparation-memory-20261024'
    monkeypatch.syspath_prepend(str(folder))
    return importlib.import_module('history_arrival_entry')


def test_past_request_is_native_valid_and_does_not_mutate_current(entry):
    current = matrix_request({'postal_code':'21211'},'distribution')
    current.personal.pantry_revision = 1
    before = current.model_dump(mode='json')
    assert entry.seed_request(current,'valid').model_dump(mode='json') == before
    past = entry.seed_request(current,'incomplete')
    assert past.recipes == past.personal.meals[0].count == 4
    assert sum(past.personal.meals[0].distribution.values()) == 4
    assert past.personal.pantry_revision == 1
    assert current.model_dump(mode='json') == before


def native_store(tmp_path):
    request,universe,facts,pantry = fixture()
    pantry['items'] = []
    plan = planner(request,universe,facts,pantry).create(_compare_scopes=False)
    store = PlanStore(tmp_path/'history.sqlite')
    owner = 'a'*64
    private = PersonalStore(store)
    private.read(owner)
    store.create(request,plan,owner_actor_hash=owner)
    return store,private,owner,request,plan,universe,facts


def test_stale_private_revision_is_rejected_instead_of_rewound(entry,tmp_path):
    store,*_ = native_store(tmp_path)
    with pytest.raises(AssertionError,match='actual current private revision'):
        entry.original_context(store,2)


def test_original_http_request_is_selected_after_native_history_arrival(entry,tmp_path):
    store,_private,owner,request,_,universe,facts = native_store(tmp_path)
    selected,current,state = entry.original_context(store,1)
    assert selected == owner and current.personal.pantry_revision == state['revision'] == 1
    assert request.personal.pantry_revision == 0
    plan = planner(current,universe,facts,state).create(_compare_scopes=False)
    store.create(current,plan,owner_actor_hash=owner)
    selected,reloaded,after = entry.original_context(store,2)
    assert selected == owner and reloaded.personal.pantry_revision == after['revision'] == 2
    assert current.personal.pantry_revision == 1 and after['items'] == state['items'] == []
    assert (planner_context(planner(current,universe,facts,state))
            == planner_context(planner(reloaded,universe,facts,after)))


def test_mixed_owners_are_rejected_before_reading_a_private_context(entry,tmp_path):
    store,private,_,request,plan,*_ = native_store(tmp_path)
    other = 'b'*64
    private.read(other)
    store.create(request,plan,owner_actor_hash=other)
    with pytest.raises(AssertionError,match='one synthetic owner'):
        entry.original_context(store,1)


def test_call_observer_counts_native_work_without_replacing_methods_or_results(entry):
    from app.services.basket_auditor import BasketAuditor
    from app.services.menu_optimizer import MenuOptimizer

    request,universe,facts,pantry = fixture()
    plain = planner(request,universe,facts,pantry).create(_compare_scopes=False)
    methods = (MenuOptimizer.optimize_library_slots,BasketAuditor.audit)
    with entry.observe_native_calls() as calls:
        measured = planner(request,universe,facts,pantry).create(_compare_scopes=False)
    assert calls['optimizer'] > 0 and calls['audit'] > 0
    assert (MenuOptimizer.optimize_library_slots,BasketAuditor.audit) == methods
    assert measured.optimized_basket == plain.optimized_basket
    assert measured.personal.slots == plain.personal.slots
    assert sys.getprofile() is None


def test_call_observer_restores_profile_on_failure(entry):
    with pytest.raises(ValueError,match='probe failure'), entry.observe_native_calls():
        raise ValueError('probe failure')
    assert sys.getprofile() is None


def test_http_rejection_evidence_excludes_inputs_and_capabilities(entry):
    response = httpx.Response(422,json={'detail':[{'loc':['body','personal','meals'],
        'type':'value_error','msg':'Meal count must be positive',
        'input':{'password':'never-persist-this','owner_actor_hash':'a'*64}}]},
        headers={'X-Error-Code':'form_validation_error','Set-Cookie':'never-copy-this'})
    value = entry.bootstrap.safe_http_error(response)
    encoded = json.dumps(value)
    assert value['detail'][0]['loc'] == ['body','personal','meals']
    assert 'never-' not in encoded and 'input' not in encoded and 'Set-Cookie' not in encoded
    assert value['error_code'] == 'form_validation_error'


def test_http_rejection_message_redacts_sensitive_text(entry):
    value = entry.bootstrap.safe_http_error(httpx.Response(422,json={'detail':'token never-copy-this'}))
    assert value['detail'] == '<sensitive message redacted>'


@pytest.mark.parametrize('supplied', ['22350','21120'])
def test_http_request_binds_frozen_area_without_mutating_cli_input(entry,supplied):
    request = matrix_request({'postal_code':supplied},'distribution')
    original = request.model_dump(mode='json')
    prepared = SimpleNamespace(universe=SimpleNamespace(key=SimpleNamespace(postal_codes={'21120'})))
    actual = entry.bootstrap.http_area_request(request,prepared)
    assert actual.postal_code == '21120'
    actual.personal.meals[0].count = 1
    assert request.model_dump(mode='json') == original


def test_http_request_refuses_to_guess_between_frozen_areas(entry):
    request = matrix_request({'postal_code':'22350'},'distribution')
    prepared = SimpleNamespace(universe=SimpleNamespace(key=SimpleNamespace(postal_codes={'21120','21211'})))
    with pytest.raises(AssertionError,match='unambiguous frozen postal area'):
        entry.bootstrap.http_area_request(request,prepared)


def test_history_quality_uses_native_result_instead_of_a_different_cli_price(entry):
    request,universe,facts,pantry = fixture()
    pantry['items'] = []
    plan = planner(request,universe,facts,pantry).create(_compare_scopes=False)
    result = entry.bootstrap.validate(plan,request)
    assert result['audit_passed'] and result['paid'] != 988.32
    assert entry.bootstrap.validate(plan,request,result) == result


@pytest.mark.parametrize('field,changed', [
    ('paid',0),('semantic_sha256','changed'),('verified_reference',{'context':'different'})])
def test_history_quality_rejects_changed_same_context_result(entry,field,changed):
    request,universe,facts,pantry = fixture()
    pantry['items'] = []
    plan = planner(request,universe,facts,pantry).create(_compare_scopes=False)
    result = entry.bootstrap.validate(plan,request)
    reference = {**result,field:changed}
    with pytest.raises(AssertionError,match='changed'):
        entry.bootstrap.validate(plan,request,reference)


def test_history_reference_survives_native_save_and_actual_private_revision(entry,tmp_path):
    store,private,owner,_,_,universe,facts = native_store(tmp_path)
    with store._connect() as connection:
        row = connection.execute('SELECT plan_id FROM consumer_plan_revisions').fetchone()
    saved = store.get_owned(row['plan_id'],owner_actor_hash=owner)
    reference = entry.bootstrap.validate(saved.plan,saved.request)
    state = private.read(owner)
    current = saved.request.model_copy(deep=True)
    current.personal.pantry_revision = state['revision']
    assert current.personal.pantry_revision == 1 and saved.request.personal.pantry_revision == 0
    plan = planner(current,universe,facts,state).create(_compare_scopes=False)
    assert entry.bootstrap.validate(plan,current,reference)['audit_passed']


@pytest.mark.parametrize('wrong_method', [False,True])
def test_receipt_rejects_late_peak_or_wrong_actual_method(entry,tmp_path,monkeypatch,wrong_method):
    from app.services import meal_prepared_artifacts

    report = tmp_path/'history-arrival.json'
    report.write_text(json.dumps({'native_report':'x'*20000}),encoding='utf8')
    expected_sha = hashlib.sha256(report.read_bytes()).hexdigest()
    actual_method = 'different-source' if wrong_method else entry.METHOD
    monkeypatch.setattr(meal_prepared_artifacts,'method_signature',lambda:actual_method)
    def measured():
        assert hashlib.sha256(report.read_bytes()).hexdigest() == expected_sha
        return {'peak':1 if wrong_method else entry.bootstrap.LIMIT+1,'current':1,'swap.current':0}
    monkeypatch.setattr(entry.bootstrap,'memory',measured)
    with pytest.raises(RuntimeError,match='source method|memory/swap'):
        entry.write_final(tmp_path,'arrival',True)
    footer = json.loads((tmp_path/'final-resource.json').read_bytes())
    assert footer['method_signature'] == actual_method and footer['report_sha256'] == expected_sha
    assert footer['memory_target_passed'] == wrong_method
    assert footer['measurement_complete'] != wrong_method
