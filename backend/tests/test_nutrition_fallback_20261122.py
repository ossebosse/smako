"""Owner report 2026-11-22: four of five dinners showed no nutrition."""

from __future__ import annotations

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.nutrition_fallback import fallback_evidence, fallback_identity
from app.services.nutrition_reference import MAPPINGS, reference_data
from app.services.recipe_library import current_recipes
from app.services.recipe_preparation import has_unmeasured_process


def test_the_new_references_load_with_complete_macros():
    foods = reference_data()["foods"]
    for identity in (5067, 1278, 1275, 1271, 1272, 2255, 103, 1981, 4937):
        assert identity in MAPPINGS and str(identity) in foods


def test_products_without_usable_tables_get_the_generic_reference():
    cases = {
        ("potatis", "Fast potatis i påse"): 4457,
        ("tomat", "Körsbärstomater hela"): 4937,
        ("tomat", "Tomater i kartong"): 364,
        ("paprika", "Paprika Grön"): 350,
        ("kyckling", "Svensk kycklinginnerfilé"): 1173,
        ("ägg", "Små Ägg 15p Frigående Inomhus Small"): 1225,
        ("lammkött", "Lammytterfilé Nya Zeeland"): 5067,
        ("tonfisk", "Tonfisk i vatten"): 1278,
        ("tonfisk", "Tonfisk i olja"): 1275,
        ("sardiner", "Sardiner"): 1271,
        ("mozzarella", "Mozzarella"): 2255,
        ("parmesan", "Parmigiano Reggiano 22mån Riven"): 103,
        ("bakpulver", "Bakpulver"): 1981,
        ("koriander", "Koriander"): 7193,
        ("basilika", "Basilika Finhackad Fryst"): 379,
        ("dill", "Dill"): 377,
    }
    for (name, label), identity in cases.items():
        assert fallback_identity(name, label) == identity, (name, label)


def test_a_different_food_gets_no_reference():
    assert fallback_identity("kyckling", "Kycklinglårfilé") is None  # thigh is not breast
    assert fallback_identity("tonfisk", "Tonfiskröra") is None
    assert fallback_identity("kyckling", "Grillad kyckling") is None
    assert fallback_identity("potatis", "Sötpotatis") is None
    assert fallback_identity("okänd råvara", "Okänd") is None


def test_the_reference_follows_the_recipe_input_form():
    recipes = [r for r in current_recipes() if r.preparation is not None and not has_unmeasured_process(r)]
    seen = set()
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            name = canonicalize_ingredient_name(ingredient.name)
            form = recipe.preparation.input_forms.get(name)
            if name in {"lammkött", "tonfisk", "sardiner", "potatis", "ägg", "koriander"} and (name, form) not in seen:
                evidence = fallback_evidence(recipe, ingredient.name)
                if form in {"raw_edible", "cooked_drained", "preserved_drained"} and ingredient.unit == "g" and (name, form) != ("ägg", "cooked_drained"):
                    assert evidence is not None, (recipe.name, name, form)
                    assert evidence.evidence_kind == "recipe_design_input_estimate"
                    seen.add((name, form))
    assert {"lammkött", "tonfisk", "sardiner", "potatis", "ägg"} <= {n for n, _ in seen}
    # A dried reference never stands in for a cooked input.
    chickpeas = next(r for r in recipes if r.preparation.input_forms.get("kikärtor") == "cooked_drained")
    assert fallback_identity("kikärtor") == 881 and fallback_evidence(chickpeas, "kikärtor") is None


def test_dried_products_are_not_the_raw_food():
    assert fallback_identity("persilja", "Persilja torkad") is None
    assert fallback_identity("basilika", "Basilika torkad") is None
    assert fallback_identity("potatis", "Potatismos pulver") is None
    assert fallback_identity("persilja", "Persilja i kruka") == 352


def test_olive_oil_at_home_has_values():
    from app.services.staples import volume_evidence

    evidence = volume_evidence("olivolja", "ml")
    assert evidence is not None and evidence.nutrition["kcal"] > 750
    assert fallback_identity("oliver", "Svarta oliver urkärnade") == 402
    assert fallback_identity("oliver", "Gröna oliver") is None


def test_spring_onion_and_capers_are_left_out_and_named():
    from app.services.staples import negligible_spice

    assert negligible_spice("salladslök", 40, "g") and negligible_spice("kapris", 20, "g")
    assert not negligible_spice("gul lök", 40, "g")
