"""A warm label requires positive, build-bound preparation evidence."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _gate(monkeypatch):
    path = Path(__file__).parents[2] / "scripts/release_verification/warm_preparation.py"
    spec = importlib.util.spec_from_file_location("warm_probe_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    clock = [0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    return module


def _evidence(**updates):
    return {"build_id": "build", "status": "ready", "preparation_status": "ready",
            "library_status": "ready", "universes": [{"universe_id": "lund", "status": "ready"},
                {"universe_id": "malmo", "status": "ready"}], **updates}


def _request(responses):
    def get(*args, **kwargs):
        status, evidence = responses.pop(0)
        return SimpleNamespace(status=status, json=lambda: evidence, dispose=lambda: None)
    return SimpleNamespace(get=get)


def test_warm_probe_waits_for_completion_outside_the_menu_clock(monkeypatch):
    module = _gate(monkeypatch)
    request = _request([(202, _evidence(status="not_ready")), (200, _evidence())])
    result = module.wait_for_warm_preparation(request, "https://example.test", build_id="build",
                                              universe_ids=["lund", "malmo"])
    assert result["observations"] == 2 and result["wait_seconds"] == 2
    assert result["evidence"] == _evidence()


@pytest.mark.parametrize("evidence", [_evidence(build_id="old"), _evidence(universes=[]),
    _evidence(library_status="failed"), _evidence(preparation_status="partial"),
    _evidence(universes=[{"universe_id": "lund", "status": "ready"},
                        {"universe_id": "malmo", "status": "unknown"}])])
def test_http_200_alone_does_not_certify_a_warm_probe(monkeypatch, evidence):
    module = _gate(monkeypatch)
    with pytest.raises(RuntimeError):
        module.wait_for_warm_preparation(_request([(200, evidence)]), "https://example.test",
                                        build_id="build", universe_ids=["lund", "malmo"])


def test_preparation_timeout_never_starts_a_warm_measurement(monkeypatch):
    module = _gate(monkeypatch)
    with pytest.raises(TimeoutError, match="no warm latency measurement"):
        module.wait_for_warm_preparation(_request([(202, _evidence(status="not_ready"))]),
            "https://example.test", build_id="build", universe_ids=["lund", "malmo"], timeout=1)
