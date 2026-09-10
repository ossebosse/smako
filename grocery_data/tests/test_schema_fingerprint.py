from grocery_data.app.monitoring.schema_fingerprint import (
    JsonType,
    diff_json_schemas,
    fingerprint_json,
)


def test_fingerprint_is_stable_across_values_key_order_and_record_order() -> None:
    first = {
        "products": [
            {"name": "Pasta", "price": 19.9, "available": True},
            {"name": "Rice", "price": 22, "available": False},
        ],
        "meta": {"count": 2},
    }
    second = {
        "meta": {"count": 999},
        "products": [
            {"available": False, "price": 1, "name": "Different"},
            {"price": 2.5, "name": "Another", "available": True},
        ],
    }

    old = fingerprint_json(first)
    new = fingerprint_json(second)

    assert old.digest == new.digest
    assert old.paths["$.products"] == (JsonType.ARRAY,)
    assert old.paths["$.products[].price"] == (JsonType.NUMBER,)


def test_schema_diff_reports_added_removed_and_type_changed_paths() -> None:
    old = {
        "product": {
            "name": "Pasta",
            "price": 20,
            "packageSize": "500 g",
            "legacy": True,
        }
    }
    new = {
        "product": {
            "name": "Pasta",
            "price": 21,
            "packageSize": {"value": 500, "unit": "g"},
            "gtin": "7312345678901",
        }
    }

    diff = diff_json_schemas(old, new)

    assert "$.product.gtin" in diff.added
    assert "$.product.packageSize.value" in diff.added
    assert "$.product.legacy" in diff.removed
    change = next(item for item in diff.type_changed if item.path == "$.product.packageSize")
    assert change.old_types == (JsonType.STRING,)
    assert change.new_types == (JsonType.OBJECT,)
    assert diff.has_changes


def test_array_path_types_are_unions_not_index_specific() -> None:
    fingerprint = fingerprint_json({"values": ["known", None, "other"]})

    assert fingerprint.paths["$.values[]"] == (JsonType.NULL, JsonType.STRING)
