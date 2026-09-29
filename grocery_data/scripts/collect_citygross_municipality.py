"""City Gross municipal collection through the existing collector and OWN.

Explicit isolated entry point. Publication/reload remains the ordinary refresh
job's responsibility. Every store has its own candidate DB and failure record.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
from pathlib import Path
from time import perf_counter

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.citygross.client import CityGrossClient
from grocery_data.app.connectors.citygross.connector import CityGrossConnector
from grocery_data.app.connectors.citygross.municipality_inventory import (
    approved_citygross_stores,
    discover,
)
from grocery_data.app.domain import CoverageLevel, GeographicArea, RawBatch
from grocery_data.app.domain.municipality import municipality_name
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory


class MunicipalCityGrossConnector(CityGrossConnector):
    """Only discovery is municipal; transport and price parsing are unchanged."""

    def __init__(self, inventory, store_id, *, client=None):
        self.inventory = inventory
        self.store = approved_citygross_stores(inventory)[store_id]
        self.locator = RawBatch.model_validate(inventory["registry"])
        self.latest_catalog = None
        super().__init__(client=client or CityGrossClient(
            allow_full_crawl=True, max_pages=None, allowed_store_ids=(store_id,),
        ), coverage=CoverageLevel.FULL_ONLINE_CATALOG)

    async def fetch_stores(self, area):
        if area.model_dump(mode="json") != self.inventory["area"]:
            raise ValueError("municipal collection area differs from inventory")
        return self.locator

    def parse_stores(self, raw, references, area):
        del references
        # Raw storage canonicalizes JSON and replay has no network counters.
        # Compare the original public facts and observation, never raw spacing.
        signature = lambda batch: [(d.kind, d.url, d.query, d.fetched_at, d.http_status, d.json_payload())
                                   for d in batch.documents]
        if (raw.chain != self.locator.chain or signature(raw) != signature(self.locator)
                or area.model_dump(mode="json") != self.inventory["area"]):
            raise ValueError("municipal register/area changed")
        # Revalidate at collection time. No locality/name fallback can add stores.
        return [approved_citygross_stores(self.inventory)[self.store.external_id]]

    async def fetch_catalog(self, store):
        try:
            self.latest_catalog = await super().fetch_catalog(store)
        except ConnectorFetchError as exc:
            self.latest_catalog = exc.partial_batch
            raise
        return self.latest_catalog


def _write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _accepted_details(database, result):
    with sqlite3.connect(database) as db:
        observed = db.execute("SELECT MIN(observed_at) FROM price_observations WHERE catalog_snapshot_id=?",
                              (result.snapshot_id,)).fetchone()[0]
        windows = [{"valid_from": a, "valid_to": b} for a, b in db.execute(
            "SELECT DISTINCT valid_from,valid_to FROM promotions WHERE catalog_snapshot_id=?",
            (result.snapshot_id,))]
    return {"observed_at": observed, "windows": windows,
            "retrieved_products": result.metrics.products_fetched,
            "approved_products": result.metrics.products_parsed if result.promoted else 0,
            "quarantine_count": result.metrics.products_quarantined,
            "own": result.metrics.products_parsed if result.promoted else 0,
            "snapshot_id": result.snapshot_id, "active_snapshot_id": result.active_snapshot_id,
            "metrics": result.metrics.model_dump(mode="json"), "warnings": list(result.warnings)}


async def collect_retained_offers(store, locator, catalog, area, directory):
    """Row-qualified fallback; retain the full run and original observations."""
    from grocery_data.app.connectors.citygross.row_approved_offers import (
        CityGrossRowApprovedOfferConnector,
    )

    database = directory / "offers.sqlite"
    engine = create_database_engine("sqlite:///" + database.resolve().as_posix())
    create_schema(engine)
    adapter = CityGrossRowApprovedOfferConnector(store=store, locator=locator, catalog=catalog)
    collector = GroceryCollector(create_session_factory(engine), FilesystemRawSnapshotStore(directory / "offers-raw"))
    try:
        with RefreshRunLock(production_refresh_lock_path(database, directory / "price-universes")):
            result = await collector.collect_area(adapter, area,
                scope_key=f"municipality:{area.municipality_code}:citygross:{store.external_id}:offer-rows")
        details = _accepted_details(database, result)
        details.update(status="success" if result.promoted else "failed", coverage="offers_only",
                       resolved_database=str(database.resolve()), qualification=adapter.row_acceptance,
                       source_fetch_mode="retained_pages_without_new_network",
                       offers_snapshot_promoted=result.promoted)
        _write(directory / "offers-result.json", details)
        return details
    finally:
        await adapter.aclose()
        engine.dispose()


async def collect(inventory, store_ids, output, *, connector_factory=MunicipalCityGrossConnector):
    """Collect only approved IDs, retain failures, and return durable source DBs."""
    approved = approved_citygross_stores(inventory)
    store_ids = set(store_ids)
    if not store_ids.issubset(approved):
        raise ValueError("requested City Gross store absent from verified municipality")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    _write(output / "inventory.json", inventory)
    area = GeographicArea.model_validate(inventory["area"])
    report = {"production_activation": False, "inventory_selected_ids": sorted(store_ids),
              "municipality_code": area.municipality_code,
              "source_fetch_mode": "fresh_network" if store_ids else "no_external_price_calls",
              "stores": []}
    started = perf_counter()
    for store_id in sorted(store_ids):
        directory = output / store_id
        directory.mkdir()
        database = directory / "own.sqlite"
        engine = create_database_engine("sqlite:///" + database.resolve().as_posix())
        create_schema(engine)
        connector = connector_factory(inventory, store_id)
        collector = GroceryCollector(create_session_factory(engine), FilesystemRawSnapshotStore(directory / "raw"))
        row = {"store_id": store_id, "site_id": approved[store_id].physical_store_external_id,
               "name": approved[store_id].name, "status": "failed", "coverage": "full_online_catalog",
               "price_channel": "online_store", "source_url": approved[store_id].source_fields["official_store_url"],
               "database": database.relative_to(output).as_posix(), "resolved_database": str(database.resolve()),
               "own": 0, "approved_products": 0, "quarantine_count": 0, "retrieved_products": 0,
               "observed_at": None, "windows": [], "price_universe": None}
        report["stores"].append(row)
        try:
            with RefreshRunLock(production_refresh_lock_path(database, directory / "price-universes")):
                result = await collector.collect_area(connector, area,
                    scope_key=f"municipality:{area.municipality_code}:citygross:{store_id}")
            row.update(_accepted_details(database, result))
            row.update(status="success" if result.promoted else "failed",
                       full_snapshot_status=result.status.value, full_snapshot_promoted=result.promoted)
        except Exception as exc:  # noqa: BLE001 - isolate each failed store
            row.update(error_type=type(exc).__name__, reason="catalog_fetch_or_validation_failed")
        finally:
            await connector.aclose()
            engine.dispose()
        batch = connector.latest_catalog
        if batch is not None:
            row["actual_catalog_network_requests"] = batch.transport.request_count
            row["source_version"] = [d.payload_hash for d in batch.documents]
            row["catalog_completion"] = batch.catalog_completion.model_dump(mode="json") if batch.catalog_completion else None
            if not row["retrieved_products"] and batch.catalog_completion:
                row["retrieved_products"] = batch.catalog_completion.products_observed
            if not row["observed_at"] and batch.documents:
                row["observed_at"] = min(d.fetched_at for d in batch.documents).isoformat()
            if row["status"] != "success" and any(d.kind == "catalog_page" for d in batch.documents):
                row["full_catalog_outcome"] = dict(row)
                try:
                    fallback = await collect_retained_offers(
                        approved[store_id], connector.locator, batch, area, directory)
                    row["offers_fallback"] = fallback
                    if fallback["status"] == "success":
                        row.update(fallback)
                        row["database"] = (directory / "offers.sqlite").relative_to(output).as_posix()
                except Exception as exc:  # noqa: BLE001 - keep failed fallback and original full cause
                    row["offers_fallback"] = {"status": "failed", "error_type": type(exc).__name__,
                                               "reason": "retained_offer_qualification_failed"}
        _write(directory / "result.json", row)
        _write(output / "coverage.json", report)
    report["runtime_seconds"] = round(perf_counter() - started, 3)
    _write(output / "coverage.json", report)
    return report


async def run(code, output, *, inventory_path=None, inventory_only=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    area = GeographicArea(city=municipality_name(code), mode="municipality", municipality_code=code)
    inventory = (json.loads(Path(inventory_path).read_bytes()) if inventory_path
                 else await discover(area, output / "discovery"))
    if inventory["area"] != area.model_dump(mode="json"):
        raise ValueError("retained inventory belongs to another municipality")
    selected = approved_citygross_stores(inventory)
    report = {"inventory": inventory, "production_activation": False}
    if not inventory_only:
        report["collection"] = await collect(inventory, set(selected), output / "collection")
    _write(output / "coverage.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--municipality-code", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--inventory-only", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(run(args.municipality_code, args.output,
                             inventory_path=args.inventory, inventory_only=args.inventory_only))
    print(json.dumps({"selected": report["inventory"]["selected_store_ids"],
                      "stores": report.get("collection", {}).get("stores", [])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
