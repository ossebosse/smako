"""Thin dry rice noodles retain exact article, package, shape and conflict gates."""
from dataclasses import replace
from functools import lru_cache

import pytest
from app.models import Product
from app.models.provenance import SourceProvenance
from app.services.complete_recipes import product_form_compatible
from app.services.intake_product_links import compatible, entries, ingredient_product
from app.services.personal_policy import ProductFacts
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver
from app.services.recipe_library import current_recipes

KEY = 'intake_all_8edc96a34921'


def source_fixture(proof):
    p = Product(product_id=proof['product_id'], store_id=proof['store_id'], store_name='Synthetic source fixture',
        name=proof['name'], canonical_name='risvermicelli', category=proof['category'], brand=proof['brand'],
        gtin=proof.get('gtin'), chain=proof['source_provenance']['chain'], price=10,
        package_quantity=400, package_unit='g', usable_quantity=400, usable_unit='g',
        quantity_confidence='exact', semantic_confidence='exact',
        source_provenance=SourceProvenance.model_validate(proof['source_provenance']))
    fact = ProductFacts(source='synthetic fixture', source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id, retailer_product_id=proof['retailer_product_id'],
        ingredients=(proof['quantity']['declared_ingredients'],), ingredients_complete=True,
        ingredient_evidence_kind='product_declaration',
        conflicts=('supplier_nutrition_conflict',) if proof['retailer_product_id'] == '101261105_ST' else ())
    return p, fact


@pytest.fixture(params=['101195358_ST', '101261105_ST'])
def rice(request):
    proof = next(r for r in entries()[KEY]['reviewed_links'] if r['retailer_product_id'] == request.param)
    return (*source_fixture(proof), proof)


@lru_cache(maxsize=1)
def issued_recipe():
    return next(r for r in current_recipes() if any('pack:' + KEY in (i.product_requirements or ()) for i in r.ingredients))


def test_exact_thin_dry_form_keeps_purchase_grams_and_cannot_clear_round_or_broad(rice):
    p, fact, _proof = rice
    assert compatible(KEY, p, fact)
    assert ingredient_product('risvermicelli', 'dry', ['pack:' + KEY], p, fact)
    assert product_form_compatible(issued_recipe(), 'risvermicelli', p, fact)
    assert not compatible('intake_all_f65e475da5be', p, fact)
    assert not compatible('intake_all_e3c4c91f56c3', p, fact)
    purchase = PurchaseQuantityResolver().resolve(p, required_quantity=401, required_unit='g')
    assert purchase.packages_needed == 2 and purchase.purchased_usable_quantity == purchase.purchased_quantity == 800
    assert purchase.total_price == 20 and purchase.quantity_confidence == 'exact'
    assert not ingredient_product('risvermicelli', 'cooked_drained', ['pack:' + KEY], p, fact)
    assert fact.nutrition == {} and fact.organic is fact.animal is None


@pytest.mark.parametrize('changed', [
    {'name': 'Färdigkokta risnudlar med sås'}, {'brand': 'unreviewed brand'},
    {'package_quantity': 500}, {'usable_quantity': 399}, {'store_id': 'other-store'},
    {'gtin': 'unreviewed-identity'}, {'source_provenance': None},
])
def test_no_exact_food_or_quantity_review_crosses_changed_identity(rice, changed):
    p, fact, _proof = rice
    assert not compatible(KEY, p.model_copy(update=changed), fact)


def test_full_composition_and_current_quantity_conflicts_still_block(rice):
    p, fact, _proof = rice
    assert not compatible(KEY, p, replace(fact, ingredients=('Vetemjöl, ägg, vatten',)))
    assert not compatible(KEY, p, replace(fact, source_snapshot_id='another-price-snapshot'))
    assert not compatible(KEY, p, replace(fact, conflicts=('unknown_quantity_conflict',)))
    assert compatible(KEY, p, replace(fact, conflicts=('supplier_nutrition_conflict',)))


def test_every_real_context_uses_its_existing_article_without_inventing_a_product_gtin():
    proofs = entries()[KEY]['reviewed_links']
    assert len(proofs) == 14
    assert {p['retailer_product_id'] for p in proofs} == {'101195358_ST', '101261105_ST'}
    for proof in proofs:
        p, fact = source_fixture(proof)
        assert compatible(KEY, p, fact)
        assert proof['gtin'] is None
        source = proof['quantity']['exact_article_source']
        assert source['article'] == proof['retailer_product_id']
        assert source['consumer_gtin'] in {'8850521111127', '8936007820360'}
        assert source['displayVolume'] == '400g' and source['sha256']
