"""Stable checkpoint paths and retention of a completed cheaper prefix."""
from types import SimpleNamespace

from app.services.library_search_cohorts import merged_library_cohorts
from app.services.meal_library_content import identity

from backend.tests.test_incremental_library_search import options, run


def library(size):
    recipes, generations = [], {}
    for index in range(size):
        recipe = SimpleNamespace(design=SimpleNamespace(base_id=f'r{index}', version='1.0.0', variant_id='base'))
        recipes.append(recipe)
        generations[identity(recipe)] = 1 if index < 100 else 2 if index < 200 else 3 if index < 262 else 4 + (index - 262) // 500
    slots = [[SimpleNamespace(recipe=r) for r in recipes] for _ in range(3)]
    return recipes, generations, slots


def test_nested_libraries_follow_identical_completed_checkpoint_paths():
    previous = None
    for size in (262, 1000, 2000, 5000):
        recipes, generations, slots = library(size)
        cohorts, completed, prefixes = merged_library_cohorts(slots, recipes, generations, first_generation=2)
        assert prefixes[-1] == size
        assert {prefixes[index] for index in completed} == {n for n in (262, 1000, 2000, 5000) if n <= size}
        if previous:
            smaller, smaller_prefixes = previous
            assert tuple(n for n in prefixes if n <= smaller) == smaller_prefixes
        for (_, groups), prefix in zip(cohorts, prefixes, strict=True):
            assert all(len(group) == prefix for group in groups)
        previous = size, prefixes


def test_completed_prefix_survives_later_shortlist_excluding_its_winner():
    prices = {
        ('A',): 1, ('B',): 3, ('C',): 2,
        ('A', 'A'): 10, ('A', 'B'): 15, ('B', 'A'): 15, ('B', 'B'): 2,
        ('C', 'A'): 8, ('A', 'C'): 8, ('C', 'C'): 6, ('B', 'C'): 12, ('C', 'B'): 12,
    }
    def evaluate(slots, *, final):
        return prices[tuple(s.recipe.name for s in slots)]
    def refinement(groups):
        return [[s for s in group if len(group) <= 2 or s.recipe.name != 'B'] for group in groups]
    cohorts = [(1, options('A')), (2, options('AB')), (3, options('ABC'))]
    assert [run(cohorts[:n], evaluate=evaluate, refinement_selector=refinement,
                completed_prefix_indexes=range(n))[1] for n in (1, 2, 3)] == [10, 2, 2]
    prices[('B', 'B')] = 20
    assert run(cohorts, evaluate=evaluate, refinement_selector=refinement,
               completed_prefix_indexes=range(3))[1] == 6


def test_small_exact_prefix_is_retained_when_later_pool_exceeds_enumeration_budget():
    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        return {('A', 'A', 'A'): 10, ('B', 'C', 'D'): 2}.get(names, 50)
    chosen, cost = run([(1, options('ABCD', days=3)), (2, options('ABCDE', days=3))],
        evaluate=evaluate, unordered_small_pool_limit=20, completed_prefix_indexes={0, 1},
        refinement_selector=lambda groups: [[s for s in group if s.recipe.name in 'AE'] for group in groups])
    assert cost == 2 and {s.recipe.name for s in chosen} == {'B', 'C', 'D'}


def test_checkpoint_with_no_new_qualified_recipe_still_completes_the_pending_prefix():
    prices = {
        ('A',): 1, ('B',): 3, ('C',): 2,
        ('A', 'A'): 10, ('A', 'B'): 15, ('B', 'A'): 15, ('B', 'B'): 2,
        ('C', 'A'): 8, ('A', 'C'): 8, ('C', 'C'): 6, ('B', 'C'): 12, ('C', 'B'): 12,
    }
    def refinement(groups):
        return [[s for s in group if len(group) <= 2 or s.recipe.name != 'B'] for group in groups]
    _, cost = run([(1, options('A')), (2, options('AB')), (3, options('AB')), (4, options('ABC'))],
        evaluate=lambda slots, final: prices[tuple(s.recipe.name for s in slots)],
        completed_prefix_indexes={2, 3}, refinement_selector=refinement)
    assert cost == 2
