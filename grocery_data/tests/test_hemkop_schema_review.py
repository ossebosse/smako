import pytest

from grocery_data.app.connectors.hemkop.parser import HemkopParser
from grocery_data.app.domain import Chain
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange
from grocery_data.app.services.collector import _review_schema_diff


@pytest.mark.parametrize('store', ['4123', '4224', '9999'])
@pytest.mark.parametrize('before,after', [
    (('null', 'array'), ('array',)),
    (('array',), ('null', 'array')),
])
def test_real_current_nullable_label_and_terminal_sample_change(store, before, after):
    prefix = store + ':catalog_page:$[].results'
    diff = SchemaDiff(
        added=tuple(prefix + '[].energyDeclaration.' + k for k in ['image', 'link', 'value']),
        type_changed=(
            SchemaTypeChange(path=prefix, old_types=before, new_types=after),
            SchemaTypeChange(path=prefix+'[].energyDeclaration', old_types=('null',),
                             new_types=('null', 'object')),
        ),
    )
    assert _review_schema_diff(Chain.HEMKOP, 'hemkop-parser-v1', diff) is None
    assert _review_schema_diff(Chain.HEMKOP, HemkopParser.parser_version, diff) is None
    assert _review_schema_diff(Chain.WILLYS, 'hemkop-parser-v1', diff) == diff
    assert _review_schema_diff(Chain.HEMKOP, 'hemkop-parser-v2', diff) == diff


@pytest.mark.parametrize('path,old,new', [
    ('results', ('array',), ('object',)),
    ('results[].energyDeclaration', ('null',), ('string',)),
    ('results[].energyDeclaration.value', ('string',), ('number',)),
    ('results[].priceValue', ('number',), ('string',)),
    ('results[].campaigns', ('array',), ('null',)),
])
def test_unreviewed_type_changes_still_block(path, old, new):
    diff = SchemaDiff(type_changed=(SchemaTypeChange(
        path='4123:catalog_page:$[].'+path, old_types=old, new_types=new),))
    assert _review_schema_diff(Chain.HEMKOP, 'hemkop-parser-v1', diff) == diff
    assert _review_schema_diff(Chain.HEMKOP, HemkopParser.parser_version, diff) == diff


@pytest.mark.parametrize('path', ['results', 'results[].priceValue',
    'results[].potentialPromotions', 'results[].energyDeclaration.restriction'])
def test_other_missing_or_added_fields_still_block(path):
    key='4123:catalog_page:$[].'+path
    diff=SchemaDiff(added=(key,),removed=(key,))
    assert _review_schema_diff(Chain.HEMKOP, 'hemkop-parser-v1', diff) == diff
    assert _review_schema_diff(Chain.HEMKOP, HemkopParser.parser_version, diff) == diff


_OFFERS = "hemkop-physical-offers-v2"
_STORE_SCHEMA = {"stores": {"paths": {"$[][].hasPickingBaseStore": ["boolean"], "$[][].storeId": ["string"]}}}


def test_physical_offers_accept_observed_nullable_rotation_and_picking_flag():
    # Exact diffs that rejected every Lund/Malmö run from 2026-10-29.
    diff = SchemaDiff(
        added=("stores:$[][].hasPickingBaseStore",),
        removed=(),
        type_changed=(
            SchemaTypeChange(path="4224:physical_offers:$[].results[].price",
                             old_types=("string",), new_types=("null", "string")),
            SchemaTypeChange(path="4224:physical_offers:$[].results[].priceNoUnit",
                             old_types=("string",), new_types=("null", "string")),
            SchemaTypeChange(path="4123:physical_offers:$[].results[].potentialPromotions[].redeemLimit",
                             old_types=("null", "number"), new_types=("null",)),
            SchemaTypeChange(path="4123:physical_offers:$[].results[].potentialPromotions[].promotionRedeemLimit",
                             old_types=("null", "number"), new_types=("null",)),
        ),
    )
    assert _review_schema_diff(Chain.HEMKOP, _OFFERS, diff, schemas=_STORE_SCHEMA) is None


@pytest.mark.parametrize("change", [
    SchemaTypeChange(path="4123:physical_offers:$[].results[].price",
                     old_types=("string",), new_types=("number",)),
    SchemaTypeChange(path="4123:physical_offers:$[].results[].potentialPromotions[].price",
                     old_types=("number",), new_types=("null", "number")),
    SchemaTypeChange(path="4123:physical_offers:$[].results[].potentialPromotions[].redeemLimit",
                     old_types=("number",), new_types=("null", "string")),
])
def test_physical_offers_other_type_changes_still_block(change):
    diff = SchemaDiff(added=(), removed=(), type_changed=(change,))
    reviewed = _review_schema_diff(Chain.HEMKOP, _OFFERS, diff, schemas=_STORE_SCHEMA)
    assert reviewed is not None and reviewed.type_changed == (change,)


def test_physical_offers_unknown_additions_and_bad_flag_type_still_block():
    diff = SchemaDiff(added=("4123:physical_offers:$[].results[].newField",
                             "stores:$[][].hasPickingBaseStore"), removed=(), type_changed=())
    bad = {"stores": {"paths": {"$[][].hasPickingBaseStore": ["string"]}}}
    reviewed = _review_schema_diff(Chain.HEMKOP, _OFFERS, diff, schemas=bad)
    assert set(reviewed.added) == set(diff.added)
    reviewed = _review_schema_diff(Chain.HEMKOP, _OFFERS, diff, schemas=_STORE_SCHEMA)
    assert reviewed.added == ("4123:physical_offers:$[].results[].newField",)
