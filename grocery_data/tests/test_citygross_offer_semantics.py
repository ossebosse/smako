"""Explicit retained-source regressions, without live HTTP or refreshed clocks."""
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from grocery_data.app.connectors.citygross.parser import CityGrossParser
from grocery_data.app.connectors.citygross.row_approved_offers import (
    CityGrossRowApprovedOfferConnector,
)
from grocery_data.app.domain import GeographicArea, RawBatch, RawFetch, SourceStore
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import CatalogSnapshotModel, SourceProductModel

OBSERVED = datetime(2026, 8, 22, 12, tzinfo=UTC)
FIXTURE = (Path(__file__).parents[1] / "app/connectors/citygross/fixtures/catalog_samples.json")


def evidence(*, restriction=None, another_store=False):
    payload = json.loads(FIXTURE.read_bytes())
    pasta = next(r for r in payload["items"] if r["id"] == "101548710_ST")
    ordinary = next(r for r in payload["items"] if r["id"] == "101233933_ST")
    pasta["url"] = "/matvaror/skafferiet/pasta-ris-och-mos/test-pasta"
    pasta["maximumQuantity"] = 25
    prices = pasta["productStoreDetails"]["prices"]
    prices["activePromotion"] = prices["promotions"][0]
    if restriction:
        prices["activePromotion"].update(restriction)
    if another_store:
        pasta["productStoreDetails"]["id"] = "another"
    payload.update(items=[pasta, ordinary], pageSize=2, totalCount=2, totalPages=1)
    raw = RawBatch(chain="citygross", documents=(RawFetch(
        chain="citygross", store_external_id="3211", kind="catalog_page", method="GET",
        url="https://www.citygross.se/api/v1/Loop54/products",
        query={"store": "3211", "skip": "0", "take": "2"}, fetched_at=OBSERVED,
        http_status=200, content_type="application/json", payload=json.dumps(payload).encode(),
        connector_version="citygross-v1", page_number=0),))
    store = SourceStore(chain="citygross", external_id="3211", name="Malmö Hyllie",
        address="Hyllie Allé 3 C", city="Malmö", coverage="full_online_catalog",
        online_shopping=True, price_context_type="online_store", physical_store_external_id="169",
        raw_reference="fixture:official-register", source_fields={"site_id": "169",
            "store_number": "3211", "price_context_verified": True,
            "store_page_url": "https://www.citygross.se/butiker/malmo-hyllie"})
    return store, raw


def test_source_roles_restrictions_and_online_identity_survive_parser():
    store, raw = evidence()
    parsed = CityGrossParser().parse_catalog(raw, ["raw:retained"], store)
    assert not parsed.failures
    pasta = parsed.products[0]
    assert pasta.sale_price == pasta.regular_price == Decimal("14.1")
    assert pasta.offers[0].price == 50 and pasta.offers[0].quantity == 4
    assert pasta.offers[0].max_quantity is None  # 25 is not a discount-group cap.
    assert pasta.offers[0].source_payload["maximumQuantity"] == 25
    assert pasta.offers[0].source_payload["raw_promotion"]["maxAppliedPerReceipt"] == 0
    assert pasta.source_fields["source_channel"] == "online_price"
    assert pasta.source_fields["source_variant_id"] == pasta.external_product_id
    assert pasta.source_fields["raw_prices"]["ordinaryPrice"]["price"] == 14.1
    assert pasta.fetched_at == OBSERVED


@pytest.mark.parametrize("restriction", [
    {"minAmount": 300}, {"couponId": "private-coupon"},
    {"membersOnly": None}, {"maxAppliedPerReceipt": 2.5}, {"to": "unknown"},
])
def test_unsupported_campaign_conditions_remain_non_authoritative(restriction):
    store, raw = evidence(restriction=restriction)
    parsed = CityGrossParser().parse_catalog(raw, ["raw:retained"], store)
    assert not parsed.failures
    pasta = parsed.products[0]
    assert pasta.regular_price == pasta.sale_price == Decimal("14.1")
    assert pasta.offers[0].type.value == "other"
    assert pasta.offers[0].source_payload["purchase_blockers"]


async def test_partial_offers_use_normal_collector_without_full_catalog_claim(tmp_path):
    store, raw = evidence()
    connector = CityGrossRowApprovedOfferConnector(store=store, locator=raw, catalog=raw)
    engine = create_database_engine("sqlite:///" + str(tmp_path / "own.sqlite"))
    create_schema(engine)
    factory = create_session_factory(engine)
    collector = GroceryCollector(factory, FilesystemRawSnapshotStore(tmp_path / "raw"))
    result = await collector.collect_area(connector, GeographicArea(city="Malmö"),
        scope_key="municipality:citygross:3211:offer-rows")
    assert result.promoted
    assert result.metrics.products_parsed == 1
    assert result.metrics.products_quarantined == 1
    assert connector.row_acceptance["complete"] is False
    assert connector.row_acceptance["replayed_without_network"] is True
    assert connector.row_acceptance["full_parse"]["denominator"] == 2
    with session_scope(factory) as session:
        snapshot = session.get(CatalogSnapshotModel, result.snapshot_id)
        assert snapshot.coverage == "offers_only"
        row = session.scalar(select(SourceProductModel))
        assert row.fetched_at == OBSERVED
        assert row.sale_price is None and row.regular_price is None
        assert row.source_fields["catalog_ordinary_price_reference"] == "14.1"
        assert row.source_fields["maximumQuantity"] == 25
    engine.dispose()


@pytest.mark.parametrize("failure", ["store", "coupon", "mapping"])
def test_partial_offers_fail_closed_for_wrong_context_or_conditions(failure):
    store, raw = evidence(another_store=failure == "store",
                          restriction={"couponId": "private"} if failure == "coupon" else None)
    if failure == "mapping":
        store = store.model_copy(update={"source_fields": {**store.source_fields, "site_id": None}})
    connector = CityGrossRowApprovedOfferConnector(store=store, locator=raw, catalog=raw)
    parsed = connector.parse_catalog(raw, ["raw:retained"], connector.store)
    assert not parsed.products
    assert parsed.failures


async def test_actual_single_campaign_and_minimum_spend_through_own():
    from app.providers.own import OwnGroceryPriceProvider

    from grocery_data.app.normalization import ProductNormalizer

    path = Path(__file__).parent / "fixtures/citygross/municipal-promotion-evidence-20260923.json"
    retained = json.loads(path.read_bytes())["items"]
    store, _ = evidence()
    provider = OwnGroceryPriceProvider("http://isolated.invalid", use_member_prices=True)
    try:
        for identity, expected_sale, expected_offers in (
            ("100308301_ST", Decimal("39.95"), 1),
            ("101615621_ST", Decimal("99.95"), 0),
        ):
            captured = retained[identity]
            observed = datetime.strptime(captured["source_document"].split("_")[0],
                                         "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)
            failures = []
            source = CityGrossParser()._parse_product(captured["row"], store=store,
                reference="retained:" + captured["source_document"], fetched_at=observed,
                failures=failures)
            assert not failures
            assert source.sale_price == expected_sale
            normalized = ProductNormalizer().normalize(source, parser_version=CityGrossParser.parser_version)
            projection = {**normalized.model_dump(mode="json"),
                "store_id": store.external_id, "regular_price": source.regular_price,
                "member_price": source.member_price, "source_fields": source.source_fields,
                "promotions": [o.model_dump(mode="json") for o in source.offers]}
            product = provider._product_from_row(projection)
            assert product is not None
            assert product.effective_price == float(expected_sale)
            assert len(product.offers) == expected_offers
            if identity == "101615621_ST":
                assert product.member_price is None
                assert source.offers[0].source_payload["raw_promotion"]["minAmount"] == 300
                assert source.offers[0].type.value == "other"
            else:
                assert product.offers[0].valid_to.isoformat() == "2026-09-27"
                assert product.price == 47.95
    finally:
        await provider.aclose()
