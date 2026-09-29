"""Saved public connector responses, no network and no invented source facts."""
from pathlib import Path

import pytest

from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import RawBatch, SourceStore
from grocery_data.app.services.ica_area_offers import offer_store_proposal


@pytest.mark.parametrize('account,bms,parsed,rejected', [
    ('1004598', '15172', 56, {'5004133713', '5004224693', '5004224713'}),
    ('1004339', '2774', 45, {'5004125026', '2005238259', '2005464327', '5004125029'}),
])
def test_real_deposit_unknown_remains_quarantined_without_changing_denominator(account, bms, parsed, rejected):
    raw = RawBatch.model_validate_json((Path(__file__).parent / 'fixtures/ica/area-20260916' / f'{account}.json').read_bytes())
    store = SourceStore(chain='ica', external_id=account, name='Fixture source store', city='Lund',
                        raw_reference='fixture', coverage='offers_only', source_fields={'store_id': bms})
    result = IcaParser().parse_catalog(raw, ['saved-public-response'], store)
    assert len(result.products) == parsed
    assert {f.sample['id'] for f in result.failures} == rejected
    assert all(f.error_message.startswith('deposit_amount_unverified:') for f in result.failures)
    assert parsed / (parsed + len(rejected)) < .95
    assert all(p.fetched_at == raw.documents[0].fetched_at for p in result.products)
    assert not rejected & {p.external_product_id for p in result.products}


def test_store_proposal_requires_complete_verified_inventory_and_keeps_failed_stores():
    row = {'ica_account_id': 'official-id', 'area_membership': 'inside',
           'area_reason': 'official_address_locality_matches_existing_area', 'collection_status': 'error'}
    coverage = {'inventory': {'complete': True}, 'stores': [row]}
    assert offer_store_proposal(coverage)['ica_offer_store_ids'] == ['official-id']
    coverage['inventory']['complete'] = False
    assert offer_store_proposal(coverage)['ica_offer_store_ids'] == []
