from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.domain.promotion_pricing import MembershipProgram

from .basket import OptimizedBasket, StoreBasket
from .diversity import DiversityMode, DiversityPolicyOverrides
from .ingredient import NormalizedIngredient
from .personal import PersonalPlanning, PersonalResult
from .product import CheapIngredient
from .quality import (
    DiversityRepetitionSummary,
    PlanQualitySummary,
    StoreTradeoff,
    SurplusSummary,
)
from .recipe import Recipe
from .recipe_preferences import RecipePreferences


class DietPreference(StrEnum):
    """Consumer-facing dietary filter for price-aware candidate generation."""

    MIXED = "mixed"
    MEAT_ALLOWED = "meat_allowed"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"


class AvailabilityMode(StrEnum):
    """Requested physical-assortment caution for a reproducible plan.

    The current price universe does not claim live shelf inventory. Keeping
    this preference in the immutable request lets the separate evidence layer
    apply it without treating an online catalogue as physical stock.
    """

    NORMAL = "normal"
    STRICT = "strict"


class PlanRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    recipe_preferences: RecipePreferences | None = Field(default=None, exclude_if=lambda v: v is None)
    recipe_diversity_overrides: dict[str, int | float | None] | None = Field(default=None, exclude_if=lambda v: v is None)
    allow_nutrition_estimates: bool = Field(default=False, exclude_if=lambda v: not v)
    use_pantry: bool = Field(default=True, exclude_if=lambda v: v)
    purchase_planning_mode: Literal["exact", "estimated"] = "exact"
    allowed_store_ids: tuple[str, ...] = Field(
        default=(), max_length=40,
        description="Optional explicit price-context selection for this plan only. Empty preserves the existing area.",
        exclude_if=lambda value: not value,
    )
    postal_code: str = "22350"
    recipes: int = Field(default=5, ge=0, le=7)
    personal: PersonalPlanning | None = None
    servings: int = Field(default=4, ge=1, le=12)
    max_stores: int = Field(default=2, ge=1, le=4)
    use_member_prices: bool = False
    memberships: dict[
        Literal["ica", "coop", "willys", "hemkop", "citygross", "lidl"],
        bool,
    ] = Field(
        default_factory=dict,
        max_length=6,
        description=(
            "Per-chain memberships. When omitted, use_member_prices remains the "
            "backward-compatible all-chains switch."
        ),
    )
    membership_programs: tuple[MembershipProgram, ...] = Field(
        default_factory=tuple,
        max_length=6,
        description=(
            "Stable generic membership-program identities. The API also accepts this "
            "sequence in the legacy memberships field."
        ),
    )
    optimization_iterations: int = Field(default=1, ge=0, le=2)
    strategy: Literal["legacy", "optimized"] | None = None
    candidate_recipe_count: int = Field(default=80, ge=10, le=300)
    candidate_search_limit: int | None = Field(default=None, ge=5, le=300)
    beam_width: int = Field(default=30, ge=5, le=100)
    varied_budget_percent: float = Field(default=25, ge=0, le=100)
    diversity_mode: DiversityMode = DiversityMode.BALANCED
    diet_preference: DietPreference = DietPreference.MIXED
    availability_mode: AvailabilityMode = AvailabilityMode.NORMAL
    avoid_ingredients: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="Ingredients to avoid; this is not a medical allergy guarantee.",
    )
    max_same_primary_ingredient_meals: int = Field(default=2, ge=1, le=5)
    max_same_recipe_family: int = Field(default=2, ge=1, le=5)
    max_same_carbohydrate_meals: int = Field(default=3, ge=1, le=5)
    max_pairwise_recipe_similarity: float = Field(default=0.70, ge=0, le=1)
    max_same_cooking_method_meals: int | None = Field(default=None, ge=1, le=5)
    max_same_dish_form_meals: int | None = Field(default=None, ge=1, le=5)
    max_pairwise_culinary_similarity: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )
    min_kcal_per_serving: float = Field(default=450, ge=0, le=2000)
    max_kcal_per_serving: float = Field(default=900, ge=1, le=3000)
    min_protein_g_per_serving: float = Field(default=18, ge=0, le=200)
    min_vegetable_g_per_serving: float = Field(default=100, ge=0, le=1000)
    debug: bool = False

    @field_validator("allowed_store_ids")
    @classmethod
    def validate_allowed_stores(cls, values):
        if any(not v.strip() or v != v.strip() for v in values):
            raise ValueError("Butiks-ID får inte vara tomt eller ha omgivande blanksteg.")
        if len(set(values)) != len(values):
            raise ValueError("Butiks-ID måste vara unika.")
        return values

    @field_validator("recipe_diversity_overrides")
    @classmethod
    def validate_recipe_diversity_overrides(cls, values):
        if values is None:
            return None
        return DiversityPolicyOverrides.model_validate(values).model_dump(exclude_unset=True)

    @model_validator(mode="after")
    def explicit_store_selection_requires_personal(self):
        if self.allowed_store_ids and self.personal is None and not (self.recipe_preferences and self.recipe_preferences.mode == "complete"):
            raise ValueError("Uttryckligt butiksval stöds i personlig planering.")
        prefs = self.recipe_preferences
        if prefs and prefs.mode == "complete":
            dinner_count = (next((meal.count for meal in self.personal.meals if meal.meal_type == "dinner"), 0)
                            if self.personal else self.recipes)
            required = (prefs.min_distinct_cuisines if prefs.cuisine_distribution == "minimum"
                        else len(prefs.cuisines) if prefs.cuisine_distribution == "each_selected" else 0)
            if required > dinner_count:
                raise ValueError("Köksfördelning: fler obligatoriska matkök än middagar. Ändra antal middagar eller variationsvalet.")
        return self

    @model_validator(mode="before")
    @classmethod
    def normalize_membership_programs(cls, value: Any) -> Any:
        """Accept stable program IDs while preserving legacy chain flags.

        The normalized request intentionally stores both projections: stable program
        identities survive the API and saved-plan JSON, while older provider plumbing
        can consume the chain-boolean mapping until it is removed separately.
        """

        if not isinstance(value, dict):
            return value
        data = dict(value)
        membership_input_supplied = (
            "memberships" in data or "membership_programs" in data
        )
        raw_flags = data.get("memberships")
        raw_programs = data.get("membership_programs")
        if isinstance(raw_flags, (list, tuple, set, frozenset)):
            raw_programs = tuple(raw_flags) + tuple(raw_programs or ())
            raw_flags = {}
        if raw_flags is None:
            raw_flags = {}
        if not isinstance(raw_flags, dict):
            raise TypeError("memberships must be stable program IDs or chain flags")

        chain_flags: dict[str, bool] = {}
        enabled_programs: set[MembershipProgram] = set()
        for raw_name, enabled in raw_flags.items():
            program = MembershipProgram.from_value(str(raw_name))
            chain_flags[program.chain] = bool(enabled)
            if enabled:
                enabled_programs.add(program)
        for raw_program in raw_programs or ():
            program = MembershipProgram.from_value(raw_program)
            enabled_programs.add(program)
            chain_flags[program.chain] = True

        if membership_input_supplied:
            data["memberships"] = chain_flags
            data["membership_programs"] = tuple(
                sorted(enabled_programs, key=lambda program: program.value)
            )
        if enabled_programs:
            data["use_member_prices"] = True
        return data

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal_code(cls, value: object) -> str:
        digits = "".join(character for character in str(value) if character.isdigit())
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        return digits

    @field_validator("avoid_ingredients", mode="before")
    @classmethod
    def normalize_avoid_ingredients(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str) or not isinstance(value, (list, tuple, set)):
            raise TypeError("avoid_ingredients must be a sequence")
        normalized = [" ".join(str(item).casefold().split()) for item in value]
        return list(dict.fromkeys(item for item in normalized if item))

    @model_validator(mode="after")
    def validate_quality_range(self) -> PlanRequest:
        if self.max_kcal_per_serving <= self.min_kcal_per_serving:
            raise ValueError(
                "max_kcal_per_serving must be greater than min_kcal_per_serving"
            )
        return self


class OptimizationScenario(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    max_stores: int | None = Field(default=None, ge=1)
    basket: OptimizedBasket | None = None
    error: str | None = None


class PlanOptimizationSummary(BaseModel):
    """Backward-compatible metadata for the optional menu-search strategy."""

    model_config = ConfigDict(frozen=True)

    strategy: Literal["legacy", "optimized"]
    economic_ingredients: int = Field(default=0, ge=0)
    candidate_recipes_generated: int = Field(default=0, ge=0)
    candidate_recipes_valid: int = Field(default=0, ge=0)
    candidate_recipes_analyzed: int = Field(default=0, ge=0)
    candidate_recipes_search_pool: int = Field(default=0, ge=0)
    legacy_candidates_added: int = Field(default=0, ge=0)
    candidate_recipes_rejected: int = Field(default=0, ge=0)
    candidate_recipes_structurally_valid: int = Field(default=0, ge=0)
    candidate_recipes_nutrition_rejected: int = Field(default=0, ge=0)
    candidate_batches: dict[str, int] = Field(default_factory=dict)
    beam_width: int | None = Field(default=None, ge=1)
    max_stores: int | None = Field(default=None, ge=1)
    states_evaluated: int = Field(default=0, ge=0)
    basket_cache_hits: int = Field(default=0, ge=0)
    basket_cache_misses: int = Field(default=0, ge=0)
    basket_calculations: int = Field(default=0, ge=0)
    basket_cache_hit_rate: float = Field(default=0, ge=0, le=1)
    estimated_savings_vs_legacy: float | None = Field(default=None, ge=0)
    max_pairwise_recipe_similarity: float | None = Field(default=None, ge=0, le=1)
    timings_seconds: dict[str, float] = Field(default_factory=dict)
    timings_ms: dict[str, float] = Field(default_factory=dict)
    span_statistics: dict[str, dict[str, int | float]] = Field(default_factory=dict)
    operation_counters: dict[str, int] = Field(default_factory=dict)
    search_depth_counters: dict[str, dict[str, int]] = Field(default_factory=dict)
    diversity_mode: DiversityMode | None = None
    diversity_score: float | None = Field(default=None, ge=0, le=1)
    diversity_plan_states: dict[str, int] = Field(default_factory=dict)


class RecipeCostSummary(BaseModel):
    """Deterministic incremental basket cost for one selected recipe.

    Package leftovers can be shared by later recipes, so this is deliberately
    labelled incremental rather than pretending to allocate every package
    uniquely between meals.
    """

    model_config = ConfigDict(frozen=True)

    recipe_name: str = Field(min_length=1)
    incremental_ingredient_cost: float | None = None
    allocated_basket_cost: float = Field(ge=0)
    cost_per_portion: float = Field(ge=0)


class DiversityPlanOption(BaseModel):
    """One price-versus-variety alternative from the shared product snapshot."""

    model_config = ConfigDict(frozen=True)

    variation_policy_version: str = "legacy"  # Missing on historical saved plans.
    variation_target_met: bool = True
    variation_limitations: list[str] = Field(default_factory=list)
    varied_budget_percent: float = 25
    balanced_reference_total: float | None = None
    premium_vs_balanced: float | None = None
    budget_ceiling: float | None = None
    inter_plan_distance: dict[str, Any] | None = None
    mode: DiversityMode
    recipes: list[Recipe]
    ingredients: list[NormalizedIngredient]
    optimized_basket: OptimizedBasket
    recipe_costs: list[RecipeCostSummary] = Field(default_factory=list)
    portions: int = Field(gt=0)
    price_per_portion: float = Field(ge=0)
    diversity_score: float = Field(ge=0, le=1)
    average_pairwise_similarity: float = Field(ge=0, le=1)
    max_pairwise_similarity: float = Field(ge=0, le=1)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)
    premium_vs_cheapest: float = Field(default=0, ge=0)
    premium_per_portion: float = Field(default=0, ge=0)
    repetition: DiversityRepetitionSummary
    quality: PlanQualitySummary
    surplus: SurplusSummary
    states_evaluated: int = Field(default=0, ge=0)
    basket_calculations: int = Field(default=0, ge=0)


class LegacyPlanComparison(BaseModel):
    """Recipe-first baseline costed on the exact same product snapshot."""

    model_config = ConfigDict(frozen=True)

    total: float = Field(ge=0)
    price_per_portion: float = Field(ge=0)
    recipes: list[str] = Field(default_factory=list)
    basket: OptimizedBasket
    savings: float = Field(default=0, ge=0)


class PriceContextCoverage(BaseModel):
    """Consumer-safe scope and lineage for one price context.

    Context identifiers and snapshot IDs preserve reproducibility.  The UI uses
    only the explicit display/scope labels and never needs crawler policy,
    endpoint or environment details.
    """

    model_config = ConfigDict(frozen=True)

    context_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    chain: str = Field(min_length=1)
    price_context_type: str | None = Field(default=None, min_length=1)
    price_semantics: Literal["online_price"] | None = None
    price_scope_label: str = Field(min_length=1)
    snapshot_ids: tuple[str, ...] = ()
    status: Literal["compared", "excluded_stale"]


class PlanPriceData(BaseModel):
    """Freshness and identity of the immutable prices used for one result."""

    model_config = ConfigDict(frozen=True)

    price_universe_id: str = Field(min_length=1)
    built_at: datetime
    pricing_timestamp: datetime | None = None
    snapshot_ids: tuple[str, ...] = ()
    product_count: int = Field(default=0, ge=0)
    canonical_index_count: int = Field(default=0, ge=0)
    oldest_price_age_hours: float = Field(default=0, ge=0)
    status: Literal["fresh", "aging", "degraded", "stale", "broken"]
    oldest_usable_price_age_hours: float | None = Field(default=None, ge=0)
    usable_context_count: int = Field(default=0, ge=0)
    excluded_stale_context_count: int = Field(default=0, ge=0)
    excluded_stale_context_ids: tuple[str, ...] = ()
    compared_price_contexts: tuple[PriceContextCoverage, ...] = ()
    excluded_price_contexts: tuple[PriceContextCoverage, ...] = ()
    cache_state: Literal["cold", "warm"] | None = None
    live_chain_requests: int = Field(default=0, ge=0)


class MembershipCoverage(BaseModel):
    """Request-local availability of verified generic member contracts."""

    model_config = ConfigDict(frozen=True)

    membership_program: MembershipProgram
    active_contracts: int = Field(default=0, ge=0)
    contexts: tuple[str, ...] = ()
    status: Literal["available", "no_verified_contracts"]
    message: str = Field(min_length=1)


class MembershipSavings(BaseModel):
    """Savings against the same exact products and quantities at public prices."""

    model_config = ConfigDict(frozen=True)

    basket_total_with_memberships: float = Field(ge=0)
    same_basket_public_total: float = Field(ge=0)
    amount: float = Field(ge=0)
    member_price_lines: int = Field(default=0, ge=0)


class PlanResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    personal: PersonalResult | None = None

    app_version: str = Field(default="0.1.0", min_length=1, max_length=64)
    build_id: str = Field(default="local", min_length=1, max_length=128)
    location: str
    postal_code: str | None = None
    strategy: Literal["legacy", "optimized"] = "legacy"
    diversity_mode: DiversityMode = DiversityMode.BALANCED
    membership_programs_used: tuple[MembershipProgram, ...] = ()
    membership_coverage: tuple[MembershipCoverage, ...] = ()
    membership_savings: MembershipSavings | None = None
    recipes: list[Recipe]
    recipe_costs: list[RecipeCostSummary] = Field(default_factory=list)
    ingredients: list[NormalizedIngredient]
    cheap_ingredients: list[CheapIngredient] = Field(default_factory=list)
    single_store_options: list[StoreBasket]
    optimized_basket: OptimizedBasket
    optimization_scenarios: list[OptimizationScenario] = Field(default_factory=list)
    portions: int = Field(ge=0)
    price_per_portion: float = Field(ge=0)
    data_source: str
    data: PlanPriceData | None = None
    source_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    recipe_source: str
    warnings: list[str] = Field(default_factory=list)
    attribution_text: str | None = None
    attribution_url: str | None = None
    optimization_iterations_attempted: int = Field(default=0, ge=0)
    optimization_iterations_accepted: int = Field(default=0, ge=0)
    optimization: PlanOptimizationSummary | None = None
    legacy_comparison: LegacyPlanComparison | None = None
    quality: PlanQualitySummary | None = None
    surplus: SurplusSummary | None = None
    store_tradeoff: StoreTradeoff | None = None
    plans: dict[DiversityMode, DiversityPlanOption] = Field(default_factory=dict)
    diversity_plan_errors: dict[DiversityMode, str] = Field(default_factory=dict)
    debug_info: dict[str, Any] | None = None
