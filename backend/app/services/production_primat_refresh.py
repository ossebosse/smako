"""Bounded production refresh of the closed Primat product cache.

The refresh deliberately reuses the accepted frozen-cache contract.  Persisted
rows are identity evidence only: every selected context is matched exactly
against one current store resolution before any product row can enter the
replacement cache.  Provider credentials, HTTP bodies and transport state are
never returned or written.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from math import isfinite
from pathlib import Path
from typing import Any

from app.services.primat_frozen_cache_collect import (
    CanonicalIngredientQuery,
    _query_key,
    build_frozen_external_cache,
    canonical_ingredient_query_surface,
    load_eligible_primat_contexts,
    revalidate_primat_contexts,
)
from app.services.primat_ica_catalog import (
    CatalogStore,
    catalog_products,
    catalog_ready,
    default_catalog_path,
)
from app.services.primat_recipe_queries import RECIPE_QUERIES
from app.services.primat_phase_c_export import FrozenExternalCacheBundle, write_closed_json
from scripts.benchmark_lund_phase_c import _BoundedPrimatProvider

from grocery_data.app.domain import Chain
from grocery_data.app.domain.source_strategy import SourceProvider, source_strategy_for
from grocery_data.app.services.refresh_diagnostics import source_failure_diagnostic

_MAX_CONTEXTS_PER_PRODUCT_REQUEST = 15
# Owner request 2026-11-22: ICA's prices for more of the recipe ingredients.
# Primat's free plan: 60 calls a minute, 200 rows a call, 20 000 rows a day.
# The 48 benchmark searches keep 100 rows; the recipe searches ask for 50.
_BENCHMARK_LIMIT = 100
_RECIPE_LIMIT = 50
_SECONDS_BETWEEN_SEARCHES = 1.1


def _ready_catalog(store_ids: list[str]) -> CatalogStore | None:
    """The stored full ICA catalog, when enabled and complete for these stores.

    ``PRIMAT_ICA_CATALOG_SOURCE=true`` turns it on.  Until a full round has
    finished with at least ``PRIMAT_ICA_CATALOG_MIN_PRODUCTS`` usable food rows
    per store, the nightly searches are used as before.
    """

    if os.getenv("PRIMAT_ICA_CATALOG_SOURCE", "false").casefold() != "true":
        return None
    if not store_ids or any(not store_id.startswith("ica:") for store_id in store_ids):
        return None
    try:
        path = default_catalog_path()
    except KeyError:
        return None
    if not path.is_file():
        return None
    store = CatalogStore(path)
    minimum = int(os.getenv("PRIMAT_ICA_CATALOG_MIN_PRODUCTS", "1000"))
    if catalog_ready(store, store_ids=store_ids, min_products=minimum):
        return store
    store.close()
    return None


def production_query_items() -> tuple[tuple[CanonicalIngredientQuery, int], ...]:
    """The nightly searches with their row limits: the 48, then the recipe queries."""

    base = canonical_ingredient_query_surface().items
    used = {_query_key(item.query) for item in base}
    items = [(item, _BENCHMARK_LIMIT) for item in base]
    for query in RECIPE_QUERIES:
        key = _query_key(query)
        if key and key not in used:
            used.add(key)
            items.append((CanonicalIngredientQuery(canonical=f"recipe:{query}", query=query), _RECIPE_LIMIT))
    return tuple(items)


def _expected_requests() -> int:
    return 1 + len(production_query_items())


def _normalized_postal_code(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) != 5:
        raise ValueError("postal_code must contain exactly five digits")
    return digits


def _normalized_city(value: str) -> str:
    city = " ".join(value.split())
    if not city or len(city) > 100 or any(ord(character) < 32 for character in city):
        raise ValueError("city must be a non-empty printable value")
    return city


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _primat_primary_contexts(database: Path, *, city: str, max_age_hours: float) -> tuple[Any, ...]:
    candidates = load_eligible_primat_contexts(
        database,
        city=city,
        max_age_hours=max_age_hours,
        chains=frozenset(Chain),
        allow_stale_identity_seed=True,
    )
    return tuple(
        context
        for context in candidates
        if source_strategy_for(
            context.chain,
            context_id=context.provider_context_id,
        ).basket_primary.provider
        is SourceProvider.PRIMAT
    )


def _safe_transport_report(report: object, *, searches: int | None = None) -> dict[str, Any]:
    """Copy only the fixed, credential-free bounded-transport counters.

    ``searches`` is the number of product searches made: all of them, or none
    when the stored full catalog supplied the products.
    """

    if not isinstance(report, dict):
        raise TypeError("bounded Primat transport did not expose counters")
    if searches is None:
        searches = _expected_requests() - 1
    expected = 1 + searches
    expected_endpoints = {"/stores/resolve": 1}
    if searches:
        expected_endpoints["/products"] = searches
    requests = int(report.get("requests", -1))
    denied = int(report.get("denied_requests", -1))
    concurrency = int(report.get("max_concurrency", -1))
    endpoints = report.get("endpoints")
    statuses = report.get("statuses")
    if (
        requests != expected
        or denied != 0
        or concurrency != 1
        or endpoints != expected_endpoints
        or statuses != {"200": expected}
    ):
        raise RuntimeError(f"bounded {expected}-request Primat transport contract failed")
    return {
        "mode": "bounded_primat_live",
        "request_limit": expected,
        "requests": requests,
        "endpoints": expected_endpoints,
        "statuses": {"200": expected},
        "denied_requests": denied,
        "max_concurrency": concurrency,
    }


def plan_city_primat_refresh(
    database: Path,
    city: str,
    max_age_hours: float,
) -> dict[str, Any]:
    """Describe the exact persisted Primat scope without network or writes."""

    normalized_city = _normalized_city(city)
    if not isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_age_hours must be finite and positive")
    eligible = _primat_primary_contexts(
        database.resolve(strict=True),
        city=normalized_city,
        max_age_hours=max_age_hours,
    )
    return {
        "city": normalized_city,
        "status": "planned" if eligible else "no_verified_primat_primary_contexts",
        "contexts": [
            {
                "context_id": context.provider_context_id,
                "chain": context.chain.value,
                "coverage": context.coverage.value,
                "mapping_confidence": context.confidence.value,
                "identity_seed_age_hours": float(context.data_age_hours),
            }
            for context in eligible
        ],
        "provider_requests_planned": _expected_requests() if eligible else 0,
        "provider_requests_per_context": 0,
        "credentials_included": False,
    }


def _store_context_key(store: Any) -> tuple[str, str]:
    provenance = store.source_provenance
    if provenance is None or not provenance.provider_store_id:
        raise ValueError("Primat LKG store lacks provider identity provenance")
    return str(store.chain), str(provenance.provider_store_id)


def _merge_context_lkg(
    refreshed: FrozenExternalCacheBundle,
    *,
    lkg_cache: Path,
    failed_contexts: tuple[Any, ...],
    max_age_hours: float,
) -> FrozenExternalCacheBundle:
    """Merge only failed exact contexts from a fresh closed city cache."""

    try:
        lkg = FrozenExternalCacheBundle.model_validate_json(
            lkg_cache.resolve(strict=True).read_bytes()
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Primat context LKG is not a valid closed cache") from exc
    if lkg.postal_code != refreshed.postal_code:
        raise ValueError("Primat context LKG has the wrong postal scope")

    required = {(context.chain.value, context.provider_store_id) for context in failed_contexts}
    selected_stores = tuple(store for store in lkg.stores if _store_context_key(store) in required)
    if {_store_context_key(store) for store in selected_stores} != required:
        raise ValueError("Primat context LKG does not cover every failed exact context")
    now = datetime.now(tz=UTC)
    for store in selected_stores:
        provenance = store.source_provenance
        assert provenance is not None
        age = (now - provenance.source_observed_at.astimezone(UTC)).total_seconds() / 3600
        if age < 0:
            raise ValueError("Primat context LKG observation is in the future")

    selected_store_ids = {store.store_id for store in selected_stores}
    selected_products = tuple(
        product for product in lkg.products if product.store_id in selected_store_ids
    )
    if {product.store_id for product in selected_products} != selected_store_ids:
        raise ValueError("Primat context LKG lacks products for a failed context")

    stores = tuple(sorted((*refreshed.stores, *selected_stores), key=lambda row: row.store_id))
    if len({store.store_id for store in stores}) != len(stores):
        raise ValueError("merged Primat cache contains duplicate stores")
    product_map = {
        (product.store_id, product.product_id): product
        for product in (*refreshed.products, *selected_products)
    }
    if len(product_map) != len(refreshed.products) + len(selected_products):
        raise ValueError("merged Primat cache contains duplicate products")
    observed = []
    for store in stores:
        provenance = store.source_provenance
        if provenance is None:
            raise ValueError("merged Primat store lacks provenance")
        observed.append(provenance.source_observed_at.astimezone(UTC))
    return FrozenExternalCacheBundle(
        postal_code=refreshed.postal_code,
        captured_at=min(observed),
        stores=stores,
        products=tuple(product_map[key] for key in sorted(product_map)),
    )


async def collect_city_primat_cache(
    database: Path,
    city: str,
    postal_code: str,
    output: Path,
    max_age_hours: float,
    lkg_cache: Path | None = None,
) -> dict[str, Any]:
    """Refresh one city's verified Primat-primary contexts into a closed cache.

    The operation spends one store-resolution request and one sequential
    product request for each of the shared 48 canonical queries and the
    recipe-ingredient queries (``production_query_items``).  An existing
    output is replaced only after exact identity revalidation, complete
    collection and closed-schema validation have all succeeded.
    """

    normalized_city = _normalized_city(city)
    normalized_postal = _normalized_postal_code(postal_code)
    if not isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_age_hours must be finite and positive")

    resolved_database = database.resolve(strict=True)
    resolved_output = output.resolve()
    if resolved_database == resolved_output:
        raise ValueError("Primat cache output must not overwrite its identity database")

    eligible = _primat_primary_contexts(
        resolved_database,
        city=normalized_city,
        max_age_hours=max_age_hours,
    )
    if not eligible:
        return {
            "status": "SKIPPED",
            "reason_code": "no_verified_primat_primary_contexts",
            "city": normalized_city,
            "postal_code": normalized_postal,
            "contexts": 0,
            "provider_requests": 0,
            "output_written": False,
            "credentials_included": False,
            "raw_http_included": False,
        }
    if len(eligible) > _MAX_CONTEXTS_PER_PRODUCT_REQUEST:
        raise ValueError("verified Primat context scope exceeds one bounded product request")

    surface = canonical_ingredient_query_surface()
    searches = production_query_items()
    exact_contexts = frozenset(
        (context.chain.value, context.provider_context_id) for context in eligible
    )
    provider = _BoundedPrimatProvider.load(
        exact_contexts=exact_contexts,
        max_requests=1 + len(searches),
        context_bootstrap=False,
    )
    stage = "store_resolution"
    query = None
    native_store_ids = []
    context_diagnostics = []
    try:
        resolution = await provider.resolve_store_candidates(normalized_postal)
        stage = "exact_context_revalidation"
        contexts = []
        failed_contexts = []
        for persisted in eligible:
            try:
                [current] = revalidate_primat_contexts(
                    resolution,
                    (persisted,),
                    city=normalized_city,
                )
            except ValueError as exc:
                failed_contexts.append(persisted)
                context_diagnostics.append({
                    "context_id": persisted.provider_context_id,
                    "required_coverage": persisted.coverage.value,
                    "diagnostic": source_failure_diagnostic(exc),
                })
                continue
            contexts.append(current)
        contexts = tuple(contexts)
        failed_contexts = tuple(failed_contexts)
        if not contexts:
            raise ValueError("current Primat resolution revalidated no exact contexts")
        native_store_ids = sorted(context.store.store_id for context in contexts)
        if failed_contexts and lkg_cache is None:
            # No complete replacement can be built. Do not spend the product
            # requests only to misattribute this identity/coverage failure to
            # the last product query at closed-cache validation.
            raise ValueError("failed Primat contexts require a fresh per-context LKG")

        collected = []
        zero_result_queries = 0
        catalog_rows = catalog_skipped = 0
        catalog = _ready_catalog(native_store_ids)
        source_mode = "catalog" if catalog is not None else "searches"
        if catalog is not None:
            stage = "catalog_products"
            oldest = resolution.observed_at - timedelta(hours=max_age_hours)
            try:
                for row, fetched_at in catalog_products(
                    catalog, store_ids=native_store_ids, not_before=oldest
                ):
                    try:
                        product = provider._parse_product(row)
                    except (TypeError, ValueError):
                        product = None
                    if product is None or product.source_provenance is None:
                        catalog_skipped += 1
                        continue
                    observed = min(fetched_at, resolution.observed_at)
                    collected.append(product.model_copy(update={
                        "source_provenance": product.source_provenance.model_copy(
                            update={"source_observed_at": observed}
                        )
                    }))
                    catalog_rows += 1
            finally:
                catalog.close()
            searches = []
        for index, (item, limit) in enumerate(searches):
            stage = "product_fetch_and_parse"
            query = item.query
            if index:
                await asyncio.sleep(_SECONDS_BETWEEN_SEARCHES)  # Primat: 60 calls a minute
            requests_before = int(provider.transport_report.get("requests", -1))
            rows = await provider.search_products(item.query, native_store_ids, limit=limit)
            requests_after = int(provider.transport_report.get("requests", -1))
            if requests_after != requests_before + 1:
                raise RuntimeError("canonical ingredient did not spend exactly one request")
            collected.extend(rows)
            zero_result_queries += not rows

        transport = _safe_transport_report(provider.transport_report, searches=len(searches))
        stage = "closed_product_validation"
        bundle = build_frozen_external_cache(
            resolution,
            contexts,
            collected,
            catalog_window_hours=max_age_hours if source_mode == "catalog" else None,
        )
        if failed_contexts:
            if lkg_cache is None:
                raise ValueError("failed Primat contexts require a fresh per-context LKG")
            stage = "context_lkg_validation"
            bundle = _merge_context_lkg(
                bundle,
                lkg_cache=lkg_cache,
                failed_contexts=failed_contexts,
                max_age_hours=max_age_hours,
            )
    except Exception as exc:
        exc.refresh_diagnostic = {
            **source_failure_diagnostic(exc),
            "stage": stage,
            "query": query,
            "store_ids": native_store_ids,
            "provider_requests": int(provider.transport_report.get("requests", 0)),
            "context_failures": context_diagnostics,
        }
        raise
    finally:
        await provider.aclose()

    written = write_closed_json(resolved_output, bundle)
    products_by_store = Counter(product.store_id for product in bundle.products)
    return {
        "status": "PASS",
        "city": normalized_city,
        "postal_code": normalized_postal,
        "optimizer_runs": 0,
        "transport": transport,
        "surface": {
            "schema_version": surface.schema_version,
            "sha256": surface.sha256,
            "canonical_ingredients": len(surface.items),
            "recipe_queries": max(0, len(searches) - len(surface.items)),
            "queries": len(searches),
            "zero_result_queries": zero_result_queries,
            "source": source_mode,
            "catalog_products": catalog_rows,
            "catalog_rows_skipped": catalog_skipped,
        },
        "contexts": [
            {
                "context_id": context.eligible.provider_context_id,
                "chain": context.eligible.chain.value,
                "coverage": context.eligible.coverage.value,
                "mapping_confidence": context.eligible.confidence.value,
                "identity_seed_age_hours": float(context.eligible.data_age_hours),
                "stale_identity_seed": (float(context.eligible.data_age_hours) > max_age_hours),
                "products": products_by_store[context.store.store_id],
            }
            for context in contexts
        ]
        + [
            {
                "context_id": context.provider_context_id,
                "chain": context.chain.value,
                "coverage": context.coverage.value,
                "mapping_confidence": context.confidence.value,
                "identity_seed_age_hours": float(context.data_age_hours),
                "status": "lkg_retained",
            }
            for context in failed_contexts
        ],
        "context_failures": len(failed_contexts),
        "context_lkg_used": len(failed_contexts),
        "output": {
            "file": resolved_output.name,
            "bytes": int(written["bytes"]),
            "sha256": _sha256(resolved_output),
            "schema_version": bundle.schema_version,
            "stores": len(bundle.stores),
            "products": len(bundle.products),
            "credentials_included": False,
            "headers_included": False,
            "cookies_included": False,
            "raw_http_included": False,
        },
    }


__all__ = ["collect_city_primat_cache", "plan_city_primat_refresh"]
