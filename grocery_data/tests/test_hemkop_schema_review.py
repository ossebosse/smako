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
