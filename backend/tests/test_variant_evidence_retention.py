"""Qualification keeps variant evidence for every candidate of a large library."""
from collections import OrderedDict
from types import SimpleNamespace
from unittest.mock import patch

from app.services import personal_planner as planner_module
from app.services.personal_planner import PersonalPlanner


def run_candidates(count, existing=0):
    recipes = [SimpleNamespace(id=f"r{n}", name=f"Rätt {n}", design=SimpleNamespace(content_source=None))
               for n in range(count)]
    qualified = {"basket": SimpleNamespace(stores=[], total=100), "trace_inputs": (None, None), "allocations": []}
    evidence = OrderedDict((("breakfast", f"b{n}"), object()) for n in range(existing))
    stub = SimpleNamespace(
        complete=True, include_content_pack=True, library_generation=None,
        request=SimpleNamespace(recipe_preferences=None),
        spec=SimpleNamespace(slots=[], profile=None, allow_nutrition_estimates=False),
        diagnostics=SimpleNamespace(pools=[], singleton_passed=0, reject=lambda *a: None),
        product_trace=SimpleNamespace(recipe=lambda *a: None),
        clean_recipe=lambda recipe, meal: recipe,
        basket=lambda slots, final: qualified,
        _check_nutrition=lambda *args: [{"values": {}}],
        variant_search_evidence=evidence, _recipe_id=lambda recipe: recipe.id, _prior_recipe_ids=None)
    meal = SimpleNamespace(meal_type="dinner", profile=None, diet=None,
                           limits=SimpleNamespace(active=False), recipe_choices=None)
    candidates = getattr(PersonalPlanner._candidates, "__wrapped__", PersonalPlanner._candidates)
    with (patch("app.services.recipe_library.meal_candidates", return_value=recipes),
          patch.object(planner_module, "MealSlot", lambda **kw: SimpleNamespace(**kw)),
          patch.object(planner_module, "merged_profile",
                       lambda *a: SimpleNamespace(exclusions=[], allergies=[])),
          patch.object(planner_module, "recipe_respects_diet", lambda *a, **k: True)):
        valid = candidates(stub, meal)
    return valid, evidence


def test_every_qualified_variant_keeps_its_evidence_beyond_2048():
    valid, evidence = run_candidates(2100, existing=30)
    assert len(valid) == 2100
    assert all(("dinner", f"r{n}") in evidence for n in range(2100))
    assert sum(key[0] == "breakfast" for key in evidence) == 30  # other meal types retained


def test_small_library_evidence_is_unchanged():
    valid, evidence = run_candidates(50)
    assert len(valid) == 50
    assert list(evidence) == [("dinner", f"r{n}") for n in range(50)]
