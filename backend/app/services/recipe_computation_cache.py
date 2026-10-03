"""Bounded request-local reuse of pure computations on exact recipe values."""

from app.models.recipe import Recipe


def recipe_value(recipe: Recipe | None):
    if recipe is None:
        return None
    preparation = recipe.preparation
    # Models/ingredients/designs are frozen, but the two recipe lists and the
    # preparation form dictionary are not. Snapshot them, retaining unrounded
    # quantities and every version/provenance field. A new or edited value must
    # never inherit validation, a culinary profile or an ID from its old value.
    preparation_value = None if preparation is None else (
        preparation.version, preparation.origin, preparation.parent_sha256,
        preparation.family, tuple(preparation.input_forms.items()),
    )
    return (
        recipe.name, recipe.servings, tuple(recipe.ingredients), tuple(recipe.instructions),
        preparation_value, recipe.design,
    )


class RecipeComputationCache:
    """Owned by one planner; never cache prices, nutrition or user decisions."""

    def __init__(self, *, limit=512):
        self.limit = limit
        self.values = {}

    def get(self, recipe, compute):
        # The callable is part of the key: e.g. different normalizer instances
        # cannot borrow each other's profiles. Only immutable results are used.
        key = (compute, recipe_value(recipe))
        if key not in self.values:
            value = compute(recipe)
            if len(self.values) >= self.limit:
                self.values.clear()
            self.values[key] = value
        return self.values[key]
