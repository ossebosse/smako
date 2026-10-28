"""Offline boundary checks for the explicitly authorized five-article pilot."""
import asyncio
import importlib.util
import json
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from grocery_data.app.api.health import connector_health_detail
from grocery_data.app.connectors.base import SourcePolicyError
from grocery_data.app.connectors.registry import ConnectorRegistry
from grocery_data.app.connectors.specialist_pilot import (
    PILOT_PAGES,
    SpecialistPilotClient,
    sanitize_public_html,
)
from grocery_data.app.domain.enums import DEFAULT_SOURCE_CHAINS, Chain
from grocery_data.app.domain.raw import RawBatch
from grocery_data.app.domain.source_strategy import CHAIN_SOURCE_STRATEGIES, source_strategy_for
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore


def test_pilot_identities_do_not_expand_default_sources():
    assert set(DEFAULT_SOURCE_CHAINS) == set(CHAIN_SOURCE_STRATEGIES)
    assert len(DEFAULT_SOURCE_CHAINS) == 6
    assert not set(PILOT_PAGES) & set(DEFAULT_SOURCE_CHAINS)
    for chain in PILOT_PAGES:
        with pytest.raises(RuntimeError, match="no source strategy"):
            source_strategy_for(chain)
        with pytest.raises(NotImplementedError, match="not enabled"):
            ConnectorRegistry().create(chain)
        with pytest.raises(HTTPException) as error:
            connector_health_detail(chain, session=None)
        assert error.value.status_code == 404
    products = {chain: set(pages) - {"delivery", "terms", "category"} for chain, pages in PILOT_PAGES.items()}
    assert products == {Chain.PONGMARKET: {"BW0003", "PMSM0014", "PMSM0031"},
                        Chain.MED24: {"9576"}, Chain.EXTREMEFOOD: {"944"}}


def test_public_retention_drops_session_state_and_preserves_product_declaration():
    payload = b'''<h1>Tapioca 400g</h1><div>20 kr</div>
    <form><input name="csrf" value="private-a">private-form-data</form>
    <script>window.session="private-b";</script><style>.secret{display:none}</style>
    <script type="application/ld+json">{"@graph":[
    {"@type":"Person","name":"private-c"},
    {"@type":"Product","sku":"BW0003","name":"Tapioca 400g","session":"private-d",
     "offers":{"@type":"Offer","price":"20.00","priceCurrency":"SEK","token":"private-e",
       "url":"https://shop.example/product?session=private-schema"}}]}</script>
    <a href="/checkout/session-private">checkout</a><a href="/product?token=private-f">product</a>
    <a href="javascript:private-g">bad</a><a href="/944-maseca.html">Maseca</a>'''
    result = sanitize_public_html(payload)
    assert b"private-" not in result
    data = json.loads(result)
    assert data["headings"] == ["Tapioca 400g"]
    assert data["product_json_ld"][0]["offers"]["price"] == "20.00"
    assert data["public_links"] == ["/944-maseca.html"]
    assert data["transport_body_sha256"]


def test_no_opt_in_and_unlisted_article_fail_before_network():
    async def check():
        def unexpected(request):
            pytest.fail("No request is permitted")
        async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as transport:
            client = SpecialistPilotClient(Chain.PONGMARKET, client=transport)
            with pytest.raises(SourcePolicyError):
                await client.fetch("BW0003")
            client.operator_opt_in = True
            with pytest.raises(ValueError, match="allowlist"):
                await client.fetch("BW0004")
    asyncio.run(check())


@pytest.mark.parametrize("status", [302, 404, 500])
def test_failed_response_is_not_product_evidence_and_redirect_is_not_followed(status):
    async def check():
        requests = []
        def response(request):
            requests.append(request)
            return httpx.Response(status, headers={"Location": "https://unreviewed.example/"},
                                  content=b"error private-body")
        async with httpx.AsyncClient(transport=httpx.MockTransport(response), follow_redirects=True) as transport:
            client = SpecialistPilotClient(Chain.MED24, operator_opt_in=True, client=transport)
            result = await client.fetch("9576")
            assert len(requests) == 1
            assert result.http_status == status
            assert json.loads(result.payload)["usable_product_evidence"] is False
            assert b"private-body" not in result.payload
    asyncio.run(check())


def test_failed_attempt_keeps_previous_evidence_and_reports_incomplete(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[2] / "scripts/fetch_specialist_pilot.py"
    spec = importlib.util.spec_from_file_location("specialist_pilot_command", script)
    command = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(command)

    status = 200
    monkeypatch.setattr(command, "PILOT_PAGES", {Chain.MED24: {"9576": PILOT_PAGES[Chain.MED24]["9576"]}})

    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(status, content=b"<h1>Product</h1>"))) as transport:
            monkeypatch.setattr(command, "SpecialistPilotClient", lambda chain, operator_opt_in:
                SpecialistPilotClient(chain, operator_opt_in=operator_opt_in, client=transport))
            return await command.collect(tmp_path, opt_in=True)

    assert asyncio.run(check()) is True
    originals = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    status = 404
    assert asyncio.run(check()) is False
    assert all(p.read_bytes() == data for p, data in originals.items())
    summaries = [json.loads(p.read_text()) for p in tmp_path.glob("attempts/*/summary.json")]
    assert sorted(item["complete"] for item in summaries) == [False, True]
    assert all(item["price_activation"] is False for item in summaries)


@pytest.mark.parametrize("status,body", [(403, b"denied private-token"), (429, b"rate limit"),
                                       (200, b"verify you are human private-token")])
def test_access_restriction_stops_source_without_retry_or_body_retention(status, body):
    async def check():
        requests = []
        def response(request):
            requests.append(request)
            return httpx.Response(status, content=body)
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as transport:
            client = SpecialistPilotClient(Chain.PONGMARKET, operator_opt_in=True, client=transport)
            document = await client.fetch("BW0003")
            assert document.kind == "access_stopped" and b"private-token" not in document.payload
            with pytest.raises(ValueError, match="stopped"):
                await client.fetch("PMSM0014")
            assert len(requests) == 1
    asyncio.run(check())


def test_observation_is_stored_and_hash_verified_before_qualification(tmp_path):
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(200, content=b'<h1>Rice flour 500g</h1><div>33 kr</div>'))) as transport:
            client = SpecialistPilotClient(Chain.PONGMARKET, operator_opt_in=True, client=transport)
            document = await client.fetch("PMSM0031")
            store = FilesystemRawSnapshotStore(tmp_path)
            record = store.save_batch(RawBatch(chain=client.chain, documents=(document,)), snapshot_id="pilot-test")[0]
            assert record.fetched_at == document.fetched_at
            assert json.loads(store.load(record))["headings"] == ["Rice flour 500g"]
            record.resolve(tmp_path).write_bytes(b"changed")
            with pytest.raises(ValueError, match="integrity"):
                store.load(record)
    asyncio.run(check())
