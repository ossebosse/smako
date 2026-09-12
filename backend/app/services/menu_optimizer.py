"""Package-aware beam search for the cheapest complete weekly menu.

The search deliberately treats a menu as one basket.  Every evaluated state is
normalised and aggregated across all of its recipes before the existing
``BasketOptimizer`` chooses real packages and stores.  Per-recipe prices are
only used to order/prune candidates; they never determine the winning menu.
"""

from __future__ import annotations

from collections import Counter, OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from itertools import combinations
from math import comb
from time import perf_counter

from app.errors import IncompleteBasketError
from app.models.basket import (
    BasketAuditResult,
    BasketVerificationStatus,
    OptimizedBasket,
)
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate, SaleModel, SemanticConfidence
from app.models.recipe import Recipe
from app.models.store import Store
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import money
from app.services.basket_optimizer import BasketOptimizer
from app.services.ingredient_normalizer import IngredientNormalizer
from app.services.performance_trace import (
    increment_performance_counter,
    record_performance_depth,
    record_performance_seconds,
)
from app.services.price_universe import (
    BasketResultCache,
    PackageCostCache,
    PriceUniverse,
    canonical_requirement_items,
)
from app.services.recipe_candidate_validator import recipe_id
from app.services.recipe_profile import RecipeProfileBuilder
from app.services.stable_candidate_pool import stratified_candidate_shortlist

from grocery_data.app.domain.promotion_pricing import UserPricingContext

type RecipeClassifier = Callable[[Recipe], str | None]
@dataclass(frozen=True, order=True)
class IngredientProfile:
    """Search identity retains preparation; iteration exposes only real needs."""

    quantities: tuple[tuple[str, str, str], ...]
    preparation: tuple[str, str]

    def __iter__(self):
        return iter(self.quantities)


type StateKey = tuple[int | None, tuple[object, ...]]


_VERIFICATION_RANK: dict[BasketVerificationStatus, int] = {
    BasketVerificationStatus.VERIFIED: 0,
    BasketVerificationStatus.VERIFIED_WITH_ESTIMATES: 1,
    BasketVerificationStatus.UNVERIFIED: 2,
    BasketVerificationStatus.INVALID: 3,
}


def _candidate_checkout_floor(candidate: ProductCandidate) -> Decimal:
    """Return a conservative positive lower bound for any one purchase.

    Fixed-package and piece products always require at least one package/piece.
    A conditional multipack total may be cheaper than one ordinary package, so
    every active offer total participates in the minimum.  Weight-rate models
    deliberately return zero: an arbitrary positive requested weight has no
    source-proven minimum purchase value.  A weaker zero floor is preferable
    to an unsafe cost-bound prune.
    """

    if candidate.sale_model not in {
        SaleModel.FIXED_PACKAGE,
        SaleModel.SOLD_BY_PIECE,
    }:
        return Decimal(0)
    values = [candidate.price, candidate.effective_price]
    if candidate.sale_model == SaleModel.SOLD_BY_PIECE:
        values.append(candidate.piece_price)
    values.extend(offer.price for offer in candidate.offers if offer.is_active())
    positive = [money(value) for value in values if value is not None and value > 0]
    return min(positive, default=Decimal(0))


def admissible_checkout_lower_bound(
    profiles: Sequence[IngredientProfile],
    candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
    *,
    basket_auditor: BasketAuditor | None = None,
) -> Decimal:
    """Return an admissible optimistic floor for a partial recipe state.

    The bound ignores store constraints, quantities above one package and all
    future ingredients.  It therefore cannot exceed the authoritative final
    basket, including when a threshold promotion makes two packages cheaper
    than one.  This intentionally conservative contract is regression-tested
    against exhaustive small searches before it is allowed to prune.
    """

    auditor = basket_auditor or BasketAuditor()
    required_dimensions = {
        (canonical, unit)
        for profile in profiles
        for canonical, unit, _quantity in profile
        if not auditor.is_pantry(canonical)
    }
    result = Decimal(0)
    for canonical, _unit in sorted(required_dimensions):
        candidates = candidates_by_name.get(canonical, ())
        floors = [
            floor
            for candidate in candidates
            if (floor := _candidate_checkout_floor(candidate)) > 0
        ]
        # Missing/weight-only candidates contribute zero.  That keeps the
        # bound safe even for aliases which the optimizer resolves later.
        if floors:
            result += min(floors)
    return money(result)


def _evaluation_verification_rank(evaluation: _BasketEvaluation) -> int:
    return max(
        _VERIFICATION_RANK[evaluation.basket.verification_status],
        _VERIFICATION_RANK[evaluation.audit.verification_status],
    )


@dataclass(frozen=True, slots=True)
class DiversityConstraints:
    """Simple structural limits used while expanding the beam.

    Explicit mappings or resolvers are useful when candidate generation already
    knows a recipe's family and primary ingredient.  The local inference is a
    conservative fallback for the current ``Recipe`` model, which has no such
    fields yet.  Mapping keys are recipe names.
    """

    min_recipe_families: int = 0
    min_cooking_methods: int = 0
    target_recipe_count: int = 0
    min_reference_changes: int = 0
    reference_distinct_recipes: frozenset[str] = frozenset()
    max_same_primary_ingredient_meals: int | None = 2
    max_same_recipe_family: int | None = 2
    recipe_families: Mapping[str, str] = field(default_factory=dict)
    primary_ingredients: Mapping[str, str] = field(default_factory=dict)
    family_resolver: RecipeClassifier | None = None
    primary_ingredient_resolver: RecipeClassifier | None = None
    max_same_carbohydrate_meals: int | None = 3
    carbohydrates: Mapping[str, str] = field(default_factory=dict)
    carbohydrate_resolver: RecipeClassifier | None = None
    max_pairwise_recipe_similarity: float | None = 0.70
    pairwise_recipe_similarities: Mapping[tuple[str, str], float] = field(default_factory=dict)
    max_same_cooking_method: int | None = None
    max_same_dish_form: int | None = None
    cooking_methods: Mapping[str, str] = field(default_factory=dict)
    dish_forms: Mapping[str, str] = field(default_factory=dict)
    cooking_method_resolver: RecipeClassifier | None = None
    dish_form_resolver: RecipeClassifier | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "max_same_primary_ingredient_meals",
            "max_same_recipe_family",
            "max_same_carbohydrate_meals",
            "max_same_cooking_method",
            "max_same_dish_form",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 1:
                raise ValueError(f"{field_name} must be at least one or None")
        if (
            self.max_pairwise_recipe_similarity is not None
            and not 0 <= self.max_pairwise_recipe_similarity <= 1
        ):
            raise ValueError("max_pairwise_recipe_similarity must be between zero and one or None")
        if any(not 0 <= value <= 1 for value in self.pairwise_recipe_similarities.values()):
            raise ValueError("pairwise recipe similarities must be between zero and one")


@dataclass(frozen=True, slots=True)
class RecipeMarginalCost:
    """Deterministic basket change when a chosen recipe is added."""

    recipe_name: str
    previous_total: float
    new_total: float
    marginal_cost: float


@dataclass(frozen=True, slots=True)
class MenuSearchStats:
    """Debuggable counters for one isolated optimisation run."""

    candidate_count: int
    candidates_received: int
    candidates_deduplicated: int
    candidates_pruned: int
    beam_width: int
    states_evaluated: int
    cache_hits: int
    cache_misses: int
    basket_calculations: int
    cache_hit_rate: float
    diversity_rejections: int
    incomplete_rejections: int
    duplicate_state_rejections: int
    states_by_depth: tuple[int, ...]
    lower_bound_rejections: int = 0
    greedy_seed_evaluations: int = 0
    incremental_requirement_cache_hits: int = 0
    incremental_requirement_cache_misses: int = 0
    retained_stable_candidates: int = 0
    optimistic_bound_evaluations: int = 0
    optimistic_bound_rejections: int = 0
    possible_menu_combinations: int = 0
    expansion_candidates_visited: int = 0
    unique_economic_states: int = 0
    duplicate_economic_state_hits: int = 0
    full_basket_evaluations: int = 0


@dataclass(frozen=True, slots=True)
class MenuOptimizationResult:
    """Cheapest menu found by the configured beam search."""

    recipes: list[Recipe]
    basket: OptimizedBasket
    ingredients: list[NormalizedIngredient]
    stats: MenuSearchStats
    marginal_costs: list[RecipeMarginalCost]
    basket_audit: BasketAuditResult


@dataclass(frozen=True, slots=True)
class MenuVariantOptimizationResult:
    """Several constraint variants priced from one candidate/product snapshot."""

    results: Mapping[str, MenuOptimizationResult]
    errors: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class _BasketEvaluation:
    ingredients: tuple[NormalizedIngredient, ...]
    basket: OptimizedBasket
    audit: BasketAuditResult


@dataclass(frozen=True, slots=True)
class _Candidate:
    recipe: Recipe
    profile: IngredientProfile
    verification_rank: int
    individual_total: Decimal
    family: str | None
    primary_ingredient: str | None
    carbohydrate: str | None
    cooking_method: str | None
    dish_form: str | None


@dataclass(frozen=True, slots=True)
class _SearchState:
    recipes: tuple[Recipe, ...]
    profiles: frozenset[IngredientProfile]
    evaluation: _BasketEvaluation


@dataclass(frozen=True, slots=True)
class _PendingExpansion:
    """A beam expansion awaiting authoritative basket evaluation."""

    ordinal: int
    recipes: tuple[Recipe, ...]
    profiles: frozenset[IngredientProfile]
    optimistic_verification_rank: int
    optimistic_total: Decimal


@dataclass(slots=True)
class _MutableStats:
    states_evaluated: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    diversity_rejections: int = 0
    incomplete_rejections: int = 0
    duplicate_state_rejections: int = 0
    lower_bound_rejections: int = 0
    greedy_seed_evaluations: int = 0
    incremental_requirement_cache_hits: int = 0
    incremental_requirement_cache_misses: int = 0
    optimistic_bound_evaluations: int = 0
    optimistic_bound_cache_hits: int = 0
    optimistic_bound_rejections: int = 0
    expansion_candidates_visited: int = 0
    states_by_depth: list[int] = field(default_factory=list)


@dataclass(slots=True)
class _SharedEvaluationStore:
    successful: dict[StateKey, _BasketEvaluation] = field(default_factory=dict)
    incomplete: set[StateKey] = field(default_factory=set)
    lower_bounds: dict[frozenset[IngredientProfile], Decimal] = field(
        default_factory=dict
    )
    optimistic_bounds: dict[StateKey, tuple[int, Decimal] | None] = field(
        default_factory=dict
    )
    canonical_requirement_keys: dict[
        frozenset[IngredientProfile], tuple[object, ...]
    ] = field(default_factory=dict)
    checkout_floors: dict[str, Decimal] = field(default_factory=dict)


_PRIMARY_INGREDIENTS = frozenset(
    {
        "kyckling",
        "nötfärs",
        "blandfärs",
        "köttfärs",
        "fläskkött",
        "falukorv",
        "korv",
        "fisk",
        "lax",
        "ägg",
        "tofu",
        "linser",
        "bönor",
        "kidneybönor",
        "svarta bönor",
        "kikärtor",
        "vita bönor",
    }
)

_CARBOHYDRATES = frozenset({"potatis", "ris", "pasta", "nudlar", "couscous", "bröd", "tortillas"})

_FAMILY_NAME_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("risrätt", ("risrätt", "risratt")),
    ("nudelrätt", ("nudelrätt", "nudelratt")),
    ("potatisrätt", ("potatisrätt", "potatisratt")),
    ("soppa", ("soppa",)),
    ("pasta", ("pasta", "spaghetti", "spagetti", "makaron", "penne")),
    ("gryta", ("gryta", "chili", "curry")),
    ("wok", ("wok", "stekt ris")),
    ("panna", ("panna", "pytt")),
    ("tortilla", ("taco", "tortilla", "wrap")),
    ("gratäng", ("gratäng", "gratang")),
    ("ugn", ("ugns", "i ugn")),
    ("sallad", ("sallad",)),
)

_FAMILY_INGREDIENTS: tuple[tuple[str, frozenset[str]], ...] = (
    ("pasta", frozenset({"pasta"})),
    ("ris", frozenset({"ris"})),
    ("nudlar", frozenset({"nudlar"})),
    ("tortilla", frozenset({"tortillas"})),
    ("potatis", frozenset({"potatis"})),
    ("couscous", frozenset({"couscous"})),
)


class _EvaluationCache:
    """Per-run cache; product data must never leak between plan requests."""

    def __init__(
        self,
        *,
        normalizer: IngredientNormalizer,
        basket_optimizer: BasketOptimizer,
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        max_stores: int | None,
        stats: _MutableStats,
        basket_auditor: BasketAuditor,
        shared_store: _SharedEvaluationStore | None = None,
        price_universe: PriceUniverse | None = None,
        basket_result_cache: BasketResultCache | None = None,
        basket_optimizer_version: str = "basket-optimizer-v1",
        pricing_context_id: str = "pricing-context:public",
        user_pricing_context: UserPricingContext | None = None,
        canonical_requirement_cache: bool = False,
        incremental_requirement_reuse: bool = False,
        nested_store_limit: int | None = None,
    ) -> None:
        self.normalizer = normalizer
        self.basket_optimizer = basket_optimizer
        # The higher-level quote cache uses candidate-sequence identity.  A
        # tuple snapshot makes that identity exact for this request and also
        # isolates the running search from caller-side list mutation.  Keep
        # the legacy path untouched until search reuse is explicitly enabled.
        self.candidates_by_name = (
            {
                canonical: (
                    candidates
                    if isinstance(candidates, tuple)
                    else tuple(candidates)
                )
                for canonical, candidates in candidates_by_name.items()
            }
            if canonical_requirement_cache
            else candidates_by_name
        )
        self.stores = tuple(stores) if canonical_requirement_cache else stores
        self.max_stores = max_stores
        self.stats = stats
        self.basket_auditor = basket_auditor
        if (price_universe is None) != (basket_result_cache is None):
            raise ValueError(
                "price_universe and basket_result_cache must be supplied together"
            )
        self.price_universe = price_universe
        self.basket_result_cache = basket_result_cache
        self.basket_optimizer_version = basket_optimizer_version
        self.pricing_context_id = pricing_context_id
        self.user_pricing_context = user_pricing_context or UserPricingContext()
        self.canonical_requirement_cache = canonical_requirement_cache
        self.incremental_requirement_reuse = incremental_requirement_reuse
        self.nested_store_limit = nested_store_limit
        store = shared_store or _SharedEvaluationStore()
        self._successful = store.successful
        self._incomplete = store.incomplete
        self._recipe_ingredients: dict[IngredientProfile, tuple[NormalizedIngredient, ...]] = {}
        self._recipe_profiles: dict[int, tuple[Recipe, IngredientProfile]] = {}
        self._lower_bounds = store.lower_bounds
        self._optimistic_bounds = store.optimistic_bounds
        self._canonical_requirement_keys = store.canonical_requirement_keys
        self._checkout_floors = store.checkout_floors
        if not self._checkout_floors:
            for canonical, candidates in self.candidates_by_name.items():
                floors = tuple(
                    floor
                    for candidate in candidates
                    if (floor := _candidate_checkout_floor(candidate)) > 0
                )
                if floors:
                    self._checkout_floors[canonical] = min(floors)
        self._pantry_cache: dict[str, bool] = {}

    def register_recipe(self, profile: IngredientProfile, recipe: Recipe) -> None:
        """Materialize one recipe's normalized delta once per search run."""

        if not self.incremental_requirement_reuse or profile in self._recipe_ingredients:
            if self.incremental_requirement_reuse:
                self._recipe_profiles[id(recipe)] = (recipe, profile)
            return
        self._recipe_ingredients[profile] = tuple(
            self.normalizer.normalize_and_aggregate([recipe])
        )
        self._recipe_profiles[id(recipe)] = (recipe, profile)
        self.stats.incremental_requirement_cache_misses += 1

    def _ingredients_for(
        self,
        recipes: Sequence[Recipe],
        profiles: Sequence[IngredientProfile],
    ) -> list[NormalizedIngredient]:
        if not self.incremental_requirement_reuse:
            return self.normalizer.normalize_and_aggregate(recipes)

        recipe_rows: list[tuple[Recipe, tuple[NormalizedIngredient, ...]]] = []
        for recipe in recipes:
            identity = id(recipe)
            cached_profile = self._recipe_profiles.get(identity)
            if cached_profile is not None and cached_profile[0] is recipe:
                profile = cached_profile[1]
                normalized = self._recipe_ingredients[profile]
            else:
                normalized = tuple(self.normalizer.normalize_and_aggregate([recipe]))
                profile = IngredientProfile(tuple(
                    sorted(
                        (
                            ingredient.canonical_name,
                            ingredient.unit,
                            str(Decimal(str(ingredient.required_quantity)).normalize()),
                        )
                        for ingredient in normalized
                    )
                ), RecipeProfileBuilder._structure(recipe))
                self._recipe_profiles[identity] = (recipe, profile)
            cached = self._recipe_ingredients.get(profile)
            if cached is None:
                self._recipe_ingredients[profile] = normalized
                cached = normalized
                self.stats.incremental_requirement_cache_misses += 1
            else:
                self.stats.incremental_requirement_cache_hits += 1
            recipe_rows.append((recipe, cached))

        # Preserve the authoritative normalizer's first-seen display order and
        # source-recipe lineage while summing already-normalized deltas.
        aggregated: OrderedDict[tuple[str, str], dict[str, object]] = OrderedDict()
        for recipe, rows in recipe_rows:
            for ingredient in rows:
                key = (ingredient.canonical_name, ingredient.unit)
                if key not in aggregated:
                    aggregated[key] = {
                        "canonical_name": ingredient.canonical_name,
                        "required_quantity": Decimal(0),
                        "unit": ingredient.unit,
                        "display_name": ingredient.display_name,
                        "source_recipes": [],
                    }
                row = aggregated[key]
                row["required_quantity"] = row["required_quantity"] + Decimal(
                    str(ingredient.required_quantity)
                )
                source_recipes = row["source_recipes"]
                if recipe.name not in source_recipes:
                    source_recipes.append(recipe.name)
        return [
            # Every value is derived from already validated normalized recipe
            # deltas. Avoid repeating Pydantic validation for the hundreds of
            # thousands of immutable aggregate rows explored by the beam.
            NormalizedIngredient.model_construct(
                canonical_name=str(row["canonical_name"]),
                required_quantity=float(row["required_quantity"]),
                unit=str(row["unit"]),
                display_name=str(row["display_name"]),
                source_recipes=list(row["source_recipes"]),
            )
            for row in aggregated.values()
        ]

    def key_for(
        self,
        profiles: Sequence[IngredientProfile],
        ingredients: Sequence[NormalizedIngredient] | None = None,
    ) -> StateKey:
        # BasketOptimizer treats None and non-positive limits as unlimited.
        effective_limit = (
            None if self.max_stores is None or self.max_stores <= 0 else self.max_stores
        )
        if self.canonical_requirement_cache:
            if ingredients is None:
                raise ValueError("ingredients are required for canonical basket cache keys")
            return effective_limit, tuple(canonical_requirement_items(ingredients))
        return effective_limit, tuple(sorted(profiles))

    def key_for_profiles(self, profiles: Sequence[IngredientProfile]) -> StateKey:
        """Build the canonical requirement key from normalized recipe deltas.

        Ingredient profiles already contain canonical names, canonical units
        and normalized decimal quantities.  Summing those immutable deltas
        avoids constructing Pydantic ingredient rows merely to discover that
        another diversity variant has already priced the same basket.
        """

        effective_limit = (
            None if self.max_stores is None or self.max_stores <= 0 else self.max_stores
        )
        profile_set = profiles if isinstance(profiles, frozenset) else frozenset(profiles)
        items = self._canonical_requirement_keys.get(profile_set)
        if items is None:
            aggregated: dict[tuple[str, str], Decimal] = {}
            for profile in profile_set:
                for canonical, unit, quantity in profile:
                    key = (canonical, unit)
                    aggregated[key] = aggregated.get(key, Decimal(0)) + Decimal(
                        quantity
                    )
            items = tuple(
                (canonical, format(quantity.normalize(), "f"), unit)
                for (canonical, unit), quantity in sorted(aggregated.items())
            )
            self._canonical_requirement_keys[profile_set] = items
        return effective_limit, items

    def _is_pantry(self, canonical: str) -> bool:
        cached = self._pantry_cache.get(canonical)
        if cached is not None:
            return cached
        value = self.basket_auditor.is_pantry(canonical)
        self._pantry_cache[canonical] = value
        return value

    def lower_bound(self, profiles: Sequence[IngredientProfile]) -> Decimal:
        key = profiles if isinstance(profiles, frozenset) else frozenset(profiles)
        cached = self._lower_bounds.get(key)
        if cached is not None:
            return cached
        required_dimensions = {
            (canonical, unit)
            for profile in key
            for canonical, unit, _quantity in profile
            if not self._is_pantry(canonical)
        }
        value = money(
            sum(
                (
                    self._checkout_floors.get(canonical, Decimal(0))
                    for canonical, _unit in required_dimensions
                ),
                Decimal(0),
            )
        )
        self._lower_bounds[key] = value
        return value

    def optimistic_bound(
        self,
        recipes: Sequence[Recipe],
        profiles: Sequence[IngredientProfile],
    ) -> tuple[int, Decimal] | None:
        """Price one exact quantity relaxation once, without a store limit."""

        key = (
            self.key_for_profiles(profiles)
            if self.canonical_requirement_cache
            else self.key_for(profiles)
        )
        if key in self._optimistic_bounds:
            self.stats.optimistic_bound_cache_hits += 1
            return self._optimistic_bounds[key]
        target_store_limit = self.max_stores
        if (
            self.nested_store_limit is not None
            and self.nested_store_limit > 0
            and (
                target_store_limit is None
                or target_store_limit <= 0
                or self.nested_store_limit > target_store_limit
            )
        ):
            target_store_limit = self.nested_store_limit
        if self.canonical_requirement_cache:
            purchasable_requirements = tuple(
                item for item in key[1] if not self._is_pantry(str(item[0]))
            )
            nested = self.basket_optimizer.same_depth_nested_store_limited_requirement_keys(
                purchasable_requirements,
                self.candidates_by_name,
                self.stores,
                max_stores=target_store_limit,
            )
        else:
            ingredients = self._ingredients_for(recipes, profiles)
            purchasable = [
                ingredient
                for ingredient in ingredients
                if not self._is_pantry(ingredient.canonical_name)
            ]
            nested = self.basket_optimizer.same_depth_nested_store_limited_keys(
                purchasable,
                self.candidates_by_name,
                self.stores,
                max_stores=target_store_limit,
            )
        for cap, result in enumerate(nested, start=1):
            cap_key: StateKey = (cap, key[1])
            self._optimistic_bounds[cap_key] = (
                (result[0], result[1]) if result is not None else None
            )
        requested = nested[-1] if nested else None
        if key not in self._optimistic_bounds:
            self._optimistic_bounds[key] = (
                (requested[0], requested[1]) if requested is not None else None
            )
        leading_key = self._optimistic_bounds.get(key)
        self.stats.optimistic_bound_evaluations += 1
        return leading_key

    def _is_legacy_semantic_only_failure(
        self,
        audit: BasketAuditResult,
        basket: OptimizedBasket,
    ) -> bool:
        """Keep pre-confidence fixtures runnable without weakening strict live mode."""

        policy = self.basket_optimizer.verification_policy
        if policy.enforce_audit_verification or not policy.allow_legacy_low_without_evidence:
            return False
        items = [item for group in basket.stores for item in group.items]
        legacy_low = [item for item in items if item.semantic_confidence == SemanticConfidence.LOW]
        return (
            bool(legacy_low)
            and all(not item.semantic_evidence for item in legacy_low)
            and all(row.deficit_quantity == 0 and row.quantity_reconciled for row in audit.items)
        )

    def evaluate(
        self,
        recipes: Sequence[Recipe],
        profiles: Sequence[IngredientProfile],
    ) -> _BasketEvaluation | None:
        ingredients: list[NormalizedIngredient] | None = None
        key = (
            self.key_for_profiles(profiles)
            if self.canonical_requirement_cache
            else self.key_for(profiles)
        )
        self.stats.states_evaluated += 1
        if key in self._successful:
            self.stats.cache_hits += 1
            # The key proves equal canonical quantities, units and store cap,
            # so the cached basket and audit are authoritative for search
            # ranking. Recipe names are presentation lineage only; bind those
            # once for the eventual public winner in ``materialize`` instead
            # of repeating a full audit on every economic cache hit.
            return self._successful[key]
        if key in self._incomplete:
            self.stats.cache_hits += 1
            return None

        self.stats.cache_misses += 1
        if ingredients is None:
            ingredients = self._ingredients_for(recipes, profiles)
        purchasable_ingredients = [
            ingredient
            for ingredient in ingredients
            if not self._is_pantry(ingredient.canonical_name)
        ]
        try:
            def calculate_basket() -> OptimizedBasket:
                return self.basket_optimizer.optimize(
                    purchasable_ingredients,
                    self.candidates_by_name,
                    self.stores,
                    max_stores=self.max_stores,
                    calculate_savings=False,
                )

            if self.price_universe is not None and self.basket_result_cache is not None:
                basket = self.basket_result_cache.get_or_compute(
                    self.price_universe,
                    purchasable_ingredients,
                    allowed_context_ids=(store.store_id for store in self.stores),
                    max_stores=self.max_stores,
                    optimizer_version=self.basket_optimizer_version,
                    pricing_context_id=self.pricing_context_id,
                    factory=calculate_basket,
                )
            else:
                basket = calculate_basket()
        except (IncompleteBasketError, ValueError):
            self._incomplete.add(key)
            self.stats.incomplete_rejections += 1
            return None

        audit = self.basket_auditor.audit(
            ingredients,
            basket,
            user_pricing_context=self.user_pricing_context,
        )
        audit_is_acceptable = audit.passed or self._is_legacy_semantic_only_failure(audit, basket)
        if not audit_is_acceptable or (
            self.basket_optimizer.verification_policy.enforce_audit_verification
            and (
                basket.verification_status == BasketVerificationStatus.INVALID
                or audit.verification_status == BasketVerificationStatus.INVALID
            )
        ):
            self._incomplete.add(key)
            self.stats.incomplete_rejections += 1
            return None

        result = _BasketEvaluation(
            ingredients=tuple(ingredients),
            basket=basket,
            audit=audit,
        )
        self._successful[key] = result
        return result

    def materialize(
        self,
        recipes: Sequence[Recipe],
        profiles: Sequence[IngredientProfile],
        evaluation: _BasketEvaluation,
    ) -> _BasketEvaluation:
        """Bind exact recipe lineage to a cached economic evaluation once."""

        if not self.canonical_requirement_cache:
            return evaluation
        ingredients = self._ingredients_for(recipes, profiles)
        return _BasketEvaluation(
            ingredients=tuple(ingredients),
            basket=evaluation.basket,
            audit=self.basket_auditor.audit(
                ingredients,
                evaluation.basket,
                user_pricing_context=self.user_pricing_context,
            ),
        )


class MenuOptimizer:
    """Find a cheap diverse recipe set with package and store aware beam search."""

    def __init__(
        self,
        *,
        normalizer: IngredientNormalizer | None = None,
        basket_optimizer: BasketOptimizer | None = None,
        basket_auditor: BasketAuditor | None = None,
    ) -> None:
        self.normalizer = normalizer or IngredientNormalizer()
        self.basket_optimizer = basket_optimizer or BasketOptimizer()
        self.basket_auditor = basket_auditor or BasketAuditor()

    def _profile(self, recipe: Recipe) -> IngredientProfile:
        ingredients = self.normalizer.normalize_and_aggregate([recipe])
        return IngredientProfile(tuple(
            sorted(
                (
                    ingredient.canonical_name,
                    ingredient.unit,
                    str(Decimal(str(ingredient.required_quantity)).normalize()),
                )
                for ingredient in ingredients
            )
        ), RecipeProfileBuilder._structure(recipe))

    def optimize_slots(self, candidates_by_slot, *, evaluate, accepts, score, beam_width=12,
                       search_trace=None):
        """Use the same complete-basket search discipline for typed meal slots.

        ``evaluate`` aggregates ALL meal types, explicit extras and allocated stock
        through BasketOptimizer. Nothing is priced as separate meal baskets. The
        cache is request-local because stock, profile and locks are private inputs.
        """
        states = [([], None)]
        cache = {}
        for index, options in enumerate(candidates_by_slot):
            errors = []
            trace = {"depth": index + 1, "proposals": 0, "constraints_rejected": 0,
                     "evaluation_rejected": 0, "priced": 0, "retained": 0, "beam_pruned": 0}
            if search_trace is not None:
                search_trace.append(trace)
            expanded = []
            for chosen, _result in states:
                for slot in options:
                    slots = [*chosen, slot]
                    final = index == len(candidates_by_slot) - 1
                    trace["proposals"] += 1
                    if not accepts(slots, final=final):
                        trace["constraints_rejected"] += 1
                        continue
                    key = tuple((s.id, recipe_id(s.recipe) if s.recipe else None) for s in slots)
                    try:
                        if key not in cache:
                            cache[key] = evaluate(slots, final=final)
                        result = cache[key]
                        expanded.append((slots, result))
                        trace["priced"] += 1
                    except (IncompleteBasketError, ValueError) as exc:
                        trace["evaluation_rejected"] += 1
                        if len(errors) < 12:
                            errors.append(exc)
            if not expanded:
                if errors:
                    raise errors[-1]
                raise IncompleteBasketError("Inga kandidater uppfyller måltidsfördelningen och variationskraven.")
            expanded.sort(key=lambda state: score(*state))
            states = expanded[:beam_width]
            trace["retained"] = len(states)
            trace["beam_pruned"] = len(expanded) - len(states)
        if not candidates_by_slot:
            return [], evaluate([], final=True)
        return min(states, key=lambda state: score(*state))

    def accepts_recipes(self, recipes, constraints):
        classified = []
        for recipe in recipes:
            family, primary, carb, method, form = self._classify(recipe, constraints)
            classified.append(_Candidate(recipe=recipe, profile=self._profile(recipe),
                verification_rank=0, individual_total=Decimal(0), family=family,
                primary_ingredient=primary, carbohydrate=carb, cooking_method=method, dish_form=form))
        return self._satisfies_diversity(classified, constraints)

    def _mapping_value(self, mapping: Mapping[str, str], recipe: Recipe) -> str | None:
        direct = mapping.get(recipe.name)
        if direct:
            return direct.casefold().strip()
        target = recipe.name.casefold()
        for name, value in mapping.items():
            if name.casefold() == target and value.strip():
                return value.casefold().strip()
        return None

    def _infer_primary(self, recipe: Recipe) -> str | None:
        for ingredient in self.normalizer.normalize_and_aggregate([recipe]):
            if ingredient.canonical_name in _PRIMARY_INGREDIENTS:
                return ingredient.canonical_name
        return None

    def _infer_carbohydrate(self, recipe: Recipe) -> str | None:
        for ingredient in self.normalizer.normalize_and_aggregate([recipe]):
            if ingredient.canonical_name in _CARBOHYDRATES:
                return ingredient.canonical_name
        return None

    def _infer_family(self, recipe: Recipe) -> str | None:
        folded_name = recipe.name.casefold()
        for family, markers in _FAMILY_NAME_MARKERS:
            if any(marker in folded_name for marker in markers):
                return family

        canonical_names = {
            ingredient.canonical_name
            for ingredient in self.normalizer.normalize_and_aggregate([recipe])
        }
        for family, members in _FAMILY_INGREDIENTS:
            if canonical_names & members:
                return family
        return None

    def _classify(
        self,
        recipe: Recipe,
        constraints: DiversityConstraints,
    ) -> tuple[
        str | None,
        str | None,
        str | None,
        str | None,
        str | None,
    ]:
        family = self._mapping_value(constraints.recipe_families, recipe)
        if family is None and constraints.family_resolver is not None:
            family = constraints.family_resolver(recipe)
        if family is None:
            family = self._infer_family(recipe)

        primary = self._mapping_value(constraints.primary_ingredients, recipe)
        if primary is None and constraints.primary_ingredient_resolver is not None:
            primary = constraints.primary_ingredient_resolver(recipe)
        if primary is None:
            primary = self._infer_primary(recipe)

        carbohydrate = self._mapping_value(constraints.carbohydrates, recipe)
        if carbohydrate is None and constraints.carbohydrate_resolver is not None:
            carbohydrate = constraints.carbohydrate_resolver(recipe)
        if carbohydrate is None:
            carbohydrate = self._infer_carbohydrate(recipe)

        cooking_method = self._mapping_value(constraints.cooking_methods, recipe)
        if cooking_method is None and constraints.cooking_method_resolver is not None:
            cooking_method = constraints.cooking_method_resolver(recipe)

        dish_form = self._mapping_value(constraints.dish_forms, recipe)
        if dish_form is None and constraints.dish_form_resolver is not None:
            dish_form = constraints.dish_form_resolver(recipe)

        return (
            family.casefold().strip() if family else None,
            primary.casefold().strip() if primary else None,
            carbohydrate.casefold().strip() if carbohydrate else None,
            cooking_method.casefold().strip() if cooking_method else None,
            dish_form.casefold().strip() if dish_form else None,
        )

    @staticmethod
    def _satisfies_diversity(
        candidates: Sequence[_Candidate], constraints: DiversityConstraints
    ) -> bool:
        remaining = max(0, constraints.target_recipe_count - len(candidates))
        changed = sum(c.recipe.name in constraints.reference_distinct_recipes for c in candidates)
        if changed + remaining < constraints.min_reference_changes:
            return False
        if len({c.family for c in candidates if c.family}) + remaining < constraints.min_recipe_families:
            return False
        if len({c.cooking_method for c in candidates if c.cooking_method}) + remaining < constraints.min_cooking_methods:
            return False
        if constraints.max_same_recipe_family is not None:
            families = Counter(candidate.family for candidate in candidates if candidate.family)
            if families and max(families.values()) > constraints.max_same_recipe_family:
                return False
        if constraints.max_same_primary_ingredient_meals is not None:
            primaries = Counter(
                candidate.primary_ingredient
                for candidate in candidates
                if candidate.primary_ingredient
            )
            if (
                primaries
                and max(primaries.values()) > constraints.max_same_primary_ingredient_meals
            ):
                return False
        if constraints.max_same_carbohydrate_meals is not None:
            carbohydrates = Counter(
                candidate.carbohydrate for candidate in candidates if candidate.carbohydrate
            )
            if (
                carbohydrates
                and max(carbohydrates.values()) > constraints.max_same_carbohydrate_meals
            ):
                return False
        if constraints.max_same_cooking_method is not None:
            methods = Counter(
                candidate.cooking_method for candidate in candidates if candidate.cooking_method
            )
            if methods and max(methods.values()) > constraints.max_same_cooking_method:
                return False
        if constraints.max_same_dish_form is not None:
            forms = Counter(candidate.dish_form for candidate in candidates if candidate.dish_form)
            if forms and max(forms.values()) > constraints.max_same_dish_form:
                return False
        if constraints.max_pairwise_recipe_similarity is not None:
            for left, right in combinations(candidates, 2):
                key = tuple(
                    sorted(
                        (
                            left.recipe.name.casefold().strip(),
                            right.recipe.name.casefold().strip(),
                        )
                    )
                )
                score = constraints.pairwise_recipe_similarities.get(key)
                if score is not None and score >= constraints.max_pairwise_recipe_similarity:
                    return False
        return True

    @staticmethod
    def _state_sort_key(state: _SearchState) -> tuple[object, ...]:
        return (
            _evaluation_verification_rank(state.evaluation),
            money(state.evaluation.basket.total),
            state.evaluation.basket.store_count,
            tuple(sorted(state.profiles)),
        )

    @staticmethod
    def _nested_store_limits(
        max_stores: int | None,
        stores: Sequence[Store],
    ) -> tuple[int | None, ...]:
        """Return finite store caps whose feasible sets nest into the request.

        A beam is an approximation: ranking partial menus under a larger store
        cap can discard the winner found under a smaller cap even though that
        complete menu remains feasible.  Running the finite lower-cap
        frontiers in the same request gives the requested frontier a real,
        audited incumbent.  Unlimited legacy calls keep their existing single
        search; the consumer contract is the explicit finite 1/2/3 limit.
        """

        if max_stores is None or max_stores <= 1:
            return (max_stores,)
        store_count = len({str(getattr(store, "store_id", "")) for store in stores})
        effective_limit = min(max_stores, store_count)
        if effective_limit <= 1:
            return (max_stores,)
        return (*range(1, effective_limit), max_stores)

    def _reprice_nested_incumbent(
        self,
        result: MenuOptimizationResult,
        cache: _EvaluationCache,
        *,
        recipe_count: int,
        constraints: DiversityConstraints,
    ) -> _SearchState:
        """Reprice a lower-cap winner under the current, relaxed store cap.

        The returned state is built from the real recipes and an authoritative
        basket evaluation for the current cap.  No total, item, provenance or
        audit row is copied from the lower-cap result.
        """

        recipes = tuple(result.recipes)
        profiles = frozenset(self._profile(recipe) for recipe in recipes)
        if len(recipes) != recipe_count or len(profiles) != recipe_count:
            raise RuntimeError("A nested store-cap incumbent is not a complete menu")
        classified: list[_Candidate] = []
        for recipe in recipes:
            profile = self._profile(recipe)
            family, primary, carbohydrate, cooking_method, dish_form = self._classify(
                recipe,
                constraints,
            )
            classified.append(
                _Candidate(
                    recipe=recipe,
                    profile=profile,
                    verification_rank=0,
                    individual_total=Decimal(0),
                    family=family,
                    primary_ingredient=primary,
                    carbohydrate=carbohydrate,
                    cooking_method=cooking_method,
                    dish_form=dish_form,
                )
            )
        if not self._satisfies_diversity(classified, constraints):
            raise RuntimeError("A nested store-cap incumbent violates its search policy")
        for recipe in recipes:
            cache.register_recipe(self._profile(recipe), recipe)
        evaluation = cache.evaluate(recipes, tuple(profiles))
        if evaluation is None:
            raise RuntimeError(
                "A feasible lower store-cap menu became infeasible after relaxing the cap"
            )
        return _SearchState(
            recipes=recipes,
            profiles=profiles,
            evaluation=evaluation,
        )

    def _greedy_complete_state(
        self,
        candidates: Sequence[_Candidate],
        cache: _EvaluationCache,
        *,
        recipe_count: int,
        constraints: DiversityConstraints,
        empty_evaluation: _BasketEvaluation,
    ) -> _SearchState | None:
        """Build a deterministic feasible upper bound for safe cost pruning.

        This is not an approximate winner: it is a fully priced and audited
        complete menu.  The beam result is compared with it at the end.  If a
        greedy path gets trapped by diversity constraints, no bound is used.
        """

        state = _SearchState(
            recipes=(),
            profiles=frozenset(),
            evaluation=empty_evaluation,
        )
        by_profile = {candidate.profile: candidate for candidate in candidates}
        for _depth in range(recipe_count):
            selected = [by_profile[profile] for profile in state.profiles]
            pending: list[_PendingExpansion] = []
            for ordinal, candidate in enumerate(candidates):
                if candidate.profile in state.profiles:
                    continue
                if not self._satisfies_diversity([*selected, candidate], constraints):
                    continue
                profiles = state.profiles | {candidate.profile}
                recipes = (*state.recipes, candidate.recipe)
                optimistic = cache.optimistic_bound(recipes, profiles)
                if optimistic is None:
                    continue
                pending.append(
                    _PendingExpansion(
                        ordinal=ordinal,
                        recipes=recipes,
                        profiles=profiles,
                        optimistic_verification_rank=optimistic[0],
                        optimistic_total=optimistic[1],
                    )
                )
            pending.sort(
                key=lambda row: (
                    row.optimistic_verification_rank,
                    row.optimistic_total,
                    row.ordinal,
                    tuple(sorted(row.profiles)),
                )
            )
            best: _SearchState | None = None
            for index, row in enumerate(pending):
                if best is not None:
                    best_rank = _evaluation_verification_rank(best.evaluation)
                    best_total = money(best.evaluation.basket.total)
                    if row.optimistic_verification_rank > best_rank or (
                        row.optimistic_verification_rank == best_rank
                        and row.optimistic_total > best_total
                    ):
                        rejected = len(pending) - index
                        cache.stats.optimistic_bound_rejections += rejected
                        break
                evaluation = cache.evaluate(row.recipes, tuple(row.profiles))
                if evaluation is None:
                    continue
                candidate_state = _SearchState(
                    recipes=row.recipes,
                    profiles=row.profiles,
                    evaluation=evaluation,
                )
                if best is None or self._state_sort_key(
                    candidate_state
                ) < self._state_sort_key(best):
                    best = candidate_state
            if best is None:
                return None
            state = best
        return state

    def optimize(
        self,
        candidates: Sequence[Recipe],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        *,
        recipe_count: int = 5,
        max_stores: int | None = 2,
        beam_width: int = 40,
        diversity_constraints: DiversityConstraints | None = None,
        candidate_limit: int | None = None,
        price_universe: PriceUniverse | None = None,
        package_cost_cache: PackageCostCache | None = None,
        basket_result_cache: BasketResultCache | None = None,
        pricing_context_id: str = "pricing-context:public",
        user_pricing_context: UserPricingContext | None = None,
        retained_recipe_ids: frozenset[str] = frozenset(),
        stratified_candidate_pruning: bool = False,
        search_reuse_enabled: bool = False,
        admissible_lower_bound_enabled: bool = False,
    ) -> MenuOptimizationResult:
        """Search for a cheap menu within one request-local quote cache."""

        shared_evaluations = _SharedEvaluationStore()
        store_limits = self._nested_store_limits(max_stores, stores)
        with self.basket_optimizer.quote_cache(
            price_universe=price_universe,
            persistent_cache=package_cost_cache,
        ):
            if len(store_limits) > 1:
                return self._optimize_nested_store_caps(
                    candidates,
                    candidates_by_name,
                    stores,
                    store_limits=tuple(int(limit) for limit in store_limits),
                    recipe_count=recipe_count,
                    beam_width=beam_width,
                    diversity_constraints=diversity_constraints,
                    candidate_limit=candidate_limit,
                    shared_evaluations=shared_evaluations,
                    price_universe=price_universe,
                    basket_result_cache=basket_result_cache,
                    pricing_context_id=pricing_context_id,
                    user_pricing_context=user_pricing_context,
                    retained_recipe_ids=retained_recipe_ids,
                    stratified_candidate_pruning=stratified_candidate_pruning,
                    search_reuse_enabled=search_reuse_enabled,
                    admissible_lower_bound_enabled=admissible_lower_bound_enabled,
                )
            return self._optimize(
                candidates,
                candidates_by_name,
                stores,
                recipe_count=recipe_count,
                max_stores=max_stores,
                beam_width=beam_width,
                diversity_constraints=diversity_constraints,
                candidate_limit=candidate_limit,
                shared_evaluations=shared_evaluations,
                price_universe=price_universe,
                basket_result_cache=basket_result_cache,
                pricing_context_id=pricing_context_id,
                user_pricing_context=user_pricing_context,
                retained_recipe_ids=retained_recipe_ids,
                stratified_candidate_pruning=stratified_candidate_pruning,
                search_reuse_enabled=search_reuse_enabled,
                admissible_lower_bound_enabled=admissible_lower_bound_enabled,
            )

    def optimize_variants(
        self,
        candidates: Sequence[Recipe],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        variants: Mapping[str, DiversityConstraints],
        *,
        recipe_count: int = 5,
        max_stores: int | None = 2,
        beam_width: int = 40,
        candidate_limit: int | None = None,
        price_universe: PriceUniverse | None = None,
        package_cost_cache: PackageCostCache | None = None,
        basket_result_cache: BasketResultCache | None = None,
        pricing_context_id: str = "pricing-context:public",
        user_pricing_context: UserPricingContext | None = None,
        retained_recipe_ids: frozenset[str] = frozenset(),
        stratified_candidate_pruning: bool = False,
        search_reuse_enabled: bool = False,
        admissible_lower_bound_enabled: bool = False,
    ) -> MenuVariantOptimizationResult:
        """Run several diversity policies over one immutable candidate snapshot.

        Each mode keeps its own beam frontier, while deterministic state/basket
        evaluations and low-level package quotes are shared for this request.
        An infeasible alternative is reported without discarding feasible modes.
        """

        results: dict[str, MenuOptimizationResult] = {}
        errors: dict[str, str] = {}
        shared_evaluations = _SharedEvaluationStore()
        request_candidates_by_name: Mapping[
            str, Sequence[ProductCandidate]
        ] = candidates_by_name
        if search_reuse_enabled:
            # Freeze once for the whole multi-policy run.  Every variant then
            # sees the same exact sequence identities, allowing the bounded
            # quote-set cache to reuse work across CHEAPEST/BALANCED/VARIED as
            # well as within each beam.
            request_candidates_by_name = {
                canonical: (
                    candidates
                    if isinstance(candidates, tuple)
                    else tuple(candidates)
                )
                for canonical, candidates in candidates_by_name.items()
            }
        with self.basket_optimizer.quote_cache(
            price_universe=price_universe,
            persistent_cache=package_cost_cache,
        ):
            store_limits = self._nested_store_limits(max_stores, stores)
            for key, constraints in variants.items():
                try:
                    if len(store_limits) > 1:
                        results[key] = self._optimize_nested_store_caps(
                            candidates,
                            request_candidates_by_name,
                            stores,
                            store_limits=tuple(int(limit) for limit in store_limits),
                            recipe_count=recipe_count,
                            beam_width=beam_width,
                            diversity_constraints=constraints,
                            candidate_limit=candidate_limit,
                            shared_evaluations=shared_evaluations,
                            price_universe=price_universe,
                            basket_result_cache=basket_result_cache,
                            pricing_context_id=pricing_context_id,
                            user_pricing_context=user_pricing_context,
                            retained_recipe_ids=retained_recipe_ids,
                            stratified_candidate_pruning=stratified_candidate_pruning,
                            search_reuse_enabled=search_reuse_enabled,
                            admissible_lower_bound_enabled=admissible_lower_bound_enabled,
                        )
                    else:
                        results[key] = self._optimize(
                            candidates,
                            request_candidates_by_name,
                            stores,
                            recipe_count=recipe_count,
                            max_stores=max_stores,
                            beam_width=beam_width,
                            diversity_constraints=constraints,
                            candidate_limit=candidate_limit,
                            shared_evaluations=shared_evaluations,
                            price_universe=price_universe,
                            basket_result_cache=basket_result_cache,
                            pricing_context_id=pricing_context_id,
                            user_pricing_context=user_pricing_context,
                            retained_recipe_ids=retained_recipe_ids,
                            stratified_candidate_pruning=stratified_candidate_pruning,
                            search_reuse_enabled=search_reuse_enabled,
                            admissible_lower_bound_enabled=admissible_lower_bound_enabled,
                        )
                except IncompleteBasketError as exc:
                    errors[key] = str(exc)
        return MenuVariantOptimizationResult(results=results, errors=errors)

    def _result_from_winner(
        self,
        winner: _SearchState,
        cache: _EvaluationCache,
        mutable_stats: _MutableStats,
        scored: Sequence[_Candidate],
        *,
        candidates_received: int,
        candidates_deduplicated: int,
        candidates_pruned: int,
        recipe_count: int,
        beam_width: int,
        retained_recipe_ids: frozenset[str],
    ) -> MenuOptimizationResult:
        """Materialise public result/provenance for one authoritative frontier."""

        winner_evaluation = cache.materialize(
            winner.recipes,
            tuple(winner.profiles),
            winner.evaluation,
        )
        marginal_costs: list[RecipeMarginalCost] = []
        prefix_recipes: list[Recipe] = []
        prefix_profiles: list[IngredientProfile] = []
        previous_total = Decimal(0)
        for recipe in winner.recipes:
            profile = self._profile(recipe)
            prefix_recipes.append(recipe)
            prefix_profiles.append(profile)
            evaluation = cache.evaluate(prefix_recipes, prefix_profiles)
            if evaluation is None:  # Defensive: every winning prefix was feasible.
                raise RuntimeError("A cached winning menu prefix became incomplete")
            new_total = money(evaluation.basket.total)
            marginal_costs.append(
                RecipeMarginalCost(
                    recipe_name=recipe.name,
                    previous_total=float(previous_total),
                    new_total=float(new_total),
                    marginal_cost=float(money(new_total - previous_total)),
                )
            )
            previous_total = new_total

        hit_total = mutable_stats.cache_hits + mutable_stats.cache_misses
        stats = MenuSearchStats(
            candidate_count=len(scored),
            candidates_received=candidates_received,
            candidates_deduplicated=candidates_deduplicated,
            candidates_pruned=candidates_pruned,
            beam_width=beam_width,
            states_evaluated=mutable_stats.states_evaluated,
            cache_hits=mutable_stats.cache_hits,
            cache_misses=mutable_stats.cache_misses,
            basket_calculations=mutable_stats.cache_misses,
            cache_hit_rate=round(
                mutable_stats.cache_hits / hit_total if hit_total else 0.0,
                4,
            ),
            diversity_rejections=mutable_stats.diversity_rejections,
            incomplete_rejections=mutable_stats.incomplete_rejections,
            duplicate_state_rejections=mutable_stats.duplicate_state_rejections,
            states_by_depth=tuple(mutable_stats.states_by_depth),
            lower_bound_rejections=mutable_stats.lower_bound_rejections,
            greedy_seed_evaluations=mutable_stats.greedy_seed_evaluations,
            incremental_requirement_cache_hits=(
                mutable_stats.incremental_requirement_cache_hits
            ),
            incremental_requirement_cache_misses=(
                mutable_stats.incremental_requirement_cache_misses
            ),
            retained_stable_candidates=sum(
                recipe_id(candidate.recipe) in retained_recipe_ids
                for candidate in scored
            ),
            optimistic_bound_evaluations=mutable_stats.optimistic_bound_evaluations,
            optimistic_bound_rejections=mutable_stats.optimistic_bound_rejections,
            possible_menu_combinations=comb(len(scored), recipe_count),
            expansion_candidates_visited=mutable_stats.expansion_candidates_visited,
            unique_economic_states=mutable_stats.optimistic_bound_evaluations,
            duplicate_economic_state_hits=mutable_stats.optimistic_bound_cache_hits,
            full_basket_evaluations=mutable_stats.cache_misses,
        )
        if mutable_stats.incremental_requirement_cache_hits:
            increment_performance_counter(
                "incremental_requirement_cache_hits",
                mutable_stats.incremental_requirement_cache_hits,
            )
        if mutable_stats.incremental_requirement_cache_misses:
            increment_performance_counter(
                "incremental_requirement_cache_misses",
                mutable_stats.incremental_requirement_cache_misses,
            )
        for counter_name, amount in {
            "beam_states": mutable_stats.states_evaluated,
            "menu_cache_hits": mutable_stats.cache_hits,
            "menu_cache_misses": mutable_stats.cache_misses,
            "cache_hits": mutable_stats.cache_hits,
            "cache_misses": mutable_stats.cache_misses,
            "optimistic_bound_evaluations": (
                mutable_stats.optimistic_bound_evaluations
            ),
            "optimistic_bound_cache_hits": mutable_stats.optimistic_bound_cache_hits,
            "optimistic_bound_rejections": (
                mutable_stats.optimistic_bound_rejections
            ),
            "states_pruned_by_cost_bound": mutable_stats.lower_bound_rejections,
            "greedy_seed_evaluations": mutable_stats.greedy_seed_evaluations,
            "duplicate_state_rejections": mutable_stats.duplicate_state_rejections,
            "diversity_rejections": mutable_stats.diversity_rejections,
            "incomplete_rejections": mutable_stats.incomplete_rejections,
            "possible_menu_combinations": comb(len(scored), recipe_count),
            "expansion_candidates_visited": (
                mutable_stats.expansion_candidates_visited
            ),
            "unique_economic_states": mutable_stats.optimistic_bound_evaluations,
            "duplicate_economic_state_hits": (
                mutable_stats.optimistic_bound_cache_hits
            ),
            "full_basket_evaluations": mutable_stats.cache_misses,
        }.items():
            if amount:
                increment_performance_counter(counter_name, amount)
        return MenuOptimizationResult(
            recipes=list(winner.recipes),
            basket=winner_evaluation.basket,
            ingredients=list(winner_evaluation.ingredients),
            stats=stats,
            marginal_costs=marginal_costs,
            basket_audit=winner_evaluation.audit,
        )

    def _optimize_nested_store_caps(
        self,
        candidates: Sequence[Recipe],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        *,
        store_limits: tuple[int, ...],
        recipe_count: int,
        beam_width: int,
        diversity_constraints: DiversityConstraints | None,
        candidate_limit: int | None,
        shared_evaluations: _SharedEvaluationStore,
        price_universe: PriceUniverse | None,
        basket_result_cache: BasketResultCache | None,
        pricing_context_id: str,
        user_pricing_context: UserPricingContext | None,
        retained_recipe_ids: frozenset[str],
        stratified_candidate_pruning: bool,
        search_reuse_enabled: bool,
        admissible_lower_bound_enabled: bool,
    ) -> MenuOptimizationResult:
        """Search every nested finite store cap in one depth expansion.

        A separate beam and exact basket cache is retained for each cap, so
        cap-1/cap-2 ordering is identical to an isolated search.  Structural
        expansions shared by several frontiers are generated once and the
        basket optimizer's cumulative cap vector supplies every same-depth
        economic key in one exact store-subset scan.
        """

        started = perf_counter()
        if recipe_count < 1:
            raise ValueError("recipe_count must be at least one")
        if beam_width < 1:
            raise ValueError("beam_width must be at least one")
        if candidate_limit is not None and candidate_limit < recipe_count:
            raise ValueError("candidate_limit cannot be smaller than recipe_count")
        if not stores:
            raise IncompleteBasketError("No stores are available for menu optimisation")
        if not store_limits or any(limit < 1 for limit in store_limits):
            raise ValueError("nested store limits must be positive")
        if tuple(sorted(set(store_limits))) != store_limits:
            raise ValueError("nested store limits must be strictly increasing")
        increment_performance_counter("recipe_candidates_considered", len(candidates))

        constraints = diversity_constraints or DiversityConstraints()
        requested_limit = store_limits[-1]
        stats_by_cap = {limit: _MutableStats() for limit in store_limits}
        caches = {
            limit: _EvaluationCache(
                normalizer=self.normalizer,
                basket_optimizer=self.basket_optimizer,
                candidates_by_name=candidates_by_name,
                stores=stores,
                max_stores=limit,
                stats=stats_by_cap[limit],
                basket_auditor=self.basket_auditor,
                shared_store=shared_evaluations,
                price_universe=price_universe,
                basket_result_cache=basket_result_cache,
                pricing_context_id=pricing_context_id,
                user_pricing_context=user_pricing_context,
                canonical_requirement_cache=search_reuse_enabled,
                incremental_requirement_reuse=search_reuse_enabled,
                # A cap-only state should not pay for larger-cap subsets.  If
                # another frontier needs it, that frontier populates the full
                # cumulative vector before the smaller cap reads its key.
                nested_store_limit=limit,
            )
            for limit in store_limits
        }

        representatives: dict[IngredientProfile, Recipe] = {}
        for recipe in sorted(candidates, key=lambda row: row.name.casefold()):
            representatives.setdefault(self._profile(recipe), recipe)
        deduplicated_count = len(candidates) - len(representatives)
        classifications = {
            profile: self._classify(recipe, constraints)
            for profile, recipe in representatives.items()
        }

        scored_by_cap: dict[int, list[_Candidate]] = {}
        pruned_by_cap: dict[int, int] = {}
        failed_caps: set[int] = set()
        for limit in store_limits:
            cache = caches[limit]
            scored: list[_Candidate] = []
            for profile, recipe in representatives.items():
                cache.register_recipe(profile, recipe)
                evaluation = cache.evaluate([recipe], [profile])
                if evaluation is None:
                    continue
                family, primary, carbohydrate, cooking_method, dish_form = (
                    classifications[profile]
                )
                scored.append(
                    _Candidate(
                        recipe=recipe,
                        profile=profile,
                        verification_rank=_evaluation_verification_rank(evaluation),
                        individual_total=money(evaluation.basket.total),
                        family=family,
                        primary_ingredient=primary,
                        carbohydrate=carbohydrate,
                        cooking_method=cooking_method,
                        dish_form=dish_form,
                    )
                )
            scored.sort(
                key=lambda row: (
                    row.verification_rank,
                    row.individual_total,
                    row.recipe.name.casefold(),
                    row.profile,
                )
            )
            before_limit = len(scored)
            if candidate_limit is not None:
                if retained_recipe_ids or stratified_candidate_pruning:
                    shortlist = stratified_candidate_shortlist(
                        [candidate.recipe for candidate in scored],
                        limit=candidate_limit,
                        stable_recipe_ids=retained_recipe_ids,
                        stratify_additions=stratified_candidate_pruning,
                    )
                    selected_ids = {recipe_id(recipe) for recipe in shortlist.recipes}
                    scored = [
                        candidate
                        for candidate in scored
                        if recipe_id(candidate.recipe) in selected_ids
                    ]
                else:
                    scored = scored[:candidate_limit]
            scored_by_cap[limit] = scored
            pruned_by_cap[limit] = before_limit - len(scored)
            if len(scored) < recipe_count:
                failed_caps.add(limit)

        if requested_limit in failed_caps:
            available = len(scored_by_cap[requested_limit])
            raise IncompleteBasketError(
                f"Only {available} purchasable distinct recipe candidates are available; "
                f"{recipe_count} are required"
            )

        beams: dict[int, list[_SearchState]] = {}
        candidates_by_profile: dict[int, dict[IngredientProfile, _Candidate]] = {}
        incumbents: dict[int, _SearchState | None] = {}
        completed_caps: set[int] = set(failed_caps)
        for limit in store_limits:
            if limit in failed_caps:
                continue
            empty_evaluation = _BasketEvaluation(
                ingredients=(),
                basket=OptimizedBasket(
                    total=0,
                    stores=[],
                    max_stores=limit,
                    savings_vs_single_store=0,
                ),
                audit=self.basket_auditor.audit([], []),
            )
            beams[limit] = [
                _SearchState(
                    recipes=(),
                    profiles=frozenset(),
                    evaluation=empty_evaluation,
                )
            ]
            candidates_by_profile[limit] = {
                candidate.profile: candidate
                for candidate in scored_by_cap[limit]
            }
            incumbents[limit] = None

        if admissible_lower_bound_enabled:
            # Descending order lets a larger cap's exact cumulative vector
            # populate keys consumed by lower frontiers when their greedy
            # profiles happen to coincide.
            for limit in reversed(store_limits):
                if limit in failed_caps:
                    continue
                mutable_stats = stats_by_cap[limit]
                before = mutable_stats.states_evaluated
                incumbent = self._greedy_complete_state(
                    scored_by_cap[limit],
                    caches[limit],
                    recipe_count=recipe_count,
                    constraints=constraints,
                    empty_evaluation=beams[limit][0].evaluation,
                )
                incumbents[limit] = incumbent
                mutable_stats.greedy_seed_evaluations = (
                    mutable_stats.states_evaluated - before
                )

        for depth in range(1, recipe_count + 1):
            active_caps = tuple(
                limit for limit in store_limits if limit not in completed_caps
            )
            if not active_caps:
                break
            stat_baselines = {
                limit: (
                    stats_by_cap[limit].states_evaluated,
                    stats_by_cap[limit].diversity_rejections,
                    stats_by_cap[limit].incomplete_rejections,
                    stats_by_cap[limit].duplicate_state_rejections,
                    stats_by_cap[limit].lower_bound_rejections,
                )
                for limit in active_caps
            }
            expanded_by_cap: dict[
                int, dict[frozenset[IngredientProfile], _SearchState]
            ] = {limit: {} for limit in active_caps}
            raw_pending_by_cap: dict[
                int,
                dict[
                    frozenset[IngredientProfile],
                    tuple[int, tuple[Recipe, ...], frozenset[IngredientProfile]],
                ],
            ] = {limit: {} for limit in active_caps}
            diversity_by_profiles: dict[
                frozenset[IngredientProfile], bool
            ] = {}

            # Generate each cap's exact beam frontier.  Candidate order and
            # ordinals remain cap-specific; only identical structural states
            # share the later cumulative price-vector computation.
            for limit in active_caps:
                mutable_stats = stats_by_cap[limit]
                cache = caches[limit]
                scored = scored_by_cap[limit]
                by_profile = candidates_by_profile[limit]
                expansion_ordinal = 0
                for state in beams[limit]:
                    selected = [by_profile[profile] for profile in state.profiles]
                    for candidate in scored:
                        mutable_stats.expansion_candidates_visited += 1
                        if candidate.profile in state.profiles:
                            continue
                        profiles = state.profiles | {candidate.profile}
                        if (
                            profiles in expanded_by_cap[limit]
                            or profiles in raw_pending_by_cap[limit]
                        ):
                            mutable_stats.duplicate_state_rejections += 1
                            continue
                        diversity_allowed = diversity_by_profiles.get(profiles)
                        if diversity_allowed is None:
                            diversity_allowed = self._satisfies_diversity(
                                [*selected, candidate], constraints
                            )
                            diversity_by_profiles[profiles] = diversity_allowed
                        if not diversity_allowed:
                            mutable_stats.diversity_rejections += 1
                            continue
                        incumbent = incumbents[limit]
                        if (
                            admissible_lower_bound_enabled
                            and incumbent is not None
                            and _evaluation_verification_rank(incumbent.evaluation) == 0
                            and cache.lower_bound(profiles)
                            > money(incumbent.evaluation.basket.total)
                        ):
                            mutable_stats.lower_bound_rejections += 1
                            continue

                        recipes = (*state.recipes, candidate.recipe)
                        if admissible_lower_bound_enabled:
                            raw_pending_by_cap[limit][profiles] = (
                                expansion_ordinal,
                                recipes,
                                profiles,
                            )
                            expansion_ordinal += 1
                            continue
                        evaluation = cache.evaluate(recipes, tuple(profiles))
                        if evaluation is not None:
                            expanded_by_cap[limit][profiles] = _SearchState(
                                recipes=recipes,
                                profiles=profiles,
                                evaluation=evaluation,
                            )

            pending_by_cap: dict[
                int, dict[frozenset[IngredientProfile], _PendingExpansion]
            ] = {limit: {} for limit in active_caps}
            if admissible_lower_bound_enabled:
                caps_by_profiles: dict[
                    frozenset[IngredientProfile], list[int]
                ] = {}
                for limit in active_caps:
                    for profiles in raw_pending_by_cap[limit]:
                        caps_by_profiles.setdefault(profiles, []).append(limit)

                for profiles, needed_caps in caps_by_profiles.items():
                    largest_needed = max(needed_caps)
                    ordinal, recipes, _ = raw_pending_by_cap[largest_needed][profiles]
                    # This one miss computes every cumulative cap key up to the
                    # largest frontier that actually contains this state.
                    largest_optimistic = caches[largest_needed].optimistic_bound(
                        recipes,
                        profiles,
                    )
                    for limit in needed_caps:
                        ordinal, recipes, _ = raw_pending_by_cap[limit][profiles]
                        optimistic = (
                            largest_optimistic
                            if limit == largest_needed
                            else caches[limit].optimistic_bound(
                                recipes,
                                profiles,
                            )
                        )
                        if optimistic is None:
                            stats_by_cap[limit].incomplete_rejections += 1
                            continue
                        pending_by_cap[limit][profiles] = _PendingExpansion(
                            ordinal=ordinal,
                            recipes=recipes,
                            profiles=profiles,
                            optimistic_verification_rank=optimistic[0],
                            optimistic_total=optimistic[1],
                        )

            for limit in active_caps:
                mutable_stats = stats_by_cap[limit]
                expanded = expanded_by_cap[limit]
                pending = pending_by_cap[limit]
                exact_feasible_states = len(expanded)
                if admissible_lower_bound_enabled and pending:
                    ordered_pending = sorted(
                        pending.values(),
                        key=lambda row: (
                            row.optimistic_verification_rank,
                            row.optimistic_total,
                            row.ordinal,
                            tuple(sorted(row.profiles)),
                        ),
                    )
                    for pending_index, row in enumerate(ordered_pending):
                        if len(expanded) >= beam_width:
                            threshold = max(
                                expanded.values(), key=self._state_sort_key
                            )
                            threshold_rank = _evaluation_verification_rank(
                                threshold.evaluation
                            )
                            threshold_total = money(threshold.evaluation.basket.total)
                            if row.optimistic_verification_rank > threshold_rank or (
                                row.optimistic_verification_rank == threshold_rank
                                and row.optimistic_total > threshold_total
                            ):
                                rejected = len(ordered_pending) - pending_index
                                mutable_stats.lower_bound_rejections += rejected
                                mutable_stats.optimistic_bound_rejections += rejected
                                break
                        evaluation = caches[limit].evaluate(
                            row.recipes, tuple(row.profiles)
                        )
                        if evaluation is None:
                            continue
                        exact_feasible_states += 1
                        expanded[row.profiles] = _SearchState(
                            recipes=row.recipes,
                            profiles=row.profiles,
                            evaluation=evaluation,
                        )
                        if len(expanded) > beam_width:
                            worst = max(expanded.values(), key=self._state_sort_key)
                            del expanded[worst.profiles]

                if not expanded:
                    incumbent = incumbents[limit]
                    if incumbent is not None:
                        beams[limit] = [incumbent]
                    else:
                        failed_caps.add(limit)
                    completed_caps.add(limit)
                    continue
                beams[limit] = sorted(
                    expanded.values(), key=self._state_sort_key
                )[:beam_width]
                mutable_stats.states_by_depth.append(len(beams[limit]))
                if limit == requested_limit:
                    (
                        states_before,
                        diversity_before,
                        incomplete_before,
                        duplicate_before,
                        lower_bound_before,
                    ) = stat_baselines[limit]
                    record_performance_depth(
                        depth,
                        states_evaluated=(
                            mutable_stats.states_evaluated - states_before
                        ),
                        states_expanded=exact_feasible_states,
                        states_kept=len(beams[limit]),
                        diversity_rejections=(
                            mutable_stats.diversity_rejections - diversity_before
                        ),
                        incomplete_rejections=(
                            mutable_stats.incomplete_rejections - incomplete_before
                        ),
                        duplicate_state_rejections=(
                            mutable_stats.duplicate_state_rejections - duplicate_before
                        ),
                        cost_bound_rejections=(
                            mutable_stats.lower_bound_rejections - lower_bound_before
                        ),
                    )

        if requested_limit in failed_caps:
            raise IncompleteBasketError(
                "No complete menu satisfies the basket and diversity constraints"
            )

        # Fold the independently preserved frontiers into the relaxed cap.
        # Re-evaluation is authoritative: no lower-cap total, store row or
        # provenance is copied into a higher-cap result.
        carried: _SearchState | None = None
        winner_by_cap: dict[int, _SearchState] = {}
        for limit in store_limits:
            if limit in failed_caps:
                continue
            incumbent = incumbents[limit]
            winner = min(
                (
                    *beams[limit],
                    *((incumbent,) if incumbent is not None else ()),
                ),
                key=self._state_sort_key,
            )
            if carried is not None:
                carried_evaluation = caches[limit].evaluate(
                    carried.recipes,
                    tuple(carried.profiles),
                )
                if carried_evaluation is None:
                    raise RuntimeError(
                        "A feasible lower store-cap menu became infeasible after relaxing the cap"
                    )
                repriced = _SearchState(
                    recipes=carried.recipes,
                    profiles=carried.profiles,
                    evaluation=carried_evaluation,
                )
                if self._state_sort_key(repriced) < self._state_sort_key(winner):
                    winner = repriced
            winner_by_cap[limit] = winner
            carried = winner

        winner = winner_by_cap[requested_limit]
        result = self._result_from_winner(
            winner,
            caches[requested_limit],
            stats_by_cap[requested_limit],
            scored_by_cap[requested_limit],
            candidates_received=len(candidates),
            candidates_deduplicated=deduplicated_count,
            candidates_pruned=pruned_by_cap[requested_limit],
            recipe_count=recipe_count,
            beam_width=beam_width,
            retained_recipe_ids=retained_recipe_ids,
        )
        record_performance_seconds("menu_search", perf_counter() - started)
        return result

    def _optimize(
        self,
        candidates: Sequence[Recipe],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        *,
        recipe_count: int = 5,
        max_stores: int | None = 2,
        beam_width: int = 40,
        diversity_constraints: DiversityConstraints | None = None,
        candidate_limit: int | None = None,
        shared_evaluations: _SharedEvaluationStore | None = None,
        price_universe: PriceUniverse | None = None,
        basket_result_cache: BasketResultCache | None = None,
        pricing_context_id: str = "pricing-context:public",
        user_pricing_context: UserPricingContext | None = None,
        retained_recipe_ids: frozenset[str] = frozenset(),
        stratified_candidate_pruning: bool = False,
        search_reuse_enabled: bool = False,
        admissible_lower_bound_enabled: bool = False,
        nested_store_incumbent: MenuOptimizationResult | None = None,
        nested_store_limit: int | None = None,
    ) -> MenuOptimizationResult:
        """Search for exactly ``recipe_count`` recipes as one real basket.

        ``candidate_limit`` is the optional individual-cost pruning bound.  It
        is intentionally separate from ``beam_width`` and defaults to no
        pruning, so individually expensive candidates can still win through
        shared packages.
        """

        started = perf_counter()
        if recipe_count < 1:
            raise ValueError("recipe_count must be at least one")
        if beam_width < 1:
            raise ValueError("beam_width must be at least one")
        if candidate_limit is not None and candidate_limit < recipe_count:
            raise ValueError("candidate_limit cannot be smaller than recipe_count")
        if not stores:
            raise IncompleteBasketError("No stores are available for menu optimisation")
        increment_performance_counter("recipe_candidates_considered", len(candidates))

        constraints = diversity_constraints or DiversityConstraints()
        mutable_stats = _MutableStats()
        cache = _EvaluationCache(
            normalizer=self.normalizer,
            basket_optimizer=self.basket_optimizer,
            candidates_by_name=candidates_by_name,
            stores=stores,
            max_stores=max_stores,
            stats=mutable_stats,
            basket_auditor=self.basket_auditor,
            shared_store=shared_evaluations,
            price_universe=price_universe,
            basket_result_cache=basket_result_cache,
            pricing_context_id=pricing_context_id,
            user_pricing_context=user_pricing_context,
            canonical_requirement_cache=search_reuse_enabled,
            incremental_requirement_reuse=search_reuse_enabled,
            nested_store_limit=nested_store_limit,
        )

        # Stable profile dedupe prevents cosmetic recipe variants from filling
        # the beam with identical ingredient requirements.
        representatives: dict[IngredientProfile, Recipe] = {}
        for recipe in sorted(candidates, key=lambda row: row.name.casefold()):
            representatives.setdefault(self._profile(recipe), recipe)
        deduplicated_count = len(candidates) - len(representatives)

        scored: list[_Candidate] = []
        for profile, recipe in representatives.items():
            cache.register_recipe(profile, recipe)
            evaluation = cache.evaluate([recipe], [profile])
            if evaluation is None:
                continue
            family, primary, carbohydrate, cooking_method, dish_form = self._classify(
                recipe, constraints
            )
            scored.append(
                _Candidate(
                    recipe=recipe,
                    profile=profile,
                    verification_rank=_evaluation_verification_rank(evaluation),
                    individual_total=money(evaluation.basket.total),
                    family=family,
                    primary_ingredient=primary,
                    carbohydrate=carbohydrate,
                    cooking_method=cooking_method,
                    dish_form=dish_form,
                )
            )

        scored.sort(
            key=lambda row: (
                row.verification_rank,
                row.individual_total,
                row.recipe.name.casefold(),
                row.profile,
            )
        )
        before_limit = len(scored)
        if candidate_limit is not None:
            if retained_recipe_ids or stratified_candidate_pruning:
                shortlist = stratified_candidate_shortlist(
                    [candidate.recipe for candidate in scored],
                    limit=candidate_limit,
                    stable_recipe_ids=retained_recipe_ids,
                    stratify_additions=stratified_candidate_pruning,
                )
                selected_ids = {recipe_id(recipe) for recipe in shortlist.recipes}
                scored = [
                    candidate
                    for candidate in scored
                    if recipe_id(candidate.recipe) in selected_ids
                ]
            else:
                scored = scored[:candidate_limit]
        pruned_count = before_limit - len(scored)
        if len(scored) < recipe_count:
            raise IncompleteBasketError(
                f"Only {len(scored)} purchasable distinct recipe candidates are available; "
                f"{recipe_count} are required"
            )

        empty_evaluation = _BasketEvaluation(
            ingredients=(),
            basket=OptimizedBasket(
                total=0,
                stores=[],
                max_stores=None if max_stores is None or max_stores <= 0 else max_stores,
                savings_vs_single_store=0,
            ),
            audit=self.basket_auditor.audit([], []),
        )
        beam = [_SearchState(recipes=(), profiles=frozenset(), evaluation=empty_evaluation)]
        candidate_by_profile = {candidate.profile: candidate for candidate in scored}

        incumbent: _SearchState | None = None
        if nested_store_incumbent is not None:
            incumbent = self._reprice_nested_incumbent(
                nested_store_incumbent,
                cache,
                recipe_count=recipe_count,
                constraints=constraints,
            )
        if admissible_lower_bound_enabled:
            seed_evaluations_before = mutable_stats.states_evaluated
            greedy_incumbent = self._greedy_complete_state(
                scored,
                cache,
                recipe_count=recipe_count,
                constraints=constraints,
                empty_evaluation=empty_evaluation,
            )
            if greedy_incumbent is not None and (
                incumbent is None
                or self._state_sort_key(greedy_incumbent)
                < self._state_sort_key(incumbent)
            ):
                incumbent = greedy_incumbent
            mutable_stats.greedy_seed_evaluations = (
                mutable_stats.states_evaluated - seed_evaluations_before
            )

        for _depth in range(1, recipe_count + 1):
            states_before = mutable_stats.states_evaluated
            diversity_before = mutable_stats.diversity_rejections
            incomplete_before = mutable_stats.incomplete_rejections
            duplicate_before = mutable_stats.duplicate_state_rejections
            lower_bound_before = mutable_stats.lower_bound_rejections
            expanded: dict[frozenset[IngredientProfile], _SearchState] = {}
            pending: dict[frozenset[IngredientProfile], _PendingExpansion] = {}
            expansion_ordinal = 0
            for state in beam:
                selected = [candidate_by_profile[profile] for profile in state.profiles]
                for candidate in scored:
                    mutable_stats.expansion_candidates_visited += 1
                    if candidate.profile in state.profiles:
                        continue
                    profiles = state.profiles | {candidate.profile}
                    if profiles in expanded or profiles in pending:
                        mutable_stats.duplicate_state_rejections += 1
                        continue
                    if not self._satisfies_diversity([*selected, candidate], constraints):
                        mutable_stats.diversity_rejections += 1
                        continue

                    if (
                        admissible_lower_bound_enabled
                        and
                        incumbent is not None
                        and _evaluation_verification_rank(incumbent.evaluation) == 0
                        and cache.lower_bound(profiles)
                        > money(incumbent.evaluation.basket.total)
                    ):
                        mutable_stats.lower_bound_rejections += 1
                        continue

                    recipes = (*state.recipes, candidate.recipe)
                    if admissible_lower_bound_enabled:
                        optimistic = cache.optimistic_bound(recipes, profiles)
                        if optimistic is None:
                            mutable_stats.incomplete_rejections += 1
                            continue
                        pending[profiles] = _PendingExpansion(
                            ordinal=expansion_ordinal,
                            recipes=recipes,
                            profiles=profiles,
                            optimistic_verification_rank=optimistic[0],
                            optimistic_total=optimistic[1],
                        )
                        expansion_ordinal += 1
                        continue

                    evaluation = cache.evaluate(recipes, tuple(profiles))
                    if evaluation is None:
                        continue
                    expanded[profiles] = _SearchState(
                        recipes=recipes,
                        profiles=profiles,
                        evaluation=evaluation,
                    )

            exact_feasible_states = len(expanded)
            if admissible_lower_bound_enabled and pending:
                ordered_pending = sorted(
                    pending.values(),
                    key=lambda row: (
                        row.optimistic_verification_rank,
                        row.optimistic_total,
                        row.ordinal,
                        tuple(sorted(row.profiles)),
                    ),
                )
                for pending_index, row in enumerate(ordered_pending):
                    if len(expanded) >= beam_width:
                        threshold = max(expanded.values(), key=self._state_sort_key)
                        threshold_rank = _evaluation_verification_rank(
                            threshold.evaluation
                        )
                        threshold_total = money(threshold.evaluation.basket.total)
                        if row.optimistic_verification_rank > threshold_rank or (
                            row.optimistic_verification_rank == threshold_rank
                            and row.optimistic_total > threshold_total
                        ):
                            rejected = len(ordered_pending) - pending_index
                            mutable_stats.lower_bound_rejections += rejected
                            mutable_stats.optimistic_bound_rejections += rejected
                            break
                    evaluation = cache.evaluate(row.recipes, tuple(row.profiles))
                    if evaluation is None:
                        continue
                    exact_feasible_states += 1
                    expanded[row.profiles] = _SearchState(
                        recipes=row.recipes,
                        profiles=row.profiles,
                        evaluation=evaluation,
                    )
                    if len(expanded) > beam_width:
                        worst = max(expanded.values(), key=self._state_sort_key)
                        del expanded[worst.profiles]

            if not expanded:
                if incumbent is not None:
                    beam = [incumbent]
                    break
                raise IncompleteBasketError(
                    "No complete menu satisfies the basket and diversity constraints"
                )
            ordered = sorted(expanded.values(), key=self._state_sort_key)
            beam = ordered[:beam_width]
            mutable_stats.states_by_depth.append(len(beam))
            record_performance_depth(
                _depth,
                states_evaluated=mutable_stats.states_evaluated - states_before,
                states_expanded=exact_feasible_states,
                states_kept=len(beam),
                diversity_rejections=(
                    mutable_stats.diversity_rejections - diversity_before
                ),
                incomplete_rejections=(
                    mutable_stats.incomplete_rejections - incomplete_before
                ),
                duplicate_state_rejections=(
                    mutable_stats.duplicate_state_rejections - duplicate_before
                ),
                cost_bound_rejections=(
                    mutable_stats.lower_bound_rejections - lower_bound_before
                ),
            )

        winner = min(
            (*beam, *((incumbent,) if incumbent is not None else ())),
            key=self._state_sort_key,
        )
        winner_evaluation = cache.materialize(
            winner.recipes,
            tuple(winner.profiles),
            winner.evaluation,
        )
        marginal_costs: list[RecipeMarginalCost] = []
        prefix_recipes: list[Recipe] = []
        prefix_profiles: list[IngredientProfile] = []
        previous_total = Decimal(0)
        for recipe in winner.recipes:
            profile = self._profile(recipe)
            prefix_recipes.append(recipe)
            prefix_profiles.append(profile)
            evaluation = cache.evaluate(prefix_recipes, prefix_profiles)
            if evaluation is None:  # Defensive: every winning prefix was feasible.
                raise RuntimeError("A cached winning menu prefix became incomplete")
            new_total = money(evaluation.basket.total)
            marginal_costs.append(
                RecipeMarginalCost(
                    recipe_name=recipe.name,
                    previous_total=float(previous_total),
                    new_total=float(new_total),
                    marginal_cost=float(money(new_total - previous_total)),
                )
            )
            previous_total = new_total

        hit_total = mutable_stats.cache_hits + mutable_stats.cache_misses
        stats = MenuSearchStats(
            candidate_count=len(scored),
            candidates_received=len(candidates),
            candidates_deduplicated=deduplicated_count,
            candidates_pruned=pruned_count,
            beam_width=beam_width,
            states_evaluated=mutable_stats.states_evaluated,
            cache_hits=mutable_stats.cache_hits,
            cache_misses=mutable_stats.cache_misses,
            basket_calculations=mutable_stats.cache_misses,
            cache_hit_rate=round(
                mutable_stats.cache_hits / hit_total if hit_total else 0.0,
                4,
            ),
            diversity_rejections=mutable_stats.diversity_rejections,
            incomplete_rejections=mutable_stats.incomplete_rejections,
            duplicate_state_rejections=mutable_stats.duplicate_state_rejections,
            states_by_depth=tuple(mutable_stats.states_by_depth),
            lower_bound_rejections=mutable_stats.lower_bound_rejections,
            greedy_seed_evaluations=mutable_stats.greedy_seed_evaluations,
            incremental_requirement_cache_hits=(
                mutable_stats.incremental_requirement_cache_hits
            ),
            incremental_requirement_cache_misses=(
                mutable_stats.incremental_requirement_cache_misses
            ),
            retained_stable_candidates=sum(
                recipe_id(candidate.recipe) in retained_recipe_ids for candidate in scored
            ),
            optimistic_bound_evaluations=mutable_stats.optimistic_bound_evaluations,
            optimistic_bound_rejections=mutable_stats.optimistic_bound_rejections,
            possible_menu_combinations=comb(len(scored), recipe_count),
            expansion_candidates_visited=mutable_stats.expansion_candidates_visited,
            unique_economic_states=mutable_stats.optimistic_bound_evaluations,
            duplicate_economic_state_hits=mutable_stats.optimistic_bound_cache_hits,
            full_basket_evaluations=mutable_stats.cache_misses,
        )
        if mutable_stats.incremental_requirement_cache_hits:
            increment_performance_counter(
                "incremental_requirement_cache_hits",
                mutable_stats.incremental_requirement_cache_hits,
            )
        if mutable_stats.incremental_requirement_cache_misses:
            increment_performance_counter(
                "incremental_requirement_cache_misses",
                mutable_stats.incremental_requirement_cache_misses,
            )
        for counter_name, amount in {
            "beam_states": mutable_stats.states_evaluated,
            "menu_cache_hits": mutable_stats.cache_hits,
            "menu_cache_misses": mutable_stats.cache_misses,
            "cache_hits": mutable_stats.cache_hits,
            "cache_misses": mutable_stats.cache_misses,
            "optimistic_bound_evaluations": (
                mutable_stats.optimistic_bound_evaluations
            ),
            "optimistic_bound_cache_hits": mutable_stats.optimistic_bound_cache_hits,
            "optimistic_bound_rejections": (
                mutable_stats.optimistic_bound_rejections
            ),
            "states_pruned_by_cost_bound": mutable_stats.lower_bound_rejections,
            "greedy_seed_evaluations": mutable_stats.greedy_seed_evaluations,
            "duplicate_state_rejections": (
                mutable_stats.duplicate_state_rejections
            ),
            "diversity_rejections": mutable_stats.diversity_rejections,
            "incomplete_rejections": mutable_stats.incomplete_rejections,
            "possible_menu_combinations": comb(len(scored), recipe_count),
            "expansion_candidates_visited": (
                mutable_stats.expansion_candidates_visited
            ),
            "unique_economic_states": mutable_stats.optimistic_bound_evaluations,
            "duplicate_economic_state_hits": (
                mutable_stats.optimistic_bound_cache_hits
            ),
            "full_basket_evaluations": mutable_stats.cache_misses,
        }.items():
            if amount:
                increment_performance_counter(counter_name, amount)
        result = MenuOptimizationResult(
            recipes=list(winner.recipes),
            basket=winner_evaluation.basket,
            ingredients=list(winner_evaluation.ingredients),
            stats=stats,
            marginal_costs=marginal_costs,
            basket_audit=winner_evaluation.audit,
        )
        record_performance_seconds("menu_search", perf_counter() - started)
        return result


def optimize_menu(
    candidates: Sequence[Recipe],
    candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
    stores: Sequence[Store],
    *,
    recipe_count: int = 5,
    max_stores: int | None = 2,
    beam_width: int = 40,
    diversity_constraints: DiversityConstraints | None = None,
    candidate_limit: int | None = None,
    user_pricing_context: UserPricingContext | None = None,
) -> MenuOptimizationResult:
    """Functional convenience wrapper around :class:`MenuOptimizer`."""

    return MenuOptimizer().optimize(
        candidates,
        candidates_by_name,
        stores,
        recipe_count=recipe_count,
        max_stores=max_stores,
        beam_width=beam_width,
        diversity_constraints=diversity_constraints,
        candidate_limit=candidate_limit,
        user_pricing_context=user_pricing_context,
    )


__all__ = [
    "DiversityConstraints",
    "MenuOptimizationResult",
    "MenuOptimizer",
    "MenuSearchStats",
    "MenuVariantOptimizationResult",
    "RecipeMarginalCost",
    "admissible_checkout_lower_bound",
    "optimize_menu",
]
