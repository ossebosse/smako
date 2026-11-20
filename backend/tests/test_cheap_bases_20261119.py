"""Owner decision 2026-11-19: Claude-authored dinners on cheap ingredients with few dishes."""
from collections import Counter

from app.services import intake_product_links as links
from app.services.meal_library_content import manifest_entries
from app.services.recipe_library import current_recipes, ingredient_count

PACK = "smako-cheap-bases-20261119"


def _pack():
    return [r for r in current_recipes(len(manifest_entries()["current"]))
            if r.design.content_source and r.design.content_source.pack_id == PACK]


def test_pack_has_three_variants_per_base_across_six_cuisines():
    recipes = _pack()
    bases = {r.design.base_id for r in recipes}
    assert len(bases) == 49 and len(recipes) == 147
    assert Counter(r.design.variant_id for r in recipes) == {"simple": 49, "standard": 49, "extended": 49}
    assert set(Counter(r.design.cuisines[0] for r in recipes)) == {"swedish", "greek", "italian", "mexican", "indian", "thai"}


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


def test_original_ingredients_are_kept():
    names = {i.canonical_name: i for r in _pack() for i in r.ingredients}
    assert {"olivolja", "fisksås", "majstortillas", "balsamvinäger", "mozzarella", "mynta", "citrongräs",
            "rimmat fläsk"} <= set(names)
    assert names["mynta"].product_requirements == ("pack:intake_all_shape_trimmed_mint",)
    assert names["citrongräs"].product_requirements == ("pack:intake_all_shape_top5_whole_lemongrass",)
