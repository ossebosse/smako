"""Owner decision 2026-11-27: every current dish has a popularity score 1–5."""

from collections import Counter

from app.services.recipe_library import current_recipes
from app.services.recipe_popularity import DEFAULT_CUTOFF, popularity, popularity_reason, rated_dishes


def _current_dishes():
    return {r.design.base_id: r for r in current_recipes() if r.design}


def test_every_current_dish_has_a_score():
    missing = sorted(base for base in _current_dishes() if popularity(base) is None)
    assert not missing, (
        "Nya rätter behöver en popularitet (1–5) i app/data/recipe_popularity.json: "
        + ", ".join(missing[:20]))


def test_scores_have_reasons():
    for base in rated_dishes():
        assert popularity(base) in {1, 2, 3, 4, 5}
        assert popularity_reason(base)


def test_known_anchors():
    dishes = _current_dishes()
    liver = [b for b, r in dishes.items() if r.design.primary_ingredient == "kycklinglever"]
    assert liver and all(popularity(b) <= 2 for b in liver)
    sauce = [b for b, r in dishes.items() if r.name.startswith("Köttfärssås med pasta")]
    assert sauce and all(popularity(b) == 5 for b in sauce)


def test_cutoff_keeps_enough_dinners_per_diet():
    # A cut-off must leave each diet a large pool, so weekly variation survives.
    kept = Counter()
    for base, recipe in _current_dishes().items():
        d = recipe.design
        if "dinner" in d.meal_types and popularity(base) >= DEFAULT_CUTOFF:
            kept["veg" if d.vegetarian else "fish" if d.fish else "meat"] += 1
    assert min(kept["veg"], kept["fish"], kept["meat"]) >= 150, kept
