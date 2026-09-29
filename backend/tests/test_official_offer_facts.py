"""Declared nutrition and non-executable kilogram quotes stay separate."""
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate, SaleModel
from app.services.official_product_facts import declared_facts
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context, price_contracts_for_candidate

from grocery_data.app.domain.promotion_pricing import UserPricingContext

ROOT = Path(__file__).parents[2]/'reports/offer-nutrition-20260924'


@pytest.fixture
def product():
    u = PreparedPriceUniverseArtifact.model_validate_json((ROOT/'prepared-1280-second.json').read_bytes()).restore()
    return next(p for p in u.universe.products if p.name == 'Majskorvar Krispiga Glutenfria')


def test_declaration_is_usable_without_estimates_and_does_not_invent_gtin(product):
    before = product.model_dump_json()
    facts = declared_facts([product])
    fact = facts[(product.store_id, product.product_id)]
    assert fact.nutrition['kcal'] == 390
    planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=False), source_facts=lambda _:fact)
    assert PersonalPlanner._nutrition_evidence(planner,product,product.name,'g',{'kcal','protein_g'},None) == fact
    assert product.gtin is None and product.model_dump_json() == before
    assert fact.field_sources['nutrition.kcal'][0]['supplier_gtin'] == '7340083401794'
    assert fact.observed_at == '2026-09-24T16:15:30.589403+00:00'
    assert PersonalPlanner._nutrition_evidence(planner,product,product.name,'ml',{'kcal'},None) is None
    planner.source_facts = lambda _:replace(fact,source_snapshot_id='wrong-campaign')
    assert PersonalPlanner._nutrition_evidence(planner,product,product.name,'g',{'kcal'},None) is None


@pytest.mark.parametrize('update', [{'brand':'Other'}, {'name':'Majskorvar med ost'},
    {'package_quantity':100}, {'gtin':'7310865004703'}, {'usable_quantity':80}])
def test_wrong_variant_brand_pack_gtin_or_edible_basis_cannot_borrow_facts(product, update):
    assert not declared_facts([product.model_copy(update=update)])


def test_kg_quote_is_preserved_but_never_a_package_or_exact_purchase(product):
    offer = product.offers[0].model_copy(update={'price_basis_unit':'kg'})
    p = product.model_copy(update={'sale_model':SaleModel.UNKNOWN, 'package_quantity':None,
        'package_unit':None, 'usable_quantity':None, 'usable_unit':None, 'offers':[offer]})
    p = type(product).model_validate(p.model_dump())
    candidate = ProductCandidate.from_product(p,1)
    assert not price_contracts_for_candidate(candidate)
    with pytest.raises(ValueError, match='no active eligible'):
        price_candidate_for_context(candidate,UserPricingContext.from_chain_flags({'willys':True}),on_date=date(2026,9,24))
    assert not ProductMatcher().match(NormalizedIngredient(canonical_name=p.name,required_quantity=100,unit='g'),[p])
    assert not declared_facts([p])
