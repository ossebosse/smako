"""Seed breadth for future authored families; all full-pool checks stay later."""
from types import SimpleNamespace

import pytest
from app.services.recipe_candidate_validator import recipe_id
from app.services.recipe_library import current_recipes
from app.services.recipe_profile import RecipeProfileBuilder
from app.services.stable_candidate_pool import VariantSearchEvidence, library_variant_shortlist


@pytest.fixture(autouse=True)
def synthetic_culinary_profiles(monkeypatch, request):
    if request.node.name == "test_real_current_library_keeps_every_base":
        return
    # Large future catalogues here are topology fixtures, not newly approved
    # content. Qualification is tested by the real planner integration suite.
    monkeypatch.setattr(RecipeProfileBuilder, "build", lambda self, r: SimpleNamespace(
        recipe_family=r.design.family, dish_form=r.design.family,
        primary_protein=r.design.primary_ingredient, primary_carb=r.design.side,
        cooking_method=r.design.method))


def family(count=30):
    base = current_recipes()[0]
    return [base.model_copy(update={"name": f"Variant {i}", "design": base.design.model_copy(
        update={"variant_id": f"test-{i}"})}) for i in range(count)]


def evidence_for(recipes):
    return {recipe_id(r): VariantSearchEvidence(1000 - i, (), frozenset({("shop", f"p{i}")}))
            for i, r in enumerate(recipes)}


def test_large_family_is_bounded_but_original_cheapest_and_requested_extremes_survive():
    recipes = family(300)
    evidence = evidence_for(recipes)
    for i, r in enumerate(recipes):
        e = evidence[recipe_id(r)]
        evidence[recipe_id(r)] = VariantSearchEvidence(
            e.paid, (("protein_g", 1 if i == 10 else 100 if i == 20 else 40),), e.packages)
    chosen = library_variant_shortlist(recipes, evidence)
    assert len(chosen) == 4
    assert chosen == tuple(recipes[i] for i in (0, 10, 20, 299))
    assert library_variant_shortlist(recipes, evidence) == chosen


def test_shared_actual_packages_and_every_base_are_retained():
    recipes = family()
    other = recipes[0].model_copy(update={"name": "Other base", "design": recipes[0].design.model_copy(
        update={"base_id": "smako-test-other"})})
    all_recipes = [*recipes, other]
    evidence = evidence_for(all_recipes)
    shared = frozenset({("shop", "shared-product")})
    for r in (recipes[14], other):
        evidence[recipe_id(r)] = VariantSearchEvidence(1000, (), shared)
    chosen = library_variant_shortlist(all_recipes, evidence)
    assert len(chosen) == 5
    assert other in chosen and recipes[14] in chosen
    assert recipes[0] in chosen and recipes[-1] in chosen


def test_unknown_evidence_keeps_family_and_many_metrics_keep_their_extremes():
    recipes = family()
    evidence = evidence_for(recipes)
    del evidence[recipe_id(recipes[3])]
    assert library_variant_shortlist(recipes, evidence) == tuple(recipes)
    evidence = evidence_for(recipes)
    for i, r in enumerate(recipes):
        e = evidence[recipe_id(r)]
        values = tuple((name, 0 if i == j*2+1 else 100 if i == j*2+2 else 50)
                       for j, name in enumerate(("protein_g", "fat_g", "carbs_g")))
        evidence[recipe_id(r)] = VariantSearchEvidence(e.paid, values, e.packages)
    chosen = library_variant_shortlist(recipes, evidence)
    assert len(chosen) == 8  # protected extremes explicitly exceed nominal four
    assert all(r in chosen for r in [*recipes[:7], recipes[-1]])


def test_new_price_and_nutrition_signals_change_selection_without_global_cache():
    recipes = family()
    evidence = evidence_for(recipes)
    first = library_variant_shortlist(recipes, evidence)
    absent = next(r for r in recipes if r not in first)
    evidence[recipe_id(absent)] = VariantSearchEvidence(.01, (), frozenset())
    assert absent in library_variant_shortlist(recipes, evidence)


def test_unrequested_or_partially_known_nutrition_is_not_ranked_as_zero():
    recipes = family()
    evidence = evidence_for(recipes)
    e = evidence[recipe_id(recipes[14])]
    evidence[recipe_id(recipes[14])] = VariantSearchEvidence(e.paid, (("protein_g", 100),), e.packages)
    assert len(library_variant_shortlist(recipes, evidence)) == 4


def test_real_current_library_keeps_every_base():
    recipes = current_recipes()
    chosen = library_variant_shortlist(recipes, evidence_for(recipes))
    assert {r.design.base_id for r in chosen} == {r.design.base_id for r in recipes}
    assert len(chosen) <= len(recipes)
