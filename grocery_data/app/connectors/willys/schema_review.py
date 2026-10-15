"""Review the observed nullable image label in Willys catalog responses.

The 2026-09-30 Lund municipal source artifact added a null image value to
``energyDeclaration`` in store 2354. WillysParser v3 never reads this energy
label for price, quantity or nutrition. The 2026-10-09 retained snapshot
75f802ebbfcc410c9d65e356746f0816 also narrows six presentation-only
image/thumbnail text fields from nullable text to text. These exact nullable
text shapes are supported in either direction. Parser v5 additionally reviews
the observed number/nullable-number catalog price transition. Missing prices
remain missing and ordinary quality gates apply. The raw diff is retained;
other schema changes still stop snapshot promotion. Parser v6 additionally
reviews the explicit boolean picking-base metadata observed on 2026-10-14.
Transport, parsing and independent artifact qualification enforce its value
and exact store binding; the fingerprint exception alone cannot authorize it.
"""

import re

from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange

_LABEL_IMAGE = re.compile(
    r"[0-9]+:catalog_page:\$\[\]\.results\[\]\.energyDeclaration\.image\Z"
)

_PRODUCT_IMAGE_TEXT = re.compile(
    r"[0-9]+:catalog_page:\$\[\]\.results\[\]\.(?:image|thumbnail)\.(?:format|imageType|url)\Z"
)

_CATALOG_PRICE = re.compile(r"[0-9]+:catalog_page:\$\[\]\.results\[\]\.priceValue\Z")
_PICKING = re.compile(
    r"(?:[0-9]+:store_context:\$\[\]|stores:\$\[\]\[\])\.hasPickingBaseStore\Z"
)


def reviewed_willys_type_change(change: SchemaTypeChange, *, nullable_price: bool = False) -> bool:
    # Retained Malmö 2026-10-12: one cleaning product per store has no price.
    # Parser preserves None (never zero or promotion fallback); normal health
    # and purchasability gates still apply. All-null/type/removal changes stop.
    if nullable_price and _CATALOG_PRICE.fullmatch(change.path):
        return (set(change.old_types), set(change.new_types)) in [
            ({"number"}, {"null", "number"}),
            ({"null", "number"}, {"number"}),
        ]
    if not (_LABEL_IMAGE.fullmatch(change.path) or _PRODUCT_IMAGE_TEXT.fullmatch(change.path)):
        return False
    before, after = set(change.old_types), set(change.new_types)
    return (before, after) in [
        ({"string"}, {"null", "string"}),
        ({"null", "string"}, {"string"}),
    ]


def reviewed_willys_schema_diff(
    diff: SchemaDiff, *, nullable_price: bool = False, picking_contract: bool = False,
    schemas=None,
) -> SchemaDiff:
    def reviewed_picking(path, *, removal=False):
        if not picking_contract or not _PICKING.fullmatch(path):
            return False
        group, field = path.rsplit(":", 1)
        schema = (schemas or {}).get(group)
        paths = schema.get("paths", {}) if isinstance(schema, dict) else getattr(schema, "paths", {})
        identity = field.removesuffix("hasPickingBaseStore") + "storeId"
        if set(paths.get(identity, ())) != {"string"}:
            return False
        # Parser and transport independently require explicit false when
        # present. Missing remains supported, never synthesized as false.
        return field not in paths if removal else set(paths.get(field, ())) == {"boolean"}

    return SchemaDiff(
        added=tuple(p for p in diff.added if not reviewed_picking(p)),
        removed=tuple(p for p in diff.removed if not reviewed_picking(p, removal=True)),
        type_changed=tuple(
            change for change in diff.type_changed
            if not reviewed_willys_type_change(change, nullable_price=nullable_price)
        ),
    )
