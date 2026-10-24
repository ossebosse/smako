"""Checkpointed legacy prefixes must equal independent complete trajectories."""

from collections import Counter
from itertools import product
from random import Random

import pytest
from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services.menu_optimizer import LibraryPrefixCheckpoint, MenuOptimizer


def pool(names="ABCDEFG", days=3):
    recipes = [
        Recipe(
            name=name,
            servings=1,
            ingredients=[RecipeIngredient(name=name, quantity=1, unit="g")],
            instructions=["Synthetic test"],
        )
        for name in names
    ]
    return [
        [MealSlot(id=f"d{day}", day=day, meal_type="dinner", recipe=recipe) for recipe in recipes]
        for day in range(1, days + 1)
    ]


def identity(result):
    slots, cost = result
    return tuple((s.id, s.recipe.name) for s in slots), cost


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("secondary", [False, True])
def test_every_completed_prefix_equals_an_independent_call(seed, secondary):
    random = Random(seed)
    rows = pool()
    prices = {
        names: random.randrange(1, 100)
        for length in range(1, 4)
        for names in product("ABCDEFG", repeat=length)
    }
    calls = Counter()
    mode = "independent"

    def evaluate(slots, *, final):
        calls[mode] += 1
        return prices[tuple(s.recipe.name for s in slots)]

    def accepts(slots, *, final):
        # Nontrivial rejection plus ties and non-additive complete basket prices.
        return len({s.recipe.name for s in slots}) == len(slots)

    def score(slots, value):
        return value, tuple(s.recipe.name for s in slots)

    def joint(groups, incumbent):
        return [
            (left, right, a, b)
            for left, right in ((0, 1), (0, 2), (1, 2))
            for a in reversed(groups[left])
            for b in reversed(groups[right])
        ]

    kwargs = {
        "evaluate": evaluate,
        "accepts": accepts,
        "score": score,
        "retention_score": score,
        "refinement_score": (
            lambda slots, value: (value // 10, tuple(s.recipe.name for s in slots))
        )
        if secondary
        else None,
        "joint_proposals": joint if secondary else None,
        "substitution_slot_limit": 2 if secondary else 0,
        "substitution_order": lambda slots, incumbent, index: prices[
            tuple(s.recipe.name for s in slots)
        ],
        "beam_width": 3,
        "fallback_beam_width": 8,
        "state_identity": lambda slots: tuple(s.recipe.name for s in slots),
    }
    optimizer, checkpoint, cohorts = MenuOptimizer(), LibraryPrefixCheckpoint(), []
    resumed = 0
    for generation, size in enumerate((3, 4, 5, 7), 1):
        cohorts.append((generation, [group[:size] for group in rows]))
        mode = "independent"
        expected = optimizer.optimize_library_slots(cohorts, **kwargs)
        mode = "checkpointed"
        trace = []
        actual = optimizer.optimize_library_slots(
            cohorts,
            **kwargs,
            search_trace=trace,
            _prefix_checkpoint=checkpoint,
            _prefix_context="fixed synthetic context",
        )
        assert identity(actual) == identity(expected)
        if generation > 1:
            resumed += 1
            row = next(r for r in trace if r["library_phase"] == "resumed_prefix")
            assert row["resumed_cohorts"] == generation - 1
        assert len(checkpoint.state[3]) <= 256
    assert resumed == 3
    assert calls["checkpointed"] < calls["independent"]


@pytest.mark.parametrize(
    "change", ["quantity", "instructions", "day", "meal_type", "order", "context"]
)
def test_changed_inputs_rebuild_the_independent_trajectory(change):
    rows, checkpoint, optimizer = pool("ABC", days=2), LibraryPrefixCheckpoint(), MenuOptimizer()
    surcharge = 0

    def evaluate(slots, *, final):
        return surcharge + sum(
            (ord(s.recipe.name) - 64) * s.recipe.ingredients[0].quantity
            + s.day
            + len(s.recipe.instructions)
            + (10 if s.meal_type == "breakfast" else 0)
            for s in slots
        )

    def score(slots, cost):
        return cost, tuple(s.recipe.name for s in slots)

    kwargs = {
        "evaluate": evaluate,
        "accepts": lambda slots, final: True,
        "score": score,
        "retention_score": score,
    }
    optimizer.optimize_library_slots(
        [(1, rows)], **kwargs, _prefix_checkpoint=checkpoint, _prefix_context="before"
    )
    context = "before"
    if change == "quantity":
        ingredient = rows[0][0].recipe.ingredients[0]
        rows[0][0].recipe.ingredients[0] = ingredient.model_copy(update={"quantity": 12})
    elif change == "instructions":
        rows[0][0].recipe.instructions.append("Changed preparation")
    elif change == "day":
        rows[0][0] = rows[0][0].model_copy(update={"day": 3})
    elif change == "meal_type":
        rows[0][0] = rows[0][0].model_copy(update={"meal_type": "breakfast"})
    elif change == "order":
        rows[0].reverse()
    else:
        context, surcharge = "changed owner, facts or private allocation", 123
    trace = []
    actual = optimizer.optimize_library_slots(
        [(1, rows)],
        **kwargs,
        search_trace=trace,
        _prefix_checkpoint=checkpoint,
        _prefix_context=context,
    )
    expected = optimizer.optimize_library_slots([(1, rows)], **kwargs)
    assert identity(actual) == identity(expected)
    assert not any(r["library_phase"] == "resumed_prefix" for r in trace)


def test_checkpoint_never_imports_terminal_refinement_into_a_later_substitution_path():
    rows, checkpoint, optimizer = pool("ABC", days=3), LibraryPrefixCheckpoint(), MenuOptimizer()

    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        if len(names) < 3:
            return sum(ord(name) - 64 for name in names)
        if names == ("A", "A", "A"):
            return 10
        if names.count("B") == 2 and names.count("A") == 1:
            return 4
        if "B" not in names and "C" in names:
            return {1: 9, 2: 8, 3: 1}[names.count("C")]
        return 100

    def score(slots, cost):
        return cost, tuple(s.recipe.name for s in slots)

    kwargs = {
        "evaluate": evaluate,
        "accepts": lambda slots, final: True,
        "score": score,
        "retention_score": score,
        "beam_width": 1,
    }
    cohorts = [(1, [group[:2] for group in rows])]
    first = optimizer.optimize_library_slots(
        cohorts, **kwargs, _prefix_checkpoint=checkpoint, _prefix_context="same"
    )
    assert identity(first) == ((("d1", "A"), ("d2", "B"), ("d3", "B")), 4)
    # AAA is the unfinalized trajectory. Refinement's ABB winner is a separate
    # completed candidate; importing it would prevent three later C moves.
    assert identity(checkpoint.state[0]) == ((("d1", "A"), ("d2", "A"), ("d3", "A")), 10)
    repeated = optimizer.optimize_library_slots(
        cohorts, **kwargs, _prefix_checkpoint=checkpoint, _prefix_context="same"
    )
    assert identity(repeated) == identity(first)
    larger = cohorts + [(2, rows)]
    independent = optimizer.optimize_library_slots(larger, **kwargs)
    assert identity(independent) == ((("d1", "C"), ("d2", "C"), ("d3", "C")), 1)
    resumed = optimizer.optimize_library_slots(
        larger, **kwargs, _prefix_checkpoint=checkpoint, _prefix_context="same"
    )
    assert identity(resumed) == identity(independent)
    wrong_seed = optimizer.optimize_library_slots(
        [(0, [[s] for s in first[0]]), (2, rows)], **kwargs
    )
    assert wrong_seed[1] == 4  # A prior winner as seed is demonstrably insufficient.


def test_changed_qualification_seed_objects_and_shorter_prefix_do_not_resume():
    from decimal import Decimal

    from app.services.recipe_candidate_validator import recipe_id

    rows, checkpoint, optimizer = pool("AB", days=2), LibraryPrefixCheckpoint(), MenuOptimizer()

    def evaluate(slots, *, final):
        return Decimal("1.25") * len(slots)

    def score(slots, cost):
        return cost, tuple(s.recipe.name for s in slots)

    kwargs = {
        "evaluate": evaluate,
        "accepts": lambda slots, final: True,
        "score": score,
        "retention_score": score,
    }
    key = ((rows[0][0].id, recipe_id(rows[0][0].recipe)),)
    first = Decimal("1.25")
    optimizer.optimize_library_slots(
        [(1, rows)],
        **kwargs,
        initial_evaluations={key: first},
        _prefix_checkpoint=checkpoint,
        _prefix_context="same",
    )
    second = Decimal("1.25")
    assert second is not first
    trace = []
    optimizer.optimize_library_slots(
        [(1, rows)],
        **kwargs,
        initial_evaluations={key: second},
        search_trace=trace,
        _prefix_checkpoint=checkpoint,
        _prefix_context="same",
    )
    assert not any(r["library_phase"] == "resumed_prefix" for r in trace)
    bigger = [(1, rows), (2, rows)]
    optimizer.optimize_library_slots(
        bigger,
        **kwargs,
        initial_evaluations={key: second},
        _prefix_checkpoint=checkpoint,
        _prefix_context="same",
    )
    trace = []
    optimizer.optimize_library_slots(
        [(1, rows)],
        **kwargs,
        initial_evaluations={key: second},
        search_trace=trace,
        _prefix_checkpoint=checkpoint,
        _prefix_context="same",
    )
    assert not any(r["library_phase"] == "resumed_prefix" for r in trace)


def test_custom_optimizer_never_resumes_a_checkpoint():
    class Custom(MenuOptimizer):
        pass

    rows, checkpoint, optimizer = pool("AB", days=2), LibraryPrefixCheckpoint(), Custom()
    kwargs = {
        "evaluate": lambda slots, final: len(slots),
        "accepts": lambda slots, final: True,
        "score": lambda slots, cost: cost,
        "retention_score": lambda slots, cost: cost,
    }
    for _ in range(2):
        trace = []
        optimizer.optimize_library_slots(
            [(1, rows)],
            **kwargs,
            search_trace=trace,
            _prefix_checkpoint=checkpoint,
            _prefix_context="same",
        )
        assert checkpoint.state is None
        assert not any(r["library_phase"] == "resumed_prefix" for r in trace)
