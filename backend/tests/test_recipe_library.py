"""Library checks distinguish authored review from cooking and market evidence."""

import hashlib
import json
from collections import Counter

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.models.recipe_preferences import RecipePreferences
from app.services import recipe_library as library
from pydantic import ValidationError


def prior_candidates(*args, **kwargs):
    """Assertions specific to the issued 1.x dishes and their later versions.

    A dish of the original library may be superseded by a reviewed newer
    version from a content pack (same base and variant, higher version); the
    issued original stays in the history and is checked separately.
    """
    originals = {(r["design"]["base_id"], r["design"]["variant_id"])
                 for r in json.loads(library.LIBRARY_PATH.read_text(encoding="utf8"))["recipes"]}
    return [r for r in library.candidates(*args, **kwargs)
            if (r.design.base_id, r.design.variant_id) in originals]


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
    assert prior_candidates(RecipePreferences()) == []


def test_all_six_cuisines_have_eight_distinct_original_dishes():
    bases = prior_candidates(complete(adaptation="products"))
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
    recipes = prior_candidates(complete())
    assert len(recipes) == 104
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
    recipes = prior_candidates(complete(max_minutes=180), servings)
    assert len(recipes) == 104
    for recipe in recipes:
        assert recipe.servings == servings
        assert library.validate_recipe_design(recipe)
        assert Recipe.model_validate_json(recipe.model_dump_json()) == recipe


def test_user_constraints_filter_without_silent_relaxation():
    recipes = prior_candidates(complete(cuisines=("greek", "mexican"), allow_fish=False,
                                        max_minutes=35, min_ingredients=13, max_ingredients=14))
    assert recipes
    assert all(r.design.cuisines[0] in {"greek", "mexican"} and not r.design.fish
               and r.design.estimated_minutes <= 35 and 13 <= r.design.ingredient_count <= 14
               for r in recipes)
    assert not prior_candidates(complete(min_ingredients=3, max_ingredients=4))
    assert not prior_candidates(complete(max_minutes=10))
    assert all(r.design.variant_id == "base"
               for r in prior_candidates(complete(adaptation="products")))


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
    recipe = prior_candidates(complete())[0]
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
    first = prior_candidates(complete())
    first[0].ingredients.clear()
    second = prior_candidates(complete())
    assert second[0].ingredients
    assert library.validate_recipe_design(second[0])


def test_file_checksum_and_quality_are_explicit():
    assert hashlib.sha256(library.LIBRARY_PATH.read_bytes()).hexdigest() == library.CONTENT_SHA256
    summary = library.library_summary()
    # The original cohort stays immutable while later manifest packs can grow.
    original = library.current_recipes(2)
    assert sum(r.design.variant_id == "base" for r in original) == 62
    assert sum(r.design.variant_id != "base" for r in original) == 90
    current = library.current_recipes()
    assert summary["base_recipes"] == sum(r.design.variant_id == "base" for r in current)
    assert summary["approved_variants"] == sum(r.design.variant_id != "base" for r in current)
    assert summary["cooking_test"] == "not_cooked"
    assert "planner" in summary["purchase_qualification"]
    assert json.dumps(summary)


def test_prior_issued_versions_remain_valid_but_new_candidates_use_current_content():
    previous = json.loads(library.LIBRARY_PATH.with_name("complete-dinners-1.0.0.json").read_text(
        encoding="utf8"))["recipes"][0]
    archived = Recipe.model_validate(previous)
    assert archived.design.version == "1.0.0"
    assert library.validate_recipe_design(archived)
    assert {r.design.version for r in prior_candidates(complete())} == {"1.1.0", "1.3.0", "1.4.0"}


def test_original_96_recipe_objects_are_unchanged_and_archived():
    current = json.loads(library.LIBRARY_PATH.read_bytes())["recipes"]
    previous = json.loads(library.LIBRARY_PATH.with_name("complete-dinners-1.1.0.json").read_bytes())["recipes"]
    archived = json.loads(library.LIBRARY_PATH.with_name("complete-dinners-1.2.0.json").read_bytes())["recipes"]
    assert archived[:96] == previous
    assert len(current) == len(archived) == 104
    for issued, current_row in zip(archived, current, strict=True):
        assert issued["ingredients"] == current_row["ingredients"]
        assert issued["name"] == current_row["name"]
        assert issued["design"]["base_id"] == current_row["design"]["base_id"]
        assert issued["design"]["variant_id"] == current_row["design"]["variant_id"]
        assert library.validate_recipe_design(Recipe.model_validate(issued))
    digest = hashlib.sha256(json.dumps(previous, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":")).encode()).hexdigest()
    assert digest == "f69b7f6d758f179a2c977aa6cf54d42d1436871bfed894777f8dd3c90828354f"
    for row in previous:
        assert library.validate_recipe_design(Recipe.model_validate(row))


def test_approved_culinary_variations_change_instructions_count_and_flavor_deliberately():
    approved = [r for r in prior_candidates(complete()) if r.design.variant_id not in {"base", "protein"}]
    assert len(approved) == 8
    assert len({r.design.base_id for r in approved}) == 4
    assert all(r.design.variant_id == "base" for r in prior_candidates(complete(adaptation="products")))
    for recipe in approved:
        by_name = {i.name: i for i in recipe.ingredients}
        instructions = " ".join(recipe.instructions)
        assert library.validate_recipe_design(recipe)
        assert recipe.design.provenance.cooking_test == "not_cooked"
        if recipe.design.variant_id.startswith("white-bean"):
            assert "white_beans" in by_name["vita bönor"].product_requirements
            assert "kidney" not in instructions
            assert by_name["vita bönor"].form == "cooked_drained"
        else:
            assert "mjölk" not in by_name
            assert "mjölk" not in instructions
        if recipe.design.variant_id.startswith("water-panade"):
            assert "3 g vatten per gram ströbröd" in instructions
            assert by_name["crème fraiche"].quantity == 120
            assert recipe.design.ingredient_count == 12
        if recipe.design.base_id.endswith("green-pea-soup"):
            assert by_name["crème fraiche"].quantity == 80
            assert by_name["citronjuice"].quantity == 12
            assert "från värmen" in instructions and "utan kraftig kokning" in instructions


def test_cured_ingredients_need_drained_evidence_and_frozen_corn_is_heated():
    for recipe in prior_candidates(complete()):
        for ingredient in recipe.ingredients:
            if ingredient.name in {"oliver", "kapris"}:
                assert ingredient.form == "preserved_drained"
                assert "avrinning" in " ".join(recipe.instructions)
            if ingredient.name in {"majs", "spenat", "ärtor", "haricots verts"}:
                assert "frozen" in ingredient.product_requirements
        if recipe.design.base_id.endswith(("fish-tacos", "tofu-sofritas")):
            assert "Hetta upp majsen" in " ".join(recipe.instructions)


def test_complex_bakes_are_not_presented_as_forty_minute_dinners():
    quick = prior_candidates(complete(max_minutes=40))
    assert not any(r.design.base_id.endswith(("lentil-moussaka", "stuffed-peppers", "bean-enchiladas"))
                   for r in quick)
    all_recipes = prior_candidates(complete())
    assert any(r.design.base_id.endswith("lentil-moussaka") for r in all_recipes)


def test_four_portions_include_additional_preparation_time():
    two = prior_candidates(complete(), 2)[0]
    four = prior_candidates(complete(), 4)[0]
    assert four.design.estimated_minutes == two.design.estimated_minutes + 3
    assert four.ingredients[0].quantity == 2 * two.ingredients[0].quantity
    assert four.design.content_sha256 != two.design.content_sha256


def test_parallel_cooking_finishes_before_plating_and_rice_is_explicit():
    rice_bases = {"smako-indian-tofu-dal", "smako-indian-fish-coconut",
                  "smako-thai-coconut-fish-soup", "smako-thai-chicken-coconut-curry"}
    for recipe in prior_candidates(complete()):
        steps = {s.id: s for s in recipe.design.steps}
        final = recipe.design.steps[-1]
        assert set(final.depends_on) == set(steps) - {final.id}
        if recipe.design.base_id in rice_bases:
            assert steps["rice"].duration_minutes >= 22
            assert "ris|dry" in steps["rice"].ingredient_keys
            assert steps["rice"].depends_on == ("s1",)
        if recipe.design.base_id == "smako-greek-lemon-chicken":
            assert "Smula fetaosten" in final.text
            assert "fetaost|as_sold" in final.ingredient_keys
            assert "spenatriset" not in steps["s4"].text
        if recipe.design.base_id == "smako-mexican-chicken-bowl":
            assert "Lägg ris i skålar" in final.text
            assert "toppa med kyckling" not in steps["s4"].text
        if recipe.design.base_id == "smako-thai-tofu-satay":
            assert "Servera tofu" in final.text
            assert "sesamfrön|as_sold" in final.ingredient_keys
        if recipe.design.base_id == "smako-greek-stuffed-peppers":
            assert "prebake" in steps["s3"].depends_on
            assert "Ta ut formen" in steps["prebake"].text
            assert "fyllning som inte ryms" in steps["s3"].text.lower()
        if recipe.design.base_id == "smako-italian-lentil-ragu":
            assert "Vänd pastan med ragun" in steps["s4"].text
            assert set(steps["s4"].depends_on) == {"s2", "s3"}


def test_frozen_spinach_heating_has_margin_and_strict_time_filter_excludes_it():
    for recipe in prior_candidates(complete()):
        if recipe.design.base_id in {"smako-indian-tofu-dal", "smako-indian-bean-potato-curry"}:
            assert recipe.design.estimated_minutes == 44
            assert "5–7 minuter" in " ".join(recipe.instructions)
    quick = prior_candidates(complete(max_minutes=40))
    assert not any(r.design.base_id in {"smako-indian-tofu-dal", "smako-indian-bean-potato-curry"}
                   for r in quick)


@pytest.mark.parametrize("servings,expected_bases", [(2, 12), (4, 4)])
def test_mixed_greek_mexican_content_limit_at_forty_minutes_is_not_relaxed(servings, expected_bases):
    recipes = prior_candidates(complete(cuisines=("greek", "mexican"), max_minutes=40), servings)
    # Content availability only: actual product, nutrition and basket qualification
    # is deliberately tested through the planner on a real snapshot elsewhere.
    assert len({r.design.base_id for r in recipes}) == expected_bases
    assert {r.design.cuisines[0] for r in recipes} == {"greek", "mexican"}
    assert all(r.design.estimated_minutes <= 40 for r in recipes)


def test_four_person_mixed_content_needs_explicit_forty_three_minute_choice():
    for minutes, expected in [(42, 4), (43, 12), (45, 12)]:
        recipes = prior_candidates(complete(cuisines=("greek", "mexican"), max_minutes=minutes), 4)
        assert len({r.design.base_id for r in recipes}) == expected


def test_larger_portion_allowance_is_not_assigned_to_new_auxiliary_timer():
    for recipe in prior_candidates(complete(max_minutes=180), 6):
        if recipe.design.version in {"1.3.0", "1.4.0"}:
            for step in recipe.design.steps:
                if step.id in {"rice", "prebake"}:
                    assert "omgångar" not in step.text


def test_equipment_revision_preserves_every_previously_issued_meal_and_timing():
    old = json.loads(library.LIBRARY_PATH.with_name("complete-dinners-1.3.0.json").read_bytes())["recipes"]
    new = json.loads(library.LIBRARY_PATH.read_bytes())["recipes"]
    for issued, current in zip(old, new, strict=True):
        assert library.validate_recipe_design(Recipe.model_validate(issued))
        assert issued['ingredients'] == current['ingredients']
        assert issued['instructions'] == current['instructions']
        assert issued['design']['steps'] == current['design']['steps']
        assert issued['design']['estimated_minutes'] == current['design']['estimated_minutes']
        if issued['design']['equipment'] != current['design']['equipment']:
            assert current['design']['version'] == '1.4.0'


def test_secondary_cookware_exists_for_simultaneous_soup_and_bread_components():
    for recipe in prior_candidates(complete(max_minutes=180)):
        base = recipe.design.base_id.removeprefix('smako-')
        tools = ' '.join(recipe.design.equipment)
        if base in {'mexican-corn-soup', 'swedish-green-pea-soup'}:
            assert all(tool in tools for tool in ('gryta', 'stekpanna', 'potatisstöt', 'rivjärn'))
        if base in {'greek-keftedes', 'swedish-beef-patties', 'thai-lentil-coconut-soup'}:
            assert 'stekpanna' in tools
        if base in {'thai-tofu-satay', 'swedish-lentil-patties'}:
            assert 'två kastruller' in tools
        if base in {'greek-fish-plaki', 'italian-salmon-cartoccio'}:
            assert 'ugnsform med ugnssäkert lock eller folie' in tools


@pytest.mark.parametrize("values", [
    {"min_ingredients": 16, "max_ingredients": 10}, {"cuisines": ["greek", "greek"]},
    {"cuisines": ["french"]}, {"min_protein_g": float("nan")},
    {"max_minutes": 0}, {"adaptation": "arbitrary"}, {"unknown": True},
])
def test_preferences_reject_incoherent_or_unknown_choices(values):
    with pytest.raises(ValidationError):
        complete(**values)
