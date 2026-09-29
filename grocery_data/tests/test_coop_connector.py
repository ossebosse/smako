from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors import SOURCE_COVERAGE, ConnectorRegistry
from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.coop import (
    CoopAccessChallenge,
    CoopBrowserOffersTransport,
    CoopClient,
    CoopConnector,
    CoopParser,
)
from grocery_data.app.connectors.coop.models import sanitized_store_page_html
from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    GeographicArea,
    PromotionType,
    RawBatch,
    RawFetch,
    SaleModel,
    SourceStore,
)
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import ReplayService

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "coop" / "fixtures"


def _store(*, online_context: bool = False) -> SourceStore:
    return SourceStore(
        chain=Chain.COOP,
        external_id="2696",
        name="Stora Coop Lund",
        city="Lund",
        coverage=CoverageLevel.OFFERS_ONLY,
        raw_reference="raw:store",
        source_fields={
            "store_page_path": "/butiker-erbjudanden/stora-coop/stora-coop-lund/",
            "disable_store_offers_flyer": False,
            "online_fulfilment_store_id": "lund-route" if online_context else None,
        },
    )


def _raw(name: str, *, kind: str = "rendered_catalog_page") -> RawBatch:
    return RawBatch(
        chain=Chain.COOP,
        documents=(
            RawFetch(
                chain=Chain.COOP,
                store_external_id="2696",
                kind=kind,
                method="GET",
                url="https://www.coop.se/handla/example-7340191165588",
                http_status=200,
                content_type="text/html",
                payload=(FIXTURES / name).read_bytes(),
                connector_version="coop-v1",
                page_number=1,
            ),
        ),
    )


def _parse(
    name: str,
    *,
    kind: str = "rendered_catalog_page",
    online: bool = False,
):
    return CoopParser().parse_catalog(
        _raw(name, kind=kind),
        [f"raw:{name}"],
        _store(online_context=online),
    )


def test_verified_bootstrap_scope_contains_all_discovered_lund_and_malmo_pages() -> None:
    assert len(CoopClient._VERIFIED_STORE_PAGES["lund"]) == 7
    assert len(CoopClient._VERIFIED_STORE_PAGES["malmö"]) == 13
    assert len(set(CoopClient._VERIFIED_STORE_PAGES["lund"])) == 7
    assert len(set(CoopClient._VERIFIED_STORE_PAGES["malmö"])) == 13


def test_store_parser_preserves_distinct_identifier_namespaces() -> None:
    source_payload = (FIXTURES / "store_lund.html").read_bytes() + (
        b'<script type="application/json">'
        b'{"subscriptionKey":"must-not-survive","apiKey":"also-secret"}</script>'
    )
    safe_payload = sanitized_store_page_html(source_payload)
    assert b"must-not-survive" not in safe_payload
    assert b"subscriptionKey" not in safe_payload
    raw = RawBatch(
        chain=Chain.COOP,
        documents=(
            RawFetch(
                chain=Chain.COOP,
                kind="store_page",
                method="GET",
                url="https://www.coop.se/butiker/stora-coop-lund",
                http_status=200,
                content_type="text/html",
                payload=safe_payload,
                connector_version="coop-v1",
            ),
        ),
    )

    stores = CoopParser().parse_stores(raw, ["raw:store"], GeographicArea(city="Lund"))

    assert len(stores) == 1
    store = stores[0]
    assert store.external_id == "2696"
    assert store.coverage == CoverageLevel.OFFERS_ONLY
    assert store.source_fields["ledger_account_number"] == 105760
    assert store.source_fields["organization_unit_id"] == 114
    assert store.source_fields["online_fulfilment_store_id"] is None
    assert store.address == "Traktorvägen 2"
    assert store.postal_code == "22660"
    assert store.city == "Lund"
    assert store.latitude == Decimal("55.7175812")
    assert store.longitude == Decimal("13.1644267")
    assert CoopConnector().catalog_eligible(store) is True


@pytest.mark.asyncio
async def test_store_transport_persists_only_allowlisted_replay_evidence() -> None:
    paths = CoopClient._VERIFIED_STORE_PAGES["lund"]

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        position = paths.index(path)
        store_id = 2696 + position
        name = f"Coop Lund {position + 1}"
        payload = (
            '<script type="application/json">'
            '{"subscriptionKey":"must-not-survive","nested":{"apiKey":"also-secret"}}'
            "</script>"
            '<script type="application/json">'
            f'{{"storeID":{store_id},"ledgerAccountNumber":105760,'
            f'"organizationUnitID":114,"name":"{name}","url":"{path}",'
            '"disableStoreOffersFlyer":false}'
            "</script>"
        )
        return httpx.Response(200, text=payload, headers={"content-type": "text/html"})

    http_client = httpx.AsyncClient(
        base_url="https://www.coop.se",
        transport=httpx.MockTransport(handler),
    )
    client = CoopClient(client=http_client, requests_per_second=10000)
    try:
        batch = await client.fetch_stores(GeographicArea(city="Lund"))
    finally:
        await http_client.aclose()

    assert len(batch.documents) == 7
    assert all(b"must-not-survive" not in document.payload for document in batch.documents)
    assert all(b"subscriptionKey" not in document.payload for document in batch.documents)
    references = [f"raw:{position}" for position in range(1, 8)]
    stores = CoopParser().parse_stores(batch, references, GeographicArea(city="Lund"))
    assert {store.external_id for store in stores} == {
        str(store_id) for store_id in range(2696, 2703)
    }
    assert {store.city for store in stores} == {"Lund"}
    assert {store.source_fields["city_evidence"] for store in stores} == {
        "verified_bootstrap_scope"
    }


def test_fixed_package_card_preserves_sale_and_comparison_price() -> None:
    result = _parse("fixed_package.html")
    assert result.failures == []
    source = result.products[0]
    assert source.external_product_id == "7340191165588"
    assert source.gtin is None
    assert source.sale_price == source.regular_price == Decimal("11.95")
    assert source.comparison_price == Decimal("23.90")
    assert source.comparison_unit == "kg"
    assert source.package_quantity == 500
    assert source.package_unit == "g"
    canonical = ProductNormalizer().normalize(source, parser_version=CoopParser.parser_version)
    assert canonical.sale_model == SaleModel.FIXED_PACKAGE
    assert canonical.quantity_confidence == Confidence.EXACT


def test_piece_product_remains_distinct_from_weight_comparison_price() -> None:
    source = _parse("piece_product.html").products[0]
    canonical = ProductNormalizer().normalize(source, parser_version=CoopParser.parser_version)
    assert source.package_quantity == 1
    assert source.package_unit == "st"
    assert canonical.sale_model == SaleModel.SOLD_BY_PIECE
    assert canonical.sale_price == Decimal("14.90")
    assert canonical.comparison_price == Decimal("87.65")


def test_variable_weight_member_offer_keeps_rate_and_piece_cost_separate() -> None:
    source = _parse("variable_weight.html", kind="rendered_offers_page").products[0]
    canonical = ProductNormalizer().normalize(source, parser_version=CoopParser.parser_version)
    assert source.sale_price is None and source.regular_price is None
    assert source.sale_unit == "kg"
    assert source.average_weight_kg == Decimal("1.1")
    assert canonical.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE
    assert canonical.quantity_confidence == Confidence.ESTIMATED
    assert canonical.unit_price is None
    assert canonical.sale_price is None
    assert source.offers[0].source_payload["comparison_reference_text"]
    assert source.offers[0].type == PromotionType.MEMBER_PRICE
    assert source.offers[0].price == Decimal("74.90")
    assert source.offers[0].member_only is True


def test_member_multibuy_is_never_flattened_to_unit_price() -> None:
    source = _parse("member_multibuy.html", kind="rendered_offers_page").products[0]
    offer = source.offers[0]
    assert source.sale_price is None and source.regular_price is None
    assert "74" in offer.source_payload["ordinary_reference_text"]
    assert source.member_price is None
    assert offer.type == PromotionType.MULTIBUY
    assert offer.quantity == 2
    assert offer.price == 105
    assert offer.member_only is True
    assert offer.max_quantity == 1


def test_single_member_price_remains_conditional() -> None:
    source = _parse("member_price.html", kind="rendered_offers_page").products[0]
    assert source.sale_price is None and source.regular_price is None
    assert source.member_price == 39
    assert source.offers[0].type == PromotionType.MEMBER_PRICE
    assert source.offers[0].member_only is True
    assert source.offers[0].max_quantity == 2


def test_live_button_offer_has_no_fabricated_product_identity() -> None:
    result = _parse("button_single_member.html", kind="rendered_offers_page")
    assert result.failures == []
    source = result.products[0]
    assert source.name == "Smör"
    assert source.external_product_id is None
    assert source.gtin is None
    assert source.package_quantity == 500
    assert source.package_unit == "g"
    assert source.member_price == 39
    assert source.source_fields["offer_group_identity_unresolved"] is True


def test_group_button_preserves_range_without_inventing_quantity() -> None:
    result = _parse("button_group_multibuy.html", kind="rendered_offers_page")
    assert result.failures == []
    source = result.products[0]
    assert source.name == "Bryggkaffe Mellanrost"
    assert source.brand == "Arvid Nordquist"
    assert source.package_text == "425-500 g"
    assert source.package_quantity is None
    assert source.package_unit is None
    assert source.source_fields["offer_group_count"] == 9
    assert source.offers[0].type == PromotionType.MULTIBUY
    assert source.offers[0].quantity == 2
    assert source.offers[0].price == 105
    canonical = ProductNormalizer().normalize(source, parser_version=CoopParser.parser_version)
    assert canonical.sale_model == SaleModel.UNKNOWN
    assert canonical.quantity_confidence == Confidence.UNKNOWN


def test_live_separate_member_marker_and_value_are_coalesced() -> None:
    result = _parse("live_separate_member.html", kind="rendered_offers_page")
    assert result.failures == []
    assert len(result.products) == 2
    tomato = next(product for product in result.products if product.name == "Fantasticatomater")
    halloumi = next(product for product in result.products if product.name == "Halloumi")
    assert tomato.member_price == 29
    assert tomato.comparison_price == Decimal("62.50")
    assert tomato.comparison_unit == "kg"
    assert tomato.source_fields["offer_group_count"] == 2
    assert halloumi.offers[0].type == PromotionType.MULTIBUY
    assert halloumi.offers[0].quantity == 3
    assert halloumi.offers[0].price == 69


def test_live_weekly_tip_drops_unknown_comparison_unit_without_quarantine() -> None:
    result = _parse("live_weekly_tip.html", kind="rendered_offers_page")
    assert result.failures == []
    source = result.products[0]
    assert source.name == "Maskindisktabletter"
    assert source.comparison_price is None
    assert source.comparison_unit is None
    assert source.offers[0].type == PromotionType.SALE_PRICE
    assert source.offers[0].price == 99
    assert source.offers[0].source_payload["comparison_price"] is None
    assert source.offers[0].source_payload["comparison_unit"] is None


def test_live_circa_is_estimated_while_range_remains_unknown() -> None:
    result = _parse("live_circa_and_range.html", kind="rendered_offers_page")
    assert result.failures == []
    circa = next(product for product in result.products if product.name == "Grillkryddad karré")
    ranged = next(product for product in result.products if product.name == "Fläskytterfilé")
    assert circa.package_quantity == 600
    assert circa.package_unit == "g"
    assert circa.source_fields["package_approximate"] is True
    assert ranged.package_text == "mellan cirka 850 till 900 gram"
    assert ranged.package_quantity is None
    assert ranged.package_unit is None
    canonical = ProductNormalizer().normalize(ranged, parser_version=CoopParser.parser_version)
    assert canonical.sale_model == SaleModel.UNKNOWN
    assert canonical.quantity_confidence == Confidence.UNKNOWN


def test_live_max_quantity_supports_st_styck_and_kop() -> None:
    result = _parse("live_max_forms.html", kind="rendered_offers_page")
    assert result.failures == []
    assert sorted(product.offers[0].max_quantity for product in result.products) == [1, 2, 3]


def test_unidentified_offer_groups_do_not_overwrite_each_other() -> None:
    documents = (
        _raw("button_single_member.html", kind="rendered_offers_page").documents[0],
        _raw("button_group_multibuy.html", kind="rendered_offers_page").documents[0],
    )
    result = CoopParser().parse_catalog(
        RawBatch(chain=Chain.COOP, documents=documents),
        ["raw:single", "raw:group"],
        _store(),
    )
    assert result.failures == []
    assert {product.name for product in result.products} == {"Smör", "Bryggkaffe Mellanrost"}


def test_live_numeric_field_boundary_preserves_multibuy_and_unknown_quantity() -> None:
    result = _parse("live_decimal_boundary.html", kind="rendered_offers_page")
    assert result.failures == []
    source = result.products[0]
    assert source.name == "Babyvård"
    assert source.brand == "Natusan"
    assert source.package_text == "mellan 200 till 300 milliliter"
    assert source.package_quantity is None
    assert source.comparison_price is None
    assert source.comparison_unit is None
    assert source.offers[0].type == PromotionType.MULTIBUY
    assert source.offers[0].quantity == 2
    assert source.offers[0].price == 59


def test_product_detail_requires_verified_online_context() -> None:
    rejected = _parse("product_detail.html", kind="product_detail")
    assert rejected.products == []
    assert "fulfilment-store context" in rejected.failures[0].error_message

    accepted = _parse("product_detail.html", kind="product_detail", online=True)
    source = accepted.products[0]
    assert source.gtin == "7340191165588"
    assert source.package_quantity == 500
    assert source.package_unit == "g"
    assert source.sale_price == Decimal("11.95")


def test_numeric_sku_and_url_suffix_do_not_fabricate_gtin() -> None:
    source = _parse(
        "product_detail_sku_only.html",
        kind="product_detail",
        online=True,
    ).products[0]
    assert source.external_product_id == "7340191165588"
    assert source.gtin is None


def test_sitemap_is_identity_evidence_not_fabricated_priced_products() -> None:
    result = _parse("product_sitemap.xml", kind="product_sitemap")
    urls = CoopParser.sitemap_product_urls((FIXTURES / "product_sitemap.xml").read_bytes())
    assert len(urls) == 2
    assert result.products == []
    assert result.failures == []


def test_schema_break_is_quarantined() -> None:
    result = _parse("schema_changed.html")
    assert result.products == []
    assert len(result.failures) == 1


def test_rendered_offer_replays_without_network(tmp_path: Path) -> None:
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    batch = _raw("member_multibuy.html", kind="rendered_offers_page")
    records = raw_store.save_batch(batch, snapshot_id="coop-offers")

    replay = ReplayService(raw_store).replay_catalog(CoopConnector(), records, _store())

    assert replay.network_requests == 0
    assert len(replay.parsed.products) == 1
    assert replay.normalized[0].offers[0].quantity == 2


def test_browser_raw_sanitizer_drops_unapproved_fields() -> None:
    payload = CoopBrowserOffersTransport._sanitized_payload(
        [
            {
                "href": "/handla/varor/x/product-7340191165588",
                "ariaLabel": "Product, Coop, 500 g, Pris 10 kronor styck",
                "subscriptionKey": "must-not-survive",
            }
        ],
        declared_total=1,
        store=_store(),
    )
    assert b"must-not-survive" not in payload
    assert b"subscriptionKey" not in payload
    assert b"7340191165588" in payload
    assert b'"store_external_id":"2696"' in payload


def test_browser_json_envelope_replays_button_and_cross_checks_store() -> None:
    payload = CoopBrowserOffersTransport._sanitized_payload(
        [
            {
                "href": None,
                "ariaLabel": (
                    "Spara i lista, Smör, Valio, 500 g, Medlemspris 39 kronor styck, "
                    "Ordinarie pris 59 kronor och 57 öre styck"
                ),
            }
        ],
        declared_total=1,
        store=_store(),
    )
    document = (
        _raw("fixed_package.html", kind="rendered_offers_page")
        .documents[0]
        .model_copy(
            update={
                "content_type": "application/json; profile=rendered-offer-cards",
                "payload": payload,
            }
        )
    )
    result = CoopParser().parse_catalog(
        RawBatch(chain=Chain.COOP, documents=(document,)),
        ["raw:json-envelope"],
        _store(),
    )
    assert result.failures == []
    assert result.products[0].name == "Smör"

    wrong_store = _store().model_copy(update={"external_id": "different"})
    rejected = CoopParser().parse_catalog(
        RawBatch(chain=Chain.COOP, documents=(document,)),
        ["raw:json-envelope"],
        wrong_store,
    )
    assert rejected.products == []
    assert "store identity mismatch" in rejected.failures[0].error_message


def test_browser_json_envelope_fails_closed_on_incomplete_capture() -> None:
    payload = CoopBrowserOffersTransport._sanitized_payload(
        [
            {
                "href": None,
                "ariaLabel": "Spara i lista, Smör, Valio, 500 g, Pris 59 kronor per styck",
            }
        ],
        declared_total=1,
        store=_store(),
    ).replace(b'"declared_total":1', b'"declared_total":2')
    document = (
        _raw("fixed_package.html", kind="rendered_offers_page")
        .documents[0]
        .model_copy(
            update={
                "content_type": "application/json; profile=rendered-offer-cards",
                "payload": payload,
            }
        )
    )
    result = CoopParser().parse_catalog(
        RawBatch(chain=Chain.COOP, documents=(document,)),
        ["raw:incomplete-json-envelope"],
        _store(),
    )
    assert result.products == []
    assert "incomplete" in result.failures[0].error_message


class _FixtureOffersTransport:
    async def fetch(self, store: SourceStore) -> RawFetch:
        return (
            _raw("member_price.html", kind="rendered_offers_page")
            .documents[0]
            .model_copy(update={"store_external_id": store.external_id})
        )


class _ChallengeTransport:
    async def fetch(self, store: SourceStore) -> RawFetch:
        del store
        raise CoopAccessChallenge("Human Verification", status_code=403)


@pytest.mark.asyncio
async def test_client_wraps_rendered_offer_as_raw_first_batch() -> None:
    http_client = httpx.AsyncClient(
        base_url="https://www.coop.se",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    client = CoopClient(client=http_client, offers_transport=_FixtureOffersTransport())
    try:
        batch = await client.fetch_offers(_store())
    finally:
        await http_client.aclose()
    assert batch.documents[0].kind == "rendered_offers_page"
    assert batch.transport.request_count == 1


@pytest.mark.asyncio
async def test_access_challenge_stops_and_preserves_sanitized_diagnostic() -> None:
    http_client = httpx.AsyncClient(base_url="https://www.coop.se")
    client = CoopClient(client=http_client, offers_transport=_ChallengeTransport())
    try:
        with pytest.raises(ConnectorFetchError, match="ACCESS_CHALLENGE") as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()
    partial = caught.value.partial_batch
    assert len(partial.documents) == 1
    assert partial.documents[0].kind == "access_challenge"
    assert partial.documents[0].payload == b'{"reason":"access_challenge"}'


def test_registry_exposes_full_online_descriptor_but_keeps_offer_factory() -> None:
    descriptor = SOURCE_COVERAGE[Chain.COOP]
    assert descriptor.implemented is True
    assert descriptor.acceptance_contract_passed is True
    assert descriptor.missing_acceptance_checks == ()
    assert descriptor.source_coverage == CoverageLevel.FULL_ONLINE_CATALOG
    assert "online" in (descriptor.limitation or "").casefold()
    assert isinstance(ConnectorRegistry().create(Chain.COOP), CoopConnector)
