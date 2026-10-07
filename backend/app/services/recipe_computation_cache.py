"""Bounded request-local reuse of pure computations on exact recipe values."""

from collections import OrderedDict
from dataclasses import dataclass, field

from app.models.recipe import Recipe
from app.services.ingredient_normalizer import canonicalize_ingredient_name


def remember_bounded(mapping, key, value, limit):
    """Retain frequently used pure work without raising its existing bound."""
    if key not in mapping and len(mapping) >= limit:
        mapping.popitem(last=False)
    mapping[key] = value
    mapping.move_to_end(key)
    return value


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
        if limit < 1:
            raise ValueError("Recipe computation cache limit must be positive")
        self.limit = limit
        self.values = OrderedDict()
        self._identities = OrderedDict()
        self._interned = OrderedDict()
        self._forms = OrderedDict()

    def _put(self, mapping, key, value):
        # An additional recipe must not flush every frequently reused prefix.
        # The old bounds remain unchanged; evicted pure work is recomputed.
        remember_bounded(mapping, key, value, self.limit)

    def key(self, recipe):
        # Always take a fresh snapshot of mutable lists and the form dictionary.
        # Identity only locates the last exact value; it never approves a hit.
        # Retain a strong reference as well, so Python cannot reuse its ID.
        snapshot = recipe_value(recipe)
        previous = self._identities.get(id(recipe))
        if previous is not None and previous[0] is recipe and previous[1] == snapshot:
            self._identities.move_to_end(id(recipe))
            return previous[2]
        key = ExactRecipeKey(snapshot)
        key = self._interned.get(key, key)
        self._put(self._interned, key, key)
        self._put(self._identities, id(recipe), (recipe, snapshot, key))
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
            self._put(self._forms, key, {name: tuple(rows) for name, rows in grouped.items()})
        else:
            self._forms.move_to_end(key)
        return self._forms[key].get(canonical_name, ())

    def get(self, recipe, compute):
        # The callable is part of the key: e.g. different normalizer instances
        # cannot borrow each other's profiles. Only immutable results are used.
        key = (compute, self.key(recipe))
        if key not in self.values:
            value = compute(recipe)
            self._put(self.values, key, value)
        else:
            self.values.move_to_end(key)
        return self.values[key]
