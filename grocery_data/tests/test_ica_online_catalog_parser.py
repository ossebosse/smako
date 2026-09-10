from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_CATEGORY_TREE_KIND,
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    IcaBatchResult,
    IcaCategoryTree,
    IcaOnlineSchemaError,
    IcaProductPage,
    purchase_semantic_fingerprint,
    reconcile_page_batches,
    sanitized_category_tree_payload,
    sanitized_context_payload,
    validate_continuation_chain,
)
from grocery_data.app.connectors.ica.online_catalog_parser import IcaOnlineCatalogParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    PriceContextType,
    RawBatch,
    RawFetch,
    SourceStore,
)

FIXTURE_DIR = Path(__file__).parents[1] / "app" / "connectors" / "ica" / "fixtures"
OBSERVED_AT = datetime(2026, 8, 25, 12, tzinfo=UTC)
REGION_ID = "92198f17-b02f-4fae-ad41-228bcc725420"
CATEGORY_ID = "ea243faf-2eca-47d7-af07-1dc61dd7693a"


def _fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _page() -> dict[str, object]:
    return deepcopy(_fixture("online_v6_product_page.json"))


def _promotion_clean_page() -> dict[str, object]:
    payload = _page()
    payload["missedPromotions"] = []
    product = payload["productGroups"][0]["decoratedProducts"][0]  # type: ignore[index]
    product.pop("featuredProductCampaign", None)
    return payload


def _complete_page_with_declared_count() -> dict[str, object]:
    payload = _promotion_clean_page()
    payload["additionalPageInfo"] = {
        "metadata": {"terminal": True},
        "currentCategory": {"categoryId": CATEGORY_ID, "productCount": 3},
    }
    return payload


def _category_tree_without_counts() -> dict[str, object]:
    payload = _fixture("online_v6_category_tree.json")

    def strip_count(node: dict[str, object]) -> None:
        node.pop("productCount", None)
        for child in node.get("childCategories", []):  # type: ignore[union-attr]
            strip_count(child)

    for root in payload["categories"]:  # type: ignore[union-attr]
        strip_count(root)
    return payload


def _batch() -> dict[str, object]:
    return deepcopy(_fixture("online_v6_product_batch.json"))


def _milk() -> dict[str, object]:
    page = _page()
    return deepcopy(page["productGroups"][0]["decoratedProducts"][0])  # type: ignore[index]


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.ICA,
        external_id=REGION_ID,
        name="ICA Online Gunnesbo",
        city="Lund",
        online_shopping=True,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        price_context_type=PriceContextType.ONLINE_STORE,
        physical_store_external_id="1088004",
        raw_reference="raw:ica-context",
        source_fields={"price_semantics": "online_price"},
    )


def _online_store(region_id: str, name: str) -> SourceStore:
    return _store().model_copy(update={"external_id": region_id, "name": name})


def _document(
    payload: dict[str, object],
    *,
    kind: str,
    query: dict[str, str] | None = None,
    page_number: int | None = None,
) -> RawFetch:
    return RawFetch(
        chain=Chain.ICA,
        store_external_id=REGION_ID,
        kind=kind,
        method="POST" if kind != ICA_CATEGORY_TREE_KIND else "GET",
        url="https://handla.ica.se/api/test",
        query=query or {},
        fetched_at=OBSERVED_AT,
        http_status=200,
        content_type="application/json",
        payload=json.dumps(payload, ensure_ascii=False).encode(),
        connector_version="ica-online-v1",
        page_number=page_number,
    )


def test_context_and_category_sanitizers_keep_only_verified_allowlist() -> None:
    ssr_tree = {
        "categories": [
            {
                "id": "11111111-1111-4111-8111-111111111111",
                "name": "Mejeri",
                "retailerId": "256",
                "fullURLPath": "/mejeri",
                "children": [
                    {
                        "id": CATEGORY_ID,
                        "name": "Mjölk",
                        "retailerId": "257",
                        "fullURLPath": "/mejeri/mjolk",
                        "children": [],
                    }
                ],
            }
        ]
    }
    state = {
        "regionId": REGION_ID,
        "retailerRegionId": "gunnesbo-retailer-region",
        "cookie": "must-not-survive",
        "trackingId": "must-not-survive",
        "navigation": ssr_tree,
    }
    html = (
        "<script>window.__INITIAL_DATA__ = "
        + json.dumps(state, ensure_ascii=False)
        + ";</script>"
    )

    context = json.loads(
        sanitized_context_payload(
            html,
            "gunnesbo-retailer-region",
            REGION_ID,
        )
    )
    category_payload = sanitized_category_tree_payload(
        html,
        "gunnesbo-retailer-region",
        REGION_ID,
    )
    category_state = json.loads(category_payload)

    assert context == {
        "regionId": REGION_ID,
        "retailerRegionId": "gunnesbo-retailer-region",
        "schema": "ica-online-context-v1",
    }
    assert "cookie" not in category_payload.decode()
    assert "tracking" not in category_payload.decode().casefold()
    assert category_state["schema"] == "ica-online-category-tree-v1"
    assert IcaCategoryTree.from_payload(category_payload).terminal_nodes[0].name == "Mjölk"


def test_context_sanitizer_rejects_mismatched_readback() -> None:
    with pytest.raises(IcaOnlineSchemaError, match="regionId readback"):
        sanitized_context_payload(
            {
                "regionId": "25cd762f-f65f-49e9-b12d-d02265c04165",
                "retailerRegionId": "gunnesbo-retailer-region",
            },
            "gunnesbo-retailer-region",
            REGION_ID,
        )


def test_category_tree_has_stable_parent_and_terminal_metadata() -> None:
    tree = IcaCategoryTree.from_payload(_fixture("online_v6_category_tree.json"))

    assert tree.node_count == 2
    assert tree.terminal_count == 1
    assert tree.terminal_nodes[0].category_id == CATEGORY_ID
    assert tree.terminal_nodes[0].parent_category_id == "11111111-1111-4111-8111-111111111111"
    assert tree.terminal_nodes[0].product_count == 3


def test_product_page_reconciles_inline_and_other_ids_and_hashes_live_token() -> None:
    payload = _page()
    token = "5260877e-b589-4766-afd4-278267b3cfc3"
    payload["additionalPageInfo"] = {"metadata": {"nextPageToken": token}}

    page = IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)

    assert len(page.decorated_products) == 1
    assert len(page.other_product_ids) == 2
    assert len(page.ordered_product_ids) == 3
    assert page.missed_promotions[0]["requiredProductQuantity"] == 2
    assert page.next_page_token == token
    assert page.next_page_token_hash == sha256(token.encode()).hexdigest()
    assert page.terminal is False


def test_replay_page_accepts_token_hash_but_never_both_token_forms() -> None:
    payload = _page()
    token_hash = "a" * 64
    payload["additionalPageInfo"] = {"metadata": {"nextPageTokenHash": token_hash}}
    page = IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)

    assert page.next_page_token is None
    assert page.next_page_token_hash == token_hash

    payload["additionalPageInfo"] = {
        "metadata": {"nextPageToken": "secret-runtime-token", "nextPageTokenHash": token_hash}
    }
    with pytest.raises(IcaOnlineSchemaError, match="both live and persisted"):
        IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)


def test_product_page_rejects_malformed_missed_promotions() -> None:
    payload = _page()
    payload["missedPromotions"] = {"promoId": "not-a-list"}

    with pytest.raises(IcaOnlineSchemaError, match="promotions must be a list"):
        IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)


def test_product_page_accepts_both_observed_promotion_key_generations() -> None:
    payload = _page()
    evidence = payload.pop("missedPromotions")
    payload["missingPromotions"] = evidence

    page = IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)

    assert page.missed_promotions[0]["requiredProductQuantity"] == 2

    payload["missedPromotions"] = []
    with pytest.raises(IcaOnlineSchemaError, match="conflicting"):
        IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)


def test_token_loop_fails_closed() -> None:
    first_payload = _page()
    second_payload = _page()
    first_payload["additionalPageInfo"] = {"metadata": {"nextPageTokenHash": "b" * 64}}
    second_payload["additionalPageInfo"] = {"metadata": {"nextPageTokenHash": "b" * 64}}
    pages = (
        IcaProductPage.from_payload(first_payload, category_id=CATEGORY_ID),
        IcaProductPage.from_payload(second_payload, category_id=CATEGORY_ID),
    )

    with pytest.raises(IcaOnlineSchemaError, match="repeated a continuation token"):
        validate_continuation_chain(pages)


def test_exact_page_duplicate_is_removed_but_price_conflict_fails_closed() -> None:
    payload = _page()
    row = _milk()
    payload["productGroups"].append(  # type: ignore[union-attr]
        {"groupType": "featured", "decoratedProducts": [row], "otherProductIds": []}
    )
    page = IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)

    assert len(page.decorated_products) == 1
    assert page.duplicate_metrics.exact_duplicates == 1

    conflict = _milk()
    conflict["price"] = {"amount": 99.90, "currency": "SEK"}
    payload["productGroups"][-1]["decoratedProducts"] = [conflict]  # type: ignore[index]
    with pytest.raises(IcaOnlineSchemaError, match="conflicting product"):
        IcaProductPage.from_payload(payload, category_id=CATEGORY_ID)


def test_purchase_fingerprint_ignores_category_placement_but_not_price() -> None:
    first = _milk()
    second = deepcopy(first)
    second["categoryPath"] = ["Ny placering"]
    second["quantityInBasket"] = 9
    assert purchase_semantic_fingerprint(first) == purchase_semantic_fingerprint(second)

    second["price"] = {"amount": 99, "currency": "SEK"}
    assert purchase_semantic_fingerprint(first) != purchase_semantic_fingerprint(second)


def test_batch_requires_every_requested_product_and_deduplicates_exact_rows() -> None:
    payload = _batch()
    requested = [row["productId"] for row in payload["products"]]  # type: ignore[index]
    payload["products"].append(deepcopy(payload["products"][0]))  # type: ignore[union-attr,index]

    result = IcaBatchResult.from_payload(payload, requested_product_ids=requested)

    assert len(result.products) == 2
    assert result.duplicate_metrics.exact_duplicates == 1

    with pytest.raises(IcaOnlineSchemaError, match="does not reconcile"):
        IcaBatchResult.from_payload(payload, requested_product_ids=[*requested, REGION_ID])


def test_page_batch_reconciliation_requires_exact_other_product_ids() -> None:
    page = IcaProductPage.from_payload(_page(), category_id=CATEGORY_ID)
    requested = list(page.other_product_ids)
    batch = IcaBatchResult.from_payload(_batch(), requested_product_ids=requested)

    resolved = reconcile_page_batches(page, [batch])

    assert resolved.product_ids == page.ordered_product_ids
    assert len(resolved.products) == 3

    with pytest.raises(IcaOnlineSchemaError, match="differ from otherProductIds"):
        reconcile_page_batches(page, [])


def test_product_parser_uses_package_price_and_keeps_campaign_unresolved() -> None:
    product = IcaOnlineCatalogParser().parse_product(
        _milk(),
        store=_store(),
        reference="raw:milk",
        fetched_at=OBSERVED_AT,
    )

    assert product.external_product_id == "f4ec81a4-4fff-4696-92dc-4a3e7bf06c31"
    assert product.source_fields["retailer_product_id"] == "2052770"
    assert product.gtin is None
    assert product.sale_price == Decimal("15.9")
    assert product.regular_price == Decimal("15.9")
    assert product.comparison_price == Decimal("10.6")
    assert product.comparison_unit == "l"
    assert product.package_quantity == Decimal(1500)
    assert product.package_unit == "ml"
    assert product.member_price is None
    assert product.offers == ()
    assert product.source_fields["promotion_resolution"] == "unresolved"


def test_product_parser_accepts_verified_nested_ica_unit_price_shape() -> None:
    row = _milk()
    row["unitPrice"] = {
        "price": {"amount": "10.60", "currency": "SEK"},
        "unit": "fop.price.per.litre",
        "unitName": "PER_LITRE",
    }

    product = IcaOnlineCatalogParser().parse_product(
        row,
        store=_store(),
        reference="raw:nested-unit-price",
        fetched_at=OBSERVED_AT,
    )

    assert product.comparison_price == Decimal("10.60")
    assert product.comparison_unit == "l"


def test_same_ica_product_identity_can_have_context_specific_prices() -> None:
    evidence = _fixture("online_v6_cross_context_price.json")
    rows = evidence["products"]  # type: ignore[assignment]
    gunnesbo_row, burlov_row = rows  # type: ignore[misc]
    gunnesbo = IcaOnlineCatalogParser().parse_product(
        gunnesbo_row["product"],
        store=_online_store(gunnesbo_row["regionId"], "ICA Online Gunnesbo"),
        reference="raw:gunnesbo-manual-evidence",
        fetched_at=OBSERVED_AT,
    )
    burlov = IcaOnlineCatalogParser().parse_product(
        burlov_row["product"],
        store=_online_store(burlov_row["regionId"], "ICA Online Burlöv"),
        reference="raw:burlov-manual-evidence",
        fetched_at=OBSERVED_AT,
    )

    assert gunnesbo.external_product_id == burlov.external_product_id
    assert gunnesbo.source_fields["retailer_product_id"] == (
        burlov.source_fields["retailer_product_id"]
    )
    assert gunnesbo.store_external_id != burlov.store_external_id
    assert gunnesbo.sale_price is not None
    assert burlov.sale_price is not None
    assert gunnesbo.sale_price != burlov.sale_price


@pytest.mark.parametrize(("available", "current"), [(False, True), (True, False)])
def test_unavailable_or_non_catalog_product_is_not_basket_priced(
    available: bool,
    current: bool,
) -> None:
    row = _milk()
    row["available"] = available
    row["isInCurrentCatalog"] = current

    product = IcaOnlineCatalogParser().parse_product(
        row,
        store=_store(),
        reference="raw:unavailable",
        fetched_at=OBSERVED_AT,
    )

    assert product.sale_price is None
    assert product.regular_price is None
    assert product.member_price is None


def test_full_offline_catalog_reconciles_page_ids_and_batch_products() -> None:
    requested_ids = [row["productId"] for row in _batch()["products"]]  # type: ignore[index]
    documents = (
        _document(_category_tree_without_counts(), kind=ICA_CATEGORY_TREE_KIND),
        _document(
            _complete_page_with_declared_count(),
            kind=ICA_PRODUCT_PAGE_KIND,
            query={"category_id": CATEGORY_ID, "page_index": "0"},
            page_number=0,
        ),
        _document(
            _batch(),
            kind=ICA_PRODUCT_BATCH_KIND,
            query={
                "category_id": CATEGORY_ID,
                "page_index": "0",
                "batch_index": "0",
                "requested_product_ids": json.dumps(requested_ids, separators=(",", ":")),
            },
            page_number=0,
        ),
    )
    raw = RawBatch(chain=Chain.ICA, documents=documents)
    parser = IcaOnlineCatalogParser()

    reconciliation = parser.reconcile_catalog(
        raw,
        ["raw:tree", "raw:page", "raw:batch"],
        _store(),
    )
    result = parser.parse_catalog(
        raw,
        ["raw:tree", "raw:page", "raw:batch"],
        _store(),
    )

    assert reconciliation.completion.is_full_traversal
    assert reconciliation.completion.expected_categories == 1
    assert reconciliation.completion.unique_products == 3
    assert len(result.products) == 3
    assert result.failures == []


def test_missing_batch_product_turns_catalog_into_schema_failure() -> None:
    batch_payload = _batch()
    requested_ids = [row["productId"] for row in batch_payload["products"]]  # type: ignore[index]
    batch_payload["products"] = batch_payload["products"][:1]  # type: ignore[index]
    documents = (
        _document(_category_tree_without_counts(), kind=ICA_CATEGORY_TREE_KIND),
        _document(
            _complete_page_with_declared_count(),
            kind=ICA_PRODUCT_PAGE_KIND,
            query={"category_id": CATEGORY_ID, "page_index": "0"},
            page_number=0,
        ),
        _document(
            batch_payload,
            kind=ICA_PRODUCT_BATCH_KIND,
            query={
                "category_id": CATEGORY_ID,
                "page_index": "0",
                "batch_index": "0",
                "requested_product_ids": json.dumps(requested_ids),
            },
            page_number=0,
        ),
    )

    result = IcaOnlineCatalogParser().parse_catalog(
        RawBatch(chain=Chain.ICA, documents=documents),
        ["raw:tree", "raw:page", "raw:batch"],
        _store(),
    )

    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "schema_changed"


def test_unresolved_promotion_evidence_blocks_full_catalog_acceptance() -> None:
    requested_ids = [row["productId"] for row in _batch()["products"]]  # type: ignore[index]
    documents = (
        _document(_fixture("online_v6_category_tree.json"), kind=ICA_CATEGORY_TREE_KIND),
        _document(
            _page(),
            kind=ICA_PRODUCT_PAGE_KIND,
            query={"category_id": CATEGORY_ID, "page_index": "0"},
            page_number=0,
        ),
        _document(
            _batch(),
            kind=ICA_PRODUCT_BATCH_KIND,
            query={
                "category_id": CATEGORY_ID,
                "page_index": "0",
                "batch_index": "0",
                "requested_product_ids": json.dumps(requested_ids),
            },
            page_number=0,
        ),
    )

    result = IcaOnlineCatalogParser().parse_catalog(
        RawBatch(chain=Chain.ICA, documents=documents),
        ["raw:tree", "raw:page", "raw:batch"],
        _store(),
    )

    assert result.products == []
    assert len(result.failures) == 1
    assert "unresolved" in result.failures[0].error_message.casefold()
