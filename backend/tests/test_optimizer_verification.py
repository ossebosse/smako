from __future__ import annotations

from collections.abc import Iterable

import pytest
from app.errors import IncompleteBasketError
from app.models.basket import BasketVerificationStatus
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.models.store import Store
from app.services.basket_auditor import BasketAuditor
from app.services.basket_optimizer import BasketOptimizer, BasketVerificationPolicy
from app.services.meal_plan_optimizer import _strict_price_improvement
from app.services.menu_optimizer import MenuOptimizer


def _store() -> Store:
    return Store(
        store_id="store",
        name="Store",
        chain="Test",
        city="Lund",
        postal_code="22350",
    )


def _ingredient(name: str = "kyckling") -> NormalizedIngredient:
    return NormalizedIngredient(canonical_name=name, required_quantity=500, unit="g")


def _candidate(
    product_id: str,
    price: float,
    *,
    ingredient: str = "kyckling",
    role: str = "thigh",
    semantic_confidence: SemanticConfidence = SemanticConfidence.HIGH,
    quantity_confidence: QuantityConfidence = QuantityConfidence.EXACT,
    evidence: list[str] | None = None,
) -> ProductCandidate:
    return ProductCandidate(
        product_id=product_id,
        product_name=product_id,
        canonical_name=ingredient,
        canonical_food="chicken" if ingredient == "kyckling" else ingredient,
        food_family="poultry" if ingredient == "kyckling" else "test",
        product_role=role,
        product_form="meat",
        semantic_confidence=semantic_confidence,
        semantic_evidence=evidence or [f"visible_role:{role}"],
        store_id="store",
        store_name="Store",
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=500,
        package_unit="g",
        usable_quantity=500,
        usable_unit="g",
        quantity_confidence=quantity_confidence,
        sale_price=price,
        price=price,
        effective_price=price,
        match_score=1,
    )


@pytest.mark.parametrize(
    "unsafe_confidence",
    [SemanticConfidence.LOW, SemanticConfidence.REJECTED],
)
def test_strict_policy_never_lets_cheap_chicken_heart_beat_valid_thigh(
    unsafe_confidence: SemanticConfidence,
) -> None:
    optimizer = BasketOptimizer(verification_policy=BasketVerificationPolicy())
    candidates = {
        "kyckling": [
            _candidate(
                "Kycklinghjärta Fryst",
                1,
                role="heart",
                semantic_confidence=unsafe_confidence,
                evidence=["visible_role:heart", "excluded_role:heart"],
            ),
            _candidate("Kycklinglårfilé", 100),
        ]
    }

    basket = optimizer.optimize([_ingredient()], candidates, [_store()], max_stores=1)

    assert basket.stores[0].items[0].product_id == "Kycklinglårfilé"
    assert basket.verification_status == BasketVerificationStatus.VERIFIED


def test_strict_policy_prefers_verified_quantity_over_unknown_cheaper_product() -> None:
    candidates = {
        "kyckling": [
            _candidate(
                "unknown-quantity",
                1,
                quantity_confidence=QuantityConfidence.UNKNOWN,
            ),
            _candidate("verified-quantity", 50),
        ]
    }

    basket = BasketOptimizer(verification_policy=BasketVerificationPolicy()).optimize(
        [_ingredient()], candidates, [_store()], max_stores=1
    )

    assert basket.stores[0].items[0].product_id == "verified-quantity"
    assert basket.verification_status == BasketVerificationStatus.VERIFIED


def test_verification_rank_places_estimate_before_unknown_even_when_it_costs_more() -> None:
    policy = BasketVerificationPolicy(
        allow_unknown_quantities=True,
        allow_unknown_sale_model=False,
    )
    candidates = {
        "kyckling": [
            _candidate(
                "unknown",
                1,
                quantity_confidence=QuantityConfidence.UNKNOWN,
            ),
            _candidate(
                "estimated",
                30,
                quantity_confidence=QuantityConfidence.ESTIMATED,
            ),
        ]
    }

    basket = BasketOptimizer(verification_policy=policy).optimize(
        [_ingredient()], candidates, [_store()], max_stores=1
    )

    assert basket.stores[0].items[0].product_id == "estimated"
    assert basket.verification_status == BasketVerificationStatus.VERIFIED_WITH_ESTIMATES


def test_verified_quote_ranks_before_cheaper_estimate() -> None:
    candidates = {
        "kyckling": [
            _candidate(
                "estimated",
                1,
                quantity_confidence=QuantityConfidence.ESTIMATED,
            ),
            _candidate("verified", 30),
        ]
    }

    basket = BasketOptimizer(verification_policy=BasketVerificationPolicy()).optimize(
        [_ingredient()], candidates, [_store()], max_stores=1
    )

    assert basket.stores[0].items[0].product_id == "verified"
    assert basket.verification_status == BasketVerificationStatus.VERIFIED


def test_plan_challenger_prefers_verified_even_when_estimate_is_cheaper() -> None:
    optimizer = BasketOptimizer(verification_policy=BasketVerificationPolicy())
    estimated = optimizer.optimize(
        [_ingredient()],
        {
            "kyckling": [
                _candidate(
                    "estimated",
                    1,
                    quantity_confidence=QuantityConfidence.ESTIMATED,
                )
            ]
        },
        [_store()],
        max_stores=1,
    )
    verified = optimizer.optimize(
        [_ingredient()],
        {"kyckling": [_candidate("verified", 30)]},
        [_store()],
        max_stores=1,
    )

    assert _strict_price_improvement(verified, estimated)
    assert not _strict_price_improvement(estimated, verified)


def test_medium_semantics_are_only_eligible_when_policy_explicitly_allows_them() -> None:
    candidates = {
        "kyckling": [
            _candidate(
                "medium",
                1,
                semantic_confidence=SemanticConfidence.MEDIUM,
            ),
            _candidate("high", 30),
        ]
    }

    strict = BasketOptimizer(verification_policy=BasketVerificationPolicy()).optimize(
        [_ingredient()], candidates, [_store()], max_stores=1
    )
    medium_allowed = BasketOptimizer(
        verification_policy=BasketVerificationPolicy(allow_medium_semantic=True)
    ).optimize([_ingredient()], candidates, [_store()], max_stores=1)

    assert strict.stores[0].items[0].product_id == "high"
    assert medium_allowed.stores[0].items[0].product_id == "medium"


def _recipe(name: str, ingredients: Iterable[tuple[str, float]]) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=ingredient,
                canonical_name=ingredient,
                quantity=quantity,
                unit="g",
            )
            for ingredient, quantity in ingredients
        ],
        instructions=["Tillaga."],
    )


def test_menu_state_ordering_prefers_verified_recipe_before_cheaper_unverified_one() -> None:
    recipes = [_recipe("Osäker", [("a", 500)]), _recipe("Verifierad", [("b", 500)])]
    candidates = {
        "a": [
            _candidate(
                "cheap-unknown",
                1,
                ingredient="a",
                role="staple",
                quantity_confidence=QuantityConfidence.UNKNOWN,
            )
        ],
        "b": [_candidate("costly-verified", 30, ingredient="b", role="staple")],
    }

    result = MenuOptimizer(
        basket_optimizer=BasketOptimizer(
            verification_policy=BasketVerificationPolicy.legacy_compatible()
        )
    ).optimize(
        recipes,
        candidates,
        [_store()],
        recipe_count=1,
        max_stores=1,
        beam_width=2,
    )

    assert [recipe.name for recipe in result.recipes] == ["Verifierad"]
    assert result.basket.verification_status == BasketVerificationStatus.VERIFIED


class _InvalidVerificationAuditor(BasketAuditor):
    def audit(self, *args, **kwargs):
        result = super().audit(*args, **kwargs)
        return result.model_copy(update={"verification_status": BasketVerificationStatus.INVALID})


def test_strict_menu_rejects_an_audit_marked_invalid() -> None:
    optimizer = MenuOptimizer(
        basket_optimizer=BasketOptimizer(verification_policy=BasketVerificationPolicy()),
        basket_auditor=_InvalidVerificationAuditor(),
    )

    with pytest.raises(IncompleteBasketError):
        optimizer.optimize(
            [_recipe("Rätt", [("kyckling", 500)])],
            {"kyckling": [_candidate("valid", 30)]},
            [_store()],
            recipe_count=1,
            max_stores=1,
        )


def test_quote_cache_fingerprint_includes_semantic_and_purchase_interpretation() -> None:
    base = _candidate("candidate", 30)
    changes: list[dict[str, object]] = [
        {"canonical_food": "other"},
        {"food_family": "other"},
        {"product_role": "breast"},
        {"product_form": "fillet"},
        {"semantic_confidence": SemanticConfidence.EXACT},
        {"semantic_evidence": ["structured_semantics_match"]},
        {"sale_model": SaleModel.VARIABLE_WEIGHT_PACKAGE},
        {"sale_price": 31.0},
        {"sale_unit": "kg"},
        {"comparison_price": 60.0, "comparison_unit": "kg"},
        {"piece_price": 3.0},
        {"estimated_piece_weight": 175.0},
        {"estimated_piece_weight_unit": "st"},
    ]
    base_fingerprint = BasketOptimizer._build_candidate_fingerprint(base)

    assert all(
        BasketOptimizer._build_candidate_fingerprint(base.model_copy(update=change))
        != base_fingerprint
        for change in changes
    )
