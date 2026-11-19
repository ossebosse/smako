"""A fixed package with offers reuses its same-count quote exactly.

The checkout of a fixed package (offer choice, multibuy groups, member caps,
deposits) depends only on the package count. These tests compare the reused
quote with a fresh full quote for every field, over many quantities, and the
per-store winners with the full quote set.
"""
import random
from datetime import date

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import OfferKind, OfferMetadata, ProductCandidate
from app.services.basket_calculator import BasketCalculator
from app.services.basket_optimizer import BasketOptimizer


def fixed(product_id, store_id, size, price, offers, *, effective=None, unit="g", **extra):
    return ProductCandidate(
        product_id=product_id, product_name=product_id, canonical_name="vara",
        store_id=store_id, store_name=store_id, package_quantity=size, package_unit=unit,
        price=price, effective_price=effective if effective is not None else price, match_score=1,
        sale_model="fixed_package", quantity_confidence="exact", offers=offers,
        purchase_date=date(2026, 11, 19), **extra)


def offer_candidates():
    multibuy = OfferMetadata(kind=OfferKind.MULTIPACK, description="3 för 90 kr", price=90, required_packages=3)
    capped_member = OfferMetadata(kind=OfferKind.MEMBER, description="Medlemspris 39 kr, max 2 st",
                                  price=39, max_quantity=2, member_program="Coop medlem")
    capped_multibuy = OfferMetadata(kind=OfferKind.MULTIPACK, description="2 för 105 kr, max 1 köp",
                                    price=105, required_packages=2, max_quantity=1)
    campaign = OfferMetadata(kind=OfferKind.CAMPAIGN, description="Kampanj 25 kr", price=25)
    expired = OfferMetadata(kind=OfferKind.CAMPAIGN, description="Slut", price=10,
                            valid_from=date(2026, 1, 1), valid_to=date(2026, 1, 31))
    return [
        fixed("multibuy", "s1", 400, 40, [multibuy]),
        fixed("member", "s1", 500, 59.57, [capped_member], effective=39),
        fixed("capped", "s2", 500, 74.65, [capped_multibuy]),
        fixed("campaign", "s2", 250, 32, [campaign], effective=25),
        fixed("expired", "s3", 300, 18, [expired]),
        fixed("two", "s3", 1000, 55, [multibuy, campaign], effective=25),
        fixed("drained", "s1", 400, 14, [multibuy], usable_quantity=235, usable_unit="g"),
        fixed("milk", "s2", 1500, 21.9, [capped_member], effective=19.9, unit="ml"),
    ]


def test_offer_package_quote_matches_full_quote_for_many_quantities():
    rng = random.Random(20261119)
    candidates = offer_candidates()
    calculator = BasketCalculator()
    optimizer = BasketOptimizer()
    with optimizer.quote_cache() as stats:
        for step in range(600):
            candidate = rng.choice(candidates)
            size = candidate.usable_quantity or candidate.package_quantity
            amount = rng.choice([round(rng.uniform(0.1, 6000), 2), rng.randint(1, 4000), float(rng.randint(1, 9) * size)])
            ingredient = NormalizedIngredient(canonical_name=f"vara [{step % 3}]", required_quantity=amount,
                                              unit=candidate.usable_unit or candidate.package_unit)
            try:
                expected = calculator.quote_item(ingredient, candidate)
            except ValueError as error:
                with pytest.raises(ValueError, match=str(error)[:20]):
                    optimizer._calculate_quote(ingredient, candidate)
                continue
            assert optimizer._calculate_quote(ingredient, candidate) == expected
        assert stats.fixed_template_hits > 300


def test_store_winners_with_offer_packages_match_full_quote_set():
    rng = random.Random(1119)
    candidates = tuple(offer_candidates()[:6])
    for _ in range(150):
        amount = rng.choice([round(rng.uniform(1, 5000), 1), rng.randint(1, 12) * 250])
        ingredient = NormalizedIngredient(canonical_name="vara", required_quantity=amount, unit="g")
        reference = BasketOptimizer()
        with reference.quote_cache():
            full, _key = reference._candidate_quotes_with_key(ingredient, candidates)
            expected = sorted(reference._store_minima(full), key=lambda q: q.store_id)
        optimizer = BasketOptimizer()
        with optimizer.quote_cache():
            # Warm the shapes and templates with other quantities first.
            for warm in (100, 777, 2400):
                optimizer._store_best_quotes_with_key(
                    NormalizedIngredient(canonical_name="vara", required_quantity=warm, unit="g"), candidates)
            winners, _key = optimizer._store_best_quotes_with_key(ingredient, candidates)
        assert sorted(winners, key=lambda q: q.store_id) == expected


def test_lower_bound_stops_early_only_above_the_limit():
    from decimal import Decimal

    candidates = offer_candidates()
    by_name = {f"vara {n}": tuple(c.model_copy(update={"canonical_name": f"vara {n}"}) for c in candidates)
               for n in range(5)}
    ingredients = [NormalizedIngredient(canonical_name=name, required_quantity=900 + 300 * n, unit="g")
                   for n, name in enumerate(by_name)]
    optimizer = BasketOptimizer()
    with optimizer.quote_cache():
        full = optimizer.lower_bound(ingredients, by_name)
        assert full is not None
        for limit in (Decimal(0), full / 3, full - Decimal("0.01"), full, full + 1):
            early = optimizer.lower_bound(ingredients, by_name, stop_above=limit)
            # Same pruning decision as the full bound, never a larger value.
            assert (early > limit) == (full > limit)
            assert early <= full
