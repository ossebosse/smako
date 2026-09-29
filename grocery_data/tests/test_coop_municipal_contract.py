"""Municipal pipeline guards; saved official sources, explicitly offline."""
import asyncio
import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop.xtra_publications import publication_links
from grocery_data.app.services.area_membership import approved_municipal_stores
from grocery_data.app.services.coop_municipal_refresh import update_selection
from grocery_data.tests.test_coop_municipality import inventory

FIX = Path(__file__).parent / "fixtures/coop-municipal-contract-20260922"
NOW = datetime(2026, 9, 22, 9, tzinfo=UTC)


@pytest.fixture(scope="module", params=[("1281", "Lund"), ("1280", "Malmö")])
def municipal(request):
    return inventory(*request.param)


def page(raw):
    return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps(
        {"props": {"pageProps": {"data": {"store": raw}}}}
    ) + "</script>"


@pytest.mark.parametrize("identity", ["3658", "3646"])
def test_current_official_structured_link_without_visible_anchor(identity):
    source = json.loads((FIX / (identity + "-page.json")).read_bytes())
    store = json.loads((FIX / (identity + "-store.json")).read_bytes())
    raw = source["store"]
    assert publication_links(page(raw), store) == [raw["weeklyOffersLink"]]
    changed = {**raw, "weeklyOffersLink": raw["weeklyOffersLink"] + "&edition=next"}
    assert publication_links(page(changed), store) == [changed["weeklyOffersLink"]]
    for patch in [{"id": "WRONG"}, {"streetName": "Another street"},
                  {"weeklyOffersLink": "https://dr.coop.se/Butik/?store=WRONG"},
                  {"weeklyOffersLink": None}]:
        with pytest.raises(ValueError):
            publication_links(page({**raw, **patch}), store)


def test_actual_second_municipality_pdf_bound_to_store_not_shared_prices():
    from grocery_data.app.connectors.coop import xtra_pdf
    from grocery_data.app.domain import RawFetch, SourceStore
    from grocery_data.app.services.offer_rows import qualify_rows

    meta = json.loads((FIX / "3646-source.json").read_bytes())
    store = SourceStore.model_validate_json((FIX / "3646-store.json").read_bytes())
    fields = {**store.source_fields, "offers_url": meta["source_url"],
              "offer_policy": xtra_pdf.POLICY, "pdf_sha256": meta["sha256"],
              "pdf_observed_at": meta["observed_at"], "pdf_pages": meta["document_pages"]}
    store = store.model_copy(update={"source_fields": fields})
    doc = RawFetch(chain="coop", store_external_id=store.external_id, kind="xtra_pdf", method="GET",
                   url=meta["source_url"], fetched_at=meta["observed_at"], http_status=200,
                   content_type="application/pdf", payload=(FIX / "3646.pdf").read_bytes(),
                   connector_version="saved-source-regression")
    parsed, report = xtra_pdf.parse_pdf(doc, store, "saved-source-regression")
    accepted, evidence = qualify_rows(parsed, store=store, observed_at=doc.fetched_at)
    assert len(report["pages"]) == 8 and len(parsed.products) == 57
    assert len(accepted.products) == 18 and not evidence["shared_blockers"]
    assert len(accepted.failures) == 39
    from grocery_data.app.services.source_purchase_terms import bound_purchase_terms
    assert all(bound_purchase_terms(p) is not None for p in accepted.products)
    assert all(p.fetched_at == doc.fetched_at for p in accepted.products)
    wrong = store.model_copy(update={"external_id": "3658", "name": "X:-Tra Skansvägen"})
    parsed, report = xtra_pdf.parse_pdf(doc, wrong, "cross-store-adversarial")
    accepted, evidence = qualify_rows(parsed, store=wrong, observed_at=doc.fetched_at)
    assert not accepted.products and evidence["shared_blockers"]


def test_unrecognized_pdf_layout_is_explicit_not_empty_success(tmp_path, monkeypatch):
    from grocery_data.scripts import collect_coop_municipality as pipeline
    from grocery_data.scripts import import_xtra_pdf_text as importer

    edition = tmp_path / "edition"
    edition.mkdir()
    (edition / "import").mkdir()
    (edition / "import/price-universe.json").write_text('{"products": []}', encoding="utf8")
    inv = inventory("1281", "Lund")
    row = next(r for r in inv["stores"] if r["store"]["external_id"] == "3658")

    async def fetched(*args):
        return {"editions": [{"status": "text_ready", "sha256": "test-layout-mutation",
                 "directory": str(edition), "source_url": row["store"]["source_fields"]["offers_url"],
                 "observed_at": NOW.isoformat()}]}

    async def imported(*args):
        return {"qualification": {"shared_blockers": []}, "partial_promoted": False,
                "metrics": {"products_parsed": 0, "products_quarantined": 0},
                "price_universe_count": 0,
                "pages": [{"page": 1, "ads": [], "unclassified_price_spans": [1],
                           "unassigned_condition_spans": []}]}

    monkeypatch.setattr(pipeline, "fetch_publications", fetched)
    monkeypatch.setattr(importer, "run", imported)
    result, products = asyncio.run(pipeline.collect_xtra(row, inv, tmp_path))
    assert not products
    assert result["status"] == "blocked_or_incomplete_publications"
    assert result["editions"][0]["import_status"] == "unsupported_text_layout"
    assert result["editions"][0]["unclassified_ads"] is None


def test_scope_drives_all_concepts_and_never_drops_unknown(municipal):
    approved = approved_municipal_stores(municipal, concepts=("Coop", "Stora Coop", "X:-tra"))
    selection = update_selection(municipal, now=NOW)
    assert set(selection["due_store_ids"]) == set(approved)
    assert len(selection["stores"]) == len(municipal["stores"]) == 778
    assert {s.source_fields["concept"] for s in approved.values()} >= {"Coop", "X:-tra"}
    code = municipal["area"]["municipality_code"]
    assert ("3658" in approved) == (code == "1281")
    assert ("3646" in approved) == (code == "1280")
    changed = copy.deepcopy(municipal)
    changed["area"]["municipality_code"] = "1280" if code == "1281" else "1281"
    assert not approved_municipal_stores(changed)
    assert not update_selection(changed, now=NOW)["due_store_ids"]
    with pytest.raises(ValueError, match="another municipality"):
        update_selection(changed, previous=selection, now=NOW)


def test_restart_failure_retry_and_source_change(municipal):
    chosen = approved_municipal_stores(municipal)
    outcomes = {i: {"status": "partial_candidate", "observed_at": NOW.isoformat(),
                    "windows": [{"valid_from": "2026-09-24", "valid_to": "2026-09-27"}]}
                for i in chosen}
    state = update_selection(municipal, outcomes, now=NOW)
    restored = update_selection(municipal, previous=state, now=NOW + timedelta(minutes=1))
    assert not restored["due_store_ids"]
    assert restored["next_inventory_check"] == state["next_inventory_check"]
    identity = next(iter(chosen))
    failed = update_selection(municipal, {identity: {"status": "failed"}}, previous=state, now=NOW)
    row = next(r for r in failed["stores"] if r["store_id"] == identity)
    assert row["last_success"] == NOW.isoformat()
    assert row["next_fetch_at"] == (NOW + timedelta(minutes=15)).isoformat()
    changed = copy.deepcopy(municipal)
    store = next(r["store"] for r in changed["stores"] if r["store"]["external_id"] == identity)
    store["source_fields"]["offers_url"] += "?changed=1"
    assert identity in update_selection(changed, previous=state, now=NOW)["due_store_ids"]


def test_no_due_work_no_network_no_empty_candidate(municipal, tmp_path, monkeypatch):
    from grocery_data.scripts import collect_coop_municipality as pipeline

    def forbidden(*args, **kwargs):
        raise AssertionError("no network, source collection or projection allowed")

    for name in ["discover", "collect", "collect_xtra", "project_structured"]:
        monkeypatch.setattr(pipeline, name, forbidden)
    inv = tmp_path / "inventory.json"
    inv.write_text(json.dumps(municipal), encoding="utf8")
    future = datetime.now(UTC) + timedelta(days=1)
    outcomes = {i: {"status": "partial_candidate", "observed_at": NOW.isoformat(), "windows": []}
                for i in approved_municipal_stores(municipal)}
    state = update_selection(municipal, outcomes, now=future)
    previous = tmp_path / "previous.json"
    previous.write_text(json.dumps(state), encoding="utf8")
    output = tmp_path / "run"
    result = asyncio.run(pipeline.run(municipal["area"]["municipality_code"], output,
                        inventory_path=inv, previous_path=previous, due_only=True))
    assert result["candidate_status"] == "not_built_no_due_work"
    assert result["price_universe_count"] is None
    assert not (output / "price-universe.json").exists()
    assert len(result["inventory"]["stores"]) == 778
