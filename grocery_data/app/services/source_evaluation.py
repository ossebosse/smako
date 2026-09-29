"""Read-only candidate diagnostics; never an import, price or activation path.

The existing source-neutral ComparisonRecord carries product facts. This module
adds explicit evaluation evidence so a diagnostic identity join is not mistaken
for an equivalent retail price. Unknown scope and conditions fail closed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
from grocery_data.app.services.freshness import FreshnessPolicy, assess_freshness
from grocery_data.app.services.primat_comparison import ComparisonRecord


@dataclass(frozen=True)
class EvaluationTerms:
    """Evidence for the *selected price*, not all offers on the product.

    ``complete`` means the caller verified conditions against the retained
    source response. None deposit/activation fields remain unknown. A zero
    deposit is permitted only where absence of deposit was verified.
    """

    price_kind: str | None = None
    eligibility: str | None = None
    membership_program: str | None = None
    activation_required: bool | None = None
    required_packages: int | None = None
    max_quantity: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    deposit_amount: Decimal | None = None
    deposit_included: bool | None = None
    complete: bool = False


@dataclass(frozen=True)
class EvaluationObservation:
    product: ComparisonRecord
    physical_store_id: str | None = None
    channel: str | None = None
    scope_evidence: str | None = None
    observed_at: datetime | None = None
    fetched_at: datetime | None = None
    price_basis: str | None = None
    terms: EvaluationTerms = EvaluationTerms()
    canonical_food: str | None = None
    usable_quantity: Decimal | None = None
    usable_unit: str | None = None
    semantic_confidence: str = "unknown"
    quantity_confidence: str = "unknown"
    quarantined: bool = False


@dataclass(frozen=True)
class DocumentedIdentityMatch:
    own_product_id: str
    primat_product_id: str
    evidence_reference: str


@dataclass(frozen=True)
class RecipeDemand:
    """One actual recipe; identities/units come from the existing normalizer."""

    recipe_id: str
    ingredients: tuple[tuple[str, str], ...]


def _aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None and value.utcoffset() is not None


def _gtin(row: EvaluationObservation) -> str | None:
    try:
        return normalize_gtin(row.product.gtin).normalized_gtin
    except InvalidGtinError:
        return None


def _identity(row: EvaluationObservation) -> str | None:
    gtin = _gtin(row)
    if gtin:
        return f"gtin:{gtin}"
    if row.product.external_product_id:
        return f"id:{row.product.external_product_id}"
    return None


def _package(row: EvaluationObservation) -> tuple[Decimal, str] | None:
    p = row.product
    factors = {
        "g": (Decimal(1), "g"), "kg": (Decimal(1000), "g"),
        "ml": (Decimal(1), "ml"), "l": (Decimal(1000), "ml"),
        "st": (Decimal(1), "st"),
    }
    if p.package_quantity is None or p.package_unit not in factors:
        return None
    factor, unit = factors[p.package_unit]
    return p.package_quantity * factor, unit


def _blockers(
    row: EvaluationObservation, *, now: datetime, policy: FreshnessPolicy,
) -> list[str]:
    result: list[str] = []
    if row.quarantined:
        result.append("quarantined")
    if not row.physical_store_id or not row.channel or not row.scope_evidence:
        result.append("unverified_store_or_channel")
    if row.channel in {"unknown", "catalog", "offers"}:
        result.append("unknown_sales_channel")
    if row.product.sale_price is None:
        result.append("no_positive_price")
    if not _aware(row.observed_at):
        result.append("missing_or_naive_observation_time")
    elif row.observed_at > now:
        result.append("future_observation")
    elif not assess_freshness(row.observed_at, now=now, policy=policy).usable:
        result.append("stale_price")
    if not _aware(row.fetched_at):
        result.append("missing_or_naive_fetch_time")
    elif row.fetched_at > now:
        result.append("future_fetch")
    elif _aware(row.observed_at) and row.observed_at > row.fetched_at:
        result.append("observation_after_fetch")
    if row.price_basis not in {"package", "kg", "l", "piece"}:
        result.append("unknown_price_basis")
    if row.product.sale_model not in {
        "fixed_package", "sold_by_weight", "sold_by_piece", "variable_weight_package",
    }:
        result.append("unknown_sale_model")
    if row.product.sale_model in {"fixed_package", "variable_weight_package"} and not _package(row):
        result.append("unknown_package")
    if row.product.sale_model == "variable_weight_package" and row.price_basis == "package":
        result.append("variable_weight_total_not_comparable")
    expected_bases = {
        "fixed_package": {"package"}, "sold_by_piece": {"piece"},
        "sold_by_weight": {"kg", "l"}, "variable_weight_package": {"kg", "l"},
    }
    if (
        row.product.sale_model in expected_bases and row.price_basis is not None
        and row.price_basis not in expected_bases[row.product.sale_model]
    ):
        result.append("price_basis_inconsistent_with_sale_model")
    terms = row.terms
    if not terms.complete:
        result.append("unverified_price_conditions")
    if terms.eligibility == "user_specific":
        result.append("personal_offer_excluded")
    elif terms.eligibility not in {"public", "member"}:
        result.append("unknown_eligibility")
    if terms.eligibility == "member" and not terms.membership_program:
        result.append("unknown_membership")
    if terms.activation_required is None:
        result.append("unknown_activation_requirement")
    if terms.required_packages is None or terms.required_packages < 1:
        result.append("unknown_purchase_quantity")
    if terms.max_quantity is not None and terms.max_quantity < 1:
        result.append("invalid_purchase_limit")
    if terms.deposit_amount is None or terms.deposit_included is None:
        result.append("unknown_deposit")
    elif not terms.deposit_amount.is_finite() or terms.deposit_amount < 0:
        result.append("invalid_deposit")
    if terms.price_kind not in {"regular", "campaign"}:
        result.append("unknown_price_kind")
    if terms.price_kind == "campaign" and (terms.valid_from is None or terms.valid_to is None):
        result.append("unknown_campaign_window")
    local_day = now.astimezone(ZoneInfo("Europe/Stockholm")).date()
    if terms.valid_from and terms.valid_to and terms.valid_from > terms.valid_to:
        result.append("invalid_validity_window")
    if terms.valid_from and local_day < terms.valid_from:
        result.append("price_not_started")
    if terms.valid_to and local_day > terms.valid_to:
        result.append("price_expired")
    return result


def compare_source_observations(
    own: Sequence[EvaluationObservation],
    primat: Sequence[EvaluationObservation],
    *,
    now: datetime,
    documented_matches: Sequence[DocumentedIdentityMatch] = (),
    max_observation_gap: timedelta = timedelta(hours=1),
    policy: FreshnessPolicy | None = None,
) -> dict:
    """Compare only proved equivalent scopes. Primat is never assumed correct."""
    if not _aware(now) or max_observation_gap.total_seconds() < 0:
        raise ValueError("aware now and nonnegative observation gap required")
    active_policy = policy or FreshnessPolicy()
    own_left, primat_left = set(range(len(own))), set(range(len(primat)))
    pairs: list[tuple[int, int, str, str]] = []
    ambiguous: set[str] = set()
    for key_fn, method in ((_gtin, "gtin"),):
        left, right = defaultdict(list), defaultdict(list)
        for i in own_left:
            if key := key_fn(own[i]):
                left[key].append(i)
        for i in primat_left:
            if key := key_fn(primat[i]):
                right[key].append(i)
        for key in sorted(left.keys() & right.keys()):
            if len(left[key]) != 1 or len(right[key]) != 1:
                ambiguous.add(f"{method}:{key}")
                continue
            a, b = left[key][0], right[key][0]
            pairs.append((a, b, method, key))
            own_left.remove(a)
            primat_left.remove(b)
    for match in documented_matches:
        if not match.evidence_reference.strip():
            raise ValueError("manual identity mappings require retained evidence")
        left = [i for i in own_left if own[i].product.external_product_id == match.own_product_id]
        right = [
            i for i in primat_left
            if primat[i].product.external_product_id == match.primat_product_id
        ]
        if len(left) != 1 or len(right) != 1:
            continue
        a, b = left[0], right[0]
        if _gtin(own[a]) and _gtin(primat[b]) and _gtin(own[a]) != _gtin(primat[b]):
            raise ValueError("documented mapping contradicts valid GTINs")
        pairs.append((a, b, "documented_identity", match.evidence_reference))
        own_left.remove(a)
        primat_left.remove(b)
    outcomes, reasons = [], Counter()
    for a, b, method, evidence in pairs:
        left, right = own[a], primat[b]
        blockers = [
            f"{source}:{reason}"
            for source, row in (("own", left), ("primat", right))
            for reason in _blockers(row, now=now, policy=active_policy)
        ]
        fields = {
            "store": (left.physical_store_id, right.physical_store_id),
            "channel": (left.channel, right.channel),
            "package": (_package(left), _package(right)),
            "sale_model": (left.product.sale_model, right.product.sale_model),
            "price_basis": (left.price_basis, right.price_basis),
            "conditions": (left.terms, right.terms),
        }
        blockers += [f"different_{field}" for field, values in fields.items() if values[0] != values[1]]
        gap = None
        if _aware(left.observed_at) and _aware(right.observed_at):
            gap = abs((left.observed_at - right.observed_at).total_seconds())
            if gap > max_observation_gap.total_seconds():
                blockers.append("observation_gap_exceeded")
        reasons.update(blockers)
        delta = None if blockers else left.product.sale_price - right.product.sale_price
        outcomes.append({
            "own_product_id": left.product.external_product_id,
            "primat_product_id": right.product.external_product_id,
            "identity_method": method, "identity_evidence": evidence,
            "comparable": not blockers, "blockers": blockers,
            "own_observed_price": str(left.product.sale_price)
            if left.product.sale_price is not None else None,
            "primat_observed_price": str(right.product.sale_price)
            if right.product.sale_price is not None else None,
            "observation_gap_seconds": gap,
            "own_minus_primat_price": str(delta) if delta is not None else None,
        })
    return {
        "report_version": "strict-source-evaluation-v1",
        "evaluated_at": now.astimezone(UTC).isoformat(),
        "maximum_observation_gap_seconds": max_observation_gap.total_seconds(),
        "freshness_policy": active_policy.model_dump(),
        "own_records": len(own), "primat_records": len(primat),
        "identity_matches": len(pairs), "ambiguous_identity_keys": sorted(ambiguous),
        "own_without_identity_match": len(own_left),
        "primat_without_identity_match": len(primat_left),
        "comparable_prices": sum(row["comparable"] for row in outcomes),
        "equal_prices": sum(
            row["comparable"] and Decimal(row["own_minus_primat_price"]) == 0 for row in outcomes
        ),
        "different_prices": sum(
            row["comparable"] and Decimal(row["own_minus_primat_price"]) != 0 for row in outcomes
        ),
        "blocker_counts": dict(sorted(reasons.items())), "pairs": outcomes,
        "missing_product_means": "not_observed; availability_not_inferred",
        "reference_policy": "Neither source is presumed correct; investigate official evidence.",
    }


def evaluate_recipe_coverage(
    rows: Sequence[EvaluationObservation],
    recipes: Sequence[RecipeDemand],
    *,
    now: datetime,
    memberships: frozenset[str] = frozenset(),
    policy: FreshnessPolicy | None = None,
) -> dict:
    """Ingredient/recipe source coverage, not nutrition or basket feasibility.

    Caller normalizes actual recipes and product canonical identities with the
    existing normalizer. No fuzzy names, density or piece-weight conversions.
    Member coverage is conditional; activation-required prices are excluded.
    """
    if not _aware(now):
        raise ValueError("now must be timezone-aware")
    if len({r.recipe_id for r in recipes}) != len(recipes):
        raise ValueError("recipe identifiers must be unique")
    active_policy = policy or FreshnessPolicy()
    counts = Counter(_identity(row) for row in rows)
    eligible: dict[tuple[str, str], set[str]] = defaultdict(set)
    recognized: dict[tuple[str, str], set[str]] = defaultdict(set)
    preliminary: dict[tuple[str, str], set[str]] = defaultdict(set)
    source_labels: dict[str, set[str]] = defaultdict(set)
    failures, freshness = Counter(), Counter()
    ages: list[float] = []
    accepted = 0
    for row in rows:
        reasons = _blockers(row, now=now, policy=active_policy)
        identity = _identity(row)
        if identity and row.canonical_food:
            source_labels[row.canonical_food].add(identity)
        if identity is None:
            reasons.append("missing_product_identity")
        elif counts[identity] > 1:
            reasons.append("duplicate_product_identity")
        if row.semantic_confidence not in {"exact", "high", "medium"} or not row.canonical_food:
            reasons.append("unknown_or_rejected_food_semantics")
        elif identity and row.usable_unit:
            recognized[(row.canonical_food, row.usable_unit)].add(identity)
        if (
            row.quantity_confidence not in {"exact", "derived"}
            or row.usable_quantity is None
            or not row.usable_quantity.is_finite()
            or row.usable_quantity <= 0
            or row.usable_unit not in {"g", "ml", "st"}
        ):
            reasons.append("no_exact_or_derived_usable_quantity")
        if row.terms.eligibility == "member" and row.terms.membership_program not in memberships:
            reasons.append("membership_required")
        if row.terms.activation_required is True:
            reasons.append("activation_required")
        if (
            identity and counts[identity] == 1 and not row.quarantined
            and row.canonical_food and row.semantic_confidence in {"exact", "high", "medium"}
            and row.quantity_confidence in {"exact", "derived"}
            and row.usable_quantity is not None and row.usable_quantity.is_finite()
            and row.usable_quantity > 0 and row.usable_unit in {"g", "ml", "st"}
            and row.product.sale_price is not None
            and row.product.sale_model in {"fixed_package", "sold_by_weight", "sold_by_piece"}
            and _aware(row.observed_at) and row.observed_at <= now
            and assess_freshness(row.observed_at, now=now, policy=active_policy).usable
        ):
            preliminary[(row.canonical_food, row.usable_unit)].add(identity)
        if _aware(row.observed_at) and row.observed_at <= now:
            age = (now - row.observed_at).total_seconds() / 3600
            ages.append(age)
            freshness[assess_freshness(row.observed_at, now=now, policy=active_policy).state] += 1
        else:
            freshness["unknown_or_future"] += 1
        failures.update(reasons)
        if not reasons:
            accepted += 1
            eligible[(row.canonical_food, row.usable_unit)].add(identity)
    demand_frequency = Counter(item for recipe in recipes for item in recipe.ingredients)
    covered = {key for key in demand_frequency if eligible[key]}
    lines = sum(demand_frequency.values())
    covered_lines = sum(demand_frequency[key] for key in covered)
    complete = sum(all(item in covered for item in recipe.ingredients) for recipe in recipes)
    return {
        "report_version": "actual-recipe-source-coverage-v1",
        "evaluated_at": now.astimezone(UTC).isoformat(),
        "freshness_policy": active_policy.model_dump(),
        "records": len(rows), "accepted_records": accepted,
        "rejected_records": len(rows) - accepted, "rejection_reasons": dict(sorted(failures.items())),
        "freshness_counts": dict(freshness),
        "minimum_observation_age_hours": min(ages) if ages else None,
        "maximum_observation_age_hours": max(ages) if ages else None,
        "recipe_count": len(recipes), "recipes_with_all_ingredient_sources": complete,
        "ingredient_unit_requirements": len(demand_frequency),
        "covered_ingredient_unit_requirements": len(covered),
        "ingredient_lines": lines, "covered_ingredient_lines": covered_lines,
        "ingredient_line_coverage": covered_lines / lines if lines else None,
        "preliminary_recognized_requirements": sum(bool(recognized[key]) for key in demand_frequency),
        "preliminary_recognized_lines": sum(
            frequency for key, frequency in demand_frequency.items() if recognized[key]
        ),
        "preliminary_priced_quantity_requirements": sum(
            bool(preliminary[key]) for key in demand_frequency
        ),
        "preliminary_priced_quantity_lines": sum(
            frequency for key, frequency in demand_frequency.items() if preliminary[key]
        ),
        "preliminary_limit": "Observed positive price + recognized food/quantity only. Price "
                             "conditions, scope and current validity remain unverified; this "
                             "is not a shared approved price or evidence of a feasible recipe.",
        "ingredients": [
            {"canonical_food": food, "unit": unit, "recipe_lines": frequency,
             "unreviewed_source_label_candidates": len(source_labels[food]),
             "recognized_product_candidates": len(recognized[(food, unit)]),
             "preliminary_priced_quantity_candidates": len(preliminary[(food, unit)]),
             "usable_product_candidates": len(eligible[(food, unit)])}
            for (food, unit), frequency in sorted(demand_frequency.items())
        ],
        "scope": "Source candidates only; package counts, promotion limits, nutrition and cooking "
                 "suitability still require the existing planner. No missing-product stock inference.",
    }
