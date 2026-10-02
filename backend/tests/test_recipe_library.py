"""Library checks distinguish authored review from cooking and market evidence."""

import hashlib
import json
from collections import Counter

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.models.recipe_preferences import RecipePreferences
from app.services import recipe_library as library
from pydantic import ValidationError


def complete(**kwargs):
    return RecipePreferences(mode="complete", **kwargs)


def test_legacy_recipe_and_preferences_remain_additive():
    value = {"name": "Legacy", "servings": 2,
             "ingredients": [{"name": "ris", "quantity": 100, "unit": "g"}],
             "instructions": ["Koka riset."]}
    stored = Recipe.model_validate(value).model_dump(mode="json")
    assert "design" not in stored and "preparation" not in stored
    assert stored["ingredients"] == [{**value["ingredients"][0], "canonical_name": None}]
    assert RecipePreferences().mode == "legacy"
    assert library.candidates(RecipePreferences()) == []


def test_all_six_cuisines_have_eight_distinct_original_dishes():
    bases = library.candidates(complete(adaptation="products"))
    assert len(bases) == 48
    assert Counter(r.design.cuisines[0] for r in bases) == dict.fromkeys(
        ["greek", "italian", "mexican", "indian", "thai", "swedish"], 8)
    assert len({r.design.base_id for r in bases}) == 48
    # Ignore protein, title and cuisine: original dishes must have different
    # structural/content fingerprints, not renamed protein substitutions.
    signatures = [(r.design.family, r.design.method, r.design.side,
                   tuple(sorted((i.canonical_name, i.form, i.quantity)
                                for i in r.ingredients if i.role != "primary"))) for r in bases]
    assert len(set(signatures)) == len(bases)
    for cuisine in {r.design.cuisines[0] for r in bases}:
        assert sum(r.design.vegetarian for r in bases if r.design.cuisines[0] == cuisine) >= 3


def test_every_version_has_consistent_count_time_steps_and_declared_review():
    recipes = library.candidates(complete())
    assert len(recipes) == 96
    for recipe in recipes:
        assert library.validate_recipe_design(recipe)
        assert 10 <= library.ingredient_count(recipe) <= 15
        assert recipe.design.estimated_minutes <= 50
        assert recipe.design.provenance.cooking_test == "not_cooked"
        assert recipe.design.provenance.machine_validation == "passed"
        assert all(i.required and i.quantity > 0 and i.unit in {"g", "ml"}
                   for i in recipe.ingredients)
        assert recipe.instructions == [s.text for s in recipe.design.steps]


@pytest.mark.parametrize("servings", [1, 2, 4, 6, 12])
def test_issued_portions_are_exact_reproducible_versions(servings):
    recipes = library.candidates(complete(max_minutes=180), servings)
    assert len(recipes) == 96
    for recipe in recipes:
        assert recipe.servings == servings
        assert library.validate_recipe_design(recipe)
        assert Recipe.model_validate_json(recipe.model_dump_json()) == recipe


def test_user_constraints_filter_without_silent_relaxation():
    recipes = library.candidates(complete(cuisines=("greek", "mexican"), allow_fish=False,
                                        max_minutes=35, min_ingredients=13, max_ingredients=14))
    assert recipes
    assert all(r.design.cuisines[0] in {"greek", "mexican"} and not r.design.fish
               and r.design.estimated_minutes <= 35 and 13 <= r.design.ingredient_count <= 14
               for r in recipes)
    assert not library.candidates(complete(min_ingredients=3, max_ingredients=4))
    assert not library.candidates(complete(max_minutes=10))
    assert all(r.design.variant_id == "base"
               for r in library.candidates(complete(adaptation="products")))


def test_exact_ingredient_identity_counts_once_across_components():
    ingredient = RecipeIngredient(name="vitlök", canonical_name="vitlök", form="raw_edible",
                                  component="main", quantity=10, unit="g")
    recipe = Recipe(name="Count", servings=2, ingredients=[
        ingredient, ingredient.model_copy(update={"component": "sauce"}),
        ingredient.model_copy(update={"form": "dry"}),
        RecipeIngredient(name="salt", quantity=2, unit="g"),
        RecipeIngredient(name="rapsolja", quantity=10, unit="ml"),
    ], instructions=["Test"])
    assert library.ingredient_count(recipe) == 3


@pytest.mark.parametrize("kind", ["quantity", "instructions", "form", "identity", "time", "requirements"])
def test_untrusted_self_signed_edit_cannot_borrow_approved_preparation(kind):
    recipe = library.candidates(complete())[0]
    raw = recipe.model_dump(mode="json")
    if kind == "quantity":
        raw["ingredients"][0]["quantity"] += 10
        raw["ingredients"][0]["quantity_max"] += 10
    elif kind == "instructions":
        raw["instructions"][0] += " Häll bort all sky."
        raw["design"]["steps"][0]["text"] = raw["instructions"][0]
    elif kind == "form":
        raw["ingredients"][0]["form"] = "as_sold"
    elif kind == "identity":
        raw["design"]["variant_id"] = "unreviewed"
    elif kind == "time":
        raw["design"]["estimated_minutes"] = 120
    else:
        raw["ingredients"][0]["product_requirements"] = ["any"]
    tampered = Recipe.model_validate(raw)
    digest = library.content_hash(tampered)
    tampered = tampered.model_copy(update={
        "design": tampered.design.model_copy(update={"content_sha256": digest}),
        "preparation": tampered.preparation.model_copy(update={"parent_sha256": digest}),
    })
    with pytest.raises(ValueError):
        library.validate_recipe_design(tampered)


def test_candidates_cannot_mutate_the_cached_registry():
    first = library.candidates(complete())
    first[0].ingredients.clear()
    second = library.candidates(complete())
    assert second[0].ingredients
    assert library.validate_recipe_design(second[0])


def test_file_checksum_and_quality_are_explicit():
    assert hashlib.sha256(library.LIBRARY_PATH.read_bytes()).hexdigest() == library.CONTENT_SHA256
    summary = library.library_summary()
    assert summary["base_recipes"] == 48
    assert summary["approved_variants"] == 48
    assert summary["cooking_test"] == "not_cooked"
    assert "planner" in summary["purchase_qualification"]
    assert json.dumps(summary)


def test_prior_issued_versions_remain_valid_but_new_candidates_use_current_content():
    previous = json.loads(library.LIBRARY_PATH.with_name("complete-dinners-1.0.0.json").read_text(
        encoding="utf8"))["recipes"][0]
    archived = Recipe.model_validate(previous)
    assert archived.design.version == "1.0.0"
    assert library.validate_recipe_design(archived)
    assert all(r.design.version == "1.1.0" for r in library.candidates(complete()))


def test_cured_ingredients_need_drained_evidence_and_frozen_corn_is_heated():
    for recipe in library.candidates(complete()):
        for ingredient in recipe.ingredients:
            if ingredient.name in {"oliver", "kapris"}:
                assert ingredient.form == "preserved_drained"
                assert "avrinning" in " ".join(recipe.instructions)
            if ingredient.name in {"majs", "spenat", "ärtor", "haricots verts"}:
                assert "frozen" in ingredient.product_requirements
        if recipe.design.base_id.endswith(("fish-tacos", "tofu-sofritas")):
            assert "Hetta upp majsen" in " ".join(recipe.instructions)


def test_complex_bakes_are_not_presented_as_forty_minute_dinners():
    quick = library.candidates(complete(max_minutes=40))
    assert not any(r.design.base_id.endswith(("lentil-moussaka", "stuffed-peppers", "bean-enchiladas"))
                   for r in quick)
    all_recipes = library.candidates(complete())
    assert any(r.design.base_id.endswith("lentil-moussaka") for r in all_recipes)


def test_four_portions_include_additional_preparation_time():
    two = library.candidates(complete(), 2)[0]
    four = library.candidates(complete(), 4)[0]
    assert four.design.estimated_minutes == two.design.estimated_minutes + 3
    assert four.ingredients[0].quantity == 2 * two.ingredients[0].quantity
    assert four.design.content_sha256 != two.design.content_sha256


@pytest.mark.parametrize("values", [
    {"min_ingredients": 16, "max_ingredients": 10}, {"cuisines": ["greek", "greek"]},
    {"cuisines": ["french"]}, {"min_protein_g": float("nan")},
    {"max_minutes": 0}, {"adaptation": "arbitrary"}, {"unknown": True},
])
def test_preferences_reject_incoherent_or_unknown_choices(values):
    with pytest.raises(ValidationError):
        complete(**values)
