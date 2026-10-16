"""Ecological search must match exhaustive checkout, including its first tie."""

from contextlib import contextmanager
from random import Random
from unittest.mock import patch

import pytest
from app.models.personal import ExtraNeed
from app.models.product import OfferMetadata
from app.services.basket_optimizer import BasketOptimizer
from app.services.performance_trace import activate_performance_trace
from app.services.personal_policy import ProductFacts

from backend.tests.test_personal_planning_v2 import prepared, product, request, run


@contextmanager
def exhaustive_checkout():
    # Zero is strictly below every positive fixture basket. Disable both new
    # pruning levels while retaining the original authoritative optimization.
    with (patch.object(BasketOptimizer, "restriction_cost_bounds", return_value=None),
          patch.object(BasketOptimizer, "same_depth_nested_store_limited_keys", return_value=((0, 0, 1),))):
        yield


def fixture(seed, *, ties=False):
    rng = Random(seed)
    products, facts = [], {}
    names = ("mjölk", "bröd", "ris", "pasta", "potatis")
    for store in ("coop", "ica", "willys"):
        for name in names:
            for organic in (False, True):
                identity = f"{name}-{'z-eco' if organic else 'a-plain'}"
                price = 10 if ties else rng.randint(8, 25) + 12 * organic
                offers = [] if ties or rng.random() > .3 else [
                    OfferMetadata(kind="campaign", description="synthetic", price=price - 3)]
                products.append(product(name, 1000, "g", price, identity=identity,
                                        store=store, offers=offers))
                facts[(store, identity)] = ProductFacts(
                    source="label", source_product_id=identity,
                    source_snapshot_id="v2-frozen", organic=organic)
    req = request(
        extras=[ExtraNeed(query=n, quantity=1000 if ties else rng.randint(501, 2200),
                          unit="g", confirmed=True) for n in names],
        organic_percent=(20, 50, 100)[seed % 3],
    )
    req.max_stores = 1 + seed % 2
    return prepared(*products), req, facts


@pytest.mark.parametrize("seed", range(12))
def test_bounds_preserve_exhaustive_basket_offers_packages_store_cap_and_savings(seed):
    p, req, facts = fixture(seed)
    # Disabling the new bounds executes every original subset in its
    # original order through the same checkout engine (no alternate prices).
    with exhaustive_checkout():
        expected = run(p, req, facts=facts)
    with activate_performance_trace() as trace:
        actual = run(p, req, facts=facts)
    assert actual.optimized_basket == expected.optimized_basket
    assert actual.personal.checks == expected.personal.checks
    counters = trace.snapshot().operation_counters
    if seed % 3 == 0:
        assert counters.get("ecological_subsets_pruned_cost", 0) + counters.get("ecological_subsets_pruned_exact_cost", 0) > 0


def test_equal_cost_retains_first_subset_and_its_exact_savings():
    p, req, facts = fixture(0, ties=True)
    with exhaustive_checkout():
        expected = run(p, req, facts=facts)
    with activate_performance_trace() as trace:
        actual = run(p, req, facts=facts)
    assert actual.optimized_basket == expected.optimized_basket
    assert actual.personal.checks["organic_cost_percent"] == 100
    assert trace.snapshot().operation_counters["ecological_subsets_pruned_cost"] >= 30


def test_coupled_promotion_cannot_use_independent_line_bounds():
    from app.models import NormalizedIngredient, ProductCandidate

    from backend.tests.test_promotion_groups import catalog, group

    p = catalog(group())
    candidates = {v.name: (ProductCandidate.from_product(v, match_score=1),)
                  for v in p.universe.products}
    needs = [NormalizedIngredient(canonical_name=n, required_quantity=1000, unit=u)
             for n, u in (("mjölk", "ml"), ("bröd", "g"), ("ris", "g"))]
    optimizer = BasketOptimizer()
    assert optimizer.restriction_cost_bounds(
        needs, candidates, candidates, allowed_store_ids=["coop"]) is None
    assert optimizer.optimize(needs, candidates, p.stores, max_stores=1).total == 75


def test_ecological_pair_discount_beats_independent_line_prices():
    from backend.tests.test_promotion_groups import group

    promotion = group(eligible_product_ids=("mjölk-eco", "bröd-eco"),
                      required_packages=2, amount=16)
    products, facts = [], {}
    for name in ("mjölk", "bröd", "ris"):
        for organic in (False, True):
            identity = name + ("-eco" if organic else "-plain")
            products.append(product(name, 1000, "g", 30 if organic else 5, identity=identity,
                                    promotion_groups=(promotion,) if identity in promotion.eligible_product_ids else ()))
            facts[("coop", identity)] = ProductFacts(
                source="label", source_product_id=identity, source_snapshot_id="v2-frozen", organic=organic)
    req = request(extras=[ExtraNeed(query=n, quantity=1000, unit="g", confirmed=True)
                          for n in ("mjölk", "bröd", "ris")], organic_percent=50)
    p = prepared(*products)
    with exhaustive_checkout():
        expected = run(p, req, facts=facts)
    actual = run(p, req, facts=facts)
    assert actual.optimized_basket == expected.optimized_basket
    assert actual.optimized_basket.total == 21
    assert actual.personal.checks["checkout_audit"]["passed"]


def test_shared_offer_only_cap_disables_independent_bounds():
    from app.models import NormalizedIngredient, ProductCandidate

    candidate = ProductCandidate.from_product(product("ris", 1000, "g", 10), match_score=1).model_copy(
        update={"price": None, "offers": [OfferMetadata(kind="campaign", description="synthetic cap",
                                                       price=5, max_quantity=1)]})
    rows = {name: (candidate,) for name in ("ris [1]", "ris [2]")}
    needs = [NormalizedIngredient(canonical_name=name, required_quantity=1000, unit="g") for name in rows]
    assert BasketOptimizer().restriction_cost_bounds(needs, rows, rows, allowed_store_ids=["coop"]) is None
