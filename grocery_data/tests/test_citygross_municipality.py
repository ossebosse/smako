"""Captured official register/SCB geometry; explicit offline mutations below."""
import gzip
import json
from copy import deepcopy
from pathlib import Path

import pytest

from grocery_data.app.connectors.citygross.municipality_inventory import (
    approved_citygross_stores,
    build_inventory,
)
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.domain.municipality import municipality_name
from grocery_data.scripts.collect_citygross_municipality import MunicipalCityGrossConnector, collect

FIXTURE = json.loads(gzip.decompress((Path(__file__).parent / "fixtures/citygross-municipality-20260923.json.gz").read_bytes()))
RAW = RawBatch.model_validate(FIXTURE["registry"])


def inventory(code="1280", raw=RAW):
    return build_inventory(GeographicArea(city=municipality_name(code), mode="municipality",
                           municipality_code=code), raw, ["saved:stores", "saved:sites"],
                           FIXTURE["boundary-" + code])


def mutated_raw(kind, mutation):
    documents = []
    for doc in RAW.documents:
        if doc.kind == kind:
            payload = doc.json_payload()
            mutation(payload)
            doc = doc.model_copy(update={"payload": json.dumps(payload).encode()})
        documents.append(doc)
    return RAW.model_copy(update={"documents": tuple(documents)})


@pytest.mark.parametrize("code,expected", [("1281", []), ("1280", ["3211"]), ("1230", ["3229"])])
def test_same_full_official_registry_selects_real_municipalities(code, expected):
    result = inventory(code)
    assert result["registry_rows"] == len(result["stores"]) == result["site_registry_rows"] == 38
    assert result["unresolved_registry_rows"] == result["unresolved_site_rows"] == []
    assert result["selected_store_ids"] == expected
    assert sorted(approved_citygross_stores(result)) == expected
    assert result["complete"] is False
    if code == "1280":
        bernstorp = next(r for r in result["stores"] if r["store"]["external_id"] == "3203")
        assert bernstorp["store"]["name"] == "Malmö Stora Bernstorp"
        assert bernstorp["geographic_evidence"]["status"] == "outside"


def test_mapping_is_generated_without_handwritten_store_number_list():
    raw = mutated_raw("store_number_map", lambda x: next(s for s in x["sites"] if str(s["id"]) == "169").update(storeNumber="9999"))
    selected = approved_citygross_stores(inventory(raw=raw))
    assert list(selected) == ["9999"]
    assert selected["9999"].physical_store_external_id == "169"
    assert selected["9999"].price_context_type.value == "online_store"


def test_invalid_registry_store_number_is_preserved_without_filesystem_selection():
    raw = mutated_raw("store_number_map", lambda x: next(s for s in x["sites"] if str(s["id"]) == "169").update(storeNumber="../../other"))
    result = inventory(raw=raw)
    hyllie = next(r for r in result["stores"] if r["store"]["physical_store_external_id"] == "169")
    assert hyllie["collection_reason"] == "invalid_store_number"
    assert not hyllie["collection_selected"]
    assert not approved_citygross_stores(result)


def test_missing_coordinates_preserved_unknown_without_locality_fallback():
    raw = mutated_raw("stores", lambda x: next(s["data"] for s in x if str(s["data"]["siteId"]) == "169").update(storeLocation={}))
    result = inventory(raw=raw)
    hyllie = next(r for r in result["stores"] if r["store"]["external_id"] == "3211")
    assert hyllie["geographic_evidence"]["status"] == "unknown"
    assert hyllie["collection_reason"] == "official_position_missing"
    assert result["selected_store_ids"] == []


def test_missing_mapping_keeps_physical_store_and_concrete_reason():
    raw = mutated_raw("store_number_map", lambda x: x.update(sites=[s for s in x["sites"] if str(s["id"]) != "169"]))
    result = inventory(raw=raw)
    hyllie = next(r for r in result["stores"] if r["store"]["physical_store_external_id"] == "169")
    assert hyllie["geographic_evidence"]["status"] == "inside"
    assert hyllie["collection_reason"] == "missing_site_mapping"
    assert not hyllie["collection_selected"]
    assert len(result["stores"]) == 38


def test_ambiguous_mapping_and_unparseable_rows_are_visible():
    raw = mutated_raw("store_number_map", lambda x: x["sites"].append(deepcopy(next(s for s in x["sites"] if str(s["id"]) == "169"))))
    result = inventory(raw=raw)
    assert result["selected_store_ids"] == []
    assert any(r["collection_reason"] == "ambiguous_site_mapping" for r in result["stores"])
    malformed = mutated_raw("stores", lambda x: x.append({"data": {"siteId": 123456}}))
    result = inventory(raw=malformed)
    assert len(result["stores"]) + len(result["unresolved_registry_rows"]) == result["registry_rows"]
    assert result["unresolved_registry_rows"][0]["reason"] == "missing_store_identity_or_name"


@pytest.mark.parametrize("field,value", [("address", "Another address"), ("name", "Lund"),
                                        ("postal_code", "22222"), ("physical_store_external_id", "11")])
def test_saved_store_identity_cannot_override_official_evidence(field, value):
    result = inventory()
    next(r for r in result["stores"] if r["collection_selected"])["store"][field] = value
    with pytest.raises(ValueError, match="official evidence"):
        approved_citygross_stores(result)


def test_saved_inside_and_selected_flags_do_not_authorize_neighbour_store():
    result = inventory()
    wrong = next(r for r in result["stores"] if r["store"]["external_id"] == "3203")
    wrong["geographic_evidence"]["status"] = "inside"
    wrong["collection_selected"] = True
    result["selected_store_ids"].append("3203")
    with pytest.raises(ValueError, match="selection"):
        approved_citygross_stores(result)


@pytest.mark.asyncio
async def test_zero_municipality_makes_no_catalog_requests(tmp_path):
    def forbidden(*args):
        raise AssertionError("zero municipality must not borrow a neighbouring store")
    result = await collect(inventory("1281"), set(), tmp_path / "zero", connector_factory=forbidden)
    assert result["stores"] == []
    assert result["source_fetch_mode"] == "no_external_price_calls"


@pytest.mark.asyncio
async def test_unapproved_store_rejected_before_transport_or_output(tmp_path):
    with pytest.raises(ValueError, match="verified municipality"):
        await collect(inventory(), {"3203"}, tmp_path / "invalid")
    assert not (tmp_path / "invalid").exists()


@pytest.mark.asyncio
async def test_municipal_connector_does_not_call_legacy_locality_discovery():
    class Client:
        async def fetch_stores(self):
            raise AssertionError("municipal inventory is already source bound")
        async def aclose(self):
            pass
    result = inventory()
    connector = MunicipalCityGrossConnector(result, "3211", client=Client())
    area = GeographicArea.model_validate(result["area"])
    raw = await connector.fetch_stores(area)
    stores = connector.parse_stores(raw, ["unused", "unused"], area)
    assert [s.external_id for s in stores] == ["3211"]
    assert stores[0].coverage.value == "full_online_catalog"
    wrong = GeographicArea(city="Lund", mode="municipality", municipality_code="1281")
    with pytest.raises(ValueError, match="differs"):
        await connector.fetch_stores(wrong)


@pytest.mark.asyncio
async def test_collection_fetch_failure_retains_store_and_no_active_own(tmp_path):
    from grocery_data.app.connectors.base import ConnectorFetchError
    from grocery_data.tests.test_citygross_full_acceptance import FullFixtureCityGrossClient

    class FailedClient(FullFixtureCityGrossClient):
        async def fetch_catalog(self, store):
            raise ConnectorFetchError("injected failure", partial_batch=RawBatch(chain="citygross", documents=()))

    def factory(inv, store_id):
        return MunicipalCityGrossConnector(inv, store_id, client=FailedClient(()))

    result = await collect(inventory(), {"3211"}, tmp_path / "failed", connector_factory=factory)
    row = result["stores"][0]
    assert row["store_id"] == "3211" and row["status"] == "failed"
    assert row["error_type"] == "ConnectorFetchError" and row["own"] == 0
    assert row["retrieved_products"] == 0
    assert Path(row["resolved_database"]).exists()


@pytest.mark.asyncio
async def test_partial_fetch_failure_qualifies_only_retained_campaign_rows(tmp_path):
    import sqlite3

    from grocery_data.app.connectors.base import ConnectorFetchError
    from grocery_data.tests.test_citygross_full_acceptance import FullFixtureCityGrossClient
    from grocery_data.tests.test_citygross_offer_semantics import OBSERVED, evidence

    _, raw = evidence()

    class PartialClient(FullFixtureCityGrossClient):
        async def fetch_catalog(self, store):
            raise ConnectorFetchError("injected page-two failure", partial_batch=raw)

    def factory(inv, store_id):
        return MunicipalCityGrossConnector(inv, store_id, client=PartialClient(()))

    result = await collect(inventory(), {"3211"}, tmp_path / "partial", connector_factory=factory)
    row = result["stores"][0]
    assert row["status"] == "success" and row["coverage"] == "offers_only"
    assert row["full_catalog_outcome"]["status"] == "failed"
    assert row["full_catalog_outcome"]["error_type"] == "ConnectorFetchError"
    assert row["own"] == row["approved_products"] == 1
    assert row["quarantine_count"] == 1 and row["retrieved_products"] == 2
    assert row["observed_at"] == OBSERVED.isoformat(timespec="microseconds")
    assert row["price_channel"] == "online_store"
    assert row["source_fetch_mode"] == "retained_pages_without_new_network"
    with sqlite3.connect(row["resolved_database"]) as db:
        stored = db.execute("SELECT coverage,price_context_type,physical_store_external_id FROM stores").fetchone()
        assert stored == ("offers_only", "online_store", "169")
    assert row["windows"] == [{"valid_from": "2026-05-04", "valid_to": "2026-08-30"}]
