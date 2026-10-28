"""Reviewed ribbon shape and drained fish mass preserve separate food forms."""
from dataclasses import replace

import pytest
from app.models.provenance import SourceProvenance
from app.services import intake_product_links as links
from app.services.complete_recipes import product_form_compatible
from app.services.official_product_facts import project_usable_quantity
from app.services.personal_policy import ProductFacts
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver
from app.services.recipe_library import current_recipes

from backend.tests.test_personal_planning_v2 import product


@pytest.mark.parametrize('name,gtin', [('sardiner', '7340083483448'), ('breda risnudlar', '7311043018758'), ('svart te', None)])
def test_reviewed_contents_and_culinary_forms_remain_exact_and_separate(name, gtin, monkeypatch):
    key, row, proof = next((key, row, proof) for key, row in links.entries().items()
        for proof in row.get('reviewed_links', ()) if row['name'] == name and proof.get('gtin') == gtin)
    quantity = proof['quantity']; usable = quantity['usable_quantity']
    p = product(proof['name'], proof['package_quantity'], 'g', 20,
        identity=proof['product_id'], store=proof['store_id']).model_copy(update={
            'gtin': gtin, 'brand': proof['brand'], 'category': proof['category'],
            'source_provenance': SourceProvenance.model_validate(proof['source_provenance'])})
    f = ProductFacts(source=quantity['source']['url'], source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id,
        ingredients=(quantity['declared_ingredients'],), ingredients_complete=True,
        ingredient_evidence_kind='product_declaration', field_sources={
            'usable_quantity': ({'basis': 'drained', 'unit': 'g', 'quantity': usable,
                'source': quantity['source']['url']},)} if row['form'] == 'preserved_drained' else {})
    q = project_usable_quantity(p, f, required_unit='g')
    assert links.compatible(key, q, f)
    assert q.package_quantity == p.package_quantity and q.usable_quantity == usable
    assert q.quantity_confidence == 'exact' and q.source_provenance == p.source_provenance
    recipe = next(r for r in current_recipes() if any(row['requirements'][0] in (i.product_requirements or ()) for i in r.ingredients))
    assert product_form_compatible(recipe, row['name'], q, f)
    if name == 'breda risnudlar':
        entries = links.entries()
        with monkeypatch.context() as scoped:
            scoped.setattr(links, 'entries', lambda: {**entries, key: {**row, 'reviewed_links': []}})
            assert not product_form_compatible(recipe, row['name'], q, f)
        assert not product_form_compatible(recipe, row['name'], q, replace(f, conflicts=('unknown_form',)))
    quote = PurchaseQuantityResolver().resolve(q, required_quantity=usable+1, required_unit='g')
    assert quote.packages_needed == 2 and quote.purchased_quantity == 2*p.package_quantity
    assert quote.purchased_usable_quantity == 2*usable and quote.total_price == 40
    changed = replace(f, ingredients=('tomato sauce' if row['name'] == 'sardiner' else 'wheat noodles',))
    assert not links.compatible(key, q, changed)
    assert not links.compatible(key, q, replace(f, source_snapshot_id='other'))
    assert not links.compatible(key, q, replace(f, conflicts=('nutrition.package_quantity',)))
    other = 'råa räkor' if row['name'] == 'sardiner' else 'risvermicelli'
    assert not links.ingredient_product(other, row['form'], row['requirements'], q, f)
    assert not f.nutrition and not f.allergens_checked and f.organic is None
    if row['name'] == 'sardiner':
        assert p.package_quantity == 120 and q.usable_quantity == 85
        assert not links.ingredient_product('sardiner', 'raw_edible', row['requirements'], q, f)
