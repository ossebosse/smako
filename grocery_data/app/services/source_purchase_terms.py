"""Validate adapter-bound PurchaseTerms at the existing row approval boundary."""
from grocery_data.app.domain.purchase_terms import PurchaseTerms


def bound_purchase_terms(product):
    """No legacy defaults: both retained source facts and offer must agree."""
    raw = product.source_fields.get('purchase_terms')
    if not raw or len(product.offers) != 1:
        return None
    terms = PurchaseTerms.model_validate(raw)
    offer = product.offers[0]
    if (offer.source_payload.get('purchase_terms') != terms.model_dump(mode='json')
            or terms.source_reference != product.source_fields.get('purchase_terms_reference', product.raw_reference)
            or terms.complete_group_size != (offer.quantity or 1)
            or terms.usage == 'blocked'):
        return None
    basis = offer.source_payload.get('price_basis_unit', 'package')
    if terms.purchase_form in {'loose_weight', 'variable_package'}:
        if basis != 'kg' or product.sale_unit != 'kg':
            return None
        if terms.purchase_form == 'variable_package' and not (terms.approximate_package_g or terms.minimum_package_g):
            return None
    elif basis != 'package':
        return None
    if terms.usage == 'exact' and (
            product.sale_unit != 'st' or not product.package_quantity or not product.package_unit):
        return None
    return terms
