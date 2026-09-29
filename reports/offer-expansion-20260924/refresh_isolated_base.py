"""Existing collectors against a private frozen base, no production activation."""
import asyncio
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from grocery_data.app.connectors.coop.online_catalog_client import CoopOnlineCatalogClient
from grocery_data.app.connectors.coop.online_catalog_connector import CoopOnlineCatalogConnector
from grocery_data.app.domain import CoverageLevel, GeographicArea
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_session_factory

R = Path(__file__).resolve().parent


async def main():
    original = R / 'base/grocery.sqlite'
    db = R / 'base/refreshed.sqlite'
    assert original.exists() and not db.exists()
    with sqlite3.connect(original.resolve().as_uri()+'?mode=ro',uri=True) as src:
        with sqlite3.connect(db) as dst:
            src.backup(dst)
    engine = create_database_engine('sqlite:///' + db.as_posix())
    connector = CoopOnlineCatalogConnector(coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        client=CoopOnlineCatalogClient(allowed_context_ids={'730400'}, allow_full_crawl=True,
            max_categories=None, max_pages_per_category=None))
    try:
        result = await GroceryCollector(create_session_factory(engine),
            FilesystemRawSnapshotStore(R / 'base/raw')).collect_area(
                connector, GeographicArea(city='Lund'), auto_promote=True)
        (R/'base-refresh.json').write_text(json.dumps(asdict(result),
            ensure_ascii=False, indent=2, default=str), encoding='utf8')
        print(result, flush=True)
    finally:
        await connector.aclose()
        engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
