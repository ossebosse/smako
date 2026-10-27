"""Check full issued preparation chains and the actual bread gate."""
import json

import pytest
from app.models import Product
from app.models.personal import TasteProfile
from app.services.complete_recipes import product_form_compatible
from app.services.meal_library_content import ROOT, identity, load_entries, manifest_entries
from app.services.personal_policy import PolicyConflict, ProductFacts, check_product
from app.services.recipe_library import current_recipes

REPORT=ROOT.parents[3]/'docs/reviews/week-search-and-cache-20261026/recipe-review.json'
REVIEW=json.loads(REPORT.read_bytes())
MINT=json.loads((ROOT.parents[3]/'docs/reviews/recipe-four-staples-20261027/recipe-review.json').read_bytes())
SUCCESSORS={r['previous_id']:r for r in MINT['corrected']}


def current(rid):
    rid=SUCCESSORS.get(rid,{}).get('runtime_id',rid)
    return next(r for r in current_recipes() if identity(r)==rid)


@pytest.mark.parametrize('row',[r for r in REVIEW['corrected'] if ':1.0.3:' in r['runtime_id']])
def test_complete_skewer_chain_uses_thawed_fruit_until_oven(row):
    r=current(row['runtime_id'])
    steps=r.design.steps
    thaw=next(i for i,s in enumerate(steps) if 'tina helt före skärning och trädning' in s.text)
    cutting=next(i for i,s in enumerate(steps) if 'använd de helt tinade skalade' in s.text)
    threading=next(i for i,s in enumerate(steps) if s.text.startswith('Trä '))
    oven=next(i for i,s in enumerate(steps) if s.text.startswith('Tillaga mitt i ugnen'))
    assert thaw<cutting<threading<oven
    assert all('frysta' not in s.text and 'varma pannan' not in s.text for s in steps[thaw+1:])
    assert steps[cutting].ingredient_keys and steps[threading].ingredient_keys
    assert all(steps[i-1].id in steps[i].depends_on for i in range(thaw+1,oven+1))
    assert row['before']==row['after']
    expected=SUCCESSORS.get(row['runtime_id'],{}).get('after',row['after'])
    assert {k:getattr(r.design,k) for k in expected}==expected


@pytest.mark.parametrize('row',REVIEW['verified_unchanged'])
def test_real_direct_heat_pan_recipes_are_preserved(row):
    r=current(row['runtime_id'])
    amendment=SUCCESSORS.get(row['runtime_id'])
    if amendment:
        assert amendment['before_content_sha256']==row['content_sha256']
        assert r.design.content_sha256==amendment['content_sha256']
    else:
        assert r.design.content_sha256==row['content_sha256']
    assert any('frysta skalade' in s.text and 'direkt i den varma pannan' in s.text for s in r.design.steps)
    assert not any('tina helt' in s.text for s in r.design.steps)


def bread(name='Rågbröd'):
    return Product(product_id='rye',store_id='store',store_name='Test',name=name,canonical_name='bröd',category='Bröd',price=25,package_quantity=500,package_unit='g',usable_quantity=500,usable_unit='g')


@pytest.mark.parametrize('row',[r for r in REVIEW['corrected'] if ':1.0.1:' in r['runtime_id']])
def test_all_rye_variants_reject_pita_and_contradictory_formula(row):
    r=current(row['runtime_id'])
    assert 'rågbröd' in r.name
    i=next(i for i in r.ingredients if i.canonical_name=='bröd')
    assert list(i.product_requirements)==['pack:rye_bread']
    assert any('Rosta rågbrödsskivorna' in s.text for s in r.design.steps)
    assert product_form_compatible(r,'bröd',bread(),None)
    assert not product_form_compatible(r,'bröd',bread('Pitabröd'),None)
    assert not product_form_compatible(r,'bröd',bread('Bröd'),None)
    f=ProductFacts(source='synthetic',source_product_id='rye',source_snapshot_id='snapshot',ingredients=('Vetemjöl, vatten, jäst, salt',))
    assert not product_form_compatible(r,'bröd',bread(),f)
    f=ProductFacts(source='synthetic',source_product_id='rye',source_snapshot_id='snapshot',ingredients=('Vatten, fullkornsrågmjöl, vetemjöl, jäst, salt',))
    assert product_form_compatible(r,'bröd',bread(),f)
    with pytest.raises(PolicyConflict):
        check_product(bread(),TasteProfile(allergies=['gluten']),None)


def test_superseded_versions_keep_exact_content_and_new_versions_are_current():
    m=manifest_entries();issued={identity(r):r for r in load_entries([*m['current'],*m['history']],ROOT)}
    active={identity(r) for r in current_recipes()}
    assert len(active)==2462
    for row in REVIEW['corrected']:
        assert row['previous_id'] in m['revocations'] and row['previous_id'] not in active
        assert issued[row['previous_id']].design.content_sha256==row['before_content_sha256']
        assert SUCCESSORS.get(row['runtime_id'],{}).get('runtime_id',row['runtime_id']) in active
