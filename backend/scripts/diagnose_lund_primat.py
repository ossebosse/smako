"""Bounded existing collector, isolated export, shared lock, no activation."""

import asyncio
import json
import os
import traceback
from pathlib import Path
from unittest.mock import patch

from app.services import production_primat_refresh as refresh

from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    credential_safe_report,
    production_refresh_lock_path,
)

DATABASE = Path("/srv/app/var/grocery/grocery_data.sqlite")
ROOT = Path("/srv/app/var/price_universes")
OUT = Path("/srv/app/var/reports/recovery-22350-20260914")
OUT.mkdir(exist_ok=True)
report = {"stage": "identity_scope", "events": [], "activation": False}
providers = []
original_load = refresh._BoundedPrimatProvider.load
original_build = refresh.build_frozen_external_cache


def load(**kwargs):
    provider = original_load(**kwargs)
    providers.append(provider)
    original_resolve = provider.resolve_store_candidates
    original_search = provider.search_products

    async def resolve(*args, **kw):
        report["stage"] = "store_resolution_and_exact_revalidation"
        return await original_resolve(*args, **kw)

    async def search(query, stores):
        report["stage"] = "product_fetch_and_parse"
        report["query"] = query
        report["store_ids"] = stores
        rows = await original_search(query, stores)
        report["events"].append({"query": query, "parsed_products": len(rows)})
        return rows

    provider.resolve_store_candidates = resolve
    provider.search_products = search
    return provider


def build(resolution, contexts, products):
    report["stage"] = "closed_product_validation"
    seen = {}
    for product in products:
        key = (product.store_id, product.product_id)
        row = product.model_dump(mode="json")
        if key in seen and seen[key] != row:
            report["first_conflicting_product"] = {
                "store_id": key[0],
                "product_id": key[1],
                "changed_fields": [k for k in row if row[k] != seen[key][k]],
                "first": seen[key],
                "second": row,
            }
            break
        seen[key] = row
    result = original_build(resolution, contexts, products)
    report["stage"] = "closed_export"
    return result


def error_record(error):
    message = str(error)
    for key, value in os.environ.items():
        if len(value) >= 6 and any(
            k in key.upper() for k in ("KEY", "TOKEN", "SECRET", "PASSWORD")
        ):
            message = message.replace(value, "[REDACTED]")
    result = {
        "type": type(error).__name__,
        "message": message,
        "stack": [
            {"file": f.filename, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(error.__traceback__)
        ],
    }
    cause = error.__cause__ or (error.__context__ if not error.__suppress_context__ else None)
    if cause is not None:
        result["cause"] = error_record(cause)
    return result


async def main():
    with RefreshRunLock(production_refresh_lock_path(DATABASE, ROOT)):
        try:
            with (
                patch.object(refresh._BoundedPrimatProvider, "load", load),
                patch.object(refresh, "build_frozen_external_cache", build),
            ):
                report["result"] = await refresh.collect_city_primat_cache(
                    DATABASE, "Lund", "22350", OUT / "primat-candidate.json", 48
                )
            report["status"] = "PASS"
        except Exception as error:  # noqa: BLE001 - isolated diagnostic captures sanitized chain
            report["status"] = "FAIL"
            report["error"] = error_record(error)
        finally:
            report["transport"] = [p.transport_report for p in providers]
            safe = credential_safe_report(report)
            (OUT / "primat-diagnostic.json").write_text(
                json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf8"
            )
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in safe.items()
                        if k not in ("events", "first_conflicting_product", "result")
                    },
                    ensure_ascii=False,
                )
            )
            if "first_conflicting_product" in safe:
                print(
                    json.dumps(
                        {
                            k: v
                            for k, v in safe["first_conflicting_product"].items()
                            if k not in ("first", "second")
                        },
                        ensure_ascii=False,
                    )
                )


asyncio.run(main())
