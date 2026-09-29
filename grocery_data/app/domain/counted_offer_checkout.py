"""Route explicit document sales-unit counts through the existing checkout.

This does not price anything and never changes a piece into a weight/package.
Other non-fixed models keep their existing conservative behaviour.
"""


def uses_counted_offer_checkout(item):
    if item.sale_model == 'fixed_package':
        return True
    provenance = item.source_provenance
    offers = getattr(item, 'offers', None) or getattr(item, 'checkout_offers', ())
    terms = getattr(item, 'purchase_terms', None)
    if terms and ((terms.purchase_form == 'piece' and terms.usage == 'exact') or getattr(item, 'conditional_variant_choice', False)):
        return bool(item.sale_model == 'sold_by_piece' and offers
                    and all(o.price_basis_unit == 'package' and o.campaign_evidence for o in offers))
    prefix = {'willys:flyer-document-ad':'willys:household:',
              'lidl:public-product':'lidl:household:'}.get(provenance.retailer_id_namespace) if provenance else None
    return bool(item.sale_model == 'sold_by_piece'
        and provenance and prefix
        and provenance.source_channel == 'offers' and item.coverage == 'offers_only'
        and item.package_quantity == 1 and item.package_unit == 'st'
        and item.usable_quantity == 1 and item.usable_unit == 'st'
        and not item.estimated_piece_weight and not item.variable_weight
        and offers and all(o.campaign_evidence and o.price_contract_id
            and o.price_contract_id.startswith(prefix) for o in offers))
