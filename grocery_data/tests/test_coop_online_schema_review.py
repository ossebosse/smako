import pytest

from grocery_data.app.domain import Chain
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange
from grocery_data.app.services.collector import _review_schema_diff

VERSION = "coop-online-catalog-parser-v1"


@pytest.mark.parametrize("context", ["730400:", "987654:", ""])
def test_reviewed_optional_fields_do_not_require_a_new_catalog_approval(context):
    prefix = context + "coop_product_category_page:$[].results.items[]."
    diff = SchemaDiff(
        added=tuple(prefix + "onlinePromotions[]." + field for field in
                    ("percentageDiscount", "adjustedPercentageDiscount")),
        removed=tuple(prefix + field for field in
                      ("localProduct", "localProduct.code", "localProduct.description",
                       "localProduct.imageUrl", "localProduct.priority")),
    )
    assert _review_schema_diff(Chain.COOP, VERSION, diff) is None
    # The raw evidence is immutable, and optional absence works on the next issue.
    assert len(diff.added) == 2 and len(diff.removed) == 5
    assert _review_schema_diff(Chain.COOP, VERSION,
                              SchemaDiff(added=diff.removed, removed=diff.added)) is None


@pytest.mark.parametrize("field", [
    "price", "gtin", "onlinePromotions[].priceData",
    "onlinePromotions[].medMeraRequired", "onlinePromotions[].startDate",
    "onlinePromotions[].maxNumberOfUseWithUnit", "localProduct.newRestriction",
    "onlinePromotions[].unknownDiscount",
])
def test_unreviewed_price_identity_and_condition_changes_still_block(field):
    prefix = "730400:coop_product_category_page:$[].results.items[]."
    critical = prefix + field
    diff = SchemaDiff(added=(prefix + "localProduct.code", critical), removed=(critical,))
    assert _review_schema_diff(Chain.COOP, VERSION, diff) == SchemaDiff(
        added=(critical,), removed=(critical,))


def test_review_is_version_chain_surface_and_type_bound():
    path = "730400:coop_product_category_page:$[].results.items[].localProduct.code"
    diff = SchemaDiff(added=(path,))
    assert _review_schema_diff(Chain.COOP, "coop-parser-v1", diff) == diff
    assert _review_schema_diff(Chain.COOP, "coop-online-catalog-parser-v2", diff) == diff
    assert _review_schema_diff(Chain.ICA, VERSION, diff) == diff
    wrong_surface = SchemaDiff(added=(path.replace("category_page", "offer_page"),))
    assert _review_schema_diff(Chain.COOP, VERSION, wrong_surface) == wrong_surface
    typed = SchemaDiff(type_changed=(SchemaTypeChange(
        path=path, old_types=("string",), new_types=("object",)),))
    assert _review_schema_diff(Chain.COOP, VERSION, typed) == typed
