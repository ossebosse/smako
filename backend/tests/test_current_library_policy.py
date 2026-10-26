"""Opt-in deadline covers inner work and save without changing legacy policy."""
from types import SimpleNamespace

import pytest
from app.api.plan import _with_current_deadline
from app.config import Settings
from app.models.ingredient import NormalizedIngredient
from app.services import plan_jobs, recipe_library
from app.services.basket_optimizer import BasketOptimizer
from app.services.personal_policy import PolicyConflict

from backend.tests.test_optimizer import product, store


def test_current_policy_is_explicit_and_legacy_remains_default():
    assert Settings().library_search_policy=='legacy'
    assert not Settings().library_merge_generations
    assert Settings(library_search_policy='smako-current-library-v2').library_search_policy=='smako-current-library-v2'


def test_nested_deadline_cannot_extend_and_inner_basket_stops(monkeypatch):
    clock=[0]
    monkeypatch.setattr(plan_jobs,'monotonic',lambda:clock[0])
    with plan_jobs.planning_deadline(1),plan_jobs.planning_deadline(100):
        clock[0]=2
        with pytest.raises(plan_jobs.PlanningDeadlineExceeded):
            BasketOptimizer(prune_dominated_stores=True).optimize(
                [NormalizedIngredient(canonical_name='ris',required_quantity=100,unit='g')],
                {'ris':[product('ris','rice','a',500,10)]},[store('a')],1)
    plan_jobs.check_cancelled()  # Context reset, no deadline left on next request.


@pytest.mark.asyncio
async def test_deadline_includes_save_and_escapes_valueerror_retries(monkeypatch):
    clock=[0]
    monkeypatch.setattr(plan_jobs,'monotonic',lambda:clock[0])
    async def save_finishes_late():
        clock[0]=61
        return 'saved'
    with pytest.raises(PolicyConflict) as error:
        await _with_current_deadline(SimpleNamespace(library_search_policy='smako-current-library-v2'),save_finishes_late)
    assert error.value.code=='SEARCH_INCOMPLETE'
    assert not issubclass(plan_jobs.PlanningDeadlineExceeded,ValueError)
    assert await _with_current_deadline(SimpleNamespace(library_search_policy='legacy'),save_finishes_late)=='saved'


def test_current_registered_value_does_not_require_historical_materialization(monkeypatch):
    recipe_library.reset_library_caches()
    current=recipe_library.current_recipes()[0]
    with monkeypatch.context() as patch:
        patch.setattr(recipe_library,'_issued_index',lambda *args:pytest.fail('current recipe must use exact current index'))
        assert recipe_library.validate_recipe_design(current)
        assert recipe_library.share_issued_recipe_parts(current).model_dump()==current.model_dump()
        changed=current.model_copy(deep=True)
        changed.instructions.append('Changed after issuance')
        with pytest.raises(ValueError):recipe_library.validate_recipe_design(changed)
    recipe_library.reset_library_caches()


@pytest.mark.asyncio
async def test_current_deadline_expires_during_admission_wait(monkeypatch):
    import asyncio

    from app.services import plan_jobs
    monkeypatch.setattr(plan_jobs,'remaining_planning_seconds',lambda:.01)
    gate=asyncio.Event()
    async def queued():
        await gate.wait()
        pytest.fail('expired request must not enter its worker')
    with pytest.raises(PolicyConflict) as error:
        await _with_current_deadline(SimpleNamespace(library_search_policy='smako-current-library-v2'),queued)
    assert error.value.code=='SEARCH_INCOMPLETE'
