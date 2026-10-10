"""Offline-only mutation of saved plans.

Every candidate comes from the persisted response and therefore from the same
immutable source snapshots.  No provider or catalogue method is reachable
from this service.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from app.config import Settings
from app.errors import IncompleteBasketError
from app.models import (
    BasketItem,
    NormalizedIngredient,
    OptimizedBasket,
    OptimizedStoreGroup,
    PlanQualitySummary,
    PlanRequest,
    PlanResponse,
    ProductAlternative,
    ProductCandidate,
    QualityStatus,
    Recipe,
    RecipeCostSummary,
    Store,
    StoreTradeoff,
)
from app.models.basket import StoreBasket
from app.services.basket_calculator import money
from app.services.diet_policy import recipe_respects_diet
from app.services.meal_plan_optimizer import MealPlanService, _basket_selection_key
from app.services.price_universe_runtime import normalized_memberships
from app.services.recipe_candidate_validator import recipe_id

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def _all_basket_items(plan: PlanResponse) -> list[BasketItem]:
    result: list[BasketItem] = []
    result.extend(item for group in plan.optimized_basket.stores for item in group.items)
    result.extend(item for basket in plan.single_store_options for item in basket.items)
    for scenario in plan.optimization_scenarios:
        if scenario.basket is not None:
            result.extend(item for group in scenario.basket.stores for item in group.items)
    for option in plan.plans.values():
        result.extend(
            item
            for group in option.optimized_basket.stores
            for item in group.items
        )
    return result


def _pricing_context(request: PlanRequest) -> UserPricingContext:
    return UserPricingContext.from_chain_flags(
        normalized_memberships(
            request.pricing_memberships or None,
            use_member_prices=request.use_member_prices,
        )
    )


def product_alternatives(plan: PlanResponse, product_id: str) -> list[ProductAlternative]:
    selected = [
        item
        for group in plan.optimized_basket.stores
        for item in group.items
        if item.product_id == product_id
    ]
    if not selected:
        raise ValueError("product is not part of the selected basket")
    ingredient = selected[0].ingredient
    required_quantity = selected[0].required_quantity
    unit = selected[0].unit
    rows: dict[tuple[str, str], BasketItem] = {}
    for item in _all_basket_items(plan):
        if (
            item.ingredient == ingredient
            and item.unit == unit
            and abs(item.required_quantity - required_quantity) < 1e-6
            and item.product_id != product_id
        ):
            rows.setdefault((item.store_id, item.product_id), item)
    return [
        ProductAlternative(
            ingredient=item.ingredient,
            product_id=item.product_id,
            product_name=item.product_name,
            gtin=item.gtin,
            store_id=item.store_id,
            store_name=item.store_name,
            packages_needed=item.packages_needed,
            total_price=item.total_price,
            source_provider=(
                item.source_provenance.source_provider
                if item.source_provenance is not None
                else None
            ),
            source_snapshot_id=(
                item.source_provenance.source_snapshot_id
                if item.source_provenance is not None
                else None
            ),
        )
        for item in sorted(
            rows.values(),
            key=lambda row: (row.total_price, row.store_name.casefold(), row.product_name.casefold()),
        )
    ]


def _store_tradeoff(
    optimized: OptimizedBasket,
    single_store_options: Sequence[StoreBasket],
) -> StoreTradeoff:
    complete = [basket for basket in single_store_options if basket.is_complete]
    one_store = min(
        complete,
        key=lambda basket: (*_basket_selection_key(basket), basket.store_id),
        default=None,
    )
    one_store_total = one_store.total if one_store is not None else None
    return StoreTradeoff(
        one_store_total=one_store_total,
        selected_total=optimized.total,
        selected_store_count=optimized.store_count,
        extra_store_savings=(
            float(
                max(
                    Decimal(0),
                    money(
                        Decimal(str(one_store_total)) - Decimal(str(optimized.total))
                    ),
                )
            )
            if one_store_total is not None
            else 0
        ),
        one_store_names=[one_store.store_name] if one_store is not None else [],
        selected_store_names=[group.store_name for group in optimized.stores],
        one_store_verification_status=(
            one_store.verification_status if one_store is not None else None
        ),
        selected_verification_status=optimized.verification_status,
    )


def _allocated_recipe_costs(
    recipes: Sequence[Recipe],
    ingredients: Sequence[NormalizedIngredient],
    basket: OptimizedBasket,
    *,
    service: MealPlanService,
) -> list[RecipeCostSummary]:
    """Reallocate the repriced basket without inventing marginal economics."""

    item_by_key = {
        (item.ingredient, item.unit): item
        for group in basket.stores
        for item in group.items
    }
    total_required = {
        (str(ingredient.canonical_name), str(ingredient.unit)): Decimal(
            str(ingredient.required_quantity)
        )
        for ingredient in ingredients
    }
    allocated_rows: list[tuple[Recipe, Decimal]] = []
    for recipe in recipes:
        allocated = Decimal(0)
        for ingredient in service.normalizer.normalize_and_aggregate([recipe]):
            key = (ingredient.canonical_name, ingredient.unit)
            item = item_by_key.get(key)
            required = total_required.get(key)
            if item is None or not required:
                continue
            allocated += (
                money(item.total_price)
                * Decimal(str(ingredient.required_quantity))
                / required
            )
        allocated = money(allocated)
        allocated_rows.append((recipe, allocated))
    if allocated_rows:
        allocated_total = sum(
            (amount for _recipe, amount in allocated_rows),
            Decimal(0),
        )
        remainder = money(basket.total) - money(allocated_total)
        recipe, amount = allocated_rows[-1]
        allocated_rows[-1] = (recipe, money(amount + remainder))
    rows = [
        RecipeCostSummary(
            recipe_name=recipe.name,
            allocated_basket_cost=float(allocated),
            cost_per_portion=float(
                money(allocated / Decimal(recipe.servings))
            ),
        )
        for recipe, allocated in allocated_rows
    ]
    return rows


def replace_product(
    plan: PlanResponse,
    request: PlanRequest,
    *,
    product_id: str,
    replacement_product_id: str,
) -> PlanResponse:
    selected = [
        item
        for group in plan.optimized_basket.stores
        for item in group.items
        if item.product_id == product_id
    ]
    if len(selected) != 1:
        raise ValueError("selected product must identify exactly one basket row")
    current = selected[0]
    replacements = [
        item
        for item in _all_basket_items(plan)
        if item.product_id == replacement_product_id
        and item.ingredient == current.ingredient
        and item.unit == current.unit
        and abs(item.required_quantity - current.required_quantity) < 1e-6
    ]
    if not replacements:
        raise ValueError("replacement is not a compatible saved-snapshot alternative")
    replacement = min(replacements, key=lambda item: (item.total_price, item.store_id))

    groups: dict[str, tuple[str, list[BasketItem]]] = {
        group.store_id: (
            group.store_name,
            [item for item in group.items if item.product_id != product_id],
        )
        for group in plan.optimized_basket.stores
    }
    name, items = groups.get(replacement.store_id, (replacement.store_name, []))
    groups[replacement.store_id] = (name, [*items, replacement])
    rebuilt_groups = [
        OptimizedStoreGroup(
            store_id=store_id,
            store_name=name,
            items=sorted(items, key=lambda item: item.ingredient),
            subtotal=float(money(sum(Decimal(str(item.total_price)) for item in items))),
        )
        for store_id, (name, items) in sorted(groups.items())
        if items
    ]
    if len(rebuilt_groups) > request.max_stores:
        raise IncompleteBasketError("replacement would exceed max_stores")
    optimized = OptimizedBasket(
        total=float(money(sum(Decimal(str(group.subtotal)) for group in rebuilt_groups))),
        stores=rebuilt_groups,
        max_stores=request.max_stores,
        savings_vs_single_store=None,
    )
    service = MealPlanService(Settings())
    audit = service.basket_auditor.audit(
        plan.ingredients,
        optimized,
        user_pricing_context=_pricing_context(request),
    )
    if not audit.passed:
        raise IncompleteBasketError("replacement basket does not cover the saved recipes")
    warnings = [
        *plan.warnings,
        "Varan byttes och räknades om lokalt mot samma sparade prisunderlag.",
    ]
    return plan.model_copy(
        update={
            "optimized_basket": optimized,
            "recipe_costs": _allocated_recipe_costs(
                plan.recipes,
                plan.ingredients,
                optimized,
                service=service,
            ),
            "price_per_portion": float(
                money(Decimal(str(optimized.total)) / Decimal(plan.portions))
            ),
            "quality": (
                plan.quality.model_copy(update={"basket_audit": audit})
                if plan.quality is not None
                else None
            ),
            "surplus": service._surplus_summary(audit),
            "store_tradeoff": _store_tradeoff(optimized, plan.single_store_options),
            "warnings": list(dict.fromkeys(warnings)),
            "plans": {},
            "diversity_plan_errors": {},
            "debug_info": None,
        },
        deep=True,
    )


def _candidate_from_item(item: BasketItem) -> ProductCandidate:
    regular_unit = None if not item.ordinary_price_known else (
        item.regular_total_price / item.packages_needed
        if item.regular_total_price is not None
        else item.base_checkout_unit_price or item.unit_price
    )
    effective = item.base_checkout_unit_price or item.unit_price
    return ProductCandidate(
        product_id=item.product_id,
        product_name=item.product_name,
        canonical_name=item.ingredient,
        store_id=item.store_id,
        store_name=item.store_name,
        price=regular_unit,
        purchase_date=item.purchase_date,
        effective_price=effective,
        match_score=1.0,
        canonical_food=item.canonical_food,
        food_family=item.food_family,
        product_role=item.product_role,
        product_form=item.product_form,
        sale_model=item.sale_model,
        sale_price=item.sale_price or effective,
        sale_unit=item.sale_unit,
        comparison_price=item.comparison_price,
        comparison_unit=item.comparison_unit,
        piece_price=item.piece_price,
        estimated_piece_weight=item.estimated_piece_weight,
        estimated_piece_weight_unit=item.estimated_piece_weight_unit,
        package_quantity=item.package_quantity,
        package_unit=item.package_unit,
        usable_quantity=item.usable_quantity,
        usable_unit=item.usable_unit,
        quantity_confidence=item.quantity_confidence,
        variable_weight=item.variable_weight,
        semantic_confidence=item.semantic_confidence,
        semantic_evidence=item.semantic_evidence,
        offers=[item.applied_offer] if item.applied_offer is not None else [],
        selected_price_contract_id=item.price_contract_id,
        selected_price_eligibility=item.eligibility,
        selected_price_mechanism=item.price_mechanism,
        selected_membership_program=item.membership_program,
        category="saved-plan",
        chain=item.chain,
        gtin=item.gtin,
        price_context_type=item.price_context_type,
        coverage=item.coverage,
        source_provenance=item.source_provenance,
    )


def _saved_candidates(plan: PlanResponse) -> dict[str, list[ProductCandidate]]:
    rows: dict[str, dict[tuple[str, str], ProductCandidate]] = {}
    for item in _all_basket_items(plan):
        rows.setdefault(item.ingredient, {}).setdefault(
            (item.store_id, item.product_id),
            _candidate_from_item(item),
        )
    return {name: list(candidates.values()) for name, candidates in rows.items()}


def _saved_stores(plan: PlanResponse) -> list[Store]:
    result: dict[str, Store] = {}
    for item in _all_basket_items(plan):
        result.setdefault(
            item.store_id,
            Store(
                store_id=item.store_id,
                name=item.store_name,
                chain=(
                    item.chain
                    or (
                        item.source_provenance.chain
                        if item.source_provenance is not None
                        else None
                    )
                    or "unknown"
                ),
                city=plan.location,
                price_context_type=item.price_context_type,
                coverage=item.coverage,
                source_provenance=item.source_provenance,
            ),
        )
    return list(result.values())


def replacement_recipe_candidates(plan: PlanResponse) -> list[Recipe]:
    selected_ids = {recipe_id(recipe) for recipe in plan.recipes}
    rows: dict[str, Recipe] = {}
    for option in plan.plans.values():
        for recipe in option.recipes:
            identity = recipe_id(recipe)
            if identity not in selected_ids:
                rows.setdefault(identity, recipe)
    return sorted(rows.values(), key=lambda recipe: recipe.name.casefold())


async def replace_recipe(
    plan: PlanResponse,
    request: PlanRequest,
    *,
    recipe_index: int,
    replacement_recipe_name: str | None,
    settings: Settings,
) -> PlanResponse:
    if recipe_index >= len(plan.recipes):
        raise ValueError("recipe_index is outside the saved menu")
    candidates = replacement_recipe_candidates(plan)
    if replacement_recipe_name is not None:
        candidates = [
            recipe
            for recipe in candidates
            if recipe.name.casefold() == replacement_recipe_name.casefold()
        ]
    candidates = [
        recipe
        for recipe in candidates
        if recipe_respects_diet(
            recipe,
            preference=request.diet_preference,
            avoid_ingredients=request.avoid_ingredients,
        )
    ]
    if not candidates:
        raise ValueError("no compatible validated replacement recipe is saved")

    service = MealPlanService(settings)
    candidate_map = _saved_candidates(plan)
    stores = _saved_stores(plan)
    policy = service._diversity_policy_for(request, request.diversity_mode)
    last_error: Exception | None = None
    for replacement in candidates:
        recipes = list(plan.recipes)
        recipes[recipe_index] = replacement
        try:
            evaluated = service._evaluate_known_candidates(
                recipes,
                stores,
                candidate_map,
                request.max_stores,
            )
            nutrition = service._nutrition_for(request).validate_recipes(recipes)
            culinary = service._culinary_report(recipes)
            if not nutrition.is_valid or not service._culinary_policy_passes(culinary, policy):
                continue
            audit = service.basket_auditor.audit(
                evaluated.ingredients,
                evaluated.optimized_basket,
                user_pricing_context=_pricing_context(request),
            )
            quality = PlanQualitySummary(
                status=QualityStatus.PASS,
                basket_audit=audit,
                nutrition=service._nutrition_summary(nutrition),
                diversity=service._diversity_summary(culinary, policy),
            )
            scenarios = await service._build_scenarios(evaluated, stores)
            warnings = [
                *plan.warnings,
                "Receptet byttes och hela korgen räknades om lokalt mot samma sparade prisunderlag.",
            ]
            return plan.model_copy(
                update={
                    "recipes": recipes,
                    "ingredients": evaluated.ingredients,
                    "single_store_options": evaluated.single_store_options,
                    "optimized_basket": evaluated.optimized_basket,
                    "recipe_costs": _allocated_recipe_costs(
                        recipes,
                        evaluated.ingredients,
                        evaluated.optimized_basket,
                        service=service,
                    ),
                    "optimization_scenarios": scenarios,
                    "price_per_portion": float(
                        money(
                            Decimal(str(evaluated.optimized_basket.total))
                            / Decimal(plan.portions)
                        )
                    ),
                    "recipe_source": f"{plan.recipe_source}+saved-snapshot-replacement",
                    "quality": quality,
                    "surplus": service._surplus_summary(audit),
                    "store_tradeoff": _store_tradeoff(
                        evaluated.optimized_basket,
                        evaluated.single_store_options,
                    ),
                    "warnings": list(dict.fromkeys(warnings)),
                    "plans": {},
                    "diversity_plan_errors": {},
                    "legacy_comparison": None,
                    "debug_info": None,
                },
                deep=True,
            )
        except (IncompleteBasketError, ValueError) as exc:
            last_error = exc
    raise IncompleteBasketError(
        "no saved-snapshot replacement satisfied diet, nutrition, diversity and basket constraints"
    ) from last_error


__all__ = [
    "product_alternatives",
    "replace_product",
    "replace_recipe",
    "replacement_recipe_candidates",
]
