"""Real reviewed drained identities retain purchase, form and personal gates."""
from dataclasses import replace

import pytest
from app.models.personal import TasteProfile
from app.models.product import QuantityConfidence
from app.models.provenance import SourceProvenance
from app.services import intake_product_links as links
from app.services.complete_recipes import product_form_compatible
from app.services.official_product_facts import project_usable_quantity
from app.services.personal_policy import PolicyConflict, ProductFacts, check_product
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver
from app.services.recipe_library import current_recipes

from backend.tests.test_personal_planning_v2 import product


@pytest.mark.parametrize('gtin', ['7340083487538', '7311043015993', '7311043010936', '7331217011699', '4068500810242'])
def test_declared_drained_contents_qualify_only_the_reviewed_form_and_exact_current_fact(gtin):
    key,row,proof = next((key,row,proof) for key,row in links.entries().items()
        for proof in row.get('reviewed_links', ()) if proof.get('gtin') == gtin)
    usable = proof['quantity']['usable_quantity']
    p = product(proof['name'],proof['package_quantity'],'g',20,
        identity=proof['product_id'],store=proof['store_id']).model_copy(update={
            'gtin':gtin,'brand':proof['brand'],'category':proof['category'],
            'usable_quantity':usable,'quantity_confidence':QuantityConfidence.DERIVED,
            'source_provenance':SourceProvenance.model_validate(proof['source_provenance'])})
    f = ProductFacts(source=proof['quantity']['source']['url'],source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id,
        ingredients=(proof['quantity']['declared_ingredients'],),ingredients_complete=True,
        ingredient_evidence_kind='product_declaration',
        conflicts=('supplier_nutrition_conflict',) if row['name']=='vinblad' else (),
        field_sources={'usable_quantity':({'basis':'drained','unit':'g','quantity':usable,
            'source':proof['quantity']['source']['url']},)})
    before = p.model_dump_json()
    q = project_usable_quantity(p,f,required_unit='g')
    assert q.package_quantity==p.package_quantity and q.usable_quantity==usable and q.quantity_confidence=='exact'
    assert p.model_dump_json()==before and q.source_provenance==p.source_provenance
    assert links.compatible(key,q,f)
    recipe=next(r for r in current_recipes() if any(row['requirements'][0] in (i.product_requirements or ()) for i in r.ingredients))
    assert product_form_compatible(recipe,row['name'],q,f)
    assert not links.ingredient_product(row['name'],'raw_edible',row['requirements'],q,f)
    assert not links.ingredient_product('råa räkor','raw_edible',row['requirements'],q,f)
    quote=PurchaseQuantityResolver().resolve(q,required_quantity=usable+1,required_unit='g')
    assert quote.packages_needed==2 and quote.total_price==40
    assert quote.purchased_quantity==2*p.package_quantity and quote.purchased_usable_quantity==2*usable
    for altered in [replace(f,ingredients=('different composition',)),
                    replace(f,source_snapshot_id='different'),
                    replace(f,conflicts=('unknown_quantity_conflict',))]:
        assert project_usable_quantity(p,altered,required_unit='g') is p
        assert not links.compatible(key,q,altered)
    assert not f.nutrition and not f.allergens_checked and f.organic is None
    with pytest.raises(PolicyConflict):check_product(q,TasteProfile(allergies=['mjölk']),f)
    with pytest.raises(PolicyConflict):check_product(q,TasteProfile(),f,organic_animals=True)
    if row['name']=='vinblad':
        assert 'NATRIUMDISULFIT' in f.ingredients[0] and f.conflicts==('supplier_nutrition_conflict',)
        with pytest.raises(PolicyConflict):check_product(q,TasteProfile(allergies=['sulfiter']),f)
