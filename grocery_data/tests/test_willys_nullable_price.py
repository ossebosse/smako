"""The retained Malmö price-null incident must not discard four entire stores."""
from datetime import UTC, datetime

import pytest

from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import Chain, CoverageLevel, SourceStore
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange
from grocery_data.app.services.collector import _review_schema_diff


@pytest.mark.parametrize('store', ['2114', '2144', '2244', '2253', '999999'])
@pytest.mark.parametrize('reverse', [False, True])
def test_reviewed_nullable_number_requires_new_parser(store, reverse):
    before, after = ('number',), ('null', 'number')
    if reverse:
        before, after = after, before
    diff = SchemaDiff(type_changed=(SchemaTypeChange(
        path=f'{store}:catalog_page:$[].results[].priceValue',
        old_types=before, new_types=after),))
    assert _review_schema_diff(Chain.WILLYS, 'willys-parser-v5', diff) is None
    assert _review_schema_diff(Chain.WILLYS, 'willys-parser-v4', diff) == diff


@pytest.mark.parametrize('types', [('null',), ('string',), ('boolean',), ('object',), ('null', 'number', 'string')])
def test_other_price_types_still_block(types):
    diff = SchemaDiff(type_changed=(SchemaTypeChange(
        path='2114:catalog_page:$[].results[].priceValue',
        old_types=('number',), new_types=types),))
    assert _review_schema_diff(Chain.WILLYS, 'willys-parser-v5', diff) == diff


def test_missing_price_never_becomes_free_or_uses_promotion_fallback():
    store = SourceStore(chain=Chain.WILLYS, external_id='2114', name='Willys',
        city='Malmö', coverage=CoverageLevel.FULL_CATALOG, raw_reference='retained:store')
    product = WillysParser()._parse_product(
        {'code': '101774905_ST', 'name': 'Äppelblom Ättiksspray Allrengöring',
         'priceValue': None, 'salesPrice': None, 'priceUnit': 'kr/st',
         'outOfStock': False, 'online': True}, store, 'retained:row', datetime.now(UTC))
    assert product.sale_price is product.regular_price is product.sale_unit is None
    assert product.availability == 'available'
    assert WillysParser()._price({'priceValue': None, 'potentialPromotions': [
        {'price': {'value': 22.5}}]}) is None
