"""Reparse isolated City Gross collection using the ordinary replay service.

Copy retained evidence to a new directory, preserve all source observations and
hashes, and fail every transport entry point. This is never a network collection.
"""
import argparse
import asyncio
import json
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from grocery_data.app.connectors.citygross.client import CityGrossClient
from grocery_data.app.domain import RunMetrics
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import create_database_engine, create_session_factory
from grocery_data.scripts.collect_citygross_municipality import (
    MunicipalCityGrossConnector,
    _accepted_details,
)


class NoNetworkMunicipalConnector(MunicipalCityGrossConnector):
    async def fetch_stores(self, area):
        raise AssertionError("municipal replay must not fetch store registry")

    async def fetch_catalog(self, store):
        raise AssertionError("municipal replay must not fetch prices")


async def replay(collection, output):
    collection, output = Path(collection), Path(output)
    if output.exists():
        raise ValueError("replay evidence output already exists")
    inventory = json.loads((collection / "inventory.json").read_bytes())
    original = json.loads((collection / "coverage.json").read_bytes())
    output.mkdir(parents=True)
    (output / "inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf8")
    report = {**original, "source_fetch_mode": "offline_database_replay", "network_requests": 0,
              "source_collection": str(collection.resolve()), "stores": []}
    for prior in original["stores"]:
        store_id = prior["store_id"]
        if prior["status"] != "success" or prior["coverage"] != "full_online_catalog":
            raise ValueError("this full replay requires accepted original full catalog")
        directory = output / store_id
        source_directory = collection / store_id
        shutil.copytree(source_directory, directory)
        database = directory / "own.sqlite"
        engine = create_database_engine("sqlite:///" + database.resolve().as_posix())
        factory = create_session_factory(engine)
        client = CityGrossClient(allow_full_crawl=False, max_pages=1, allowed_store_ids=(store_id,))
        connector = NoNetworkMunicipalConnector(inventory, store_id, client=client)
        try:
            with RefreshRunLock(production_refresh_lock_path(database, directory / "price-universes")):
                result = await DatabaseReplayService(factory, FilesystemRawSnapshotStore(directory / "raw")).replay_snapshot(
                    connector, prior["snapshot_id"], promote=True)
            with sqlite3.connect(database) as db:
                stored = db.execute("SELECT metrics FROM catalog_snapshots WHERE id=?", (result.replay_snapshot_id,)).fetchone()
                metrics = RunMetrics.model_validate(json.loads(stored[0])["run_metrics"])
                def signature(snapshot_id):
                    return db.execute("SELECT external_product_id,fetched_at FROM source_products WHERE catalog_snapshot_id=? ORDER BY external_product_id", (snapshot_id,)).fetchall()
                if signature(prior["snapshot_id"]) != signature(result.replay_snapshot_id):
                    raise ValueError("replay changed product observations")
            fake_result = SimpleNamespace(snapshot_id=result.replay_snapshot_id,
                active_snapshot_id=result.replay_snapshot_id if result.promoted else prior["snapshot_id"],
                promoted=result.promoted, metrics=metrics, warnings=[])
            row = {**prior, **_accepted_details(database, fake_result),
                   "status": "success" if result.promoted else "failed",
                   "resolved_database": str(database.resolve()),
                   "source_fetch_mode": "offline_database_replay", "network_requests": result.network_requests,
                   "actual_catalog_network_requests": 0, "source_snapshot_id": prior["snapshot_id"],
                   "parser_version": connector.parser_version, "original_observations_unchanged": True}
            report["stores"].append(row)
            (directory / "result.json").write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf8")
            (output / "coverage.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
        finally:
            await connector.aclose()
            engine.dispose()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = asyncio.run(replay(args.collection, args.output))
    print(json.dumps({"network_requests": result["network_requests"], "stores": [
        {k: row[k] for k in ("store_id", "status", "own", "observed_at", "parser_version")}
        for row in result["stores"]]}, ensure_ascii=False))
