"""Metrics cannot silently compare different inputs or claim load capacity."""
import hashlib
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.config import Settings
from app.models import PlanRequest

from backend.scripts import planner_acceptance_matrix as matrix
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


# --- Full-library reference contract (review 2026-10-18, remaining P2) ---
INPUTS = {"sha256": {"combined-prices.json": "a"}, "now": "2026-10-18T12:00:00+02:00",
          "request_sha256": "r", "facts_version": "f", "universe_id": "u"}


def reference(**changes):
    report = {"schema": "smako-planner-acceptance-v1", "inputs": dict(INPUTS), "uncapped": True,
              "reference_contract": matrix.FULL_LIBRARY_REFERENCE_CONTRACT,
              "search_limits": {"seed": 0, "refinement": 0, "seed_variant_shortlist": False,
                                "substitution": 0},
              "records": [{"outcome": "PASS", "paid": 100.0}]}
    report.update(changes)
    return report


def test_full_library_settings_match_the_contract():
    settings = matrix.full_library_search_limits(Settings())
    assert (settings.library_seed_pool_limit, settings.library_refinement_pool_limit,
            settings.library_seed_variant_shortlist,
            settings.library_substitution_pool_limit) == (0, 0, False, 0)


def test_current_full_library_reference_is_accepted():
    matrix.validate_full_library_reference(reference(), dict(INPUTS))
    # Untagged reports must still explicitly state all four settings.
    untagged = reference()
    del untagged["reference_contract"]
    matrix.validate_full_library_reference(untagged, dict(INPUTS))


@pytest.mark.parametrize("change, message", [
    # The preserved Lund standard report of the previous version: uncapped,
    # same inputs, but no shortlist flag (it kept four variants per base).
    ({"search_limits": {"seed": 0, "refinement": 0}}, "lacks 'seed_variant_shortlist'"),
    ({"search_limits": {"seed": 0, "refinement": 0, "seed_variant_shortlist": True}}, "expected False"),
    ({"search_limits": {"seed": 0, "refinement": 0, "seed_variant_shortlist": 0}}, "expected False"),
    ({"search_limits": {"seed": 0, "refinement": 0, "seed_variant_shortlist": None}}, "expected False"),
    ({"search_limits": {"seed": 40, "refinement": 0, "seed_variant_shortlist": False}}, "'seed'"),
    ({"search_limits": {"seed": False, "refinement": 0, "seed_variant_shortlist": False}}, "'seed'"),
    ({"search_limits": {"seed": 0, "refinement": 90, "seed_variant_shortlist": False}}, "'refinement'"),
    ({"search_limits": {"seed_variant_shortlist": False}}, "lacks 'seed'"),
    ({"search_limits": {"seed": 0, "refinement": 0, "seed_variant_shortlist": False}},
     "lacks 'substitution'"),
    ({"search_limits": {**matrix.FULL_LIBRARY_SEARCH_LIMITS, "substitution": 160}},
     "'substitution'"),
    ({"search_limits": {**matrix.FULL_LIBRARY_SEARCH_LIMITS, "substitution": False}},
     "'substitution'"),
    ({"reference_contract": "smako-full-library-reference-v1"}, "unknown reference contract"),
    ({"search_limits": None}, "no search_limits"),
    ({"uncapped": False}, "not an --uncapped run"),
    ({"uncapped": "true"}, "not an --uncapped run"),
    ({"inputs": {**INPUTS, "facts_version": "other"}}, "inputs differ"),
    ({"reference_contract": "smako-full-library-reference-v0"}, "unknown reference contract"),
    ({"schema": "smako-planner-acceptance-v0"}, "unknown report schema"),
    ({"records": []}, "no records"),
])
def test_incomplete_or_capped_reference_is_rejected(change, message):
    with pytest.raises(ValueError, match=message.replace("(", r"\(")):
        matrix.validate_full_library_reference(reference(**change), dict(INPUTS))


def run_cli_with_reference(tmp_path, monkeypatch, build_reference):
    """Run the real CLI on tiny frozen inputs; the planner must never be built."""
    monkeypatch.setenv("RECIPE_PREPARATION_CACHE_ROOT", "unset-by-test")  # main() overwrites it
    raw = {"combined-prices.json": b"{}", "combined-request.json": b"{}",
           "combined-facts.json": json.dumps({"facts": [], "facts_version": "fv"}).encode()}
    inputs_dir = tmp_path / "inputs"
    inputs_dir.mkdir()
    for name, data in raw.items():
        (inputs_dir / name).write_bytes(data)
    now = "2026-10-18T12:00:00+02:00"
    manifest = {"now": now, "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()}}
    (inputs_dir / "matrix-inputs.json").write_text(json.dumps(manifest))
    prepared = SimpleNamespace(universe=SimpleNamespace(universe_id="u1"))
    request = PlanRequest(recipe_preferences={"mode": "complete"})
    inputs = {"sha256": manifest["sha256"], "now": now,
              "request_sha256": matrix.digest(request.model_dump(mode="json")),
              "facts_version": "fv", "universe_id": "u1"}
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(build_reference(inputs)))
    argv = ["planner_acceptance_matrix", "--matrix", "--inputs", str(inputs_dir),
            "--output", str(tmp_path / "out"), "--matrix-case", "standard",
            "--repeat", "1", "--uncapped-reference", str(path)]
    with (patch.object(sys, "argv", argv),
          patch.object(matrix.PreparedPriceUniverseArtifact, "model_validate_json",
                       return_value=SimpleNamespace(restore=lambda: prepared)),
          patch.object(matrix, "FactsCollection", return_value=SimpleNamespace(version="fv")),
          patch.object(matrix, "matrix_request", return_value=request),
          patch.object(matrix, "PersonalPlanner", side_effect=AssertionError("planner constructed"))):
        matrix.main()


def test_legacy_reference_is_rejected_by_the_cli_before_planning(tmp_path, monkeypatch, capsys):
    def legacy(inputs):
        report = reference(inputs=inputs, search_limits={"seed": 0, "refinement": 0})
        del report["reference_contract"]
        return report

    with pytest.raises(SystemExit) as exit_info:
        run_cli_with_reference(tmp_path, monkeypatch, legacy)
    assert exit_info.value.code == 2
    assert "lacks 'seed_variant_shortlist'" in capsys.readouterr().err


def test_correct_reference_passes_the_cli_gate(tmp_path, monkeypatch):
    # Validation passes, so the run proceeds to planner construction (stubbed).
    with pytest.raises(AssertionError, match="planner constructed"):
        run_cli_with_reference(tmp_path, monkeypatch, lambda inputs: reference(inputs=inputs))
