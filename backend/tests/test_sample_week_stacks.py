"""Test-only profiler contracts; never run a real plan or contact a server here."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

script = Path(__file__).parents[2] / "scripts/recipe_layer/sample_week_stacks.py"
spec = importlib.util.spec_from_file_location("sample_week_stacks", script)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def request():
    return {"postal_code": "22350", "recipes": 5, "servings": 2, "max_stores": 2,
        "memberships": [], "diversity_mode": "varied", "purchase_planning_mode": "estimated",
        "allow_nutrition_estimates": True,
        "recipe_preferences": {"mode": "complete", "cuisines": [], "min_ingredients": 10,
            "max_ingredients": 15, "adaptation": "approved"},
        "personal": {"allow_nutrition_estimates": True, "pantry_revision": 0,
            "meals": [{"meal_type": "dinner", "count": 5, "servings": 2,
                "limits": {"min_protein_g": 0, "min_carbs_g": 0, "min_fat_g": 0, "max_kcal": 4000}}]}}


def test_extraction_preserves_submitted_payload_and_omits_session_or_saved_plan(tmp_path):
    payload = request()
    report = {"case": "unrestricted-varied", "session": "private-secret-test-marker",
        "result": {"private_stock": "empty", "request": payload,
            "response": {"owner_actor_hash": "must-not-be-copied"}}}
    source, destination = tmp_path / "source.json", tmp_path / "request.json"
    source.write_text(json.dumps(report), encoding="utf-8")
    result = runner.extract_request(source, destination)
    assert result["request"] == payload
    assert "max_minutes" not in result["request"]["recipe_preferences"]
    assert "varied_budget_percent" not in result["request"]  # Preserve original default meaning.
    assert "private-secret-test-marker" not in destination.read_text()
    assert "must-not-be-copied" not in destination.read_text()
    assert result["request_sha256"] == runner._digest(payload)
    with pytest.raises(FileExistsError):
        runner.extract_request(source, destination)


@pytest.mark.parametrize("field,value", [("slots", [{}]), ("product_locks", {"x": "y"}), ("pantry_revision", 1)])
def test_profiler_does_not_silently_replace_actual_private_or_locked_inputs(field, value):
    payload = request()
    payload["personal"][field] = value
    with pytest.raises(ValueError):
        runner.validate_request(payload)


class Frame:
    def __init__(self, path, function, line, parent=None):
        self.f_code = SimpleNamespace(co_filename=path, co_name=function)
        self.f_lineno, self.f_back = line, parent

    @property
    def f_locals(self):
        raise AssertionError("Profiler must never inspect local values")


def test_only_code_locations_are_aggregated_and_unique_stacks_are_bounded(monkeypatch):
    root = Frame("C:/Users/private/backend/app/services/personal_planner.py", "_create", 10)
    leaf = Frame("C:/Python/re.py", "match", 12, root)
    frames = {999999999: leaf}
    monkeypatch.setattr(runner.sys, "_current_frames", lambda: frames)
    sampler = runner.StackSampler(maximum_stacks=1)
    sampler.capture()
    sampler.capture()
    leaf.f_lineno += 1
    sampler.capture()
    report = sampler.report()
    assert report["selected_thread_samples"] == 3
    assert report["sample_cycles"] == 3
    assert report["overflow_samples"] == 1
    assert report["stacks"][0]["samples"] == 2
    assert report["inclusive_functions"][0]["samples"] == 2
    assert report["locals_collected"] is False
    serialized = json.dumps(report)
    assert "C:/Users/private" not in serialized
    assert "backend/app/services/personal_planner.py" in serialized
    assert "f_locals" not in serialized


def test_sampler_thread_stops_on_error_without_swallowing_original_exception(monkeypatch):
    root = Frame("/srv/app/backend/app/services/menu_optimizer.py", "_optimize_slots", 3)
    monkeypatch.setattr(runner.sys, "_current_frames", lambda: {999999999: root})
    sampler = runner.StackSampler(interval_seconds=0.01)
    with pytest.raises(RuntimeError, match="original"), sampler:
        # The stop event wait permits at least one sample without busy work.
        sampler._stop.wait(0.05)
        raise RuntimeError("original")
    assert not sampler._thread.is_alive()
    assert sampler.sample_cycles >= 1
    assert sampler.report()["interval_observed_median_seconds"] > 0
