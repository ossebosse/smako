"""Official 24 September SLV values; estimates never become declarations."""
from types import SimpleNamespace

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.services.nutrition_reference import product_reference, reference_evidence
from app.services.personal_nutrition import calculation_basis, raw_salad_instructions
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict

from backend.tests.test_personal_planning_v2 import product


def evidence(p, name, *, unit='g', allow=True, recipe=None):
    planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=allow), source_facts=lambda _: None)
    return PersonalPlanner._nutrition_evidence(planner, p, name, unit,
        {'kcal', 'protein_g', 'fat_g', 'carbs_g'}, recipe)


def test_raw_turkey_reference_is_traceable_and_not_a_cooked_declaration():
    p = product('Kalkonbröstfilé', 1000, 'g', 99)
    result = evidence(p, 'kalkonbröstfilé')
    assert result.evidence_kind == 'generic_reference'
    assert result.source_product_id == 'slv:1162'
    assert result.nutrition == {'kcal': 106, 'protein_g': 24.1, 'fat_g': .9, 'carbs_g': 0}
    assert result.field_sources['nutrition.kcal'][0]['source_url'].endswith('/1162/naringsvarden?sprak=1')
    assert evidence(p, 'kalkonbröstfilé', allow=False) is None
    assert evidence(p, 'kyckling') is None
    assert reference_evidence(1162, cooked=True) is None
    for name in ('Rökt kalkonbröstfilé', 'Kalkonlårfilé', 'Kalkonbröstfilé sous vide', 'Marinerad kalkonbröstfilé'):
        assert evidence(p.model_copy(update={'name': name}), 'kalkonbröstfilé') is None


def test_species_composition_fat_and_units_are_not_guessed():
    assert product_reference(product('Mynta', 25, 'g', 9.9), 'mynta', None) is None
    assert product_reference(product('Koriander', 25, 'g', 9.9), 'koriander', None) is None
    assert product_reference(product('Koriander frö', 25, 'g', 9.9), 'koriander', None) is None
    assert product_reference(product('Färsk koriander', 25, 'g', 9.9), 'koriander', None) == 7193
    p = product('Spansk extra jungfruolivolja', 750, 'ml', 69.9)
    assert evidence(p, 'olivolja', unit='ml') is None
    assert evidence(p, 'olivolja').source_product_id == 'slv:4659'  # separately weighed grams only
    assert evidence(p.model_copy(update={'name': 'Olivolja med vitlök'}), 'olivolja') is None
    assert evidence(product('Crème fraiche 13%', 500, 'ml', 23.9), 'crème fraiche') is None
    assert evidence(product('Crème fraiche 32%', 500, 'ml', 23.9), 'crème fraiche', unit='ml') is None


def test_new_cold_basis_requires_measured_edible_grams_and_exact_preparation():
    r = Recipe(name='Rå korianderblandning', servings=2,
        ingredients=[RecipeIngredient(name='koriander', quantity=20, unit='g'),
                     RecipeIngredient(name='vitlök', quantity=5, unit='g')],
        instructions=raw_salad_instructions())
    assert calculation_basis(r, allow_estimates=True)['method'] == 'sum_measured_raw_edible_input'
    with pytest.raises(PolicyConflict):
        calculation_basis(r, allow_estimates=False)
    with pytest.raises(PolicyConflict):
        calculation_basis(r.model_copy(update={'instructions': ['Stek i olja.']}), allow_estimates=True)
    with pytest.raises(PolicyConflict):
        calculation_basis(r.model_copy(update={'ingredients': [RecipeIngredient(name='kalkonbröstfilé', quantity=100, unit='g')]}), allow_estimates=True)


def test_fresh_mango_reference_does_not_invent_piece_weight_or_preparation():
    p = product('Mango', 1, 'st', 11.9).model_copy(update={'category': 'Mat och nära mat > Frukt & grönsaker > Frukt'})
    ref = evidence(p, 'mango')
    assert ref.source_product_id == 'slv:574' and ref.evidence_kind == 'generic_reference'
    assert evidence(p, 'mango', unit='st') is None
    assert evidence(p, 'mango', allow=False) is None
    for name in ('Mango fryst', 'Mango konserv i sockerlag', 'Mango torkad'):
        assert evidence(p.model_copy(update={'name':name}), 'mango') is None
    assert evidence(p.model_copy(update={'category':None}), 'mango') is None


def test_peach_reference_import_preserves_edible_gram_basis_without_gross_weight_conversion():
    from app.services.nutrition_reference import reference_options, validate_pantry_reference
    row=reference_evidence(580)
    assert row.nutrition == {'kcal':42,'protein_g':.8,'carbs_g':8.5,'fat_g':0}
    assert row.evidence_kind=='generic_reference'
    assert row.field_sources['nutrition.kcal'][0]['food_id']==580
    assert row.field_sources['nutrition.kcal'][0]['retrieved_at'].startswith('2026-09-25')
    assert any(o['id']=='slv:580:raw' for o in reference_options())
    assert validate_pantry_reference('persika','g','slv:580:raw')==580
    # Imported for measured edible pantry grams; the purchase's gross weight
    # cannot silently serve as stone-free ingredient weight.
    assert product_reference(product('Persikor',1000,'g',26.9),'persika',None) is None
    with pytest.raises(ValueError):validate_pantry_reference('persika','st','slv:580:raw')
