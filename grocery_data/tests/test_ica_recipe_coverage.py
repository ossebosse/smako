from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from grocery_data.app.connectors.ica.discovery import DiscoveryPageResult
from grocery_data.app.domain import IcaDiscoverySource, IcaRegistryObservation
from grocery_data.app.services.ica_query_enrichment import ICAQueryEnrichmentService
from grocery_data.app.services.ica_recipe_coverage import (
    RECIPE_QUERY_ALIASES,
    RECIPE_RELEVANT_INGREDIENTS,
    CoverageFailureReason,
    RecipeQueryCoverageBenchmark,
    RouteYieldReport,
)
from grocery_data.app.services.ica_registry import IcaProductRegistry
from grocery_data.app.storage import (
    IcaEnrichmentRunModel,
    StoreModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)

NOW = datetime(2026, 8, 21, 12, tzinfo=UTC)


def _registry():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    session = create_session_factory(engine)()
    store = StoreModel(
        chain="ica",
        external_id="1088004",
        name="Gunnesbo",
        coverage="offers_only",
        raw_reference="raw:store",
    )
    session.add(store)
    session.flush()
    return session, store, IcaProductRegistry(session)


def _observation(product_id: str, food: str, **changes) -> IcaRegistryObservation:
    values = {
        "external_product_id": product_id,
        "store_external_id": "1088004",
        "source": IcaDiscoverySource.SEARCH_PAGE,
        "source_page": f"/search?q={food}",
        "observed_at": NOW,
        "name": food,
        "brand": "ICA",
        "canonical_food": food,
        "sale_price": Decimal(10),
        "sale_model": "fixed_package",
        "semantic_confidence": "high",
        "quantity_confidence": "exact",
    }
    values.update(changes)
    return IcaRegistryObservation(**values)


def test_recipe_relevant_set_reuses_small_explainable_alias_lists() -> None:
    assert 40 <= len(RECIPE_RELEVANT_INGREDIENTS) <= 60
    assert RECIPE_QUERY_ALIASES["chicken_meat"] == (
        "kyckling",
        "kycklingfilé",
        "kycklinglår",
    )
    assert all(1 <= len(item.queries) <= 3 for item in RECIPE_RELEVANT_INGREDIENTS)


def test_coverage_levels_and_latest_observation_are_product_based() -> None:
    session, store, registry = _registry()
    for index in range(5):
        registry.ingest(_observation(str(index), "pasta"))
    # A second historical price must not inflate candidate count.
    registry.ingest(
        _observation("0", "pasta", observed_at=NOW - timedelta(days=2), sale_price=Decimal(12))
    )
    report = RecipeQueryCoverageBenchmark(session).run(
        store.id,
        ingredients=(RECIPE_RELEVANT_INGREDIENTS[8],),
        now=NOW,
    )
    row = report.ingredients[0]
    assert row.known_candidates == 5
    assert row.fresh_candidates == 5
    assert row.usable_candidates == 5
    assert row.coverage_level == 3


def test_failure_reasons_distinguish_absent_stale_and_unknown_quantity() -> None:
    session, store, registry = _registry()
    registry.ingest(
        _observation(
            "milk",
            "milk",
            observed_at=NOW - timedelta(days=8),
        )
    )
    registry.ingest(_observation("egg", "eggs", quantity_confidence="unknown"))
    selected = (
        RECIPE_RELEVANT_INGREDIENTS[0],
        RECIPE_RELEVANT_INGREDIENTS[5],
        RECIPE_RELEVANT_INGREDIENTS[7],
    )
    report = RecipeQueryCoverageBenchmark(session).run(
        store.id,
        ingredients=selected,
        now=NOW,
    )
    by_name = {row.ingredient: row for row in report.ingredients}
    assert by_name["milk"].failure_reasons == [CoverageFailureReason.STALE_PRICE]
    assert by_name["eggs"].failure_reasons == [CoverageFailureReason.UNKNOWN_QUANTITY]
    assert by_name["ris"].failure_reasons == [CoverageFailureReason.NO_PRODUCT_IDS]


def test_route_yield_rates_are_safe_for_zero_and_nonzero_pages() -> None:
    report = RouteYieldReport(
        route_type="search_ssr",
        pages=10,
        product_ids=204,
        full_products=96,
        priced_products=91,
    )
    assert report.ids_per_page == 20.4
    assert report.priced_products_per_page == 9.1
    assert (
        RouteYieldReport(
            route_type="offers", pages=0, product_ids=0, full_products=0, priced_products=0
        ).priced_products_per_page
        == 0
    )


@pytest.mark.asyncio
async def test_query_enrichment_merges_safe_page_then_stops_on_challenge() -> None:
    session, store, _ = _registry()

    class Navigator:
        def __init__(self) -> None:
            self.calls = 0

        async def navigate(self, page_identifier: str) -> DiscoveryPageResult:
            self.calls += 1
            if self.calls == 2:
                return DiscoveryPageResult(
                    page_identifier=page_identifier,
                    product_ids=frozenset(),
                    decorated_products=0,
                    price_observations=0,
                    challenge_detected=True,
                )
            observation = _observation("milk-safe", "milk")
            return DiscoveryPageResult(
                page_identifier=page_identifier,
                product_ids=frozenset({"milk-safe"}),
                decorated_products=1,
                price_observations=1,
                observations=(observation,),
            )

    navigator = Navigator()
    result = await ICAQueryEnrichmentService(session, navigator).enrich(
        store.id, ["milk", "eggs", "pasta"]
    )
    assert result.challenge_encountered
    assert result.pages_visited == 2
    assert result.observations_merged == 1
    assert navigator.calls == 2
    persisted = session.query(IcaEnrichmentRunModel).one()
    assert persisted.status == "degraded"
    assert persisted.challenge_encountered is True
    assert persisted.pages_visited == 2
