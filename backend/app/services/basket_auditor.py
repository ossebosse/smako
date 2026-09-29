"""Deterministic coverage audit for a complete weekly basket."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.models.basket import (
    BasketAuditItem,
    BasketAuditResult,
    BasketAuditSelectedProduct,
    BasketAuditStatus,
    BasketAuditUnitTotals,
    BasketItem,
    BasketVerificationStatus,
    OptimizedBasket,
    StoreBasket,
    worst_verification_status,
)
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    CanonicalUnit,
    ProductSemantics,
    QuantityConfidence,
    SemanticConfidence,
)
from app.services.basket_calculator import (
    resolve_fixed_checkout_price,
    validate_basket_purchase_limits,
)
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

from grocery_data.app.domain.counted_offer_checkout import uses_counted_offer_checkout
from grocery_data.app.domain.promotion_pricing import (
    PromotionEligibility,
    UserPricingContext,
)

DEFAULT_PANTRY_ITEMS = frozenset({"salt", "black_pepper", "water", "neutral_cooking_oil"})

_PANTRY_ALIASES = {
    "salt": "salt",
    "black pepper": "black_pepper",
    "black_pepper": "black_pepper",
    "svartpeppar": "black_pepper",
    "water": "water",
    "vatten": "water",
    "neutral cooking oil": "neutral_cooking_oil",
    "neutral_cooking_oil": "neutral_cooking_oil",
    "neutral matolja": "neutral_cooking_oil",
    "neutral olja": "neutral_cooking_oil",
}

_CENT = Decimal("0.01")
_CONFIDENCE_RANK = {
    QuantityConfidence.EXACT: 0,
    QuantityConfidence.DERIVED: 1,
    QuantityConfidence.ESTIMATED: 2,
    QuantityConfidence.UNKNOWN: 3,
}


@dataclass(slots=True)
class _Purchased:
    usable_quantity: Decimal = Decimal(0)
    total_price: Decimal = Decimal(0)
    quantity_confidence: QuantityConfidence = QuantityConfidence.EXACT
    quantity_reconciled: bool = True
    cost_reconciled: bool = True
    verification_statuses: list[BasketVerificationStatus] = field(default_factory=list)
    selected_products: list[BasketAuditSelectedProduct] = field(default_factory=list)


def _audit_canonical(value: str) -> str:
    canonical = canonicalize_ingredient_name(value)
    return _PANTRY_ALIASES.get(canonical, canonical)


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _basket_items(
    basket: OptimizedBasket | StoreBasket | Sequence[BasketItem],
) -> list[BasketItem]:
    if isinstance(basket, OptimizedBasket):
        return [item for group in basket.stores for item in group.items]
    if isinstance(basket, StoreBasket):
        return list(basket.items)
    return list(basket)


def _reconcile_basket_totals(
    basket: OptimizedBasket | StoreBasket | Sequence[BasketItem],
    items: Sequence[BasketItem],
) -> tuple[bool, Decimal, Decimal | None, list[str]]:
    """Reconcile presentation totals against the same concrete item costs."""

    calculated = _money(sum((_decimal(item.total_price) for item in items), Decimal(0)))
    if isinstance(basket, StoreBasket):
        reported = _money(_decimal(basket.total))
        errors = [] if reported == calculated else ["store total differs from selected item costs"]
        return not errors, calculated, reported, errors
    if isinstance(basket, OptimizedBasket):
        errors: list[str] = []
        for group in basket.stores:
            expected_subtotal = _money(
                sum((_decimal(item.total_price) for item in group.items), Decimal(0))
            )
            if _money(_decimal(group.subtotal)) != expected_subtotal:
                errors.append(f"store subtotal differs from item costs: {group.store_id}")
        reported = _money(_decimal(basket.total))
        reported_subtotals = _money(
            sum((_decimal(group.subtotal) for group in basket.stores), Decimal(0))
        )
        if reported != reported_subtotals:
            errors.append("basket total differs from store subtotals")
        if reported != calculated:
            errors.append("basket total differs from selected item costs")
        return not errors, calculated, reported, errors
    return True, calculated, None, []


class BasketAuditor:
    """Prove that purchased usable quantities cover aggregated requirements."""

    def __init__(
        self,
        pantry_items: Iterable[str] | None = None,
        resolver: PurchaseQuantityResolver | None = None,
    ) -> None:
        policy = DEFAULT_PANTRY_ITEMS if pantry_items is None else pantry_items
        self.pantry_items = frozenset(_audit_canonical(item) for item in policy)
        self.resolver = resolver or PurchaseQuantityResolver()

    @staticmethod
    def _semantics(item: BasketItem) -> ProductSemantics:
        return ProductSemantics(
            product_id=item.product_id,
            canonical_food=item.canonical_food,
            food_family=item.food_family,
            product_role=item.product_role,
            product_form=item.product_form,
            sale_model=item.sale_model,
            purchase_terms=item.purchase_terms,
            conditional_variant_choice=item.conditional_variant_choice,
            package_quantity=item.package_quantity,
            package_unit=item.package_unit,
            usable_quantity=item.usable_quantity,
            usable_unit=item.usable_unit,
            sale_price=item.sale_price or item.unit_price,
            sale_unit=item.sale_unit,
            comparison_price=item.comparison_price,
            comparison_unit=item.comparison_unit,
            piece_price=item.piece_price,
            estimated_piece_weight=item.estimated_piece_weight,
            estimated_piece_weight_unit=item.estimated_piece_weight_unit,
            semantic_confidence=item.semantic_confidence,
            quantity_confidence=item.quantity_confidence,
            variable_weight=item.variable_weight,
        )

    def is_pantry(self, ingredient_or_name: NormalizedIngredient | str) -> bool:
        """Return whether an ingredient belongs to this auditor's pantry policy."""

        name = (
            ingredient_or_name.canonical_name
            if isinstance(ingredient_or_name, NormalizedIngredient)
            else ingredient_or_name
        )
        return _audit_canonical(name) in self.pantry_items

    def audit(
        self,
        ingredients: Sequence[NormalizedIngredient],
        basket: OptimizedBasket | StoreBasket | Sequence[BasketItem],
        *,
        user_pricing_context: UserPricingContext | None = None,
        strategic_extras_allowed: bool = False,
    ) -> BasketAuditResult:
        concrete_items = _basket_items(basket)
        totals_reconciled, calculated_total, reported_total, total_errors = (
            _reconcile_basket_totals(basket, concrete_items)
        )
        authorization_errors: list[str] = []
        try:
            validate_basket_purchase_limits(concrete_items)
        except ValueError as exc:
            authorization_errors.append(str(exc))
        # Omitted request eligibility means no memberships or personal offers,
        # never "skip authorization". This keeps the auditor fail-closed for
        # direct/new callers as well as for the normal consumer pipeline.
        pricing_context = user_pricing_context or UserPricingContext()
        group_reconciled = {}
        if any(i.promotion_groups or i.group_applications or not i.ordinary_price_known for i in concrete_items):
            from app.services.basket_calculator import BasketCalculator

            try:
                priced = BasketCalculator.quote_group_basket(concrete_items)
                for actual, expected in zip(concrete_items, priced, strict=True):
                    group_reconciled[(actual.store_id, actual.ingredient)] = (
                        _money(_decimal(actual.total_price))
                        == _money(_decimal(expected.total_price))
                        and _money(_decimal(actual.unit_price))
                        == _money(_decimal(expected.unit_price))
                        and actual.group_applications == expected.group_applications
                    )
                    for application in expected.group_applications:
                        program = application["group"]["membership_program"]
                        if program and not pricing_context.has_membership(program):
                            authorization_errors.append("unauthorized promotion-group membership")
            except (ValueError, TypeError, KeyError):
                authorization_errors.append(
                    "promotion-group source or allocation cannot be verified"
                )
        for item in concrete_items:
            if item.applied_offer and item.applied_offer.price_basis_unit == 'kg':
                offer = item.applied_offer
                if (not item.purchase_terms or item.purchase_terms != offer.purchase_terms
                        or item.sale_unit != 'kg' or item.sale_price != offer.price
                        or not item.purchase_date or not offer.is_active(item.purchase_date)
                        or item.price_contract_id != offer.price_contract_id):
                    authorization_errors.append('weight-rate checkout differs from its source contract')
            if item.eligibility is PromotionEligibility.MEMBER:
                if item.membership_program is None or not pricing_context.has_membership(
                    item.membership_program
                ):
                    authorization_errors.append(
                        f"unauthorized member price: {item.store_id}/{item.product_id}"
                    )
            elif item.eligibility is PromotionEligibility.USER_SPECIFIC:
                authorization_errors.append(
                    "user-specific basket contract lacks a verified personal overlay: "
                    f"{item.store_id}/{item.product_id}"
                )
        total_errors.extend(authorization_errors)
        requirements: dict[tuple[str, CanonicalUnit], Decimal] = defaultdict(Decimal)
        pantry_requirements: dict[tuple[str, CanonicalUnit], Decimal] = defaultdict(Decimal)
        pantry_sources: dict[tuple[str, CanonicalUnit], list[str]] = defaultdict(list)

        for ingredient in ingredients:
            canonical = _audit_canonical(ingredient.canonical_name)
            key = (canonical, ingredient.unit)
            target = pantry_requirements if self.is_pantry(canonical) else requirements
            target[key] += _decimal(ingredient.required_quantity)
            if self.is_pantry(canonical):
                pantry_sources[key].extend(ingredient.source_recipes)

        purchased: dict[tuple[str, CanonicalUnit], _Purchased] = {}
        for item in concrete_items:
            canonical = _audit_canonical(item.ingredient)
            if self.is_pantry(canonical):
                continue
            key = (canonical, item.unit)
            row = purchased.setdefault(key, _Purchased())
            semantics = self._semantics(item)
            if (item.group_applications and group_reconciled.get((item.store_id, item.ingredient))
                    and semantics.purchase_terms):
                # Reconciled mixed variants meet the count jointly, not once
                # per variant. This does not authorize a standalone remainder.
                semantics = semantics.model_copy(update={'purchase_terms': semantics.purchase_terms.model_copy(
                    update={'complete_group_size':1})})
            quantity_for_resolution = item.required_quantity + (item.strategic_extra_quantity if strategic_extras_allowed else 0)
            if item.group_applications and group_reconciled.get((item.store_id, item.ingredient)):
                # Recompute purchased mass from the source pack size. Group
                # replay independently verifies the paid complete allocation.
                quantity_for_resolution = max(quantity_for_resolution, item.usable_quantity * item.packages_needed)
            resolution = self.resolver.resolve(
                semantics,
                required_quantity=quantity_for_resolution,
                required_unit=item.unit,
            )
            reconciliation_error: str | None = None
            reconciled = resolution.resolved
            cost_reconciled = resolution.resolved
            if resolution.resolved:
                assert resolution.packages_needed is not None
                assert resolution.purchased_quantity is not None
                assert resolution.purchased_unit is not None
                assert resolution.purchased_usable_quantity is not None
                assert resolution.usable_unit is not None
                comparisons = (
                    (float(resolution.purchased_quantity), item.purchased_quantity),
                    (
                        float(resolution.purchased_usable_quantity),
                        item.purchased_usable_quantity,
                    ),
                )
                reconciled = (
                    resolution.packages_needed == item.packages_needed
                    and resolution.purchased_unit == item.purchased_unit
                    and resolution.usable_unit == item.unit
                    and all(
                        abs(expected - actual) <= max(1e-6, abs(expected) * 1e-9)
                        for expected, actual in comparisons
                    )
                )
                if not reconciled:
                    reconciliation_error = "basket quantities differ from PurchaseQuantityResolver"
                if uses_counted_offer_checkout(item):
                    base_price = item.base_checkout_unit_price
                    if base_price is None:
                        cost_reconciled = False
                        reconciliation_error = "fixed checkout base price is missing"
                    elif item.promotion_groups or item.ungrouped_total_price is not None:
                        # Whole-basket replay above is authoritative. A group
                        # allocation is not an independently offered unit price.
                        cost_reconciled = group_reconciled.get((item.store_id, item.ingredient), False)
                    else:
                        expected_total, expected_unit_price, expected_offer, _ = (
                            resolve_fixed_checkout_price(
                                package_count=item.packages_needed,
                                base_unit_price=base_price,
                                regular_unit_price=(
                                    item.regular_unit_price if not item.ordinary_price_known else (item.regular_unit_price or item.sale_price or base_price)
                                ),
                                on_date=item.purchase_date,
                                offers=(item.applied_offer,)
                                if item.applied_offer is not None
                                else (),
                            )
                        )
                        cost_reconciled = (
                            _money(expected_total) == _money(_decimal(item.total_price))
                            and _money(expected_unit_price) == _money(_decimal(item.unit_price))
                            and expected_offer == item.applied_offer
                        )
                        if not cost_reconciled:
                            reconciliation_error = (
                                "basket fixed checkout differs from persisted checkout evidence"
                            )
                    if item.promotion_groups or item.ungrouped_total_price is not None:
                        cost_reconciled = group_reconciled.get(
                            (item.store_id, item.ingredient), False
                        )
                        reconciliation_error = (
                            None if cost_reconciled else "promotion-group checkout mismatch"
                        )
                else:
                    assert resolution.total_price is not None
                    cost_reconciled = _money(resolution.total_price) == _money(
                        _decimal(item.total_price)
                    )
                    if not cost_reconciled:
                        reconciliation_error = "basket cost differs from PurchaseQuantityResolver"
                available_quantity = resolution.purchased_usable_quantity
                confidence = resolution.quantity_confidence
                purchased_quantity = resolution.purchased_quantity
                purchased_unit = resolution.purchased_unit
            else:
                reconciliation_error = resolution.error or "purchase quantity unresolved"
                cost_reconciled = False
                available_quantity = Decimal(0)
                confidence = QuantityConfidence.UNKNOWN
                purchased_quantity = _decimal(item.purchased_quantity)
                purchased_unit = item.purchased_unit or item.unit

            row.usable_quantity += available_quantity
            row.total_price += _decimal(item.total_price)
            row.quantity_reconciled = row.quantity_reconciled and reconciled
            row.cost_reconciled = row.cost_reconciled and cost_reconciled
            item_verification = item.verification_status
            if not reconciled or not cost_reconciled:
                item_verification = BasketVerificationStatus.INVALID
            row.verification_statuses.append(item_verification)
            row.selected_products.append(
                BasketAuditSelectedProduct(
                    product_id=item.product_id,
                    product_name=item.product_name,
                    store_id=item.store_id,
                    store_name=item.store_name,
                    packages_needed=item.packages_needed,
                    usable_quantity=(
                        item.usable_quantity or float(available_quantity / item.packages_needed)
                    ),
                    usable_unit=item.usable_unit or item.unit,
                    purchased_quantity=float(purchased_quantity),
                    purchased_unit=purchased_unit,
                    purchased_usable_quantity=float(available_quantity),
                    quantity_confidence=confidence,
                    semantic_confidence=item.semantic_confidence,
                    sale_model=item.sale_model,
            purchase_terms=item.purchase_terms,
            conditional_variant_choice=item.conditional_variant_choice,
                    quantity_reconciled=reconciled,
                    cost_reconciled=cost_reconciled,
                    reconciliation_error=reconciliation_error,
                    total_price=item.total_price,
                )
            )
            if _CONFIDENCE_RANK[confidence] > _CONFIDENCE_RANK[row.quantity_confidence]:
                row.quantity_confidence = confidence

        audited: list[BasketAuditItem] = []
        all_keys = sorted(
            requirements.keys() | purchased.keys(),
            key=lambda key: (key[0], key[1]),
        )
        for canonical, unit in all_keys:
            required = requirements.get((canonical, unit), Decimal(0))
            purchase = purchased.get((canonical, unit), _Purchased())
            available = purchase.usable_quantity
            deficit = max(Decimal(0), required - available)
            surplus = max(Decimal(0), available - required)
            surplus_percent = (
                float((surplus * 100 / required).quantize(Decimal("0.01")))
                if required > 0
                else None
            )
            surplus_value = (
                _money(purchase.total_price * surplus / available)
                if available > 0 and surplus > 0
                else Decimal(0)
            )
            audited.append(
                BasketAuditItem(
                    canonical_name=canonical,
                    unit=unit,
                    status=(
                        BasketAuditStatus.FAIL
                        if (
                            deficit > 0
                            or not purchase.quantity_reconciled
                            or not purchase.cost_reconciled
                            or any(
                                product.semantic_confidence
                                in {
                                    SemanticConfidence.LOW,
                                    SemanticConfidence.REJECTED,
                                }
                                for product in purchase.selected_products
                            )
                        )
                        else BasketAuditStatus.PASS
                    ),
                    required_quantity=float(required),
                    purchased_usable_quantity=float(available),
                    deficit_quantity=float(deficit),
                    surplus_quantity=float(surplus),
                    surplus_percent=surplus_percent,
                    estimated_surplus_value=float(surplus_value),
                    quantity_confidence=(
                        purchase.quantity_confidence
                        if purchase.selected_products
                        else QuantityConfidence.UNKNOWN
                    ),
                    quantity_reconciled=purchase.quantity_reconciled,
                    cost_reconciled=purchase.cost_reconciled,
                    selected_products=sorted(
                        purchase.selected_products,
                        key=lambda product: (
                            product.store_id,
                            product.product_name.casefold(),
                            product.product_id,
                        ),
                    ),
                )
            )

        deficits = [row for row in audited if row.status == BasketAuditStatus.FAIL]
        unit_totals: list[BasketAuditUnitTotals] = []
        for unit in ("g", "ml", "st"):
            rows = [row for row in audited if row.unit == unit]
            if not rows:
                continue
            unit_totals.append(
                BasketAuditUnitTotals(
                    unit=unit,
                    required_quantity=sum(row.required_quantity for row in rows),
                    purchased_usable_quantity=sum(row.purchased_usable_quantity for row in rows),
                    deficit_quantity=sum(row.deficit_quantity for row in rows),
                    surplus_quantity=sum(row.surplus_quantity for row in rows),
                    estimated_surplus_value=float(
                        _money(
                            sum(
                                (_decimal(row.estimated_surplus_value) for row in rows),
                                Decimal(0),
                            )
                        )
                    ),
                )
            )

        pantry = [
            NormalizedIngredient(
                canonical_name=canonical,
                display_name=canonical,
                required_quantity=float(quantity),
                unit=unit,
                source_recipes=list(dict.fromkeys(pantry_sources[(canonical, unit)])),
            )
            for (canonical, unit), quantity in sorted(
                pantry_requirements.items(), key=lambda row: (row[0][0], row[0][1])
            )
        ]
        surplus_total = _money(
            sum(
                (_decimal(row.estimated_surplus_value) for row in audited),
                Decimal(0),
            )
        )
        container_verification = (
            basket.verification_status
            if isinstance(basket, (OptimizedBasket, StoreBasket))
            else BasketVerificationStatus.VERIFIED
        )
        verification_status = worst_verification_status(
            [
                container_verification,
                *(
                    status
                    for purchase in purchased.values()
                    for status in purchase.verification_statuses
                ),
            ]
        )
        if deficits or not totals_reconciled or authorization_errors:
            verification_status = BasketVerificationStatus.INVALID
        verification_warnings: list[str] = []
        if verification_status == BasketVerificationStatus.VERIFIED_WITH_ESTIMATES:
            verification_warnings.append(
                "Basket audit uses estimated piece or variable-package weights."
            )
        elif verification_status == BasketVerificationStatus.UNVERIFIED:
            verification_warnings.append("Basket audit contains unknown quantity metadata.")
        elif verification_status == BasketVerificationStatus.INVALID:
            verification_warnings.append(
                "Basket audit found a deficit, semantic rejection or quantity mismatch."
            )
        if not totals_reconciled:
            verification_warnings.append("Basket totals do not reconcile with selected item costs.")
        audit_failed = (
            bool(deficits)
            or bool(authorization_errors)
            or not totals_reconciled
            or container_verification == BasketVerificationStatus.INVALID
        )
        return BasketAuditResult(
            status=(BasketAuditStatus.FAIL if audit_failed else BasketAuditStatus.PASS),
            items=audited,
            pantry_items=pantry,
            deficits=deficits,
            unit_totals=unit_totals,
            estimated_surplus_value_total=float(surplus_total),
            verification_status=verification_status,
            verification_warnings=verification_warnings,
            totals_reconciled=totals_reconciled,
            calculated_total=float(calculated_total),
            reported_total=float(reported_total) if reported_total is not None else None,
            total_reconciliation_errors=total_errors,
        )


def audit_basket(
    ingredients: Sequence[NormalizedIngredient],
    basket: OptimizedBasket | StoreBasket | Sequence[BasketItem],
    *,
    pantry_items: Iterable[str] | None = None,
    user_pricing_context: UserPricingContext | None = None,
) -> BasketAuditResult:
    """Functional convenience wrapper."""

    return BasketAuditor(pantry_items=pantry_items).audit(
        ingredients,
        basket,
        user_pricing_context=user_pricing_context,
    )


__all__ = ["DEFAULT_PANTRY_ITEMS", "BasketAuditor", "audit_basket"]
