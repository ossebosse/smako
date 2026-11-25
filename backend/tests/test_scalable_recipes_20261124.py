"""Owner decision 2026-11-24: recipes with reviewed ranges get scaled siblings for nutrition limits."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models.personal import PortionLimits
from app.services import scalable_recipes as sr
from app.services.meal_library_content import validate_pack_bytes
from app.services.planning_rules import PlanningRules
from app.services.recipe_library import _structural_check, content_hash

PILOT = Path(__file__).parents[1] / "app/data/recipes/incoming/scalable-pilot-20261124/pack.json"


@pytest.fixture(scope="module")
def pilot():
    checked = validate_pack_bytes(PILOT.read_bytes(), label="pilot")
    assert checked["rejections"] == []
    return {f"{r.design.base_id}:{r.design.variant_id}": r for r in checked["recipes"]}


def test_a_recipe_with_main_and_side_ranges_gets_scaled_siblings_closest_first(pilot):
    recipe = pilot["smako-dinner-chickpea-potato-skillet:base"]
    siblings = sr.scaled_versions(recipe)
    assert [(s.design.variant_id, s.design.scale_steps) for s in siblings] == [
        ("base-m125s100", 3), ("base-m100s70", 6), ("base-m150s100", 6), ("base-m125s70", 9)]
    assert [s.design.scale_steps for s in siblings] == sorted(s.design.scale_steps for s in siblings)
    original = {i.name: i for i in recipe.ingredients}
    for s in siblings:
        _structural_check(s)  # component amounts still add up, every amount inside the reviewed range
        assert s.design.scaled_from == "base" and s.design.content_sha256 == content_hash(s)
        assert s.design.base_id == recipe.design.base_id and s.design.version == recipe.design.version
        assert s.instructions == recipe.instructions
        for i in s.ingredients:
            o = original[i.name]
            assert (i.quantity_min, i.quantity_max, i.quantity_step) == (o.quantity_min, o.quantity_max, o.quantity_step)
            if i.role not in ("primary", "side"):
                assert i.quantity == o.quantity
    more = siblings[0]
    assert {i.name: i.quantity for i in more.ingredients}["kikärtor"] == 300  # 240 g * 1.25 on the 20 g grid
    lighter = siblings[1]
    assert {i.name: i.quantity for i in lighter.ingredients}["potatis"] == 280  # the side's reviewed minimum


def test_main_only_recipes_and_recipes_without_ranges(pilot):
    tofu = sr.scaled_versions(pilot["smako-dinner-potato-tofu-cabbage-pan:base"])
    # 300 g * 1.25 = 375 g rounds down on the 20 g grid; the second stops at the reviewed 440 g.
    assert [(s.design.variant_id, {i.name: i.quantity for i in s.ingredients}["tofu"]) for s in tofu] == [
        ("base-m120s100", 360), ("base-m147s100", 440)]
    fixed = pilot["smako-dinner-potato-tofu-cabbage-pan:base"].model_copy(update={"ingredients": [
        i.model_copy(update={"quantity_min": i.quantity, "quantity_max": i.quantity})
        for i in pilot["smako-dinner-potato-tofu-cabbage-pan:base"].ingredients]})
    assert sr.scaled_versions(fixed) == [] and not sr.is_scalable(fixed)
    # Ranges without the scaling review (older flexible families) are never scaled.
    unreviewed = pilot["smako-dinner-potato-tofu-cabbage-pan:base"]
    unreviewed = unreviewed.model_copy(update={"design": unreviewed.design.model_copy(update={"scaling": None})})
    assert sr.scaled_versions(unreviewed) == []
    assert sr.scaled_versions(tofu[0]) == []  # never a sibling of a sibling


def test_with_scaled_versions_keeps_the_originals_first(pilot):
    recipes = list(pilot.values())
    expanded = sr.with_scaled_versions(recipes)
    assert expanded[:len(recipes)] == recipes
    ids = [f"{r.design.base_id}:{r.design.version}:{r.design.variant_id}" for r in expanded]
    assert len(ids) == len(set(ids)) and all(sr.is_scaled(r) for r in expanded[len(recipes):])


def test_only_meals_with_nutrition_limits_get_scaled_recipes():
    assert not sr.nutrition_limited(SimpleNamespace(limits=PortionLimits()))
    assert not sr.nutrition_limited(SimpleNamespace(limits=PortionLimits(max_weight_g=600)))
    assert sr.nutrition_limited(SimpleNamespace(limits=PortionLimits(min_protein_g=35)))
    assert sr.nutrition_limited(SimpleNamespace(limits=PortionLimits(max_kcal=700)))
    assert PlanningRules().scaled_step_kr == 2


def test_seasonings_follow_the_main_ingredient_only_in_its_component():
    """Owner decision 2026-11-25."""
    from app.services.recipe_authoring import standardize
    from backend.tests.test_recipe_authoring import VOCABULARY, _source

    source = _source()
    for component in source["recipes"][0]["components"]:
        for item in component["ingredients"]:
            if component["id"] == "c1" and item["name"] in ("citronjuice", "vitlök", "salt"):
                item["follows"] = "kyckling"
    pack, _ = standardize(source, VOCABULARY, reviewed_at="2026-11-25")
    [recipe] = validate_pack_bytes(json.dumps(pack).encode())["recipes"]
    more = max(sr.scaled_versions(recipe), key=lambda s: {i.name: i.quantity for i in s.ingredients}["kyckling"])
    _structural_check(more)
    before = {i.name: i.quantity for i in recipe.ingredients}
    after = {i.name: i.quantity for i in more.ingredients}
    factor = after["kyckling"] / before["kyckling"]
    assert after["citronjuice"] == pytest.approx(before["citronjuice"] * factor, abs=0.5)
    assert after["vitlök"] == pytest.approx(before["vitlök"] * factor, abs=0.5)
    assert after["rapsolja"] == before["rapsolja"] and after["oregano"] == before["oregano"]  # not followers
    salt_c1 = next(a.quantity for c in recipe.design.components if c.id == "c1" for a in c.amounts if a.ingredient_key == "salt|as_sold")
    assert after["salt"] == pytest.approx(before["salt"] + salt_c1 * (factor - 1), abs=0.5)


def test_two_main_ingredients_never_give_two_siblings_the_same_identity(pilot):
    recipe = pilot["smako-dinner-tofu-pasta-ragu:base"]

    def change(i):
        if i.name == "tofu":  # capped one step up: x1.25 and x1.5 give the same tofu amount
            return i.model_copy(update={"quantity_max": i.quantity + i.quantity_step})
        if i.name == "morot":  # a second main ingredient that keeps scaling
            return i.model_copy(update={"role": "primary", "quantity_min": 90.0, "quantity_max": 180.0, "quantity_step": 10.0})
        return i

    two = recipe.model_copy(update={"ingredients": [change(i) for i in recipe.ingredients]})
    siblings = sr.scaled_versions(two)
    assert len({s.design.variant_id for s in siblings}) == len(siblings) > 0
