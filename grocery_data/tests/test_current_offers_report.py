from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.domain.promotion_pricing import PromotionMechanism
from grocery_data.app.services.current_offers import (
    CurrentOffersReportService,
    calculate_offer_savings,
    classify_offer_validity,
    normalize_promotion_contract,
    resolve_store_aliases,
)
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
)

NOW = datetime(2026, 8, 30, 10, 30, tzinfo=UTC)
DEFAULT_VALID_FROM = date(2026, 8, 29)
DEFAULT_VALID_TO = date(2026, 8, 31)


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _seed_physical_store(
    session,  # type: ignore[no-untyped-def]
    *,
    identifier: str,
    chain: str,
    external_id: str,
    name: str,
    city: str = "Lund",
) -> PhysicalStoreModel:
    row = PhysicalStoreModel(
        id=identifier,
        chain=chain,
        external_store_id=external_id,
        external_store_aliases=[],
        name=name,
        city=city,
        official_source="fixture://official-store-registry",
        discovered_at=NOW,
        last_seen_at=NOW,
        is_active=True,
        lifecycle_state="active",
    )
    session.add(row)
    session.flush()
    return row


def _seed_context(
    session,  # type: ignore[no-untyped-def]
    *,
    physical: PhysicalStoreModel,
    context_external_id: str,
    grocery_context_id: str,
    context_name: str,
    observed_at: datetime = NOW - timedelta(hours=2),
    source_provider: str = "own",
    source_channel: str = "catalog",
    price_context_type: str = "online_store",
    coverage: str = "full_online_catalog",
    relation_type: str = "exact_store_online_context",
    offers_only: bool = False,
) -> tuple[StoreModel, CatalogSnapshotModel, RawSnapshotModel]:
    suffix = grocery_context_id.replace(":", "-")
    store = StoreModel(
        id=f"store-{suffix}",
        chain=physical.chain,
        external_id=context_external_id,
        name=context_name,
        city=physical.city,
        coverage=coverage,
        price_context_type=price_context_type,
        physical_store_external_id=physical.external_store_id,
        raw_reference="fixture://store-context",
        is_active=True,
        first_seen_at=observed_at,
        last_seen_at=observed_at,
    )
    session.add(store)
    session.flush()

    snapshot = CatalogSnapshotModel(
        id=f"snapshot-{suffix}",
        chain=physical.chain,
        scope_key=f"scope:{grocery_context_id}",
        coverage=coverage,
        state="promoted",
        is_active=True,
        connector_version="fixture-v1",
        parser_version="fixture-v1",
        normalizer_version="fixture-v1",
        created_at=observed_at,
        parsed_at=observed_at,
        validated_at=observed_at,
        health_checked_at=observed_at,
        promoted_at=observed_at,
    )
    session.add(snapshot)
    session.flush()

    raw = RawSnapshotModel(
        id=f"raw-{suffix}",
        catalog_snapshot_id=snapshot.id,
        chain=physical.chain,
        store_external_id=context_external_id,
        kind="fixture_offer_feed",
        method="GET",
        url="https://example.invalid/public-offers",
        query={},
        fetched_at=observed_at,
        http_status=200,
        content_type="application/json",
        payload_hash=(suffix + "a" * 64)[:64],
        payload_size=2,
        payload_location=f"fixture://raw/{suffix}",
        request_fingerprint=(suffix[::-1] + "b" * 64)[:64],
        connector_version="fixture-v1",
    )
    session.add(raw)
    session.flush()

    session.add(
        StoreContextLinkModel(
            id=f"link-{suffix}",
            physical_store_id=physical.id,
            grocery_context_id=grocery_context_id,
            source_provider=source_provider,
            source_channel=source_channel,
            local_store_id=store.id,
            grocery_context_name=context_name,
            price_context_type=price_context_type,
            coverage=coverage,
            relation_type=relation_type,
            confidence="exact",
            evidence="fixture exact registry identity",
            basket_eligible=not offers_only,
            offers_only=offers_only,
            snapshot_id=snapshot.id,
            observed_at=observed_at,
            linked_at=observed_at,
            last_verified_at=observed_at,
            is_active=True,
        )
    )
    session.flush()
    return store, snapshot, raw


def _seed_offer(
    session,  # type: ignore[no-untyped-def]
    *,
    store: StoreModel,
    snapshot: CatalogSnapshotModel,
    raw: RawSnapshotModel,
    key: str,
    product_name: str,
    regular_price: Decimal | None,
    offer_price: Decimal,
    promotion_type: str,
    member_only: bool = False,
    quantity: int | None = 1,
    valid_from: date | None = DEFAULT_VALID_FROM,
    valid_to: date | None = DEFAULT_VALID_TO,
    gtin: str | None = None,
    description: str | None = None,
    availability: str = "available",
) -> None:
    source = SourceProductModel(
        id=f"source-{key}",
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id=f"article-{key}",
        gtin=gtin,
        name=product_name,
        brand="Fixture Brand",
        category_path=["Fixture"],
        sale_price=offer_price,
        regular_price=regular_price,
        member_price=offer_price if member_only and quantity in {None, 1} else None,
        comparison_price=offer_price,
        comparison_unit="st",
        package_text="1 st",
        package_quantity=Decimal(1),
        package_unit="st",
        sale_unit="st",
        availability=availability,
        raw_reference=f"fixture://product/{key}",
        fetched_at=snapshot.promoted_at or snapshot.created_at,
        parser_version="fixture-v1",
        source_fields={},
        source_record_hash=(key + "c" * 64)[:64],
    )
    session.add(source)
    session.flush()

    product = ProductModel(
        id=f"product-{key}",
        source_product_id=source.id,
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        source_product_key=f"{store.chain}:{store.external_id}:{key}",
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id=source.external_product_id,
        gtin=gtin,
        name=product_name,
        brand=source.brand,
        category_path=source.category_path,
        canonical_food="fixture_food",
        semantic_confidence="high",
        sale_model="fixed_package",
        quantity_confidence="exact",
        package_quantity=Decimal(1),
        package_unit="st",
        usable_quantity=Decimal(1),
        usable_unit="st",
        sale_price=offer_price,
        sale_unit="st",
        comparison_price=offer_price,
        comparison_unit="st",
        availability=availability,
        raw_reference=source.raw_reference,
        parser_version="fixture-v1",
        normalizer_version="fixture-v1",
        observed_at=snapshot.promoted_at or snapshot.created_at,
    )
    session.add(product)
    session.flush()

    price = PriceObservationModel(
        id=f"price-{key}",
        catalog_snapshot_id=snapshot.id,
        product_id=product.id,
        source_product_id=source.id,
        store_id=store.id,
        raw_snapshot_id=raw.id,
        observed_at=snapshot.promoted_at or snapshot.created_at,
        currency="SEK",
        sale_price=offer_price,
        regular_price=regular_price,
        member_price=offer_price if member_only and quantity in {None, 1} else None,
        comparison_price=offer_price,
        comparison_unit="st",
        sale_unit="st",
    )
    session.add(price)
    session.flush()

    session.add(
        PromotionModel(
            id=f"promotion-{key}",
            catalog_snapshot_id=snapshot.id,
            source_product_id=source.id,
            product_id=product.id,
            store_id=store.id,
            raw_snapshot_id=raw.id,
            price_observation_id=price.id,
            offer_fingerprint=(key + "d" * 64)[:64],
            external_id=f"offer-{key}",
            type=promotion_type,
            valid_from=valid_from,
            valid_to=valid_to,
            price=offer_price,
            quantity=quantity,
            member_only=member_only,
            max_quantity=3,
            description=description or product_name,
            source_payload={"fixture": True},
            parser_version="fixture-v1",
        )
    )
    session.flush()


def test_offer_validity_is_inclusive_and_rejects_expired_and_future_rows() -> None:
    today = date(2026, 8, 30)

    assert classify_offer_validity(today, today, today, source_active=True) == (
        True,
        "verified_full_period",
    )
    assert classify_offer_validity(
        today - timedelta(days=2),
        today - timedelta(days=1),
        today,
    ) == (False, "verified_full_period")
    assert classify_offer_validity(
        today + timedelta(days=1),
        today + timedelta(days=2),
        today,
    ) == (False, "verified_full_period")


def test_active_source_without_full_period_is_included_with_lower_confidence() -> None:
    assert classify_offer_validity(None, None, NOW.date(), source_active=True) == (
        True,
        "source_active_without_full_period",
    )
    assert classify_offer_validity(None, None, NOW.date(), source_active=False) == (
        False,
        "period_incomplete",
    )


@pytest.mark.parametrize(
    ("member_only", "expected_eligibility", "expected_program"),
    (
        (False, "public", None),
        (True, "member", "Hemköp Klubb"),
    ),
)
def test_public_and_member_unit_sales_remain_distinct(
    member_only: bool,
    expected_eligibility: str,
    expected_program: str | None,
) -> None:
    contract = normalize_promotion_contract(
        chain="hemkop",
        promotion_type="member_price" if member_only else "sale_price",
        price=Decimal("19.90"),
        quantity=1,
        member_only=member_only,
        description="Medlemspris" if member_only else "Veckans pris",
    )

    assert contract.eligibility == expected_eligibility
    assert contract.mechanism is PromotionMechanism.SALE_PRICE
    assert contract.required_quantity == 1
    assert contract.offer_price == Decimal("19.90")
    assert contract.member_program == expected_program


@pytest.mark.parametrize(
    ("member_only", "expected_eligibility"),
    ((False, "public"), (True, "member")),
)
def test_public_and_member_multibuy_keep_compound_semantics(
    member_only: bool,
    expected_eligibility: str,
) -> None:
    contract = normalize_promotion_contract(
        chain="hemkop",
        promotion_type="multibuy",
        price=Decimal(30),
        quantity=3,
        member_only=member_only,
        description=("Medlem: 3 för 30 kr" if member_only else "3 för 30 kr"),
    )

    assert contract.eligibility == expected_eligibility
    assert contract.mechanism is PromotionMechanism.MULTIBUY
    assert contract.required_quantity == 3
    assert contract.multibuy_total == Decimal(30)
    assert contract.derived_unit_price == Decimal(10)
    if member_only:
        assert contract.member_program == "Hemköp Klubb"


def test_unit_sale_and_multibuy_savings_use_the_same_quantity_basis() -> None:
    unit = calculate_offer_savings(
        regular_price=Decimal("20.00"),
        offer_price=Decimal("15.00"),
        mechanism=PromotionMechanism.SALE_PRICE,
        required_quantity=1,
    )
    assert unit.amount == Decimal("5.00")
    assert unit.percent == Decimal("25.00")

    multi = calculate_offer_savings(
        regular_price=Decimal("12.90"),
        offer_price=Decimal("30.00"),
        mechanism=PromotionMechanism.MULTIBUY,
        required_quantity=3,
    )
    assert multi.amount == Decimal("8.70")
    assert multi.percent.quantize(Decimal("0.01")) == Decimal("22.48")
    assert multi.regular_qualifying_total == Decimal("38.70")


def test_savings_are_not_fabricated_without_regular_price_or_comparable_basis() -> None:
    missing = calculate_offer_savings(
        regular_price=None,
        offer_price=Decimal("10.00"),
        mechanism=PromotionMechanism.SALE_PRICE,
        required_quantity=1,
    )
    assert missing.amount is None
    assert missing.percent is None
    assert missing.exclusion_reason == "regular_price_missing"
    incompatible = calculate_offer_savings(
        regular_price=Decimal("20.00"),
        offer_price=Decimal("10.00"),
        mechanism=PromotionMechanism.SALE_PRICE,
        required_quantity=1,
        price_basis_compatible=False,
    )
    assert incompatible.amount is None
    assert incompatible.percent is None
    assert incompatible.exclusion_reason == "price_basis_not_comparable"


def test_registry_resolution_keeps_ica_malmborgs_ambiguity_visible(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        _seed_physical_store(
            session,
            identifier="physical:ica:clemenstorget",
            chain="ica",
            external_id="clemenstorget",
            name="ICA Supermarket Malmborgs Clemenstorget",
        )
        _seed_physical_store(
            session,
            identifier="physical:ica:tuna",
            chain="ica",
            external_id="tuna",
            name="ICA Supermarket Malmborgs Tuna",
        )

        [resolution] = resolve_store_aliases(
            session,
            city="Lund",
            aliases=("ICA Malmborgs Lund",),
        )

        assert resolution.status == "ambiguous"
        assert set(resolution.physical_store_ids) == {
            "physical:ica:clemenstorget",
            "physical:ica:tuna",
        }


def test_lidl_lund_expands_all_physical_stores_without_claiming_exact_store_price(
    storage,
) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        _seed_physical_store(
            session,
            identifier="physical:lidl:0163",
            chain="lidl",
            external_id="0163",
            name="Lidl Magistratsvägen 6",
        )
        _seed_physical_store(
            session,
            identifier="physical:lidl:0303",
            chain="lidl",
            external_id="0303",
            name="Lidl Åkerlund och Rausings väg 1",
        )

        [resolution] = resolve_store_aliases(
            session,
            city="Lund",
            aliases=("Lidl Lund",),
        )

        assert resolution.status == "expanded_area_alias"
        assert set(resolution.physical_store_ids) == {
            "physical:lidl:0163",
            "physical:lidl:0303",
        }
        assert resolution.message == "Samtliga fysiska Lidl-butiker i Lund inkluderades."


def test_lidl_offer_section_is_regional_and_not_mislabeled_store_specific(
    storage,
) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        first = _seed_physical_store(
            session,
            identifier="physical:lidl:0163",
            chain="lidl",
            external_id="0163",
            name="Lidl Magistratsvägen 6",
        )
        _seed_physical_store(
            session,
            identifier="physical:lidl:0303",
            chain="lidl",
            external_id="0303",
            name="Lidl Åkerlund och Rausings väg 1",
        )
        store, snapshot, raw = _seed_context(
            session,
            physical=first,
            context_external_id="sverige",
            grocery_context_id="own:lidl:sverige",
            context_name="Lidl Sverige",
            source_channel="offers",
            price_context_type="regional_offer",
            coverage="offers_only",
            relation_type="regional_offer_applies",
            offers_only=True,
        )
        _seed_offer(
            session,
            store=store,
            snapshot=snapshot,
            raw=raw,
            key="lidl-plus",
            product_name="Lidl Plus fixture",
            regular_price=Decimal(20),
            offer_price=Decimal(15),
            promotion_type="member_price",
            member_only=True,
            description="Med Lidl Plus",
        )

        report = CurrentOffersReportService(session, max_age_hours=24).build(
            city="Lund",
            store_aliases=("Lidl Lund",),
            now=NOW,
        )

        [section] = report.sections
        assert section.grocery_context_id == "own:lidl:sverige"
        assert section.physical_store_id is None
        assert set(section.applicable_physical_store_ids) == {
            "physical:lidl:0163",
            "physical:lidl:0303",
        }
        assert section.price_context_type == "regional_offer"
        assert "inte observerat hyllpris" in section.price_scope_label
        assert section.member_offer_count == 1
        assert section.offers[0].member_program == "Lidl Plus"


def test_service_keeps_public_member_and_multibuy_as_orthogonal_dimensions(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        physical = _seed_physical_store(
            session,
            identifier="physical:hemkop:4123",
            chain="hemkop",
            external_id="4123",
            name="Hemköp Lund Karhögstorg",
        )
        store, snapshot, raw = _seed_context(
            session,
            physical=physical,
            context_external_id="4123",
            grocery_context_id="own:hemkop:4123",
            context_name="Hemköp Karhögstorg Online",
        )
        _seed_offer(
            session,
            store=store,
            snapshot=snapshot,
            raw=raw,
            key="public-sale",
            product_name="Public sale",
            regular_price=Decimal(25),
            offer_price=Decimal(20),
            promotion_type="sale_price",
        )
        _seed_offer(
            session,
            store=store,
            snapshot=snapshot,
            raw=raw,
            key="member-sale",
            product_name="Member sale",
            regular_price=Decimal(25),
            offer_price=Decimal(18),
            promotion_type="member_price",
            member_only=True,
        )
        _seed_offer(
            session,
            store=store,
            snapshot=snapshot,
            raw=raw,
            key="public-multibuy",
            product_name="Public multibuy",
            regular_price=Decimal("12.90"),
            offer_price=Decimal(30),
            promotion_type="multibuy",
            quantity=3,
            description="3 för 30 kr",
        )
        _seed_offer(
            session,
            store=store,
            snapshot=snapshot,
            raw=raw,
            key="member-multibuy",
            product_name="Member multibuy",
            regular_price=Decimal("12.90"),
            offer_price=Decimal(30),
            promotion_type="multibuy",
            member_only=True,
            quantity=3,
            description="Medlem: 3 för 30 kr",
        )

        report = CurrentOffersReportService(session, max_age_hours=24).build(
            city="Lund",
            store_aliases=("Hemköp Karhögstorg",),
            now=NOW,
        )

        rows = {row.product_name: row for section in report.sections for row in section.offers}
        assert rows["Public sale"].eligibility == "public"
        assert rows["Public sale"].mechanism == "sale_price"
        assert rows["Member sale"].eligibility == "member"
        assert rows["Member sale"].mechanism == "sale_price"
        assert rows["Public multibuy"].eligibility == "public"
        assert rows["Public multibuy"].mechanism == "multibuy"
        assert rows["Public multibuy"].required_quantity == 3
        assert rows["Public multibuy"].multibuy_total == Decimal(30)
        assert rows["Member multibuy"].eligibility == "member"
        assert rows["Member multibuy"].mechanism == "multibuy"


def test_coop_online_context_is_not_inherited_by_martenstorget(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        stora = _seed_physical_store(
            session,
            identifier="physical:coop:2696",
            chain="coop",
            external_id="2696",
            name="Stora Coop Lund",
        )
        _seed_physical_store(
            session,
            identifier="physical:coop:3813",
            chain="coop",
            external_id="3813",
            name="Coop Mårtenstorget",
        )
        _seed_context(
            session,
            physical=stora,
            context_external_id="730400",
            grocery_context_id="own:coop:730400",
            context_name="Coop Online Syd",
            price_context_type="online_fulfillment",
            relation_type="verified_pickup_context",
        )

        report = CurrentOffersReportService(session, max_age_hours=24).build(
            city="Lund",
            store_aliases=("Stora Coop Lund", "Coop Mårtenstorget"),
            now=NOW,
        )

        online = [
            section
            for section in report.sections
            if section.grocery_context_id == "own:coop:730400"
        ]
        assert len(online) == 1
        assert online[0].physical_store_id == "physical:coop:2696"
        assert "Coop Online Syd" in online[0].price_scope_label
        assert "onlinepris" in online[0].price_scope_label
        assert "inte verifierat hyllpris" in online[0].price_scope_label
        assert all(
            section.grocery_context_id != "own:coop:730400"
            for section in report.sections
            if section.physical_store_id == "physical:coop:3813"
        )


def test_stale_offers_are_excluded_from_main_rows_and_lkg_is_explicit(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        physical = _seed_physical_store(
            session,
            identifier="physical:hemkop:4224",
            chain="hemkop",
            external_id="4224",
            name="Hemköp Brunnshög",
        )
        store, snapshot, raw = _seed_context(
            session,
            physical=physical,
            context_external_id="4224",
            grocery_context_id="own:hemkop:4224",
            context_name="Hemköp Brunnshög Online",
            observed_at=NOW - timedelta(hours=30),
        )
        _seed_offer(
            session,
            store=store,
            snapshot=snapshot,
            raw=raw,
            key="stale-sale",
            product_name="Stale sale",
            regular_price=Decimal(20),
            offer_price=Decimal(10),
            promotion_type="sale_price",
        )

        report = CurrentOffersReportService(session, max_age_hours=24).build(
            city="Lund",
            store_aliases=("Hemköp Brunnshög",),
            now=NOW,
        )

        assert not [row for section in report.sections for row in section.offers]
        assert len(report.stale_or_incomplete_sources) == 1
        assert report.stale_or_incomplete_sources[0].lkg_used is True
        assert report.stale_or_incomplete_sources[0].data_age_hours == pytest.approx(30)


def _conflict_row(
    *,
    provider: str,
    product_name: str,
    price: Decimal,
    gtin: str | None,
):
    from grocery_data.app.services.current_offers import OfferRow

    return OfferRow(
        chain="hemkop",
        store_alias="Hemköp Karhögstorg",
        store_display_name="Hemköp Karhögstorg",
        physical_store_id="physical:hemkop:4123",
        grocery_context_id=f"{provider}:hemkop:4123",
        price_context_type="online_store",
        price_scope_label="ONLINE PRICE",
        source_provider=provider,
        source_channel="catalog",
        snapshot_id=f"snapshot-{provider}",
        observed_at=NOW,
        data_age_hours=0,
        gtin=gtin,
        product_name=product_name,
        active_offer_price=price,
        eligibility="public",
        mechanism="sale_price",
        validity_confidence="verified_full_period",
        availability="available",
        semantic_confidence="high",
        quantity_confidence="exact",
        promotion_confidence="explicit_contract",
        price_basis="package_price",
        active_at_generated_at=True,
        current_data=True,
    )


def _conflict_section(row):  # type: ignore[no-untyped-def]
    from grocery_data.app.services.current_offers import StoreOfferSection

    return StoreOfferSection(
        store_alias=row.store_alias,
        store_display_name=row.store_display_name,
        physical_store_id=row.physical_store_id,
        grocery_context_id=row.grocery_context_id,
        price_context_type=row.price_context_type,
        price_scope_label=row.price_scope_label,
        source_provider=row.source_provider,
        source_channel=row.source_channel,
        snapshot_id=row.snapshot_id,
        observed_at=row.observed_at,
        data_age_hours=0,
        freshness="fresh",
        offers=(row,),
    )


def test_source_disagreement_requires_strong_gtin_identity() -> None:
    from grocery_data.app.services.current_offers import _source_disagreements

    own = _conflict_section(
        _conflict_row(
            provider="own",
            product_name="Mjölk 1,5 l",
            price=Decimal("20.00"),
            gtin="7311043007851",
        )
    )
    primat = _conflict_section(
        _conflict_row(
            provider="primat",
            product_name="Mellanmjölk 1.5L",
            price=Decimal("22.00"),
            gtin="7311043007851",
        )
    )

    [disagreement] = _source_disagreements((own, primat))
    assert disagreement.gtin == "7311043007851"
    assert disagreement.price_a == Decimal("20.00")
    assert disagreement.price_b == Decimal("22.00")
    assert disagreement.difference == Decimal("2.00")


def test_similar_product_names_are_not_fuzzy_merged_without_gtin() -> None:
    from grocery_data.app.services.current_offers import _source_disagreements

    own = _conflict_section(
        _conflict_row(
            provider="own",
            product_name="Ekologisk mellanmjölk 1,5 l",
            price=Decimal("20.00"),
            gtin=None,
        )
    )
    primat = _conflict_section(
        _conflict_row(
            provider="primat",
            product_name="Eko mellanmjölk 1.5L",
            price=Decimal("22.00"),
            gtin=None,
        )
    )

    assert _source_disagreements((own, primat)) == ()


def test_report_uses_stockholm_time_and_exports_provenance_without_secrets(
    storage, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    from grocery_data.app.services.current_offers import write_current_offers_exports

    with session_scope(storage) as session:
        physical = _seed_physical_store(
            session,
            identifier="physical:hemkop:4123",
            chain="hemkop",
            external_id="4123",
            name="Hemköp Lund Karhögstorg",
        )
        store, snapshot, raw = _seed_context(
            session,
            physical=physical,
            context_external_id="4123",
            grocery_context_id="own:hemkop:4123",
            context_name="Hemköp Karhögstorg Online",
        )
        _seed_offer(
            session,
            store=store,
            snapshot=snapshot,
            raw=raw,
            key="export-sale",
            product_name="Export sale",
            regular_price=Decimal(20),
            offer_price=Decimal(10),
            promotion_type="sale_price",
            gtin="7311043007851",
        )
        report = CurrentOffersReportService(session, max_age_hours=24).build(
            city="Lund",
            store_aliases=("Hemköp Karhögstorg",),
            now=NOW,
        )

    assert report.generated_at_local.isoformat().endswith("+02:00")
    assert report.generated_at_utc == NOW
    paths = write_current_offers_exports(report, tmp_path)
    assert set(paths) == {"json", "csv", "markdown"}
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths.values())
    assert "own:hemkop:4123" in combined
    assert "snapshot-own-hemkop-4123" in combined
    assert "7311043007851" in combined
    for secret_name in ("Authorization", "Cookie", "CSRF", "DATABASE_URL"):
        assert secret_name not in combined
