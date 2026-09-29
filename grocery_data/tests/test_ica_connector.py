from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.ica import IcaConnector
from grocery_data.app.connectors.ica.client import IcaClient
from grocery_data.app.connectors.ica.models import IcaSchemaError, initial_data_from_html
from grocery_data.app.connectors.ica.parser import IcaParser, parse_comparison, parse_package
from grocery_data.app.connectors.registry import SOURCE_COVERAGE, ConnectorRegistry
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    PromotionType,
    RawBatch,
    RawFetch,
)
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import (
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "ica" / "fixtures"


def _fetch(name: str, kind: str, *, store_id: str | None = None) -> RawFetch:
    return RawFetch(
        chain=Chain.ICA,
        store_external_id=store_id,
        kind=kind,
        method="GET",
        url=f"https://www.ica.se/{name}",
        fetched_at=datetime(2026, 8, 21, tzinfo=UTC),
        http_status=200,
        content_type="text/html",
        payload=(FIXTURES / name).read_bytes(),
        connector_version="ica-v1",
    )


_FORBIDDEN_RUNTIME_KEY_PARTS = {
    "accesstoken",
    "authorization",
    "cookie",
    "credentials",
    "i3sessionid",
    "localstorage",
    "mapapikey",
    "publicaccesstoken",
    "sessionid",
    "sessionstorage",
    "storecookie",
}


def _with_runtime_material(payload: bytes) -> bytes:
    injected = (
        b'{"accessToken":"runtime-access","publicAccessToken":"runtime-public",'
        b'"sessionId":"runtime-session","i3SessionId":"runtime-i3",'
        b'"MAP_API_KEY":"runtime-map","storeCookie":"runtime-cookie",'
        b'"authorization":"runtime-auth","localStorage":{"token":"runtime-storage"},'
    )
    return payload.replace(b"window.__INITIAL_DATA__ = {", b"window.__INITIAL_DATA__ = " + injected)


def _assert_no_runtime_material(payload: bytes) -> None:
    assert b"runtime-" not in payload
    decoded = json.loads(payload)

    def visit(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                compact = "".join(character for character in key.casefold() if character.isalnum())
                assert not any(part in compact for part in _FORBIDDEN_RUNTIME_KEY_PARTS)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(decoded)


def test_initial_data_decoder_does_not_modify_quoted_undefined() -> None:
    payload = b'<script>window.__INITIAL_DATA__ = {"text":"undefined", "value":undefined};</script>'
    assert initial_data_from_html(payload) == {"text": "undefined", "value": None}


def test_store_fixture_is_public_offers_only() -> None:
    stores = IcaParser().parse_stores(
        RawBatch(chain=Chain.ICA, documents=(_fetch("stores_lund.html", "stores_page"),)),
        ["raw:stores"],
        GeographicArea(city="Lund"),
    )
    assert len(stores) == 1
    store = stores[0]
    assert store.external_id == "1088004"
    assert store.coverage == CoverageLevel.OFFERS_ONLY
    assert store.online_shopping is True
    assert store.source_fields["offers_url"].startswith("https://www.ica.se/erbjudanden/")


def test_store_parser_fails_closed_on_incomplete_filtered_page() -> None:
    payload = (
        b'<script>window.__INITIAL_DATA__ = {"resultStore":{"total":2,"storeCards":[]}};</script>'
    )
    raw = RawFetch(
        chain=Chain.ICA,
        kind="stores_page",
        method="GET",
        url="https://www.ica.se/stores",
        http_status=200,
        payload=payload,
        connector_version="ica-v1",
    )
    with pytest.raises(IcaSchemaError, match="incomplete"):
        IcaParser().parse_stores(
            RawBatch(chain=Chain.ICA, documents=(raw,)), ["raw"], GeographicArea(city="Lund")
        )


@pytest.mark.asyncio
async def test_physical_locator_uses_municipality_page_and_preserves_strict_locality() -> None:
    initial_data = {
        "resultStore": {
            "totalNrOfStores": 2,
            "storeCards": [
                {
                    "accountNumber": "1088004",
                    "storeId": "17883",
                    "storeName": "ICA Maxi Stormarknad Gunnesbo",
                    "onlineUrl": "/handla/ica-maxi-gunnesbo/",
                    "highlightUrls": {"offers": "/erbjudanden/maxi-gunnesbo/"},
                    "address": {
                        "street": "Traktorvägen 1-3",
                        "postalCode": "22660",
                        "city": "Lund",
                        "municipality": "Lund",
                        "coordinates": {
                            "latitude": 55.71647,
                            "longitude": 13.16357,
                        },
                    },
                },
                {
                    "accountNumber": "1003452",
                    "storeId": "2786",
                    "storeName": "ICA Nära Södra Sandby",
                    "address": {
                        "street": "Backgatan 2",
                        "postalCode": "24731",
                        "city": "Södra Sandby",
                        "municipality": "Lund",
                    },
                },
            ],
        }
    }
    requested_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_paths.append(request.url.path)
        payload = (
            "<script>window.__INITIAL_DATA__ = "
            + json.dumps(initial_data, ensure_ascii=False)
            + ";</script>"
        ).encode()
        return httpx.Response(200, content=payload, request=request)

    async with httpx.AsyncClient(
        base_url="https://www.ica.se",
        transport=httpx.MockTransport(handler),
    ) as http_client:
        connector = IcaConnector(client=IcaClient(client=http_client, requests_per_second=1000))
        raw = await connector.fetch_physical_stores(GeographicArea(city="Lund"))
        stores = connector.parse_physical_stores(
            raw,
            ["raw:physical-locator"],
            GeographicArea(city="Lund"),
        )

    assert requested_paths == ["/butiker/lund/"]
    assert len(stores) == 1
    assert stores[0].external_id == "1088004"
    assert stores[0].source_fields["store_id"] == "17883"
    assert stores[0].city == "Lund"
    assert stores[0].online_shopping is True
    assert stores[0].source_fields["official_physical_locator"] is True


def test_offers_fixture_preserves_multibuy_member_and_identity_uncertainty() -> None:
    parser = IcaParser()
    store = parser.parse_stores(
        RawBatch(chain=Chain.ICA, documents=(_fetch("stores_lund.html", "stores_page"),)),
        ["raw:stores"],
        GeographicArea(city="Lund"),
    )[0]
    result = parser.parse_catalog(
        RawBatch(
            chain=Chain.ICA,
            documents=(_fetch("offers.html", "offers_page", store_id=store.external_id),),
        ),
        ["raw:offers"],
        store,
    )
    assert not result.failures
    assert len(result.products) == 3
    tomato = result.products[0]
    assert tomato.gtin == "7318690123456"
    assert tomato.regular_price is None
    assert tomato.source_fields["price_evidence"]["reference_regular"] == "18.80"
    assert tomato.source_fields["price_evidence"]["reference_is_current_checkout"] is False
    assert tomato.package_quantity == Decimal(200)
    assert tomato.comparison_price == Decimal("62.50")
    assert tomato.offers[0].type == PromotionType.MULTIBUY
    assert tomato.offers[0].quantity == 2
    assert tomato.offers[0].price == Decimal(25)
    coconut = result.products[1]
    assert coconut.gtin is None  # an offer group with two variants is not one GTIN
    assert coconut.offers[0].member_only is True
    assert coconut.offers[0].type == PromotionType.MULTIBUY
    assert coconut.offers[0].price == Decimal(25)
    assert result.products[2].offers[0].type == PromotionType.PERCENT_DISCOUNT
    assert result.products[2].offers[0].price is None


def test_sanitized_real_offer_fixture_remains_offline_parser_complete() -> None:
    parser = IcaParser()
    store = parser.parse_stores(
        RawBatch(chain=Chain.ICA, documents=(_fetch("stores_lund.html", "stores_page"),)),
        ["raw:stores"],
        GeographicArea(city="Lund"),
    )[0]
    raw = RawFetch(
        chain=Chain.ICA,
        store_external_id=store.external_id,
        kind="offers_page",
        method="GET",
        url="https://www.ica.se/erbjudanden/public/",
        fetched_at=datetime(2026, 8, 21, tzinfo=UTC),
        http_status=200,
        content_type="application/json; profile=sanitized-offers_page",
        payload=(FIXTURES / "offers_sanitized.json").read_bytes(),
        connector_version="ica-v2",
    )

    result = parser.parse_catalog(
        RawBatch(chain=Chain.ICA, documents=(raw,)),
        ["raw:sanitized-offers"],
        store,
    )

    assert not result.failures
    assert [product.external_product_id for product in result.products] == [
        "offer-multi",
        "offer-member",
        "offer-percent",
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1 kg", (Decimal(1000), "g")),
        ("500 ml", (Decimal(500), "ml")),
        ("70-pack", (Decimal(70), "st")),
        ("400/240 g", (None, None)),
        ("400-500 g", (None, None)),
    ],
)
def test_package_parser_never_invents_quantity(
    text: str, expected: tuple[Decimal | None, str | None]
) -> None:
    assert parse_package(text) == expected


def test_comparison_price_is_not_package_quantity() -> None:
    assert parse_comparison("39:90/kg") == (Decimal("39.90"), "kg")
    assert parse_package("39:90/kg") == (None, None)


def test_explicit_ica_kg_offer_normalizes_as_sold_by_weight() -> None:
    parser = IcaParser()
    store = parser.parse_stores(
        RawBatch(chain=Chain.ICA, documents=(_fetch("stores_lund.html", "stores_page"),)),
        ["raw:stores"],
        GeographicArea(city="Lund"),
    )[0]
    parsed = parser.parse_catalog(
        RawBatch(
            chain=Chain.ICA,
            documents=(_fetch("sold_by_weight.html", "offers_page", store_id=store.external_id),),
        ),
        ["raw:weight"],
        store,
    )
    assert not parsed.failures
    source = parsed.products[0]
    assert source.sale_unit == "kg"
    assert source.package_quantity is None
    canonical = ProductNormalizer().normalize(source, parser_version=parser.parser_version)
    assert canonical.sale_model.value == "sold_by_weight"
    assert canonical.package_quantity is None
    assert canonical.unit_price == Decimal("69.90")


def test_registry_declares_ica_offers_only() -> None:
    descriptor = SOURCE_COVERAGE[Chain.ICA]
    assert descriptor.implemented is True
    assert descriptor.source_coverage == CoverageLevel.OFFERS_ONLY
    assert isinstance(ConnectorRegistry().create(Chain.ICA), IcaConnector)


@pytest.mark.asyncio
async def test_client_uses_only_public_city_and_offer_pages() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        fixture = "stores_lund.html" if "oppettider" in request.url.path else "offers.html"
        return httpx.Response(200, content=(FIXTURES / fixture).read_bytes(), request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://www.ica.se", follow_redirects=False
    ) as http:
        client = IcaClient(client=http, requests_per_second=1000)
        connector = IcaConnector(client=client)
        stores_raw = await connector.fetch_stores(GeographicArea(city="Lund"))
        _assert_no_runtime_material(stores_raw.documents[0].payload)
        stores = connector.parse_stores(stores_raw, ["raw:stores"], GeographicArea(city="Lund"))
        offers_raw = await connector.fetch_catalog(stores[0])
        _assert_no_runtime_material(offers_raw.documents[0].payload)
        assert offers_raw.transport.request_count == 1
    assert seen == [
        "/butiker/oppettider/handla-online/lund/",
        "/erbjudanden/maxi-ica-stormarknad-gunnesbo-lund-1088004/",
    ]


@pytest.mark.asyncio
async def test_ica_raw_collection_replays_without_network(tmp_path: Path) -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        fixture = "stores_lund.html" if "oppettider" in request.url.path else "offers.html"
        return httpx.Response(
            200,
            # Transport/LKG fixture needs payable offers, not an unsupported
            # percentage whose only price basis is a campaign reference.
            content=_with_runtime_material((FIXTURES / fixture).read_bytes().replace(
                b'"benefitType":"PERCOFF"', b'"benefitType":"FIXED"')),
            request=request,
        )

    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'ica.sqlite'}")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://www.ica.se"
    ) as http:
        connector = IcaConnector(client=IcaClient(client=http, requests_per_second=1000))
        collected = await GroceryCollector(factory, raw_store).collect_area(
            connector, GeographicArea(city="Lund")
        )
        assert collected.promoted is True
        assert collected.metrics.products_parsed == 3
        source_snapshot = collected.snapshot_id
        replayed = await DatabaseReplayService(factory, raw_store).replay_snapshot(
            connector, source_snapshot
        )
    stored_payloads = [path.read_bytes() for path in (tmp_path / "raw").rglob("*.json")]
    assert len(stored_payloads) == 2
    for payload in stored_payloads:
        _assert_no_runtime_material(payload)
    assert requests == 2
    assert replayed.network_requests == 0
    assert replayed.products_parsed == collected.metrics.products_parsed
    assert replayed.products_quarantined == 0
    assert replayed.promoted is False
    with session_scope(factory) as session:
        assert SnapshotRepository(session).active(Chain.ICA, scope_key="lund").id == source_snapshot
    engine.dispose()


@pytest.mark.asyncio
async def test_ica_access_challenge_persists_only_inert_diagnostic() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            content=b'<html><title>Access denied</title><script>accessToken="runtime-secret"</script>',
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://www.ica.se"
    ) as http:
        client = IcaClient(client=http, requests_per_second=1000)
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_stores(GeographicArea(city="Lund"))

    documents = caught.value.partial_batch.documents
    assert len(documents) == 1
    assert documents[0].content_type == "application/json; profile=transport-stop-diagnostic"
    _assert_no_runtime_material(documents[0].payload)
    assert documents[0].json_payload()["classification"] == "access_challenge"


@pytest.mark.asyncio
async def test_ica_schema_break_keeps_lkg_and_repairs_by_offline_replay(tmp_path: Path) -> None:
    broken = False
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if "oppettider" in request.url.path:
            body = (FIXTURES / "stores_lund.html").read_bytes()
        else:
            body = (FIXTURES / "offers.html").read_bytes()
            # Explicit synthetic payable amount for this LKG transport test.
            body = body.replace(b'"benefitType":"PERCOFF"', b'"benefitType":"FIXED"')
            if broken:
                body = body.replace(b'"weeklyOffers"', b'"weeklyDeals"')
        return httpx.Response(200, content=body, request=request)

    class RepairedIcaParser(IcaParser):
        parser_version = "ica-parser-v2-test-repair"

        def weekly_offer_rows(self, data):  # type: ignore[no-untyped-def]
            offers = data.get("offers")
            if isinstance(offers, dict) and isinstance(offers.get("weeklyDeals"), list):
                return offers["weeklyDeals"]
            return super().weekly_offer_rows(data)

    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'ica.sqlite'}")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://www.ica.se"
    ) as http:
        client = IcaClient(client=http, requests_per_second=1000)
        connector = IcaConnector(client=client)
        good = await GroceryCollector(factory, raw_store).collect_area(
            connector, GeographicArea(city="Lund")
        )
        broken = True
        failed = await GroceryCollector(factory, raw_store).collect_area(
            connector, GeographicArea(city="Lund")
        )
        assert good.promoted is True
        assert failed.promoted is False
        assert failed.status.value == "broken"
        with session_scope(factory) as session:
            assert (
                SnapshotRepository(session).active(Chain.ICA, scope_key="lund").id
                == good.snapshot_id
            )
        repaired = IcaConnector(client=client, parser=RepairedIcaParser())
        replay = await DatabaseReplayService(factory, raw_store).replay_snapshot(
            repaired,
            failed.snapshot_id,
            promote=True,
            accept_schema_change=True,
        )
    assert requests == 4
    assert replay.network_requests == 0
    assert replay.products_parsed == 3
    assert replay.promoted is True
    with session_scope(factory) as session:
        assert (
            SnapshotRepository(session).active(Chain.ICA, scope_key="lund").id
            == replay.replay_snapshot_id
        )
    engine.dispose()
