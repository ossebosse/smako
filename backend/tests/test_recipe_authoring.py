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


def _fixed_source():
    """The example without scalable ranges, for rules that are not about scaling."""
    source = _source()
    for component in source["recipes"][0]["components"]:
        for item in component["ingredients"]:
            item.pop("range", None)
            item.pop("step", None)
    return source


def test_example_is_standardized_into_a_valid_pack():
    pack, report = standardize(_source(), VOCABULARY, reviewed_at="2026-10-17")
    checked = validate_pack_bytes(json.dumps(pack).encode())
    assert checked["rejections"] == []
    row = report[0]
    # Active work 6+6+5+4+10 = 31 min (parallel prep included); the critical path
    # 6 -> 30 passive -> 10 = 46 min, so 15 minutes are pure waiting.
    assert (row["total_minutes"], row["waiting_minutes"], row["active_minutes"]) == (46, 15, 31)
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


def test_parallel_active_work_longer_than_the_path_sets_the_total():
    source = _source()
    for step in source["recipes"][0]["steps"]:
        step["passive"] = False
    _, report = standardize(source, VOCABULARY, reviewed_at="2026-10-17")
    assert report[0]["active_minutes"] == report[0]["total_minutes"] == 61
    assert report[0]["waiting_minutes"] == 0


def test_conflicting_product_requirements_for_one_purchase_line_are_rejected():
    source = _source()
    extra = {"name": "yoghurt naturell", "form": "as_sold", "quantity": 20, "role": "sauce",
             "label": "Yoghurt", "requirements": ["plain"]}
    source["recipes"][0]["components"][3]["ingredients"].append(extra)
    source["recipes"][0]["steps"][4]["uses"].append("yoghurt naturell")
    with pytest.raises(ValueError, match="olika produktkrav"):
        standardize(source, VOCABULARY, reviewed_at="2026-10-17")


def test_process_water_in_ml_scales_and_dl_is_rejected():
    source = _fixed_source()
    source["recipes"][0]["steps"][0]["text"] += " Häll 200 ml vatten i plåten."
    pack, _ = standardize(source, VOCABULARY, reviewed_at="2026-10-17")
    assert pack["recipes"][0]["design"]["steps"][0]["scalable_amounts"] == [["200 ml", 200.0]] or \
        pack["recipes"][0]["design"]["steps"][0]["scalable_amounts"] == [("200 ml", 200.0)]
    source["recipes"][0]["steps"][0]["text"] += " Tillsätt 2 dl vatten."
    with pytest.raises(ValueError, match="dl/l"):
        standardize(source, VOCABULARY, reviewed_at="2026-10-17")


def test_several_process_amounts_scale_once_and_decimals_are_one_amount():
    """Review 2026-10-18 P2: '100 ml ... 200 ml' and '125,5 ml' scaled wrongly."""
    from app.services.recipe_library import _scale_amount_tokens

    amounts = (("100 ml", 100.0), ("200 ml", 200.0))
    text = "Häll i 100 ml vatten, sedan 200 ml vatten."
    assert _scale_amount_tokens(text, amounts, 2) == "Häll i 200 ml vatten, sedan 400 ml vatten."
    assert _scale_amount_tokens(text, amounts, 0.5) == "Häll i 50 ml vatten, sedan 100 ml vatten."
    assert _scale_amount_tokens("Tillsätt 125,5 ml vatten.", (("125,5 ml", 125.5),), 2) == "Tillsätt 251 ml vatten."
    # A token never matches inside another number.
    assert _scale_amount_tokens("1200 ml vatten och 200 ml vatten", (("200 ml", 200.0),), 2) == \
        "1200 ml vatten och 400 ml vatten"


def test_author_registers_each_amount_once_with_decimals():
    source = _fixed_source()
    source["recipes"][0]["steps"][0]["text"] += " Häll 100 ml vatten och 125,5 ml dricksvatten i plåten."
    pack, _ = standardize(source, VOCABULARY, reviewed_at="2026-10-17")
    assert [tuple(a) for a in pack["recipes"][0]["design"]["steps"][0]["scalable_amounts"]] == \
        [("100 ml", 100.0), ("125,5 ml", 125.5)]


@pytest.mark.slow
def test_issued_water_steps_scale_as_before():
    """Every issued water step keeps its exact text at all five serving counts."""
    from app.services.meal_library_content import manifest_entries
    from app.services.recipe_library import _scaled, current_recipes, supports_servings

    checked_steps = 0
    for recipe in current_recipes(len(manifest_entries()["current"])):
        steps = [(index, step) for index, step in enumerate(recipe.design.steps)
                 if step.scalable_amounts and "vatten" in step.text]
        if not steps:
            continue
        checked_steps += len(steps)
        for servings in (1, 2, 4, 8, 12):
            if not supports_servings(recipe, servings):
                with pytest.raises(ValueError, match='satser'):
                    _scaled(recipe, servings)
                continue
            scaled = _scaled(recipe, servings)
            for index, step in steps:
                text = scaled.design.steps[index].text
                for _token, quantity in step.scalable_amounts:
                    assert f"{quantity * servings / recipe.servings:g} ml".replace(".", ",") in text
    assert checked_steps >= 11


# Owner decision 2026-11-24: new recipes carry reviewed ranges the planner may scale within.
def _item(source, name):
    return next(i for c in source["recipes"][0]["components"] for i in c["ingredients"] if i["name"] == name)


def test_reviewed_ranges_become_the_library_quantity_grid():
    pack, report = standardize(_source(), VOCABULARY, reviewed_at="2026-11-24")
    assert validate_pack_bytes(json.dumps(pack).encode())["rejections"] == []
    lines = {i["name"]: i for i in pack["recipes"][0]["ingredients"]}
    assert (lines["kyckling"]["quantity"], lines["kyckling"]["quantity_min"], lines["kyckling"]["quantity_max"],
            lines["kyckling"]["quantity_step"]) == (300, 240, 420, 20)
    assert (lines["potatis"]["quantity_min"], lines["potatis"]["quantity_max"], lines["potatis"]["quantity_step"]) == (350, 600, 50)
    oil = lines["rapsolja"]
    assert oil["quantity_min"] == oil["quantity_max"] == oil["quantity"]  # other roles stay fixed
    assert report[0]["scalable"] == ["kyckling|raw_edible", "potatis|raw_edible"] and report[0]["warnings"] == []
    assert pack["recipes"][0]["design"]["scaling"] == "reviewed_ranges"


@pytest.mark.parametrize("name, change, message", [
    ("rapsolja", {"range": [10, 20]}, "bara huvudråvara"),
    ("kyckling", {"range": [100, 420]}, "halva och dubbla"),
    ("kyckling", {"range": [320, 420]}, "omsluta"),
    ("kyckling", {"range": [240, 420], "step": 25}, "jämnt"),
    ("kyckling", {"step": 20}, "step utan range"),
])
def test_unsafe_ranges_are_rejected(name, change, message):
    source = _source()
    item = _item(source, name)
    item.pop("range", None); item.pop("step", None); item.update(change)
    with pytest.raises(ValueError, match=message):
        standardize(source, VOCABULARY, reviewed_at="2026-11-24")


def test_a_scaled_ingredient_cannot_be_cooked_in_a_fixed_water_amount():
    source = _source()
    source["recipes"][0]["steps"][1]["text"] = "Koka potatisen i 800 ml vatten cirka 20 minuter."
    with pytest.raises(ValueError, match="vatten för en skalbar"):
        standardize(source, VOCABULARY, reviewed_at="2026-11-24")


def test_a_dinner_without_a_scalable_main_ingredient_is_flagged():
    source = _source()
    source = _fixed_source()
    _, report = standardize(source, VOCABULARY, reviewed_at="2026-11-24")
    assert any("Skalbar mängd" in w for w in report[0]["warnings"]) and report[0]["scalable"] == []


# Owner decision 2026-11-25: seasonings that go with the main ingredient scale with it.
def _with_followers():
    source = _source()
    for name in ("citronjuice", "oregano", "vitlök", "salt"):
        _item(source, name)["follows"] = "kyckling"
    return source


def test_followers_get_a_range_that_follows_the_main_ingredient():
    pack, report = standardize(_with_followers(), VOCABULARY, reviewed_at="2026-11-25")
    assert validate_pack_bytes(json.dumps(pack).encode())["rejections"] == []
    lines = {i["name"]: i for i in pack["recipes"][0]["ingredients"]}
    lemon = lines["citronjuice"]  # 15 ml with 300 g chicken; chicken 240-420 g
    assert lemon["scales_with"] == "kyckling|raw_edible"
    assert (lemon["quantity"], lemon["quantity_min"], lemon["quantity_max"]) == (15, 12, 21)
    assert "scales_with" not in lines["rapsolja"]


def test_only_seasonings_in_the_main_component_can_follow():
    source = _with_followers()
    _item(source, "potatis")["follows"] = "kyckling"
    with pytest.raises(ValueError, match="kan inte följa"):
        standardize(source, VOCABULARY, reviewed_at="2026-11-25")
    source = _with_followers()
    _item(source, "dill")["follows"] = "kyckling"  # the tzatziki, another component
    with pytest.raises(ValueError, match="samma komponent"):
        standardize(source, VOCABULARY, reviewed_at="2026-11-25")
