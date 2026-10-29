"""Reviewed source absences; synthetic mutations never become price facts."""
import copy
import json

import pytest

from grocery_data.app.connectors.coop.browser import CoopBrowserOffersTransport
from grocery_data.app.connectors.coop.structured_offers import (
    confirmed_empty_response,
    sanitized_response,
)
from grocery_data.app.connectors.coop.xtra_publications import publication_links
from grocery_data.tests.test_coop_municipal_contract import FIX, page
from grocery_data.tests.test_coop_physical_structured import parse, source


def empty(envelope):
    envelope.update(captured_total=0, declared_total=None, cards=[])
    envelope["structured_offers"]["data"] = {}


def test_reviewed_empty_object_requires_store_bound_response_and_empty_dom():
    store, batch = source()
    envelope = json.loads(batch.documents[0].payload)
    empty(envelope)
    evidence = envelope["structured_offers"]
    assert sanitized_response({}) == {}
    assert confirmed_empty_response([evidence], store)
    payload = CoopBrowserOffersTransport._sanitized_payload(
        [], declared_total=None, store=store, structured_responses=[evidence])
    assert json.loads(payload)["structured_offers"]["data"] == {}
    parsed, accepted, qualification = parse(mutate=empty)
    assert not parsed.products and not parsed.failures and not accepted.products
    assert not qualification["shared_blockers"]
    for patch in ({"captured_total": 1}, {"cards": [{}]}, {"declared_total": 1}):
        def changed(value, patch=patch):
            empty(value)
            value.update(patch)
        assert parse(mutate=changed)[0].failures
    for patch in ({"http_status": 503}, {"source_url": "https://external.api.coop.se/wrong"},
                  {"ledger_account_number": "wrong"}, {"store_external_id": "wrong"},
                  {"error": "failed"}, {"data": None}, {"data": []},
                  {"data": {"unknown": []}}, {"data": {"sortingGroups": []}}):
        assert not confirmed_empty_response([{**evidence, **patch}], store)
    assert not confirmed_empty_response([evidence, evidence], store)


@pytest.mark.parametrize("identity", ["3658", "3646"])
def test_explicit_blank_official_publication_is_empty_but_missing_or_conflicting_is_blocked(identity):
    raw = json.loads((FIX / (identity + "-page.json")).read_bytes())["store"]
    store = json.loads((FIX / (identity + "-store.json")).read_bytes())
    blank = {**raw, "weeklyOffersLink": ""}
    assert publication_links(page(blank), store) == []
    for value in (None, False, [], {}):
        with pytest.raises(ValueError):
            publication_links(page({**blank, "weeklyOffersLink": value}), store)
    missing = copy.deepcopy(blank)
    del missing["weeklyOffersLink"]
    with pytest.raises(ValueError):
        publication_links(page(missing), store)
    with pytest.raises(ValueError):
        publication_links(page({**blank, "id": "wrong"}), store)
    with pytest.raises(ValueError):
        publication_links(page(blank) + '<a href="https://dr.coop.se/Butik/?store=other">Flyer</a>', store)
    with pytest.raises(ValueError):
        publication_links(page(blank) + '<a href="https://example.test/current.pdf">Reklamblad</a>', store)


async def test_verified_absent_publication_preserves_observation_and_unknown_stays_failed(tmp_path, monkeypatch):
    from grocery_data.scripts import collect_coop_municipality as pipeline
    evidence = {"editions": [], "discovered_links": [],
                "publication_status": "confirmed_no_current_publication",
                "store_page_sha256": "a" * 64,
                "store_page_observed_at": "2026-10-29T08:00:00+00:00"}
    async def fetched(*args):
        return copy.deepcopy(evidence)
    monkeypatch.setattr(pipeline, "fetch_publications", fetched)
    result, products = await pipeline.collect_xtra({}, {}, tmp_path)
    assert not products and result["status"] == "confirmed_no_qualified_rows"
    assert result["observed_at"] == evidence["store_page_observed_at"]
    evidence.pop("publication_status")
    result, _ = await pipeline.collect_xtra({}, {}, tmp_path)
    assert result["status"] == "blocked_or_incomplete_publications"


@pytest.mark.parametrize("known_empty", [True, False])
async def test_disabled_flyer_runs_real_import_only_for_verified_empty_response(tmp_path, monkeypatch, known_empty):
    from grocery_data.scripts import collect_coop_physical_offers as pipeline
    store, batch = source()
    store = store.model_copy(update={"source_fields": {**store.source_fields, "disable_store_offers_flyer": True}})
    envelope = json.loads(batch.documents[0].payload)
    empty(envelope)
    if not known_empty:
        envelope["structured_offers"]["data"] = {"sortingGroups": []}
    batch = batch.model_copy(update={"documents": (batch.documents[0].model_copy(
        update={"payload": json.dumps(envelope).encode()}),)})
    class Client:
        async def _get(self, *args, **kwargs):
            return batch.documents[0]
    class Public:
        client = Client()
        def parse_stores(self, *args):
            return [store]
        async def fetch_offers(self, *args):
            return batch
        async def aclose(self):
            pass
    monkeypatch.setattr(pipeline, "CoopConnector", Public)
    report = await pipeline.collect({"stores": [{"store": store.model_dump(mode="json")}]},
                                    {store.external_id}, tmp_path / "attempt")
    row = report["stores"][0]
    if known_empty:
        extracted = json.loads((tmp_path / "attempt/sources" / (store.external_id + "-extracted.json")).read_bytes())
        assert not extracted["products"] and not extracted["failures"]
        assert row["status"] == "rejected" and not row["qualification"]["shared_blockers"]
        assert not row["partial_snapshot_promoted"] and row["own"] == 0
    else:
        assert row["status"] == "failed" and row["own"] == 0
