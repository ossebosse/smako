from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from app.providers.own import OwnGroceryPriceProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong", [None, "address", "physical_store_external_id", "price_context_type"])
async def test_municipal_provider_adds_exact_store_across_localities_without_other_chains(wrong):
    requests = []

    def row(store_id, chain, city):
        result = {"id": chain + ":" + store_id, "external_id": store_id, "chain": chain,
                  "name": "Test " + store_id, "city": city, "postal_code": "21611", "address": "Gatan 1",
                  "coverage": "full_catalog", "active": True, "price_context_type": "online_store",
                  "physical_store_external_id": store_id, "snapshot_id": "approved",
                  "observed_at": datetime.now(UTC).isoformat(), "data_age_hours": 0, "connector_status": "healthy"}
        if wrong and store_id == "2144":
            result[wrong] = "incorrect"
        return result

    def handler(request):
        requests.append(dict(request.url.params))
        city = request.url.params.get("city")
        records = [row("2144", "willys", "Limhamn"), row("extra", "coop", "Limhamn")] if city else [row("2244", "willys", "Malmö")]
        return httpx.Response(200, json={"items": records})

    evidence = {"2144": SimpleNamespace(external_id="2144", city="Limhamn", address="Gatan 1", postal_code="216 11")}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://own.example/") as client:
        provider = OwnGroceryPriceProvider("https://own.example", client=client, municipal_willys_stores=evidence)
        result = await provider.find_stores("21120")
    assert {s.source_store_id for s in result} == ({"2144"} if wrong is None else set())
    assert any(r.get("city") == "Limhamn" for r in requests)


@pytest.mark.asyncio
async def test_no_municipal_opt_in_preserves_existing_postal_query():
    requests = []

    def handler(request):
        requests.append(dict(request.url.params))
        return httpx.Response(200, json={"items": [{"id": "willys:2176", "external_id": "2176", "chain": "willys",
            "name": "Willys", "city": "Lund", "postal_code": "22363", "coverage": "full_catalog",
            "active": True, "snapshot_id": "old", "connector_status": "healthy", "data_age_hours": 1,
            "observed_at": datetime.now(UTC).isoformat()}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://own.example/") as client:
        result = await OwnGroceryPriceProvider("https://own.example", client=client).find_stores("22350")
    assert len(result) == 1 and requests == [{"postal_code": "22350", "limit": "500", "offset": "0"}]


@pytest.mark.asyncio
async def test_hemkop_municipal_catalog_requires_exact_official_suburb_store():
    def handler(request):
        rows = [{"id": "hemkop:4247", "external_id": "4247", "chain": "hemkop", "name": "Test",
            "city": "Limhamn", "postal_code": "21611", "address": "Gatan 1", "coverage": "full_catalog",
            "price_context_type": "online_store", "physical_store_external_id": "4247", "active": True,
            "snapshot_id": "approved", "connector_status": "healthy", "data_age_hours": 1,
            "observed_at": datetime.now(UTC).isoformat()}]
        return httpx.Response(200, json={"items": rows if request.url.params.get("city") == "Limhamn" else []})

    evidence = {"4247": SimpleNamespace(external_id="4247", city="Limhamn", address="Gatan 1", postal_code="21611")}
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://own.example/") as client:
        provider = OwnGroceryPriceProvider("https://own.example", client=client, municipal_hemkop_stores=evidence)
        assert len(await provider.find_stores("21120")) == 1
        evidence["4247"].address = "Other address"
        assert not await provider.find_stores("21120")


@pytest.mark.asyncio
async def test_missing_approved_context_blocks_artifact_publication(tmp_path, monkeypatch):
    from app.services.production_price_universe_build import build_city_price_universe

    from backend.tests.test_own_provider_grocery_data_contract import _contract_database
    from backend.tests.test_production_price_universe_build import _copy_sqlite_database
    from grocery_data.app.services import willys_municipal_scope

    scopes = {key: SimpleNamespace(external_id=key, city="Lund", address="Företagsvägen 10", postal_code="227 61")
              for key in ("2354", "missing-approved-store")}
    monkeypatch.setattr(willys_municipal_scope, "approved_snapshot_stores", lambda *_: scopes)
    engine, _ = _contract_database()
    database = tmp_path / "source.sqlite"
    _copy_sqlite_database(engine, database)
    engine.dispose()
    output = tmp_path / "candidate.json"
    with pytest.raises(RuntimeError, match="contexts missing"):
        await build_city_price_universe(database, "Lund", "22350", None, output, 48)
    assert not output.exists()
