"""Type summaries never replace actual purchase conditions or price evidence."""
from decimal import Decimal

import pytest

from grocery_data.app.connectors.coop.online_catalog_parser import CoopOnlineCatalogParser
from grocery_data.app.domain import Chain
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange
from grocery_data.app.services.collector import _review_schema_diff
from grocery_data.tests.test_coop_online_catalog_parser import OBSERVED_AT, _capped_fixture, _store

VERSION = "coop-online-catalog-parser-v5"
PREFIX = "730400:coop_product_category_page:$[].results.items[]."


def test_only_exact_summary_and_image_paths_are_reviewed_in_v5():
    paths = tuple(PREFIX + field for field in ("availablePromotions", "availablePromotions[]", "energyLabel.imageUrl"))
    assert _review_schema_diff(Chain.COOP, VERSION, SchemaDiff(added=paths)) is None
    assert _review_schema_diff(Chain.COOP, "coop-online-catalog-parser-v4", SchemaDiff(added=paths))
    for path in (paths[0].replace("730400", "999"), PREFIX + "availablePromotions[].price", PREFIX + "energyLabel.restriction"):
        diff = SchemaDiff(added=(path,))
        assert _review_schema_diff(Chain.COOP, VERSION, diff) == diff
    typed = SchemaDiff(type_changed=(SchemaTypeChange(path=paths[1], old_types=("string",), new_types=("object",)),))
    assert _review_schema_diff(Chain.COOP, VERSION, typed) == typed


@pytest.mark.parametrize("summary,accepted", [(["FIXED_PRICE"], True), ([], False),
    (["MULTI_BUY_FIXED_PRICE"], False), (["PERSONAL_PRICE"], False),
    (["FIXED_PRICE", "FIXED_PRICE"], False), (None, False), ("FIXED_PRICE", False),
    ([{"price": 1}], False)])
def test_summary_must_match_actual_promotions_or_only_base_price_survives(summary, accepted):
    row = _capped_fixture("online_api_soy_promotion_730400.json")["results"]["items"][0]
    row["availablePromotions"] = summary
    product = CoopOnlineCatalogParser().parse_product(row, store=_store(), reference="synthetic:summary", fetched_at=OBSERVED_AT)
    assert bool(product.offers) is accepted
    assert product.regular_price == Decimal("28.35")
    assert product.sale_price == (Decimal("19.9") if accepted else product.regular_price)
    assert product.source_fields["available_promotion_summary_verified"] is accepted
    assert product.source_fields["available_promotion_types"] == summary
    if accepted:
        # A matching summary still cannot establish an absent purchase limit.
        for promotion in row["onlinePromotions"]:
            promotion.pop("maxNumberOfUseWithUnit")
        product = CoopOnlineCatalogParser().parse_product(row, store=_store(), reference="synthetic:summary", fetched_at=OBSERVED_AT)
        assert not product.offers and product.sale_price == product.regular_price
