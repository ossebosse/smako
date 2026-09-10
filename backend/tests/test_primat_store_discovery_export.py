from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pytest
from app.providers.primat import PrimatPriceProvider, PrimatStoreResolution
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from scripts.capture_lund_primat_stores import _closed_stop_result
from scripts.capture_lund_primat_stores import _run as run_capture

from grocery_data.app.services.provider_store_identity import (
    read_primat_store_discovery_bundle,
)

BASE_URL = "https://primat.nu/api/v3/"


def _provider(
    handler: Any,
) -> tuple[PrimatPriceProvider, httpx.AsyncClient]:
    client = httpx.AsyncClient(
        base_url=BASE_URL,
        transport=httpx.MockTransport(handler),
    )
    return PrimatPriceProvider(api_key="secret-test-key", client=client), client


async def _resolution() -> PrimatStoreResolution:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "place": {"locality": "Lund", "postal_code": "22350"},
                "default_selection": ["ica:2771"],
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
                        "selected": False,
                    },
                    {
                        "chain": "willys",
                        "store_id": "2354",
                        "key": "willys:2354",
                        "name": "Willys Lund Nova",
                        "tier": "full",
                        "selected": False,
                    },
                ],
            },
            request=request,
        )

    provider, client = _provider(handler)
    try:
        return await provider.resolve_store_candidates("22350")
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_discovery_export_keeps_all_target_contexts_in_closed_projection(
    tmp_path: Path,
) -> None:
    bundle = primat_store_discovery_bundle(await _resolution())
    path = tmp_path / "primat-stores.json"
    path.write_text(
        json.dumps(bundle.model_dump(mode="json", by_alias=True)),
        encoding="utf-8",
    )
    replay = read_primat_store_discovery_bundle(path)

    assert replay.raw_rows == 3
    assert [(row.chain.value, row.provider_store_id) for row in replay.items] == [
        ("ica", "2771"),
        ("coop", "106430"),
    ]
    assert [row.selected for row in replay.items] == [True, False]
    encoded = path.read_text(encoding="utf-8")
    assert "secret-test-key" not in encoded
    assert "authorization" not in encoded.casefold()
    assert "cookie" not in encoded.casefold()
    assert all(replay.request.response_sha256 in row.raw_reference for row in replay.items)


@pytest.mark.asyncio
async def test_capture_script_requires_opt_in_without_constructing_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed = False

    def forbidden(**_kwargs: Any) -> None:
        nonlocal constructed
        constructed = True
        raise AssertionError

    monkeypatch.setattr(
        "scripts.capture_lund_primat_stores._BoundedPrimatProvider.load",
        forbidden,
    )
    args = argparse.Namespace(
        allow_bounded_primat_store_discovery=False,
        city="Lund",
        postal_code="22350",
        output=tmp_path / "must-not-exist.json",
    )

    with pytest.raises(PermissionError):
        await run_capture(args)
    assert constructed is False
    assert not args.output.exists()


@pytest.mark.asyncio
async def test_capture_script_writes_once_from_bounded_provider_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolution = await _resolution()

    class FakeBoundedProvider:
        transport_report: ClassVar[dict[str, Any]] = {
            "mode": "primat_context_bootstrap",
            "request_limit": 1,
            "requests": 1,
            "endpoints": {"/stores/resolve": 1},
            "statuses": {"200": 1},
            "denied_requests": 0,
            "max_concurrency": 1,
        }

        async def resolve_store_candidates(self, postal_code: str) -> PrimatStoreResolution:
            assert postal_code == "22350"
            return resolution

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr(
        "scripts.capture_lund_primat_stores._BoundedPrimatProvider.load",
        lambda **kwargs: FakeBoundedProvider(),
    )
    output = tmp_path / "primat-stores.json"
    args = argparse.Namespace(
        allow_bounded_primat_store_discovery=True,
        city="Lund",
        postal_code="22350",
        output=output,
    )

    report = await run_capture(args)

    assert report["status"] == "PASS"
    assert report["transport"]["requests"] == 1
    assert report["discovery"]["public_target_contexts"] == 2
    assert output.exists()
    assert read_primat_store_discovery_bundle(output).request.request_count == 1
    with pytest.raises(FileExistsError):
        await run_capture(args)


def test_capture_stop_diagnostic_never_copies_exception_message() -> None:
    diagnostic = _closed_stop_result(
        RuntimeError("Bearer top-secret Cookie=session-secret provider payload")
    )

    assert diagnostic == {
        "status": "STOPPED",
        "error_code": "provider_schema_or_io_stop",
        "error_type": "RuntimeError",
        "credentials_included": False,
        "headers_included": False,
        "cookies_included": False,
        "raw_http_included": False,
    }
