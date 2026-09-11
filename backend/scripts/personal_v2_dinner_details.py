"""One bounded, approved Coop facts-only probe. Never imports prices into a catalog."""

import asyncio
import json
from pathlib import Path

from grocery_data.app.connectors.coop.online_catalog_client import CoopOnlineCatalogClient
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)


async def main():
    selection = json.loads(Path("/tmp/dinner-detail-selection.json").read_bytes())
    ids = list(dict.fromkeys(r["id"] for r in selection))
    assert 0 < len(ids) <= 50
    target = Path("/tmp/dinner-detail-result.json")
    assert not target.exists(), "Do not repeat a completed probe"
    client = CoopOnlineCatalogClient()
    result = {
        "requested_distinct_products": len(ids),
        "context": "730400",
        "selection": selection,
        "price_observations_created": 0,
    }
    try:
        document = await client.fetch_products_by_id("730400", ids)
        # The existing connector already sanitizes the public payload.
        result.update(status="FETCHED", document=document.model_dump(mode="json"))
    except Exception as exc:  # noqa: BLE001 - stop boundary; never retry or expose transport values
        # Exception text can contain transport parameters: report its type only.
        result.update(status="STOPPED", error_type=type(exc).__name__)
    finally:
        await client.aclose()
    target.write_text(json.dumps(result, ensure_ascii=False), encoding="utf8")
    print(json.dumps({k: v for k, v in result.items() if k not in {"document", "selection"}}))


if __name__ == "__main__":
    lock = RefreshRunLock(
        production_refresh_lock_path(
            Path("/srv/app/var/grocery/grocery_data.sqlite"), Path("/srv/app/var/price_universes")
        )
    )
    with lock:
        asyncio.run(main())
