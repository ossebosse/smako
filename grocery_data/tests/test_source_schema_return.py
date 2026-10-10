"""Exact retained Oct 9 failures; semantic store/price guards remain independent."""
import json
from pathlib import Path

import pytest

from grocery_data.app.connectors.hemkop.models import validated_store_context
from grocery_data.app.domain import Chain
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange
from grocery_data.app.services.collector import _review_schema_diff

ROWS = json.loads((Path(__file__).parent / "fixtures/source-schema-return-20261010.json").read_text(encoding="utf8"))


@pytest.mark.parametrize("record", [r for r in ROWS if r["diff"]], ids=lambda r: r["snapshot_id"])
def test_authentic_rejected_diff_is_reviewed(record):
    diff = SchemaDiff.model_validate(record["diff"])
    schemas = {p.rsplit(":", 1)[0]: {"paths": {p.rsplit(":", 1)[1].replace("hasPickingBaseStore", "storeId"): ["string"]}} for p in diff.removed}
    assert _review_schema_diff(Chain(record["chain"]), record["parser_version"], diff, schemas=schemas) is None
    if record["chain"] == "hemkop":
        for sample in record["samples"]:
            row = sample["fields"]
            assert "hasPickingBaseStore" not in row
            assert validated_store_context(row, row["storeId"])
            assert not validated_store_context(row, "wrong")


@pytest.mark.parametrize("group", ["image", "thumbnail"])
@pytest.mark.parametrize("field", ["url", "format", "imageType"])
@pytest.mark.parametrize("types", [("number",), ("object",), ("null", "boolean"), ("null",)])
def test_image_review_does_not_accept_other_types(group, field, types):
    diff = SchemaDiff(type_changed=(SchemaTypeChange(path=f"2354:catalog_page:$[].results[].{group}.{field}", old_types=("null", "string"), new_types=types),))
    assert _review_schema_diff(Chain.WILLYS, "willys-parser-v3", diff) == diff


@pytest.mark.parametrize("path", ["results[].priceValue", "results[].potentialPromotions", "results[].image.price", "storeId"])
def test_commercial_or_unknown_schema_change_still_blocks(path):
    diff = SchemaDiff(type_changed=(SchemaTypeChange(path=f"2354:catalog_page:$[].{path}", old_types=("null", "string"), new_types=("string",)),))
    assert _review_schema_diff(Chain.WILLYS, "willys-parser-v3", diff) == diff


@pytest.mark.parametrize("schemas", [None, {}, {"4123:store_context": {"paths": {}}}, {"4123:store_context": {"paths": {"$[].storeId": ["string"], "$[].hasPickingBaseStore": ["null"]}}}])
def test_missing_picking_flag_needs_present_store_schema(schemas):
    diff = SchemaDiff(removed=("4123:store_context:$[].hasPickingBaseStore",))
    assert _review_schema_diff(Chain.HEMKOP, "hemkop-parser-v1.1-picking-contract", diff, schemas=schemas) == diff


def test_optional_removal_does_not_hide_missing_identity_or_unknown_fields():
    keys=("4123:store_context:$[].hasPickingBaseStore", "4123:store_context:$[].storeId", "4123:store_context:$[].priceArea")
    diff=SchemaDiff(removed=keys)
    assert _review_schema_diff(Chain.HEMKOP,"hemkop-parser-v1.1-picking-contract",diff,schemas={"4123:store_context":{"paths":{}}})==diff
    assert _review_schema_diff(Chain.HEMKOP,"hemkop-parser-v1",diff,schemas={"4123:store_context":{"paths":{"$[].storeId":["string"]}}})==diff
