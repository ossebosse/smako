import json
from pathlib import Path

import pytest

from grocery_data.app.domain import Chain
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.services.collector import _review_schema_diff

VERSION = 'hemkop-parser-v1.1-picking-contract'


def test_retained_two_paths_require_boolean_evidence_and_version():
    paths = ('4123:store_context:$[].hasPickingBaseStore', 'stores:$[][].hasPickingBaseStore')
    diff = SchemaDiff(added=paths)
    schemas = {p.rsplit(':', 1)[0]: {'paths': {p.rsplit(':', 1)[1]: ['boolean']}} for p in paths}
    assert _review_schema_diff(Chain.HEMKOP, VERSION, diff, schemas=schemas) is None
    assert _review_schema_diff(Chain.HEMKOP, 'hemkop-parser-v1', diff, schemas=schemas) == diff
    assert _review_schema_diff(Chain.HEMKOP, VERSION, diff) == diff
    schemas['stores']['paths']['$[][].hasPickingBaseStore'] = ['null', 'boolean']
    assert _review_schema_diff(Chain.HEMKOP, VERSION, diff, schemas=schemas).added == (paths[1],)


def test_original_reduced_rows_are_false_and_bound_to_expected_stores():
    from grocery_data.app.connectors.hemkop.models import validated_store_context
    fixture = json.loads((Path(__file__).parent / 'fixtures/hemkop-picking-store-20261008.json').read_text(encoding='utf-8'))
    for record in fixture['records']:
        for row in record['rows']:
            assert row['hasPickingBaseStore'] is False
            assert validated_store_context(row, row['storeId'])
            assert not validated_store_context(row, 'other-store')


@pytest.mark.parametrize('value', [None, 'false', 0, 1, True, {}, []])
def test_unknown_or_invalid_picking_binding_stops(value):
    from grocery_data.app.connectors.hemkop.models import validated_store_context
    assert not validated_store_context({'storeId': '4123', 'hasPickingBaseStore': value}, '4123')


def test_missing_remains_legacy_and_nested_wrong_identity_cannot_authorize():
    from grocery_data.app.connectors.hemkop.models import validated_store_context
    assert validated_store_context({'storeId': '4123'}, '4123')
    assert validated_store_context({'pickingStore': {'storeId': '4123'}}, '4123')
    assert not validated_store_context({'storeId': 'wrong', 'other': {'storeId': '4123'}}, '4123')
    assert not validated_store_context({'storeId': 'wrong', 'pickingStore': {'storeId': '4123'}}, '4123')
    assert not validated_store_context({'storeId': '4123', 'pickingStore': {'storeId': 'wrong'}}, '4123')

def test_authentic_campaign_conflict_and_two_legitimate_offers():
    from grocery_data.app.connectors.hemkop.client import _DuplicateTracker
    rows = json.loads((Path(__file__).parent / 'fixtures/hemkop-promotion-conflict-20261008.json').read_text(encoding='utf-8'))
    assert len(rows) == 2
    tracker = _DuplicateTracker.create()
    tracker.observe(rows[0]['product'], category_fingerprints={}, category_pages={}, page_number=0)
    with pytest.raises(ValueError, match='cross-partition duplicate changed semantic'):
        tracker.observe(rows[1]['product'], category_fingerprints={}, category_pages={}, page_number=0)
    # Both public multi-buy and loyalty single-price may coexist. Identical
    # evidence across categories passes; the conflicting absence above does not.
    product = rows[1]['product']
    assert len(product['potentialPromotions']) == 2
    tracker = _DuplicateTracker.create()
    for _ in range(2):
        tracker.observe(product, category_fingerprints={}, category_pages={}, page_number=0)
    assert tracker.cross_partition_duplicates == 1
    assert tracker.conflicting_duplicates == 0
