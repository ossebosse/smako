"""Bounded explicit physical-store evaluation; isolated OWN, no live activation.

Inventory is existing discovery output. IDs select a verification sample; they
are neither a new discovery list nor a production allowlist. No images/models.
"""
import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from time import perf_counter

from grocery_data.app.connectors.coop.connector import CoopConnector, CoopRowApprovedOfferConnector
from grocery_data.app.domain import GeographicArea, RawBatch, SourceStore
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory


def same_official_identity(prior, fresh):
    """Public map uses strings; StorePageType uses integer account numbers."""
    left = prior.source_fields.get("ledger_account_number")
    right = fresh.source_fields.get("ledger_account_number")
    return (prior.chain == fresh.chain and prior.external_id == fresh.external_id
            and left is not None and right is not None and str(left) == str(right))


async def collect(inventory, store_ids, output):
    if output.exists():
        raise ValueError("output exists; refusing to overwrite evidence or data")
    records = inventory.get("stores", [])
    selected = {}
    for row in records:
        store = SourceStore.model_validate(row.get("store", row))
        if store.chain.value == "coop" and store.external_id in store_ids:
            if store.external_id in selected and selected[store.external_id] != store:
                raise ValueError("conflicting inventory store identities")
            selected[store.external_id] = store
    if selected.keys() != set(store_ids):
        raise ValueError("requested store absent from verified inventory")
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    database = output / "own.sqlite"
    engine = create_database_engine("sqlite:///" + database.resolve().as_posix())
    create_schema(engine)
    collector = GroceryCollector(create_session_factory(engine), FilesystemRawSnapshotStore(output / "raw"))
    connector = CoopConnector()
    report = {"production_activation": False, "coverage": "partial_row_approved_offers_only",
              "inventory_selected_ids": sorted(store_ids), "stores": []}
    started = perf_counter()
    try:
        with RefreshRunLock(production_refresh_lock_path(database, output / "price-universes")):
            for account, prior in selected.items():
                row = {"store_id": account, "name": prior.name, "status": "failed", "own": 0}
                report["stores"].append(row)
                try:
                    row["stage"] = "official_store_identity"
                    # Recheck official StorePageType identity before offer fetch.
                    doc = await connector.client._get(prior.source_fields["store_page_path"], kind="store_page")
                    locator = RawBatch(chain="coop", documents=(doc,))
                    stores = connector.parse_stores(locator, ["official-store"], GeographicArea(city=prior.city))
                    if len(stores) != 1 or not same_official_identity(prior, stores[0]):
                        raise ValueError("official store identity changed")
                    fresh = stores[0]
                    store = SourceStore.model_validate({**fresh.model_dump(),
                        "address": fresh.address or prior.address,
                        "postal_code": fresh.postal_code or prior.postal_code,
                        "latitude": fresh.latitude or prior.latitude,
                        "longitude": fresh.longitude or prior.longitude,
                        "source_fields": {**prior.source_fields, **fresh.source_fields,
                            "retained_address_reference": prior.raw_reference if not fresh.address else None}})
                    row["stage"] = "public_offer_fetch"
                    batch = await connector.fetch_offers(store)
                    row.update(last_fetched_at=batch.documents[0].fetched_at.isoformat(), fetch_status="success")
                    for label, value in (("store", store), ("locator", locator), ("batch", batch)):
                        (sources / f"{account}-{label}.json").write_text(value.model_dump_json(indent=2), encoding="utf-8")
                    retained = CoopRowApprovedOfferConnector(store=store, locator=locator, offers=batch)
                    row["stage"] = "row_approved_import"
                    result = await collector.collect_area(retained, GeographicArea(city=store.city),
                        scope_key=f"{store.city.casefold()}:coop:{account}:offer-rows")
                    (sources / f"{account}-extracted.json").write_text(retained.extracted.model_dump_json(indent=2), encoding="utf-8")
                    row.update(status="partial_candidate" if result.promoted else "rejected", source_url=batch.documents[0].url,
                        observed_at=batch.documents[0].fetched_at.isoformat(),
                        source_hash=batch.documents[0].payload_hash,
                        extracted_variants=len(retained.extracted.products),
                        own=result.metrics.products_parsed if result.promoted else 0,
                        quarantined=result.metrics.products_quarantined,
                        full_snapshot_status=result.status.value,
                        partial_snapshot_promoted=result.promoted,
                        snapshot_id=result.snapshot_id,
                        metrics=result.metrics.model_dump(mode="json"),
                        qualification=retained.row_acceptance,
                        blockers=dict(Counter(b for d in retained.row_acceptance["decisions"] for b in d["blockers"])))
                    row["stage"] = "complete"
                except Exception as exc:  # noqa: BLE001 - retain failed sample stores; no retry
                    from grocery_data.app.services.failure_diagnostics import failure_details

                    row["error_type"] = type(exc).__name__
                    row["failure_details"] = failure_details(exc)
                    row["error"] = "Public fetch/identity/import failed; no activation or retry"
                (output / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        await connector.aclose()
        engine.dispose()
    report["runtime_seconds"] = round(perf_counter() - started, 3)
    (output / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--store-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(set(args.store_id)) > 5:
        parser.error("this bounded evaluation accepts at most five stores")
    report = asyncio.run(collect(json.loads(args.inventory.read_bytes()), set(args.store_id), args.output))
    print(json.dumps({"stores": [{k: row[k] for k in ("store_id", "status", "own")} for row in report["stores"]],
                      "runtime_seconds": report["runtime_seconds"]}))
    if any(row["status"] != "partial_candidate" for row in report["stores"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
