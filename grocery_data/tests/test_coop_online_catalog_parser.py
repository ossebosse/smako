from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop.online_catalog_models import validated_category_tree
from grocery_data.app.connectors.coop.online_catalog_parser import (
    COOP_ONLINE_CATEGORY_PAGE_KIND,
    COOP_ONLINE_CATEGORY_TREE_KIND,
    COOP_ONLINE_PRODUCT_BY_ID_KIND,
    COOP_ONLINE_PRODUCT_SEARCH_KIND,
    COOP_ONLINE_PROMOTION_KIND,
    CoopOnlineCatalogParser,
    CoopOnlineCompletenessError,
)
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    PriceContextType,
    PromotionType,
    RawBatch,
    RawFetch,
    SaleModel,
    SourceStore,
)
from grocery_data.app.normalization.products import ProductNormalizer
from grocery_data.app.storage import (
    ProductBundleRepository,
    RawSnapshotRepository,
    SnapshotRepository,
    StoreRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

FIXTURE_DIR = Path(__file__).parents[1] / "app" / "connectors" / "coop" / "fixtures"
OBSERVED_AT = datetime(2026, 8, 25, 12, tzinfo=UTC)


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _fixture_row(name: str) -> dict[str, object]:
    payload = _fixture(name)
    return deepcopy(payload["results"]["items"][0])  # type: ignore[index]


def _milk() -> dict[str, object]:
    return _fixture_row("online_api_milk_730400.json")


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.COOP,
        external_id="730400",
        name="Coop Online Syd",
        city=None,
        online_shopping=True,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        price_context_type=PriceContextType.ONLINE_FULFILLMENT,
        physical_store_external_id=None,
        raw_reference="raw:context:730400",
        source_fields={"price_semantics": "online_price"},
    )


def _document(
    payload: dict[str, object],
    *,
    kind: str,
    skip: int | None = 0,
    take: int | None = 24,
    category_id: str | None = None,
    search_query: str | None = None,
) -> RawFetch:
    query = {"groups": "CUSTOMER_PRIVATE"}
    if skip is not None:
        query["skip"] = str(skip)
    if take is not None:
        query["take"] = str(take)
    if category_id is not None:
        query["category_id"] = category_id
    if search_query is not None:
        query["search_query"] = search_query
    return RawFetch(
        chain=Chain.COOP,
        store_external_id="730400",
        kind=kind,
        method="POST",
        url="https://external.api.coop.se/personalization/search/test",
        query=query,
        fetched_at=OBSERVED_AT,
        http_status=200,
        content_type="application/json",
        payload=json.dumps(payload, ensure_ascii=False).encode(),
        connector_version="coop-online-v1",
        page_number=(skip or 0) // (take or 1),
    )


def _tree(*codes: str) -> RawFetch:
    children = [
        {
            "code": code,
            "name": f"Category {code}",
            "url": f"/handla/varor/category-{code}",
            "children": [],
        }
        for code in codes
    ]
    return RawFetch(
        chain=Chain.COOP,
        store_external_id="730400",
        kind=COOP_ONLINE_CATEGORY_TREE_KIND,
        method="GET",
        url="https://external.api.coop.se/ecommerce/coop/users/anonymous/categories/tree/730400",
        fetched_at=OBSERVED_AT,
        http_status=200,
        content_type="application/json",
        payload=json.dumps(
            {"nodes": [{"code": "root", "name": "Root", "children": children}]}
        ).encode(),
        connector_version="coop-online-v1",
    )


def _page_payload(items: list[dict[str, object]], *, count: int, query: str | None = None):
    payload: dict[str, object] = {"results": {"count": count, "items": items}}
    if query is not None:
        payload["queryUsed"] = query
    return payload


def test_verified_milk_fields_map_without_price_or_quantity_inference() -> None:
    document = _document(
        _fixture("online_api_milk_730400.json"),
        kind=COOP_ONLINE_PRODUCT_SEARCH_KIND,
        search_query="mjölk",
    )

    page, (product,) = CoopOnlineCatalogParser().parse_page(
        document,
        reference="raw:milk",
        store=_store(),
        expected_query="mjölk",
    )

    assert page.reported_count == 1
    assert product.external_product_id == "7300156573186"
    assert product.gtin == "7300156573186"
    assert product.sale_price == Decimal("16.27")
    assert product.regular_price == Decimal("16.27")
    assert product.comparison_price == Decimal("10.85")
    assert product.comparison_unit == "l"
    assert product.package_quantity == 1500
    assert product.package_unit == "ml"
    assert product.sale_unit == "st"
    assert product.member_price is None
    assert product.offers == ()
    assert product.source_fields["customer_group"] == "CUSTOMER_PRIVATE"
    assert product.source_fields["price_semantics"] == "online_price"


def test_customer_private_is_b2c_and_never_manufactures_membership() -> None:
    row = _milk()
    row["promotionPriceData"] = {"b2cPrice": 9.9}
    row["onlinePromotions"] = [
        {
            "id": "undated-private-campaign",
            "type": "FIXED_PRICE",
            "priceData": {"b2cPrice": 9.9},
            "medMeraRequired": False,
        }
    ]

    product = CoopOnlineCatalogParser().parse_product(
        row,
        store=_store(),
        reference="raw:private",
        fetched_at=OBSERVED_AT,
    )

    assert product.sale_price == Decimal("16.27")
    assert product.member_price is None
    assert product.offers == ()


def test_verified_fixed_promotion_separates_base_and_effective_price() -> None:
    document = _document(
        _fixture("online_api_soy_promotion_730400.json"),
        kind=COOP_ONLINE_PROMOTION_KIND,
        take=50,
    )

    (product,) = CoopOnlineCatalogParser().parse_promotion(
        document,
        reference="raw:soy",
        store=_store(),
    )

    assert product.external_product_id == "7300156601421"
    assert product.regular_price == Decimal("28.35")
    assert product.sale_price == Decimal("19.9")
    assert product.comparison_price == Decimal("113.4")
    assert len(product.offers) == 1
    offer = product.offers[0]
    assert offer.external_id == "v.35 DR 2026 såser"
    assert offer.type is PromotionType.SALE_PRICE
    assert offer.price == Decimal("19.9")
    assert offer.member_only is False
    assert offer.valid_from.isoformat() == "2026-08-23"
    assert offer.valid_to.isoformat() == "2026-08-30"


def test_multibuy_preserves_bundle_condition_instead_of_flattening_promotion_price() -> None:
    document = _document(
        _fixture("online_api_multibuy_730400.json"),
        kind=COOP_ONLINE_PROMOTION_KIND,
        take=50,
    )

    (product,) = CoopOnlineCatalogParser().parse_promotion(
        document,
        reference="raw:multibuy",
        store=_store(),
    )

    assert product.regular_price == Decimal("17.51")
    assert product.sale_price == Decimal("17.51")
    assert product.source_fields["promotion_price_b2c"] == "12.5"
    assert len(product.offers) == 1
    offer = product.offers[0]
    assert offer.type is PromotionType.MULTIBUY
    assert offer.quantity == 2
    assert offer.price == 29
    assert offer.member_only is False


def test_approximate_weight_package_preserves_member_price_and_average_weight() -> None:
    document = _document(
        _fixture("online_api_variable_weight_member_730400.json"),
        kind=COOP_ONLINE_PROMOTION_KIND,
        take=50,
    )

    (product,) = CoopOnlineCatalogParser().parse_promotion(
        document,
        reference="raw:lax",
        store=_store(),
    )

    assert product.external_product_id == "2383471000006"
    assert product.package_quantity == 1150
    assert product.package_unit == "g"
    assert product.average_weight_kg == Decimal("1.15")
    assert product.sale_unit == "kg"
    assert product.basket_type == "ST"
    assert product.sale_price == Decimal("259.32")
    assert product.regular_price == Decimal("259.32")
    assert product.comparison_price == Decimal("259.32")
    assert product.comparison_unit == "kg"
    assert product.member_price == Decimal(139)
    assert product.offers[0].type is PromotionType.MEMBER_PRICE
    assert product.offers[0].member_only is True
    assert product.offers[0].price == Decimal(139)
    assert product.offers[0].source_payload["piece_price"] == "159.85"
    assert product.offers[0].source_payload["comparative_price"] == "139.0"

    canonical = ProductNormalizer().normalize(
        product,
        parser_version=CoopOnlineCatalogParser.parser_version,
    )
    assert canonical.sale_model is SaleModel.VARIABLE_WEIGHT_PACKAGE
    assert canonical.package_quantity == 1150
    assert canonical.package_unit == "g"
    assert canonical.unit_price == Decimal("259.32")
    assert canonical.sale_price == Decimal("298.2180")


def test_vikt_sales_unit_is_explicit_sold_by_weight_semantics() -> None:
    row = _milk()
    row.update(
        {
            "id": "sold-by-weight-row",
            "ean": None,
            "salesUnit": "Vikt",
            "packageSize": None,
            "packageSizeUnit": None,
            "packageSizeInformation": None,
            "salesPriceData": {"b2cPrice": 49.9},
            "pricePriceData": {"b2cPrice": 49.9},
            "comparativePriceData": {"b2cPrice": 49.9},
            "comparativePriceText": "kr/kg",
            "comparativePriceUnit": {"unit": "kilogram"},
        }
    )

    product = CoopOnlineCatalogParser().parse_product(
        row,
        store=_store(),
        reference="raw:weight",
        fetched_at=OBSERVED_AT,
    )

    assert product.sale_unit == "kg"
    assert product.package_quantity is None
    assert product.basket_type == "VIKT"


def test_percentage_discount_preserves_both_verified_percentage_fields() -> None:
    row = _fixture_row("online_api_percentage_discount_730400.json")

    product = CoopOnlineCatalogParser().parse_product(
        row,
        store=_store(),
        reference="raw:percentage",
        fetched_at=OBSERVED_AT,
    )

    assert product.sale_price == Decimal("13.02")
    offer = product.offers[0]
    assert offer.type is PromotionType.PERCENT_DISCOUNT
    assert offer.source_payload["percentage_discount"] == "20"
    assert offer.source_payload["adjusted_percentage_discount"] == "20"


@pytest.mark.parametrize(
    ("unit", "postfix", "text", "expected"),
    [
        ("styck", None, "kr/st", "st"),
        ("liter", "drickfärdig", "kr/lit drickfärdig", "l"),
        ("kg", "ätklar", "kr/kg ätklar", "kg"),
    ],
)
def test_explicit_comparison_unit_survives_source_postfix(
    unit: str,
    postfix: str | None,
    text: str,
    expected: str,
) -> None:
    row = _milk()
    row["comparativePriceUnit"] = {
        "unit": unit,
        **({"postfix": postfix} if postfix is not None else {}),
    }
    row["comparativePriceText"] = text

    product = CoopOnlineCatalogParser().parse_product(
        row,
        store=_store(),
        reference="raw:comparison-postfix",
        fetched_at=OBSERVED_AT,
    )

    assert product.comparison_price == Decimal("10.85")
    assert product.comparison_unit == expected
    assert product.source_fields["comparison_unit_verified"] is True


@pytest.mark.parametrize(
    ("text", "unit_payload"),
    [
        ("kr/tvätt/disk", None),
        ("utan sås/spad", {"postfix": "utan sås/spad"}),
    ],
)
def test_unverifiable_comparison_unit_is_provenance_only(
    text: str,
    unit_payload: dict[str, str] | None,
) -> None:
    row = _milk()
    row["comparativePriceText"] = text
    row["comparativePriceUnit"] = unit_payload

    product = CoopOnlineCatalogParser().parse_product(
        row,
        store=_store(),
        reference="raw:comparison-unverified",
        fetched_at=OBSERVED_AT,
    )

    assert product.comparison_price is None
    assert product.comparison_unit is None
    assert product.source_fields["raw_comparative_price_b2c"] == "10.85"
    assert product.source_fields["raw_comparative_price_text"] == text
    assert product.source_fields["raw_comparative_price_unit"] == unit_payload
    assert product.source_fields["comparison_unit_verified"] is False


def test_unproven_weight_piece_promotion_is_withheld_from_basket_math() -> None:
    document = _document(
        _fixture("online_api_unproven_weight_promotion_730400.json"),
        kind=COOP_ONLINE_PROMOTION_KIND,
        take=50,
    )

    (product,) = CoopOnlineCatalogParser().parse_promotion(
        document,
        reference="raw:unproven-weight-promotion",
        store=_store(),
    )

    assert product.sale_unit == "kg"
    assert product.average_weight_kg is None
    assert product.basket_type == "VIKT"
    assert product.sale_price == Decimal(102)
    assert product.regular_price == Decimal(102)
    assert product.offers == ()
    assert product.source_fields["active_promotion_ids"] == [
        "sanitized-weight-rate-89"
    ]
    assert product.source_fields["withheld_uncertain_promotion_ids"] == [
        "sanitized-weight-rate-89"
    ]
    assert product.source_fields["withheld_promotion_reason"] == (
        "weight_piece_semantics_unproven"
    )

    canonical = ProductNormalizer().normalize(
        product,
        parser_version=CoopOnlineCatalogParser.parser_version,
    )
    assert canonical.sale_model is SaleModel.SOLD_BY_WEIGHT
    assert canonical.sale_price == Decimal(102)
    assert canonical.unit_price == Decimal(102)


def test_only_matching_current_fixed_promotion_sets_effective_price() -> None:
    document = _document(
        _fixture("online_api_competing_fixed_promotions_730400.json"),
        kind=COOP_ONLINE_PROMOTION_KIND,
        take=50,
    )

    (product,) = CoopOnlineCatalogParser().parse_promotion(
        document,
        reference="raw:competing-fixed",
        store=_store(),
    )

    assert product.regular_price == Decimal("149.9")
    assert product.sale_price == Decimal("129.9")
    assert len(product.offers) == 2
    assert {offer.price for offer in product.offers} == {
        Decimal("129.9"),
        Decimal(100),
    }
    assert product.source_fields["withheld_uncertain_promotion_ids"] == []


def test_by_id_product_is_semantically_equal_to_search_row() -> None:
    payload = _fixture("online_api_milk_730400.json")
    search_document = _document(
        payload,
        kind=COOP_ONLINE_PRODUCT_SEARCH_KIND,
        search_query="mjölk",
    )
    by_id_document = _document(
        payload,
        kind=COOP_ONLINE_PRODUCT_BY_ID_KIND,
        skip=None,
        take=None,
    )
    parser = CoopOnlineCatalogParser()

    _, (search_product,) = parser.parse_page(
        search_document,
        reference="raw:search",
        store=_store(),
        expected_query="mjölk",
    )
    (by_id_product,) = parser.parse_by_id(
        by_id_document,
        reference="raw:by-id",
        store=_store(),
    )

    excluded = {"raw_reference"}
    assert search_product.model_dump(exclude=excluded) == by_id_product.model_dump(exclude=excluded)


def test_complete_search_offset_traversal_reconciles_every_reported_row() -> None:
    rows = [_milk() for _ in range(3)]
    for index, row in enumerate(rows):
        row["id"] = f"product-{index}"
        row["ean"] = None
    documents = (
        _document(
            _page_payload(rows[:2], count=3, query="mjölk"),
            kind=COOP_ONLINE_PRODUCT_SEARCH_KIND,
            skip=0,
            take=2,
            search_query="mjölk",
        ),
        _document(
            _page_payload(rows[2:], count=3, query="mjölk"),
            kind=COOP_ONLINE_PRODUCT_SEARCH_KIND,
            skip=2,
            take=2,
            search_query="mjölk",
        ),
    )

    result = CoopOnlineCatalogParser().reconcile_search(
        RawBatch(chain=Chain.COOP, documents=documents),
        ["raw:milk:0", "raw:milk:2"],
        _store(),
    )

    assert result.completion.is_full_traversal is True
    assert result.completion.expected_products == 3
    assert result.completion.pages_fetched == 2
    assert result.completion.unique_products == 3
    assert result.completion.duplicate_products == 0


def test_missing_offset_page_fails_closed() -> None:
    document = _document(
        _page_payload([_milk()], count=3, query="mjölk"),
        kind=COOP_ONLINE_PRODUCT_SEARCH_KIND,
        skip=2,
        take=2,
        search_query="mjölk",
    )

    with pytest.raises(CoopOnlineCompletenessError, match="pagination is incomplete"):
        CoopOnlineCatalogParser().reconcile_search(
            RawBatch(chain=Chain.COOP, documents=(document,)),
            ["raw:milk:2"],
            _store(),
        )


def test_identical_within_category_duplicate_is_safely_deduplicated() -> None:
    row = _milk()
    page = _document(
        _page_payload([row, deepcopy(row)], count=2),
        kind=COOP_ONLINE_CATEGORY_PAGE_KIND,
        take=2,
        category_id="334703",
    )
    raw = RawBatch(chain=Chain.COOP, documents=(_tree("334703"), page))

    result = CoopOnlineCatalogParser().reconcile_catalog(
        raw,
        ["raw:tree", "raw:category"],
        _store(),
    )

    assert len(result.products) == 1
    assert result.duplicate_metrics.exact_duplicates_removed == 1
    assert result.duplicate_metrics.pagination_overlaps == 0
    assert result.completion.is_full_traversal is True


def test_identical_later_page_duplicate_is_classified_as_pagination_overlap() -> None:
    first = _milk()
    second = _milk()
    second["id"] = "another-product"
    second["ean"] = None
    page_zero = _document(
        _page_payload([first, second], count=3),
        kind=COOP_ONLINE_CATEGORY_PAGE_KIND,
        skip=0,
        take=2,
        category_id="334703",
    )
    page_one = _document(
        _page_payload([deepcopy(first)], count=3),
        kind=COOP_ONLINE_CATEGORY_PAGE_KIND,
        skip=2,
        take=2,
        category_id="334703",
    )

    result = CoopOnlineCatalogParser().reconcile_catalog(
        RawBatch(chain=Chain.COOP, documents=(_tree("334703"), page_zero, page_one)),
        ["raw:tree", "raw:page:0", "raw:page:1"],
        _store(),
    )

    assert result.duplicate_metrics.exact_duplicates_removed == 1
    assert result.duplicate_metrics.pagination_overlaps == 1
    assert result.completion.is_full_traversal is True


def test_conflicting_same_id_duplicate_fails_closed() -> None:
    first = _milk()
    conflict = deepcopy(first)
    conflict["salesPriceData"] = {"b2cPrice": 99}
    conflict["pricePriceData"] = {"b2cPrice": 99}
    page = _document(
        _page_payload([first, conflict], count=2),
        kind=COOP_ONLINE_CATEGORY_PAGE_KIND,
        take=2,
        category_id="334703",
    )

    with pytest.raises(CoopOnlineCompletenessError, match="duplicate conflicts"):
        CoopOnlineCatalogParser().reconcile_catalog(
            RawBatch(chain=Chain.COOP, documents=(_tree("334703"), page)),
            ["raw:tree", "raw:category"],
            _store(),
        )


def test_identical_cross_category_overlap_is_retained_once_and_explained() -> None:
    first_page = _document(
        _page_payload([_milk()], count=1),
        kind=COOP_ONLINE_CATEGORY_PAGE_KIND,
        category_id="milk-a",
    )
    second_page = _document(
        _page_payload([_milk()], count=1),
        kind=COOP_ONLINE_CATEGORY_PAGE_KIND,
        category_id="milk-b",
    )

    result = CoopOnlineCatalogParser().reconcile_catalog(
        RawBatch(
            chain=Chain.COOP,
            documents=(_tree("milk-a", "milk-b"), first_page, second_page),
        ),
        ["raw:tree", "raw:a", "raw:b"],
        _store(),
    )

    assert len(result.products) == 1
    assert result.duplicate_metrics.cross_category_overlaps == 1
    assert result.completion.cross_partition_duplicates == 1
    assert result.completion.is_full_traversal is True


def test_verified_tree_duplicate_leaf_is_collapsed_and_distinct_code_alias_is_preserved() -> None:
    payload = {
        "nodes": [
            {
                "code": "root",
                "name": "Root",
                "children": [
                    {
                        "code": "334819",
                        "name": "Presentinslagning",
                        "url": "/handla/varor/presentinslagning",
                    },
                    {
                        "code": "334819",
                        "name": "Presentinslagning",
                        "url": "/handla/varor/presentinslagning",
                    },
                    {
                        "code": "alias-code",
                        "name": "Presentpapper",
                        "url": "/handla/varor/presentinslagning",
                    },
                ],
            }
        ]
    }

    tree = validated_category_tree(payload)

    assert len(tree.terminal_rows()) == 3
    assert len(tree.terminal_nodes()) == 2
    assert tree.duplicate_terminal_rows == 1
    assert tree.navigation_aliases == {
        "/handla/varor/presentinslagning": ("334819", "alias-code")
    }


def test_online_context_cannot_be_modeled_as_a_physical_store() -> None:
    physical_impersonation = _store().model_copy(
        update={
            "price_context_type": PriceContextType.PHYSICAL_STORE,
            "physical_store_external_id": "730400",
        }
    )
    document = _document(
        _fixture("online_api_milk_730400.json"),
        kind=COOP_ONLINE_PRODUCT_SEARCH_KIND,
        search_query="mjölk",
    )

    with pytest.raises(Exception, match="ONLINE_FULFILLMENT"):
        CoopOnlineCatalogParser().parse_page(
            document,
            reference="raw:milk",
            store=physical_impersonation,
            expected_query="mjölk",
        )


def test_every_online_parser_provenance_payload_is_plain_json_native() -> None:
    fixture_names = (
        "online_api_milk_730400.json",
        "online_api_soy_promotion_730400.json",
        "online_api_multibuy_730400.json",
        "online_api_variable_weight_member_730400.json",
        "online_api_percentage_discount_730400.json",
        "online_api_unproven_weight_promotion_730400.json",
        "online_api_competing_fixed_promotions_730400.json",
    )
    parser = CoopOnlineCatalogParser()

    for name in fixture_names:
        product = parser.parse_product(
            _fixture_row(name),
            store=_store(),
            reference=f"raw:{name}",
            fetched_at=OBSERVED_AT,
        )
        json.dumps(product.source_fields, ensure_ascii=False)
        for offer in product.offers:
            json.dumps(offer.source_payload, ensure_ascii=False)


def test_percentage_discount_product_persists_through_bundle_repository() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            source_store = _store()
            store_row = StoreRepository(session).upsert(source_store, seen_at=OBSERVED_AT)
            snapshot = SnapshotRepository(session).create(
                chain=Chain.COOP,
                coverage=CoverageLevel.FULL_ONLINE_CATALOG,
                connector_version="coop-online-catalog-v1",
                scope_key="coop:online:730400",
                parser_version=CoopOnlineCatalogParser.parser_version,
                normalizer_version=ProductNormalizer.normalizer_version,
                created_at=OBSERVED_AT,
            )
            document = _document(
                _fixture("online_api_percentage_discount_730400.json"),
                kind=COOP_ONLINE_PROMOTION_KIND,
                take=50,
            )
            raw_row = RawSnapshotRepository(session).record_fetch(
                document,
                catalog_snapshot_id=snapshot.id,
                payload_location="raw/coop/test/percentage.json",
            )
            (source,) = CoopOnlineCatalogParser().parse_promotion(
                document,
                reference=f"raw:{raw_row.id}",
                store=source_store,
            )
            canonical = ProductNormalizer().normalize(
                source,
                parser_version=CoopOnlineCatalogParser.parser_version,
            )

            bundle = ProductBundleRepository(session).persist(
                source=source,
                canonical=canonical,
                catalog_snapshot_id=snapshot.id,
                raw_snapshot_id=raw_row.id,
                store_id=store_row.id,
            )

            assert len(bundle.promotions) == 1
            assert bundle.promotions[0].source_payload["percentage_discount"] == "20"
            assert (
                bundle.promotions[0].source_payload["adjusted_percentage_discount"]
                == "20"
            )
    finally:
        engine.dispose()


def test_energy_label_and_badge_order_do_not_change_any_parsed_product_field():
    before = _milk()
    before["accreditedTags"] = [{"code": "KRAV", "description": "KRAV", "priority": 1}]
    after = deepcopy(before)
    after["accreditedTags"][0].pop("priority")
    after["energyLabel"] = {
        "accessibilityText": "Energy label", "energyClass": "A",
        "productSheetUrl": "https://www.coop.se/product-sheet.pdf",
        "smallImageUrl": "https://www.coop.se/energy-label.png",
    }
    parser = CoopOnlineCatalogParser()
    kwargs = {"store": _store(), "reference": "raw:presentation-review", "fetched_at": OBSERVED_AT}
    assert parser.parse_product(before, **kwargs) == parser.parse_product(after, **kwargs)
