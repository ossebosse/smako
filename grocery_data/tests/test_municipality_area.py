from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import Chain, GeographicArea, RawBatch, RawFetch
from grocery_data.app.services.area_membership import assess_area
from grocery_data.app.services.ica_area_offers import offer_store_proposal

FIXTURES = Path(__file__).parent / "fixtures/municipality"


def stores(code):
    raw = RawFetch(chain=Chain.ICA,kind="stores_page",method="GET",
                   url="https://www.ica.se/butiker/" + ("lund/" if code=="1281" else "malmo/"),
                   fetched_at=datetime(2026,9,20,14,50,tzinfo=UTC),http_status=200,
                   content_type="application/json",connector_version="ica-v2",
                   payload=(FIXTURES/(code+".json")).read_bytes())
    return IcaParser().parse_physical_stores(RawBatch(chain=Chain.ICA,documents=(raw,)),
              ["fixture"],GeographicArea(city="Lund"),include_outside=True)


def test_lund_administrative_field_keeps_other_localities():
    area=GeographicArea(city="Lund",mode="municipality",municipality_code="1281")
    for store in stores("1281"):
        assert assess_area(store,area)["status"]=="inside"
        if store.city in {"Genarp","Veberöd","Södra Sandby"}:
            assert assess_area(store,GeographicArea(city="Lund"))["status"]=="outside"
        assert assess_area(store,area)["evidence"]["source_sha256"]
    assert area.area_key != GeographicArea(city="Lund").area_key


def test_malmo_map_projection_without_municipality_is_unknown_not_excluded():
    area=GeographicArea(city="Malmö",mode="municipality",municipality_code="1280")
    parsed=stores("1280")
    missing=[s for s in parsed if not s.source_fields.get("municipality")]
    assert missing
    assert all(assess_area(s,area)["status"]=="unknown" for s in missing)
    known=[s for s in parsed if s.source_fields.get("municipality")=="Malmö"]
    assert known and all(assess_area(s,area)["status"]=="inside" for s in known)


@pytest.mark.parametrize("chain",list(Chain))
def test_shared_rule_does_not_depend_on_chain_or_user_postcode(chain):
    store=stores("1281")[0]
    fields=dict(store.source_fields)
    fields["address_municipality_evidence"]={**fields["address_municipality_evidence"],"chain":chain.value}
    store=store.model_copy(update={"chain":chain,"source_fields":fields})
    area=GeographicArea(city="Lund",mode="municipality",municipality_code="1281",postal_codes=("99999",))
    assert assess_area(store,area)["status"]=="inside"


@pytest.mark.parametrize("change",[{"store_id":"wrong"},{"address":"wrong"},{"source_sha256":"bad"},
    {"observed_at":"2026-09-20"},{"municipality_code":"1280"},{"municipality_name":"Limhamn"}])
def test_invalid_or_conflicting_evidence_fails_closed(change):
    store=stores("1281")[0]; fields=dict(store.source_fields)
    fields["address_municipality_evidence"]={**fields["address_municipality_evidence"],**change}
    changed=store.model_copy(update={"source_fields":fields})
    assert assess_area(changed,GeographicArea(city="Lund",mode="municipality",municipality_code="1281"))["status"]=="unknown"


def test_code_and_mode_required_and_no_cross_municipality_match():
    for kwargs in ({"city":"Lund","municipality_code":"1281"},
                   {"city":"Lund","mode":"municipality"},
                   {"city":"Lund","mode":"municipality","municipality_code":"1280"},
                   {"city":"Lund","mode":"municipality","municipality_code":"9999"}):
        with pytest.raises(ValidationError): GeographicArea(**kwargs)
    assert assess_area(stores("1281")[0],GeographicArea(city="Malmö",mode="municipality",municipality_code="1280"))["status"]=="outside"


def test_locator_count_does_not_approve_municipality_activation():
    proposal=offer_store_proposal({"area":{"mode":"municipality"},"inventory":{"complete":True},
             "stores":[{"ica_account_id":"1004598","area_membership":"inside", "area_reason":"verified_address_municipality_matches"}]})
    assert not proposal["inventory_approved"]
    assert proposal["ica_offer_store_ids"]==[]
    assert not proposal["production_activation"]


@pytest.mark.asyncio
async def test_real_missing_localities_enriched_without_url_inference(tmp_path):
    from grocery_data.app.services.ica_area_offers import enrich_municipality_addresses

    class SavedConnector:
        parser = IcaParser()
        def __init__(self):
            self.calls = []

        async def fetch_physical_stores(self, area):
            self.calls.append(area.city)
            index = ["Bunkeflostrand", "Limhamn", "Oxie"].index(area.city)
            raw = RawFetch(chain=Chain.ICA, kind="stores_page", method="GET",
                url=f"https://www.ica.se/butiker/{area.city.lower()}/",
                fetched_at=datetime(2026, 9, 20, 14, 49, tzinfo=UTC), http_status=200,
                content_type="application/json", connector_version="ica-v2",
                payload=(FIXTURES/f"municipality-address-{index}-0.json").read_bytes())
            return RawBatch(chain=Chain.ICA, documents=(raw,))

    connector = SavedConnector()
    area = GeographicArea(city="Malmö", mode="municipality", municipality_code="1280")
    before = stores("1280")
    after, evidence = await enrich_municipality_addresses(before, area, connector, tmp_path)
    assert len(after) == len(before)
    assert len(connector.calls) == 3
    improved = [s for s in after if s.external_id in {"1003660", "1004076", "1004140", "1003682"}]
    assert len(improved) == 4
    assert all(assess_area(s, area)["status"] == "inside" for s in improved)
    assert evidence["unqueried"] == []
    # Toftanäs's URL/address locality alone does not establish municipal membership.
    toftanas = next(s for s in after if s.external_id == "1003807")
    assert assess_area(toftanas, area)["status"] == "unknown"


@pytest.mark.asyncio
async def test_enrichment_error_stops_queries_and_keeps_unknown_rows(tmp_path):
    from grocery_data.app.services.ica_area_offers import enrich_municipality_addresses

    class FailedConnector:
        async def fetch_physical_stores(self, area):
            raise RuntimeError("source unavailable")

    before = stores("1280")
    after, evidence = await enrich_municipality_addresses(before,
        GeographicArea(city="Malmö",mode="municipality",municipality_code="1280"),
        FailedConnector(), tmp_path)
    assert after == before
    assert len(evidence["queries"]) == 1
    assert evidence["queries"][0]["status"] == "error"
    assert len(evidence["unqueried"]) == 2


@pytest.mark.asyncio
async def test_previous_area_cannot_silently_expand_existing_plan_scope(tmp_path):
    from grocery_data.app.services.ica_area_offers import collect_area_offers
    with pytest.raises(ValueError, match="different geographic modes"):
        await collect_area_offers(GeographicArea(city="Lund",mode="municipality",municipality_code="1281"),
            tmp_path/"unused", previous={"area":{"city":"Lund"}})
    assert not (tmp_path/"unused").exists()


def test_cross_query_evidence_requires_exact_store_address_and_keeps_observation():
    from grocery_data.app.services.area_membership import reuse_municipality_evidence
    area = GeographicArea(city="Malmö",mode="municipality",municipality_code="1280")
    lund = stores("1281")
    sparse = next(s for s in stores("1280") if s.external_id == "1004409")
    assert assess_area(sparse,area)["status"] == "unknown"
    enriched = reuse_municipality_evidence(sparse,lund,area)
    assert assess_area(enriched,area)["status"] == "outside"
    original = next(s for s in lund if s.external_id == sparse.external_id)
    assert enriched.source_fields["address_municipality_evidence"] == original.source_fields["address_municipality_evidence"]
    moved = sparse.model_copy(update={"address":"Different address"})
    assert assess_area(reuse_municipality_evidence(moved,lund,area),area)["status"] == "unknown"


def test_conflicting_municipalities_are_not_silently_overwritten():
    from grocery_data.app.services.area_membership import reuse_municipality_evidence
    area = GeographicArea(city="Lund",mode="municipality",municipality_code="1281")
    original = stores("1281")[0]
    fields = dict(original.source_fields)
    fields["address_municipality_evidence"] = {**fields["address_municipality_evidence"],"municipality_name":"Malmö"}
    other = original.model_copy(update={"source_fields":fields})
    assert assess_area(reuse_municipality_evidence(original,[other],area),area)["reason"] == "conflicting_verified_municipality_addresses"
