import copy
import json
from pathlib import Path

import pytest
from app.services.meal_library_content import validate_pack_bytes
from app.services.recipe_authoring import standardize

EXAMPLE = Path(__file__).parents[2] / "docs/recipes/examples/authoring-example.json"
VOCABULARY = {
    "kyckling|raw_edible": ("g", []), "citronjuice|as_sold": ("ml", ["pack:lemon_juice", "pure_juice"]),
    "oregano|dry": ("g", ["dried_leaf", "pack:oregano"]), "vitlök|raw_edible": ("g", ["pack:garlic"]),
    "rapsolja|as_sold": ("ml", ["pack:oil"]), "salt|as_sold": ("g", ["pack:salt"]),
    "potatis|raw_edible": ("g", ["pack:potato"]), "yoghurt naturell|as_sold": ("g", ["pack:yogurt", "plain", "thick"]),
    "gurka|raw_edible": ("g", ["pack:cucumber"]), "dill|raw_edible": ("g", ["pack:dill"]),
    "tomat|raw_edible": ("g", ["pack:tomato"]), "rödlök|raw_edible": ("g", ["pack:red_onion"]),
}


def _source():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_is_standardized_into_a_valid_pack():
    pack, report = standardize(_source(), VOCABULARY, reviewed_at="2026-10-17")
    checked = validate_pack_bytes(json.dumps(pack).encode())
    assert checked["rejections"] == []
    row = report[0]
    # Critical path: 6 min prep -> 30 min passive roasting -> 10 min final step.
    assert (row["total_minutes"], row["waiting_minutes"], row["active_minutes"]) == (46, 30, 16)
    assert row["counted_ingredients"] == 11 and row["warnings"] == []
    recipe = pack["recipes"][0]
    oil = next(i for i in recipe["ingredients"] if i["name"] == "rapsolja")
    assert oil["unit"] == "ml" and oil["product_requirements"] == ["pack:oil"]
    assert recipe["design"]["vegetarian"] is False and recipe["design"]["fish"] is False


def test_unknown_identity_is_rejected_with_suggestions():
    source = _source()
    source["recipes"][0]["components"][0]["ingredients"][0]["form"] = "dry"
    with pytest.raises(ValueError, match="okänd identitet kyckling\\|dry"):
        standardize(source, VOCABULARY, reviewed_at="2026-10-17")


def test_every_ingredient_must_be_used_in_a_step():
    source = _source()
    source["recipes"][0]["steps"][4]["uses"] = ["tomat"]
    with pytest.raises(ValueError, match="används inte"):
        standardize(source, VOCABULARY, reviewed_at="2026-10-17")


def test_missing_food_safety_text_and_small_dinners_are_reported():
    source = copy.deepcopy(_source())
    source["recipes"][0]["steps"][5]["text"] = "Stek kycklingen och servera."
    _, report = standardize(source, VOCABULARY, reviewed_at="2026-10-17")
    assert any("74 °C" in w for w in report[0]["warnings"])
