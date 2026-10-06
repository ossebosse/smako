"""Verification-tool regressions; no mocked menu qualifies real food here."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def runner():
    path=Path(__file__).parents[2]/"scripts/release_verification/complete_recipe_browser.py"
    spec=importlib.util.spec_from_file_location("browser_evidence_test",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("injected",[False,True])
def test_invalid_body_is_retained_and_only_exact_injection_can_be_classified(injected):
    module=runner();observed=[]
    reference="exact-negative-reference"
    response=SimpleNamespace(url="http://127.0.0.1:18128/api/plans",status=500,
        headers={"content-type":"text/plain","x-request-id":reference},
        request=SimpleNamespace(method="POST",headers={"x-request-id":reference},
            post_data_json={},timing={"responseEnd":10}))
    def malformed():raise json.JSONDecodeError("empty response","",0)
    response.json=malformed
    module.record_response(response,observed)
    assert observed[0].body_error_kind=="invalid_json" and observed[0].captured_body is None
    page=SimpleNamespace(wait_for_timeout=lambda ms:None)
    fault={"scenario":"lost-start","injected":[{"url":response.url,
        "request_id":reference if injected else "different-reference",
        "kind":"lost_accepted_start_response"}]}
    # Even an exact injected error is never a fabricated successful result.
    with pytest.raises(AssertionError,match="No terminal" if injected else "Unexpected invalid JSON"):
        module.wait_operation(page,observed,0,timeout=.001,fault=fault)
