"""Consumer-safe membership coverage and fixed-basket savings reporting."""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from app.models import (
    MembershipCoverage,
    MembershipSavings,
    NormalizedIngredient,
    OptimizedBasket,
    ProductCandidate,
)
from app.services.basket_calculator import BasketCalculator
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.user_pricing import (
    price_candidate_for_context,
    price_contracts_for_candidate,
)

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    UserPricingContext,
)

_CENT = Decimal("0.01")

_PROGRAM_LABELS = {
    MembershipProgram.ICA_STAMMIS: "ICA Stammis",
    MembershipProgram.COOP_MEMBER: "Coop medlem",
    MembershipProgram.HEMKOP_MEMBER: "Klubb Hemköp",
    MembershipProgram.LIDL_PLUS: "Lidl Plus",
    MembershipProgram.WILLYS_PLUS: "Willys Plus",
    MembershipProgram.CITY_GROSS_PRIO: "City Gross Prio",
}

_PROGRAM_PRICE_LABELS = {
    MembershipProgram.ICA_STAMMIS: "Stammispriser",
    MembershipProgram.COOP_MEMBER: "Coop-medlemspriser",
    MembershipProgram.HEMKOP_MEMBER: "Klubb Hemköp-priser",
    MembershipProgram.LIDL_PLUS: "Lidl Plus-priser",
    MembershipProgram.WILLYS_PLUS: "Willys Plus-priser",
    MembershipProgram.CITY_GROSS_PRIO: "City Gross Prio-priser",
}


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


def _all_candidates(pool: EconomicIngredientPool) -> tuple[ProductCandidate, ...]:
    rows: dict[tuple[str, str], ProductCandidate] = {}
    for mapping in (
        pool.matched_candidates_by_name,
        pool.semantic_candidates_by_name,
        pool.candidates_by_name,
    ):
        for candidates in mapping.values():
            for candidate in candidates:
                rows.setdefault((candidate.store_id, candidate.product_id), candidate)
    return tuple(rows[key] for key in sorted(rows))


def membership_coverage(
    pool: EconomicIngredientPool,
    context: UserPricingContext,
    *,
    on_date: date,
) -> tuple[MembershipCoverage, ...]:
    """Describe only the selected programmes against the request's contexts."""

    candidates = _all_candidates(pool)
    selected_programs = tuple(
        sorted(context.memberships, key=lambda item: item.value)
    )
    contracts_by_program: dict[MembershipProgram, set[str]] = {
        program: set() for program in selected_programs
    }
    contexts_by_program: dict[MembershipProgram, set[str]] = {
        program: set() for program in selected_programs
    }
    # Parse every candidate's contracts once. A user may enable several
    # programmes, and repeating this full scan per checkbox made warm replans
    # needlessly proportional to the number of selected memberships.
    for candidate in candidates:
        for contract in price_contracts_for_candidate(candidate):
            program = contract.membership_program
            if (
                contract.eligibility is PromotionEligibility.MEMBER
                and program in contracts_by_program
                and contract.is_active(on_date)
                and context.allows(contract)
            ):
                assert program is not None
                contracts_by_program[program].add(contract.reference)
                contexts_by_program[program].add(candidate.store_name)

    result: list[MembershipCoverage] = []
    for program in selected_programs:
        contracts = contracts_by_program[program]
        contexts = contexts_by_program[program]
        label = _PROGRAM_LABELS[program]
        if contracts:
            message = (
                f"{label}: {len(contracts)} verifierade medlemspriskontrakt "
                "finns i sökningens priskontexter."
            )
            status = "available"
        else:
            message = (
                f"{label} är aktiverat, men vi har för närvarande inga verifierade "
                f"{_PROGRAM_PRICE_LABELS[program]} för de priskontexter som används "
                "i denna sökning."
            )
            status = "no_verified_contracts"
        result.append(
            MembershipCoverage(
                membership_program=program,
                active_contracts=len(contracts),
                contexts=tuple(sorted(contexts)),
                status=status,
                message=message,
            )
        )
    return tuple(result)


def fixed_basket_membership_savings(
    basket: OptimizedBasket,
    shared_pool: EconomicIngredientPool,
    *,
    on_date: date,
) -> MembershipSavings:
    """Reprice the same selected products and quantities with memberships off."""

    candidates = {
        (candidate.store_id, candidate.product_id): candidate
        for candidate in _all_candidates(shared_pool)
    }
    calculator = BasketCalculator()
    public_total = Decimal(0)
    member_lines = 0
    for group in basket.stores:
        for item in group.items:
            try:
                shared_candidate = candidates[(item.store_id, item.product_id)]
            except KeyError as exc:  # pragma: no cover - hard invariant guard
                raise ValueError(
                    "selected basket product is absent from the shared economic pool"
                ) from exc
            public_candidate = price_candidate_for_context(
                shared_candidate,
                UserPricingContext(),
                on_date=on_date,
            )
            requirement = NormalizedIngredient(
                canonical_name=item.ingredient,
                required_quantity=item.required_quantity,
                unit=item.unit,
            )
            public_total += _money(
                calculator.quote_item(requirement, public_candidate).total_price
            )
            if item.membership_required:
                member_lines += 1

    current_total = _money(basket.total)
    public_total = _money(public_total)
    savings = max(Decimal(0), public_total - current_total)
    return MembershipSavings(
        basket_total_with_memberships=float(current_total),
        same_basket_public_total=float(public_total),
        amount=float(_money(savings)),
        member_price_lines=member_lines,
    )


__all__ = ["fixed_basket_membership_savings", "membership_coverage"]
