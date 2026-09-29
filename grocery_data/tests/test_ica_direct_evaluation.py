from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import Chain, GeographicArea, RawBatch, RawFetch
from grocery_data.scripts import evaluate_ica_direct as diagnostic

FIXTURES = Path(__file__).parents[1] / "app/connectors/ica/fixtures"


def mock_transport(monkeypatch, handler):
    original = httpx.AsyncClient

    def client(**kwargs):
        return original(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(diagnostic.httpx, "AsyncClient", client)


@pytest.mark.parametrize("status", [202, 401, 403, 405, 429])
async def test_access_stop_retains_no_body_or_identity_and_never_retries(
    monkeypatch, tmp_path, status
):
    requests = []

    def response(request):
        requests.append(request)
        assert "cookie" not in request.headers
        assert "authorization" not in request.headers
        return httpx.Response(
            status,
            headers={"Content-Type": "text/html"},
            text="Request blocked; sessionId=must-not-be-saved",
        )

    mock_transport(monkeypatch, response)
    result = await diagnostic.probe_catalog(
        "1088004", tmp_path, verified_online_url="https://handlaprivatkund.ica.se/stores/1088004"
    )
    assert len(requests) == 1
    assert result["returned_product_count"] == 0
    assert result["promotable"] is False
    assert result["catalog_completeness"] == "UNPROVEN"
    assert "must-not-be-saved" not in json.dumps(result)
    assert not list(tmp_path.iterdir())


async def test_successful_search_reuses_parser_but_cannot_prove_catalogue(monkeypatch, tmp_path):
    requests = []

    def response(request):
        requests.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/json"},
            content=(FIXTURES / "online_v6_product_page.json").read_bytes(),
        )

    mock_transport(monkeypatch, response)
    result = await diagnostic.probe_catalog(
        "1088004", tmp_path, verified_online_url="https://handlaprivatkund.ica.se/stores/1088004"
    )
    assert len(requests) == 1
    assert result["returned_product_count"] > 0
    assert result["accepted_global_prices"] == 0
    assert result["catalog_completeness"] == "UNPROVEN"
    assert result["promotable"] is False
    assert "region_id" not in result
    assert result["fetched_at"] != result["started_at"]
    assert requests[0].url.params["maxPageSize"] == "300"
    assert requests[0].url.params["maxProductsToDecorate"] == "50"


async def test_source_schema_change_does_not_become_an_empty_success(monkeypatch, tmp_path):
    mock_transport(monkeypatch, lambda _: httpx.Response(200, json={"renamedGroups": []}))
    result = await diagnostic.probe_catalog(
        "1088004", tmp_path, verified_online_url="https://handlaprivatkund.ica.se/stores/1088004"
    )
    assert result["classification"] == "transport_or_schema_error"
    assert result["accepted_global_prices"] == 0
    assert not list(tmp_path.iterdir())


async def test_no_unverified_store_or_overwrite(tmp_path):
    with pytest.raises(ValueError, match="allowlist"):
        await diagnostic.probe_catalog("FALADSTORGET", tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        await diagnostic.run(tmp_path, "all", "test")


@pytest.mark.parametrize(
    "url",
    [None, "https://www.ica.se/stores/1004409", "https://handlaprivatkund.ica.se/stores/1088004"],
)
async def test_no_online_mapping_means_no_request(monkeypatch, tmp_path, url):
    def no_network(*args, **kwargs):
        raise AssertionError("No network permitted without a verified online store URL")

    monkeypatch.setattr(diagnostic.httpx, "AsyncClient", no_network)
    result = await diagnostic.probe_catalog("1004409", tmp_path, verified_online_url=url)
    assert result["classification"] == "UNVERIFIED_ONLINE_MAPPING"
    assert result["request_count"] == 0


def test_observed_locator_ids_and_online_scope_are_not_interchangeable():
    raw = RawFetch(
        chain=Chain.ICA,
        kind="stores_page",
        method="GET",
        http_status=200,
        url="https://www.ica.se/butiker/oppettider/lund/",
        connector_version="ica-v2",
        payload=(FIXTURES / "direct_locator_20260914_sanitized.json").read_bytes(),
    )
    stores = IcaParser().parse_physical_stores(
        RawBatch(chain=Chain.ICA, documents=(raw,)), ["fixture"], GeographicArea(city="Lund")
    )
    mapped = {store.external_id: store for store in stores}
    assert set(mapped) == {"1088004", "1004409"}
    assert mapped["1088004"].source_fields["store_id"] == "17883"
    assert mapped["1088004"].source_fields["online_url"] == (
        "https://handlaprivatkund.ica.se/stores/1088004"
    )
    assert mapped["1004409"].source_fields["store_id"] == "2771"
    assert mapped["1004409"].source_fields["online_url"] is None
    assert mapped["1004409"].online_shopping is False
