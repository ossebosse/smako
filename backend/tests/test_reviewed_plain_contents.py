"""Reviewed declarations establish input identity, never personal approvals."""
from dataclasses import replace

import pytest
from app.models.personal import TasteProfile
from app.models.provenance import SourceProvenance
from app.services.intake_product_links import compatible, entries
from app.services.personal_policy import PolicyConflict, ProductFacts, check_product
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

from backend.tests.test_personal_planning_v2 import product

CASES = [
    ('101328401_ST', 'INGREDIENSER Majskorn.'),
    ('101350897_ST', 'INGREDIENSER Majskorn*. *Ekologisk ingrediens.'),
    ('101234770_ST', 'Ingredienser: Malda psylliumfröskal. Kan innehålla spår av sesam- och senapsfrön.'),
    ('101405340_ST', 'Ingredienser: Ljust pulveriserat psylliumfröskal (psyllium husk)'),
    ('101278378_ST', 'Ingredienser: Svenskt sidfläsk (92%), vatten, salt, glykossirap, antioxidationsmedel (E301), konserveringsmedel (E250). Stekfläsk är en rå produkt som ska tillagas före användning.'),
]


@pytest.mark.parametrize('code,declaration', CASES)
def test_exact_review_binds_composition_context_and_purchase_but_not_personal_facts(code, declaration):
    key,row,proof = next((key,row,proof) for key,row in entries().items()
        for proof in row.get('reviewed_links', ()) if proof.get('retailer_product_id') == code)
    p=product(proof['name'],proof['package_quantity'],'g',20,
        identity=proof['product_id'],store=proof['store_id']).model_copy(update={
            'brand':proof['brand'],'category':proof['category'],'gtin':proof['gtin'],
            'source_provenance':SourceProvenance.model_validate(proof['source_provenance'])})
    f=ProductFacts(source=proof['quantity']['source']['url'],source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id,retailer_product_id=code,
        ingredients=(declaration,),ingredients_complete=True,ingredient_evidence_kind='product_declaration')
    assert compatible(key,p,f)
    assert not compatible(key,p,replace(f,ingredients=(declaration+' Different composition',)))
    assert not compatible(key,p.model_copy(update={'store_id':'unreviewed-context'}),f)
    assert not compatible(key,p,replace(f,source_snapshot_id='different-source'))
    checkout=PurchaseQuantityResolver().resolve(p,required_quantity=p.package_quantity+1,required_unit='g')
    assert checkout.packages_needed==2 and checkout.total_price==40
    with pytest.raises(PolicyConflict) as unknown:
        check_product(p,TasteProfile(allergies=['jordnötter']),f)
    assert unknown.value.code=='DATA_BLOCKED'
    with pytest.raises(PolicyConflict) as organic:
        check_product(p,TasteProfile(),f,organic_animals=True)
    assert organic.value.code=='DATA_BLOCKED'
    if code=='101234770_ST':
        with pytest.raises(PolicyConflict):
            check_product(p,TasteProfile(allergies=['sesam']),f)
    from app.services.complete_recipes import product_form_compatible
    from app.services.recipe_library import current_recipes
    recipe=next(r for r in current_recipes() if any(i.name==row['name'] for i in r.ingredients))
    assert product_form_compatible(recipe,row['name'],p,f)
