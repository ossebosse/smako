from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
from app.models import Product
from app.providers.primat import PrimatPriceProvider, PrimatStoreResolution
from app.services.primat_context_smoke_export import primat_context_smoke_bundle
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from scripts.smoke_lund_primat_contexts import _run as run_smoke

from grocery_data.app.services.provider_store_identity import (
    read_primat_context_smoke_bundle,
)

BASE_URL = "https://primat.nu/api/v3/"


def _mapping_database(path: Path) -> Path:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "CREATE TABLE physical_stores (id TEXT, city TEXT, is_active INTEGER)"
        )
        connection.execute(
            """
            CREATE TABLE provider_store_identity_mappings (
                physical_store_id TEXT, provider TEXT, provider_context_id TEXT,
                status TEXT, is_active INTEGER
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE store_context_links (
                physical_store_id TEXT, source_provider TEXT,
                grocery_context_id TEXT, is_active INTEGER
            )
            """
        )
        for suffix, context_id in (
            ("ica", "primat:ica:2771"),
            ("coop", "primat:coop:106430"),
        ):
            physical_id = f"physical:{suffix}"
            connection.execute(
                "INSERT INTO physical_stores VALUES (?, 'Lund', 1)",
                (physical_id,),
            )
            connection.execute(
                "INSERT INTO provider_store_identity_mappings VALUES "
                "(?, 'primat', ?, 'verified', 1)",
                (physical_id, context_id),
            )
            connection.execute(
                "INSERT INTO store_context_links VALUES (?, 'primat', ?, 1)",
                (physical_id, context_id),
            )
        connection.commit()
    finally:
        connection.close()
    return path


async def _live_shapes() -> tuple[
    PrimatStoreResolution,
    list[Product],
    dict[str, Any],
]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/stores/resolve"):
            return httpx.Response(
                200,
                json={
                    "place": {"locality": "Lund", "postal_code": "22350"},
                    "default_selection": ["ica:2771", "coop:106430"],
                    "stores": [
                        {
                            "chain": "ica",
                            "store_id": "2771",
                            "key": "ica:2771",
                            "name": "ICA Clemenstorget",
                            "address": "Clemenstorget 5",
                            "postal_code": "22221",
                            "tier": "full",
                            "selected": True,
                        },
                        {
                            "chain": "coop",
                            "store_id": "106430",
                            "key": "coop:106430",
                            "name": "Coop Mårtenstorget",
                            "address": "Mårtenstorget 11",
                            "postal_code": "22351",
                            "tier": "full",
                            "selected": True,
                        },
                    ],
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "chain": "ica",
                        "store_id": "2771",
                        "product_id": "milk-ica",
                        "name": "Mjölk 1 l",
                        "brand": "Test",
                        "category": "Mejeri",
                        "amount": 1,
                        "unit": "l",
                        "package": "1 l",
                        "available": True,
                        "prices": {
                            "regular": 16.9,
                            "effective": 16.9,
                            "member": None,
                            "multiprice": {"price": None, "quantity": None},
                            "member_multiprice": {"price": None, "quantity": None},
                            "comparison": None,
                            "offer": None,
                        },
                    },
                    {
                        "chain": "coop",
                        "store_id": "106430",
                        "product_id": "milk-coop",
                        "name": "Mjölk 1 l",
                        "brand": "Test",
                        "category": "Mejeri",
                        "amount": 1,
                        "unit": "l",
                        "package": "1 l",
                        "available": True,
                        "prices": {
                            "regular": 17.9,
                            "effective": 17.9,
                            "member": None,
                            "multiprice": {"price": None, "quantity": None},
                            "member_multiprice": {"price": None, "quantity": None},
                            "comparison": None,
                            "offer": None,
                        },
                    },
                ]
            },
            request=request,
        )

    client = httpx.AsyncClient(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    provider = PrimatPriceProvider(api_key="secret-smoke-key", client=client)
    try:
        resolution = await provider.resolve_store_candidates("22350")
        products = await provider.search_products(
            "mjölk",
            ["ica:2771", "coop:106430"],
        )
        response = provider.last_response_metadata()
    finally:
        await client.aclose()
    return resolution, products, response


@pytest.mark.asyncio
async def test_smoke_export_proves_priced_rows_per_context_without_secrets(
    tmp_path: Path,
) -> None:
    resolution, products, response = await _live_shapes()
    bundle = primat_context_smoke_bundle(
        resolution,
        products,
        requested_context_ids=frozenset(
            {"primat:ica:2771", "primat:coop:106430"}
        ),
        mapping_discovery_response_sha256="d" * 64,
        product_response=response,
    )
    path = tmp_path / "smoke.json"
    path.write_text(
        json.dumps(bundle.model_dump(mode="json", by_alias=True)),
        encoding="utf-8",
    )
    replay = read_primat_context_smoke_bundle(path)

    assert [(row.product_rows, row.priced_product_rows) for row in replay.items] == [
        (1, 1),
        (1, 1),
    ]
    assert all(row.provenance_valid for row in replay.items)
    assert replay.store_discovery_response_sha256 == "d" * 64
    encoded = path.read_text(encoding="utf-8").casefold()
    assert "secret-smoke-key" not in encoded
    assert "authorization" not in encoded
    assert "cookie" not in encoded


@pytest.mark.asyncio
async def test_smoke_script_uses_one_resolve_and_one_shared_product_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolution, products, product_response = await _live_shapes()
    discovery = primat_store_discovery_bundle(resolution)
    discovery_path = tmp_path / "stores.json"
    discovery_path.write_text(
        json.dumps(discovery.model_dump(mode="json", by_alias=True)),
        encoding="utf-8",
    )

    class FakeProvider:
        transport_report: ClassVar[dict[str, Any]] = {
            "mode": "bounded_primat_live",
            "request_limit": 2,
            "requests": 2,
            "endpoints": {"/products": 1, "/stores/resolve": 1},
            "statuses": {"200": 2},
            "denied_requests": 0,
            "max_concurrency": 1,
        }

        async def resolve_store_candidates(self, postal_code: str) -> PrimatStoreResolution:
            assert postal_code == "22350"
            return resolution

        async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
            assert query == "mjölk"
            assert store_ids == ["coop:106430", "ica:2771"]
            return products

        def last_response_metadata(self) -> dict[str, Any]:
            return product_response

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        "scripts.smoke_lund_primat_contexts._BoundedPrimatProvider.load",
        lambda **kwargs: FakeProvider(),
    )
    output = tmp_path / "smoke.json"
    database = _mapping_database(tmp_path / "mapping.sqlite")
    args = argparse.Namespace(
        allow_bounded_primat_context_smoke=True,
        city="Lund",
        postal_code="22350",
        database=database,
        store_discovery=discovery_path,
        context_id=["primat:ica:2771", "primat:coop:106430"],
        output=output,
    )

    report = await run_smoke(args)

    assert report["status"] == "PASS"
    assert report["transport"]["requests"] == 2
    assert all(row["priced_product_rows"] == 1 for row in report["contexts"])
    assert read_primat_context_smoke_bundle(output).identity_revalidated is True


@pytest.mark.asyncio
async def test_smoke_script_requires_opt_in_before_provider_construction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed = False

    def forbidden(**_kwargs: Any) -> None:
        nonlocal constructed
        constructed = True
        raise AssertionError

    monkeypatch.setattr(
        "scripts.smoke_lund_primat_contexts._BoundedPrimatProvider.load",
        forbidden,
    )
    args = argparse.Namespace(
        allow_bounded_primat_context_smoke=False,
        city="Lund",
        postal_code="22350",
        database=tmp_path / "not-read.sqlite",
        store_discovery=tmp_path / "not-read.json",
        context_id=["primat:ica:2771"],
        output=tmp_path / "not-written.json",
    )

    with pytest.raises(PermissionError):
        await run_smoke(args)
    assert constructed is False
    assert not args.output.exists()
