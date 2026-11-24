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


def test_scope_starved_by_a_peer_goes_first_next_run(tmp_path, monkeypatch):
    """Malmö Willys starved behind Lund for three weeks (2026-11)."""
    clock = [0.0]
    monkeypatch.setattr(relay, 'monotonic', lambda: clock[0])
    order = []

    def run_scope(scope, **kwargs):
        code = scope.name.removeprefix('municipality-')
        order.append(code)
        if len(order) % 2 == 1:      # whoever runs first uses most of the window
            clock[0] += 5000
            return 0
        return 2                      # the second one runs out of collection time

    scopes = [{'municipality_code': '1281'}, {'municipality_code': '1280'}]
    for _ in range(4):
        relay.run_municipalities(tmp_path, RelayTransport(), scopes=scopes, run_scope=run_scope)
    firsts = order[0::2]
    assert set(firsts[:2]) == {'1280', '1281'}     # turns alternate
    assert firsts[0] != firsts[1] and firsts[1] != firsts[2] and firsts[2] != firsts[3]
