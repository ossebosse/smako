"""Retained v5 inventory projections with v6 raw picking validation."""
import json
from copy import deepcopy

import pytest

from grocery_data.app.connectors.willys.flyer_inventory import (
    approved_flyer_stores,
    build_inventory,
)
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.tests.test_willys_flyers import inventory


def flagged_inventory(code='1281', flag=False):
    original = inventory(code)
    raw = RawBatch.model_validate(original['registry'])
    rows = raw.documents[0].json_payload()
    for row in rows:
        if isinstance(row, dict):
            row['hasPickingBaseStore'] = flag
    document = raw.documents[0].model_copy(update={'payload': json.dumps(rows).encode()})
    changed = raw.model_copy(update={'documents': (document,)})
    return build_inventory(GeographicArea.model_validate(original['area']),
                           changed.model_dump(mode='json'), original['boundary'])


def legacy_projection(current):
    previous = deepcopy(current)
    for row in previous['stores']:
        row['store']['source_fields'].pop('hasPickingBaseStore', None)
    return previous


@pytest.mark.parametrize('code', ['1281', '1280'])
def test_v5_metadata_omission_preserves_exact_physical_selection_and_original_evidence(code):
    current = flagged_inventory(code)
    previous = legacy_projection(current)
    before = deepcopy(previous)
    expected = approved_flyer_stores(current)
    actual = approved_flyer_stores(previous)
    assert actual == expected
    assert set(actual) == set(current['selected_store_ids'])
    assert all(s.source_fields['hasPickingBaseStore'] is False for s in actual.values())
    assert previous == before
    assert all(s.online_shopping is False and s.price_context_type.value == 'physical_store'
               for s in actual.values())


@pytest.mark.parametrize('flag', [True, None, 0, 1, 'false'])
def test_invalid_original_register_flag_cannot_inherit_legacy_compatibility(flag):
    with pytest.raises(ValueError, match='picking base'):
        flagged_inventory(flag=flag)


@pytest.mark.parametrize('flag', [True, None, 0, 1, 'false'])
def test_forged_derived_flag_does_not_compare_equal_to_false(flag):
    current = flagged_inventory()
    current['stores'][0]['store']['source_fields']['hasPickingBaseStore'] = flag
    with pytest.raises(ValueError, match='picking metadata'):
        approved_flyer_stores(current)


@pytest.mark.parametrize('change', ['identity', 'address', 'selection', 'coordinates', 'raw_hash'])
def test_legacy_projection_does_not_hide_other_evidence_changes(change):
    previous = legacy_projection(flagged_inventory())
    row = next(r for r in previous['stores'] if r['collection_selected'])
    if change == 'identity':
        row['store']['external_id'] = 'invented'
    elif change == 'address':
        row['store']['address'] = 'Changed address'
    elif change == 'selection':
        row['collection_selected'] = False
    elif change == 'coordinates':
        row['store']['latitude'] = 0
    else:
        row['store']['source_fields']['coordinate_source']['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='differs from official evidence'):
        approved_flyer_stores(previous)
