from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from grocery_data.app.connectors.ica.discovery import (
    DiscoveryBudget,
    DiscoveryPageResult,
    IcaDiscoveryPlanner,
)
from grocery_data.app.connectors.ica.models import IcaSchemaError
from grocery_data.app.connectors.ica.registry_parser import (
    declared_product_ids,
    extract_product_detail_jsonld,
    extract_registry_observations,
    has_access_challenge,
    initial_state_from_html,
)
from grocery_data.app.domain import IcaDiscoverySource, IcaRegistryObservation
from grocery_data.app.services.ica_registry import IcaProductRegistry
from grocery_data.app.storage import (
    IcaDiscoveryEventModel,
    IcaProductRegistryModel,
    StoreModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)

NOW = datetime(2026, 8, 21, 10, tzinfo=UTC)
FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "ica" / "fixtures"


def _session():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    session = factory()
    session.add(
        StoreModel(
            chain="ica",
            external_id="1000",
            name="ICA Test",
            coverage="offers_only",
            raw_reference="raw:test",
        )
    )
    session.commit()
    return session


def _observation(source: IcaDiscoverySource, **changes):
    values = {
        "external_product_id": "1007759",
        "store_external_id": "1000",
        "source": source,
        "source_page": "/search?q=pasta",
        "observed_at": NOW,
    }
    values.update(changes)
    return IcaRegistryObservation(**values)


def test_registry_deduplicates_identity_but_preserves_discovery_sources() -> None:
    session = _session()
    registry = IcaProductRegistry(session)
    registry.ingest(_observation(IcaDiscoverySource.SEARCH_PAGE))
    registry.ingest(_observation(IcaDiscoverySource.OFFERS_PAGE))
    session.commit()

    assert len(list(session.scalars(select(IcaProductRegistryModel)))) == 1
    assert {row.source for row in session.scalars(select(IcaDiscoveryEventModel))} == {
        "search_page",
        "offers_page",
    }


def test_registry_accumulates_and_upgrades_metadata_without_deleting_old_ids() -> None:
    session = _session()
    registry = IcaProductRegistry(session)
    product = registry.ingest(_observation(IcaDiscoverySource.CATEGORY_PAGE))
    registry.ingest(
        _observation(
            IcaDiscoverySource.SSR_INITIAL_STATE,
            name="Spirali 500g",
            brand="ICA",
            package_text="500 g",
            sale_price=Decimal("12.20"),
            comparison_price=Decimal("24.40"),
            comparison_unit="kg",
            sale_model="fixed_package",
            semantic_confidence="high",
            quantity_confidence="exact",
            canonical_food="pasta",
        )
    )
    session.commit()
    session.refresh(product)
    assert product.metadata_level == "full_metadata"
    assert product.name == "Spirali 500g"
    assert registry.stats(product_events_store_id(session))["known_products"] == 1


def product_events_store_id(session) -> str:
    return session.scalar(select(StoreModel.id))


def test_query_level_coverage_requires_every_fresh_safe_ingredient() -> None:
    session = _session()
    registry = IcaProductRegistry(session)
    for index, food in enumerate(("milk", "eggs", "pasta")):
        registry.ingest(
            _observation(
                IcaDiscoverySource.SSR_INITIAL_STATE,
                external_product_id=str(index),
                canonical_food=food,
                name=food,
                brand="brand",
                sale_price=Decimal(10),
                sale_model="fixed_package",
                semantic_confidence="high",
                quantity_confidence="exact",
            )
        )
    store_id = product_events_store_id(session)
    complete = registry.basket_coverage(store_id, ["milk", "eggs", "pasta"], now=NOW)
    incomplete = registry.basket_coverage(store_id, ["milk", "eggs", "pasta", "rice"], now=NOW)
    assert complete.complete_for_request
    assert not incomplete.complete_for_request
    assert incomplete.missing_ingredients == ["rice"]


def test_stale_price_is_not_query_complete() -> None:
    session = _session()
    registry = IcaProductRegistry(session)
    registry.ingest(
        _observation(
            IcaDiscoverySource.OFFERS_PAGE,
            canonical_food="milk",
            name="Milk",
            brand="Brand",
            sale_price=Decimal(10),
            sale_model="fixed_package",
            semantic_confidence="high",
            quantity_confidence="exact",
            observed_at=NOW - timedelta(days=8),
        )
    )
    result = registry.basket_coverage(product_events_store_id(session), ["milk"], now=NOW)
    assert not result.complete_for_request


def test_ssr_replay_extracts_declared_and_decorated_products_offline() -> None:
    state = {
        "catalogue": {"productIds": ["1007759", "other"], "totalCount": 2},
        "productEntities": {
            "1007759": {
                "retailerProductId": "1007759",
                "productName": "Spirali 500g",
                "brand": "ICA",
                "packageDescription": "500 g",
                "price": {"value": "12.20"},
                "comparisonPrice": {"value": "24.40", "unit": "kg"},
            }
        },
    }
    html = (
        "<script>window.__INITIAL_STATE__ = " + __import__("json").dumps(state) + ";</script>"
    ).encode()
    replayed = initial_state_from_html(html)
    assert declared_product_ids(replayed) == {"1007759", "other"}
    rows = extract_registry_observations(
        replayed,
        store_external_id="1000",
        source=IcaDiscoverySource.SEARCH_PAGE,
        source_page="/search?q=pasta",
        observed_at=NOW,
    )
    assert len(rows) == 1
    assert rows[0].sale_price == Decimal("12.20")


def test_challenge_detection_is_fail_closed() -> None:
    assert has_access_challenge(status=405, body="AWS WAF CAPTCHA")
    assert has_access_challenge(status=202, body="Human Verification")
    assert not has_access_challenge(status=200, body="ordinary catalog")


def test_sanitized_real_search_ssr_replays_nested_price_and_size_offline() -> None:
    state = initial_state_from_html((FIXTURES / "registry_search_ssr.html").read_bytes())
    rows = extract_registry_observations(
        state,
        store_external_id="1088004",
        source=IcaDiscoverySource.SEARCH_PAGE,
        source_page="/search?q=pasta",
        observed_at=NOW,
    )
    assert len(rows) == 1
    assert rows[0].external_product_id == "2142011"
    assert rows[0].sale_price == Decimal("25.45")
    assert rows[0].comparison_price == Decimal("63.63")
    assert rows[0].comparison_unit == "fop.price.per.kg"
    assert rows[0].package_text == "0.4kg"


def test_challenge_fixture_never_parses_as_product_data() -> None:
    body = (FIXTURES / "access_challenge.html").read_text(encoding="utf-8")
    assert has_access_challenge(status=202, body=body)
    with pytest.raises(IcaSchemaError, match="INITIAL_STATE"):
        initial_state_from_html(body.encode())


def test_sanitized_product_detail_jsonld_replays_one_priced_product() -> None:
    rows = extract_product_detail_jsonld(
        (FIXTURES / "registry_product_detail.html").read_bytes(),
        store_external_id="1088004",
        source_page="/products/margarin/2118486",
        observed_at=NOW,
    )
    assert len(rows) == 1
    assert rows[0].external_product_id == "2118486"
    assert rows[0].sale_price == Decimal("21.90")
    assert rows[0].availability == "InStock"
    assert rows[0].gtin is None


@pytest.mark.asyncio
async def test_discovery_planner_stops_immediately_on_challenge() -> None:
    class Navigator:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def navigate(self, page_identifier: str) -> DiscoveryPageResult:
            self.calls.append(page_identifier)
            return DiscoveryPageResult(
                page_identifier=page_identifier,
                product_ids=frozenset({page_identifier}),
                decorated_products=0,
                price_observations=0,
                challenge_detected=page_identifier == "second",
            )

    navigator = Navigator()
    result = await IcaDiscoveryPlanner(DiscoveryBudget(max_page_navigations=3)).run(
        navigator,
        category_pages=["first", "second", "must-not-run"],
        search_pages=[],
    )
    assert result.challenge_encountered
    assert result.stopped_early
    assert navigator.calls == ["first", "second"]
