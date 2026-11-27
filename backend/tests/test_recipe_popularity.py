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


# ---- The planner cut-off (owner decisions 2026-11-27) ------------------------
from types import SimpleNamespace

import pytest
from app.models.personal import TasteProfile
from app.services.personal_planner import PersonalPlanner


def _dish(name_start):
    return next(r for r in current_recipes() if r.design and r.name.startswith(name_start) and not r.design.scaled_from)


def _planner(likes=(), liked=(), floor=3):
    return SimpleNamespace(spec=SimpleNamespace(liked_recipes=list(liked), profile=TasteProfile(likes=list(likes))),
                           meals={"dinner": SimpleNamespace(profile=TasteProfile())},
                           _popularity_floor=floor, _popularity_unlocked=set())


def test_the_cut_off_keeps_popular_dishes_and_liked_ones():
    sauce, liver, chicken_liver = _dish("Köttfärssås med pasta"), _dish("Leverbiffar"), _dish("Pad khing – wokad kycklinglever")
    planner = _planner()
    assert PersonalPlanner._popular_choices(planner, "dinner", [sauce, liver]) == [sauce]
    planner = _planner(liked=[liver.design.base_id])
    assert PersonalPlanner._popular_choices(planner, "dinner", [sauce, liver]) == [sauce, liver]
    planner = _planner(floor=1)
    assert PersonalPlanner._popular_choices(planner, "dinner", [sauce, liver, chicken_liver]) == [sauce, liver, chicken_liver]


def test_a_typed_like_unlocks_only_when_no_popular_dish_names_it():
    sauce, liver, chicken = _dish("Köttfärssås med pasta"), _dish("Leverbiffar"), _dish("Butter chicken – kyckling i krämig")
    chicken_liver = _dish("Pad khing – wokad kycklinglever")
    planner = _planner(likes=["lever"])
    assert PersonalPlanner._popular_choices(planner, "dinner", [sauce, liver]) == [sauce, liver]
    assert planner._popularity_unlocked == {"lever"}
    # "kyckling" names kycklinglever too, but popular chicken dishes exist.
    planner = _planner(likes=["kyckling"])
    assert PersonalPlanner._popular_choices(planner, "dinner", [chicken, chicken_liver]) == [chicken]
    assert not planner._popularity_unlocked


def _lowering_planner(fail_until, dropped=5, requested=3):
    tried = []
    planner = SimpleNamespace(complete=True, _requested_popularity_floor=lambda: requested)

    def create(**kwargs):
        tried.append(planner._popularity_floor)
        planner._popularity_dropped = dropped
        if planner._popularity_floor > fail_until:
            raise ValueError("Ingen vecka")
        return SimpleNamespace(personal=SimpleNamespace(checks={}))
    planner._create_avoiding_recent = create
    return planner, tried


def test_the_cut_off_is_lowered_one_step_when_no_week_fits():
    planner, tried = _lowering_planner(fail_until=2)
    result = PersonalPlanner._create_avoiding(planner)
    assert tried == [3, 2]
    assert result.personal.checks["popularity"]["floor"] == 2 and result.personal.checks["popularity"]["lowered"]


def test_no_retry_when_the_cut_off_removed_nothing_or_for_byt_ratt():
    planner, tried = _lowering_planner(fail_until=0, dropped=0)
    with pytest.raises(ValueError):
        PersonalPlanner._create_avoiding(planner)
    assert tried == [3]
    planner, tried = _lowering_planner(fail_until=0)
    with pytest.raises(ValueError):
        PersonalPlanner._create_avoiding(planner, replace_slot="dinner-1")
    assert tried == [3]


def _week(floor, likes=()):
    """A real one-dinner plan with Biftekia (popularity 4) as the only dish."""
    from app.config import Settings
    from app.models import PlanRequest
    from app.models.personal import MealSettings, PersonalPlanning
    from app.models.recipe_preferences import RecipePreferences
    from app.services.personal_policy import ProductFacts
    from app.services.recipe_library import candidates

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products")
    dish = next(r for r in candidates(prefs, 2) if r.name.startswith("Biftekia på nötfärs"))
    assert popularity(dish.design.base_id) == 4
    products = [product(i.name, max(100, i.quantity), i.unit, 10).model_copy(update={
        "category": "Kryddor" if i.form == "dry" else "Frukt & grönsaker" if i.form == "raw_edible" else "Mat",
        "name": "Grekisk Yoghurt Naturell 10%" if i.name == "yoghurt naturell" else i.name + " Malen" if i.name == "spiskummin" else i.name,
    }) for i in dish.ingredients]
    facts = {(p.store_id, p.product_id): ProductFacts(source="synthetic_test_declaration", source_product_id=p.product_id,
        source_snapshot_id="v2-frozen", ingredients=(p.name,), ingredients_complete=True) for p in products}
    request = PlanRequest(recipes=1, servings=2, max_stores=1, recipe_preferences=prefs,
        personal=PersonalPlanning(meals=[MealSettings(count=1, servings=2)], popularity_floor=floor,
                                  profile={"likes": list(likes)}))
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(*products), state(), facts=facts, now=NOW)
    planner._candidates = lambda meal, **kw: [dish]
    result = planner.create()
    assert result.recipes[0] == dish
    return result.personal.checks.get("popularity")


@pytest.mark.slow
def test_a_real_plan_lowers_the_cut_off_only_when_needed():
    assert _week(floor=4) == {**_week(floor=4), "floor": 4, "lowered": False, "removed_choices": 0}
    lowered = _week(floor=5)
    assert lowered["floor"] == 4 and lowered["lowered"] and lowered["requested_floor"] == 5
    unlocked = _week(floor=5, likes=["biftekia"])
    assert unlocked["floor"] == 5 and unlocked["unlocked_likes"] == ["biftekia"]
    assert _week(floor=1) is None
