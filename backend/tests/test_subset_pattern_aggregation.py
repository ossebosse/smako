"""Structural reuse must retain every scalar winner, amount and Decimal flag."""
from decimal import localcontext
from itertools import combinations
from random import Random

from app.models import NormalizedIngredient
from app.services.basket_optimizer import BasketOptimizer, _QuoteCacheSession

from backend.tests.test_search_reuse import _product


def test_structural_patterns_match_exhaustive_quotes_and_plain_aggregation():
    rng = Random(7216)
    optimizer = BasketOptimizer()
    ids = tuple('abcdefg')
    with optimizer.quote_cache():
        session = optimizer._quote_cache_context.get()
        for case in range(12):
            # Ties, missing stores, multiple products and changing package
            # counts exercise the complete order, not just the cheapest price.
            products = tuple(
                _product('x', rng.choice((1, 2, 5)), store_id=store,
                         product_id=f'{store}-{j}', package_quantity=rng.choice((1, 3, 7)))
                for store in ids if rng.random() > .25 for j in range(2)
            )
            for limit in (1, 2, 4):
                subsets = tuple(c for size in range(1, limit + 1) for c in combinations(ids, size))
                vectors = []
                for quantity in (1, 2, 9):
                    ingredient = NormalizedIngredient(canonical_name=f'x-{case}',
                                                      required_quantity=quantity, unit='st')
                    quotes, key = optimizer._candidate_quotes_with_key(ingredient, products)
                    vector = optimizer._quote_subset_vector(quotes, key, ids, subsets, limit)
                    assert tuple(s.quote for s in vector) == tuple(
                        optimizer._cheapest_quote(quotes, set(subset)) for subset in subsets
                    )
                    vectors.append(vector)
                for precision in (28, 3, 40, 28):
                    with localcontext() as ctx:
                        ctx.prec = precision
                        ctx.clear_flags()
                        expected = optimizer._grouped_subset_keys(
                            vectors, subsets, limit, _QuoteCacheSession(), winning_mask=True,
                        )
                        flags = ctx.flags.copy()
                        ctx.clear_flags()
                        actual = optimizer._grouped_subset_keys(
                            vectors, subsets, limit, session, winning_mask=True,
                        )
                        assert actual == expected
                        assert ctx.flags == flags
                        assert [None if key is None else key[1].as_tuple() for key in actual[0]] == [
                            None if key is None else key[1].as_tuple() for key in expected[0]
                        ]
        assert session.vector_groups and session.subset_memberships
    assert not session.vector_groups and not session.subset_memberships
