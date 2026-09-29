"""Search proofs must be conservative and never stand in for final audit."""

from itertools import product
from types import SimpleNamespace as NS

import pytest
from app.models.personal import PortionLimits
from app.services.nutrition_search_bounds import build_nutrition_bounds


def bounds(values=((10, 20), (1, 2)), goal=30, **kwargs):
    slots = [NS(id="dinner-1", recipe=NS(name="synthetic", servings=2))]
    rows = [
        {
            "name": key,
            "purchase_key": key,
            "source": "dinner-1",
            "quantity": 200,
            "original_quantity": 200,
            "unit": "g",
        }
        for key in ("a", "b")
    ]
    candidates = {
        key: [NS(store_id="one", product_id=str(i), protein=p) for i, p in enumerate(proteins)]
        for key, proteins in zip(("a", "b"), values, strict=True)
    }
    evidence = lambda c, *_: NS(
        nutrition={"protein_g": c.protein},
        nutrition_unit="g",
        nutrition_basis="per 100 g",
        nutrition_preparation="as_sold",
    )
    return build_nutrition_bounds(
        slots,
        kwargs.pop("rows", rows),
        candidates,
        kwargs.pop("allocations", []),
        meal_limits=lambda _: PortionLimits(min_protein_g=goal),
        evidence=kwargs.pop("evidence", evidence),
    ), candidates


def test_relaxed_upper_and_lower_cover_every_combination():
    bound, _ = bounds()
    lower, upper = bound.intervals()
    for a, b in product((10, 20), (1, 2)):
        assert lower[0] <= a + b <= upper[0]
    assert bound.violations()[0]["upper"] == 22
    assert bound.violations()[0]["shortfall"] == 8


def test_viable_domain_survives_but_impossible_partial_domain_is_pruned():
    bound, candidates = bounds(goal=21)
    assert not bound.violations()
    assert bound.violations({**candidates, "a": candidates["a"][:1]})
    assert not bound.violations({**candidates, "a": candidates["a"][1:]})


@pytest.mark.parametrize(
    "bad",
    [
        None,
        NS(
            nutrition={"protein_g": 99},
            nutrition_unit="ml",
            nutrition_basis="per 100 ml",
            nutrition_preparation="as_sold",
        ),
        NS(
            nutrition={"protein_g": float("nan")},
            nutrition_unit="g",
            nutrition_basis="per 100 g",
            nutrition_preparation="as_sold",
        ),
    ],
)
def test_missing_incompatible_or_nonfinite_evidence_cannot_prove_failure(bad):
    assert bounds(evidence=lambda *_: bad)[0] is None


def test_pantry_or_consumed_history_use_existing_calculation():
    assert bounds(allocations=[{"quantity": 20}])[0] is None
    row = {
        "name": "a",
        "purchase_key": "a",
        "source": "dinner-1",
        "quantity": 100,
        "original_quantity": 200,
        "unit": "g",
    }
    assert bounds(rows=[row])[0] is None


def test_near_boundary_is_not_falsely_pruned_or_approved():
    bound, _ = bounds(values=((19.9999999999,), (10,)), goal=30)
    assert not bound.violations()  # Ordinary strict final check remains necessary.


def test_compiled_class_filter_matches_independent_domain_bounds():
    bound, candidates = bounds(goal=21)
    keys = list(candidates)
    choices = [[[c] for c in candidates[k]] for k in keys]
    compiled = bound.compile_choices(keys, choices)
    for indices in product(range(2), repeat=2):
        narrowed = {k: choices[n][indices[n]] for n, k in enumerate(keys)}
        assert compiled(indices) == bool(bound.violations(narrowed))
