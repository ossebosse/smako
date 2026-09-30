"""Replay a captured Hemkop catalog under the reviewed parser, without refetching.

Run in an isolated data copy with job.py from the retained release evidence on
PYTHONPATH. The source snapshot and its raw files must already be present.
"""

import argparse
import asyncio
import json
import os
import socket
import sqlite3
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

from job import configure

from grocery_data.app.connectors.hemkop.connector import HemkopConnector
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import create_database_engine, create_session_factory


def no_network(*_args, **_kwargs):
    raise AssertionError("Replay attempted a network request")


def raw_times(database: Path, snapshot_id: str):
    with sqlite3.connect(database) as connection:
        return connection.execute(
            "SELECT MIN(fetched_at), MAX(fetched_at), COUNT(*) "
            "FROM raw_snapshots WHERE catalog_snapshot_id=?",
            (snapshot_id,),
        ).fetchone()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--store-id", choices=("4123", "4224"), required=True)
    args = parser.parse_args()
    configure()
    work = Path("/work")
    database = work / "grocery.sqlite"
    factory = create_session_factory(create_database_engine(os.environ["GROCERY_DATABASE_URL"]))
    service = DatabaseReplayService(factory, FilesystemRawSnapshotStore(work / "raw"))
    original = raw_times(database, args.snapshot_id)
    if not original[2]:
        raise ValueError("Captured snapshot has no raw references")
    with (
        RefreshRunLock(production_refresh_lock_path(database, work / "price-universes")),
        patch.object(socket, "getaddrinfo", no_network),
    ):
        result = asyncio.run(
            service.replay_snapshot(
                HemkopConnector.for_replay(store_external_ids=(args.store_id,)),
                args.snapshot_id,
                promote=True,
            )
        )
    replayed = raw_times(database, result.replay_snapshot_id)
    if original != replayed:
        raise AssertionError("Replay changed raw observation range or reference count")
    outcome = {
        "source_snapshot_id": args.snapshot_id,
        "store_id": args.store_id,
        "result": asdict(result),
        "source_raw_range": original,
        "replay_raw_range": replayed,
        "network_requests": 0,
    }
    target = work / "release-hemkop-terminal-replay.json"
    target.write_text(json.dumps(outcome, default=str, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(outcome, default=str))


if __name__ == "__main__":
    main()
