"""Metrics cannot silently compare different inputs or claim load capacity."""
import pytest
from app.models import PlanRequest

from backend.scripts.planner_acceptance_matrix import CASES, matrix_request, summarize


@pytest.mark.parametrize("case", CASES)
def test_matrix_preserves_store_and_price_scope_without_mutating_base(case):
    base = PlanRequest(allowed_store_ids=["willys-local"], max_stores=2,
                       recipe_preferences={"mode": "complete"}).model_dump(mode="json")
    request = matrix_request(base, case)
    assert request.allowed_store_ids == ("willys-local",)
    assert request.max_stores == 2
    assert request.personal.allow_nutrition_estimates
    assert base["personal"] is None


def test_profiled_times_do_not_count_as_acceptance_and_queue_is_unknown():
    result = summarize([{"profiled": True, "wall_seconds": 999, "outcome": "PASS"},
                        {"profiled": False, "wall_seconds": 20, "outcome": "PASS"},
                        {"profiled": False, "wall_seconds": 40, "outcome": "BLOCKED"}])
    assert result["samples"] == 2 and result["successful"] == 1
    assert result["sample_p95_seconds"] == 40
    assert result["within_30_seconds"] == 1
    assert result["within_60_seconds"] == 2
    assert result["successful_within_60_seconds"] == 1
    assert result["queue_seconds"] is None and not result["p95_capacity_claim"]
