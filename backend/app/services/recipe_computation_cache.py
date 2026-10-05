"""Bounded request-local reuse of pure computations on exact recipe values."""

from dataclasses import dataclass, field

from app.models.recipe import Recipe
from app.services.ingredient_normalizer import canonicalize_ingredient_name


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


@dataclass(frozen=True, slots=True)
class ExactRecipeKey:
    """An exact value with its recursive hash computed only once."""

    value: tuple | None
    _hash: int = field(init=False, compare=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_hash", hash(self.value))

    def __hash__(self):
        return self._hash


class RecipeComputationCache:
    """Owned by one planner; never cache prices, nutrition or user decisions."""

    def __init__(self, *, limit=1024):
        self.limit = limit
        self.values = {}
        self._identities = {}
        self._interned = {}
        self._forms = {}

    def key(self, recipe):
        # Always take a fresh snapshot of mutable lists and the form dictionary.
        # Identity only locates the last exact value; it never approves a hit.
        # Retain a strong reference as well, so Python cannot reuse its ID.
        snapshot = recipe_value(recipe)
        previous = self._identities.get(id(recipe))
        if previous is not None and previous[0] is recipe and previous[1] == snapshot:
            return previous[2]
        key = ExactRecipeKey(snapshot)
        if len(self._identities) >= self.limit or len(self._interned) >= self.limit:
            self._identities.clear()
            self._interned.clear()
        key = self._interned.setdefault(key, key)
        self._identities[id(recipe)] = (recipe, snapshot, key)
        return key

    def forms_for(self, recipe, canonical_name):
        """Exact ordered input-form requirements, never product qualification."""
        key = self.key(recipe)
        if key not in self._forms:
            grouped = {}
            for ingredient in recipe.ingredients:
                name = canonicalize_ingredient_name(ingredient.name)
                grouped.setdefault(name, []).append(
                    (ingredient.form, tuple(ingredient.product_requirements or ())))
            if len(self._forms) >= self.limit:
                self._forms.clear()
            self._forms[key] = {name: tuple(rows) for name, rows in grouped.items()}
        return self._forms[key].get(canonical_name, ())

    def get(self, recipe, compute):
        # The callable is part of the key: e.g. different normalizer instances
        # cannot borrow each other's profiles. Only immutable results are used.
        key = (compute, self.key(recipe))
        if key not in self.values:
            value = compute(recipe)
            if len(self.values) >= self.limit:
                self.values.clear()
            self.values[key] = value
        return self.values[key]
