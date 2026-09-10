"""Operator-only bounded Primat audit; private evidence, never a public dataset."""

import asyncio
import json
import os
from pathlib import Path

from app.providers.primat import PrimatPriceProvider
from app.services.production_primat_refresh import collect_city_primat_cache
from sqlalchemy.engine import make_url

from deploy.scripts.run_daily_refresh import _operations_lock
from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.raw_storage import sanitize_json_payload


async def main():
    root = Path("/srv/app/var/reports/automation-ica-audit")
    root.mkdir(mode=0o700, exist_ok=False)
    rows = {}
    occurrences = {}
    original = PrimatPriceProvider._parse_product
    fields = {
        "chain",
        "store_id",
        "product_id",
        "id",
        "name",
        "brand",
        "category",
        "amount",
        "unit",
        "package",
        "available",
        "gtin",
        "ean",
        "prices",
        "changed_at",
        "confirmed_at",
        "sale_model",
        "sale_unit",
        "price_unit",
        "fixed_package",
        "variable_weight",
        "sold_by_weight",
        "count",
        "weight",
        "volume",
        "eligibility",
        "scope",
        "audience",
    }

    def capture(self, row):
        safe = sanitize_json_payload({k: v for k, v in row.items() if k in fields})
        key = str(row.get("store_id")) + ":" + str(row.get("product_id") or row.get("id"))
        if key in rows and rows[key] != safe:
            raise ValueError("raw identity changed during audit")
        rows[key] = safe
        occurrences[str(row.get("store_id"))] = occurrences.get(str(row.get("store_id")), 0) + 1
        return original(self, row)

    PrimatPriceProvider._parse_product = capture
    with _operations_lock():
        database = Path(make_url(os.environ["GROCERY_DATABASE_URL"]).database)
        cache = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]) / "external-provider-cache"
        active = json.loads((cache / "active/city-lund.json").read_bytes())
        previous = (cache / active["artifact_file"]).read_bytes()
        atomic_write_bytes(root / "previous-cache.json", previous)
        report = await collect_city_primat_cache(
            database,
            "Lund",
            "22350",
            root / "candidate-before.json",
            48,
            lkg_cache=cache / active["artifact_file"],
        )
        for name, value in [
            ("raw-private.json", {"rows": list(rows.values()), "occurrences": occurrences}),
            ("capture.json", report),
        ]:
            atomic_write_bytes(root / name, json.dumps(value, ensure_ascii=False).encode())
            os.chmod(root / name, 0o600)
    print(
        json.dumps(
            {
                "status": report["status"],
                "transport": report["transport"],
                "unique_raw_rows": len(rows),
                "contexts": report["contexts"],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
