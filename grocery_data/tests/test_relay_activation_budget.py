"""Leave room for municipal publication without extending the scheduled task."""
import json

import pytest

from grocery_data import local_relay as relay
from grocery_data.relay_config import RelayTransport


@pytest.mark.parametrize('budget,expected', [(3299, None), (3300, 600), (4000, 1300)])
def test_delivery_reserve_can_defer_collection(tmp_path, monkeypatch, budget, expected):
    monkeypatch.setattr(relay, 'monotonic', lambda: 0.0)
    calls = []

    def run_scope(scope, **kwargs):
        calls.append(kwargs['collection_seconds'])
        return 0

    result = relay.run_municipalities(tmp_path, RelayTransport(),
        scopes=[{'municipality_code': '1280'}], run_scope=run_scope, budget_seconds=budget)
    assert calls == ([] if expected is None else [expected])
    assert result == (1 if expected is None else 0)
    if expected is None:
        status = json.loads((tmp_path / 'municipal-relay-status.json').read_bytes())
        assert status['municipalities'][0]['reason'] == 'run_window'


def test_elapsed_first_scope_reduces_next_collection_not_delivery_reserve(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(relay, 'monotonic', lambda: clock[0])
    calls = []

    def run_scope(scope, **kwargs):
        calls.append(kwargs['collection_seconds'])
        clock[0] += 4500
        return 0

    assert relay.run_municipalities(tmp_path, RelayTransport(), scopes=[
        {'municipality_code': '1281'}, {'municipality_code': '1280'},
    ], run_scope=run_scope) == 0
    assert calls == [7200, 3000]
    assert calls[-1] + relay.ACTIVATION_TIMEOUT_SECONDS == 10200 - 4500
