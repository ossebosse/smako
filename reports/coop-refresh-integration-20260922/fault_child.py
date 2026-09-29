"""Explicit faults/withdrawal mutation around ordinary CLI, never live evidence."""
import json
import os
import runpy
import sys
from pathlib import Path

from grocery_data.app.domain import RawBatch
from grocery_data.app.services.coop_offer_job import configuration, location, read
from grocery_data.scripts import collect_coop_physical_offers


async def failed_transport(*args, **kwargs):
    raise TimeoutError("controlled isolated transport failure")


if os.environ.get("TEST_COOP_EXPIRY_DATE"):
    from datetime import datetime
    from app.providers import coop_municipality_offers
    test_day = datetime.fromisoformat(os.environ["TEST_COOP_EXPIRY_DATE"])
    class PurchaseDay(datetime):
        @classmethod
        def now(cls, tz=None):
            return test_day.replace(tzinfo=tz)
    coop_municipality_offers.datetime = PurchaseDay
elif os.environ.get("TEST_COOP_WITHDRAWAL") == "true":
    root, config = configuration()
    state = read(location(root, config))
    selected = next(r for r in state["selection"]["stores"] if r["selected"] and r["concept"] != "X:-tra")
    account = selected["store_id"]
    retained = (root / state["approved"][account][0]["database"]).parent / "sources"
    locator = RawBatch.model_validate_json((retained / (account+"-locator.json")).read_bytes())
    batch = RawBatch.model_validate_json((retained / (account+"-batch.json")).read_bytes())
    document = batch.documents[0]
    payload = json.loads(document.payload)
    payload.update(cards=[], captured_total=0)
    if payload.get("declared_total") is not None:
        payload["declared_total"] = 0
    for group in payload["structured_offers"]["data"]["sortingGroups"]:
        group.update(offerAmount=0, offers=[])
    batch = batch.model_copy(update={"documents": (document.model_copy(update={"payload": json.dumps(payload).encode()}),)})
    class EmptyCoop(collect_coop_physical_offers.CoopConnector):
        def __init__(self):
            super().__init__()
            async def get(*args, **kwargs):
                return locator.documents[0]
            self.client._get = get
        async def fetch_offers(self, store):
            assert store.external_id == account
            return batch
    collect_coop_physical_offers.CoopConnector = EmptyCoop
else:
    collect_coop_physical_offers.collect = failed_transport
sys.argv = ["grocery_data", *sys.argv[1:]]
runpy.run_module("grocery_data", run_name="__main__")
