from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from grocery_data.app.services.catalog_recipe_coverage import (
    REPRESENTATIVE_RECIPE_BASKET,
    CatalogRecipeCoverageBenchmark,
)
from grocery_data.app.services.ica_recipe_coverage import (
    RECIPE_QUERY_ALIASES,
    RECIPE_RELEVANT_INGREDIENTS,
    CoverageFailureReason,
    RecipeRelevantIngredient,
)
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    ParserFailureModel,
    PriceObservationModel,
    ProductModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def _ingredients(*names: str) -> tuple[RecipeRelevantIngredient, ...]:
    by_name = {item.canonical: item for item in RECIPE_RELEVANT_INGREDIENTS}
    return tuple(by_name[name] for name in names)


def _database() -> tuple[Session, StoreModel, CatalogSnapshotModel, RawSnapshotModel]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    session = create_session_factory(engine)()
    store = StoreModel(
        id="store-3211",
        chain="citygross",
        external_id="3211",
        name="Malmö Hyllie",
        city="Malmö",
        coverage="partial_catalog",
        raw_reference="raw:stores#3211",
    )
    snapshot = CatalogSnapshotModel(
        id="candidate-snapshot",
        chain="citygross",
        scope_key="malmö",
        coverage="partial_catalog",
        state="parsed",
        is_active=False,
        connector_version="citygross-v1",
        parser_version="citygross-parser-v1",
        normalizer_version="product-normalizer-v2",
    )
    raw = RawSnapshotModel(
        id="raw-candidate",
        catalog_snapshot_id=snapshot.id,
        chain="citygross",
        store_external_id=store.external_id,
        kind="catalog_page",
        method="GET",
        url="https://public.example/products",
        query={"store": "3211"},
        fetched_at=NOW,
        http_status=200,
        content_type="application/json",
        payload_hash="a" * 64,
        payload_size=100,
        payload_location="raw/candidate.json",
        request_fingerprint="request-candidate",
        connector_version="citygross-v1",
    )
    session.add_all([store, snapshot, raw])
    session.flush()
    return session, store, snapshot, raw


def _add_candidate(
    session: Session,
    store: StoreModel,
    snapshot: CatalogSnapshotModel,
    raw: RawSnapshotModel,
    *,
    canonical_food: str,
    suffix: str,
    observed_at: datetime = NOW,
    sale_price: Decimal | None = Decimal(10),
    with_price_observation: bool = True,
    sale_model: str = "fixed_package",
    semantic_confidence: str = "high",
    quantity_confidence: str = "exact",
    quarantined: bool = False,
) -> ProductModel:
    raw_reference = f"raw:{raw.id}#items[{suffix}]"
    source = SourceProductModel(
        id=f"source-{suffix}",
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id=f"external-{suffix}",
        name=f"Product {suffix}",
        category_path=["Test"],
        sale_price=sale_price,
        raw_reference=raw_reference,
        fetched_at=observed_at,
        parser_version="test-parser",
        source_fields={},
        source_record_hash=f"hash-{suffix}",
    )
    product = ProductModel(
        id=f"product-{suffix}",
        source_product_id=source.id,
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        source_product_key=f"citygross:{store.external_id}:external-{suffix}",
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id=source.external_product_id,
        name=source.name,
        category_path=["Test"],
        canonical_food=canonical_food,
        semantic_confidence=semantic_confidence,
        sale_model=sale_model,
        quantity_confidence=quantity_confidence,
        sale_price=sale_price,
        raw_reference=raw_reference,
        parser_version="test-parser",
        normalizer_version="test-normalizer",
        observed_at=observed_at,
    )
    session.add(source)
    session.flush()
    session.add(product)
    session.flush()
    if with_price_observation:
        session.add(
            PriceObservationModel(
                id=f"price-{suffix}",
                catalog_snapshot_id=snapshot.id,
                product_id=product.id,
                source_product_id=source.id,
                store_id=store.id,
                raw_snapshot_id=raw.id,
                observed_at=observed_at,
                sale_price=sale_price,
            )
        )
    if quarantined:
        session.add(
            ParserFailureModel(
                id=f"failure-{suffix}",
                catalog_snapshot_id=snapshot.id,
                raw_snapshot_id=raw.id,
                chain=store.chain,
                store_external_id=store.external_id,
                raw_record_reference=raw_reference,
                error_code="invalid_price",
                error_message="test quarantine",
                parser_version="test-parser",
                failure_fingerprint=f"failure-fingerprint-{suffix}",
                sample={"external_product_id": source.external_product_id},
            )
        )
    session.flush()
    return product


def test_catalog_benchmark_reuses_exact_existing_ingredient_set_and_aliases() -> None:
    assert CatalogRecipeCoverageBenchmark.ingredient_set is RECIPE_RELEVANT_INGREDIENTS
    assert CatalogRecipeCoverageBenchmark.query_aliases is RECIPE_QUERY_ALIASES
    assert len(REPRESENTATIVE_RECIPE_BASKET) == 13
    assert set(REPRESENTATIVE_RECIPE_BASKET).issubset(RECIPE_QUERY_ALIASES)


def test_candidate_counts_and_levels_use_store_specific_price_rows() -> None:
    session, store, snapshot, raw = _database()
    for index in range(5):
        _add_candidate(
            session,
            store,
            snapshot,
            raw,
            canonical_food="pasta",
            suffix=f"pasta-{index}",
        )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="pasta",
        suffix="pasta-no-price",
        with_price_observation=False,
    )

    report = CatalogRecipeCoverageBenchmark(session).run(
        snapshot.id,
        store.id,
        ingredients=_ingredients("pasta"),
        representative_basket=("pasta",),
        now=NOW,
    )

    assert snapshot.is_active is False
    assert report.snapshot_id == snapshot.id
    row = report.ingredients[0]
    assert row.known_candidates == 6
    assert row.fresh_candidates == 5
    assert row.usable_candidates == 5
    assert row.coverage_level == 3
    assert report.at_least_one == 1
    assert report.at_least_three == 1
    assert report.at_least_five == 1
    assert report.representative_basket.complete_for_request is True


def test_failure_reasons_cover_price_freshness_quality_model_and_quarantine() -> None:
    session, store, snapshot, raw = _database()
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="cream",
        suffix="cream-no-price",
        with_price_observation=False,
    )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="eggs",
        suffix="eggs-stale",
        observed_at=NOW - timedelta(days=8),
    )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="ris",
        suffix="rice-model",
        sale_model="unknown",
    )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="pasta",
        suffix="pasta-quantity",
        quantity_confidence="unknown",
    )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="chicken_meat",
        suffix="chicken-semantic",
        semantic_confidence="low",
    )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="cheese",
        suffix="cheese-quarantine",
        quarantined=True,
    )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="butter",
        suffix="butter-zero",
        sale_price=Decimal(0),
    )
    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="tomato",
        suffix="tomato-future",
        observed_at=NOW + timedelta(days=1),
    )
    selected = _ingredients(
        "milk",
        "cream",
        "eggs",
        "ris",
        "pasta",
        "chicken_meat",
        "cheese",
        "butter",
        "tomato",
    )

    report = CatalogRecipeCoverageBenchmark(session).run(
        snapshot.id,
        store.id,
        ingredients=selected,
        representative_basket=tuple(item.canonical for item in selected),
        now=NOW,
    )
    by_name = {row.ingredient: row for row in report.ingredients}

    assert by_name["milk"].failure_reasons == [CoverageFailureReason.NO_PRODUCT_IDS]
    assert by_name["cream"].failure_reasons == [CoverageFailureReason.NO_STORE_PRICE]
    assert by_name["eggs"].failure_reasons == [CoverageFailureReason.STALE_PRICE]
    assert by_name["ris"].failure_reasons == [CoverageFailureReason.UNKNOWN_PURCHASE_MODEL]
    assert by_name["pasta"].failure_reasons == [CoverageFailureReason.UNKNOWN_QUANTITY]
    assert by_name["chicken_meat"].failure_reasons == [CoverageFailureReason.SEMANTIC_REJECTION]
    assert by_name["cheese"].failure_reasons == [CoverageFailureReason.QUARANTINED]
    assert by_name["butter"].failure_reasons == [CoverageFailureReason.NO_STORE_PRICE]
    assert by_name["tomato"].failure_reasons == [CoverageFailureReason.STALE_PRICE]
    assert report.representative_basket.complete_for_request is False
    assert set(report.representative_basket.failure_reasons) == {
        item.canonical for item in selected
    }


def test_default_thirteen_item_basket_reports_incomplete_then_complete() -> None:
    session, store, snapshot, raw = _database()
    for canonical in REPRESENTATIVE_RECIPE_BASKET:
        _add_candidate(
            session,
            store,
            snapshot,
            raw,
            canonical_food=canonical,
            suffix=f"basket-{canonical}",
            observed_at=(NOW - timedelta(days=8) if canonical == "red_lentils" else NOW),
        )

    benchmark = CatalogRecipeCoverageBenchmark(session)
    incomplete = benchmark.run(snapshot.id, store.id, now=NOW)
    basket = incomplete.representative_basket
    assert basket.requested_ingredients == 13
    assert basket.safely_priced_ingredients == 12
    assert basket.complete_for_request is False
    assert basket.missing_ingredients == ["red_lentils"]
    assert basket.failure_reasons["red_lentils"] == [CoverageFailureReason.STALE_PRICE]

    _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="red_lentils",
        suffix="basket-red-lentils-fresh",
    )
    complete = benchmark.run(snapshot.id, store.id, now=NOW).representative_basket
    assert complete.safely_priced_ingredients == 13
    assert complete.coverage_ratio == 1
    assert complete.complete_for_request is True
    assert complete.missing_ingredients == []
    assert complete.failure_reasons == {}


def test_other_store_prices_never_make_candidate_store_usable() -> None:
    session, store, snapshot, raw = _database()
    product = _add_candidate(
        session,
        store,
        snapshot,
        raw,
        canonical_food="milk",
        suffix="milk-wrong-store-price",
        with_price_observation=False,
    )
    other_store = StoreModel(
        id="store-3203",
        chain="citygross",
        external_id="3203",
        name="Malmö Stora Bernstorp",
        city="Malmö",
        coverage="partial_catalog",
        raw_reference="raw:stores#3203",
    )
    session.add(other_store)
    session.flush()
    source = session.get(SourceProductModel, product.source_product_id)
    assert source is not None
    session.add(
        PriceObservationModel(
            id="price-other-store",
            catalog_snapshot_id=snapshot.id,
            product_id=product.id,
            source_product_id=source.id,
            store_id=other_store.id,
            raw_snapshot_id=raw.id,
            observed_at=NOW,
            sale_price=Decimal(10),
        )
    )
    session.flush()

    report = CatalogRecipeCoverageBenchmark(session).run(
        snapshot.id,
        store.id,
        ingredients=_ingredients("milk"),
        representative_basket=("milk",),
        now=NOW,
    )
    row = report.ingredients[0]
    assert row.known_candidates == 1
    assert row.fresh_candidates == 0
    assert row.usable_candidates == 0
    assert row.failure_reasons == [CoverageFailureReason.NO_STORE_PRICE]


def test_benchmark_validates_candidate_lineage_and_inputs() -> None:
    session, store, snapshot, _ = _database()
    benchmark = CatalogRecipeCoverageBenchmark(session)
    with pytest.raises(LookupError, match="does not exist"):
        benchmark.run("missing", store.id, now=NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        benchmark.run(snapshot.id, store.id, now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError, match="RECIPE_RELEVANT_INGREDIENTS"):
        benchmark.run(
            snapshot.id,
            store.id,
            ingredients=(),
            representative_basket=("parallel-taxonomy-item",),
            now=NOW,
        )
