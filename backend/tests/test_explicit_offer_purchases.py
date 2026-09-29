"""Whole product shopping requests, distinct from generic recipe ingredients."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.models.recipe import Recipe, RecipeIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.lidl_product_facts import reviewed_facts
from app.services.personal_nutrition import calculation_basis, raw_salad_instructions
from app.services.personal_planner import PersonalPlanner
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def products():
    path = Path(__file__).parent / 'fixtures/qualified-offers-20260924.json'
    return [Product.model_validate(p) for p in json.loads(path.read_bytes())['products']]


@pytest.mark.parametrize('name', ['Chicken nuggets', 'Pulled pork', 'Majssnacks ost & bacon',
    'Kroketter med skinka & ost', 'Serranoskinka', 'Spansk extra jungfruolivolja'])
def test_explicit_product_purchase_through_matcher_checkout_and_audit(name):
    p = next(p for p in products() if p.name == name)
    n = NormalizedIngredient(canonical_name=name, required_quantity=p.package_quantity, unit=p.package_unit)
    context = UserPricingContext.from_chain_flags({'lidl': True})
    matches = ProductMatcher().match(n, [p])
    assert len(matches) == 1
    assert matches[0].product_role == 'explicit_whole_product'
    candidate = price_candidate_for_context(matches[0], context, on_date=date(2026, 9, 24))
    item = BasketCalculator().calculate_item(n, candidate)
    assert BasketAuditor(pantry_items=frozenset()).audit([n], [item], user_pricing_context=context).passed
    assert p.price is None
    assert not ProductMatcher().match(n, [p], store_ids=['a different store'])
    assert not ProductMatcher().match(n, [p.model_copy(update={'name': p.name + ' annan variant'})])


@pytest.mark.parametrize('name,ingredient', [('Chicken nuggets', 'kyckling'),
    ('Majssnacks ost & bacon', 'ost'), ('Kroketter med skinka & ost', 'ost'),
    ('Serranoskinka', 'nötfärs')])
def test_explicit_purchase_never_qualifies_component_or_nutrition(name, ingredient):
    p = next(p for p in products() if p.name == name)
    assert not ProductMatcher().match(NormalizedIngredient(canonical_name=ingredient, required_quantity=100, unit='g'), [p])
    planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=True), source_facts=lambda _: None)
    assert PersonalPlanner._nutrition_evidence(planner, p, name, 'g', {'protein_g'}, None) is None


def test_prior_non_offer_semantics_unchanged_and_raw_turkey_not_chicken():
    p = next(p for p in products() if p.name == 'Chicken nuggets')
    n = NormalizedIngredient(canonical_name=p.name, required_quantity=100, unit='g')
    assert not ProductMatcher().match(n, [p.model_copy(update={'source_provenance': None})])
    p = next(p for p in products() if p.name == 'Kalkonbröstfilé')
    assert not ProductMatcher().match(NormalizedIngredient(canonical_name='kyckling', required_quantity=100, unit='g'), [p])


def test_drained_purchase_uses_400g_not_540g_as_usable_amount():
    p = next(p for p in products() if p.name == 'Vita bönor')
    assert (p.package_quantity, p.usable_quantity, p.usable_unit) == (540, 400, 'g')
    n = NormalizedIngredient(canonical_name='Vita bönor', required_quantity=450, unit='g')
    context = UserPricingContext()
    candidate = price_candidate_for_context(ProductMatcher().match(n, [p])[0], context, on_date=date(2026,9,24))
    item = BasketCalculator().calculate_item(n, candidate)
    assert item.total_price == 27.8
    assert BasketAuditor(pantry_items=frozenset()).audit([n], [item], user_pricing_context=context).passed


def test_real_cold_recipe_price_nutrition_and_checkout_are_separate():
    rows = products()
    recipe = Recipe(name='Koriander med vitlök', servings=2,
        ingredients=[RecipeIngredient(name='koriander', quantity=20, unit='g'),
                     RecipeIngredient(name='vitlök', quantity=5, unit='g')], instructions=raw_salad_instructions())
    assert calculation_basis(recipe, allow_estimates=True)['method'] == 'sum_measured_raw_edible_input'
    items, needs, macros = [], [], {'kcal': 0, 'protein_g': 0, 'carbs_g': 0, 'fat_g': 0}
    planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=True), source_facts=lambda _: None)
    for ingredient in recipe.ingredients:
        p = next(p for p in rows if p.name == ('Koriander' if ingredient.name == 'koriander' else 'Vitlök i kapsel 100g'))
        n = NormalizedIngredient(canonical_name=ingredient.name, required_quantity=ingredient.quantity, unit='g')
        candidate = price_candidate_for_context(ProductMatcher().match(n, [p])[0], UserPricingContext(), on_date=date(2026,9,24))
        items.append(BasketCalculator().calculate_item(n, candidate)); needs.append(n)
        fact = PersonalPlanner._nutrition_evidence(planner, p, ingredient.name, 'g', set(macros), recipe)
        assert fact.evidence_kind == 'generic_reference'
        for k in macros:macros[k] += fact.nutrition[k] * ingredient.quantity / 100
    assert round(macros['kcal'], 2) == 13.8  # measured recipe input, not whole purchased packages
    assert BasketAuditor(pantry_items=frozenset()).audit(needs, items, user_pricing_context=UserPricingContext()).passed


def test_supplier_declaration_survives_new_qualified_campaign_without_reaging():
    p = next(p for p in products() if p.name == 'Lingongrova')
    before = reviewed_facts([p])[(p.store_id, p.product_id)]
    # Synthetic next-campaign reference; no claim of real future price evidence.
    p = p.model_copy(update={'offers': [o.model_copy(update={'price_contract_id': 'lidl:household:test-next:11218552'}) for o in p.offers]})
    after = reviewed_facts([p])[(p.store_id, p.product_id)]
    assert before == after
    assert not reviewed_facts([p.model_copy(update={'package_quantity': 600})])
    assert not reviewed_facts([p.model_copy(update={'gtin': '0000000000000'})])
