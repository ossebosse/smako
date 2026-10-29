"""Both municipal price versions depend on the shared ordinary-price source."""

import sqlite3
from datetime import UTC, datetime

from grocery_data.app.services.coop_offer_job import source_plan


def test_new_syd_snapshot_invalidates_malmo_build_without_price_collection(tmp_path):
    database = tmp_path / "grocery.sqlite"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE catalog_snapshots(id,chain,scope_key,is_active,state)")
        db.execute("INSERT INTO catalog_snapshots VALUES ('old','coop','coop:online:730400',1,'promoted')")
    environment = {
        "GROCERY_DATABASE_URL": "sqlite:///" + database.as_posix(),
        "COOP_MUNICIPAL_OFFERS_ROOT": str(tmp_path / "offers"),
        "COOP_MUNICIPAL_OFFERS_ENABLED": "true", "COOP_MUNICIPALITY_CODE": "1280",
        "COOP_MUNICIPAL_BUILD_CITY": "Malmö",
    }
    now = datetime(2026, 10, 29, 10, tzinfo=UTC)
    before = source_plan(environment=environment, now=now)
    with sqlite3.connect(database) as db:
        db.execute("UPDATE catalog_snapshots SET id='new'")
    after = source_plan(environment=environment, now=now)
    assert before["fingerprint"] != after["fingerprint"]
    assert before["due_store_ids"] == after["due_store_ids"] == []
    assert before["external_price_requests"] == after["external_price_requests"] == 0
