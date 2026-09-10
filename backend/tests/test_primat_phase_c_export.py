from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from app.errors import PriceProviderAccessChallengeError
from app.models import SourceProvenance, Store
from app.providers.primat import PrimatPriceProvider
from app.services.primat_phase_c_export import (
    BoundedPrimatPhaseCExporter,
    PrimatPhaseCExportError,
    PrimatPhaseCInvariant,
    load_active_physical_stores,
    write_closed_json,
)
from scripts.benchmark_lund_phase_c import _FrozenExternalProvider
from scripts.export_lund_primat_contexts import _closed_stop_result
from scripts.export_lund_primat_contexts import _run as run_context_bootstrap

from grocery_data.app.domain import Chain
from grocery_data.app.domain.store import PhysicalStore

BASE_URL = "https://primat.nu/api/v3/"
NOW = datetime(2026, 8, 23, 14, tzinfo=UTC)


def _provider(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[PrimatPriceProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        transport=httpx.MockTransport(handler),
    )
    return PrimatPriceProvider(api_key="top-secret-test", client=client), client


def _physical(
    chain: Chain,
    external_id: str,
    name: str,
    *,
    aliases: tuple[str, ...] = (),
    address: str | None = None,
    postal_code: str | None = None,
    latitude: Decimal | None = None,
    longitude: Decimal | None = None,
) -> PhysicalStore:
    return PhysicalStore(
        id=f"physical:{chain.value}:{external_id}",
        chain=chain,
        external_store_id=external_id,
        external_store_aliases=aliases,
        name=name,
        address=address,
        postal_code=postal_code,
        city="Lund",
        latitude=latitude,
        longitude=longitude,
        official_source=f"https://official.example/{chain.value}/{external_id}",
        discovered_at=NOW,
        last_seen_at=NOW,
    )


PHYSICAL_STORES = (
    _physical(
        Chain.ICA,
        "1004409",
        "ICA Kvantum Malmborgs Clemenstorget",
        aliases=("2771",),
        address="Clemenstorget 5",
        postal_code="22221",
        latitude=Decimal("55.70649"),
        longitude=Decimal("13.18801"),
    ),
    _physical(
        Chain.COOP,
        "3813",
        "Coop Mårtenstorget",
        address="Mårtenstorget 11",
        postal_code="22351",
    ),
    _physical(
        Chain.LIDL,
        "0303",
        "Lidl Åkerlund och Rausings väg 1",
        address="Åkerlund och Rausings väg 1",
        postal_code="22730",
        latitude=Decimal("55.69938"),
        longitude=Decimal("13.17783"),
    ),
)


def _resolve_payload() -> dict[str, Any]:
    return {
        "place": {
            "locality": "Lund",
            "postal_code": "22350",
            "latitude": 55.7028,
            "longitude": 13.1927,
        },
        "default_selection": ["ica:2771", "coop:provider-coop", "lidl:provider-lidl"],
        "stores": [
            {
                "chain": "ica",
                "store_id": "2771",
                "key": "ica:2771",
                "name": "Completely unrelated provider label",
                "tier": "full",
                "selected": True,
                "customer_facing": True,
            },
            {
                "chain": "coop",
                "store_id": "provider-coop",
                "key": "coop:provider-coop",
                "name": "Another provider label",
                "address": "Mårtenstorget 11",
                "postal_code": "22351",
                "tier": "full",
                "selected": True,
                "customer_facing": True,
            },
            {
                "chain": "lidl",
                "store_id": "provider-lidl",
                "key": "lidl:provider-lidl",
                "name": "Third provider label",
                "latitude": 55.69938,
                "longitude": 13.17783,
                "tier": "full",
                "selected": True,
                "customer_facing": True,
            },
            {
                "chain": "coop",
                "store_id": "staff",
                "key": "coop:staff",
                "name": "Endast personal Lund",
                "tier": "full",
                "selected": True,
                "customer_facing": False,
            },
        ],
    }


def _product_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (chain, native_id) in enumerate(
        (("ica", "2771"), ("coop", "provider-coop"), ("lidl", "provider-lidl")),
        start=1,
    ):
        rows.append(
            {
                "chain": chain,
                "store_id": native_id,
                "product_id": f"p{index}",
                "name": f"Pasta {index} 500 g",
                "brand": "Test",
                "category": "Skafferi > Pasta",
                "amount": 500,
                "unit": "g",
                "package": "500 g",
                "available": True,
                "prices": {
                    "regular": 10 + index,
                    "effective": 10 + index,
                    "member": None,
                    "multiprice": {"price": None, "quantity": None},
                    "member_multiprice": {"price": None, "quantity": None},
                    "comparison": None,
                    "offer": None,
                },
            }
        )
    return rows


@pytest.mark.asyncio
async def test_export_maps_id_alias_address_and_coordinates_without_names(
    tmp_path: Path,
) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/stores/resolve"):
            return httpx.Response(200, json=_resolve_payload(), request=request)
        return httpx.Response(200, json={"data": _product_rows()}, request=request)

    provider, client = _provider(handler)
    try:
        exporter = BoundedPrimatPhaseCExporter(provider, PHYSICAL_STORES)
        first = await exporter.resolve_once()
        second = await exporter.resolve_once()
        await provider.search_products("pasta", [row.store.store_id for row in first])
        detached = provider.request_scoped_product_snapshot()
        detached[0].search_terms.append("must-not-mutate-provider-cache")
        assert all(
            "must-not-mutate-provider-cache" not in row.search_terms
            for row in provider.request_scoped_product_snapshot()
        )
        context_path = tmp_path / "contexts.json"
        cache_path = tmp_path / "cache.json"
        write_closed_json(context_path, exporter.context_bundle())
        write_closed_json(cache_path, exporter.frozen_external_cache())
    finally:
        await client.aclose()

    assert first == second
    assert exporter.resolve_requests == 1
    assert [request.url.path for request in requests].count("/api/v3/stores/resolve") == 1
    assert [row.identity.basis.value for row in first] == [
        "official_address_postal_code",
        "official_external_id",
        "official_coordinates",
    ]
    context_payload = json.loads(context_path.read_text(encoding="utf-8"))
    assert context_payload["schema"] == "grocery-context-evidence-bundle-v1"
    assert {row["chain"] for row in context_payload["items"]} == {"ica", "coop", "lidl"}
    assert "top-secret-test" not in context_path.read_text(encoding="utf-8")
    assert "top-secret-test" not in cache_path.read_text(encoding="utf-8")

    frozen = _FrozenExternalProvider.load(
        cache_path,
        postal_code="22350",
        exact_contexts=frozenset((row.export.chain.value, row.export.context_id) for row in first),
    )
    frozen_stores = await frozen.find_stores("22350")
    frozen_products = await frozen.search_products(
        "ignored offline",
        [store.store_id for store in frozen_stores],
    )
    assert len(frozen_stores) == 3
    assert len(frozen_products) == 3
    assert all(store.coverage == "full_catalog" for store in frozen_stores)
    assert all(product.source_provenance.source_provider == "primat" for product in frozen_products)


@pytest.mark.asyncio
async def test_export_fails_closed_when_only_the_display_name_matches() -> None:
    physical = _physical(
        Chain.ICA,
        "official-ica",
        "ICA Same Name",
        address="Officialgatan 1",
        postal_code="22221",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "place": {"locality": "Lund", "postal_code": "22350"},
                "default_selection": ["ica:provider-ica"],
                "stores": [
                    {
                        "chain": "ica",
                        "store_id": "provider-ica",
                        "key": "ica:provider-ica",
                        "name": "ICA Same Name",
                        "tier": "full",
                        "selected": True,
                    }
                ],
            },
            request=request,
        )

    provider, client = _provider(handler)
    try:
        exporter = BoundedPrimatPhaseCExporter(
            provider,
            (physical,),
            required_chains=frozenset({Chain.ICA}),
        )
        with pytest.raises(
            PrimatPhaseCExportError,
            match="no exact official Lund identity",
        ) as error:
            await exporter.resolve_once()
        assert error.value.invariant == PrimatPhaseCInvariant.IDENTITY_NO_EXACT_MATCH
        assert error.value.chain == Chain.ICA
        diagnostic = _closed_stop_result(error.value)
        assert diagnostic == {
            "status": "STOPPED",
            "error_code": "export_contract_identity_no_exact_match_ica",
            "error_type": "PrimatPhaseCExportError",
            "credentials_included": False,
            "raw_http_included": False,
            "contract_invariant": "identity_no_exact_match",
            "chain": "ica",
        }
        assert "provider-ica" not in json.dumps(diagnostic)
        with pytest.raises(PrimatPhaseCExportError, match="retry refused"):
            await exporter.resolve_once()
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(
            503,
            text="<html><title>Access denied</title>Cloudflare CAPTCHA</html>",
            headers={"content-type": "text/html"},
        ),
        httpx.Response(
            200,
            json={"message": "Human verification required", "stores": []},
        ),
    ],
)
async def test_primat_access_challenge_stops_without_retry(response: httpx.Response) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            response.status_code,
            content=response.content,
            headers=response.headers,
            request=request,
        )

    provider, client = _provider(handler)
    try:
        with pytest.raises(PriceProviderAccessChallengeError, match="access challenge"):
            await provider.find_stores("22350")
    finally:
        await client.aclose()
    assert requests == 1


def test_physical_store_loader_is_immutable_and_keeps_aliases(tmp_path: Path) -> None:
    database = tmp_path / "registry.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE physical_stores (
                id TEXT, chain TEXT, external_store_id TEXT,
                external_store_aliases TEXT, name TEXT, address TEXT,
                postal_code TEXT, city TEXT, latitude NUMERIC, longitude NUMERIC,
                official_source TEXT, discovered_at TEXT, last_seen_at TEXT,
                is_active INTEGER, lifecycle_state TEXT, not_seen_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO physical_stores VALUES
            ('physical:ica:1004409', 'ica', '1004409', '["2771"]',
             'ICA Clemenstorget', 'Clemenstorget 5', '22221', 'Lund',
             55.70649, 13.18801, 'https://official.example/ica', ?, ?, 1,
             'active', NULL)
            """,
            (NOW.isoformat(), NOW.isoformat()),
        )
        connection.commit()
    finally:
        connection.close()
    before = hashlib.sha256(database.read_bytes()).hexdigest()

    stores = load_active_physical_stores(database)

    assert len(stores) == 1
    assert stores[0].external_store_aliases == ("2771",)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert not database.with_name(database.name + "-wal").exists()
    assert not database.with_name(database.name + "-shm").exists()
    assert not database.with_name(database.name + "-journal").exists()


@pytest.mark.asyncio
async def test_context_bootstrap_cli_service_reuses_bounded_factory_without_network(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "registry.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE physical_stores (
                id TEXT, chain TEXT, external_store_id TEXT,
                external_store_aliases TEXT, name TEXT, address TEXT,
                postal_code TEXT, city TEXT, latitude NUMERIC, longitude NUMERIC,
                official_source TEXT, discovered_at TEXT, last_seen_at TEXT,
                is_active INTEGER, lifecycle_state TEXT, not_seen_at TEXT
            )
            """
        )
        for chain, external_id in (("ica", "100"), ("coop", "200"), ("lidl", "300")):
            connection.execute(
                """
                INSERT INTO physical_stores VALUES
                (?, ?, ?, '[]', ?, NULL, NULL, 'Lund', NULL, NULL,
                 ?, ?, ?, 1, 'active', NULL)
                """,
                (
                    f"physical:{chain}:{external_id}",
                    chain,
                    external_id,
                    f"{chain} official",
                    f"https://official.example/{chain}",
                    NOW.isoformat(),
                    NOW.isoformat(),
                ),
            )
        connection.commit()
    finally:
        connection.close()

    class FakeBoundedProvider:
        def __init__(self) -> None:
            self.calls = 0
            self.closed = False
            self.transport_report = {
                "mode": "primat_context_bootstrap",
                "request_limit": 1,
                "requests": 1,
                "endpoints": {"/stores/resolve": 1},
                "statuses": {"200": 1},
                "denied_requests": 0,
                "max_concurrency": 1,
            }

        async def find_stores(self, _postal_code: str) -> list[Store]:
            self.calls += 1
            return [
                Store(
                    store_id=f"{chain}:{external_id}",
                    source_store_id=external_id,
                    name=f"{chain} context",
                    chain=chain,
                    city="Lund",
                    coverage="full_catalog",
                    price_context_type="physical_store",
                    source_provenance=SourceProvenance(
                        source_provider="primat",
                        source_channel="catalog",
                        source_snapshot_id="primat-request-fixture",
                        source_observed_at=NOW,
                        chain=chain,
                        store_id=f"{chain}:{external_id}",
                        store_name=f"{chain} context",
                        provider_store_id=external_id,
                        price_context="physical_store",
                        coverage="full_catalog",
                    ),
                )
                for chain, external_id in (
                    ("ica", "100"),
                    ("coop", "200"),
                    ("lidl", "300"),
                )
            ]

        async def aclose(self) -> None:
            self.closed = True

    fake = FakeBoundedProvider()
    from scripts import export_lund_primat_contexts as script

    monkeypatch.setattr(
        script._BoundedPrimatProvider,
        "load",
        lambda **_kwargs: fake,
    )
    output = tmp_path / "contexts.json"
    result = await run_context_bootstrap(
        SimpleNamespace(
            allow_bounded_primat_context_bootstrap=True,
            database=database,
            postal_code="22350",
            output=output,
        )
    )

    assert result["status"] == "PASS"
    assert result["database_unchanged"] is True
    assert len(result["contexts"]) == 3
    assert fake.calls == 1
    assert fake.closed is True
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == "grocery-context-evidence-bundle-v1"
    assert {row["chain"] for row in payload["items"]} == {"ica", "coop", "lidl"}
