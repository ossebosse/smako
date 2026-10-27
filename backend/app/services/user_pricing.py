"""Request-time price eligibility over one immutable shared PriceUniverse.

The shared artifact retains every verified public and generic-member contract.
This module creates a short-lived candidate projection for one
``UserPricingContext``; it never mutates the artifact and never contacts a
provider. Personal offers can later be supplied as an explicit overlay of
``PriceContract`` rows through the same resolver.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.models.product import OfferKind, OfferMetadata, ProductCandidate, SaleModel
from app.services.economic_ingredient_selector import (
    EconomicIngredientPool,
    EconomicIngredientSelector,
    EconomicIngredientSignal,
    _candidate_key,
)
from app.services.ingredient_taxonomy import IngredientCategory, IngredientTaxonomyEntry

from grocery_data.app.domain.counted_offer_checkout import uses_counted_offer_checkout
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PriceContract,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)
from grocery_data.app.services.fixed_checkout_price import resolve_effective_price

_STOCKHOLM = ZoneInfo("Europe/Stockholm")


class EstimatedPurchaseRequired(ValueError):
    """Known variable quantity needs the user's explicit purchase consent."""



def current_pricing_date() -> date:
    """Return the retail calendar date used for Swedish offer validity."""

    return datetime.now(tz=_STOCKHOLM).date()


def _stable_reference(candidate: ProductCandidate, suffix: str) -> str:
    provenance = candidate.source_provenance
    snapshot = provenance.source_snapshot_id if provenance is not None else "unknown-snapshot"
    payload = f"{snapshot}|{candidate.store_id}|{candidate.product_id}|{suffix}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"price-contract:{digest}"


def _membership_program(
    candidate: ProductCandidate,
    offer: OfferMetadata | None = None,
) -> MembershipProgram | None:
    if offer is not None and offer.membership_program is not None:
        return offer.membership_program
    values = (
        offer.member_program if offer is not None else None,
        candidate.chain,
    )
    for value in values:
        if not value:
            continue
        try:
            return MembershipProgram.from_value(value)
        except ValueError:
            continue
    return None


def _offer_contract(
    candidate: ProductCandidate,
    offer: OfferMetadata,
    *,
    index: int,
    rate_contract: bool = False,
) -> PriceContract:
    if offer.price_basis_unit != 'package' and not rate_contract:
        raise ValueError('Quoted weight rate requires measured purchase weight; not a package price')
    if offer.deposit and offer.deposit.gtin is not None and offer.deposit.gtin != candidate.gtin:
        raise ValueError("deposit contract belongs to another product variant")
    eligibility = offer.eligibility or (
        PromotionEligibility.MEMBER
        if offer.kind is OfferKind.MEMBER or offer.member_program
        else PromotionEligibility.PUBLIC
    )
    mechanism = offer.mechanism or (
        PromotionMechanism.MULTIBUY
        if offer.kind is OfferKind.MULTIPACK
        else PromotionMechanism.SALE_PRICE
    )
    provenance = candidate.source_provenance
    membership_program = (
        _membership_program(candidate, offer)
        if eligibility is PromotionEligibility.MEMBER
        else None
    )
    candidate_chain = (candidate.chain or "").casefold().replace(" ", "")
    if (
        membership_program is not None
        and candidate_chain
        and membership_program.chain != candidate_chain
    ):
        raise ValueError(
            "membership program does not match product chain: "
            f"{membership_program.value}/{candidate.chain}"
        )
    reference = offer.price_contract_id or _stable_reference(
        candidate,
        "|".join(
            (
                str(index),
                eligibility.value,
                mechanism.value,
                str(offer.price),
                str(offer.required_packages),
                str(offer.max_quantity or ""),
                offer.valid_from.isoformat() if offer.valid_from else "",
                offer.valid_to.isoformat() if offer.valid_to else "",
            )
        ),
    )
    return PriceContract(
        reference=reference,
        eligibility=eligibility,
        mechanism=mechanism,
        description=offer.description,
        price=Decimal(str(offer.price)),
        percent_discount=(
            Decimal(str(offer.percent_discount))
            if offer.percent_discount is not None
            else None
        ),
        required_packages=offer.required_packages,
        max_quantity=offer.max_quantity,
        membership_program=membership_program,
        member_program=offer.member_program,
        product_id=candidate.product_id,
        price_context_id=candidate.store_id,
        source=provenance.source_provider if provenance is not None else None,
        source_snapshot_id=(
            provenance.source_snapshot_id if provenance is not None else None
        ),
        observed_at=provenance.source_observed_at if provenance is not None else None,
        currency=offer.currency,
        source_confidence=offer.source_confidence,
        semantic_confidence=(
            offer.semantic_confidence
            or (provenance.semantic_confidence if provenance is not None else None)
        ),
        quantity_confidence=(
            offer.quantity_confidence
            or (provenance.quantity_confidence if provenance is not None else None)
        ),
        valid_from=offer.valid_from,
        valid_to=offer.valid_to,
        campaign_evidence=offer.campaign_evidence,
        deposit=offer.deposit,
    )


def price_contracts_for_candidate(
    candidate: ProductCandidate,
) -> tuple[PriceContract, ...]:
    """Project the compact artifact representation into normalized contracts."""

    provenance = candidate.source_provenance
    regular = PriceContract(
        reference=_stable_reference(candidate, "regular"),
        eligibility=PromotionEligibility.PUBLIC,
        mechanism=PromotionMechanism.REGULAR,
        description="Ordinarie pris",
        price=Decimal(str(candidate.price)),
        product_id=candidate.product_id,
        price_context_id=candidate.store_id,
        source=provenance.source_provider if provenance is not None else None,
        source_snapshot_id=(
            provenance.source_snapshot_id if provenance is not None else None
        ),
        observed_at=provenance.source_observed_at if provenance is not None else None,
        semantic_confidence=(
            provenance.semantic_confidence if provenance is not None else None
        ),
        quantity_confidence=(
            provenance.quantity_confidence if provenance is not None else None
        ),
    ) if candidate.price is not None else None
    contracts = [regular] if regular is not None else []
    offer_contracts = [
        _offer_contract(candidate, offer, index=index)
        for index, offer in enumerate(candidate.offers)
        if offer.price_basis_unit == 'package'
    ]
    contracts.extend(offer_contracts)

    effective_price = Decimal(str(candidate.effective_price))
    member_single_prices = {
        contract.price
        for contract in offer_contracts
        if contract.eligibility is PromotionEligibility.MEMBER
        and contract.required_packages == 1
        and contract.price is not None
    }
    has_same_public_single = any(
        contract.eligibility is PromotionEligibility.PUBLIC
        and contract.mechanism
        in {PromotionMechanism.SALE_PRICE, PromotionMechanism.PERCENT_DISCOUNT}
        and contract.required_packages == 1
        and contract.price is not None
        and abs(contract.price - effective_price) <= Decimal("0.005")
        for contract in offer_contracts
    )
    if (
        candidate.price is not None
        and effective_price < Decimal(str(candidate.price))
        and not has_same_public_single
        and all(
            member_price is None
            or abs(member_price - effective_price) > Decimal("0.005")
            for member_price in member_single_prices
        )
        and (
            candidate.member_price is None
            or abs(Decimal(str(candidate.member_price)) - effective_price)
            > Decimal("0.005")
        )
    ):
        contracts.append(
            PriceContract(
                reference=_stable_reference(candidate, "public-current"),
                eligibility=PromotionEligibility.PUBLIC,
                mechanism=PromotionMechanism.SALE_PRICE,
                description="Aktuellt publikt pris",
                price=effective_price,
                product_id=candidate.product_id,
                price_context_id=candidate.store_id,
                source=provenance.source_provider if provenance is not None else None,
                source_snapshot_id=(
                    provenance.source_snapshot_id if provenance is not None else None
                ),
                observed_at=(
                    provenance.source_observed_at if provenance is not None else None
                ),
                semantic_confidence=(
                    provenance.semantic_confidence if provenance is not None else None
                ),
                quantity_confidence=(
                    provenance.quantity_confidence if provenance is not None else None
                ),
            )
        )

    member_price = candidate.member_price
    program = _membership_program(candidate)
    has_same_member_single = any(
        contract.eligibility is PromotionEligibility.MEMBER
        and contract.mechanism
        in {PromotionMechanism.SALE_PRICE, PromotionMechanism.PERCENT_DISCOUNT}
        and contract.required_packages == 1
        and contract.price is not None
        and member_price is not None
        and abs(contract.price - Decimal(str(member_price))) <= Decimal("0.005")
        for contract in offer_contracts
    )
    if member_price is not None and program is not None and not has_same_member_single:
        contracts.append(
            PriceContract(
                reference=_stable_reference(candidate, f"member:{program.value}"),
                eligibility=PromotionEligibility.MEMBER,
                mechanism=PromotionMechanism.SALE_PRICE,
                description=program.consumer_label,
                price=Decimal(str(member_price)),
                membership_program=program,
                member_program=program.consumer_label,
                product_id=candidate.product_id,
                price_context_id=candidate.store_id,
                source=provenance.source_provider if provenance is not None else None,
                source_snapshot_id=(
                    provenance.source_snapshot_id if provenance is not None else None
                ),
                observed_at=(
                    provenance.source_observed_at if provenance is not None else None
                ),
                semantic_confidence=(
                    provenance.semantic_confidence if provenance is not None else None
                ),
                quantity_confidence=(
                    provenance.quantity_confidence if provenance is not None else None
                ),
            )
        )
    return tuple(contracts)


def _eligible_member_contracts(
    pool: EconomicIngredientPool,
    context: UserPricingContext,
    *,
    on_date: date | None = None,
) -> tuple[PriceContract, ...]:
    """Return active member contracts reachable before economic pruning.

    Reading only the public shortlist would miss a membership winner whose
    canonical was pruned during the shared prebuild.
    """

    candidate_rows = (
        pool.matched_candidates_by_name
        or pool.semantic_candidates_by_name
        or pool.candidates_by_name
    )
    target_date = on_date or current_pricing_date()
    eligible: list[PriceContract] = []
    for rows in candidate_rows.values():
        for candidate in rows:
            if candidate.member_price is None and not any(
                offer.eligibility is PromotionEligibility.MEMBER
                or offer.kind is OfferKind.MEMBER
                or offer.membership_program is not None
                or offer.member_program is not None
                for offer in candidate.offers
            ):
                continue
            eligible.extend(
                contract
                for contract in price_contracts_for_candidate(candidate)
                if contract.eligibility is PromotionEligibility.MEMBER
                and context.allows(contract)
                and contract.is_active(target_date)
            )
    return tuple(eligible)


def eligible_member_contract_references(
    pool: EconomicIngredientPool,
    context: UserPricingContext,
    *,
    on_date: date | None = None,
) -> frozenset[str]:
    """Return active member contract IDs for diagnostics and provenance."""

    return frozenset(
        contract.reference
        for contract in _eligible_member_contracts(pool, context, on_date=on_date)
    )


def eligible_member_contract_fingerprints(
    pool: EconomicIngredientPool,
    context: UserPricingContext,
    *,
    on_date: date | None = None,
) -> frozenset[str]:
    """Hash complete active contracts for safe cross-context menu caching."""

    fingerprints: set[str] = set()
    for contract in _eligible_member_contracts(pool, context, on_date=on_date):
        payload = contract.model_dump(mode="json", exclude_computed_fields=True)
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        fingerprints.add(
            f"member-contract:{hashlib.sha256(encoded).hexdigest()}"
        )
    return frozenset(fingerprints)


def _synthetic_member_offer(
    candidate: ProductCandidate,
    contract: PriceContract,
) -> OfferMetadata:
    assert contract.price is not None
    return OfferMetadata(
        kind=OfferKind.MEMBER,
        description=contract.description,
        price=float(contract.price),
        price_contract_id=contract.reference,
        eligibility=contract.eligibility,
        mechanism=contract.mechanism,
        membership_program=contract.membership_program,
        member_program=contract.member_program,
        source_confidence=contract.source_confidence,
        semantic_confidence=contract.semantic_confidence,
        quantity_confidence=contract.quantity_confidence,
        valid_from=contract.valid_from,
        valid_to=contract.valid_to,
        deposit=contract.deposit,
        campaign_evidence=contract.campaign_evidence,
    )


def _price_weight_candidate(candidate, context, target_date):
    """Select a verified rate using the existing eligibility/price resolver.

    One rate unit is resolved here; physical quantities and package caps are
    calculated separately by PurchaseQuantityResolver and basket checkout.
    """
    terms = candidate.purchase_terms
    contracts = [_offer_contract(candidate, o, index=i, rate_contract=True)
                 for i, o in enumerate(candidate.offers)
                 if o.price_basis_unit == 'kg' and o.required_packages == 1
                 and o.deposit is None]
    def unavailable():
        # Explain the resolver's own contract gates; this does not implement
        # another eligibility policy or manufacture a fallback price.
        active = [c for c in contracts if c.is_active(target_date)]
        if not contracts:
            return "No verified kg rate contract without unresolved deposit"
        if not active:
            return f"No weight-price contract active on {target_date}"
        if not any(context.allows(c) for c in active):
            programs = sorted({str(c.membership_program) for c in active if c.membership_program})
            return "Active weight-price contract requires membership/activation eligibility: " + ", ".join(programs)
        return "No verified applicable weight-price contract"

    try:
        resolution = resolve_effective_price(contracts, 1, context, on_date=target_date)
    except ValueError as exc:
        raise ValueError(unavailable()) from exc
    selected = resolution.applied_promotion
    if selected is None:
        raise ValueError(unavailable())
    offer = next(o for i, o in enumerate(candidate.offers)
                 if _offer_contract(candidate, o, index=i, rate_contract=True).reference == selected.reference)
    if terms.purchase_form == 'loose_weight' and offer.max_quantity is not None:
        raise ValueError('Loose weight needs an explicit weight purchase-limit unit')
    quantity = terms.approximate_package_g or terms.minimum_package_g
    if terms.purchase_form == 'variable_package' and quantity is None:
        raise ValueError('No source package-weight estimate or verified minimum')
    from app.services.purchase_quantity_resolver import project_purchase_shape

    candidate = project_purchase_shape(candidate)
    rate = float(resolution.checkout_total)
    return candidate.model_copy(update={
        'sale_price': rate, 'sale_unit': 'kg', 'effective_price': rate,
        'comparison_price': rate, 'comparison_unit': 'kg', 'offers': [offer],
        'purchase_date': target_date, 'selected_price_contract_id': selected.reference,
        'selected_price_eligibility': selected.eligibility,
        'selected_price_mechanism': selected.mechanism,
        'selected_membership_program': selected.membership_program,
    })


def _ordinary_weight_rate(candidate, context, target_date):
    """Retain an independent ordinary rate when a legacy offer cap is unbound.

    Older catalog rows can carry a kg offer without a verified limit unit.
    Its count must not be guessed from an identifier or package size. Keep
    those offers as source metadata and resolve only the separate ordinary
    rate; the existing quantity resolver still rounds whole variable packs.
    """
    if (candidate.purchase_terms is not None
            or candidate.sale_model not in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}
            or candidate.sale_unit != 'kg'
            or candidate.price is None or candidate.sale_price != candidate.price
            or not all(o.price_basis_unit == 'kg' and o.required_packages == 1
                       and o.max_quantity is not None and o.limit_unit is None
                       and o.deposit is None and o.mechanism is PromotionMechanism.SALE_PRICE
                       and abs(o.price - candidate.price) > 0.005
                       for o in candidate.offers)):
        raise ValueError('Unbound weight offer requires an independent ordinary kg rate')
    ordinary = candidate.model_copy(update={
        'effective_price': candidate.price, 'member_price': None, 'offers': [],
    })
    contracts = price_contracts_for_candidate(ordinary)
    resolution = resolve_effective_price(contracts, 1, context, on_date=target_date)
    return candidate.model_copy(update={
        'sale_price': float(resolution.checkout_total), 'effective_price': float(resolution.checkout_total),
        'comparison_price': float(resolution.checkout_total), 'comparison_unit': 'kg',
        'member_price': None, 'purchase_date': target_date,
        'selected_price_contract_id': contracts[0].reference,
        'selected_price_eligibility': PromotionEligibility.PUBLIC,
        'selected_price_mechanism': PromotionMechanism.REGULAR,
        'selected_membership_program': None,
    })


def price_candidate_for_context(
    candidate: ProductCandidate,
    context: UserPricingContext,
    *,
    on_date: date | None = None,
    planning_mode: str = "exact",
    allow_campaign_choice: bool = False,
) -> ProductCandidate:
    """Return one request-local candidate; the input artifact row is untouched."""

    terms = candidate.purchase_terms
    source_quantity_confidence = candidate.quantity_confidence
    estimated_deposit = any(o.deposit and o.deposit.confidence == 'estimated' for o in candidate.offers)
    if estimated_deposit and planning_mode != 'estimated':
        raise EstimatedPurchaseRequired('Estimated deposit requires estimated planning mode')
    if estimated_deposit:
        candidate = candidate.model_copy(update={'quantity_confidence': 'estimated'})
    if terms and terms.usage == 'variant_selection_required' and allow_campaign_choice:
        if terms.purchase_form not in {'piece', 'fixed_package'} or any(o.price_basis_unit != 'package' for o in candidate.offers):
            raise ValueError('Conditional campaign needs a verified count purchase')
        candidate = candidate.model_copy(update={
            'conditional_variant_choice': True, 'sale_model': SaleModel.SOLD_BY_PIECE,
            'package_quantity': 1, 'package_unit': 'st', 'usable_quantity': 1, 'usable_unit': 'st',
            'quantity_confidence': 'estimated' if estimated_deposit else 'exact', 'estimated_piece_weight': None,
            'variable_weight': False, 'piece_price': candidate.effective_price,
            'semantic_confidence': 'high',
            'semantic_evidence': ['user-confirmed campaign sales unit; actual variant unresolved'],
        })
    elif terms and terms.usage in {'blocked', 'variant_selection_required'}:
        raise ValueError('Purchase requires completion: ' + terms.usage)
    if terms and terms.usage == 'estimated':
        if planning_mode != 'estimated':
            raise EstimatedPurchaseRequired('Weight-dependent checkout requires estimated planning mode')
        return _price_weight_candidate(candidate, context, on_date or current_pricing_date())
    if candidate.sale_model in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}:
        if planning_mode != 'estimated':
            raise EstimatedPurchaseRequired('Weight-dependent checkout requires estimated planning mode')
        candidate = candidate.model_copy(update={'quantity_confidence': 'estimated'})
    target_date = on_date or current_pricing_date()
    from app.services.basket_calculator import has_counted_weight_contract
    if has_counted_weight_contract(candidate, candidate.offers):
        ordinary = candidate.sale_price
        if ordinary is None or ordinary != candidate.price:
            raise ValueError('Independent ordinary kg rate required for capped package checkout')
        contracts = [_offer_contract(candidate, o, index=i, rate_contract=True)
            for i, o in enumerate(candidate.offers) if o.limit_unit == 'purchase_packages']
        offers = [o for o, c in zip([o for o in candidate.offers if o.limit_unit == 'purchase_packages'], contracts, strict=True)
                  if c.is_active(target_date) and context.allows(c)]
        # Keep inactive metadata out of checkout. No membership or cap bypass.
        rate = min([ordinary, *(o.price for o in offers)])
        return candidate.model_copy(update={'price': ordinary, 'sale_price': rate,
            'effective_price': rate, 'comparison_price': rate, 'comparison_unit': 'kg',
            'offers': offers, 'purchase_date': target_date})
    if any(o.price_basis_unit == 'kg' for o in candidate.offers):
        if source_quantity_confidence == 'unknown':
            raise ValueError('Ordinary weight fallback requires known source quantity evidence')
        return _ordinary_weight_rate(candidate, context, target_date)
    candidate = candidate.model_copy(update={"promotion_groups": tuple(
        g for g in candidate.promotion_groups
        if g.valid_from <= target_date <= g.valid_to
        and (g.membership_program is None or g.membership_program in context.memberships)
    )}) if candidate.promotion_groups else candidate
    contracts = price_contracts_for_candidate(candidate)
    try:
        resolution = resolve_effective_price(contracts, 1, context, on_date=target_date)
    except ValueError:
        # Retain eligible offers-only multibuys until the actual package count
        # is known. This is a ranking signal, never a one-package sale price.
        grouped = [c for c in contracts if c.mechanism is PromotionMechanism.MULTIBUY
                   and c.required_packages > 1 and c.price is not None
                   and c.is_active(target_date) and context.allows(c)]
        if candidate.price is not None or not uses_counted_offer_checkout(candidate) or not grouped:
            raise
        # Reuse the same checkout resolver to validate the complete group.
        signals = [float(resolve_effective_price(contracts, c.required_packages, context,
                         on_date=target_date).checkout_total) / c.required_packages for c in grouped]
        eligible_offers = [o for i, o in enumerate(candidate.offers)
                           if (c := _offer_contract(candidate, o, index=i)).is_active(target_date)
                           and context.allows(c)]
        return candidate.model_copy(update={
            "purchase_date": target_date, "effective_price": min(signals),
            "sale_price": None, "piece_price": None, "offers": eligible_offers,
            "selected_price_contract_id": None,
            "selected_price_mechanism": PromotionMechanism.MULTIBUY,
        })
    eligible_offers: list[OfferMetadata] = []
    present_references: set[str] = set()
    for index, offer in enumerate(candidate.offers):
        contract = _offer_contract(candidate, offer, index=index)
        if context.allows(contract) and contract.is_active(target_date):
            normalized = offer.model_copy(
                update={
                    "price_contract_id": contract.reference,
                    "eligibility": contract.eligibility,
                    "mechanism": contract.mechanism,
                    "membership_program": contract.membership_program,
                }
            )
            eligible_offers.append(normalized)
            present_references.add(contract.reference)

    selected = resolution.applied_promotion
    if (
        selected is not None
        and selected.eligibility is PromotionEligibility.MEMBER
        and selected.reference not in present_references
    ):
        eligible_offers.append(_synthetic_member_offer(candidate, selected))

    effective = float(resolution.checkout_total)
    updates: dict[str, object] = {
        "purchase_date": target_date,
        "effective_price": effective,
        "sale_price": effective,
        "offers": eligible_offers,
        "member_price": candidate.member_price if any(
            contract.eligibility is PromotionEligibility.MEMBER
            and contract.required_packages == 1 and contract.is_active(target_date)
            and contract.price is not None and candidate.member_price is not None
            and abs(contract.price - Decimal(str(candidate.member_price))) <= Decimal("0.005")
            for contract in contracts
        ) else None,
        "promotion_groups": tuple(
            g
            for g in candidate.promotion_groups
            if g.valid_from <= target_date <= g.valid_to
            and (g.membership_program is None or g.membership_program in context.memberships)
        ),
        "selected_price_contract_id": (
            selected.reference
            if selected is not None
            else _stable_reference(candidate, "regular")
        ),
        "selected_price_eligibility": (
            selected.eligibility if selected is not None else PromotionEligibility.PUBLIC
        ),
        "selected_price_mechanism": (
            selected.mechanism if selected is not None else PromotionMechanism.REGULAR
        ),
        "selected_membership_program": (
            selected.membership_program if selected is not None else None
        ),
    }
    if candidate.sale_model is SaleModel.SOLD_BY_PIECE:
        updates["piece_price"] = effective
    # ProductCandidate and every nested pricing/provenance model are frozen.
    # ``eligible_offers`` is a new list, while all untouched values are safe to
    # share with the immutable artifact row. A deep copy adds no isolation but
    # repeatedly clones provenance and offer models during membership switches.
    return candidate.model_copy(update=updates)


def _project_rows(
    rows: Iterable[ProductCandidate],
    context: UserPricingContext,
    *,
    on_date: date,
    planning_mode: str = "exact",
) -> list[ProductCandidate]:
    projected: list[ProductCandidate] = []
    for candidate in rows:
        member_offers = any(
            offer.eligibility is PromotionEligibility.MEMBER
            or offer.kind is OfferKind.MEMBER
            or offer.membership_program is not None
            or offer.member_program is not None
            for offer in candidate.offers
        )
        selected_member_price = (
            candidate.member_price is not None
            and (program := _membership_program(candidate)) is not None
            and program in context.memberships
        )
        if (
            candidate.price is None
            or candidate.sale_model in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}
            or candidate.promotion_groups
            or member_offers
            or selected_member_price
            or candidate.effective_price < candidate.price
            or candidate.selected_price_contract_id is not None
            or candidate.selected_price_eligibility
            is not PromotionEligibility.PUBLIC
            or candidate.selected_price_mechanism is not PromotionMechanism.REGULAR
            or candidate.selected_membership_program is not None
        ):
            try:
                projected.append(price_candidate_for_context(candidate, context, on_date=on_date, planning_mode=planning_mode))
            except ValueError:
                if candidate.price is not None and candidate.sale_model not in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}:
                    raise
                # Optional offers outside their verified validity are unavailable.
                continue
        else:
            # Most catalog rows are ordinary public prices. Reuse the frozen
            # artifact model instead of cloning and revalidating an identical
            # PriceContract on every membership switch.
            projected.append(candidate)
    return projected


def _membership_can_change_candidate(
    candidate: ProductCandidate,
    context: UserPricingContext,
    *,
    on_date: date,
) -> bool:
    """Whether this row can gain an active contract in this membership set."""

    return (
        candidate.member_price is not None
        and (program := _membership_program(candidate)) is not None
        and program in context.memberships
    ) or any(
        offer.eligibility is PromotionEligibility.MEMBER
        and (program := _membership_program(candidate, offer)) is not None
        and program in context.memberships
        and offer.is_active(on_date)
        for offer in candidate.offers
    )


def prepare_economic_pool_for_pricing(
    pool: EconomicIngredientPool,
    *,
    selector: EconomicIngredientSelector,
) -> EconomicIngredientPool:
    """Validate the complete matcher surface once per prepared artifact.

    Older prepared artifacts persist the full pre-economic matcher map but
    only the public category winners in ``semantic_candidates_by_name``. A
    universe-local runtime cache stores this expanded, price-independent map,
    so later membership switches redo only pricing/ranking and never repeat
    taxonomy, quantity and verification gates.
    """

    if pool.projection_semantics_identity == selector.cache_identity:
        return pool
    taxonomy = {entry.canonical: entry for entry in selector.taxonomy}
    semantic_candidates: dict[str, list[ProductCandidate]] = {}
    for canonical in sorted(taxonomy):
        entry = taxonomy[canonical]
        if canonical in pool.matched_candidates_by_name:
            source_rows = pool.matched_candidates_by_name[canonical]
        elif canonical in pool.semantic_candidates_by_name:
            source_rows = pool.semantic_candidates_by_name[canonical]
        else:
            source_rows = pool.candidates_by_name.get(canonical, ())
        semantic_candidates[canonical] = selector.validate_semantic_candidates(
            entry,
            source_rows,
        )
    return pool.model_copy(
        update={
            "semantic_candidates_by_name": semantic_candidates,
            "projection_semantics_identity": selector.cache_identity,
        }
    )


def _merge_ranked_candidates(
    entry: IngredientTaxonomyEntry,
    *candidate_groups: Iterable[ProductCandidate],
) -> list[ProductCandidate]:
    """Return the cheapest stable row for every exact store/product identity."""

    merged: dict[tuple[str, str], ProductCandidate] = {}
    for candidates in candidate_groups:
        for candidate in candidates:
            identity = (candidate.store_id, candidate.product_id)
            previous = merged.get(identity)
            if previous is None or _candidate_key(entry, candidate) < _candidate_key(
                entry,
                previous,
            ):
                merged[identity] = candidate
    return sorted(
        merged.values(),
        key=lambda candidate: _candidate_key(entry, candidate),
    )


def _store_shortlist(
    selector: EconomicIngredientSelector,
    entry: IngredientTaxonomyEntry,
    candidates: Iterable[ProductCandidate],
) -> list[ProductCandidate]:
    selected, _support = _store_shortlist_with_support(
        selector,
        entry,
        candidates,
    )
    return selected


def _store_shortlist_with_support(
    selector: EconomicIngredientSelector,
    entry: IngredientTaxonomyEntry,
    candidates: Iterable[ProductCandidate],
) -> tuple[list[ProductCandidate], list[ProductCandidate]]:
    """Return exact per-store selection plus reusable public support rows."""

    by_store: dict[str, list[ProductCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_store[candidate.store_id].append(candidate)
    selected: list[ProductCandidate] = []
    support: list[ProductCandidate] = []
    for store_id in sorted(by_store):
        store_selected, store_support = selector._select_store_candidates_with_support(
            entry,
            by_store[store_id],
        )
        selected.extend(store_selected)
        support.extend(store_support)
    return (
        _merge_ranked_candidates(entry, selected),
        _merge_ranked_candidates(entry, support),
    )


def _economic_signal(
    selector: EconomicIngredientSelector,
    entry: IngredientTaxonomyEntry,
    candidates: list[ProductCandidate],
) -> EconomicIngredientSignal:
    examples = selector._select_examples(entry, candidates)
    best = examples[0]
    return EconomicIngredientSignal(
        canonical=entry.canonical,
        display_name=entry.display_name,
        category=entry.category,
        best_local_unit_price=best.normalized_unit_price,
        normalized_unit=best.normalized_unit,
        economic_score=best.economic_score,
        is_offer=best.is_offer,
        example_products=examples,
    )


def _category_shortlist(
    selector: EconomicIngredientSelector,
    ranked: dict[
        IngredientCategory,
        list[tuple[EconomicIngredientSignal, list[ProductCandidate]]],
    ],
) -> list[tuple[EconomicIngredientSignal, list[ProductCandidate]]]:
    result: list[tuple[EconomicIngredientSignal, list[ProductCandidate]]] = []
    for category in IngredientCategory:
        rows = sorted(
            ranked.get(category, ()),
            key=lambda row: (row[0].economic_score, row[0].canonical),
        )
        limit = selector.max_ingredients_per_category.get(category)
        result.extend(rows[:limit] if limit is not None else rows)
    return result


def project_economic_pool(
    pool: EconomicIngredientPool,
    context: UserPricingContext,
    *,
    selector: EconomicIngredientSelector,
    on_date: date | None = None,
    public_floor_pool: EconomicIngredientPool | None = None,
) -> EconomicIngredientPool:
    """Build one request-local economic view before any price-based pruning.

    ``matched_candidates_by_name`` is the prepared artifact's complete,
    semantics-first matcher result.  Projecting it before the selector's store
    shortlist and category caps lets a verified member contract influence both
    product and canonical-ingredient ranking.  The shared artifact remains
    untouched.

    Every current-context canonical shortlist plus an independently priced
    public floor is retained for checkout. Adding another chain membership can
    therefore change recipe-generation signals without removing the exact
    candidates that priced an already fixed menu.
    """

    taxonomy = {entry.canonical: entry for entry in selector.taxonomy}
    semantics_prepared = pool.projection_semantics_identity == selector.cache_identity
    projected_candidates: dict[str, list[ProductCandidate]] = {}
    projected_semantic: dict[str, list[ProductCandidate]] = {}
    projected_matched: dict[str, list[ProductCandidate]] = {}
    projected_shortlist_support: dict[str, list[ProductCandidate]] = {}
    projected_signals: list[EconomicIngredientSignal] = []
    target_date = on_date or current_pricing_date()

    ranked_by_category: dict[
        IngredientCategory,
        list[tuple[EconomicIngredientSignal, list[ProductCandidate]]],
    ] = defaultdict(list)
    public_context = UserPricingContext()
    needs_public_floor = (
        context.cache_identity != public_context.cache_identity
        and public_floor_pool is None
    )
    public_candidates_by_name: dict[str, list[ProductCandidate]] = (
        dict(public_floor_pool.candidates_by_name)
        if public_floor_pool is not None
        else {}
    )
    public_support_by_name: dict[str, list[ProductCandidate]] = (
        dict(public_floor_pool.projection_shortlist_support_by_name)
        if public_floor_pool is not None
        else {}
    )
    checkout_candidates_by_name: dict[str, list[ProductCandidate]] = {}
    canonical_names = sorted(set(taxonomy) & (
        set(pool.candidates_by_name)
        | set(pool.semantic_candidates_by_name)
        | set(pool.matched_candidates_by_name)
    ))
    for canonical in canonical_names:
        entry = taxonomy.get(canonical)
        if entry is None:
            continue

        # Older prepared artifacts may not contain the full matcher map.  The
        # fallbacks keep those artifacts usable, while newly built universes
        # always take the complete pre-economic path first.
        if semantics_prepared:
            source_rows = list(pool.semantic_candidates_by_name.get(canonical, ()))
        else:
            source_rows = _merge_ranked_candidates(
                entry,
                pool.matched_candidates_by_name.get(canonical, ()),
                pool.semantic_candidates_by_name.get(canonical, ()),
                pool.candidates_by_name.get(canonical, ()),
            )
        membership_changing_rows = [
            candidate
            for candidate in source_rows
            if _membership_can_change_candidate(
                candidate,
                context,
                on_date=target_date,
            )
        ]
        membership_can_change_canonical = bool(membership_changing_rows)
        if public_floor_pool is not None and not membership_can_change_canonical:
            matched = list(
                public_floor_pool.semantic_candidates_by_name.get(
                    canonical,
                    source_rows,
                )
            )
            semantic = matched
            selected = list(
                public_floor_pool.candidates_by_name.get(canonical, ())
            )
            projected_shortlist_support[canonical] = list(
                public_support_by_name.get(canonical, ())
            )
        elif (
            public_floor_pool is not None
            and semantics_prepared
            and canonical in public_floor_pool.semantic_candidates_by_name
            and canonical in public_support_by_name
        ):
            # Only membership-carrying rows can change relative to the public
            # projection. Reuse every frozen public row and recompute those
            # deltas. The public support set contains the top-K candidates and
            # the winner at every representative demand in every store, so it
            # is the complete unchanged side of the exact shortlist comparison.
            public_semantic = public_floor_pool.semantic_candidates_by_name[canonical]
            public_by_identity = {
                (candidate.store_id, candidate.product_id): candidate
                for candidate in public_semantic
            }
            changed_by_identity = {
                (candidate.store_id, candidate.product_id): candidate
                for candidate in _project_rows(
                    membership_changing_rows, context, on_date=target_date,
                    planning_mode="estimated" if selector.verification_policy.allow_estimated_quantities else "exact",
                )
            }
            matched = []
            for candidate in source_rows:
                identity = (candidate.store_id, candidate.product_id)
                projected = changed_by_identity.get(identity)
                if projected is None:
                    projected = public_by_identity.get(identity)
                if projected is None:
                    # Defensive compatibility for older/incomplete public
                    # projections: fall back to the authoritative full path.
                    eligible = _project_rows(
                        [candidate], context, on_date=target_date,
                        planning_mode="estimated" if selector.verification_policy.allow_estimated_quantities else "exact",
                    )
                    if not eligible:
                        continue
                    projected = eligible[0]
                matched.append(projected)
            semantic = matched
            current_by_identity = {
                (candidate.store_id, candidate.product_id): candidate
                for candidate in semantic
            }
            comparison_basis = {
                identity: current_by_identity[identity]
                for identity in (
                    (candidate.store_id, candidate.product_id)
                    for candidate in public_support_by_name[canonical]
                )
                if identity in current_by_identity
            }
            comparison_basis.update(changed_by_identity)
            selected = _store_shortlist(
                selector,
                entry,
                comparison_basis.values(),
            )
            projected_shortlist_support[canonical] = list(
                public_support_by_name[canonical]
            )
        else:
            matched = _project_rows(source_rows, context, on_date=target_date,
                planning_mode="estimated" if selector.verification_policy.allow_estimated_quantities else "exact")
            semantic = (
                matched
                if semantics_prepared
                else selector.validate_semantic_candidates(entry, matched)
            )
            if semantic and context.cache_identity == public_context.cache_identity:
                selected, support = _store_shortlist_with_support(
                    selector,
                    entry,
                    semantic,
                )
                projected_shortlist_support[canonical] = support
            else:
                selected = _store_shortlist(selector, entry, semantic) if semantic else []
        projected_matched[canonical] = matched
        projected_semantic[canonical] = semantic
        if not semantic:
            continue
        if not selected:
            continue
        checkout_candidates_by_name[canonical] = selected
        ranked_by_category[entry.category].append(
            (_economic_signal(selector, entry, selected), selected)
        )

        # The shared prebuild predates request eligibility and may still carry
        # member offer metadata. Reconstruct one explicit public floor. All
        # current-context canonical/store winners are retained below; because
        # a normalized member program must match the candidate's chain, adding
        # another chain membership cannot change an already-enabled store's
        # shortlist. The public rows cover stores newly affected by membership.
        if needs_public_floor:
            public_matched = _project_rows(
                source_rows,
                public_context,
                on_date=target_date,
                planning_mode="estimated" if selector.verification_policy.allow_estimated_quantities else "exact",
            )
            public_semantic = (
                public_matched
                if semantics_prepared
                else selector.validate_semantic_candidates(entry, public_matched)
            )
            public_selected, public_support = _store_shortlist_with_support(
                selector,
                entry,
                public_semantic,
            )
            if public_selected:
                public_candidates_by_name[canonical] = public_selected
                projected_shortlist_support[canonical] = public_support

    # Apply the configured canonical-category caps only after eligibility has
    # changed the economic view. These signals drive recipe generation.
    projected_candidates.update(checkout_candidates_by_name)
    for signal, candidates in _category_shortlist(selector, ranked_by_category):
        projected_signals.append(signal)
        projected_candidates[signal.canonical] = candidates

    # Resolve public winner identities back to the current projection so any
    # newly eligible contract still applies when a previously fixed menu is
    # repriced.
    for canonical, public_candidates in public_candidates_by_name.items():
        entry = taxonomy[canonical]
        current_by_identity = {
            (candidate.store_id, candidate.product_id): candidate
            for candidate in projected_semantic.get(canonical, ())
        }
        retained_in_context = [
            current_by_identity[identity]
            for identity in (
                (candidate.store_id, candidate.product_id)
                for candidate in public_candidates
            )
            if identity in current_by_identity
        ]
        projected_candidates[canonical] = _merge_ranked_candidates(
            entry,
            projected_candidates.get(canonical, ()),
            retained_in_context,
        )

    return EconomicIngredientPool(
        ingredients=projected_signals,
        candidates_by_name=projected_candidates,
        semantic_candidates_by_name=projected_semantic,
        matched_candidates_by_name=projected_matched,
        projection_shortlist_support_by_name=projected_shortlist_support,
        search_queries_executed=pool.search_queries_executed,
        products_considered=pool.products_considered,
    )


__all__ = [
    "current_pricing_date",
    "eligible_member_contract_fingerprints",
    "eligible_member_contract_references",
    "prepare_economic_pool_for_pricing",
    "price_candidate_for_context",
    "price_contracts_for_candidate",
    "project_economic_pool",
]
