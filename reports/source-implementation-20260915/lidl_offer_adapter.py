"""Isolated adapter of the explicitly reviewed Sep15 candidate; no activation.

All source observations are retained. Contract identity hashes the exact
candidate and review version, so no future campaign inherits the approval.
"""
import hashlib
import json
from datetime import datetime

from app.models.product import OfferMetadata, Product
from app.models.provenance import SourceProvenance
from app.models.store import Store
from app.providers.federated import FederatedGroceryPriceProvider


def candidate_models(candidate):
    physical = candidate['products'][0]['physical_store']
    snapshot = 'lidl-national:' + hashlib.sha256(
        json.dumps(candidate, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:24]
    store = Store(
        store_id='own:lidl:0303', name=physical['name'], chain='lidl',
        city=physical['city'], postal_code=physical['postal_code'],
        address=physical['address'], latitude=physical['latitude'],
        longitude=physical['longitude'], physical_store_external_id='public_feedback_tnc:0303',
        price_context_type='physical_store', coverage='offers_only',
        source_store_id='0303',
    )
    store = store.model_copy(update={'store_id': FederatedGroceryPriceProvider._context_id(store)})
    observed = min(datetime.fromisoformat(p['observed_at']) for p in candidate['products'])
    provenance = SourceProvenance(
        source_provider='own', source_channel='national_flyer_offer',
        source_snapshot_id=snapshot, source_observed_at=observed,
        chain='lidl', store_id=store.store_id, store_name=store.name,
        provider_store_id='public_feedback_tnc:0303', price_context='physical_store',
        coverage='offers_only', source_role='EXPERIMENTAL_ISOLATED',
    )
    store = store.model_copy(update={'source_provenance': provenance})
    products = []
    for row in candidate['products']:
        if not row.get('eligible_for_isolated_planning') or row['coverage'] != 'offers_only':
            raise ValueError('reviewed isolated offer required')
        if row['national_flyer_id'] != row['review']['flyer_id']:
            raise ValueError('exact reviewed campaign identity required')
        if row['id'] != row['review']['product_id'] or row['gtin'] != row['review']['gtin']:
            raise ValueError('exact reviewed product identity required')
        price = float(row['sale_price'])
        products.append(Product(
            product_id=row['id'], name=row['name'], canonical_name=row['canonical_food'],
            canonical_food=row['canonical_food'], category=' > '.join(row['category']),
            store_id=store.store_id, store_name=store.name, chain='lidl', gtin=row['gtin'],
            price_context_type='physical_store', coverage='offers_only',
            package_quantity=float(row['package_quantity']), package_unit=row['package_unit'],
            usable_quantity=float(row['usable_quantity']), usable_unit=row['usable_unit'],
            quantity_confidence='exact', semantic_confidence=row['semantic_confidence'],
            sale_model='fixed_package', sale_price=price, sale_unit=row['package_unit'],
            price=None, effective_price=price,
            comparison_price=float(row['comparison_price']),
            comparison_unit=row['comparison_unit'],
            offers=[OfferMetadata(
                kind='campaign', description=f"Verifierat nationellt reklamblad {row['national_flyer_id']}",
                price=price, max_quantity=row['max_packages'],
                valid_from=row['valid_from'], valid_to=row['valid_to'],
                price_contract_id=f"{snapshot}:{row['id']}",
            )],
            source_provenance=provenance.model_copy(update={
                'source_observed_at': datetime.fromisoformat(row['observed_at'])
            }),
        ))
    return store, products

