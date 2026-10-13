from __future__ import annotations

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.services import stable_candidate_pool
from app.services.ingredient_taxonomy import INGREDIENT_TAXONOMY
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator
from app.services.recipe_candidate_validator import ingredient_profile, recipe_id
from app.services.stable_candidate_pool import (
    StableCandidatePoolBuilder,
    stratified_candidate_shortlist,
)


def _addition(name: str, *, primary: str = "kyckling") -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=primary,
                canonical_name=primary,
                quantity=600,
                unit="g",
            ),
            RecipeIngredient(
                name="ris",
                canonical_name="ris",
                quantity=300,
                unit="g",
            ),
            RecipeIngredient(
                name="morot",
                canonical_name="morot",
                quantity=400,
                unit="g",
            ),
        ],
        instructions=["Tillaga allt."],
    )


def test_stable_base_is_identical_when_price_aware_candidates_change() -> None:
    builder = StableCandidatePoolBuilder(stable_count=20)

    without_addition = builder.build([], servings=4)
    with_addition = builder.build([_addition("Extern prisrätt")], servings=4)

    assert without_addition.recipes == with_addition.recipes[:20]
    assert without_addition.stable_recipe_ids == with_addition.stable_recipe_ids
    assert all(
        recipe_id(recipe) in with_addition.stable_recipe_ids
        for recipe in with_addition.recipes[:20]
    )


def test_price_aware_candidates_are_additive_and_deterministic() -> None:
    additions = [_addition("Zeta", primary="lax"), _addition("Alfa", primary="tofu")]
    builder = StableCandidatePoolBuilder(stable_count=20)

    first = builder.build(additions, servings=4)
    second = builder.build(additions, servings=4)

    assert first == second
    assert first.price_aware_received == 2
    assert first.price_aware_added == 2
    assert [recipe.name for recipe in first.recipes[-2:]] == ["Zeta", "Alfa"]


def test_stable_profile_wins_over_price_aware_cosmetic_duplicate() -> None:
    stable = DeterministicRecipeCandidateGenerator().generate_candidates(
        # The builder uses the taxonomy internally; this call only obtains a
        # real stable profile without duplicating generator implementation.
        INGREDIENT_TAXONOMY,
        20,
        4,
    )[0]
    cosmetic_duplicate = stable.model_copy(update={"name": "Nytt prisstyrt namn"})

    pool = StableCandidatePoolBuilder(stable_count=20).build(
        [cosmetic_duplicate],
        servings=4,
    )

    assert pool.price_aware_added == 0
    assert pool.duplicate_additions == 1
    assert ingredient_profile(cosmetic_duplicate) in {
        ingredient_profile(recipe) for recipe in pool.recipes
    }


def test_shortlist_retains_every_stable_recipe_before_price_aware_additions() -> None:
    stable = [
        _addition(f"Stable {index}", primary=primary)
        for index, primary in enumerate(
            ("kyckling", "lax", "tofu"),
            start=1,
        )
    ]
    additions = [
        _addition(f"Pris {index}", primary=primary)
        for index, primary in enumerate(("ägg", "bönor", "kikärtor"), start=1)
    ]
    ranked = [additions[0], stable[0], additions[1], stable[1], additions[2], stable[2]]
    stable_ids = frozenset(recipe_id(recipe) for recipe in stable)

    result = stratified_candidate_shortlist(
        ranked,
        limit=4,
        stable_recipe_ids=stable_ids,
    )

    assert stable_ids <= {recipe_id(recipe) for recipe in result.recipes}
    assert result.retained_stable == 3
    assert result.retained_price_aware == 1
    assert result.pruned == 2


def test_shortlist_fails_instead_of_silently_dropping_stable_base() -> None:
    stable = [
        _addition(f"Stable {index}", primary=primary)
        for index, primary in enumerate(
            ("kyckling", "lax", "tofu"),
            start=1,
        )
    ]

    with pytest.raises(ValueError, match="smaller than the validated stable base"):
        stratified_candidate_shortlist(
            stable,
            limit=2,
            stable_recipe_ids=frozenset(recipe_id(recipe) for recipe in stable),
        )


def test_stratified_additions_do_not_fill_shortlist_with_one_recipe_shape() -> None:
    repetitive = [
        _addition(f"Risgryta {index}", primary="kyckling")
        for index in range(3)
    ]
    diverse = _addition("Tofupasta", primary="tofu").model_copy(
        update={
            "ingredients": [
                RecipeIngredient(
                    name="tofu",
                    canonical_name="tofu",
                    quantity=600,
                    unit="g",
                ),
                RecipeIngredient(
                    name="pasta",
                    canonical_name="pasta",
                    quantity=300,
                    unit="g",
                ),
                RecipeIngredient(
                    name="broccoli",
                    canonical_name="broccoli",
                    quantity=400,
                    unit="g",
                ),
            ]
        }
    )

    result = stratified_candidate_shortlist(
        [*repetitive, diverse],
        limit=2,
        stratify_additions=True,
    )

    assert repetitive[0] in result.recipes
    assert diverse in result.recipes


def test_shortlist_reuses_ids_only_within_one_call_and_preserves_ranked_order(monkeypatch):
    ranked = [_addition(f"Pris {index}", primary=primary)
              for index, primary in enumerate(("kyckling", "lax", "tofu", "ägg"))]
    duplicate = ranked[0].model_copy(deep=True)
    calls = []

    def measured_id(recipe):
        calls.append(recipe)
        return recipe_id(recipe)

    monkeypatch.setattr(stable_candidate_pool, 'recipe_id', measured_id)
    result = stratified_candidate_shortlist([*ranked, duplicate], limit=3)
    assert len(calls) == 5
    assert result.received == 5 and result.pruned == 2
    assert list(result.recipes) == [r for r in ranked if r in result.recipes]

    ranked[-1].instructions.append("Blanda moroten först.")
    calls.clear()
    result = stratified_candidate_shortlist(
        ranked, limit=1, stable_recipe_ids=frozenset({recipe_id(ranked[-1])}),
    )
    assert result.recipes == (ranked[-1],)
    assert result.retained_stable == 1
    assert len(calls) == len(ranked)
