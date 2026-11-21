"""Owner decision 2026-11-20: dinners carry the dish's real name; only names change."""
import copy
import json
import sys
from pathlib import Path

import pytest
from app.services.recipe_library import current_recipes

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/recipe_layer"))
import rename_core_dinners_20261121 as core
import rename_dinners_20261120 as names


@pytest.fixture(scope="module")
def review():
    return json.loads((names.REPORT / "library-transition.json").read_bytes())


def test_the_rename_is_a_complete_bound_transition(review):
    names.checked_transition(review)
    broken = copy.deepcopy(review)
    broken["corrected"].pop()
    with pytest.raises(AssertionError):
        names.checked_transition(broken)


def test_current_dinners_carry_the_reviewed_names():
    overrides = json.loads((names.REPORT / "recipe-names.json").read_bytes())
    pending = set(json.loads((names.REPORT / "library-transition.json").read_bytes())["core_library_names_pending"])
    current = {r.name for r in current_recipes() if "dinner" in r.design.meal_types}
    assert not (set(overrides) - pending) & current
    assert {"Pressstekta kycklinglår med potatis och tomat", "Spätzle med kyckling och brynt svamp",
            "Peinirli – öppna degbåtar med nötfärs"} <= current
    assert not any("inspirerad" in name for name in current)


def test_core_library_names_follow_in_their_own_transition():
    review = json.loads((core.REPORT / "library-transition.json").read_bytes())
    core.checked_transition(review)
    overrides = json.loads((core.REPORT / "recipe-names.json").read_bytes())
    pending = set(json.loads((names.REPORT / "library-transition.json").read_bytes())["core_library_names_pending"])
    assert set(overrides) == pending
    current = {r.name for r in current_recipes()}
    assert not set(overrides) & current and set(overrides.values()) <= current
