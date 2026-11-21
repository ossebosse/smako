"""Owner request 2026-11-21: 100 more Claude-authored dinners where the cheap pool is thin."""
import json
from collections import Counter
from pathlib import Path

from app.services import intake_product_links as links
from app.services.meal_library_content import manifest_entries
from app.services.recipe_library import current_recipes, ingredient_count

REVIEW = Path(__file__).resolve().parents[2] / "docs/reviews/variation-bases-20261121/library-transition.json"
BASES = {row["runtime_id"].split(":")[0] for row in json.loads(REVIEW.read_bytes())["added"]}
FISH = {"fisk", "tonfisk", "sardiner", "matjessill", "ätklar inläggningssill", "blåmusselkött utan skal"}
MEAT = {"kyckling", "kycklinglever", "fläskfärs", "blandfärs", "fläskkött", "fläskkarré", "falukorv",
        "isterband", "rimmat fläsk", "kokt skinka"}


def _pack():
    return [r for r in current_recipes(len(manifest_entries()["current"])) if r.design.base_id in BASES]


def test_pack_has_three_variants_per_base_across_six_cuisines():
    recipes = _pack()
    assert len({r.design.base_id for r in recipes}) == 100 and len(recipes) == 300
    assert Counter(r.design.variant_id for r in recipes) == {"simple": 100, "standard": 100, "extended": 100}
    assert set(Counter(r.design.cuisines[0] for r in recipes)) == {"swedish", "greek", "italian", "mexican", "indian", "thai"}


def test_the_thin_segments_get_the_most_dishes():
    primaries = Counter(r.design.primary_ingredient for r in _pack() if r.design.variant_id == "standard")
    fish = sum(n for p, n in primaries.items() if p in FISH)
    meat = sum(n for p, n in primaries.items() if p in MEAT)
    assert fish >= 30 and meat >= 35 and fish + meat + sum(primaries.values()) - fish - meat == 100


def test_standard_and_extended_fit_the_default_dinner_choice():
    for recipe in _pack():
        if recipe.design.variant_id != "simple":
            assert 10 <= ingredient_count(recipe) <= 15, recipe.name


def test_every_ingredient_names_an_identity_with_a_reviewed_product():
    """Owner decision 2026-11-20: ingredients resolve; they are not swapped."""
    entries = links.entries()
    for recipe in _pack():
        for ingredient in recipe.ingredients:
            for requirement in ingredient.product_requirements or ():
                row = entries.get(requirement.removeprefix("pack:"))
                if row is None or row["kind"] != "definition_only":
                    continue
                assert (row.get("reviewed_links")
                        or (row["name"], row["form"]) in links.PACKAGE_WEIGHT_IDENTITIES), (recipe.name, requirement)


def test_safety_temperatures_are_in_the_steps():
    for recipe in _pack():
        names = {i.canonical_name for i in recipe.ingredients}
        text = " ".join(step for step in recipe.instructions)
        if names & {"kyckling", "kycklinglever"}:
            assert "74 °C" in text, recipe.name
        if names & {"fläskfärs", "blandfärs"}:
            assert "72 °C" in text, recipe.name
        if "fisk" in names:
            assert "63 °C" in text, recipe.name
