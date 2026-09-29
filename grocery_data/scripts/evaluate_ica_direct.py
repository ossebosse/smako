"""Bounded, non-promotable ICA evidence probe using existing source parsers.

This diagnostic never opens a database, imports a candidate or changes source policy.
The normal operation lock must be held by the operator on a scheduled host.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import time
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.ica.client import IcaClient
from grocery_data.app.connectors.ica.models import initial_data_from_html
from grocery_data.app.connectors.ica.online_catalog_client import (
    _looks_like_access_stop,
    sanitized_api_payload,
)
from grocery_data.app.connectors.ica.online_catalog_models import IcaProductPage
from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.normalization import ProductNormalizer

APPROVED_STORES = ("1088004", "1004409")
CATALOG_ORIGIN = "https://handlaprivatkund.ica.se"
UA = "grocery-data-poc/0.1 (+source-transparency)"
MAX_CATALOG_BYTES = 2 * 1024 * 1024


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_batch(batch: RawBatch, output: Path, label: str) -> list[dict]:
    records = []
    for index, raw in enumerate(batch.documents):
        filename = f"{label}-{index}-{raw.kind}.json"
        (output / filename).write_bytes(raw.payload)
        records.append(
            {
                "path": filename,
                "sha256": sha256(raw.payload).hexdigest(),
                "kind": raw.kind,
                "http_status": raw.http_status,
                "url": raw.url,
                "fetched_at": raw.fetched_at.isoformat(),
                "bytes": len(raw.payload),
                "content_type": raw.content_type,
            }
        )
    return records


async def probe_offers(output: Path, *, include_offers: bool = True) -> dict:
    parser = IcaParser()
    normalizer = ProductNormalizer()
    area = GeographicArea(city="Lund")
    started = time.monotonic()
    result: dict = {"source_kind": "PUBLIC_STORE_OFFERS", "stores": []}
    async with httpx.AsyncClient(
        base_url="https://www.ica.se",
        timeout=30,
        trust_env=False,
        follow_redirects=False,
        headers={"Accept": "text/html", "User-Agent": UA},
    ) as http:
        client = IcaClient(
            client=http, requests_per_second=0.5, retry_policy=RetryPolicy(attempts=1)
        )
        try:
            locator = await client.fetch_physical_stores(area)
        except ConnectorFetchError as exc:
            result["failure_type"] = type(exc.__cause__).__name__
            result["raw"] = save_batch(exc.partial_batch, output, "locator-stop")
            return result
        result["locator_raw"] = save_batch(locator, output, "locator")
        data = initial_data_from_html(locator.documents[0].payload)
        result["locator_declared_stores"] = data["resultStore"].get("totalNrOfStores")
        stores = parser.parse_physical_stores(locator, ["locator"], area)
        result["parsed_city_stores"] = len(stores)
        selected = {s.external_id: s for s in stores if s.external_id in APPROVED_STORES}
        for store_id in APPROVED_STORES:
            store = selected.get(store_id)
            if store is None:
                result["stores"].append({"store_id": store_id, "status": "MAPPING_NOT_FOUND"})
                continue
            row = {
                "store_id": store_id,
                "name": store.name,
                "address": store.address,
                "official_store_id": store.source_fields.get("store_id"),
                "online_url": store.source_fields.get("online_url"),
                "offers_url": store.source_fields.get("offers_url"),
                "online_shopping": store.online_shopping,
            }
            if not include_offers:
                row["status"] = "LOCATOR_ONLY"
                result["stores"].append(row)
                continue
            store_started = time.monotonic()
            try:
                batch = await client.fetch_catalog(store)
            except ConnectorFetchError as exc:
                row.update(
                    status="FETCH_STOP",
                    failure_type=type(exc.__cause__).__name__,
                    raw=save_batch(exc.partial_batch, output, f"offers-{store_id}-stop"),
                )
                result["stores"].append(row)
                # Each source context has only one prescribed request, never a retry.
                continue
            row["raw"] = save_batch(batch, output, f"offers-{store_id}")
            parsed = parser.parse_catalog(batch, [f"offers-{store_id}"], store)
            source_rows = parser.weekly_offer_rows(
                initial_data_from_html(batch.documents[0].payload)
            )
            normalized = []
            normalizer_failures = Counter()
            for product in parsed.products:
                try:
                    normalized.append(
                        normalizer.normalize(product, parser_version=parser.parser_version)
                    )
                except (ValueError, TypeError) as exc:
                    normalizer_failures[type(exc).__name__] += 1
            write_json(
                output / f"parsed-{store_id}.json",
                [p.model_dump(mode="json") for p in parsed.products],
            )
            write_json(
                output / f"normalized-{store_id}.json",
                [p.model_dump(mode="json") for p in normalized],
            )
            row.update(
                status="PARSED",
                fetched=len(source_rows),
                parsed=len(parsed.products),
                parse_rejected=len(parsed.failures),
                normalized=len(normalized),
                normalization_rejected=sum(normalizer_failures.values()),
                parse_failure_counts=dict(Counter(f.error_code for f in parsed.failures)),
                gtin=sum(bool(p.gtin) for p in parsed.products),
                explicit_package=sum(p.package_quantity is not None for p in parsed.products),
                unconditional_price=sum(p.sale_price is not None for p in parsed.products),
                member_offers=sum(o.member_only for p in parsed.products for o in p.offers),
                purchase_models=dict(Counter(p.sale_model.value for p in normalized)),
                fetched_at=batch.documents[0].fetched_at.isoformat(),
                source_observation_time=None,
                observation_time_semantics="public response observed at fetched_at; source modification time absent",
                runtime_seconds=round(time.monotonic() - store_started, 3),
                promotable=False,
                quality_gate_passed=False,
            )
            result["stores"].append(row)
        result["request_count"] = client._request_count
    result["runtime_seconds"] = round(time.monotonic() - started, 3)
    return result


async def probe_catalog(
    store_id: str, output: Path, *, verified_online_url: str | None = None
) -> dict:
    """One historic observed API contract, no region mapping or completeness claim."""
    if store_id not in APPROVED_STORES:
        raise ValueError("ICA diagnostic store is outside the explicit two-store allowlist")
    if verified_online_url != f"{CATALOG_ORIGIN}/stores/{store_id}":
        return {
            "store_id": store_id,
            "classification": "UNVERIFIED_ONLINE_MAPPING",
            "request_count": 0,
            "returned_product_count": 0,
            "accepted_global_prices": 0,
            "promotable": False,
            "catalog_completeness": "UNPROVEN",
        }
    path = f"/stores/{store_id}/api/webproductpagews/v6/product-pages/search"
    params = {
        "q": "mjölk",
        "includeAdditionalPageInfo": "true",
        "maxPageSize": "300",
        "maxProductsToDecorate": "50",
        "tag": "web",
    }
    started = time.monotonic()
    result: dict = {
        "store_id": store_id,
        "source_kind": "ONLINE_CATALOG_SEARCH",
        "method": "GET",
        "url": CATALOG_ORIGIN + path,
        "query": params,
        "started_at": datetime.now(UTC).isoformat(),
        "retry_count": 0,
        "catalog_completeness": "UNPROVEN",
        "promotable": False,
        "returned_product_count": 0,
        "accepted_global_prices": 0,
    }
    headers = {
        "Accept": "application/json",
        "User-Agent": UA,
        "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
        "Referer": f"{CATALOG_ORIGIN}/stores/{store_id}/",
    }
    try:
        async with (
            httpx.AsyncClient(
                timeout=30, trust_env=False, follow_redirects=False, headers=headers
            ) as http,
            http.stream("GET", CATALOG_ORIGIN + path, params=params) as response,
        ):
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > MAX_CATALOG_BYTES:
                    raise ValueError("RESPONSE_SIZE_LIMIT")
                body.extend(chunk)
            safe_response = httpx.Response(
                response.status_code,
                content=bytes(body),
                headers={"content-type": response.headers.get("content-type", "")},
            )
            result.update(
                status=response.status_code,
                content_type=response.headers.get("content-type"),
                bytes=len(body),
                fetched_at=datetime.now(UTC).isoformat(),
            )
            if _looks_like_access_stop(safe_response, expect_json=True):
                result["classification"] = (
                    "rate_limit"
                    if response.status_code == 429
                    else "request_blocked"
                    if b"request blocked" in bytes(body).lower()
                    else "access_stop"
                )
            elif response.is_error:
                result["classification"] = "http_error"
            else:
                payload = sanitized_api_payload(json.loads(body))
                page = IcaProductPage.from_payload(payload, category_id="search:mjölk")
                filename = f"catalog-{store_id}.json"
                (output / filename).write_bytes(payload)
                result.update(
                    classification="PUBLIC_PRODUCT_JSON",
                    raw=filename,
                    raw_sha256=sha256(payload).hexdigest(),
                    returned_product_count=len(page.decorated_products),
                    ordered_ids=len(page.ordered_product_ids),
                    undecorated_ids=len(page.other_product_ids),
                    declared_products=page.declared_product_count,
                    terminal=page.terminal,
                )
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        result["classification"] = "transport_or_schema_error"
        result["failure_type"] = type(exc).__name__
    result["runtime_seconds"] = round(time.monotonic() - started, 3)
    return result


async def run(output: Path, mode: str, location: str) -> dict:
    if output.exists():
        raise ValueError("Evidence directory already exists; refusing overwrite or duplicate run")
    if any(
        os.getenv(k)
        for k in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        )
    ):
        raise ValueError("Proxy environment is outside this diagnostic contract")
    output.mkdir(parents=True)
    started = time.monotonic()
    result: dict = {
        "schema": "ica-direct-evaluation-v2",
        "location": location,
        "platform": platform.system(),
        "python": platform.python_version(),
        "uid": os.getuid() if hasattr(os, "getuid") else None,
        "started_at": datetime.now(UTC).isoformat(),
        "promotable": False,
        "activation_performed": False,
        "mode": mode,
    }
    result["offers"] = await probe_offers(output, include_offers=mode in {"all", "offers"})
    if mode in {"all", "catalog"}:
        result["catalog"] = []
        mappings = {row["store_id"]: row.get("online_url") for row in result["offers"]["stores"]}
        for index, store_id in enumerate(APPROVED_STORES):
            if index:
                await asyncio.sleep(2)
            result["catalog"].append(
                await probe_catalog(store_id, output, verified_online_url=mappings.get(store_id))
            )
    result["built_at"] = datetime.now(UTC).isoformat()
    result["runtime_seconds"] = round(time.monotonic() - started, 3)
    write_json(output / "metrics.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("all", "offers", "catalog"), default="all")
    parser.add_argument("--location", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.output, args.mode, args.location))
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
