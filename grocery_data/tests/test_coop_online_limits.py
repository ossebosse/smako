"""Missing purchase limits must never turn into an unlimited discount."""
from decimal import Decimal

import pytest

from grocery_data.app.connectors.coop.online_catalog_parser import CoopOnlineCatalogParser
from grocery_data.app.domain import Chain
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange
from grocery_data.app.services.collector import _review_schema_diff
from grocery_data.tests.test_coop_online_catalog_parser import OBSERVED_AT, _fixture_row, _store

VERSION = "coop-online-catalog-parser-v4"
PREFIX = "730400:coop_product_category_page:$[].results.items[].onlinePromotions[]."
PATHS = tuple(PREFIX + field for field in (
    "maxNumberOfUse", "maxNumberOfUseWithUnit", "maxNumberOfUseWithUnit.unit", "maxNumberOfUseWithUnit.value"))


def test_only_exact_cap_removals_are_reviewed_by_the_withholding_parser():
    diff = SchemaDiff(removed=PATHS)
    assert _review_schema_diff(Chain.COOP, VERSION, diff) is None
    assert _review_schema_diff(Chain.COOP, "coop-online-catalog-parser-v3", diff) == diff
    for changed in (SchemaDiff(added=PATHS), SchemaDiff(removed=(PATHS[0].replace("730400", "999"),)),
                    SchemaDiff(removed=(PREFIX + "medMeraRequired",)),
                    SchemaDiff(type_changed=(SchemaTypeChange(path=PATHS[0], old_types=("number",), new_types=("string",)),))):
        assert _review_schema_diff(Chain.COOP, VERSION, changed) == changed


@pytest.mark.parametrize("limit", [None, {}, {"unit": "Kilogram", "value": 5},
    {"unit": "Styck", "value": 0}, {"unit": "Styck", "value": -1},
    {"unit": "Styck", "value": 1.5}, {"unit": "Styck", "value": True},
    {"unit": "Styck", "value": "unlimited"}, {"unit": "Styck", "value": "5 kg"}])
def test_unverified_limit_keeps_base_and_withholds_both_offer_and_effective_discount(limit):
    row = _fixture_row("online_api_soy_promotion_730400.json")
    for promotion in row["onlinePromotions"]:
        if limit is not None:
            promotion.update(maxNumberOfUse=4500, maxNumberOfUseWithUnit=limit)
    product = CoopOnlineCatalogParser().parse_product(row, store=_store(), reference="synthetic:limit", fetched_at=OBSERVED_AT)
    assert product.regular_price == product.sale_price == Decimal("28.35")
    assert not product.offers and product.member_price is None
    assert product.source_fields["withheld_unverified_limit_promotion_ids"]
    assert product.fetched_at == OBSERVED_AT


def test_verified_piece_cap_is_retained_in_offer_and_missing_raw_limit_is_not_accepted():
    row = _fixture_row("online_api_soy_promotion_730400.json")
    for promotion in row["onlinePromotions"]:
        promotion.update(maxNumberOfUse=4500, maxNumberOfUseWithUnit={"unit": "Styck", "value": 5.0})
    parser = CoopOnlineCatalogParser()
    product = parser.parse_product(row, store=_store(), reference="synthetic:limit", fetched_at=OBSERVED_AT)
    assert product.sale_price == Decimal("19.9") and product.offers[0].max_quantity == 5
    for promotion in row["onlinePromotions"]:
        del promotion["maxNumberOfUse"]
    product = parser.parse_product(row, store=_store(), reference="synthetic:limit", fetched_at=OBSERVED_AT)
    assert not product.offers and product.sale_price == product.regular_price
