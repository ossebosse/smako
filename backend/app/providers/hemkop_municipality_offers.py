"""Hemköp's qualified physical additions reuse the established optional OWN provider."""
from app.providers.ica_area_offers import IcaAreaOfferProvider


class HemkopMunicipalityOfferProvider(IcaAreaOfferProvider):
    offer_chain = 'hemkop'
    accepted_parsers = frozenset({'hemkop-physical-offers-v1', 'hemkop-physical-offers-v2'})
    source_name = 'hemkop-municipality-offers'
    attribution_text = 'Frivilliga butiksspecifika Hemköp-erbjudanden'

    def exact_variant(self, product, fields, account):
        return (fields.get('hemkop_physical_policy') == 'hemkop-physical-singleton-offers-v1'
                and fields.get('verified_store_scope') is True
                and (fields.get('source_variant_id') or product.purchase_terms
                     and product.purchase_terms.usage == 'variant_selection_required')
                and fields.get('source_query', {}).get('q') == account
                and not fields.get('purchase_blockers'))

    def report(self):
        return {**self.base.report(), 'hemkop_municipal_offers': self.diagnostics}

    def retailer_identity(self, fields):
        if not fields.get('source_variant_id'):
            return {}  # Open campaign identity must not impersonate its display variant.
        return {'retailer_product_id': fields['source_variant_id'],
            'retailer_id_namespace': 'hemkop:public-product',
            'retailer_identity_source_sha256': fields['source_sha256']}
