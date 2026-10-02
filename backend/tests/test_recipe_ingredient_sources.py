from types import SimpleNamespace

import pytest
from app.services.nutrition_reference import product_reference, reference_data, reference_evidence
from app.services.product_semantics import evaluate_product_semantics


@pytest.mark.parametrize('name,accepted', [
    ('Grekisk Yoghurt Naturell 10%', True), ('Mild Yoghurt Naturell 3%', True),
    ('Yoghurt Naturell Vanilj', False), ('Kvarg Yoghurt Vanilj 0,3%', False),
    ('Yoghurt Naturell med honung', False), ('Drickyoghurt Naturell', False),
])
def test_plain_yoghurt_is_distinct_from_flavoured_or_other_dairy(name, accepted):
    assert evaluate_product_semantics('yoghurt naturell', {'name': name}).compatible == accepted


@pytest.mark.parametrize('name,accepted', [
    ('Paprikapulver', True), ('Paprikapulver Milt', True),
    ('Paprika', False), ('Kyckling med paprikapulver', False),
    ('Paprikapulver Kryddblandning', False),
])
def test_powdered_paprika_is_a_distinct_whole_ingredient(name, accepted):
    assert evaluate_product_semantics('paprikapulver', {'name': name}).compatible == accepted


@pytest.mark.parametrize('canonical,name,accepted', [
    ('keso', 'Keso Cottage cheese Naturell 4%', True),
    ('keso', 'Keso Cottage Cheese Naturell Mini 1,5%', True),
    ('keso', 'Keso Cottage Cheese Vanilj 2,9%', False),
    ('keso', 'Kusar Keso Osötat', False),
    ('kapris', 'Kapris Små', True), ('kapris', 'Kapris Non Pareilles', True),
    ('kapris', 'Tapenade Al Basilico Basilika Oliv Kapris', False),
])
def test_cottage_cheese_and_capers_require_complete_food_label(canonical, name, accepted):
    assert evaluate_product_semantics(canonical, {'name': name}).compatible == accepted


def product(name, category):
    return SimpleNamespace(name=name, category=category, offers=[])


def test_references_keep_raw_frozen_and_dried_forms_separate():
    assert product_reference(product('Blomkål', 'Frukt & Grönt'), 'blomkål', None) == 322
    assert product_reference(product('Blomkål Fryst', 'Fryst'), 'blomkål', None) == 323
    assert product_reference(product('Dill', 'Frukt & Grönt'), 'dill', None) == 377
    for name in ('Dill Burk', 'Dill torkad', 'Dillchips', 'Dill & Gräslök Dippmix'):
        assert product_reference(product(name, 'Skafferi'), 'dill', None) is None
    assert product_reference(product('Blomkål stuvad', 'Färdigmat'), 'blomkål', None) is None
    assert product_reference(product('Aubergine', 'Zucchini & Aubergine'), 'aubergine', None) == 372
    assert product_reference(product('Stjälkselleri', 'Frukt & Grönt'), 'selleri', None) == 321
    assert product_reference(product('Rotselleri', 'Frukt & Grönt'), 'selleri', None) is None
    assert product_reference(product('Sellerisalt', 'Kryddor'), 'selleri', None) is None


@pytest.mark.parametrize('canonical', ['aubergine', 'zucchini'])
def test_new_whole_vegetable_semantics_reject_preserved_and_prepared(canonical):
    assert evaluate_product_semantics(canonical, {'name': canonical.title(), 'category': 'Frukt & Grönt'}).compatible
    for name, category in [(canonical + ' inlagd', 'Konserver'), (canonical + ' i olja', 'Konserver'),
                           ('Lasagne med ' + canonical, 'Färdigrätter')]:
        assert not evaluate_product_semantics(canonical, {'name': name, 'category': category}).compatible


def test_imported_sources_retain_ids_versions_and_all_unrounded_macros():
    data = reference_data()
    for identity in (362, 372, 4941, 361, 322, 323, 333, 383, 291, 377, 352, 379, 7199, 2306, 7198, 702, 1941, 321, 294):
        entry = data['foods'][str(identity)]
        assert entry['food']['nummer'] == identity and entry['food']['version']
        assert all(a['url'].startswith('https://dataportal.livsmedelsverket.se/') and len(a['sha256']) == 64
                   for a in entry['acquisition'])
        evidence = reference_evidence(identity)
        assert set(evidence.nutrition) == {'protein_g', 'carbs_g', 'fat_g', 'kcal'}
        assert evidence.evidence_kind == 'generic_reference'
    conflict = SimpleNamespace(conflicts=('nutrition.protein_g',), ingredients=())
    assert product_reference(product('Spenat', 'Frukt & Grönt'), 'spenat', conflict) is None
