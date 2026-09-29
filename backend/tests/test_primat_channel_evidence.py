import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from app.models.provenance import SourceProvenance
from app.providers.primat import PrimatPriceProvider
from app.services.primat_frozen_cache_collect import _normalized_product, _normalized_store
from app.services.primat_store_discovery_export import primat_store_discovery_bundle

from grocery_data.app.domain.enums import Chain, CoverageLevel, PriceContextType
from grocery_data.app.domain.price_context_evidence import (
    PriceContextEvidence,
    observed_store_channel,
)


@pytest.mark.parametrize('source', [None, 'physical_store', 'online_store'])
async def test_future_resolution_distinguishes_source_from_default(source):
    row = {'store_id': '1088004', 'key': 'ica:1088004', 'chain': 'ica',
           'name': 'Maxi Gunnesbo', 'city': 'Lund'}
    if source:
        row['price_context_type'] = source
    client = httpx.AsyncClient(base_url='https://primat.nu/api/v3/',
        transport=httpx.MockTransport(lambda request: httpx.Response(
            200, request=request, json={'stores': [row], 'place': {'locality': 'Lund'}})))
    provider = PrimatPriceProvider(api_key='synthetic-test-key', client=client)
    async with client:
        resolution = await provider.resolve_store_candidates('22350')
    candidate = primat_store_discovery_bundle(resolution).items[0]
    evidence = candidate.price_context_evidence
    assert evidence.source_state == ('explicit' if source else 'missing')
    assert evidence.source_value == source
    assert evidence.assignment_basis == ('source_field' if source else 'legacy_physical_store_default')
    # Existing effective channel behavior is preserved, never reclassified.
    assert candidate.price_context_type == (source or 'physical_store')
    assert evidence.scope == 'store_metadata'
    assert candidate.observed_at == resolution.observed_at
    derived = evidence.assigned('persisted_grocery_context')
    assert derived.source_value == evidence.source_value
    assert derived.source_state == evidence.source_state
    assert derived.assignment_basis == 'persisted_grocery_context'
    product = provider._parse_product({
        'chain': 'ica', 'store_id': '1088004', 'product_id': 'synthetic-pasta',
        'name': 'Pasta 500 g', 'amount': 500, 'unit': 'g', 'prices': {'regular': 19.9},
    })
    assert product is not None
    assert product.source_provenance.price_context_evidence.assignment_basis == 'store_metadata'
    context = SimpleNamespace(store=resolution.stores[0], eligible=SimpleNamespace(
        coverage=CoverageLevel.FULL_CATALOG, price_context_type=PriceContextType.PHYSICAL_STORE,
        physical_store_external_id='1088004', chain=Chain.ICA, provider_store_id='1088004'))
    normalized = _normalized_product(product, context=context, resolution=resolution)
    store = _normalized_store(context)
    for prov in (normalized.source_provenance, store.source_provenance):
        assert prov.price_context == 'physical_store'
        assert prov.price_context_evidence.source_value == source
        assert prov.price_context_evidence.source_state == ('explicit' if source else 'missing')
        assert prov.price_context_evidence.assignment_basis == 'persisted_grocery_context'
        assert prov.source_observed_at == resolution.observed_at


def test_legacy_provenance_serialization_is_unchanged_and_time_is_preserved():
    old = {'source_provider': 'primat', 'source_channel': 'catalog',
           'source_snapshot_id': 'historical-fixture',
           'source_observed_at': datetime(2026, 8, 24, tzinfo=UTC),
           'price_context': 'physical_store'}
    row = SourceProvenance.model_validate(old)
    assert row.price_context_evidence is None
    assert 'price_context_evidence' not in row.model_dump(mode='json')
    assert row.price_context == 'physical_store'
    assert row.source_observed_at == old['source_observed_at']
    roundtrip = SourceProvenance.model_validate_json(row.model_dump_json())
    assert roundtrip.model_dump_json() == row.model_dump_json()


def test_missing_and_unrecognized_are_not_explicit_source_evidence():
    with pytest.raises(ValueError):
        PriceContextEvidence(source_state='missing', assignment_basis='source_field')
    evidence = observed_store_channel('unknown-private-value')
    assert evidence.source_state == 'unrecognized'
    assert evidence.source_value is None
    assert 'unknown-private-value' not in json.dumps(evidence.model_dump(mode='json'))
