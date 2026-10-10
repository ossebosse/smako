"""Package-aware, deterministic purchase calculations."""

from __future__ import annotations

import functools
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, Decimal
from hashlib import sha256

from app.models.basket import BasketItem
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    CanonicalUnit,
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.provenance import SourceProvenance
from app.services.ingredient_normalizer import normalize_quantity
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

from grocery_data.app.domain.counted_offer_checkout import uses_counted_offer_checkout
from grocery_data.app.domain.promotion_pricing import (
    CheckoutPromotion,
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.services.fixed_checkout_price import (
    money as shared_money,
)
from grocery_data.app.services.fixed_checkout_price import (
    resolve_fixed_package_checkout,
)


class GroupPricingError(ValueError):
    """An explicit group contract cannot be priced and verified safely."""


def money(value: float | Decimal) -> Decimal:
    """Convert a monetary value to integer-cents precision."""

    return shared_money(value)


def resolve_fixed_checkout_price(
    *,
    package_count: int,
    base_unit_price: float | Decimal,
    regular_unit_price: float | Decimal | None,
    on_date: date | None = None,
    offers: Iterable[OfferMetadata] = (),
) -> tuple[Decimal, Decimal, OfferMetadata | None, str | None]:
    """Pure fixed-package checkout calculation shared by calculator and audit.

    ``base_unit_price`` is the already-eligible ordinary/campaign/member price
    for buying one package. Conditional multipacks are evaluated here because
    eligibility depends on the final package count. Persisting that base price
    lets :class:`BasketAuditor` independently repeat the same arithmetic rather
    than trusting a basket's stored total.
    """

    offer_rows = tuple(offers)
    references: dict[str, OfferMetadata] = {}
    normalized: list[CheckoutPromotion] = []
    for index, offer in enumerate(offer_rows):
        reference = offer.price_contract_id or f"basket-offer:{index:08d}"
        references[reference] = offer
        normalized.append(
            CheckoutPromotion(
                reference=reference,
                eligibility=offer.eligibility or PromotionEligibility.PUBLIC,
                mechanism=offer.mechanism or (
                    PromotionMechanism.MULTIBUY
                    if offer.kind is OfferKind.MULTIPACK
                    else PromotionMechanism.SALE_PRICE
                ),
                description=offer.description,
                price=Decimal(str(offer.price)),
                percent_discount=(
                    Decimal(str(offer.percent_discount))
                    if offer.percent_discount is not None
                    else None
                ),
                required_packages=offer.required_packages,
                max_quantity=offer.max_quantity,
                membership_program=offer.membership_program,
                member_program=offer.member_program,
                valid_from=offer.valid_from,
                valid_to=offer.valid_to,
                deposit=offer.deposit,
                campaign_evidence=offer.campaign_evidence,
            )
        )
    resolution = resolve_fixed_package_checkout(
        package_count=package_count,
        base_unit_price=base_unit_price,
        regular_unit_price=regular_unit_price,
        promotions=tuple(normalized),
        on_date=on_date,
    )
    applied = (
        references.get(resolution.applied_promotion.reference)
        if resolution.applied_promotion is not None
        else None
    )
    description = (
        applied.description
        if applied is not None
        else (
            "Kampanjpris"
            if regular_unit_price is not None and money(base_unit_price) < money(regular_unit_price)
            else None
        )
    )
    return resolution.checkout_total, resolution.displayed_unit_price, applied, description


def has_counted_weight_contract(product, offers):
    return bool(product.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE
        and product.package_unit == 'g' and product.package_quantity
        and product.sale_unit == 'kg' and product.purchase_terms is None
        and any(o.limit_unit == 'purchase_packages' and o.max_quantity is not None
                and o.price_basis_unit == 'kg' and o.required_packages == 1 and o.deposit is None for o in offers))


def resolve_counted_weight_checkout(product, offers, package_count, ordinary_package_price, on_date):
    """Use the existing integer-pack promotion resolver at source-estimated mass.

    The kg rate remains in the persisted contract. Only this request-local
    checkout projection converts it to a representative package price.
    """
    if not has_counted_weight_contract(product, offers):
        raise ValueError('Count cap lacks variable-package ordering evidence')
    factor = Decimal(str(product.package_quantity)) / 1000
    original = [o for o in offers if o.limit_unit == 'purchase_packages'
                and o.price_basis_unit == 'kg' and o.required_packages == 1 and o.deposit is None]
    projected = [o.model_copy(update={'price': float(money(Decimal(str(o.price))*factor)),
                    'price_basis_unit': 'package'}) for o in original]
    ordinary = money(ordinary_package_price)
    choices = [resolve_fixed_checkout_price(
        package_count=package_count, base_unit_price=base,
        regular_unit_price=ordinary, on_date=on_date, offers=projected)
        for base in sorted({ordinary, *(money(o.price) for o in projected if o.is_active(on_date) and money(o.price) < ordinary)})]
    total, unit_price, applied, description = min(choices, key=lambda x: (x[0], x[2].price_contract_id if x[2] else ''))
    return total, unit_price, original[projected.index(applied)] if applied else None, description


def _best_checkout_price(
    candidate: ProductCandidate, package_count: int
) -> tuple[Decimal, Decimal, OfferMetadata | None, str | None]:
    """Resolve a candidate's fixed checkout using its eligible base price."""

    return resolve_fixed_checkout_price(
        package_count=package_count,
        base_unit_price=candidate.effective_price,
        regular_unit_price=candidate.price,
        offers=candidate.offers,
        on_date=candidate.purchase_date,
    )


def _selected_offer_reference(
    candidate: ProductCandidate,
    offer: OfferMetadata,
) -> str:
    if offer.price_contract_id is not None:
        return offer.price_contract_id
    try:
        index = candidate.offers.index(offer)
    except ValueError:
        index = 0
    payload = (
        f"{candidate.store_id}|{candidate.product_id}|{index}|{offer.kind.value}|"
        f"{offer.price}|{offer.required_packages}|{offer.max_quantity or ''}|"
        f"{offer.valid_from or ''}|{offer.valid_to or ''}"
    )
    return f"price-contract:{sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def _fail_closed_non_fixed_price(
    candidate: ProductCandidate,
) -> tuple[ProductCandidate, str | None]:
    """Keep an unenforceable capped rate out of non-fixed checkout math.

    ``max_quantity`` has package/group semantics in the shared offer model.
    Weight, piece and variable-weight resolution currently have no verified
    way to translate that cap into the model's purchased quantity.  If one of
    their checkout-driving price fields is the price of an active capped
    single offer, applying it to the whole requested quantity would silently
    exceed the source condition.  Retain the offer as provenance metadata but
    quote the independently observed ordinary price instead.
    """

    if candidate.purchase_terms and candidate.purchase_terms.usage == 'estimated':
        if candidate.selected_price_contract_id is None or len(candidate.offers) != 1:
            raise ValueError('Weight campaign must pass request-time eligibility first')
        return candidate, None
    if uses_counted_offer_checkout(candidate) or has_counted_weight_contract(candidate, candidate.offers):
        return candidate, None

    checkout_prices = {
        money(value)
        for value in (
            candidate.sale_price,
            candidate.piece_price,
            candidate.effective_price,
        )
        if value is not None
    }
    if not checkout_prices:
        return candidate, None

    capped_prices = {
        money(offer.price)
        for offer in candidate.offers
        if offer.required_packages == 1
        and offer.max_quantity is not None
        and offer.kind in {OfferKind.CAMPAIGN, OfferKind.MEMBER}
        and offer.is_active()
    }
    unsafe_prices = checkout_prices & capped_prices
    if not unsafe_prices:
        return candidate, None

    # An equivalent active uncapped single offer independently authorises the
    # same checkout price, so the capped row alone must not suppress it.
    uncapped_prices = {
        money(offer.price)
        for offer in candidate.offers
        if offer.required_packages == 1
        and offer.max_quantity is None
        and offer.kind in {OfferKind.CAMPAIGN, OfferKind.MEMBER}
        and offer.is_active()
    }
    if unsafe_prices <= uncapped_prices:
        return candidate, None

    ordinary = float(money(candidate.price))
    updates: dict[str, float] = {
        "effective_price": ordinary,
        "sale_price": ordinary,
    }
    # A comparison rate can describe the same capped current promotion.  Only
    # discard it when it actually matches the unsafe price: a distinct
    # comparison rate is useful independent evidence of the ordinary rate.
    comparison_is_unsafe = (
        candidate.comparison_price is not None
        and money(candidate.comparison_price) in unsafe_prices
    )
    updates_with_nullable_rate: dict[str, object] = {
        **updates,
        "selected_price_contract_id": None,
        "selected_price_eligibility": PromotionEligibility.PUBLIC,
        "selected_price_mechanism": PromotionMechanism.REGULAR,
        "selected_membership_program": None,
    }
    if comparison_is_unsafe:
        updates_with_nullable_rate["comparison_price"] = None
        updates_with_nullable_rate["comparison_unit"] = None
    if candidate.sale_model == SaleModel.SOLD_BY_PIECE:
        updates_with_nullable_rate["piece_price"] = ordinary
    elif candidate.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE:
        # For a variable package ``price`` is the ordinary representative
        # package total, not necessarily a kg/l rate.  Removing the unsafe
        # sale-unit path lets an independent ordinary comparison rate win, or
        # otherwise falls back to that package total without changing units.
        updates_with_nullable_rate["sale_unit"] = None
    return (
        candidate.model_copy(update=updates_with_nullable_rate, deep=True),
        (
            "capped non-fixed offer retained as metadata but not applied because its cap unit "
            "is not safely modelled"
        ),
    )


def comparable_weight_rate(candidate: ProductCandidate) -> tuple[float, str] | None:
    """Quote a rate through the same quantity and cap guards as checkout.

    This is not a fixed package total or a promise about the final weighed bill.
    The caller has already applied membership, date and estimated-mode policy.
    """
    candidate, cap_warning = _fail_closed_non_fixed_price(candidate)
    if cap_warning:
        return None
    if candidate.sale_model not in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}:
        return None
    resolver = PurchaseQuantityResolver()
    rate = resolver._rate(candidate)
    if rate is None or rate[1] not in {'g', 'ml'}:
        return None
    if not resolver.resolve(candidate, required_quantity=1, required_unit=rate[1]).resolved:
        return None
    return float(rate[0] * Decimal(1000) / rate[2]), 'kg' if rate[1] == 'g' else 'l'


def calculate_packages(required_quantity: float, package_quantity: float) -> int:
    """Return the whole number of packages which must actually be bought."""

    required = Decimal(str(required_quantity))
    package = Decimal(str(package_quantity))
    if not required.is_finite() or required <= 0:
        raise ValueError("required_quantity must be greater than zero")
    if not package.is_finite() or package <= 0:
        raise ValueError("package_quantity must be greater than zero")
    return int((required / package).to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True, slots=True)
class BasketItemQuote:
    """Lightweight result used while comparing product and store alternatives.

    Menu search evaluates thousands of baskets.  Constructing a validated
    Pydantic ``BasketItem`` for every losing product in every losing store
    combination is unnecessary work.  A quote retains the exact checkout and
    tie-break values, and is materialised only when it belongs to a returned
    basket.
    """

    ingredient: str
    product_id: str
    product_name: str
    gtin: str | None
    chain: str | None
    price_context_type: str | None
    coverage: str | None
    store_id: str
    store_name: str
    match_score: float
    required_quantity: float
    unit: CanonicalUnit
    canonical_food: str | None
    food_family: str | None
    product_role: str | None
    product_form: str | None
    semantic_confidence: SemanticConfidence
    semantic_evidence: tuple[str, ...]
    sale_model: SaleModel
    sale_price: float
    sale_unit: str | None
    comparison_price: float | None
    comparison_unit: str | None
    piece_price: float | None
    estimated_piece_weight: float | None
    estimated_piece_weight_unit: CanonicalUnit
    package_quantity: float | None
    package_unit: CanonicalUnit | None
    usable_quantity: float | None
    usable_unit: CanonicalUnit | None
    quantity_confidence: QuantityConfidence
    variable_weight: bool
    packages_needed: int
    purchased_quantity: float
    purchased_unit: CanonicalUnit
    purchased_usable_quantity: float
    waste_quantity: float
    unit_price: Decimal
    base_checkout_unit_price: Decimal | None
    total_price: Decimal
    regular_total_price: Decimal | None
    regular_unit_price: Decimal | None
    purchase_date: date | None
    price_contract_id: str | None
    eligibility: PromotionEligibility
    price_mechanism: PromotionMechanism
    membership_program: MembershipProgram | None
    offer_description: str | None
    applied_offer: OfferMetadata | None
    resolution_warning: str | None
    source_provenance: SourceProvenance | None
    purchase_terms: object = None
    pending_group_checkout: bool = False
    conditional_variant_choice: bool = False
    purchase_units: bool = False
    checkout_offers: tuple = ()

    def to_basket_item(self) -> BasketItem:
        """Build the public, fully validated model for a selected quote."""

        return BasketItem(
            ingredient=self.ingredient,
            product_id=self.product_id,
            product_name=self.product_name,
            gtin=self.gtin,
            chain=self.chain,
            price_context_type=self.price_context_type,
            coverage=self.coverage,
            store_id=self.store_id,
            store_name=self.store_name,
            required_quantity=self.required_quantity,
            unit=self.unit,
            canonical_food=self.canonical_food,
            food_family=self.food_family,
            product_role=self.product_role,
            product_form=self.product_form,
            semantic_confidence=self.semantic_confidence,
            semantic_evidence=list(self.semantic_evidence),
            sale_model=self.sale_model,
            purchase_terms=self.purchase_terms,
            conditional_variant_choice=self.conditional_variant_choice,
            purchase_units=self.purchase_units,
            pending_group_checkout=self.pending_group_checkout,
            sale_price=self.sale_price,
            sale_unit=self.sale_unit,
            comparison_price=self.comparison_price,
            comparison_unit=self.comparison_unit,
            piece_price=self.piece_price,
            estimated_piece_weight=self.estimated_piece_weight,
            estimated_piece_weight_unit=self.estimated_piece_weight_unit,
            package_quantity=self.package_quantity,
            package_unit=self.package_unit,
            usable_quantity=self.usable_quantity,
            usable_unit=self.usable_unit,
            quantity_confidence=self.quantity_confidence,
            variable_weight=self.variable_weight,
            packages_needed=self.packages_needed,
            purchased_quantity=self.purchased_quantity,
            purchased_unit=self.purchased_unit,
            purchased_usable_quantity=self.purchased_usable_quantity,
            waste_quantity=self.waste_quantity,
            unit_price=float(self.unit_price),
            regular_unit_price=float(self.regular_unit_price) if self.regular_unit_price is not None else None,
            ordinary_price_known=self.regular_unit_price is not None,
            purchase_date=self.purchase_date,
            price_contract_id=self.price_contract_id,
            eligibility=self.eligibility,
            price_mechanism=self.price_mechanism,
            membership_program=self.membership_program,
            base_checkout_unit_price=(
                float(self.base_checkout_unit_price)
                if self.base_checkout_unit_price is not None
                else None
            ),
            total_price=float(self.total_price),
            regular_total_price=float(self.regular_total_price) if self.regular_total_price is not None else None,
            purchase_warning=self.resolution_warning,
            offer_description=self.offer_description,
            applied_offer=self.applied_offer,
            checkout_offers=self.checkout_offers or ((self.applied_offer,) if self.applied_offer and self.regular_unit_price is None else ()),
            source_provenance=self.source_provenance,
        )


def validate_purchase_unit_limit(item, package_count: int) -> None:
    """Validate a source sales-unit cap separately from discount calculations."""
    provenance = item.source_provenance
    limit = provenance.maximum_purchase_units if provenance is not None else None
    if limit is None:
        return
    if item.sale_model not in {
        SaleModel.FIXED_PACKAGE, SaleModel.SOLD_BY_PIECE, SaleModel.VARIABLE_WEIGHT_PACKAGE,
    }:
        raise ValueError("source purchase-unit limit requires a verified count of sales units")
    if package_count > limit:
        raise ValueError(f"source purchase-unit limit exceeded: {package_count} > {limit}")


def validate_basket_purchase_limits(items) -> None:
    """A repeated exact product consumes the same cart limit across aliases."""
    quantities = {}
    for item in items:
        key = (item.store_id, item.product_id)
        quantities[key] = quantities.get(key, 0) + item.packages_needed
    for item in items:
        validate_purchase_unit_limit(item, quantities[(item.store_id, item.product_id)])


class BasketCalculator:
    """Calculate package count, checkout cost and surplus for one ingredient."""

    def __init__(self, resolver: PurchaseQuantityResolver | None = None) -> None:
        self.resolver = resolver or PurchaseQuantityResolver()

    @staticmethod
    def quote_group_basket(items):
        """Exact disjoint allocation of source-defined groups over NEW packages.

        Residual packages use the existing checkout resolver. A group consumes
        its units before any single-product promotion is evaluated. This avoids
        stacking or counting pantry/history. Single-group completion can add
        explicit whole packages of an already selected variant.
        """

        validate_basket_purchase_limits(items)
        household_caps = {}
        for item in items:
            offer = item.applied_offer
            if (offer and offer.price_contract_id and (offer.price_contract_id.startswith(("coop:household:", "lidl:household:", "willys:household:")) or offer.limit_unit == "purchase_packages" or (offer.purchase_terms and offer.purchase_terms.limit_scope == "household_campaign"))
                    and offer.max_quantity is not None):
                used, cap = household_caps.get(offer.price_contract_id, (0, offer.max_quantity))
                # Source cap counts complete purchase groups; single-price
                # contracts have required_packages=1. Different local prices
                # stay on their own items. The stricter observed cap wins.
                units = (item.packages_needed + offer.required_packages - 1) // offer.required_packages
                used += min(units, offer.max_quantity) if offer.limit_unit == "purchase_packages" else units
                cap = min(cap, offer.max_quantity)
                household_caps[offer.price_contract_id] = used, cap
                if used > cap:
                    raise GroupPricingError("Coop household campaign limit exceeded across physical stores/aliases")
        # Weight/piece lines have already been quoted by their own purchase
        # resolver. An offers-only package elsewhere in the basket must not
        # send those lines through fixed-package residual pricing.
        fixed = [item for item in items if uses_counted_offer_checkout(item)]
        if len(fixed) != len(items):
            if any(item.promotion_groups for item in items if not uses_counted_offer_checkout(item)):
                raise GroupPricingError("Promotion groups require fixed-package purchase evidence")
            if not fixed:
                return list(items)
            quoted = iter(BasketCalculator.quote_group_basket(fixed))
            return [next(quoted) if uses_counted_offer_checkout(item) else item for item in items]
        groups = {}
        for item in items:
            for group in item.promotion_groups:
                provenance = item.source_provenance
                if (
                    group.store_id != item.store_id
                    or group.chain != item.chain
                    or item.product_id not in group.eligible_product_ids
                    or not provenance
                    or group.source_snapshot_id != provenance.source_snapshot_id
                    or group.source != provenance.source_provider
                ):
                    raise GroupPricingError("Promotion group lacks exact product/context/source evidence")
                if item.purchase_date and not group.valid_from <= item.purchase_date <= group.valid_to:
                    raise GroupPricingError("Promotion group is outside its verified campaign dates")
                key = (group.store_id, group.group_id)
                if key in groups and groups[key] != group:
                    raise GroupPricingError("Conflicting source promotion group definitions")
                groups[key] = group
        contracts = tuple(groups[k] for k in sorted(groups))
        if contracts and any(o.deposit for item in items for o in item.checkout_offers
                             if any(g.store_id == item.store_id and item.product_id in g.eligible_product_ids for g in contracts)):
            raise GroupPricingError("Kampanjgruppens pantinkludering saknar belägg; varupriserna bevaras.")
        if not contracts and all(i.ordinary_price_known for i in items):
            return list(items)
        if any(g.pricing_rule != "fixed_total" and any(
            not i.ordinary_price_known for i in items
            if i.store_id == g.store_id and i.product_id in g.eligible_product_ids
        ) for g in contracts):
            raise GroupPricingError("group discounts require independent ordinary price evidence")
        counts = tuple(i.packages_needed for i in items)
        # Bound recursion as well as the number of searched states. Large
        # explicit baskets must fail with the same safe policy response.
        if sum(counts) > 500:
            raise GroupPricingError("Kampanjgrupper kan verifieras för högst 500 köpta förpackningar per korg.")
        base = tuple(
            Decimal(str(i.regular_unit_price or i.base_checkout_unit_price or 1)) for i in items
        )

        @functools.cache
        def residual_quote(index, count):
            item = items[index]
            return resolve_fixed_checkout_price(
                package_count=count,
                base_unit_price=item.base_checkout_unit_price,
                regular_unit_price=item.regular_unit_price,
                on_date=item.purchase_date,
                offers=item.checkout_offers,
            )

        def residual(index, count):
            return money(residual_quote(index, count)[0]) if count else Decimal(0)

        same_products = {}
        for i, item in enumerate(items):
            identity = (item.store_id, item.product_id)
            same_products.setdefault(identity, []).append(i)
        for indices in same_products.values():
            first = items[indices[0]]
            if any((items[i].checkout_offers, items[i].regular_unit_price,
                    items[i].base_checkout_unit_price) !=
                   (first.checkout_offers, first.regular_unit_price, first.base_checkout_unit_price)
                   for i in indices):
                raise GroupPricingError("Conflicting checkout evidence for identical product")

        @functools.cache
        def residual_rows(remaining):
            costs = [Decimal(0)] * len(items)
            for indices in same_products.values():
                count = sum(remaining[i] for i in indices)
                if not count:
                    continue
                total = residual(indices[0], count)
                assigned = Decimal(0)
                active = [i for i in indices if remaining[i]]
                for offset, i in enumerate(active):
                    cost = total - assigned if offset == len(active) - 1 else min(
                        total - assigned, money(total * remaining[i] / count))
                    costs[i] = cost
                    assigned += cost
            return tuple(costs)

        def allocations(remaining, indices, needed, offset=0, prefix=()):
            if offset == len(indices):
                if needed == 0:
                    vector = [0] * len(items)
                    for index, amount in zip(indices, prefix, strict=True):
                        vector[index] = amount
                    yield tuple(vector)
                return
            index = indices[offset]
            for amount in range(min(needed, remaining[index]) + 1):
                yield from allocations(
                    remaining, indices, needed - amount, offset + 1, (*prefix, amount)
                )

        states = 0
        limit_keys = tuple((g.chain, g.limit_key) if g.limit_scope == 'household_campaign'
                           else (g.store_id, g.group_id) for g in contracts)
        shared_caps = {key: min(g.max_groups for g, k in zip(contracts, limit_keys, strict=True)
                               if k == key and g.max_groups is not None)
                       for key in set(limit_keys)
                       if any(k == key and g.max_groups is not None for g, k in zip(contracts, limit_keys, strict=True))}

        @functools.cache
        def solve(remaining, used):
            nonlocal states
            states += 1
            if states > 100000:
                raise GroupPricingError("Kampanjkombinationen är för stor för verifierad exakt beräkning.")
            try:
                best = (sum(residual_rows(remaining), Decimal(0)), ())
            except ValueError:
                best = (Decimal('Infinity'), ())  # No separately evidenced residual purchase.
            for index, group in enumerate(contracts):
                cap = shared_caps.get(limit_keys[index])
                if cap is not None and sum(v for v, k in zip(used, limit_keys, strict=True) if k == limit_keys[index]) >= cap:
                    continue
                eligible = [
                    i
                    for i, item in enumerate(items)
                    if remaining[i]
                    and item.store_id == group.store_id
                    and item.product_id in group.eligible_product_ids
                ]
                if sum(remaining[i] for i in eligible) < group.required_packages:
                    continue
                for vector in allocations(remaining, eligible, group.required_packages):
                    ordinary = sum((base[i] * n for i, n in enumerate(vector)), Decimal(0))
                    cost = (
                        money(group.amount)
                        if group.pricing_rule == "fixed_total"
                        else money(max(Decimal(0), ordinary - Decimal(str(group.amount))))
                    )
                    next_used = tuple(v + (i == index) for i, v in enumerate(used))
                    rest_cost, rest_path = solve(
                        tuple(a - b for a, b in zip(remaining, vector, strict=True)), next_used
                    )
                    candidate = (cost + rest_cost, ((index, vector, cost), *rest_path))
                    if candidate[0] < best[0]:
                        best = candidate
            return best

        total, path = solve(counts, (0,) * len(contracts))
        if not total.is_finite():
            # Complete a single evidenced mix with whole packages of an
            # already selected variant. No residual price or new identity.
            if len(contracts) == 1:
                group = contracts[0]
                if (group.pricing_rule == 'fixed_total'
                        and all(i.store_id == group.store_id and i.product_id in group.eligible_product_ids for i in items)):
                    missing = (-sum(counts)) % group.required_packages
                    complete_count = (sum(counts) + missing) // group.required_packages
                    if missing and (group.max_groups is None or complete_count <= group.max_groups):
                        current = items[0]  # stable, explicitly selected variant
                        count = current.packages_needed + missing
                        gross = current.package_quantity * count
                        usable = current.usable_quantity * count
                        completed = current.model_copy(update={
                            'packages_needed': count, 'purchased_quantity': gross,
                            'purchased_usable_quantity': usable, 'waste_quantity': usable-current.required_quantity,
                            'purchase_warning': 'Helt flerköp: extra hela förpackningar av denna identifierade variant ingår; separat restpris saknas.'})
                        return BasketCalculator.quote_group_basket([completed, *items[1:]])
            raise GroupPricingError("Hela kampanjgrupper krävs; separat restpris saknas.")
        remaining = list(counts)
        charges = [Decimal(0)] * len(items)
        audits = [[] for _ in items]
        for sequence, (index, vector, cost) in enumerate(path):
            group = contracts[index]
            ordinary = sum((base[i] * n for i, n in enumerate(vector)), Decimal(0))
            contributors = [i for i, n in enumerate(vector) if n]
            assigned = Decimal(0)
            contribution_rows = []
            for offset, i in enumerate(contributors):
                charge = (
                    cost - assigned
                    if offset == len(contributors) - 1
                    else min(cost - assigned, money(cost * base[i] * vector[i] / ordinary))
                )
                assigned += charge
                charges[i] += charge
                remaining[i] -= vector[i]
                contribution_rows.append(
                    {
                        "ingredient": items[i].ingredient,
                        "product_id": items[i].product_id,
                        "product_name": items[i].product_name,
                        "packages": vector[i],
                        "charge": float(charge),
                    }
                )
            audit = {
                "application": sequence + 1,
                "group": group.model_dump(mode="json"),
                "total": float(cost),
                "contributors": contribution_rows,
            }
            for i in contributors:
                audits[i].append(audit)
        result = []
        residual_costs = residual_rows(tuple(remaining))
        for i, item in enumerate(items):
            charged = money(charges[i] + residual_costs[i])
            identical = same_products[(item.store_id, item.product_id)]
            residual_count = sum(remaining[j] for j in identical)
            offer = residual_quote(identical[0], residual_count)[2] if remaining[i] else None
            program = next((contracts[index].membership_program for index, vector, _ in path
                            if vector[i] and contracts[index].membership_program), None)
            program = program or (offer.membership_program if offer else None)
            result.append(
                item.model_copy(
                    update={
                        "pending_group_checkout": False,
                        "total_price": float(charged),
                        "unit_price": float(money(charged / item.packages_needed)),
                        "group_applications": audits[i],
                        "group_residual_packages": remaining[i],
                        "group_residual_total": float(residual_costs[i]),
                        "applied_offer": offer,
                        "price_contract_id": ("group-checkout:" + sha256(json.dumps(audits[i], sort_keys=True).encode()).hexdigest()) if audits[i] else offer.price_contract_id if offer else None,
                        "membership_program": program,
                        "eligibility": PromotionEligibility.MEMBER if program else PromotionEligibility.PUBLIC,
                        "price_mechanism": PromotionMechanism.MULTIBUY if audits[i] else
                        offer.mechanism if offer else PromotionMechanism.REGULAR,
                        "ungrouped_total_price": item.ungrouped_total_price
                        if item.ungrouped_total_price is not None
                        else item.total_price,
                    }
                )
            )
        assert money(sum(Decimal(str(i.total_price)) for i in result)) == money(total)
        return result

    def quote_item(
        self,
        ingredient: NormalizedIngredient,
        candidate: ProductCandidate,
        *, defer_group_checkout: bool = False,
    ) -> BasketItemQuote:
        """Calculate an exact checkout quote without Pydantic materialisation."""

        required_quantity, required_unit = normalize_quantity(
            ingredient.required_quantity, ingredient.unit
        )
        if candidate.purchase_terms and (candidate.purchase_terms.usage == 'blocked' or (candidate.purchase_terms.usage == 'variant_selection_required' and not candidate.conditional_variant_choice)):
            raise ValueError('Unresolved purchase evidence: ' + candidate.purchase_terms.usage)
        checkout_candidate, capped_offer_warning = _fail_closed_non_fixed_price(candidate)
        quantity_candidate = checkout_candidate
        if (uses_counted_offer_checkout(checkout_candidate)
                and checkout_candidate.sale_price is None and checkout_candidate.price is None
                and checkout_candidate.offers):
            # Quantity resolution still takes a numerical cost signal. Keep it
            # local: the authoritative fixed checkout below must cover the
            # actual package count and the public item retains sale_price=None.
            quantity_candidate = checkout_candidate.model_copy(update={
                "sale_price": checkout_candidate.effective_price,
                "piece_price": checkout_candidate.effective_price if checkout_candidate.sale_model == SaleModel.SOLD_BY_PIECE else checkout_candidate.piece_price})
        if defer_group_checkout:
            if not checkout_candidate.promotion_groups or checkout_candidate.sale_model != SaleModel.FIXED_PACKAGE:
                raise ValueError('Deferred checkout requires a source-bound fixed-package campaign group')
            # Quantity only: the whole-basket group solver must authorize cost.
            # This request-local projection never changes the source offer.
            if quantity_candidate.purchase_terms:
                quantity_candidate = quantity_candidate.model_copy(update={
                    'purchase_terms': quantity_candidate.purchase_terms.model_copy(update={'complete_group_size':1})})
        resolution = self.resolver.resolve(
            quantity_candidate,
            required_quantity=required_quantity,
            required_unit=required_unit,
        )
        if not resolution.resolved:
            prefix = (
                "Incompatible units"
                if resolution.error and resolution.error.startswith("incompatible")
                else "Unresolved purchase quantity"
            )
            raise ValueError(
                f"{prefix} for {ingredient.canonical_name}: {resolution.error or 'unknown reason'}"
            )
        if any(
            value is None
            for value in (
                resolution.packages_needed,
                resolution.purchased_quantity,
                resolution.purchased_unit,
                resolution.purchased_usable_quantity,
                resolution.usable_unit,
                resolution.waste_quantity,
                resolution.unit_price,
                resolution.total_price,
            )
        ):
            raise ValueError("resolved purchase is missing required quantities or cost")

        required = resolution.required_quantity
        package_count = resolution.packages_needed
        purchased = resolution.purchased_quantity
        purchased_unit = resolution.purchased_unit
        purchased_usable = resolution.purchased_usable_quantity
        usable_unit = resolution.usable_unit
        waste = resolution.waste_quantity
        assert package_count is not None
        assert purchased is not None and purchased_unit is not None
        assert purchased_usable is not None and usable_unit is not None
        assert waste is not None
        validate_purchase_unit_limit(checkout_candidate, package_count)

        applied_offer: OfferMetadata | None = None
        offer_description: str | None = None
        base_checkout_unit_price: Decimal | None = None
        if uses_counted_offer_checkout(checkout_candidate):
            base_checkout_unit_price = money(checkout_candidate.effective_price)
            if defer_group_checkout:
                total, unit_price = resolution.total_price, resolution.unit_price
            else:
                total, unit_price, applied_offer, offer_description = _best_checkout_price(
                    checkout_candidate, package_count
                )
            regular_total = money(money(checkout_candidate.price) * package_count) if checkout_candidate.price is not None else None
        else:
            # The resolver is the source of truth for piece, weight and
            # variable-package prices. In particular, a piece product may
            # carry a current ``piece_price`` which differs from the provider's
            # legacy package/effective-price fields. Routing it through the
            # fixed-package checkout path would silently charge the wrong
            # amount (for example 3 pieces at 5 kr instead of 3 kr).
            total = resolution.total_price
            unit_price = resolution.unit_price
            assert total is not None and unit_price is not None
            regular_total = (
                money(money(checkout_candidate.price) * package_count)
                if checkout_candidate.sale_model == SaleModel.SOLD_BY_PIECE
                else total
            )

        if has_counted_weight_contract(checkout_candidate, checkout_candidate.offers):
            base_checkout_unit_price = money(Decimal(str(checkout_candidate.price))*Decimal(str(checkout_candidate.package_quantity))/1000)
            total, unit_price, applied_offer, offer_description = resolve_counted_weight_checkout(
                checkout_candidate, checkout_candidate.offers, package_count,
                base_checkout_unit_price, checkout_candidate.purchase_date)
            regular_total = money(Decimal(str(checkout_candidate.price)) * purchased / 1000)

        if checkout_candidate.purchase_terms and checkout_candidate.purchase_terms.usage == 'estimated':
            applied_offer = checkout_candidate.offers[0]
            if not applied_offer.is_active(checkout_candidate.purchase_date):
                raise ValueError('Expired weight offer')
            if applied_offer.max_quantity is not None and package_count > applied_offer.max_quantity:
                raise ValueError('Weight-package campaign purchase limit exceeded')
            offer_description = applied_offer.description
            regular_total = None if checkout_candidate.price is None else regular_total

        resolution_warning = ("Villkorat kampanjval: välj en kampanjmärkt variant. Innehåll, allergener och näring är inte verifierade. " + "; ".join(checkout_candidate.purchase_terms.exclusions)) if checkout_candidate.conditional_variant_choice else resolution.warning
        if checkout_candidate.purchase_units:
            resolution_warning = "Köpförpackningar med okänd innehållsmängd. Ingen gram-/literjämförelse eller näringsberäkning. Verifiera innehållsmängden före bokföring i skafferiet."
        if has_counted_weight_contract(checkout_candidate, checkout_candidate.offers):
            resolution_warning = (f"Uppskattad förpackningsvikt. Rabatten gäller högst {applied_offer.max_quantity if applied_offer else 0} förpackningar; "
                f"övriga beräknas med belagt ordinarie pris {checkout_candidate.price:g} kr/kg. Slutbeloppet beror på verklig vikt.")
        if capped_offer_warning is not None:
            resolution_warning = (
                f"{resolution_warning}; {capped_offer_warning}"
                if resolution_warning
                else capped_offer_warning
            )

        basket_usable_quantity = checkout_candidate.usable_quantity
        basket_usable_unit = checkout_candidate.usable_unit
        if checkout_candidate.sale_model == SaleModel.SOLD_BY_PIECE:
            # A piece product may expose its source package in grams while the
            # recipe asks for pieces (or vice versa via estimated piece weight).
            # The resolver has already proved the conversion and returns the
            # purchased usable amount in the requirement's canonical unit.
            # Project that per-piece result into the public basket contract;
            # copying the source unit can create an internally inconsistent
            # BasketItem even though the purchase resolution itself is valid.
            basket_usable_quantity = float(purchased_usable / package_count)
            basket_usable_unit = usable_unit

        selected_contract_id = ("pending-group:" + ":".join(g.group_id for g in checkout_candidate.promotion_groups)) if defer_group_checkout else checkout_candidate.selected_price_contract_id
        selected_eligibility = checkout_candidate.selected_price_eligibility
        selected_mechanism = checkout_candidate.selected_price_mechanism
        selected_membership = checkout_candidate.selected_membership_program
        if applied_offer is not None:
            selected_contract_id = _selected_offer_reference(
                checkout_candidate,
                applied_offer,
            )
            selected_eligibility = applied_offer.eligibility or PromotionEligibility.PUBLIC
            selected_mechanism = applied_offer.mechanism or (
                PromotionMechanism.MULTIBUY
                if applied_offer.kind is OfferKind.MULTIPACK
                else PromotionMechanism.SALE_PRICE
            )
            selected_membership = applied_offer.membership_program

        return BasketItemQuote(
            ingredient=ingredient.canonical_name,
            product_id=candidate.product_id,
            product_name=candidate.product_name,
            gtin=candidate.gtin,
            chain=candidate.chain,
            price_context_type=candidate.price_context_type,
            coverage=candidate.coverage,
            store_id=candidate.store_id,
            store_name=candidate.store_name,
            match_score=candidate.match_score,
            required_quantity=float(required),
            unit=required_unit,
            canonical_food=candidate.canonical_food,
            food_family=candidate.food_family,
            product_role=candidate.product_role,
            product_form=candidate.product_form,
            semantic_confidence=candidate.semantic_confidence,
            semantic_evidence=tuple(candidate.semantic_evidence),
            sale_model=checkout_candidate.sale_model,
            purchase_terms=checkout_candidate.purchase_terms,
            conditional_variant_choice=checkout_candidate.conditional_variant_choice,
            purchase_units=checkout_candidate.purchase_units,
            pending_group_checkout=defer_group_checkout,
            sale_price=checkout_candidate.sale_price,
            sale_unit=checkout_candidate.sale_unit,
            comparison_price=checkout_candidate.comparison_price,
            comparison_unit=checkout_candidate.comparison_unit,
            piece_price=checkout_candidate.piece_price,
            estimated_piece_weight=checkout_candidate.estimated_piece_weight,
            estimated_piece_weight_unit=checkout_candidate.estimated_piece_weight_unit,
            package_quantity=checkout_candidate.package_quantity,
            package_unit=checkout_candidate.package_unit,
            usable_quantity=basket_usable_quantity,
            usable_unit=basket_usable_unit,
            quantity_confidence=resolution.quantity_confidence,
            variable_weight=checkout_candidate.variable_weight,
            packages_needed=package_count,
            purchased_quantity=float(purchased),
            purchased_unit=purchased_unit,
            purchased_usable_quantity=float(purchased_usable),
            waste_quantity=float(waste),
            unit_price=unit_price,
            base_checkout_unit_price=base_checkout_unit_price,
            total_price=total,
            regular_total_price=regular_total,
            regular_unit_price=base_checkout_unit_price if has_counted_weight_contract(checkout_candidate, checkout_candidate.offers) else money(checkout_candidate.price) if checkout_candidate.price is not None else None,
            purchase_date=checkout_candidate.purchase_date,
            price_contract_id=selected_contract_id,
            eligibility=selected_eligibility,
            price_mechanism=selected_mechanism,
            membership_program=selected_membership,
            offer_description=offer_description,
            applied_offer=applied_offer,
            checkout_offers=tuple(checkout_candidate.offers) if has_counted_weight_contract(checkout_candidate, checkout_candidate.offers) else (),
            resolution_warning=resolution_warning,
            source_provenance=candidate.source_provenance,
        )

    def calculate_item(
        self,
        ingredient: NormalizedIngredient,
        candidate: ProductCandidate,
    ) -> BasketItem:
        """Return the public basket model for one ingredient and product."""

        return self.quote_item(ingredient, candidate).to_basket_item()


def calculate_item(ingredient: NormalizedIngredient, candidate: ProductCandidate) -> BasketItem:
    """Functional wrapper for scripts and tests."""

    return BasketCalculator().calculate_item(ingredient, candidate)


__all__ = [
    "BasketCalculator",
    "BasketItemQuote",
    "calculate_item",
    "calculate_packages",
    "money",
    "resolve_fixed_checkout_price",
]
