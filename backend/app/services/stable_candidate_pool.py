"""Price-independent recipe retention and deterministic candidate unions.

The economic ingredient pool is intentionally useful as an *additive* signal,
but its ordering changes when a price context is added or refreshed.  This
module provides the other half of the search surface: a deterministic recipe
library derived solely from the versioned taxonomy and generator.  Keeping the
two origins explicit prevents a price refresh from silently replacing every
previously valid recipe before the basket search starts.

Nothing in this module prices products or weakens recipe validation.  Callers
must still run the ordinary structural, nutrition, semantic and quantity gates
after constructing the union.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from app.models.recipe import Recipe
from app.services.ingredient_taxonomy import INGREDIENT_TAXONOMY
from app.services.recipe_candidate_generator import (
    DeterministicRecipeCandidateGenerator,
)
from app.services.recipe_candidate_validator import ingredient_profile, recipe_id
from app.services.recipe_profile import RecipeProfile, RecipeProfileBuilder

STABLE_BASE_CANDIDATE_COUNT: Final = 120
DEFAULT_SEARCH_CANDIDATE_LIMIT: Final = 120


@dataclass(frozen=True, slots=True)
class StableCandidatePool:
    """One deterministic base plus price-aware additions.

    ``recipes`` always has base candidates first.  ``stable_recipe_ids`` makes
    retention explicit for the later quality-safe shortlist instead of relying
    on positional knowledge which can be lost during validation.
    """

    recipes: tuple[Recipe, ...]
    stable_recipe_ids: frozenset[str]
    stable_generated: int
    price_aware_received: int
    price_aware_added: int
    duplicate_additions: int


@dataclass(frozen=True, slots=True)
class CandidateShortlist:
    """A deterministic quality-safe shortlist with explicit retention stats."""

    recipes: tuple[Recipe, ...]
    received: int
    retained_stable: int
    retained_price_aware: int
    pruned: int


class StableCandidatePoolBuilder:
    """Build a version-stable base and merge price-aware candidates additively."""

    def __init__(
        self,
        *,
        stable_count: int = STABLE_BASE_CANDIDATE_COUNT,
        generator: DeterministicRecipeCandidateGenerator | None = None,
    ) -> None:
        if stable_count < 1 or stable_count > 300:
            raise ValueError("stable_count must be between 1 and 300")
        self.stable_count = stable_count
        self.generator = generator or DeterministicRecipeCandidateGenerator()

    def build(
        self,
        price_aware_candidates: list[Recipe] | tuple[Recipe, ...],
        *,
        servings: int,
    ) -> StableCandidatePool:
        """Return a deterministic superset without consulting product prices.

        The base generator receives the complete versioned taxonomy in its
        authoritative order.  Missing products are deliberately handled later
        by ``RecipeCandidateValidator``.  Consequently adding a valid product
        may make another base recipe eligible, but can never reshape or remove
        an already generated base recipe.
        """

        if servings < 1 or servings > 20:
            raise ValueError("servings must be between 1 and 20")
        stable = self.generator.generate_candidates(
            INGREDIENT_TAXONOMY,
            self.stable_count,
            servings,
        )
        stable_ids = frozenset(recipe_id(recipe) for recipe in stable)

        # Match the validator's conservative duplicate-profile semantics.  A
        # price-aware cosmetic variant must not displace its stable equivalent.
        seen_ids = set(stable_ids)
        seen_profiles = {ingredient_profile(recipe) for recipe in stable}
        additions: list[Recipe] = []
        duplicates = 0
        for recipe in price_aware_candidates:
            identity = recipe_id(recipe)
            profile = ingredient_profile(recipe)
            if identity in seen_ids or profile in seen_profiles:
                duplicates += 1
                continue
            seen_ids.add(identity)
            seen_profiles.add(profile)
            additions.append(recipe)

        return StableCandidatePool(
            recipes=(*stable, *additions),
            stable_recipe_ids=stable_ids,
            stable_generated=len(stable),
            price_aware_received=len(price_aware_candidates),
            price_aware_added=len(additions),
            duplicate_additions=duplicates,
        )


def _profile_dimensions(profile: RecipeProfile) -> tuple[str, ...]:
    return (
        f"family:{profile.recipe_family}",
        f"dish:{profile.dish_form}",
        f"protein:{profile.primary_protein or '-'}",
        f"carb:{profile.primary_carb or '-'}",
        f"cooking:{profile.cooking_method}",
    )


def stratified_candidate_shortlist(
    economically_ranked: Sequence[Recipe],
    *,
    limit: int,
    stable_recipe_ids: frozenset[str] = frozenset(),
    stratify_additions: bool = True,
    profile_builder: RecipeProfileBuilder | None = None,
) -> CandidateShortlist:
    """Retain every stable candidate, then fill additions deterministically.

    The input order is the caller's cheap-to-expensive ordering.  CHEAPEST can
    opt out of stratification, while BALANCED/VARIED use five explainable
    dimensions.  A limit smaller than the retained base fails explicitly; it
    never silently discards baseline recipes.
    """

    if limit < 1:
        raise ValueError("limit must be at least one")
    unique: list[Recipe] = []
    seen: set[str] = set()
    for recipe in economically_ranked:
        identity = recipe_id(recipe)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(recipe)

    stable = [recipe for recipe in unique if recipe_id(recipe) in stable_recipe_ids]
    if len(stable) > limit:
        raise ValueError(
            "candidate limit is smaller than the validated stable base; "
            "increase the limit instead of silently dropping baseline recipes"
        )
    if len(unique) <= limit:
        return CandidateShortlist(
            recipes=tuple(unique),
            received=len(economically_ranked),
            retained_stable=len(stable),
            retained_price_aware=len(unique) - len(stable),
            pruned=len(economically_ranked) - len(unique),
        )

    additions = [recipe for recipe in unique if recipe_id(recipe) not in stable_recipe_ids]
    slots = limit - len(stable)
    if not stratify_additions:
        selected_additions = additions[:slots]
    else:
        builder = profile_builder or RecipeProfileBuilder()
        profiles = {recipe_id(recipe): builder.build(recipe) for recipe in unique}
        dimensions = Counter(
            dimension
            for recipe in stable
            for dimension in _profile_dimensions(profiles[recipe_id(recipe)])
        )
        ranked = {recipe_id(recipe): index for index, recipe in enumerate(unique)}
        remaining = list(additions)
        selected_additions: list[Recipe] = []
        while remaining and len(selected_additions) < slots:
            chosen = min(
                remaining,
                key=lambda recipe: (
                    sum(
                        dimensions[dimension]
                        for dimension in _profile_dimensions(profiles[recipe_id(recipe)])
                    ),
                    max(
                        dimensions[dimension]
                        for dimension in _profile_dimensions(profiles[recipe_id(recipe)])
                    ),
                    ranked[recipe_id(recipe)],
                    recipe_id(recipe),
                ),
            )
            remaining.remove(chosen)
            selected_additions.append(chosen)
            dimensions.update(_profile_dimensions(profiles[recipe_id(chosen)]))

    selected_ids = {recipe_id(recipe) for recipe in (*stable, *selected_additions)}
    # Preserve caller ranking after deciding membership; beam tie-breaking and
    # cache artifacts therefore remain deterministic and economically ordered.
    selected = tuple(recipe for recipe in unique if recipe_id(recipe) in selected_ids)
    return CandidateShortlist(
        recipes=selected,
        received=len(economically_ranked),
        retained_stable=len(stable),
        retained_price_aware=len(selected_additions),
        pruned=len(economically_ranked) - len(selected),
    )


__all__ = [
    "DEFAULT_SEARCH_CANDIDATE_LIMIT",
    "STABLE_BASE_CANDIDATE_COUNT",
    "CandidateShortlist",
    "StableCandidatePool",
    "StableCandidatePoolBuilder",
    "stratified_candidate_shortlist",
]
