from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from grocery_data.app.services.primat_comparison import ComparisonRecord
from grocery_data.app.services.source_evaluation import (
    DocumentedIdentityMatch,
    EvaluationObservation,
    EvaluationTerms,
    RecipeDemand,
    compare_source_observations,
    evaluate_recipe_coverage,
)

NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def observation(source="own", **changes):
    row = EvaluationObservation(
        product=ComparisonRecord(
            source=source, gtin="7310865004703", external_product_id=f"{source}-milk",
            name="Mjölk", sale_price=Decimal("15.90"), package_quantity=Decimal(1000),
            package_unit="ml", sale_model="fixed_package",
        ),
        physical_store_id="ica:gunnesbo", channel="online", scope_evidence="fixture:store-map",
        observed_at=NOW, fetched_at=NOW, price_basis="package",
        terms=EvaluationTerms(
            price_kind="regular", eligibility="public", activation_required=False,
            required_packages=1, deposit_amount=Decimal(0), deposit_included=False, complete=True,
        ),
        canonical_food="milk", usable_quantity=Decimal(1000), usable_unit="ml",
        semantic_confidence="high", quantity_confidence="exact",
    )
    return replace(row, **changes)


def compare(own=None, primat=None, **changes):
    return compare_source_observations(
        own or [observation()], primat or [observation("primat")], now=NOW, **changes,
    )


def test_exact_identity_still_requires_store_channel_and_package_agreement():
    result = compare()
    assert result["comparable_prices"] == 1
    assert result["equal_prices"] == 1
    right = observation("primat", physical_store_id="ica:clemen", channel="physical")
    right = replace(right, product=right.product.model_copy(update={"package_quantity": Decimal(1500)}))
    result = compare(primat=[right])
    assert result["comparable_prices"] == 0
    assert {"different_store", "different_channel", "different_package"} <= set(result["blocker_counts"])


def test_same_names_never_create_identity_matches():
    left = observation()
    right = observation("primat")
    left = replace(left, product=left.product.model_copy(update={"gtin": None}))
    right = replace(right, product=right.product.model_copy(update={"gtin": None}))
    assert compare([left], [right])["identity_matches"] == 0
    result = compare([left], [right], documented_matches=[DocumentedIdentityMatch(
        "own-milk", "primat-milk", "fixture:reviewed-exact-retailer-product-code",
    )])
    assert result["comparable_prices"] == 1
    assert result["pairs"][0]["identity_method"] == "documented_identity"
    with pytest.raises(ValueError, match="retained evidence"):
        compare([left], [right], documented_matches=[DocumentedIdentityMatch(
            "own-milk", "primat-milk", " ",
        )])


@pytest.mark.parametrize("terms,reason", [
    ({"eligibility": "user_specific"}, "personal_offer_excluded"),
    ({"complete": False}, "unverified_price_conditions"),
    ({"activation_required": None}, "unknown_activation_requirement"),
    ({"deposit_amount": None}, "unknown_deposit"),
    ({"price_kind": "campaign"}, "unknown_campaign_window"),
    ({"valid_to": date(2026, 9, 13)}, "price_expired"),
    ({"valid_from": date(2026, 9, 15)}, "price_not_started"),
])
def test_unknown_and_personal_conditions_fail_closed(terms, reason):
    left = observation()
    left = replace(left, terms=replace(left.terms, **terms))
    result = compare([left])
    assert result["comparable_prices"] == 0
    assert f"own:{reason}" in result["blocker_counts"]


@pytest.mark.parametrize("changes", [
    {"required_packages": 2}, {"max_quantity": 4}, {"activation_required": True},
    {"deposit_amount": Decimal(2)}, {"deposit_included": True},
    {"eligibility": "member", "membership_program": "ica_stammis"},
])
def test_multibuy_limits_activation_membership_and_deposit_must_match(changes):
    left = observation()
    result = compare([replace(left, terms=replace(left.terms, **changes))])
    assert result["comparable_prices"] == 0
    assert "different_conditions" in result["blocker_counts"]


def test_old_observation_is_not_refreshed_by_new_fetch_or_build():
    left = observation(observed_at=NOW - timedelta(hours=48))
    result = compare([left])
    assert "own:stale_price" in result["blocker_counts"]
    assert "observation_gap_exceeded" in result["blocker_counts"]
    assert compare([observation(observed_at=NOW + timedelta(seconds=1))])["comparable_prices"] == 0
    assert compare([observation(observed_at=None)])["comparable_prices"] == 0


def test_stock_and_variable_weight_total_are_never_inferred():
    left = observation()
    left = replace(left, product=left.product.model_copy(update={"sale_model": "variable_weight_package"}))
    result = compare([left])
    assert "own:variable_weight_total_not_comparable" in result["blocker_counts"]
    assert result["missing_product_means"] == "not_observed; availability_not_inferred"


def test_duplicate_identity_cannot_inflate_matches_or_recipe_coverage():
    result = compare([observation(), observation()])
    assert result["comparable_prices"] == 0
    assert len(result["ambiguous_identity_keys"]) == 1
    coverage = evaluate_recipe_coverage(
        [observation(), observation()], [RecipeDemand("milk-recipe", (("milk", "ml"),))], now=NOW,
    )
    assert coverage["accepted_records"] == 0
    assert coverage["rejection_reasons"]["duplicate_product_identity"] == 2


def test_actual_recipe_frequency_and_units_retain_missing_requirements():
    recipes = [
        RecipeDemand("breakfast", (("milk", "ml"), ("eggs", "st"))),
        RecipeDemand("snack", (("milk", "ml"),)),
        RecipeDemand("weight-recipe", (("milk", "g"),)),
    ]
    result = evaluate_recipe_coverage([observation()], recipes, now=NOW)
    assert result["ingredient_unit_requirements"] == 3
    assert result["covered_ingredient_unit_requirements"] == 1
    assert result["covered_ingredient_lines"] == 2
    assert result["ingredient_lines"] == 4
    assert result["ingredient_line_coverage"] == 0.5
    assert result["recipes_with_all_ingredient_sources"] == 1


def test_member_coverage_is_explicitly_conditional_and_activation_excluded():
    row = observation()
    row = replace(row, terms=replace(row.terms, eligibility="member", membership_program="ica"))
    recipes = [RecipeDemand("breakfast", (("milk", "ml"),))]
    assert evaluate_recipe_coverage([row], recipes, now=NOW)["accepted_records"] == 0
    assert evaluate_recipe_coverage(
        [row], recipes, now=NOW, memberships=frozenset({"ica"}),
    )["accepted_records"] == 1
    activated = replace(row, terms=replace(row.terms, activation_required=True))
    assert evaluate_recipe_coverage(
        [activated], recipes, now=NOW, memberships=frozenset({"ica"}),
    )["accepted_records"] == 0


def test_freshness_boundaries_reuse_operational_policy():
    recipes = [RecipeDemand("breakfast", (("milk", "ml"),))]
    for hours, state, accepted in ((35.99, "fresh", 1), (36, "aging", 1), (48, "stale", 0)):
        result = evaluate_recipe_coverage(
            [observation(observed_at=NOW - timedelta(hours=hours))], recipes, now=NOW,
        )
        assert result["freshness_counts"] == {state: 1}
        assert result["accepted_records"] == accepted


def test_preliminary_ingredient_signal_is_distinct_from_approved_coverage():
    row = observation(terms=EvaluationTerms())
    result = evaluate_recipe_coverage(
        [row], [RecipeDemand("breakfast", (("milk", "ml"),))], now=NOW,
    )
    assert result["accepted_records"] == 0
    assert result["covered_ingredient_lines"] == 0
    assert result["preliminary_priced_quantity_lines"] == 1
    assert result["ingredients"][0]["unreviewed_source_label_candidates"] == 1


def test_identical_inconsistent_sale_model_and_price_basis_are_not_comparable():
    row = observation(price_basis="kg")
    result = compare([row], [row])
    assert result["comparable_prices"] == 0
    assert "own:price_basis_inconsistent_with_sale_model" in result["blocker_counts"]


def test_stockholm_midnight_is_offer_date_boundary():
    now = datetime(2026, 9, 13, 22, tzinfo=UTC)
    row = observation(observed_at=now, fetched_at=now)
    row = replace(row, terms=replace(
        row.terms, price_kind="campaign", valid_from=date(2026, 9, 7), valid_to=date(2026, 9, 13),
    ))
    result = compare_source_observations([row], [row], now=now)
    assert "own:price_expired" in result["blocker_counts"]
