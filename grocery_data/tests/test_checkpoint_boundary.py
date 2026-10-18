"""Response metadata must not invalidate geography-bound traversal reuse."""
import json
from copy import deepcopy
from hashlib import sha256

import pytest

from grocery_data.app.services.catalog_checkpoint import _boundary_identity
from grocery_data.tests.test_willys_municipality import FIXTURE


def encode(boundary, payload):
    boundary['payload'] = json.dumps(payload)
    boundary['source_sha256'] = sha256(boundary['payload'].encode()).hexdigest()
    return boundary


@pytest.mark.parametrize('code', ['1281', '1280'])
def test_response_timestamp_only_preserves_identity_and_raw_evidence(code):
    first = deepcopy(FIXTURE['boundary-' + code])
    payload = json.loads(first['payload'])
    payload['timeStamp'] = '2026-10-18T21:13:23.503Z'
    encode(first, payload)
    second = deepcopy(first)
    payload['timeStamp'] = '2026-10-18T22:13:02.725Z'
    encode(second, payload)
    second['observed_at'] = payload['timeStamp']
    original = deepcopy((first, second))
    assert first['source_sha256'] != second['source_sha256']
    assert _boundary_identity(first) == _boundary_identity(second)
    assert (first, second) == original


@pytest.mark.parametrize('change', ['geometry', 'properties', 'crs', 'extra_payload', 'source_url', 'documentation'])
def test_other_boundary_changes_invalidate_identity(change):
    first = deepcopy(FIXTURE['boundary-1280'])
    second = deepcopy(first)
    payload = json.loads(second['payload'])
    if change == 'geometry':
        def shift(coordinates):
            if isinstance(coordinates[0], (int, float)):
                coordinates[0] += 0.0001
            else:
                for child in coordinates:
                    shift(child)
        shift(payload['features'][0]['geometry']['coordinates'])
    elif change == 'properties':
        payload['features'][0]['properties']['review_test'] = 'changed'
    elif change == 'crs':
        payload['crs']['properties']['name'] = 'EPSG:4326'
        assert payload['crs'] != json.loads(first['payload'])['crs']
    elif change == 'extra_payload':
        payload['unreviewedMetadata'] = 'changed'
    else:
        second[change] += '&review_test=changed'
    encode(second, payload)
    assert _boundary_identity(first) != _boundary_identity(second)


@pytest.mark.parametrize('damage', ['raw_hash', 'count', 'municipality', 'version', 'timestamp_type', 'timestamp_naive'])
def test_unverified_boundary_cannot_supply_checkpoint_identity(damage):
    boundary = deepcopy(FIXTURE['boundary-1280'])
    payload = json.loads(boundary['payload'])
    if damage == 'count':
        payload['numberReturned'] += 1
    elif damage == 'timestamp_type':
        payload['timeStamp'] = 42
    elif damage == 'timestamp_naive':
        payload['timeStamp'] = '2026-10-18T22:00:00'
    encode(boundary, payload)
    if damage == 'raw_hash':
        boundary['source_sha256'] = '0' * 64
    elif damage == 'municipality':
        boundary['municipality_code'] = '1281'
    elif damage == 'version':
        boundary['version'] = 'unreviewed'
    with pytest.raises(ValueError):
        _boundary_identity(boundary)
