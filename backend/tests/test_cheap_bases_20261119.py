"""Owner decision 2026-11-19: Claude-authored dinners on cheap ingredients with few dishes."""
from collections import Counter

from app.services.meal_library_content import manifest_entries
from app.services.recipe_library import current_recipes, ingredient_count

PACK = "smako-cheap-bases-20261119"
# Not buyable anywhere in Lund or Malmö on beta 2026-11-19 (plan diagnostics).
UNBUYABLE = {"olivolja", "mozzarella", "rimmat fläsk", "majstortillas", "fisksås", "mynta", "balsamvinäger",
             "majsgryn", "risottoris"}


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


def test_no_ingredient_that_lund_or_malmo_cannot_buy():
    for recipe in _pack():
        assert not {i.canonical_name for i in recipe.ingredients} & UNBUYABLE, recipe.name
