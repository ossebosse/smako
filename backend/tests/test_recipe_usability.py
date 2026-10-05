"""Shared boundaries: source-bound culinary facts and pure, bounded reuse."""
import hashlib
from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.config import Settings
from app.models.personal import TasteProfile
from app.services.complete_recipes import _supplier_classification, _whole_food_identity
from app.services.content_pack_requirements import compatible
from app.services.ingredient_normalizer import _canonicalize_name, canonicalize_ingredient_name
from app.services.official_product_facts import supplement_catalog_facts
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, request, state
from backend.tests.test_personal_qualified_facts import facts
from grocery_data.app.services.product_declarations import parse_santa_maria_culinary


def test_source_parser_preserves_case_and_never_synthesizes_nutrition():
    body = '<main><h1>Paprikapulver 200Gx6</h1><p>Paprika är mild och smakrik.</p></main>'.encode()
    acquisition = {'url': 'https://www.santamariaworld.com/se/produkter/paprika-stor/',
        'status': 200, 'observed_at': '2026-10-05T10:00:00+00:00', 'sha256': hashlib.sha256(body).hexdigest()}
    row = parse_santa_maria_culinary(body, acquisition)
    assert (row['package_quantity'], row['declared_case_units']) == (200, 6)
    assert row['gtin'] is None and 'nutrition' not in row and 'ingredients' not in row
    with pytest.raises(ValueError, match='unverified'):
        parse_santa_maria_culinary(body + b'changed', acquisition)
    with pytest.raises(ValueError, match='unverified'):
        parse_santa_maria_culinary(body, {**acquisition, 'url': 'https://example.org/se/produkter/test'})


def paprika(**changes):
    return product('Paprikapulver', 200, 'g', 42, brand='Santa Maria',
        gtin='7311311014499', sale_model='fixed_package').model_copy(update=changes)


def test_culinary_attribute_changes_only_its_declared_field():
    p = paprika()
    original = facts(p, ingredients=('Paprika.',), nutrition={'protein_g': 14},
        nutrition_unit='g', nutrition_basis='per 100 g', observed_at=NOW.isoformat())
    current = supplement_catalog_facts([p], {(p.store_id, p.product_id): original})[(p.store_id, p.product_id)]
    assert current.nutrition == original.nutrition
    assert current.observed_at == original.observed_at
    assert current.ingredients == original.ingredients
    assert not current.allergens_checked
    assert _supplier_classification(p, current, 'mild_spice')
    assert compatible(['paprika_powder'], p, current)
    for changes in ({'package_quantity': 37}, {'brand': 'Other'}, {'name': 'Paprikapulver stark'},
                    {'store_id': 'other'}, {'source_provenance': None}):
        assert not _supplier_classification(p.model_copy(update=changes), current, 'mild_spice')
        different = p.model_copy(update=changes)
        result = supplement_catalog_facts([different], {(different.store_id, different.product_id): original})
        if 'store_id' not in changes:
            assert 'mild_spice' not in result[(different.store_id, different.product_id)].product_classification
    blocked = replace(original, conflicts=('contradictory_source',))
    assert supplement_catalog_facts([p], {(p.store_id, p.product_id): blocked})[(p.store_id, p.product_id)] == blocked


@pytest.mark.parametrize('name,allowed', [('Risoni Pasta', True), ('Risoni', True),
    ('Risoni Pasta med ost', False), ('Risoni Kokt', False), ('Penne', False)])
def test_small_pasta_label_boundaries(name, allowed):
    p = SimpleNamespace(name=name, brand='Garant', category='Pasta')
    assert bool(_whole_food_identity('pasta', 'dry', p, None, ['pack:small_pasta'])) == allowed


def test_shell_egg_identity_does_not_assert_edible_mass():
    p = product('Ägg Frigående Inomhus 12-pack', 636, 'g', 40)
    f = facts(p, ingredients=('ÄGG',))
    assert _whole_food_identity('ägg', 'raw_edible', p, f)
    for name in ('Äggvita', 'Ägg kokta', 'Ägg i lag'):
        assert not _whole_food_identity('ägg', 'raw_edible', p.model_copy(update={'name': name}), f)
    assert not _whole_food_identity('ägg', 'raw_edible', p, replace(f, ingredients=('ägg, salt',)))
    assert not f.field_sources.get('usable_quantity')


def test_canonical_text_cache_is_bounded_and_retains_validation():
    for index in range(4100):
        canonicalize_ingredient_name('unmapped ' + str(index))
    assert _canonicalize_name.cache_info().currsize <= 4096
    assert canonicalize_ingredient_name('gul lök') != canonicalize_ingredient_name('rödlök')
    with pytest.raises(ValueError):
        canonicalize_ingredient_name([])


def test_negative_resolution_is_request_local_and_recreates_errors(monkeypatch):
    planner = PersonalPlanner(request(), Settings(), prepared(), state(), facts={}, now=NOW)
    profile = TasteProfile()
    for index in range(2):
        with pytest.raises(PolicyConflict) as error:
            planner.resolve('mjölk', 100, 'ml', profile=profile)
        assert error.value.stage is None
        error.value.stage = 'caller annotation'
    assert len(planner.lookup_failures) == 1
    # New facts/products never inherit a prior request's negative result.
    fresh = PersonalPlanner(request(), Settings(), prepared(product('mjölk', 1000, 'ml', 20)),
                            state(), facts={}, now=NOW)
    assert not fresh.lookup_failures
    assert fresh.resolve('mjölk', 100, 'ml', profile=profile)


@pytest.mark.parametrize('changes', [{'package_quantity': 400}, {'package_unit': 'ml'},
    {'name': 'Risoni Pasta med spenat'}, {'brand': 'Other'}, {'gtin': '7310130009716'}])
def test_manufacturer_declared_pasta_category_never_erases_variant_or_pack(changes):
    p = product('Risoni Pasta', 500, 'g', 20, brand='Garant', sale_model='fixed_package')
    result = supplement_catalog_facts([p], {})[(p.store_id, p.product_id)]
    assert result.nutrition['protein_g'] == 12
    assert result.ingredients == ('DURUMVETE. Kan innehålla spår av SOJA och SENAP.',)
    assert not result.allergens_checked and p.gtin is None
    bad = p.model_copy(update=changes)
    assert (bad.store_id, bad.product_id) not in supplement_catalog_facts([bad], {})


def test_apple_reference_is_generic_measured_edible_form_and_rejects_conflicts():
    from app.services.nutrition_reference import product_reference, reference_evidence
    p = product('Äpple Röda', 1000, 'g', 30).model_copy(update={'category': 'Frukt & grönt'})
    assert product_reference(p, 'äpple', None) == 588
    leaf = p.model_copy(update={'name': 'Äpple', 'category': 'Äpple'})
    assert product_reference(leaf, 'äpple', None) == 588
    assert product_reference(leaf.model_copy(update={'category': 'Skafferi'}), 'äpple', None) is None
    evidence = reference_evidence(588)
    assert evidence.nutrition_unit == 'g'
    assert evidence.ingredient == 'äpple med skal'
    for name in ('Äpple skalat', 'Äppelmos', 'Äpple Torkat', 'Äpple Fryst'):
        assert product_reference(p.model_copy(update={'name': name}), 'äpple', None) is None
    assert product_reference(p, 'äpple', facts(p, conflicts=('source conflict',))) is None


def test_vector_checkout_matches_scalar_subset_selection_with_ties_and_changed_amounts(monkeypatch):
    import random
    from decimal import Decimal

    from app.models import NormalizedIngredient
    from app.services.basket_optimizer import BasketOptimizer, _CompactQuoteSelection

    from backend.tests.test_search_reuse import _product, _store
    rng = random.Random(498)
    stores = [_store(s) for s in ('a', 'b', 'c', 'd')]
    for case in range(24):
        ingredients = [NormalizedIngredient(canonical_name=n, required_quantity=rng.randint(1, 10), unit='st')
                       for n in ('x', 'y', 'z')]
        products = {n: tuple(_product(n, rng.choice([2, 3, 5]), store_id=s,
                          package_quantity=rng.choice([2, 4, 7]), product_id=f'{n}-{s}-{j}')
                            for s in ('a', 'b', 'c', 'd') for j in range(2)) for n in ('x', 'y', 'z')}
        vector, scalar = BasketOptimizer(), BasketOptimizer()
        def reference(quotes, key, ids, subsets, limit, scalar=scalar):
            result = []
            for subset in subsets:
                quote = scalar._cheapest_quote(quotes, set(subset))
                result.append(_CompactQuoteSelection(quote=quote,
                    verification_rank=scalar.verification_policy.rank_for_quote(quote) if quote else 0,
                    total_price=quote.total_price if quote else Decimal(0),
                    store_id=quote.store_id if quote else None))
            return tuple(result)
        monkeypatch.setattr(scalar, '_quote_subset_vector', reference)
        with vector.quote_cache(), scalar.quote_cache():
            for cap in (1, 2, 4):
                assert vector.optimize(ingredients, products, stores, max_stores=cap) == scalar.optimize(
                    ingredients, products, stores, max_stores=cap)
                assert vector.optimize(ingredients, products, stores, max_stores=cap) == BasketOptimizer().optimize(
                    ingredients, products, stores, max_stores=cap)
                assert vector.optimize(ingredients, products, stores, max_stores=cap) == vector.optimize(
                    ingredients, {key: list(rows) for key, rows in products.items()}, stores, max_stores=cap)


@pytest.mark.parametrize('cached', [False, True])
def test_no_qualified_quotes_reports_incomplete_basket_not_internal_error(cached):
    from contextlib import nullcontext

    from app.models import NormalizedIngredient
    from app.services.basket_optimizer import BasketOptimizer, IncompleteBasketError

    from backend.tests.test_search_reuse import _store

    optimizer = BasketOptimizer()
    with (
        optimizer.quote_cache() if cached else nullcontext(),
        pytest.raises(IncompleteBasketError, match="No complete basket"),
    ):
        optimizer.optimize(
            [NormalizedIngredient(canonical_name="x", required_quantity=1, unit="st")],
            {"x": () if cached else []}, [_store("a")], max_stores=1,
        )


def test_subset_patterns_rebind_amounts_and_recompute_price_order():
    from app.models import NormalizedIngredient
    from app.services.basket_optimizer import BasketOptimizer

    from backend.tests.test_search_reuse import _product, _store

    optimizer = BasketOptimizer(memoize_store_subsets=True)
    stores = [_store(s) for s in ('a', 'b')]
    products = {'x': (_product('x', 3, store_id='a', package_quantity=1),
                      _product('x', 5, store_id='b', package_quantity=2))}
    with optimizer.quote_cache() as stats:
        totals = []
        for quantity in (1, 3, 2):
            ingredient = NormalizedIngredient(canonical_name='x', required_quantity=quantity, unit='st')
            actual = optimizer.optimize([ingredient], products, stores, max_stores=2)
            reference = BasketOptimizer().optimize([ingredient], products, stores, max_stores=2)
            assert actual == reference
            totals.append(actual.total)
        assert totals == [3, 9, 5]
        assert stats.subset_pattern_hits >= 1
        assert stats.subset_pattern_misses == 2
        session = optimizer._quote_cache_context.get()
        assert len(session.subset_patterns) == 2
    assert not session.subset_patterns
