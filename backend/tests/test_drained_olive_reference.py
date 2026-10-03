"""Synthetic boundary tests; authentic qualification is reported separately."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.models.recipe_preferences import RecipePreferences
from app.services.nutrition_reference import product_reference, reference_data, reference_evidence
from app.services.personal_policy import ProductFacts
from app.services.recipe_library import candidates
from app.services.recipe_preparation import input_evidence


def olive(name='Oliver Kalamata Urkärnade Eko', quantity=170):
    return SimpleNamespace(name=name, category='Oliver', usable_quantity=quantity,
                           usable_unit='g', offers=[])


def facts(composition='Vatten, urkärnade kalamataoliver*, salt, vinäger*, olivolja*. '
                     '*Ekologiskt certifierad ingrediens.'):
    return ProductFacts(source='retained-supplier', source_product_id='olive',
        source_snapshot_id='snapshot', ingredients=(composition,), nutrition_unit='g',
        nutrition_basis='supplier per 100g, drainage unspecified',
        nutrition_preparation='draining_unspecified',
        nutrition={'kcal': 201, 'fat_g': 20, 'carbs_g': 3.9, 'protein_g': 1.6},
        field_sources={'usable_quantity': ({'basis': 'drained', 'quantity': 170,
                                            'unit': 'g', 'source': 'https://www.dabas.com/productsheet/07350002405543'},)})


def recipe():
    return next(r for r in candidates(RecipePreferences(mode='complete'))
                if r.design.base_id == 'smako-greek-fish-plaki')


def test_official_black_oiled_drained_reference_keeps_complete_source_and_unknown_brand_basis():
    entry = reference_data()['foods']['402']
    assert entry['food']['namn'] == 'Oliver svarta m. olja avrunna'
    assert entry['food']['version'] == '2026-06-29T00:29:43.913'
    assert len(entry['acquisition']) == 2
    assert all(len(a['sha256']) == 64 and a['status'] == 200 for a in entry['acquisition'])
    assert product_reference(olive(), 'oliver', facts()) == 402
    evidence = input_evidence(recipe(), olive(), 'oliver', 'g', False, facts())
    assert evidence and evidence.evidence_kind != 'product_declaration'
    assert evidence.nutrition == reference_evidence(402).nutrition
    assert evidence.nutrition != facts().nutrition
    for entries in evidence.field_sources.values():
        assert any(e.get('kind') == 'supplier_drained_quantity_reference_basis' for e in entries)
        assert any(e.get('food_id') == 402 for e in entries)


@pytest.mark.parametrize('name,composition', [
    ('Oliver Gröna Urkärnade', 'Urkärnade gröna oliver, vatten, olivolja, salt'),
    ('Oliver Kalamata Urkärnade', 'Urkärnade kalamataoliver, vatten, salt'),
    ('Svarta Oliver Urkärnade', 'Urkärnade svarta oliver, vatten, salt'),
    ('Oliver Kalamata Med Kärna', 'Kalamataoliver med kärna, olivolja, salt'),
    ('Oliver Kalamata Urkärnade', 'Urkärnade kalamataoliver, vitlök, olivolja, salt'),
    ('Oliver Kalamata Urkärnade', 'Urkärnade kalamataoliver, paprika, olivolja, salt'),
    ('Oliver Kalamata Urkärnade', ''),
    ('Olivmix Utan Kärnor', 'Urkärnade svarta oliver, gröna oliver, olivolja, salt'),
    ('Oliver Okänd Sort Urkärnade', 'Urkärnade oliver, olivolja, salt'),
])
def test_green_filled_oil_free_pitted_unknown_and_flavoured_forms_do_not_borrow_reference(name, composition):
    f = facts(composition)
    assert product_reference(olive(name), 'oliver', f) is None
    assert input_evidence(recipe(), olive(name), 'oliver', 'g', False, f) is None


def test_conflict_and_missing_or_wrong_drained_mass_remain_blocked():
    for f in [replace(facts(), conflicts=('supplier_nutrition_conflict',)),
              replace(facts(), field_sources={}),
              replace(facts(), field_sources={'usable_quantity': ({'basis':'net', 'quantity':170, 'unit':'g', 'source':'supplier'},)})]:
        assert product_reference(olive(), 'oliver', f) is None
        assert input_evidence(recipe(), olive(), 'oliver', 'g', False, f) is None
    assert product_reference(olive(quantity=370), 'oliver', facts()) is None


def test_fontana_kalamon_composition_matches_same_reviewed_food():
    p = olive('Oliver Kalamon Urkärnade', quantity=130)
    f = replace(facts('INGREDIENSER: Vatten, urkärnade oliver av sorten Kalamata (44,8%), '
                     'vinäger, extra virgin olivolja, havssalt.'),
                field_sources={'usable_quantity': ({'basis':'drained', 'quantity':130, 'unit':'g', 'source':'supplier'},)})
    assert product_reference(p, 'oliver', f) == 402


@pytest.mark.parametrize('opt_in', [False, True])
def test_normal_planner_requires_explicit_generic_nutrition_opt_in(opt_in):
    from app.config import Settings
    from app.models import PlanRequest
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

    p = product('Oliver Kalamata Urkärnade Eko', 370, 'g', 37.5,
                identity='olive', usable_quantity=170, usable_unit='g')
    f = replace(facts(), source_product_id=p.product_id,
                source_snapshot_id=p.source_provenance.source_snapshot_id)
    request = PlanRequest(purchase_planning_mode='estimated',
                          personal={'allow_nutrition_estimates':opt_in})
    planner = PersonalPlanner(request, Settings(), prepared(p), state(),
                              facts={(p.store_id,p.product_id):f}, now=NOW)
    evidence = planner.nutrition_evidence(p, 'oliver', 'g',
                                         {'kcal','protein_g','fat_g','carbs_g'}, recipe())
    assert bool(evidence) == opt_in
