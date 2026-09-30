"""Fail closed except for the observed Willys energy-label image variation."""

import pytest

from grocery_data.app.domain import Chain
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange
from grocery_data.app.services.collector import _review_schema_diff


@pytest.mark.parametrize("store", ["2354", "2176"])
@pytest.mark.parametrize(
    ("before", "after"),
    [(("string",), ("null", "string")), (("null", "string"), ("string",))],
)
def test_observed_nullable_image_label_is_reviewed_for_current_parser(
    store, before, after
):
    diff = SchemaDiff(
        type_changed=(
            SchemaTypeChange(
                path=f"{store}:catalog_page:$[].results[].energyDeclaration.image",
                old_types=before,
                new_types=after,
            ),
        )
    )
    assert _review_schema_diff(Chain.WILLYS, "willys-parser-v3", diff) is None
    assert _review_schema_diff(Chain.WILLYS, "willys-parser-v2", diff) == diff
    assert _review_schema_diff(Chain.HEMKOP, "willys-parser-v3", diff) == diff


@pytest.mark.parametrize(
    ("path", "before", "after"),
    [
        ("results[].energyDeclaration.image", ("string",), ("number",)),
        ("results[].energyDeclaration.value", ("string",), ("null", "string")),
        ("results[].priceValue", ("number",), ("string",)),
        ("results", ("array",), ("object",)),
    ],
)
def test_other_type_changes_remain_blocked(path, before, after):
    diff = SchemaDiff(
        type_changed=(
            SchemaTypeChange(
                path=f"2354:catalog_page:$[].{path}",
                old_types=before,
                new_types=after,
            ),
        )
    )
    assert _review_schema_diff(Chain.WILLYS, "willys-parser-v3", diff) == diff


def test_added_or_removed_fields_remain_blocked():
    path = "2354:catalog_page:$[].results[].priceValue"
    diff = SchemaDiff(added=(path,), removed=(path,))
    assert _review_schema_diff(Chain.WILLYS, "willys-parser-v3", diff) == diff
