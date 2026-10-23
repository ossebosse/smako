"""Small generated menus must not lose a cheaper non-local combination."""
from itertools import product

import pytest
from app.errors import IncompleteBasketError

from backend.tests.test_incremental_library_search import options, run


def test_complete_three_way_move_survives_bad_prefixes_and_single_or_pair_costs():
    trace = []
    def evaluate(slots, *, final):
        names = ''.join(s.recipe.name for s in slots)
        if len(names) < 3:
            return 1 if set(names) == {'A'} else 1000
        return 3 if set(names) == {'B', 'C', 'D'} else 100
    chosen, cost = run([(1, options('ABCD', days=3))], evaluate=evaluate,
                      unordered_small_pool_limit=20, search_trace=trace)
    assert cost == 3 and {s.recipe.name for s in chosen} == {'B', 'C', 'D'}
    assert trace[0]['library_phase'] == 'exhaustive'
    assert trace[0]['state_space'] == trace[0]['proposals'] == 20
    assert trace[0]['beam_pruned'] == 0


def test_different_meal_types_are_not_interchanged_and_every_state_matches_cartesian_reference():
    groups = options('ABC', days=3)
    for slot in groups[-1]:
        slot.meal_type = 'snack'
    def evaluate(slots, *, final):
        return {('A', 'C', 'B'): 1}.get(tuple(s.recipe.name for s in slots), 10)
    accepts = lambda slots, final: slots[-1].meal_type == 'snack'
    _, cost = run([(1, groups)], evaluate=evaluate, accepts=accepts,
                  unordered_small_pool_limit=18)
    reference = min(evaluate(slots, final=True) for slots in product(*groups) if accepts(slots, True))
    assert cost == reference == 1


def test_constraints_and_failed_whole_baskets_remain_blocking():
    def evaluate(slots, *, final):
        if any(s.recipe.name == 'B' for s in slots):
            raise IncompleteBasketError('Missing product evidence')
        return sum(1 if s.recipe.name == 'C' else 5 for s in slots)
    chosen, cost = run([(1, options('ABCD'))], evaluate=evaluate,
        accepts=lambda slots, final: all(s.recipe.name != 'D' for s in slots),
        unordered_small_pool_limit=10)
    assert cost == 2 and all(s.recipe.name == 'C' for s in chosen)


def test_large_pool_keeps_bounded_search_before_any_enumeration():
    trace = []
    run([(1, options('ABCDE', days=3))], evaluate=lambda slots, final: len(slots),
        unordered_small_pool_limit=34, search_trace=trace)
    assert not any(r.get('library_phase') == 'exhaustive' for r in trace)


def test_no_feasible_complete_menu_is_not_reported_as_a_search_success():
    with pytest.raises(IncompleteBasketError):
        run([(1, options('AB'))], evaluate=lambda slots, final: 1,
            accepts=lambda slots, final: False, unordered_small_pool_limit=3)


def test_week_enumeration_does_not_claim_global_product_or_nutrition_optimality():
    from app.services.complete_recipes import completed_search_outcome

    result = completed_search_outcome({'search': [{'library_phase': 'exhaustive', 'beam_pruned': 0}]})
    assert result['search_budget']['week_search_method'] == 'exhaustive_week_combinations'
    assert not result['global_optimum_proven']
