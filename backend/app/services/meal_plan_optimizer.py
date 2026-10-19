"""End-to-end price-first meal planning orchestration."""

from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

from app.config import Settings
from app.errors import IncompleteBasketError, PriceProviderError
from app.models import (
    BasketVerificationStatus,
    CheapIngredient,
    DiversityMode,
    DiversityPlanOption,
    DiversityPolicy,
    DiversityQualitySummary,
    DiversityRepetitionSummary,
    LegacyPlanComparison,
    NormalizedIngredient,
    NutritionQualitySummary,
    OptimizationScenario,
    OptimizedBasket,
    PlanOptimizationSummary,
    PlanPriceData,
    PlanQualitySummary,
    PlanRequest,
    PlanResponse,
    PriceContextCoverage,
    ProductCandidate,
    QualityStatus,
    Recipe,
    RecipeCostSummary,
    RecipeNutritionQuality,
    RecipeSimilarityPairQuality,
    Store,
    StoreBasket,
    StoreTradeoff,
    SurplusSummary,
)
from app.providers.base import GroceryPriceProvider
from app.providers.factory import create_price_provider
from app.providers.federated import SourceResolutionDiagnostics
from app.providers.mock import MockPriceProvider
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import money
from app.services.basket_optimizer import BasketOptimizer, BasketVerificationPolicy
from app.services.cheap_products import CheapProductsService
from app.services.culinary_similarity import CulinaryMenuReport, CulinarySimilarity
from app.services.diet_policy import filter_economic_pool, recipe_respects_diet
from app.services.diversity_policy import create_diversity_policy
from app.services.economic_ingredient_selector import (
    EconomicIngredientPool,
    EconomicIngredientSelector,
)
from app.services.ingredient_normalizer import IngredientNormalizer
from app.services.inter_plan_distance import (
    INTER_PLAN_POLICY_VERSION,
    compare_plans,
    reference_identity,
    search_conditioned_varied,
)
from app.services.membership_reporting import (
    fixed_basket_membership_savings,
    membership_coverage,
)
from app.services.menu_optimizer import (
    DiversityConstraints,
    LazyPairwiseSimilarities,
    MenuOptimizationResult,
    MenuOptimizer,
)
from app.services.nutrition_validator import (
    MealQualityConstraints,
    NutritionValidator,
    RecipeQualityValidationReport,
)
from app.services.performance_trace import (
    current_performance_trace,
    increment_performance_counter,
    performance_span,
    record_performance_seconds,
    traced_plan_call,
)
from app.services.price_universe_runtime import (
    PACKAGE_CALCULATOR_VERSION,
    LocalPriceUniverseProvider,
    PreparedPriceUniverse,
    PreparedPriceUniverseManager,
    menu_search_cache_key,
    normalized_memberships,
)
from app.services.product_matcher import ProductMatcher
from app.services.recipe_candidate_generator import (
    DeterministicRecipeCandidateGenerator,
    OpenAIRecipeCandidateGenerator,
    RecipeCandidateGenerator,
    create_recipe_candidate_generator,
)
from app.services.recipe_candidate_validator import (
    RecipeCandidateValidator,
    carbohydrate_ingredient,
    primary_ingredient,
    recipe_family,
    recipe_id,
)
from app.services.recipe_generator import (
    MockRecipeGenerator,
    OpenAIRecipeGenerator,
    RecipeGenerator,
)
from app.services.recipe_similarity import (
    RecipeSimilarityAnalyzer,
    RecipeSimilarityConstraints,
)
from app.services.stable_candidate_pool import StableCandidatePoolBuilder
from app.services.user_pricing import (
    current_pricing_date,
    eligible_member_contract_fingerprints,
    prepare_economic_pool_for_pricing,
    price_candidate_for_context,
    project_economic_pool,
)

from grocery_data.app.domain.promotion_pricing import (
    UserPricingContext,
)

# Primat's lexical search uses different catalogue wording across chains. Keep
# the small set of intentional substitutes here, next to orchestration, rather
# than teaching the price provider grocery semantics.
_PRODUCT_SEARCH_VARIANTS: dict[str, tuple[str, ...]] = {
    "frysta grönsaker": ("wokgrönsaker",),
}

# These fields pre-date named diversity modes and are commonly serialized by
# generated clients even when the caller did not intend to customize anything.
# Treating those schema defaults as explicit overrides would silently turn
# CHEAPEST into a constrained mode and weaken BALANCED/VARIED.
_LEGACY_DIVERSITY_DEFAULTS: dict[str, int | float] = {
    "max_same_primary_ingredient_meals": 2,
    "max_same_recipe_family": 2,
    "max_same_carbohydrate_meals": 3,
    "max_pairwise_recipe_similarity": 0.70,
}

_BASKET_VERIFICATION_RANK: dict[BasketVerificationStatus, int] = {
    BasketVerificationStatus.VERIFIED: 0,
    BasketVerificationStatus.VERIFIED_WITH_ESTIMATES: 1,
    BasketVerificationStatus.UNVERIFIED: 2,
    BasketVerificationStatus.INVALID: 3,
}


def _consumer_price_context_coverage(
    prepared: PreparedPriceUniverse,
    *,
    usable_context_ids: Iterable[str],
    excluded_stale_context_ids: Iterable[str],
) -> tuple[tuple[PriceContextCoverage, ...], tuple[PriceContextCoverage, ...]]:
    """Project immutable context lineage into a safe consumer contract."""

    usable = frozenset(usable_context_ids)
    excluded = frozenset(excluded_stale_context_ids)
    snapshot_ids: dict[str, set[str]] = {
        store.store_id: set() for store in prepared.stores
    }
    for store in prepared.stores:
        provenance = store.source_provenance
        if provenance is not None:
            snapshot_ids[store.store_id].add(provenance.source_snapshot_id)
    for product in prepared.universe.products:
        provenance = product.source_provenance
        if provenance is not None and product.store_id in snapshot_ids:
            snapshot_ids[product.store_id].add(provenance.source_snapshot_id)

    def scope_label(store: Store) -> str:
        if store.price_label:
            return store.price_label
        context_type = str(store.price_context_type or "").casefold()
        if store.price_semantics == "online_price" or "online" in context_type:
            return "onlinepris"
        if "physical" in context_type:
            return "butikskopplad prisdata"
        return "digital priskontext"

    rows = {
        store.store_id: PriceContextCoverage(
            context_id=store.store_id,
            display_name=store.name,
            chain=store.chain,
            price_context_type=store.price_context_type,
            price_semantics=store.price_semantics,
            price_scope_label=scope_label(store),
            snapshot_ids=tuple(sorted(snapshot_ids[store.store_id])),
            status=(
                "compared" if store.store_id in usable else "excluded_stale"
            ),
        )
        for store in prepared.stores
        if store.store_id in usable or store.store_id in excluded
    }
    compared = tuple(
        sorted(
            (rows[context_id] for context_id in usable if context_id in rows),
            key=lambda row: (row.display_name.casefold(), row.context_id),
        )
    )
    unavailable = tuple(
        sorted(
            (rows[context_id] for context_id in excluded if context_id in rows),
            key=lambda row: (row.display_name.casefold(), row.context_id),
        )
    )
    return compared, unavailable


def _basket_selection_key(basket: OptimizedBasket | StoreBasket) -> tuple[int, Decimal]:
    """Prefer trustworthy totals before comparing price."""

    return (
        _BASKET_VERIFICATION_RANK[basket.verification_status],
        money(basket.total),
    )


def _strict_price_improvement(
    candidate: OptimizedBasket,
    current: OptimizedBasket,
) -> bool:
    """Apply the same trust-before-price ordering to challenger plans."""

    return _basket_selection_key(candidate) < _basket_selection_key(current)


@dataclass(slots=True)
class _EvaluatedPlan:
    recipes: list[Recipe]
    ingredients: list[NormalizedIngredient]
    candidates_by_name: dict[str, list[ProductCandidate]]
    single_store_options: list[StoreBasket]
    optimized_basket: OptimizedBasket


class MealPlanService:
    """Coordinates semantic work while all price decisions stay deterministic."""

    def __init__(
        self,
        settings: Settings,
        *,
        cheap_products: CheapProductsService | None = None,
        normalizer: IngredientNormalizer | None = None,
        matcher: ProductMatcher | None = None,
        basket_optimizer: BasketOptimizer | None = None,
        economic_selector: EconomicIngredientSelector | None = None,
        candidate_generator: RecipeCandidateGenerator | None = None,
        candidate_validator: RecipeCandidateValidator | None = None,
        menu_optimizer: MenuOptimizer | None = None,
        nutrition_validator: NutritionValidator | None = None,
        similarity_analyzer: RecipeSimilarityAnalyzer | None = None,
        culinary_similarity: CulinarySimilarity | None = None,
        basket_auditor: BasketAuditor | None = None,
        price_universe_manager: PreparedPriceUniverseManager | None = None,
    ) -> None:
        self.settings = settings
        self.cheap_products = cheap_products or CheapProductsService()
        self.normalizer = normalizer or IngredientNormalizer()
        self.matcher = matcher or ProductMatcher(
            allow_medium_semantic=settings.allow_medium_semantic_matches
        )
        verification_policy = BasketVerificationPolicy(
            allow_medium_semantic=settings.allow_medium_semantic_matches,
            allow_estimated_quantities=settings.allow_estimated_quantities,
            allow_unknown_quantities=settings.allow_unknown_quantities,
            allow_unknown_sale_model=settings.allow_unknown_sale_model,
        )
        self.basket_optimizer = basket_optimizer or BasketOptimizer(
            verification_policy=verification_policy,
            memoize_store_subsets=settings.stable_candidate_search_enabled,
        )
        self.basket_auditor = basket_auditor or BasketAuditor()
        self.economic_selector = economic_selector or EconomicIngredientSelector(
            matcher=self.matcher,
            verification_policy=verification_policy,
        )
        self.candidate_generator = candidate_generator
        self.candidate_validator = candidate_validator or RecipeCandidateValidator()
        self.nutrition_validator = nutrition_validator
        self.similarity_analyzer = similarity_analyzer
        self.culinary_similarity = culinary_similarity or CulinarySimilarity()
        self.menu_optimizer = menu_optimizer or MenuOptimizer(
            normalizer=self.normalizer,
            basket_optimizer=self.basket_optimizer,
            basket_auditor=self.basket_auditor,
        )
        self.price_universe_manager = price_universe_manager

    @staticmethod
    def _full_basket_stores(stores: Sequence[Store]) -> list[Store]:
        """Reject offer feeds before any basket/product search begins."""

        eligible = [
            store
            for store in stores
            if (store.tier or "").casefold() != "offers_only"
            and (
                store.source_provenance is None
                or store.source_provenance.source_channel.casefold() != "offers"
            )
        ]
        if not eligible:
            raise IncompleteBasketError(
                "Prisprovidern returnerade endast offer-only-butiker utan verifierad katalog."
            )
        return eligible

    @staticmethod
    def _source_diagnostics(provider: GroceryPriceProvider) -> list[dict[str, Any]]:
        rows = getattr(provider, "diagnostics", ())
        return MealPlanService._safe_source_diagnostics(
            row.model_dump(mode="json")
            for row in rows
            if isinstance(row, SourceResolutionDiagnostics)
        )

    @staticmethod
    def _safe_source_diagnostics(
        rows: Iterable[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Project provider diagnostics onto a closed, credential-free schema.

        Provider exception text and free-form reasons are intentionally not
        copied, even in debug mode.  Debug clients need source decisions and
        counters, not transport URLs, headers, cookies or exception payloads.
        """

        safe_rows: list[dict[str, Any]] = []
        scalar_fields = (
            "chain",
            "context_id",
            "requested_provider",
            "selected_provider",
            "selected_channel",
            "selected_role",
            "selected_snapshot_id",
            "fallback_available",
            "fallback_used",
            "basket_eligible",
            "considered_stores",
            "accepted_stores",
            "rejected_stores",
            "stale_stores",
            "products_returned",
            "rows_rejected",
            "stale_rows",
        )
        for raw in rows:
            if not isinstance(raw, Mapping):
                continue
            safe: dict[str, Any] = {}
            for field in scalar_fields:
                if field not in raw:
                    continue
                value = raw.get(field)
                if isinstance(value, str) and (
                    len(value) > 160
                    or not all(character.isalnum() or character in "._:-" for character in value)
                ):
                    value = None
                safe[field] = value
            products = raw.get("products_considered")
            if isinstance(products, Mapping):
                safe["products_considered"] = {
                    key: value
                    for key, value in products.items()
                    if isinstance(key, str)
                    and key in {"own", "primat", "price-universe", "mock"}
                    and isinstance(value, int)
                    and value >= 0
                }
            errors = raw.get("provider_errors")
            safe["provider_error_count"] = (
                len(errors)
                if isinstance(errors, (list, tuple))
                else int(raw.get("provider_error_count") or 0)
            )
            if safe.get("basket_eligible"):
                resolution = "fallback_selected" if safe.get("fallback_used") else "selected"
            elif safe.get("fallback_available"):
                resolution = "fallback_not_selected"
            else:
                resolution = "no_eligible_source"
            safe["resolution_status"] = resolution
            safe_rows.append(safe)
        return safe_rows

    @staticmethod
    def _record_price_provider_fetch_timing(
        timings: dict[str, float],
        provider: GroceryPriceProvider,
        seconds: float,
    ) -> None:
        """Record neutral fetch timing and a narrow legacy Primat alias.

        ``primat_fetch`` predates the federated/OWN provider layer. Preserve it
        only for a real Primat-only provider so existing Primat clients remain
        compatible without mislabelling OWN or federated snapshot reads.
        """

        timings["price_provider_fetch"] = seconds
        if str(getattr(provider, "source_name", "")).casefold() == "primat":
            timings["primat_fetch"] = seconds

    def _nutrition_for(self, request: PlanRequest) -> NutritionValidator:
        if self.nutrition_validator is not None:
            return self.nutrition_validator
        return NutritionValidator(
            MealQualityConstraints(
                min_kcal_per_portion=request.min_kcal_per_serving,
                max_kcal_per_portion=request.max_kcal_per_serving,
                min_protein_g_per_portion=request.min_protein_g_per_serving,
                min_vegetable_g_per_portion=request.min_vegetable_g_per_serving,
            )
        )

    def _similarity_for(self, request: PlanRequest) -> RecipeSimilarityAnalyzer:
        if self.similarity_analyzer is not None:
            return self.similarity_analyzer
        return RecipeSimilarityAnalyzer(
            RecipeSimilarityConstraints(
                near_duplicate_threshold=request.max_pairwise_recipe_similarity
            ),
            normalizer=self.normalizer,
        )

    @staticmethod
    def _nutrition_valid_recipes(
        recipes: Sequence[Recipe],
        report: RecipeQualityValidationReport,
    ) -> list[Recipe]:
        return [
            recipe
            for recipe, result in zip(recipes, report.results, strict=True)
            if result.is_valid
        ]

    @staticmethod
    def _pairwise_similarity_scores(
        recipes: Sequence[Recipe],
        analyzer: RecipeSimilarityAnalyzer,
    ) -> dict[tuple[str, str], float]:
        profiles = [
            (recipe.name.casefold().strip(), analyzer.build_profile(recipe)) for recipe in recipes
        ]
        scores: dict[tuple[str, str], float] = {}
        for left_index, (left_name, left_profile) in enumerate(profiles):
            for right_name, right_profile in profiles[left_index + 1 :]:
                key = tuple(sorted((left_name, right_name)))
                scores[key] = analyzer.compare_profiles(left_profile, right_profile).score
        return scores

    @staticmethod
    def _diversity_policy_for(
        request: PlanRequest,
        mode: DiversityMode,
    ) -> DiversityPolicy:
        """Resolve one stable named preset plus selected-mode customizations.

        Legacy clients often send every old schema default. Those values are
        not user intent and must not globally rewrite all three named plans.
        A non-default legacy value remains backward compatible by customizing
        only the requested mode, matching the old single-plan semantics.
        New explicit culinary overrides follow that same selected-mode rule.
        """

        def adapt(policy: DiversityPolicy) -> DiversityPolicy:
            if mode == DiversityMode.CHEAPEST:
                return policy
            count = request.recipes
            updates = {"target_recipe_count": count}
            if count > 5:
                updates.update(max_same_primary_ingredient_meals=3,
                               max_same_carbohydrate_meals=3,
                               max_same_cooking_method_meals=3)
            if mode == DiversityMode.VARIED:
                updates.update(min_recipe_families=min(count, (count + 3) // 2),
                               min_cooking_methods=2 if count <= 3 else 3)
            return policy.model_copy(update=updates)

        if mode != request.diversity_mode:
            return adapt(create_diversity_policy(mode))
        fields_set = request.model_fields_set
        overrides: dict[str, int | float | None] = {}
        legacy_request_to_policy = {
            "max_same_recipe_family": "max_same_recipe_family",
            "max_same_primary_ingredient_meals": ("max_same_primary_ingredient_meals"),
            "max_same_carbohydrate_meals": "max_same_carbohydrate_meals",
        }
        for request_field, policy_field in legacy_request_to_policy.items():
            value = getattr(request, request_field)
            if request_field in fields_set and value != _LEGACY_DIVERSITY_DEFAULTS[request_field]:
                overrides[policy_field] = value

        request_to_policy = {
            "max_same_cooking_method_meals": "max_same_cooking_method_meals",
            "max_same_dish_form_meals": "max_same_dish_form_meals",
            "max_pairwise_culinary_similarity": ("max_pairwise_culinary_similarity"),
        }
        for request_field, policy_field in request_to_policy.items():
            if request_field in fields_set:
                overrides[policy_field] = getattr(request, request_field)
        # Backward-compatible advanced clients may still send the old name.
        if (
            "max_pairwise_recipe_similarity" in fields_set
            and "max_pairwise_culinary_similarity" not in fields_set
            and request.max_pairwise_recipe_similarity
            != _LEGACY_DIVERSITY_DEFAULTS["max_pairwise_recipe_similarity"]
        ):
            overrides["max_pairwise_culinary_similarity"] = request.max_pairwise_recipe_similarity
        return adapt(create_diversity_policy(mode, overrides))

    @staticmethod
    def _menu_search_cache_payload(
        request: PlanRequest,
        policies: Mapping[DiversityMode, DiversityPolicy],
        candidate_limit: int | None,
        *,
        pricing_context_id: str,
        stable_candidate_search_enabled: bool = False,
        retained_stable_recipe_ids: frozenset[str] = frozenset(),
    ) -> dict[str, Any]:
        """Serialize only inputs that can change the shared variant search.

        The initial search computes CHEAPEST and BALANCED; a separately keyed
        search conditions VARIED on the final BALANCED reference. Merely
        selecting the API projection must not redo either search. Resolved
        policies do remain in the key, so a real selected-mode override is
        isolated deterministically.
        """

        payload = {
            "variation_policy_version": "structural-menu-v2",
            "inter_plan_policy_version": INTER_PLAN_POLICY_VERSION,
            "varied_budget_percent": request.varied_budget_percent,
            "recipe_count": request.recipes,
            "max_stores": request.max_stores,
            "beam_width": request.beam_width,
            "candidate_limit": candidate_limit,
            "diet_preference": request.diet_preference.value,
            "avoid_ingredients": tuple(sorted(request.avoid_ingredients)),
            "pricing_context_id": pricing_context_id,
            "policies": {
                mode.value: policies[mode].model_dump(mode="json")
                for mode in sorted(policies, key=lambda item: item.value)
            },
        }
        if stable_candidate_search_enabled:
            payload["stable_candidate_search_enabled"] = True
            payload["retained_stable_recipe_ids"] = sorted(retained_stable_recipe_ids)
        return payload

    def _culinary_profiles(
        self,
        recipes: Sequence[Recipe],
    ) -> dict[str, Any]:
        return {
            recipe.name.casefold().strip(): self.culinary_similarity.build_profile(recipe)
            for recipe in recipes
        }

    def _culinary_constraints(
        self,
        recipes: Sequence[Recipe],
        policy: DiversityPolicy,
    ) -> DiversityConstraints:
        profiles = self._culinary_profiles(recipes)
        # Pairs are scored when the search first checks them together; the
        # values are those of the former eager all-pairs loop.
        pairwise = LazyPairwiseSimilarities(
            profiles,
            lambda left, right: self.culinary_similarity.compare_profiles(left, right).score,
        )
        by_display_name = {
            recipe.name: profiles[recipe.name.casefold().strip()] for recipe in recipes
        }
        return DiversityConstraints(
            min_recipe_families=policy.min_recipe_families,
            min_cooking_methods=policy.min_cooking_methods,
            target_recipe_count=policy.target_recipe_count,
            max_same_primary_ingredient_meals=(policy.max_same_primary_ingredient_meals),
            max_same_recipe_family=policy.max_same_recipe_family,
            max_same_carbohydrate_meals=policy.max_same_carbohydrate_meals,
            recipe_families={
                name: profile.recipe_family for name, profile in by_display_name.items()
            },
            primary_ingredients={
                name: profile.primary_protein
                for name, profile in by_display_name.items()
                if profile.primary_protein
            },
            carbohydrates={
                name: profile.primary_carb
                for name, profile in by_display_name.items()
                if profile.primary_carb
            },
            max_same_cooking_method=policy.max_same_cooking_method_meals,
            max_same_dish_form=policy.max_same_dish_form_meals,
            cooking_methods={
                name: profile.cooking_method for name, profile in by_display_name.items()
            },
            dish_forms={name: profile.dish_form for name, profile in by_display_name.items()},
            max_pairwise_recipe_similarity=(policy.max_pairwise_culinary_similarity),
            pairwise_recipe_similarities=pairwise,
        )

    def _culinary_report(self, recipes: Sequence[Recipe]) -> CulinaryMenuReport:
        return self.culinary_similarity.analyze_menu(recipes)

    @staticmethod
    def _culinary_policy_passes(
        report: CulinaryMenuReport,
        policy: DiversityPolicy,
    ) -> bool:
        if len({p.recipe_family for p in report.profiles}) < policy.min_recipe_families:
            return False
        if len({p.cooking_method for p in report.profiles}) < policy.min_cooking_methods:
            return False
        checks: tuple[tuple[int | None, list[str | None]], ...] = (
            (
                policy.max_same_recipe_family,
                [profile.recipe_family for profile in report.profiles],
            ),
            (
                policy.max_same_primary_ingredient_meals,
                [profile.primary_protein for profile in report.profiles],
            ),
            (
                policy.max_same_carbohydrate_meals,
                [profile.primary_carb for profile in report.profiles],
            ),
            (
                policy.max_same_cooking_method_meals,
                [profile.cooking_method for profile in report.profiles],
            ),
            (
                policy.max_same_dish_form_meals,
                [profile.dish_form for profile in report.profiles],
            ),
        )
        for limit, values in checks:
            counts = Counter(value for value in values if value)
            if limit is not None and counts and max(counts.values()) > limit:
                return False
        threshold = policy.max_pairwise_culinary_similarity
        return threshold is None or all(pair.score < threshold for pair in report.pairs)

    @staticmethod
    def _repetition_summary(report: CulinaryMenuReport) -> DiversityRepetitionSummary:
        def counts(values: Sequence[str | None]) -> dict[str, int]:
            return dict(sorted(Counter(value for value in values if value).items()))

        return DiversityRepetitionSummary(
            recipe_families=counts([profile.recipe_family for profile in report.profiles]),
            primary_proteins=counts([profile.primary_protein for profile in report.profiles]),
            primary_carbs=counts([profile.primary_carb for profile in report.profiles]),
            dish_forms=counts([profile.dish_form for profile in report.profiles]),
            cooking_methods=counts([profile.cooking_method for profile in report.profiles]),
        )

    @staticmethod
    def _nutrition_summary(
        report: RecipeQualityValidationReport,
    ) -> NutritionQualitySummary:
        recipes = [
            RecipeNutritionQuality(
                recipe_name=result.recipe_name,
                status=QualityStatus.PASS if result.is_valid else QualityStatus.FAIL,
                is_estimate=result.estimate.is_estimate,
                kcal_per_serving=result.estimate.kcal_per_portion,
                protein_g_per_serving=result.estimate.protein_g_per_portion,
                vegetable_g_per_serving=result.estimate.vegetable_g_per_portion,
                confidence=result.estimate.confidence,
                confidence_score=result.estimate.confidence_score,
                violations=list(result.violations),
                unestimated_ingredients=list(result.estimate.unestimated_ingredients),
                piece_weight_assumptions=list(result.estimate.piece_weight_assumptions),
            )
            for result in report.results
        ]
        kcal = [recipe.kcal_per_serving for recipe in recipes]
        protein = [recipe.protein_g_per_serving for recipe in recipes]
        vegetables = [recipe.vegetable_g_per_serving for recipe in recipes]
        return NutritionQualitySummary(
            status=QualityStatus.PASS if report.is_valid else QualityStatus.FAIL,
            recipes=recipes,
            average_kcal_per_serving=round(sum(kcal) / len(kcal), 1) if kcal else 0,
            min_kcal_per_serving=min(kcal, default=0),
            max_kcal_per_serving=max(kcal, default=0),
            average_protein_g_per_serving=(round(sum(protein) / len(protein), 1) if protein else 0),
            min_protein_g_per_serving=min(protein, default=0),
            max_protein_g_per_serving=max(protein, default=0),
            average_vegetable_g_per_serving=(
                round(sum(vegetables) / len(vegetables), 1) if vegetables else 0
            ),
        )

    @classmethod
    def _diversity_summary(
        cls,
        report: CulinaryMenuReport,
        policy: DiversityPolicy,
    ) -> DiversityQualitySummary:
        passed = cls._culinary_policy_passes(report, policy)
        return DiversityQualitySummary(
            status=QualityStatus.PASS if passed else QualityStatus.FAIL,
            mode=policy.mode,
            threshold=policy.max_pairwise_culinary_similarity,
            max_pairwise_similarity=report.max_similarity,
            average_pairwise_similarity=report.average_similarity,
            diversity_score=report.diversity_score,
            repetition=cls._repetition_summary(report),
            pairs=[
                RecipeSimilarityPairQuality(
                    left_recipe=pair.left_recipe,
                    right_recipe=pair.right_recipe,
                    score=pair.score,
                    shared_ingredients=list(pair.shared_major_ingredients),
                    is_near_duplicate=(
                        policy.max_pairwise_culinary_similarity is not None
                        and pair.score >= policy.max_pairwise_culinary_similarity
                    ),
                    # Legacy recipes have no authored flavor score. Keep that
                    # component absent rather than inventing a numeric zero.
                    components={key: value for key, value in asdict(pair.components).items() if value is not None},
                )
                for pair in report.pairs
            ],
        )

    @staticmethod
    def _surplus_summary(audit: Any) -> SurplusSummary:
        return SurplusSummary(
            items=[item for item in audit.items if item.surplus_quantity > 0],
            unit_totals=audit.unit_totals,
            estimated_surplus_value=audit.estimated_surplus_value_total,
        )

    def _diversity_plan_option(
        self,
        *,
        mode: DiversityMode,
        plan: _EvaluatedPlan,
        search_result: MenuOptimizationResult,
        nutrition_validator: NutritionValidator,
        policy: DiversityPolicy,
        cheapest_total: float,
        servings: int,
        user_pricing_context: UserPricingContext,
    ) -> DiversityPlanOption:
        audit = self.basket_auditor.audit(
            plan.ingredients,
            plan.optimized_basket,
            user_pricing_context=user_pricing_context,
        )
        nutrition = nutrition_validator.validate_recipes(plan.recipes)
        culinary = self._culinary_report(plan.recipes)
        if not audit.passed or not nutrition.is_valid:
            raise IncompleteBasketError(
                f"Planalternativet {mode.value} klarade inte basket/nutrition-audit."
            )
        if not self._culinary_policy_passes(culinary, policy):
            raise IncompleteBasketError(
                f"Planalternativet {mode.value} klarade inte sin variationspolicy."
            )
        quality = PlanQualitySummary(
            status=QualityStatus.PASS,
            basket_audit=audit,
            nutrition=self._nutrition_summary(nutrition),
            diversity=self._diversity_summary(culinary, policy),
        )
        portions = len(plan.recipes) * servings
        premium = float(
            max(
                Decimal(0),
                money(Decimal(str(plan.optimized_basket.total)) - Decimal(str(cheapest_total))),
            )
        )
        allocated_costs = {
            str(row["recipe"]): float(row["deterministic_allocated_cost"])
            for row in self._cost_feedback(plan)["recipe_costs"]
        }
        recipe_costs = [
            RecipeCostSummary(
                recipe_name=row.recipe_name,
                incremental_ingredient_cost=row.marginal_cost,
                allocated_basket_cost=allocated_costs[row.recipe_name],
                cost_per_portion=float(
                    money(
                        Decimal(str(allocated_costs[row.recipe_name]))
                        / Decimal(servings)
                    )
                ),
            )
            for row in search_result.marginal_costs
        ]
        return DiversityPlanOption(
            variation_policy_version=policy.policy_version,
            mode=mode,
            recipes=plan.recipes,
            ingredients=plan.ingredients,
            optimized_basket=plan.optimized_basket,
            recipe_costs=recipe_costs,
            portions=portions,
            price_per_portion=float(
                money(Decimal(str(plan.optimized_basket.total)) / Decimal(portions))
            ),
            diversity_score=culinary.diversity_score,
            average_pairwise_similarity=culinary.average_similarity,
            max_pairwise_similarity=culinary.max_similarity,
            similarity_threshold=policy.max_pairwise_culinary_similarity,
            premium_vs_cheapest=premium,
            premium_per_portion=float(money(Decimal(str(premium)) / Decimal(portions))),
            repetition=self._repetition_summary(culinary),
            quality=quality,
            surplus=self._surplus_summary(audit),
            states_evaluated=search_result.stats.states_evaluated,
            basket_calculations=search_result.stats.basket_calculations,
        )

    def _strategy(self, request: PlanRequest) -> str:
        strategy = (request.strategy or self.settings.meal_plan_strategy).strip().lower()
        if strategy not in {"legacy", "optimized"}:
            raise ValueError("MEAL_PLAN_STRATEGY must be 'legacy' or 'optimized'")
        return strategy

    def _candidate_generator(self) -> tuple[RecipeCandidateGenerator, str]:
        generator = self.candidate_generator or create_recipe_candidate_generator(
            openai_api_key=self.settings.openai_api_key,
            openai_model=self.settings.openai_model,
            recipe_version="legacy",
        )
        source = (
            "openai-candidates"
            if isinstance(generator, OpenAIRecipeCandidateGenerator)
            else "deterministic-candidates"
        )
        return generator, source

    def _recipe_generator(self) -> tuple[RecipeGenerator, str]:
        if self.settings.openai_api_key:
            return (
                OpenAIRecipeGenerator(
                    api_key=self.settings.openai_api_key,
                    model=self.settings.openai_model,
                ),
                "openai",
            )
        return MockRecipeGenerator(), "mock"

    async def _generate_recipes(
        self,
        generator: RecipeGenerator,
        cheap_ingredients: Sequence[CheapIngredient],
        request: PlanRequest,
    ) -> list[Recipe]:
        return await asyncio.to_thread(
            generator.generate_recipes,
            cheap_ingredients,
            request.recipes,
            request.servings,
        )

    async def _match_all_products(
        self,
        ingredients: Sequence[NormalizedIngredient],
        stores: Sequence[Store],
        provider: GroceryPriceProvider,
    ) -> dict[str, list[ProductCandidate]]:
        increment_performance_counter(
            "canonical_ingredients_considered",
            len(ingredients),
        )
        store_ids = [store.store_id for store in stores]
        semaphore = asyncio.Semaphore(6)

        async def match_one(
            ingredient: NormalizedIngredient,
        ) -> tuple[str, list[ProductCandidate]]:
            async with semaphore:
                queries = [ingredient.canonical_name]
                if (
                    ingredient.display_name
                    and ingredient.display_name.casefold() != ingredient.canonical_name.casefold()
                ):
                    queries.append(ingredient.display_name)
                queries.extend(_PRODUCT_SEARCH_VARIANTS.get(ingredient.canonical_name, ()))

                products_by_key: dict[tuple[str, str], Any] = {}
                for query in dict.fromkeys(queries):
                    with performance_span("source_reconciliation"):
                        rows = await provider.search_products(query, store_ids)
                    increment_performance_counter("products_loaded", len(rows))
                    for product in rows:
                        products_by_key[(product.store_id, product.product_id)] = product
                products = list(products_by_key.values())
            with performance_span("candidate_product_matching"):
                candidates = self.matcher.match(ingredient, products, store_ids=store_ids)
            return ingredient.canonical_name, candidates

        pairs = await asyncio.gather(*(match_one(ingredient) for ingredient in ingredients))
        return {name: candidates for name, candidates in pairs}

    async def _evaluate(
        self,
        recipes: list[Recipe],
        stores: Sequence[Store],
        provider: GroceryPriceProvider,
        max_stores: int,
        user_pricing_context: UserPricingContext | None = None,
    ) -> _EvaluatedPlan:
        ingredients = self.normalizer.normalize_and_aggregate(recipes)
        purchasable = [
            ingredient
            for ingredient in ingredients
            if not self.basket_auditor.is_pantry(ingredient)
        ]
        candidates = await self._match_all_products(purchasable, stores, provider)
        pricing_context = user_pricing_context or UserPricingContext()
        pricing_date = current_pricing_date()
        candidates = {
            canonical: [
                price_candidate_for_context(
                    candidate,
                    pricing_context,
                    on_date=pricing_date,
                )
                for candidate in rows
            ]
            for canonical, rows in candidates.items()
        }
        missing = [name for name, rows in candidates.items() if not rows]
        if missing:
            raise IncompleteBasketError(
                "Inga godkända produktmatchningar för: " + ", ".join(sorted(missing))
            )
        single_store_options = self.basket_optimizer.single_store_options(
            purchasable, candidates, stores
        )
        optimized = self.basket_optimizer.optimize(
            purchasable, candidates, stores, max_stores=max_stores
        )
        with performance_span("basket_audit"):
            audit = self.basket_auditor.audit(
                ingredients,
                optimized,
                user_pricing_context=pricing_context,
            )
        if not audit.passed or audit.verification_status == BasketVerificationStatus.INVALID:
            raise IncompleteBasketError(
                "Den optimerade matkassen kunde inte verifieras av BasketAuditor."
            )
        return _EvaluatedPlan(
            recipes=recipes,
            ingredients=ingredients,
            candidates_by_name=candidates,
            single_store_options=single_store_options,
            optimized_basket=optimized,
        )

    def _evaluate_known_candidates(
        self,
        recipes: Sequence[Recipe],
        stores: Sequence[Store],
        candidates_by_name: dict[str, list[ProductCandidate]],
        max_stores: int,
        prepared: PreparedPriceUniverse | None = None,
        user_pricing_context: UserPricingContext | None = None,
    ) -> _EvaluatedPlan:
        """Cost recipes against one already fetched local product snapshot."""

        ingredients = self.normalizer.normalize_and_aggregate(recipes)
        purchasable = [
            ingredient
            for ingredient in ingredients
            if not self.basket_auditor.is_pantry(ingredient)
        ]
        missing = [
            ingredient.canonical_name
            for ingredient in purchasable
            if not candidates_by_name.get(ingredient.canonical_name)
        ]
        if missing:
            raise IncompleteBasketError(
                "Inga poolmatchningar för: " + ", ".join(sorted(set(missing)))
            )
        with self.basket_optimizer.quote_cache(
            price_universe=(prepared.universe if prepared is not None else None),
            persistent_cache=(prepared.package_cache if prepared is not None else None),
            calculator_version=PACKAGE_CALCULATOR_VERSION,
        ):
            single_store_options = self.basket_optimizer.single_store_options(
                purchasable, candidates_by_name, stores
            )
            optimized = self.basket_optimizer.optimize(
                purchasable,
                candidates_by_name,
                stores,
                max_stores=max_stores,
            )
        with performance_span("basket_audit"):
            audit = self.basket_auditor.audit(
                ingredients,
                optimized,
                user_pricing_context=user_pricing_context,
            )
        if not audit.passed or audit.verification_status == BasketVerificationStatus.INVALID:
            raise IncompleteBasketError(
                "Den optimerade matkassen kunde inte verifieras av BasketAuditor."
            )
        return _EvaluatedPlan(
            recipes=list(recipes),
            ingredients=ingredients,
            candidates_by_name=candidates_by_name,
            single_store_options=single_store_options,
            optimized_basket=optimized,
        )

    def _cost_feedback(self, plan: _EvaluatedPlan) -> dict[str, Any]:
        item_by_key = {
            (item.ingredient, item.unit): item
            for group in plan.optimized_basket.stores
            for item in group.items
        }
        total_required = {
            (ingredient.canonical_name, ingredient.unit): Decimal(str(ingredient.required_quantity))
            for ingredient in plan.ingredients
        }
        allocated_rows: list[tuple[str, Decimal]] = []
        for recipe in plan.recipes:
            allocated = Decimal(0)
            for ingredient in self.normalizer.normalize_and_aggregate([recipe]):
                key = (ingredient.canonical_name, ingredient.unit)
                item = item_by_key.get(key)
                required = total_required.get(key)
                if item is None or not required:
                    continue
                allocated += (
                    money(item.total_price) * Decimal(str(ingredient.required_quantity)) / required
                )
            allocated_rows.append((recipe.name, money(allocated)))

        # Each recipe share is displayed in cents, so independent rounding can
        # leave a +/- cent remainder. Reconcile that remainder on the final
        # deterministic row: the allocation remains reproducible and its sum
        # is exactly the authoritative basket total.
        if allocated_rows:
            allocated_total = sum(
                (amount for _recipe_name, amount in allocated_rows),
                Decimal(0),
            )
            remainder = money(plan.optimized_basket.total) - money(allocated_total)
            recipe_name, amount = allocated_rows[-1]
            allocated_rows[-1] = (recipe_name, money(amount + remainder))
        recipe_costs = [
            {
                "recipe": recipe_name,
                "deterministic_allocated_cost": float(amount),
            }
            for recipe_name, amount in allocated_rows
        ]

        expensive = sorted(
            (
                {
                    "ingredient": item.ingredient,
                    "product": item.product_name,
                    "deterministic_purchase_cost": item.total_price,
                }
                for group in plan.optimized_basket.stores
                for item in group.items
            ),
            key=lambda row: (-row["deterministic_purchase_cost"], row["ingredient"]),
        )[:6]
        return {
            "recipe_costs": recipe_costs,
            "deterministic_basket_total": plan.optimized_basket.total,
            "expensive_ingredients": expensive,
            "instruction": "Priserna är fakta från backend och får inte räknas om av modellen.",
        }

    async def _build_scenarios(
        self,
        plan: _EvaluatedPlan,
        stores: Sequence[Store],
    ) -> list[OptimizationScenario]:
        def calculate() -> list[OptimizationScenario]:
            specifications: list[tuple[str, int | None]] = [
                ("1 butik", 1),
                ("Max 2 butiker", 2),
                ("Max 3 butiker", 3),
                ("Obegränsat", None),
            ]
            scenarios: list[OptimizationScenario] = []
            purchasable = [
                ingredient
                for ingredient in plan.ingredients
                if not self.basket_auditor.is_pantry(ingredient)
            ]
            for label, limit in specifications:
                # This optional comparison must not allocate the full municipal
                # power set (33 contexts => 8,589,934,591 subsets). It is not the
                # requested basket: finite 1/2/3-store plans keep all their gates.
                if limit is None and len(stores) > 12:
                    scenarios.append(OptimizationScenario(
                        label=label, max_stores=None,
                        error="Jämförelsen med obegränsat antal inköpsställen är inte beräknad för detta stora prisområde.",
                    ))
                    continue
                try:
                    basket = self.basket_optimizer.optimize(
                        purchasable,
                        plan.candidates_by_name,
                        stores,
                        max_stores=limit,
                    )
                    scenarios.append(
                        OptimizationScenario(
                            label=label,
                            max_stores=limit,
                            basket=basket,
                        )
                    )
                except IncompleteBasketError as exc:
                    scenarios.append(
                        OptimizationScenario(
                            label=label,
                            max_stores=limit,
                            basket=None,
                            error=str(exc),
                        )
                    )
            return scenarios

        # Unlimited store combinations can become CPU-heavy outside the small
        # Lund PoC set, so do not block FastAPI's event loop while comparing
        # the four checkout scenarios.
        return await asyncio.to_thread(calculate)

    def _marginal_costs_for_plan(
        self,
        plan: _EvaluatedPlan,
        stores: Sequence[Store],
        max_stores: int,
    ) -> list[dict[str, float | str]]:
        """Reprice every selected prefix so debug output follows the final plan."""

        previous_total = Decimal(0)
        recipes: list[Recipe] = []
        rows: list[dict[str, float | str]] = []
        for recipe in plan.recipes:
            recipes.append(recipe)
            ingredients = self.normalizer.normalize_and_aggregate(recipes)
            purchasable = [
                ingredient
                for ingredient in ingredients
                if not self.basket_auditor.is_pantry(ingredient)
            ]
            basket = self.basket_optimizer.optimize(
                purchasable,
                plan.candidates_by_name,
                stores,
                max_stores=max_stores,
                calculate_savings=False,
            )
            new_total = money(basket.total)
            rows.append(
                {
                    "recipe_name": recipe.name,
                    "previous_total": float(previous_total),
                    "new_total": float(new_total),
                    "marginal_cost": float(money(new_total - previous_total)),
                }
            )
            previous_total = new_total
        return rows

    async def _legacy_plan_from_pool(
        self,
        request: PlanRequest,
        pool: EconomicIngredientPool,
        stores: Sequence[Store],
        warnings: list[str],
        prepared: PreparedPriceUniverse | None = None,
        user_pricing_context: UserPricingContext | None = None,
    ) -> tuple[_EvaluatedPlan | None, str]:
        """Build the recipe-first baseline on the same fetched product snapshot."""

        generator, source = self._recipe_generator()
        try:
            recipes = await self._generate_recipes(generator, pool.to_cheap_ingredients(), request)
        # OpenAI/client libraries expose unrelated operational exception
        # classes. Failure of the optional baseline must not discard a valid
        # price snapshot or candidate search.
        except Exception as exc:  # noqa: BLE001
            if not isinstance(generator, OpenAIRecipeGenerator):
                warnings.append(f"Legacy-jämförelsen kunde inte genereras ({type(exc).__name__}).")
                return None, source
            warnings.append(
                "OpenAI:s legacy-recept misslyckades; deterministiska "
                f"jämförelserecept användes ({type(exc).__name__})."
            )
            generator = MockRecipeGenerator()
            source = "mock-legacy-fallback"
            recipes = await self._generate_recipes(generator, pool.to_cheap_ingredients(), request)

        try:
            plan = self._evaluate_known_candidates(
                recipes,
                stores,
                pool.candidates_by_name,
                request.max_stores,
                prepared,
                user_pricing_context,
            )
        except (IncompleteBasketError, ValueError) as exc:
            warnings.append(
                f"Legacy-menyn saknade en komplett korg i den gemensamma produktsnapshoten ({exc})."
            )
            return None, source
        return plan, source

    async def _generate_candidate_recipes(
        self,
        request: PlanRequest,
        pool: EconomicIngredientPool,
        warnings: list[str],
    ) -> tuple[list[Recipe], str, dict[str, int], frozenset[str]]:
        generator, source = self._candidate_generator()
        try:
            recipes = await asyncio.to_thread(
                generator.generate_candidates,
                pool,
                request.candidate_recipe_count,
                request.servings,
            )
        except Exception as exc:
            if not isinstance(generator, OpenAIRecipeCandidateGenerator):
                raise
            warnings.append(
                "OpenAI:s kandidatrecept misslyckades; samma ekonomiska pool "
                f"användes med deterministisk kandidatgenerering ({type(exc).__name__})."
            )
            generator = DeterministicRecipeCandidateGenerator(recipe_version="legacy")
            source = "deterministic-candidate-fallback"
            recipes = await asyncio.to_thread(
                generator.generate_candidates,
                pool,
                request.candidate_recipe_count,
                request.servings,
            )
        batch_statistics = generator.batch_statistics
        if not self.settings.stable_candidate_search_enabled:
            return recipes, source, batch_statistics, frozenset()

        stable_pool = StableCandidatePoolBuilder(
            stable_count=self.settings.stable_candidate_base_count,
            generator=DeterministicRecipeCandidateGenerator(recipe_version="legacy"),
        ).build(
            recipes,
            servings=request.servings,
        )
        batch_statistics = {
            **batch_statistics,
            "stable_base": stable_pool.stable_generated,
            "price_aware_added": stable_pool.price_aware_added,
            "price_aware_duplicates": stable_pool.duplicate_additions,
        }
        return (
            list(stable_pool.recipes),
            f"stable-base+{source}",
            batch_statistics,
            stable_pool.stable_recipe_ids,
        )

    async def _generate_optimized_replacements(
        self,
        request: PlanRequest,
        anchor: _EvaluatedPlan,
        pool: EconomicIngredientPool,
        warnings: list[str],
    ) -> tuple[list[Recipe], int, dict[str, Any] | None]:
        """Generate one validated replacement batch from a stable anchor.

        Pricing and mode selection deliberately happen in the caller, where
        every named policy can search the same candidate union.
        """

        if request.optimization_iterations <= 0 or not self.settings.openai_api_key:
            return [], 0, None

        attempted = 1
        generator, _ = self._candidate_generator()
        details: dict[str, Any] = {
            "replacement_candidates_requested": 10,
            "replacement_candidates_generated": 0,
            "replacement_candidates_valid": 0,
            "accepted": False,
            "anchor_total": anchor.optimized_basket.total,
            "anchor_recipes": [recipe.name for recipe in anchor.recipes],
        }
        try:
            replacements = await asyncio.to_thread(
                generator.generate_replacement_candidates,
                anchor.recipes,
                self._cost_feedback(anchor),
                pool,
                10,
                request.servings,
            )
            details["replacement_candidates_generated"] = len(replacements)
            replacement_validation = await asyncio.to_thread(
                self.candidate_validator.validate_and_prune,
                replacements,
                pool.candidates_by_name,
                servings=request.servings,
            )
            details["replacement_candidates_valid"] = len(replacement_validation.valid_recipes)
            details["replacement_candidates_rejected"] = len(replacement_validation.rejected)
            nutrition_validator = self._nutrition_for(request)
            replacement_nutrition = await asyncio.to_thread(
                nutrition_validator.validate_recipes,
                replacement_validation.valid_recipes,
            )
            nutrition_valid_replacements = self._nutrition_valid_recipes(
                replacement_validation.valid_recipes,
                replacement_nutrition,
            )
            details["replacement_candidates_nutrition_valid"] = len(nutrition_valid_replacements)
            if not nutrition_valid_replacements:
                warnings.append(
                    "OpenAI:s ersättningsförslag innehöll inga fullt matchningsbara "
                    "recept som klarade måltidskvalitetsgränserna; den verifierade "
                    "planen behölls."
                )
                return [], attempted, details
            return nutrition_valid_replacements, attempted, details
        # The pass is optional. Operational OpenAI failures and malformed
        # proposals must not discard an already verified deterministic plan.
        except Exception as exc:  # noqa: BLE001
            details["error_type"] = type(exc).__name__
            warnings.append(
                "OpenAI:s frivilliga förbättringspass kunde inte verifieras; den "
                f"befintliga planen behölls ({type(exc).__name__})."
            )
            return [], attempted, details

    @traced_plan_call
    async def _build_optimized_with_provider(
        self,
        request: PlanRequest,
        provider: GroceryPriceProvider,
        inherited_warnings: list[str] | None = None,
    ) -> PlanResponse:
        """Search recipe combinations against one exact local product snapshot."""

        started = perf_counter()
        pricing_timestamp = datetime.now(tz=UTC)
        warnings = list(inherited_warnings or [])
        if request.availability_mode.value == "strict":
            warnings.append(
                "Strikt sortiment är rådgivande i denna version: endast exakt, färsk "
                "fysisk butiksevidens får påverka sortimentet. Där sådan koppling saknas "
                "behålls källstödda onlineprodukter med okänd fysisk tillgänglighet."
            )
        timings: dict[str, float] = {}
        prepared: PreparedPriceUniverse | None = None
        freshness_view = None
        membership_vector = normalized_memberships(
            request.pricing_memberships or None,
            use_member_prices=request.use_member_prices,
        )
        pricing_context = UserPricingContext.from_chain_flags(membership_vector)
        pricing_date = current_pricing_date()
        pricing_cache_identity = (
            f"{pricing_context.cache_identity}:{pricing_date.isoformat()}:"
            f"{self.economic_selector.cache_identity}"
        )
        universe_lookup_started = perf_counter()
        if self.price_universe_manager is not None:
            with performance_span("price_universe_lookup"):
                prepared = self.price_universe_manager.get_for_request(
                    request.postal_code,
                    membership_vector,
                )
                if (
                    prepared is not None
                    and prepared.status(
                        warning_age_hours=self.settings.price_age_warning_hours,
                        stale_age_hours=self.settings.max_price_age_hours,
                    ).status
                    == "stale"
                ):
                    increment_performance_counter("stale_universes_rejected")
                    prepared = None
        timings["price_universe_lookup"] = perf_counter() - universe_lookup_started
        eligible_member_contracts: frozenset[str]

        if prepared is not None:
            freshness_view = prepared.request_view(
                stale_age_hours=self.settings.max_price_age_hours,
                allowed_context_ids=request.allowed_store_ids,
            )
            pricing_cache_identity = (
                f"{pricing_cache_identity}:freshness:{freshness_view.cache_identity}"
            )
            if freshness_view.excluded_stale_context_ids:
                warnings.append(
                    f"{len(freshness_view.excluded_stale_context_ids)} äldre "
                    "priskontext(er) uteslöts från planen; övriga aktuella "
                    "priskällor jämfördes som vanligt."
                )
            increment_performance_counter("price_universe_cache_hits")
            increment_performance_counter("cache_hits")
            increment_performance_counter("stores_loaded", len(freshness_view.stores))
            increment_performance_counter(
                "products_loaded",
                prepared.universe.stats.raw_products,
            )
            stores = list(freshness_view.stores)
            projection_started = perf_counter()
            projection_base = prepared.pricing_projection_cache.get_or_compute(
                (
                    f"pricing-semantics:{self.economic_selector.cache_identity}:"
                    f"freshness:{freshness_view.cache_identity}"
                ),
                lambda: prepare_economic_pool_for_pricing(
                    freshness_view.economic_pool,
                    selector=self.economic_selector,
                ),
            )
            eligible_member_contracts = eligible_member_contract_fingerprints(
                projection_base,
                pricing_context,
                on_date=pricing_date,
            )
            public_floor_pool = None
            if pricing_context.cache_identity != UserPricingContext().cache_identity:
                public_pricing_cache_identity = (
                    f"{UserPricingContext().cache_identity}:"
                    f"{pricing_date.isoformat()}:"
                    f"{self.economic_selector.cache_identity}:"
                    f"freshness:{freshness_view.cache_identity}"
                )
                public_floor_pool = (
                    prepared.pricing_projection_cache.get_or_compute(
                        public_pricing_cache_identity,
                        lambda: project_economic_pool(
                            projection_base,
                            UserPricingContext(),
                            selector=self.economic_selector,
                            on_date=pricing_date,
                        ),
                    )
                )
            pool = prepared.pricing_projection_cache.get_or_compute(
                pricing_cache_identity,
                lambda: project_economic_pool(
                    projection_base,
                    pricing_context,
                    selector=self.economic_selector,
                    on_date=pricing_date,
                    public_floor_pool=public_floor_pool,
                ),
            )
            timings["pricing_projection"] = perf_counter() - projection_started
            timings["store_lookup"] = 0.0
            timings["economic_pool"] = 0.0
            timings["price_provider_fetch"] = 0.0
        else:
            increment_performance_counter("price_universe_cache_misses")
            increment_performance_counter("cache_misses")
            if request.allowed_store_ids:
                raise IncompleteBasketError("Lokalt prisunderlag krävs för uttryckligt butiksval.")
            if (
                self.settings.price_universe_required
                and str(getattr(provider, "source_name", "")).casefold() != "mock"
            ):
                raise IncompleteBasketError(
                    "Inget aktivt PriceUniverse matchar område, snapshots och medlemskap."
                )
            fetch_started = perf_counter()
            store_lookup_started = perf_counter()
            with (
                performance_span("load_promoted_snapshots"),
                performance_span("source_reconciliation"),
            ):
                stores = self._full_basket_stores(await provider.find_stores(request.postal_code))
            increment_performance_counter("stores_loaded", len(stores))
            timings["store_lookup"] = perf_counter() - store_lookup_started
            pool_started = perf_counter()
            shared_pool = await self.economic_selector.select(provider, stores)
            timings["economic_pool"] = perf_counter() - pool_started
            projection_started = perf_counter()
            projection_base = prepare_economic_pool_for_pricing(
                shared_pool,
                selector=self.economic_selector,
            )
            eligible_member_contracts = eligible_member_contract_fingerprints(
                projection_base,
                pricing_context,
                on_date=pricing_date,
            )
            public_floor_pool = (
                project_economic_pool(
                    projection_base,
                    UserPricingContext(),
                    selector=self.economic_selector,
                    on_date=pricing_date,
                )
                if pricing_context.cache_identity
                != UserPricingContext().cache_identity
                else None
            )
            pool = project_economic_pool(
                projection_base,
                pricing_context,
                selector=self.economic_selector,
                on_date=pricing_date,
                public_floor_pool=public_floor_pool,
            )
            timings["pricing_projection"] = perf_counter() - projection_started
            self._record_price_provider_fetch_timing(
                timings,
                provider,
                perf_counter() - fetch_started,
            )
        membership_coverage_rows = membership_coverage(
            projection_base,
            pricing_context,
            on_date=pricing_date,
        )
        if not pool.ingredients or not pool.candidates_by_name:
            raise IncompleteBasketError(
                "Ingen användbar ekonomisk råvarupool kunde byggas för området."
            )

        pool = filter_economic_pool(
            pool,
            preference=request.diet_preference,
            avoid_ingredients=request.avoid_ingredients,
        )
        if not pool.ingredients or not pool.candidates_by_name:
            raise IncompleteBasketError(
                "Inga användbara råvaror återstod efter kost- och ingrediensfiltrering."
            )

        legacy_started = perf_counter()
        legacy, legacy_source = await self._legacy_plan_from_pool(
            request,
            pool,
            stores,
            warnings,
            prepared,
            pricing_context,
        )
        # Keep the priced recipe-first result for comparison even when its
        # recipes fail the new quality guardrails. Only quality-valid legacy
        # recipes remain eligible for the optimized search/upper bound.
        legacy_comparison_plan = legacy
        timings["legacy_baseline"] = perf_counter() - legacy_started

        generation_started = perf_counter()
        (
            generated,
            recipe_source,
            candidate_batch_statistics,
            stable_recipe_ids,
        ) = await self._generate_candidate_recipes(request, pool, warnings)
        increment_performance_counter("recipe_candidates_generated", len(generated))
        record_performance_seconds(
            "recipe_candidate_generation",
            perf_counter() - generation_started,
        )
        timings["candidate_generation"] = perf_counter() - generation_started

        validation_started = perf_counter()
        generated_validation = await asyncio.to_thread(
            self.candidate_validator.validate_and_prune,
            generated,
            pool.candidates_by_name,
            servings=request.servings,
        )
        generated_validation.valid_recipes[:] = [
            recipe
            for recipe in generated_validation.valid_recipes
            if recipe_respects_diet(
                recipe,
                preference=request.diet_preference,
                avoid_ingredients=request.avoid_ingredients,
            )
        ]
        structural_seconds = perf_counter() - validation_started
        increment_performance_counter(
            "recipe_candidates_structurally_valid",
            len(generated_validation.valid_recipes),
        )
        increment_performance_counter(
            "recipe_candidates_structurally_rejected",
            len(generated_validation.rejected),
        )

        nutrition_validator = self._nutrition_for(request)
        nutrition_started = perf_counter()
        generated_nutrition = await asyncio.to_thread(
            nutrition_validator.validate_recipes,
            generated_validation.valid_recipes,
        )
        nutrition_valid_generated = self._nutrition_valid_recipes(
            generated_validation.valid_recipes,
            generated_nutrition,
        )
        legacy_nutrition: RecipeQualityValidationReport | None = None
        if legacy is not None:
            legacy_nutrition = await asyncio.to_thread(
                nutrition_validator.validate_recipes,
                legacy.recipes,
            )
            if not legacy_nutrition.is_valid:
                warnings.append(
                    "Legacy-menyn klarade inte de konfigurerade portions- och "
                    "måltidskvalitetsgränserna och används därför inte som baslinje."
                )
                legacy = None
        timings["nutrition_validation"] = perf_counter() - nutrition_started
        record_performance_seconds(
            "nutrition",
            timings["nutrition_validation"],
        )

        # Prepend the old recipe-first menu so a valid baseline ingredient
        # profile remains eligible during deterministic menu search. A second
        # prune removes any profile overlap without inflating generated/valid
        # candidate statistics exposed by the API.
        search_validation_started = perf_counter()
        search_validation = await asyncio.to_thread(
            self.candidate_validator.validate_and_prune,
            [
                *(legacy.recipes if legacy else []),
                *nutrition_valid_generated,
            ],
            pool.candidates_by_name,
            servings=request.servings,
        )
        search_validation.valid_recipes[:] = [
            recipe
            for recipe in search_validation.valid_recipes
            if recipe_respects_diet(
                recipe,
                preference=request.diet_preference,
                avoid_ingredients=request.avoid_ingredients,
            )
        ]
        timings["candidate_validation"] = structural_seconds + (
            perf_counter() - search_validation_started
        )
        record_performance_seconds(
            "candidate_validation",
            timings["candidate_validation"],
        )
        if len(search_validation.valid_recipes) < request.recipes:
            raise IncompleteBasketError(
                f"Endast {len(search_validation.valid_recipes)} giltiga receptkandidater "
                "återstod; "
                f"{request.recipes} krävs."
            )

        retained_stable_recipe_ids = frozenset(
            recipe_id(recipe)
            for recipe in search_validation.valid_recipes
            if recipe_id(recipe) in stable_recipe_ids
        )

        policies = {mode: self._diversity_policy_for(request, mode) for mode in DiversityMode}
        target_policies = dict(policies)
        variation_limitations: dict[DiversityMode, list[str]] = {}
        search_started = perf_counter()
        menu_result_cache_hits_before = (
            prepared.menu_search_cache.stats.hits if prepared is not None else 0
        )
        if self.settings.stable_candidate_search_enabled:
            configured_limit = max(
                self.settings.stable_candidate_search_limit,
                len(retained_stable_recipe_ids),
            )
            if request.candidate_search_limit is not None:
                configured_limit = max(configured_limit, request.candidate_search_limit)
            candidate_limit = min(
                configured_limit,
                len(search_validation.valid_recipes),
            )
        else:
            candidate_limit = (
                min(request.candidate_search_limit, len(search_validation.valid_recipes))
                if request.candidate_search_limit is not None
                else None
            )

        def run_variant_search() -> Any:
            # Pairwise culinary similarity is part of deterministic search,
            # not of its cache identity.  Build it only on a cache miss so a
            # repeated/prewarmed user request does not redo O(recipes²) work
            # before discovering that the exact multi-mode result is cached.
            with performance_span("diversity"):
                constraints_by_mode = {
                    mode.value: self._culinary_constraints(
                        search_validation.valid_recipes,
                        policy,
                    )
                    for mode, policy in policies.items() if mode != DiversityMode.VARIED
                }
            return self.menu_optimizer.optimize_variants(
                search_validation.valid_recipes,
                pool.candidates_by_name,
                stores,
                constraints_by_mode,
                recipe_count=request.recipes,
                max_stores=request.max_stores,
                beam_width=request.beam_width,
                candidate_limit=candidate_limit,
                price_universe=(prepared.universe if prepared is not None else None),
                package_cost_cache=(prepared.package_cache if prepared is not None else None),
                basket_result_cache=(prepared.basket_cache if prepared is not None else None),
                pricing_context_id=pricing_cache_identity,
                user_pricing_context=pricing_context,
                retained_recipe_ids=retained_stable_recipe_ids,
                stratified_candidate_pruning=(
                    self.settings.stable_candidate_search_enabled
                ),
                search_reuse_enabled=self.settings.stable_candidate_search_enabled,
                admissible_lower_bound_enabled=(
                    self.settings.stable_candidate_search_enabled
                ),
            )

        if prepared is not None:
            search_cache_key = menu_search_cache_key(
                prepared.universe,
                search_validation.valid_recipes,
                self._menu_search_cache_payload(
                    request,
                    policies,
                    candidate_limit,
                    pricing_context_id=pricing_cache_identity,
                    stable_candidate_search_enabled=(
                        self.settings.stable_candidate_search_enabled
                    ),
                    retained_stable_recipe_ids=retained_stable_recipe_ids,
                ),
            )
            effective_contract_context_id = (
                f"pricing-contract-set:{pricing_date.isoformat()}:"
                f"{self.economic_selector.cache_identity}:"
                + (",".join(sorted(eligible_member_contracts)) or "public")
                + f":freshness:{freshness_view.cache_identity}"
            )
            effective_search_cache_key = menu_search_cache_key(
                prepared.universe,
                search_validation.valid_recipes,
                self._menu_search_cache_payload(
                    request,
                    policies,
                    candidate_limit,
                    pricing_context_id=effective_contract_context_id,
                    stable_candidate_search_enabled=(
                        self.settings.stable_candidate_search_enabled
                    ),
                    retained_stable_recipe_ids=retained_stable_recipe_ids,
                ),
            )

            def effective_cached_search() -> Any:
                return prepared.effective_menu_search_cache.get_or_compute(
                    effective_search_cache_key,
                    run_variant_search,
                )

            variant_search = await asyncio.to_thread(
                prepared.menu_search_cache.get_or_compute,
                search_cache_key,
                effective_cached_search,
            )
        else:
            variant_search = await asyncio.to_thread(run_variant_search)
        timings["menu_search"] = perf_counter() - search_started
        if (
            prepared is not None
            and prepared.menu_search_cache.stats.hits > menu_result_cache_hits_before
        ):
            record_performance_seconds("menu_search", timings["menu_search"])
        variant_plans = {
            DiversityMode(mode): self._evaluate_known_candidates(
                search_result.recipes,
                stores,
                pool.candidates_by_name,
                request.max_stores,
                prepared,
                pricing_context,
            )
            for mode, search_result in variant_search.results.items()
        }
        variant_origins = {mode: "beam_search" for mode in variant_plans}
        variant_results = {
            DiversityMode(mode): search_result
            for mode, search_result in variant_search.results.items()
        }

        # The recipe-first result is already priced on this exact snapshot. It
        # remains a safe upper bound only for modes whose culinary policy it passes.
        if legacy is not None:
            legacy_culinary = self._culinary_report(legacy.recipes)
            for mode, policy in policies.items():
                plan = variant_plans.get(mode)
                if (
                    plan is not None
                    and _basket_selection_key(legacy.optimized_basket)
                    < _basket_selection_key(plan.optimized_basket)
                    and self._culinary_policy_passes(legacy_culinary, policy)
                ):
                    variant_plans[mode] = legacy
                    variant_origins[mode] = "legacy_upper_bound"

        # A plan found by a stricter mode is also a candidate upper bound for
        # every policy it satisfies. This prevents beam approximation from ever
        # making CHEAPEST more expensive than BALANCED/VARIED.
        found_plans = list(variant_plans.items())
        for target_mode, target_policy in policies.items():
            current = variant_plans.get(target_mode)
            for source_mode, candidate_plan in found_plans:
                if not self._culinary_policy_passes(
                    self._culinary_report(candidate_plan.recipes),
                    target_policy,
                ):
                    continue
                if current is None or _basket_selection_key(
                    candidate_plan.optimized_basket
                ) < _basket_selection_key(current.optimized_basket):
                    variant_plans[target_mode] = candidate_plan
                    current = candidate_plan
                    variant_origins[target_mode] = f"{source_mode.value}_mode_upper_bound"
                    if source_mode in variant_results:
                        variant_results[target_mode] = variant_results[source_mode]

        # Search exhaustion is not a proof of global infeasibility. Return an
        # audited softer menu with an explicit limitation, never a false PASS.
        for mode, fallback in ((DiversityMode.BALANCED, DiversityMode.CHEAPEST),
                               (DiversityMode.VARIED, DiversityMode.BALANCED)):
            if mode not in variant_plans and fallback in variant_plans:
                variant_plans[mode] = variant_plans[fallback]
                variant_results[mode] = variant_results[fallback]
                variant_origins[mode] = "reported_soft_variation_fallback"
                policies[mode] = policies[fallback].model_copy(update={"mode": mode})
                variation_limitations[mode] = [
                    ("Den avgränsade sökningen hittade ingen meny som klarar alla "
                    "variationsmål med tillgängliga, kostgodkända recept. "
                    "Mjuka variationskrav har lättats; kostval, priser och butiksgräns gäller.")
                ]

        if request.diversity_mode not in variant_plans:
            reason = variant_search.errors.get(
                request.diversity_mode.value,
                "ingen giltig plan hittades",
            )
            raise IncompleteBasketError(
                f"Variationsläget {request.diversity_mode.value} kunde inte byggas: {reason}"
            )

        active_search_recipes = list(search_validation.valid_recipes)
        best = variant_plans[request.diversity_mode]
        selected_plan_origin = variant_origins[request.diversity_mode]
        if selected_plan_origin == "legacy_upper_bound":
            warnings.append(
                "Beam search hittade ingen billigare giltig meny än legacy-baslinjen; "
                "den verifierade billigare baslinjen behölls."
            )
            selected_plan_origin = "legacy_upper_bound"
            recipe_source = f"{legacy_source}-upper-bound"

        selected_total_before_improvement = money(best.optimized_basket.total)
        selected_key_before_improvement = _basket_selection_key(best.optimized_basket)
        improvement_started = perf_counter()
        # BALANCED is the stable, request-mode-independent anchor. Falling back
        # through enum order only matters if a policy was infeasible in the
        # initial beam. The generator therefore sees the same menu regardless
        # of which returned plan the client initially selected.
        improvement_anchor = (
            variant_plans.get(DiversityMode.BALANCED)
            or variant_plans.get(DiversityMode.CHEAPEST)
            or next(variant_plans[mode] for mode in DiversityMode if mode in variant_plans)
        )
        replacements, attempted, improvement_details = await self._generate_optimized_replacements(
            request,
            improvement_anchor,
            pool,
            warnings,
        )
        accepted = 0
        if improvement_details is not None:
            improvement_details["old_total"] = float(selected_total_before_improvement)
        if replacements:
            # All three policies receive the same nutrition-valid union and
            # exact product snapshot. Each mode is accepted independently only
            # when deterministic repricing is strictly cheaper than its own
            # incumbent plan.
            improvement_validation = await asyncio.to_thread(
                self.candidate_validator.validate_and_prune,
                [*active_search_recipes, *replacements],
                pool.candidates_by_name,
                servings=request.servings,
            )
            active_search_recipes = improvement_validation.valid_recipes
            if improvement_details is not None:
                improvement_details["shared_candidate_pool"] = len(active_search_recipes)
                improvement_details["union_duplicates_rejected"] = len(
                    improvement_validation.rejected
                )
            constraints_by_mode = {
                mode.value: self._culinary_constraints(
                    active_search_recipes,
                    policy,
                )
                for mode, policy in policies.items() if mode != DiversityMode.VARIED
            }
            improvement_search = await asyncio.to_thread(
                self.menu_optimizer.optimize_variants,
                active_search_recipes,
                pool.candidates_by_name,
                stores,
                constraints_by_mode,
                recipe_count=request.recipes,
                max_stores=request.max_stores,
                beam_width=request.beam_width,
                # The replacement batch is small and must not be discarded by
                # an individual-cost limit inherited from the initial search.
                candidate_limit=None,
                price_universe=(prepared.universe if prepared is not None else None),
                package_cost_cache=(prepared.package_cache if prepared is not None else None),
                basket_result_cache=(prepared.basket_cache if prepared is not None else None),
                pricing_context_id=pricing_cache_identity,
                user_pricing_context=pricing_context,
                retained_recipe_ids=frozenset(
                    recipe_id(recipe)
                    for recipe in active_search_recipes
                    if recipe_id(recipe) in stable_recipe_ids
                ),
                search_reuse_enabled=self.settings.stable_candidate_search_enabled,
                admissible_lower_bound_enabled=(
                    self.settings.stable_candidate_search_enabled
                ),
            )
            mode_totals: dict[str, float] = {}
            accepted_modes: list[str] = []
            for mode_value, improvement_result in improvement_search.results.items():
                mode = DiversityMode(mode_value)
                candidate_plan = self._evaluate_known_candidates(
                    improvement_result.recipes,
                    stores,
                    pool.candidates_by_name,
                    request.max_stores,
                    prepared,
                    pricing_context,
                )
                mode_totals[mode.value] = candidate_plan.optimized_basket.total
                current = variant_plans.get(mode)
                if (
                    current is None
                    or _strict_price_improvement(
                        candidate_plan.optimized_basket,
                        current.optimized_basket,
                    )
                ) and self._culinary_policy_passes(
                    self._culinary_report(candidate_plan.recipes),
                    policies[mode],
                ):
                    variant_plans[mode] = candidate_plan
                    variant_results[mode] = improvement_result
                    variant_origins[mode] = "openai_improvement"
                    accepted_modes.append(mode.value)

            # A stricter improved plan is also a valid upper bound for every
            # looser policy. Propagate it before computing selected acceptance
            # and the eventual premium baseline.
            improved_sources = list(variant_plans.items())
            for target_mode, target_policy in policies.items():
                current = variant_plans.get(target_mode)
                for source_mode, candidate_plan in improved_sources:
                    if not self._culinary_policy_passes(
                        self._culinary_report(candidate_plan.recipes),
                        target_policy,
                    ):
                        continue
                    if current is None or _basket_selection_key(
                        candidate_plan.optimized_basket
                    ) < _basket_selection_key(current.optimized_basket):
                        variant_plans[target_mode] = candidate_plan
                        current = candidate_plan
                        variant_results[target_mode] = variant_results[source_mode]
                        variant_origins[target_mode] = (
                            f"{source_mode.value}_improvement_upper_bound"
                        )

            if improvement_details is not None:
                improvement_details["mode_totals"] = mode_totals
                improvement_details["accepted_modes"] = accepted_modes
                improvement_details["search_errors"] = dict(improvement_search.errors)

        best = variant_plans[request.diversity_mode]
        if _basket_selection_key(best.optimized_basket) < selected_key_before_improvement:
            accepted = 1
            selected_plan_origin = variant_origins[request.diversity_mode]
            recipe_source = f"{recipe_source}+openai-improvement"
            if improvement_details is not None:
                improvement_details["accepted"] = True
                price_delta = money(
                    Decimal(str(best.optimized_basket.total)) - selected_total_before_improvement
                )
                improvement_details["deterministic_savings"] = float(max(Decimal(0), -price_delta))
                improvement_details["price_delta"] = float(price_delta)
                improvement_details["verification_upgrade"] = (
                    _BASKET_VERIFICATION_RANK[best.optimized_basket.verification_status]
                    < selected_key_before_improvement[0]
                )
        if improvement_details is not None:
            improvement_details["new_total"] = best.optimized_basket.total
            if request.diversity_mode in variant_results:
                improvement_details["search_stats"] = asdict(
                    variant_results[request.diversity_mode].stats
                )
        if attempted:
            timings["llm_improvement"] = perf_counter() - improvement_started

        # Do not run a selected-mode-only one-store menu beam here: that makes
        # the returned alternatives depend on which projection the client
        # requested and can triple normal runtime when repeated for every mode.
        # The exact same selected menu is compared across store limits below;
        # requests with max_stores=1 are already searched under that limit in
        # the main shared variant search.
        tradeoff_started = perf_counter()
        one_store_search_stats: dict[str, Any] | None = None

        # Re-apply cross-mode upper bounds after optional improvement. This
        # keeps premiums non-negative when a stricter mode found a cheaper plan.
        latest_plans = list(variant_plans.items())
        for target_mode, target_policy in policies.items():
            current = variant_plans.get(target_mode)
            for source_mode, candidate_plan in latest_plans:
                if not self._culinary_policy_passes(
                    self._culinary_report(candidate_plan.recipes),
                    target_policy,
                ):
                    continue
                if current is None or _basket_selection_key(
                    candidate_plan.optimized_basket
                ) < _basket_selection_key(current.optimized_basket):
                    variant_plans[target_mode] = candidate_plan
                    current = candidate_plan
                    variant_origins[target_mode] = f"{source_mode.value}_late_upper_bound"
                    variant_results[target_mode] = variant_results[source_mode]

        balanced_reference = variant_plans[DiversityMode.BALANCED]
        balanced_total = money(balanced_reference.optimized_basket.total)
        varied_ceiling = (balanced_total * (Decimal(1) + Decimal(str(request.varied_budget_percent)) / Decimal(100))).quantize(Decimal("0.01"), rounding="ROUND_FLOOR")
        # Balanced is now final, including any validated recipe improvements.
        # Varied is searched once against that exact reference; no subsequent
        # cross-mode price upper bound may overwrite either reference or result.
        conditioned_started = perf_counter()
        balanced_result = variant_results[DiversityMode.BALANCED]
        balanced_result = MenuOptimizationResult(
            recipes=balanced_reference.recipes, basket=balanced_reference.optimized_basket,
            ingredients=balanced_reference.ingredients, stats=balanced_result.stats,
            marginal_costs=balanced_result.marginal_costs, basket_audit=balanced_result.basket_audit,
        )

        def run_conditioned_search() -> Any:
            return search_conditioned_varied(
                self.menu_optimizer, active_search_recipes, pool.candidates_by_name, stores,
                balanced_result=balanced_result,
                target_constraints=self._culinary_constraints(active_search_recipes, target_policies[DiversityMode.VARIED]),
                fallback_constraints=self._culinary_constraints(active_search_recipes, policies[DiversityMode.BALANCED]),
                budget_percent=request.varied_budget_percent,
                recipe_count=request.recipes, max_stores=request.max_stores,
                beam_width=request.beam_width, candidate_limit=None,
                price_universe=prepared.universe if prepared is not None else None,
                package_cost_cache=prepared.package_cache if prepared is not None else None,
                basket_result_cache=prepared.basket_cache if prepared is not None else None,
                pricing_context_id=pricing_cache_identity, user_pricing_context=pricing_context,
                search_reuse_enabled=self.settings.stable_candidate_search_enabled,
                admissible_lower_bound_enabled=self.settings.stable_candidate_search_enabled,
            )

        if prepared is not None:
            conditioned_key = menu_search_cache_key(prepared.universe, active_search_recipes, {
                **self._menu_search_cache_payload(request, policies, None, pricing_context_id=pricing_cache_identity),
                "phase": "conditioned_varied",
                "balanced_reference": reference_identity(balanced_reference.recipes),
                "balanced_total": str(balanced_total),
                "target_policy": target_policies[DiversityMode.VARIED].model_dump(mode="json"),
            })
            conditioned = await asyncio.to_thread(prepared.menu_search_cache.get_or_compute,
                                                   conditioned_key, run_conditioned_search)
        else:
            conditioned = await asyncio.to_thread(run_conditioned_search)
        variant_results[DiversityMode.VARIED] = conditioned.result
        variant_plans[DiversityMode.VARIED] = self._evaluate_known_candidates(
            conditioned.result.recipes, stores, pool.candidates_by_name,
            request.max_stores, prepared, pricing_context,
        )
        variant_origins[DiversityMode.VARIED] = "balanced_conditioned_search"
        policies[DiversityMode.VARIED] = (
            policies[DiversityMode.BALANCED].model_copy(update={"mode": DiversityMode.VARIED})
            if conditioned.internal_targets_relaxed else target_policies[DiversityMode.VARIED]
        )
        inter_plan = compare_plans(balanced_reference.recipes, conditioned.result.recipes)
        variation_limitations[DiversityMode.VARIED] = []
        if not inter_plan["target_met"]:
            variation_limitations[DiversityMode.VARIED].append(
                f"{inter_plan['structurally_different_dinners']} av {request.recipes} middagar kunde ändras "
                f"inom pris- och tillgänglighetsgränserna (mål {inter_plan['required_changes']})."
            )
        timings["conditioned_varied_search"] = perf_counter() - conditioned_started
        if improvement_details is not None:
            improvement_details.setdefault("mode_totals", {})["varied"] = conditioned.result.basket.total
            improvement_details["varied_selection"] = "conditioned_on_final_balanced"
            improvement_details["new_total"] = variant_plans[request.diversity_mode].optimized_basket.total

        best = variant_plans[request.diversity_mode]
        result = variant_results[request.diversity_mode]
        selected_plan_origin = variant_origins[request.diversity_mode]
        if any(
            not recipe_respects_diet(
                recipe,
                preference=request.diet_preference,
                avoid_ingredients=request.avoid_ingredients,
            )
            for recipe in best.recipes
        ):
            raise IncompleteBasketError(
                "Den valda menyn bröt mot begärt kost- eller ingrediensfilter."
            )

        complete_single_options = [
            option for option in best.single_store_options if option.is_complete
        ]
        cheapest_same_menu_single = min(
            complete_single_options,
            key=lambda option: (*_basket_selection_key(option), option.store_id),
            default=None,
        )
        one_store_total = cheapest_same_menu_single.total if cheapest_same_menu_single else None
        one_store_names = (
            [cheapest_same_menu_single.store_name] if cheapest_same_menu_single is not None else []
        )
        timings["store_tradeoff_search"] = perf_counter() - tradeoff_started

        audit_started = perf_counter()
        with performance_span("basket_audit"):
            basket_audit = self.basket_auditor.audit(
                best.ingredients,
                best.optimized_basket,
                user_pricing_context=pricing_context,
            )
        with performance_span("nutrition"):
            selected_nutrition = nutrition_validator.validate_recipes(best.recipes)
        with performance_span("diversity"):
            selected_culinary = self._culinary_report(best.recipes)
        if not basket_audit.passed:
            missing = ", ".join(
                f"{item.canonical_name} ({item.deficit_quantity:g} {item.unit})"
                for item in basket_audit.deficits
            )
            raise IncompleteBasketError(
                "Den valda matkassen täcker inte alla receptbehov: " + missing
            )
        if not selected_nutrition.is_valid:
            raise IncompleteBasketError(
                "Den valda menyn klarar inte de konfigurerade måltidskvalitetsgränserna."
            )
        if not self._culinary_policy_passes(
            selected_culinary,
            policies[request.diversity_mode],
        ):
            raise IncompleteBasketError(
                "Den valda menyn överskrider gränsen för kulinarisk likhet."
            )
        if best.optimized_basket.store_count > request.max_stores:
            raise IncompleteBasketError("Den valda matkassen överskrider max_stores.")
        if (
            best.optimized_basket.verification_status
            == BasketVerificationStatus.VERIFIED_WITH_ESTIMATES
        ):
            warnings.append(
                "Matkassen är semantiskt verifierad men innehåller uppskattade "
                "styck- eller variabelvikter; totalsumman visas därför som cirka."
            )
        elif best.optimized_basket.verification_status == BasketVerificationStatus.UNVERIFIED:
            warnings.append(
                "Matkassen innehåller okänd mängdmetadata och totalpriset är inte "
                "ett verifierat exakt inköpspris."
            )
        timings["basket_audit"] = perf_counter() - audit_started

        quality = PlanQualitySummary(
            status=QualityStatus.PASS,
            basket_audit=basket_audit,
            nutrition=self._nutrition_summary(selected_nutrition),
            diversity=self._diversity_summary(
                selected_culinary,
                policies[request.diversity_mode],
            ),
        )
        surplus = self._surplus_summary(basket_audit)
        store_tradeoff = StoreTradeoff(
            one_store_total=one_store_total,
            selected_total=best.optimized_basket.total,
            selected_store_count=best.optimized_basket.store_count,
            extra_store_savings=(
                float(
                    max(
                        Decimal(0),
                        money(
                            Decimal(str(one_store_total))
                            - Decimal(str(best.optimized_basket.total))
                        ),
                    )
                )
                if one_store_total is not None
                else 0
            ),
            one_store_names=one_store_names,
            selected_store_names=[group.store_name for group in best.optimized_basket.stores],
            one_store_verification_status=(
                cheapest_same_menu_single.verification_status
                if cheapest_same_menu_single is not None
                else None
            ),
            selected_verification_status=best.optimized_basket.verification_status,
        )

        portions = len(best.recipes) * request.servings
        cheapest_plan = variant_plans.get(DiversityMode.CHEAPEST)
        if cheapest_plan is None:
            raise IncompleteBasketError("Den obegränsade CHEAPEST-sökningen gav ingen giltig meny.")
        diversity_plans: dict[DiversityMode, DiversityPlanOption] = {}
        diversity_plan_errors: dict[DiversityMode, str] = {
            DiversityMode(mode): error
            for mode, error in variant_search.errors.items()
            if mode in {item.value for item in DiversityMode}
        }
        for mode, variant_plan in variant_plans.items():
            try:
                diversity_plans[mode] = self._diversity_plan_option(
                    mode=mode,
                    plan=variant_plan,
                    search_result=variant_results[mode],
                    nutrition_validator=nutrition_validator,
                    policy=policies[mode],
                    cheapest_total=cheapest_plan.optimized_basket.total,
                    servings=request.servings,
                    user_pricing_context=pricing_context,
                )
                option = diversity_plans[mode]
                target_met = self._culinary_policy_passes(
                    self._culinary_report(variant_plan.recipes), target_policies[mode])
                limitations = list(variation_limitations.get(mode, []))
                if not target_met:
                    actual = self._culinary_report(variant_plan.recipes)
                    target = target_policies[mode]
                    limitations.append(
                        f"Utfall: {len({p.recipe_family for p in actual.profiles})} rättfamiljer "
                        f"(mål {target.min_recipe_families}), {len({p.cooking_method for p in actual.profiles})} "
                        f"tillagningssätt (mål {target.min_cooking_methods}). "
                        "Se återkommande huvudråvaror och strukturella upprepningar i menyn."
                    )
                if mode == DiversityMode.VARIED:
                    target_met = target_met and inter_plan["target_met"]
                option = option.model_copy(update={
                    "quality": option.quality.model_copy(update={
                        "status": QualityStatus.PASS if target_met else QualityStatus.FAIL,
                        "diversity": self._diversity_summary(
                            self._culinary_report(variant_plan.recipes), target_policies[mode]).model_copy(
                                update={"status": QualityStatus.PASS if target_met else QualityStatus.FAIL})
                    })
                })
                diversity_plans[mode] = option.model_copy(update={
                    "variation_target_met": target_met,
                    "variation_limitations": limitations,
                    "varied_budget_percent": request.varied_budget_percent,
                    "balanced_reference_total": float(balanced_total),
                    "premium_vs_balanced": float(money(Decimal(str(variant_plan.optimized_basket.total)) - balanced_total)),
                    "budget_ceiling": float(varied_ceiling),
                    "inter_plan_distance": ({k: v for k, v in inter_plan.items() if k != "dinners"}
                                            if mode == DiversityMode.VARIED else None),
                })
                diversity_plan_errors.pop(mode, None)
            except IncompleteBasketError as exc:
                diversity_plan_errors[mode] = str(exc)
        if request.diversity_mode not in diversity_plans:
            raise IncompleteBasketError(
                diversity_plan_errors.get(
                    request.diversity_mode,
                    "Det valda variationsläget kunde inte kvalitetsverifieras.",
                )
            )

        quality = quality.model_copy(update={
            "status": diversity_plans[request.diversity_mode].quality.status,
            "diversity": diversity_plans[request.diversity_mode].quality.diversity
        })
        warnings.extend(variation_limitations.get(request.diversity_mode, []))
        scenarios = await self._build_scenarios(best, stores)
        savings = (
            float(
                max(
                    Decimal(0),
                    money(
                        Decimal(str(legacy_comparison_plan.optimized_basket.total))
                        - Decimal(str(best.optimized_basket.total))
                    ),
                )
            )
            if legacy_comparison_plan is not None
            else None
        )
        timings["total_runtime"] = perf_counter() - started
        timings = {key: round(value, 4) for key, value in timings.items()}
        record_performance_seconds("total_runtime", timings["total_runtime"])
        active_trace = current_performance_trace()
        performance = active_trace.snapshot() if active_trace is not None else None

        data_source = (
            prepared.source_name
            if prepared is not None
            else str(getattr(provider, "source_name", provider.__class__.__name__))
        )
        source_diagnostics = (
            self._safe_source_diagnostics(prepared.source_diagnostics)
            if request.debug and prepared is not None
            else (self._source_diagnostics(provider) if request.debug else [])
        )
        price_data = None
        if prepared is not None:
            universe_status = prepared.status(
                warning_age_hours=self.settings.price_age_warning_hours,
                stale_age_hours=self.settings.max_price_age_hours,
                cache_state="warm",
            )
            compared_contexts, excluded_contexts = _consumer_price_context_coverage(
                prepared,
                usable_context_ids=(
                    freshness_view.usable_context_ids if freshness_view is not None else ()
                ),
                excluded_stale_context_ids=(
                    freshness_view.excluded_stale_context_ids
                    if freshness_view is not None
                    else ()
                ),
            )
            price_data = PlanPriceData.model_validate(
                {
                    **universe_status.model_dump(),
                    "pricing_timestamp": pricing_timestamp,
                    "compared_price_contexts": compared_contexts,
                    "excluded_price_contexts": excluded_contexts,
                }
            )
        if data_source == "mock":
            warnings.insert(
                0,
                "Mockpriser används. De är realistisk exempeldata för Lund, inte "
                "aktuella butikspriser.",
            )
        location = str(
            getattr(provider, "location_name", None) or (stores[0].city if stores else "Lund")
        )
        legacy_comparison = None
        if legacy_comparison_plan is not None:
            legacy_comparison = LegacyPlanComparison(
                total=legacy_comparison_plan.optimized_basket.total,
                price_per_portion=float(
                    money(
                        Decimal(str(legacy_comparison_plan.optimized_basket.total))
                        / Decimal(portions)
                    )
                ),
                recipes=[recipe.name for recipe in legacy_comparison_plan.recipes],
                basket=legacy_comparison_plan.optimized_basket,
                savings=savings or 0,
            )

        membership_savings_result = fixed_basket_membership_savings(
            best.optimized_basket,
            projection_base,
            on_date=pricing_date,
        )

        debug_info: dict[str, Any] | None = None
        if request.debug:
            marginal_costs = await asyncio.to_thread(
                self._marginal_costs_for_plan,
                best,
                stores,
                request.max_stores,
            )
            debug_info = {
                "inter_plan_distance": inter_plan,
                "conditioned_varied_search": list(conditioned.attempts),
                "economic_ingredients": [
                    signal.model_dump(mode="json") for signal in pool.ingredients
                ],
                "economic_pool": {
                    "search_queries_executed": pool.search_queries_executed,
                    "products_considered": pool.products_considered,
                },
                "candidate_batches": candidate_batch_statistics,
                "candidate_family_coverage": {
                    family: {
                        "generated": Counter(recipe_family(recipe) for recipe in generated).get(
                            family, 0
                        ),
                        "valid": Counter(
                            recipe_family(recipe) for recipe in search_validation.valid_recipes
                        ).get(family, 0),
                        "selected": Counter(recipe_family(recipe) for recipe in best.recipes).get(
                            family, 0
                        ),
                    }
                    for family in sorted(
                        {recipe_family(recipe) for recipe in generated}
                        | {recipe_family(recipe) for recipe in search_validation.valid_recipes}
                    )
                },
                "candidate_sample": [
                    {
                        "name": recipe.name,
                        "family": recipe_family(recipe),
                        "primary_ingredient": primary_ingredient(recipe),
                        "carbohydrate": carbohydrate_ingredient(recipe),
                    }
                    for recipe in search_validation.valid_recipes[:20]
                ],
                "rejected_candidates": [
                    {
                        "name": rejected.recipe.name,
                        "reasons": list(rejected.reasons),
                    }
                    for rejected in generated_validation.rejected[:50]
                ],
                "nutrition_rejected_candidates": [
                    {
                        "name": validation.recipe_name,
                        "violations": list(validation.violations),
                        "estimate": asdict(validation.estimate),
                    }
                    for validation in generated_nutrition.results
                    if not validation.is_valid
                ][:50],
                "search_stats": asdict(result.stats),
                "marginal_costs": marginal_costs,
                "basket_audit": basket_audit.model_dump(mode="json"),
                "basket_verification": {
                    "status": best.optimized_basket.verification_status,
                    "warnings": best.optimized_basket.verification_warnings,
                    "products": [
                        {
                            "ingredient": item.ingredient,
                            "product": item.product_name,
                            "source": (
                                item.source_provenance.model_dump(mode="json")
                                if item.source_provenance is not None
                                else None
                            ),
                            "semantic": {
                                "canonical_food": item.canonical_food,
                                "food_family": item.food_family,
                                "role": item.product_role,
                                "form": item.product_form,
                                "confidence": item.semantic_confidence,
                                "evidence": item.semantic_evidence,
                            },
                            "purchase": {
                                "sale_model": item.sale_model,
                                "sale_price": item.sale_price,
                                "sale_unit": item.sale_unit,
                                "comparison_price": item.comparison_price,
                                "comparison_unit": item.comparison_unit,
                                "package_quantity": item.package_quantity,
                                "package_unit": item.package_unit,
                                "quantity_confidence": item.quantity_confidence,
                                "packages_needed": item.packages_needed,
                                "purchased_quantity": item.purchased_quantity,
                                "purchased_unit": item.purchased_unit,
                                "purchased_usable_quantity": (item.purchased_usable_quantity),
                                "cost": item.total_price,
                                "warning": item.purchase_warning,
                            },
                        }
                        for group in best.optimized_basket.stores
                        for item in group.items
                    ],
                },
                "nutrition": quality.nutrition.model_dump(mode="json"),
                "recipe_profiles": {
                    recipe.name: asdict(self.culinary_similarity.build_profile(recipe))
                    for recipe in best.recipes
                },
                "culinary_similarity": quality.diversity.model_dump(mode="json"),
                "diversity_policy": policies[request.diversity_mode].model_dump(mode="json"),
                "diversity_plans": {
                    mode.value: {
                        "total": option.optimized_basket.total,
                        "price_per_portion": option.price_per_portion,
                        "premium_vs_cheapest": option.premium_vs_cheapest,
                        "diversity_score": option.diversity_score,
                        "max_pairwise_similarity": (option.max_pairwise_similarity),
                        "repetition": option.repetition.model_dump(mode="json"),
                        "search_stats": asdict(variant_results[mode].stats),
                        "origin": variant_origins[mode],
                    }
                    for mode, option in diversity_plans.items()
                },
                "diversity_plan_errors": {
                    mode.value: error for mode, error in diversity_plan_errors.items()
                },
                "surplus": surplus.model_dump(mode="json"),
                "store_tradeoff": store_tradeoff.model_dump(mode="json"),
                "one_store_search_stats": one_store_search_stats,
                "selected_plan_origin": selected_plan_origin,
                "legacy_recipe_source": legacy_source,
                "llm_improvement": improvement_details,
                "source_resolution": source_diagnostics,
                "performance": (
                    {
                        "timings_ms": performance.timings_ms,
                        "span_statistics": performance.span_statistics,
                        "operation_counters": performance.operation_counters,
                        "search_depth_counters": performance.depth_counters,
                    }
                    if performance is not None
                    else None
                ),
            }

        return PlanResponse(
            location=location,
            postal_code=request.postal_code,
            strategy="optimized",
            diversity_mode=request.diversity_mode,
            membership_programs_used=tuple(
                sorted(
                    {
                        item.membership_program
                        for group in best.optimized_basket.stores
                        for item in group.items
                        if item.membership_required
                        and item.membership_program is not None
                    },
                    key=lambda program: program.value,
                )
            ),
            membership_coverage=membership_coverage_rows,
            membership_savings=membership_savings_result,
            recipes=best.recipes,
            recipe_costs=diversity_plans[request.diversity_mode].recipe_costs,
            ingredients=best.ingredients,
            cheap_ingredients=pool.to_cheap_ingredients(),
            single_store_options=best.single_store_options,
            optimized_basket=best.optimized_basket,
            optimization_scenarios=scenarios,
            portions=portions,
            price_per_portion=float(
                money(Decimal(str(best.optimized_basket.total)) / Decimal(portions))
            ),
            data_source=data_source,
            data=price_data,
            source_diagnostics=source_diagnostics,
            recipe_source=recipe_source,
            warnings=warnings,
            attribution_text=getattr(provider, "attribution_text", None),
            attribution_url=getattr(provider, "attribution_url", None),
            optimization_iterations_attempted=attempted,
            optimization_iterations_accepted=accepted,
            optimization=PlanOptimizationSummary(
                strategy="optimized",
                economic_ingredients=len(pool.ingredients),
                candidate_recipes_generated=len(generated),
                candidate_recipes_valid=len(nutrition_valid_generated),
                candidate_recipes_analyzed=result.stats.candidate_count,
                candidate_recipes_search_pool=len(active_search_recipes),
                legacy_candidates_added=max(
                    0,
                    len(search_validation.valid_recipes) - len(nutrition_valid_generated),
                ),
                candidate_recipes_rejected=(
                    len(generated_validation.rejected) + generated_nutrition.rejected_count
                ),
                candidate_recipes_structurally_valid=len(generated_validation.valid_recipes),
                candidate_recipes_nutrition_rejected=(generated_nutrition.rejected_count),
                candidate_batches=candidate_batch_statistics,
                beam_width=request.beam_width,
                max_stores=request.max_stores,
                states_evaluated=result.stats.states_evaluated,
                basket_cache_hits=result.stats.cache_hits,
                basket_cache_misses=result.stats.cache_misses,
                basket_calculations=result.stats.basket_calculations,
                basket_cache_hit_rate=result.stats.cache_hit_rate,
                estimated_savings_vs_legacy=savings,
                max_pairwise_recipe_similarity=(selected_culinary.max_similarity),
                timings_seconds=timings,
                timings_ms=performance.timings_ms if performance is not None else {},
                span_statistics=(
                    performance.span_statistics if performance is not None else {}
                ),
                operation_counters=(
                    performance.operation_counters if performance is not None else {}
                ),
                search_depth_counters=(
                    performance.depth_counters if performance is not None else {}
                ),
                diversity_mode=request.diversity_mode,
                diversity_score=selected_culinary.diversity_score,
                diversity_plan_states={
                    mode.value: option.states_evaluated for mode, option in diversity_plans.items()
                },
            ),
            legacy_comparison=legacy_comparison,
            quality=quality,
            surplus=surplus,
            store_tradeoff=store_tradeoff,
            plans=diversity_plans,
            diversity_plan_errors=diversity_plan_errors,
            debug_info=debug_info,
        )

    @traced_plan_call
    async def _build_with_provider(
        self,
        request: PlanRequest,
        provider: GroceryPriceProvider,
        inherited_warnings: list[str] | None = None,
    ) -> PlanResponse:
        started = perf_counter()
        warnings = list(inherited_warnings or [])
        pricing_context = UserPricingContext.from_chain_flags(
            normalized_memberships(
                request.pricing_memberships or None,
                use_member_prices=request.use_member_prices,
            )
        )
        if "diversity_mode" in request.model_fields_set:
            warnings.append(
                "diversity_mode tillämpas endast av optimized-strategin; "
                "legacy-strategin behåller sitt recipe-first-flöde och ekar "
                "endast det begärda läget för bakåtkompatibilitet."
            )
        stores = self._full_basket_stores(await provider.find_stores(request.postal_code))
        cheap_ingredients = await self.cheap_products.find(provider, stores)
        generator, recipe_source = self._recipe_generator()
        try:
            recipes = await self._generate_recipes(generator, cheap_ingredients, request)
        except Exception as exc:
            if not isinstance(generator, OpenAIRecipeGenerator):
                raise
            warnings.append(
                "OpenAI-receptgenereringen misslyckades; deterministiska exempelrecept "
                f"användes i stället ({type(exc).__name__})."
            )
            generator = MockRecipeGenerator()
            recipe_source = "mock-fallback"
            recipes = await self._generate_recipes(generator, cheap_ingredients, request)

        best = await self._evaluate(
            recipes,
            stores,
            provider,
            request.max_stores,
            pricing_context,
        )
        attempted = 0
        accepted = 0
        for _ in range(request.optimization_iterations):
            attempted += 1
            try:
                candidate_recipes = await asyncio.to_thread(
                    generator.improve_recipes,
                    best.recipes,
                    self._cost_feedback(best),
                    cheap_ingredients,
                    request.servings,
                )
            # Provider SDKs expose several unrelated operational exception
            # types. A failed optional improvement must never discard the
            # already verified plan.
            except Exception as exc:  # noqa: BLE001
                warnings.append(
                    "Förbättringsvarvet kunde inte genomföras; den verifierade planen "
                    f"behölls ({type(exc).__name__})."
                )
                break
            if [recipe.model_dump() for recipe in candidate_recipes] == [
                recipe.model_dump() for recipe in best.recipes
            ]:
                break
            try:
                candidate = await self._evaluate(
                    candidate_recipes,
                    stores,
                    provider,
                    request.max_stores,
                    pricing_context,
                )
            except (IncompleteBasketError, ValueError) as exc:
                warnings.append(
                    "Ett förbättringsförslag saknade en komplett verifierbar matkasse "
                    f"och förkastades ({exc})."
                )
                continue
            if _strict_price_improvement(
                candidate.optimized_basket,
                best.optimized_basket,
            ):
                best = candidate
                accepted += 1

        scenarios = await self._build_scenarios(best, stores)
        portions = len(best.recipes) * request.servings
        if (
            best.optimized_basket.verification_status
            == BasketVerificationStatus.VERIFIED_WITH_ESTIMATES
        ):
            warnings.append(
                "Matkassen är semantiskt verifierad men totalsumman innehåller "
                "uppskattade styck- eller variabelvikter."
            )
        elif best.optimized_basket.verification_status == BasketVerificationStatus.UNVERIFIED:
            warnings.append(
                "Matkassen innehåller okänd mängdmetadata och priset är inte verifierat som exakt."
            )
        data_source = str(getattr(provider, "source_name", provider.__class__.__name__))
        if data_source == "mock":
            warnings.insert(
                0,
                "Mockpriser används. De är realistisk exempeldata för Lund, inte aktuella "
                "butikspriser.",
            )
        location = str(
            getattr(provider, "location_name", None) or (stores[0].city if stores else "Lund")
        )
        total_runtime = perf_counter() - started
        record_performance_seconds("total_runtime", total_runtime)
        active_trace = current_performance_trace()
        performance = active_trace.snapshot() if active_trace is not None else None
        return PlanResponse(
            location=location,
            postal_code=request.postal_code,
            strategy="legacy",
            diversity_mode=request.diversity_mode,
            membership_programs_used=tuple(
                sorted(
                    {
                        item.membership_program
                        for group in best.optimized_basket.stores
                        for item in group.items
                        if item.membership_required
                        and item.membership_program is not None
                    },
                    key=lambda program: program.value,
                )
            ),
            recipes=best.recipes,
            ingredients=best.ingredients,
            cheap_ingredients=list(cheap_ingredients),
            single_store_options=best.single_store_options,
            optimized_basket=best.optimized_basket,
            optimization_scenarios=scenarios,
            portions=portions,
            price_per_portion=float(
                money(Decimal(str(best.optimized_basket.total)) / Decimal(portions))
            ),
            data_source=data_source,
            source_diagnostics=(self._source_diagnostics(provider) if request.debug else []),
            recipe_source=recipe_source,
            warnings=warnings,
            attribution_text=getattr(provider, "attribution_text", None),
            attribution_url=getattr(provider, "attribution_url", None),
            optimization_iterations_attempted=attempted,
            optimization_iterations_accepted=accepted,
            optimization=PlanOptimizationSummary(
                strategy="legacy",
                max_stores=request.max_stores,
                timings_seconds={"total_runtime": round(total_runtime, 4)},
                timings_ms=performance.timings_ms if performance is not None else {},
                span_statistics=(
                    performance.span_statistics if performance is not None else {}
                ),
                operation_counters=(
                    performance.operation_counters if performance is not None else {}
                ),
                search_depth_counters=(
                    performance.depth_counters if performance is not None else {}
                ),
            ),
        )

    async def create_plan(self, request: PlanRequest) -> PlanResponse:
        from app.services.complete_recipes import enabled, prepare_request
        if enabled(request):
            from app.services.personal_planner import PersonalPlanner
            from app.services.personal_policy import PolicyConflict
            prepared = self.price_universe_manager.get_for_request(request.postal_code, {}) if self.price_universe_manager else None
            if prepared is None:
                raise PolicyConflict("Lokalt publicerat prisunderlag saknas. Försök när prisunderlaget är tillgängligt.", code="DATA_BLOCKED")
            state = {"revision": 0, "profile": {}, "items": [], "reservations": {}, "events": {}, "ledger": []}
            request = prepare_request(request, self.settings)
            # The HTTP path supplies its owned pantry state before reaching this
            # method. Direct callers get an explicitly empty private workspace.
            return await asyncio.to_thread(lambda: PersonalPlanner(request, self.settings, prepared, state).create())
        strategy = self._strategy(request)
        if request.allowed_store_ids and strategy != "optimized":
            raise ValueError("Butiksval kräver den optimerade beräkningen.")
        if strategy == "legacy" and (
            request.diet_preference.value not in {"mixed", "meat_allowed"}
            or request.avoid_ingredients
        ):
            raise ValueError(
                "Kost- och ingrediensfilter kräver optimized-strategin."
            )
        # Serving an immutable artifact must not require live collector credentials
        # or a live OWN API. The builder still applies its normal freshness,
        # membership, purchase and nutrition gates to the prepared request view.
        prepared = (
            self.price_universe_manager.get_for_request(
                request.postal_code,
                normalized_memberships(
                    request.pricing_memberships or None,
                    use_member_prices=request.use_member_prices,
                ),
            )
            if strategy == "optimized" and self.price_universe_manager is not None
            else None
        )
        provider = (
            LocalPriceUniverseProvider(prepared.universe, prepared.stores)
            if prepared is not None
            else create_price_provider(
                self.settings,
                use_member_prices=request.use_member_prices or request.membership_price_policy == "all_advertised",
                memberships=request.pricing_memberships or None,
            )
        )
        builder = (
            self._build_optimized_with_provider
            if strategy == "optimized"
            else self._build_with_provider
        )
        try:
            return await builder(request, provider)
        except PriceProviderError:
            is_live = getattr(provider, "source_name", None) == "primat"
            if not (is_live and self.settings.allow_mock_fallback):
                raise
            # Restart the complete pipeline so no live and mock product rows can
            # ever coexist in the same response.
            mock = MockPriceProvider(use_member_prices=request.use_member_prices or request.membership_price_policy == "all_advertised")
            return await builder(
                request,
                mock,
                inherited_warnings=[
                    (
                        "Primat kunde inte användas. Hela planen räknades om med "
                        "tydligt märkt MockPriceProvider (providerfel; detaljer loggas inte)."
                    )
                ],
            )
        finally:
            close = getattr(provider, "aclose", None)
            if close is not None:
                await close()


__all__ = ["MealPlanService"]
