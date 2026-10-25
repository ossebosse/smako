import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models.personal import MealSettings, MealSlot
from app.models.recipe import Recipe
from app.models.recipe_preferences import RecipePreferences
from app.services import meal_library_content as content
from app.services.content_pack_requirements import intake_whole_identity
from app.services.diet_policy import recipe_respects_diet
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

EXAMPLE = Path(__file__).parents[2] / "docs/recipes/examples/authoring-example.json"


def authored(name="kyckling", *, method=None):
    source = json.loads(EXAMPLE.read_bytes())
    row = source["recipes"][0]
    row["components"][0]["ingredients"][0]["name"] = name
    for step in row["steps"]:
        step["uses"] = [name if n == "kyckling" else n for n in step["uses"]]
    if method:
        row["method"] = method
    vocabulary = library_vocabulary(current_recipes())
    vocabulary[f"{name}|raw_edible"] = ("g", ["pack:chicken_breast"])
    return standardize(source, vocabulary, reviewed_at="2026-10-25")


@pytest.mark.parametrize("name", [
    "gröna linser", "svarta linser", "gula ärtor", "klibbigt ris", "rimmat fläsk",
    "rökt lax", "varmrökt lax", "äggula", "kokta ägg", "kondenserad mjölk", "puffat ris", "äggnudlar",
])
def test_specific_input_does_not_inherit_generic_recipe_requirements(name):
    assert canonicalize_ingredient_name(name) == name
    assert f"{name}|raw_edible" not in library_vocabulary(())


@pytest.mark.parametrize("name", ["lammkött", "lammfärs", "räkor", "råa räkor", "musslor", "bläckfisk", "gelatinblad"])
def test_animal_ingredients_cannot_become_vegetarian_or_implicitly_fish(name):
    pack, report = authored(name)
    recipe = Recipe.model_validate(pack["recipes"][0])
    assert report[0]["vegetarian"] is False and report[0]["fish"] is False
    assert not recipe_respects_diet(recipe, preference="vegetarian")
    assert not recipe_respects_diet(recipe, preference="vegan")


@pytest.mark.parametrize("name", ["ricotta", "paneer", "äggula", "kondenserad mjölk", "filmjölk"])
def test_additional_dairy_and_egg_inputs_are_not_vegan(name):
    pack, _ = authored(name)
    assert not recipe_respects_diet(Recipe.model_validate(pack["recipes"][0]), preference="vegan")


@pytest.mark.parametrize("name", ["lammkött", "råa räkor", "äggvita"])
def test_cold_method_does_not_bypass_raw_animal_guard(name):
    pack, _ = authored(name, method="salad")
    checked = content.validate_pack_bytes(content.encoded(pack))
    assert any("rå animalisk" in r["reason"] for r in checked["rejections"])


def test_long_passive_preparation_survives_serialization_without_reducing_active_work():
    source = json.loads(EXAMPLE.read_bytes())
    source["recipes"][0]["steps"][1]["minutes"] = 720
    pack, report = standardize(source, library_vocabulary(current_recipes()), reviewed_at="2026-10-25")
    checked = content.validate_pack_bytes(content.encoded(pack))
    assert not checked["rejections"]
    issued = checked["recipes"][0]
    restored = Recipe.model_validate_json(issued.model_dump_json())
    assert restored.design.total_minutes == report[0]["total_minutes"] > 720
    assert restored.design.active_minutes == report[0]["active_minutes"] < 180
    assert restored.design.waiting_minutes == report[0]["waiting_minutes"]


@pytest.mark.parametrize("name,form,label", [
    ("smör", "as_sold", "Bregott smör och rapsolja"),
    ("smör", "as_sold", "Margarin"),
    ("timjan", "dry", "Timjan Kruka"),
    ("rismjöl", "dry", "Klibbigt rismjöl"),
    ("mandel", "as_sold", "Bittermandel"),
    ("valnötter", "as_sold", "Valnötter Rostade Saltade"),
    ("kokosflingor", "dry", "Kokosmjöl"),
])
def test_reviewed_whole_identities_reject_neighbouring_products(name, form, label):
    assert not intake_whole_identity(name, form, label, "")


@pytest.mark.parametrize("name", ["timjan", "rosmarin"])
def test_dried_herbs_require_dry_shelf_evidence_not_a_fresh_herb_with_the_same_name(name):
    from app.services.complete_recipes import _whole_food_identity

    herb = SimpleNamespace(name=name.capitalize(), category="Frukt & grönt > Kryddor/örter", brand=None)
    assert not _whole_food_identity(name, "dry", herb, None)
    herb.category = "Skafferi > Kryddor"
    assert _whole_food_identity(name, "dry", herb, None)


def test_butter_does_not_bypass_existing_margarine_brand_exclusions():
    from app.services.product_semantics import evaluate_product_semantics

    assert not evaluate_product_semantics("smör", SimpleNamespace(name="Smör", brand="Milda")).compatible


def test_reviewed_vocabulary_rejects_an_empty_bootstrap(tmp_path):
    path = tmp_path / "vocabulary.json"
    path.write_text(json.dumps({"schema_version": "smako-authoring-vocabulary-v1", "ingredients": [{
        "name": "smör", "form": "as_sold", "unit": "g", "requirements": [],
        "review_basis": "pending", "evidence": ["pending"],
    }]}), encoding="utf-8")
    with pytest.raises(ValueError, match="Ogiltig granskad"):
        library_vocabulary((), reviewed_path=path)


def test_import_refuses_generation_129_before_writing_and_remains_idempotent(tmp_path):
    pack, _ = authored()
    path = tmp_path / "input.json"
    path.write_bytes(content.encoded(pack))
    root = tmp_path / "library"
    root.mkdir()
    manifest_path = root / content.MANIFEST.name
    manifest_path.write_bytes(content.encoded({"schema_version": content.MANIFEST_SCHEMA, "current": [], "history": []}))
    first = content.import_pack(path, root=root)
    manifest = content.manifest_entries(root)
    manifest["history"] = manifest["current"] * 127
    manifest_path.write_bytes(content.encoded(manifest))
    before = manifest_path.read_bytes()
    content.import_pack(path, root=root)  # Existing publication is still legal at the limit.
    assert manifest_path.read_bytes() == before
    pack["pack_id"] = "new-pack"
    pack["recipes"][0]["design"]["base_id"] = "smako-greek-other-generation"
    path.write_bytes(content.encoded(pack))
    with pytest.raises(ValueError, match="för många paketgenerationer"):
        content.import_pack(path, root=root)
    assert manifest_path.read_bytes() == before
    assert [p.name for p in root.glob("meal-pack-*.json")] == [first["published_file"]]
    assert content.load_entries(manifest["current"], root)


def test_reviewed_requirements_cannot_be_removed_in_authoring():
    source = json.loads(EXAMPLE.read_bytes())
    item = source["recipes"][0]["components"][0]["ingredients"][0]
    item.update(name="smör", form="as_sold", requirements=[])
    with pytest.raises(ValueError, match="får inte tappa"):
        standardize(source, library_vocabulary(()), reviewed_at="2026-10-25")


def test_week_cap_cannot_be_bypassed_with_simple_and_extended_of_one_base():
    from app.services.personal_planner import PersonalPlanner

    variants = [r for r in current_recipes() if r.design.base_id == "smako-indian-lentil-crepes-potato"
                and r.design.variant_id in {"simple", "extended"}]
    assert len(variants) == 2
    planner = SimpleNamespace(meals={"dinner": MealSettings(count=2, max_same_base_meals=1)},
                              request=SimpleNamespace(recipe_preferences=RecipePreferences(mode="complete")))
    slots = [MealSlot(id=f"dinner-{n}", day=n, meal_type="dinner", recipe=r) for n, r in enumerate(variants, 1)]
    with pytest.raises(ValueError, match="upprepningsgränsen"):
        PersonalPlanner._check_final(planner, slots, None, None, None, None)


def test_long_issued_recipe_keeps_total_waiting_and_scaled_amounts_under_explicit_choices():
    from app.services.recipe_library import _scaled, matches_meal

    recipe = next(r for r in current_recipes() if r.design.base_id == "smako-indian-lentil-crepes-potato"
                  and r.design.variant_id == "simple")
    preferences = RecipePreferences(mode="complete")
    assert not matches_meal(recipe, MealSettings(recipe_choices={"max_total_minutes": 180}), preferences)
    assert matches_meal(recipe, MealSettings(recipe_choices={"max_total_minutes": 600}), preferences)
    for servings in (1, 2, 4, 12):
        scaled = Recipe.model_validate_json(_scaled(recipe, servings).model_dump_json())
        assert scaled.design.estimated_minutes == scaled.design.total_minutes > 300
        assert scaled.design.waiting_minutes == recipe.design.waiting_minutes
        lentils = next(i for i in scaled.ingredients if i.canonical_name == "linser")
        assert lentils.quantity == 320 * servings / 4
