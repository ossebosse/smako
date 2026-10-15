"""Actual retained source identities, opt-in and negative nutrition boundaries."""
import json
from dataclasses import replace
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning, TasteProfile
from app.models.recipe_preferences import RecipePreferences
from app.services.complete_recipes import _whole_food_identity
from app.services.official_product_facts import supplement_catalog_facts
from app.services.personal_planner import PersonalPlanner
from app.services.recipe_library import candidates
from app.services.recipe_volume_nutrition import volume_evidence

from backend.tests.test_personal_planning_v2 import state
from backend.tests.test_recipe_product_links import CLOCK, prepared, retained

ROWS = json.loads((Path(__file__).parent / 'fixtures/recipe_nutrition_links.json').read_bytes())['rows']
MACROS = {'protein_g', 'carbs_g', 'fat_g', 'kcal'}


def setup(row, *, estimates=True):
    product, raw_fact = retained(row)
    facts = supplement_catalog_facts([product], {(product.store_id, product.product_id): raw_fact})
    preferences = RecipePreferences(mode='complete', max_ingredients=20)
    recipe = next(r for r in candidates(preferences, 2) if r.name == row['recipe'])
    item = next(i for i in recipe.ingredients if i.canonical_name == row['ingredient'])
    request = PlanRequest(recipes=1, servings=2, max_stores=1, purchase_planning_mode='estimated',
        allowed_store_ids=[product.store_id], recipe_preferences=preferences,
        personal=PersonalPlanning(allow_nutrition_estimates=estimates,
            meals=[MealSettings(count=1, servings=2, limits={'min_protein_g': 40})]))
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(product), state(),
        facts=facts, now=CLOCK)
    return planner, recipe, item, product, facts[product.store_id, product.product_id]


@pytest.mark.parametrize('row', ROWS, ids=lambda r: r['ingredient'])
def test_real_catalog_input_qualifies_all_four_macros_without_price_changes(row):
    planner, recipe, item, product, fact = setup(row)
    original = product.model_dump_json()
    resolved = planner.resolve(item.name, item.quantity, item.unit, profile=TasteProfile(), recipe=recipe)
    assert resolved and resolved[0][1].price == product.price
    evidence = planner.nutrition_evidence(product, item.name, item.unit, MACROS, recipe)
    assert evidence and MACROS <= evidence.nutrition.keys()
    assert evidence.nutrition_unit == item.unit
    assert evidence.evidence_kind == 'recipe_design_input_estimate'
    assert all(evidence.field_sources['nutrition.' + k] for k in MACROS)
    assert not fact.allergens_checked
    assert product.model_dump_json() == original
    planner.spec.allow_nutrition_estimates = False
    planner.nutrition_cache.clear()
    assert planner.nutrition_evidence(product, item.name, item.unit, MACROS, recipe) is None


def test_lemon_density_changes_only_nutrition_and_preserves_declared_values():
    row = next(r for r in ROWS if r['ingredient'] == 'citronjuice')
    _, _, _, product, fact = setup(row)
    evidence = volume_evidence(product, 'citronjuice', fact)
    assert evidence.nutrition['protein_g'] == pytest.approx(.3 * 1.038)
    assert evidence.nutrition_unit == 'ml' and fact.nutrition_unit == 'g'
    assert product.usable_quantity == 200 and product.usable_unit == 'ml'
    assert volume_evidence(product, 'citronjuice', replace(fact, conflicts=('conflicting_basis',))) is None
    assert volume_evidence(product, 'citronjuice', replace(fact, nutrition={'protein_g': .3})) is None
    assert volume_evidence(product.model_copy(update={'name': 'Citronjuice från koncentrat'}), 'citronjuice', fact) is None


@pytest.mark.parametrize('ingredient,name', [('oregano', 'Oregano Kryddblandning'),
    ('oregano', 'Oregano Färsk'), ('fetaost', 'Fetaost i olja'),
    ('fetaost', 'Vegansk Fetaost'), ('ströbröd', 'Ströbröd Glutenfritt'),
    ('paprikapulver', 'Paprikapulver Rökt')])
def test_generic_references_do_not_cross_reviewed_plain_foods(ingredient, name):
    from app.services.nordic_nutrition import plain_food_evidence
    _, _, _, product, fact = setup(next(r for r in ROWS if r['ingredient'] == ingredient))
    assert plain_food_evidence(product.model_copy(update={'name': name}), ingredient, fact) is None
    assert plain_food_evidence(product, ingredient, replace(fact, nutrition={'protein_g': 1})) is None


def test_dairy_brand_cannot_disappear_into_raw_garlic():
    _, _, _, product, fact = setup(next(r for r in ROWS if r['ingredient'] == 'vitlök'))
    product = product.model_copy(update={'name': 'Crème Bonjour Vitlök', 'brand': 'Crème Bonjour',
                                        'category': 'Mejeri, ost & ägg > Färskost'})
    assert not _whole_food_identity('vitlök', 'raw_edible', product, fact)


@pytest.mark.parametrize('name', ['yoghurt naturell', 'keso', 'kvarg', 'crème fraiche', 'ägg', 'fetaost'])
def test_vegan_meal_rejects_every_plain_dairy_and_egg_ingredient(name):
    from app.models.recipe import RecipeIngredient
    from app.services.diet_policy import recipe_respects_diet

    from backend.tests.test_personal_planning_v2 import recipe as make_recipe

    recipe = make_recipe(ingredients=[RecipeIngredient(name=name, quantity=100, unit='g')])
    assert not recipe_respects_diet(recipe, preference='vegan')
    assert recipe_respects_diet(recipe, preference='vegetarian')


def test_complete_recipe_accepts_reviewed_fresh_apple_but_no_juice_or_flavoured_food():
    from backend.tests.test_personal_planning_v2 import product as make_product

    apple = make_product('Äpple Röda Svenska Klass 1', 1000, 'g', 20).model_copy(update={'category': 'Frukt & grönt'})
    assert _whole_food_identity('äpple', 'raw_edible', apple, None)
    for name in ['Äpple Juice', 'Äpple Kanel Granola', 'Äpple Kanel Yoghurt', 'Äpple Torkat']:
        assert not _whole_food_identity('äpple', 'raw_edible', apple.model_copy(update={'name': name}), None)


def test_real_apple_reaches_recipe_basket_without_inventing_source_confidence_or_price():
    from app.models import Product
    from app.services.personal_policy import ProductFacts
    from app.services.recipe_library import meal_candidates

    row = json.loads((Path(__file__).parent / 'fixtures/recipe_nutrition_links.json').read_bytes())['apple']
    product = Product.model_validate(row['product'])
    fact = ProductFacts(**row['fact'])
    meal = MealSettings(meal_type='breakfast', count=1, servings=2, recipe_choices={'max_ingredients':8})
    preferences = RecipePreferences(mode='complete')
    recipe = meal_candidates(meal, preferences)[0]
    request = PlanRequest(recipes=0, recipe_preferences=preferences, purchase_planning_mode='estimated',
        allowed_store_ids=[product.store_id], personal=PersonalPlanning(meals=[meal], allow_nutrition_estimates=True))
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(product), state(),
        facts={(product.store_id, product.product_id):fact}, now=CLOCK)
    original = product.model_dump_json()
    item = next(i for i in recipe.ingredients if i.name=='äpple')
    choices = planner.resolve(item.name, item.quantity, item.unit, profile=TasteProfile(), recipe=recipe)
    assert choices and choices[0][1].price == product.price
    assert choices[0][1].semantic_confidence == 'high'
    assert product.model_dump_json() == original


def test_coconut_declaration_keeps_explicit_ml_basis_and_exact_variant_binding():
    from app.models import Product
    from app.services.personal_policy import ProductFacts

    row = json.loads((Path(__file__).parent / 'fixtures/recipe_nutrition_links.json').read_bytes())['coconut']
    product, raw = Product.model_validate(row['product']), ProductFacts(**row['fact'])
    key = (product.store_id, product.product_id)
    facts = supplement_catalog_facts([product], {key:raw})
    assert facts[key].nutrition == {'kcal':172, 'protein_g':1.8, 'carbs_g':2.5, 'fat_g':17}
    assert facts[key].nutrition_unit == 'ml'
    assert _whole_food_identity('kokosmjölk', 'as_sold', product, facts[key])
    assert not facts[key].allergens_checked
    for change in [{'brand':'Other'}, {'package_quantity':400}, {'name':'Kokosmjölk 7%'}, {'package_unit':'g'}]:
        other = product.model_copy(update=change)
        assert not supplement_catalog_facts([other], {key:raw})[key].nutrition


def test_reviewed_cayenne_is_a_complete_estimate_and_never_a_seasoning_mix():
    from app.models import Product
    from app.services.nordic_nutrition import plain_food_evidence
    from app.services.personal_policy import ProductFacts

    row = json.loads((Path(__file__).parent / 'fixtures/recipe_nutrition_links.json').read_bytes())['cayenne']
    product, fact = Product.model_validate(row['product']), ProductFacts(**row['fact'])
    evidence = plain_food_evidence(product, 'cayennepeppar', fact)
    assert evidence.nutrition == {'kcal':375, 'protein_g':12, 'carbs_g':29.4, 'fat_g':17.3}
    assert plain_food_evidence(product, 'cayennepeppar', replace(fact, ingredients=('Cayennepeppar, salt',))) is None
    assert plain_food_evidence(product.model_copy(update={'name':'Cayennepeppar Färsk'}), 'cayennepeppar', fact) is None


def test_cold_served_weight_requires_reviewed_exact_recipe_and_consent():
    from app.services.recipe_portion_weight import estimate_portion_weight
    from app.services.reviewed_cold_meals import candidates as cold_candidates
    recipe = cold_candidates('snack', 2)[0]
    result = estimate_portion_weight(recipe, {})
    assert result['total_g'] == 400 and result['servings'] == 2
    assert result['evidence_kind'] == 'served_weight_estimate'
    assert estimate_portion_weight(recipe.model_copy(update={'instructions': ['Koka och häll av.']}), {}) is None


def test_weight_limit_is_enforced_by_planner_and_requires_estimate_opt_in():
    from app.models.personal import MealSlot
    from app.services.personal_policy import PolicyConflict, ProductFacts
    from app.services.reviewed_cold_meals import candidates as cold_candidates

    from backend.tests.test_personal_planning_v2 import prepared as build
    from backend.tests.test_personal_planning_v2 import product as make_product
    from backend.tests.test_personal_planning_v2 import request, run

    product = make_product('Kvarg naturell', 500, 'g', 20)
    recipe = cold_candidates('snack', 1)[0]
    facts = {('coop', product.product_id): ProductFacts(source='fixture', source_product_id=product.product_id,
        source_snapshot_id=product.source_provenance.source_snapshot_id,
        animal=True, ingredients=('Mjölk, syrningskultur',))}
    req = request(slots=[MealSlot(id='s', day=1, meal_type='snack', recipe=recipe)],
        meals=[MealSettings(meal_type='snack', count=1, servings=1, limits={'min_weight_g': 190, 'max_weight_g': 210})],
        allow_nutrition_estimates=True)
    plan = run(build(product), req, facts=facts)
    check = plan.personal.checks['nutrition'][0]
    assert check['values'] == {'weight_g': 200} and check['status'] == 'ESTIMATED'
    req.personal.meals[0].limits.min_weight_g = 205
    with pytest.raises(PolicyConflict) as error:
        run(build(product), req, facts=facts)
    assert error.value.code == 'NUTRITION_TARGET_NOT_MET'
    req.personal.meals[0].limits.min_weight_g = 190
    req.personal.allow_nutrition_estimates = False
    with pytest.raises(PolicyConflict) as error:
        run(build(product), req, facts=facts)
    assert error.value.code == 'DATA_BLOCKED'


def test_hot_served_weight_uses_documented_food_yield_not_added_salt_or_water_factor():
    from app.services.nutrition_reference import COOKED, reference_data
    from app.services.recipe_portion_weight import estimate_portion_weight

    from backend.tests.test_nutrition_reference import dinner, dinner_request, products
    from backend.tests.test_personal_planning_v2 import run

    prepared = products()
    names = {'kyckling': 'Kycklingbröstfilé', 'ris': 'Långkornigt Ris', 'morot': 'Morötter'}
    selected = {name: (next(p for p in prepared.universe.products if p.name == label), None)
                for name, label in names.items()}
    weight = estimate_portion_weight(dinner(), selected)
    assert weight and weight['method'] == 'food_specific_documented_batch_yield'
    data = reference_data()
    expected = 0
    for identity, grams in [(1173, 150), (2481, 80), (289, 150)]:
        main = next(i for i in data['preparations'][str(COOKED[identity])]['ingredients'] if i['nummer'] == identity)
        expected += grams * main['viktEfterTillagning'] / main['viktForeTillagning']
    assert weight['total_g'] / weight['servings'] == pytest.approx(expected)
    assert expected != pytest.approx(150 + 80 + 150)
    req = dinner_request(allow_nutrition_estimates=True)
    req.personal.meals[0].limits.min_weight_g = expected - 1
    req.personal.meals[0].limits.max_weight_g = expected + 1
    plan = run(prepared, req, facts={})
    check = plan.personal.checks['nutrition'][0]
    assert check['status'] == 'ESTIMATED'
    assert check['values']['weight_g'] == pytest.approx(expected)
    assert estimate_portion_weight(dinner(), {}) is None


def test_organic_search_cached_subsets_keep_exact_uncached_candidates_and_checkout(monkeypatch):
    from app.models.personal import ExtraNeed
    from app.services.basket_optimizer import BasketOptimizer

    from backend.tests.test_personal_planning_v2 import prepared as build
    from backend.tests.test_personal_planning_v2 import product as make_product
    from backend.tests.test_personal_planning_v2 import request, run
    from backend.tests.test_personal_qualified_facts import facts as make_facts

    products = [make_product(name, quantity, unit, price, identity=identity)
                for name, quantity, unit, price, identity in [
                    ('mjölk', 1000, 'ml', 20, 'milk'), ('mjölk', 1000, 'ml', 25, 'eco-milk'),
                    ('bröd', 500, 'g', 15, 'bread'), ('bröd', 500, 'g', 22, 'eco-bread')]]
    facts = {(p.store_id, p.product_id): make_facts(p, organic=p.product_id.startswith('eco-'))
             for p in products}
    req = request(organic_percent=70, extras=[ExtraNeed(query=n, quantity=100, unit=u, confirmed=True)
                  for n, u in [('mjölk', 'ml'), ('bröd', 'g')]])
    original = BasketOptimizer.optimize
    traces = [[], []]
    mode = 0

    def optimize(self, ingredients, candidates, *args, **kwargs):
        traces[mode].append({k: tuple((c.store_id, c.product_id) for c in v) for k, v in candidates.items()})
        if mode == 0:
            assert all(isinstance(v, tuple) for v in candidates.values())
        else:
            candidates = {k: list(v) for k, v in candidates.items()}
        return original(self, ingredients, candidates, *args, **kwargs)

    monkeypatch.setattr(BasketOptimizer, 'optimize', optimize)
    cached = run(build(*products), req, facts=facts)
    mode = 1
    uncached = run(build(*products), req, facts=facts)
    assert len(traces[0]) > 1 and traces[0] == traces[1]
    assert cached.optimized_basket == uncached.optimized_basket
    assert cached.personal.checks['organic_cost_percent'] == 100
