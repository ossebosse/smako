"""Review the observed nullable image label in Willys catalog responses.

The 2026-09-30 Lund municipal source artifact added a null image value to
``energyDeclaration`` in store 2354. WillysParser v3 never reads this energy
label for price, quantity or nutrition. The 2026-10-09 retained snapshot
75f802ebbfcc410c9d65e356746f0816 also narrows six presentation-only
image/thumbnail text fields from nullable text to text. These exact nullable
text shapes are supported in either direction; neither image structure nor
commercial fields are exempted. The raw diff is retained. Other schema changes still stop
snapshot promotion.
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


def reviewed_willys_type_change(change: SchemaTypeChange) -> bool:
    if not (_LABEL_IMAGE.fullmatch(change.path) or _PRODUCT_IMAGE_TEXT.fullmatch(change.path)):
        return False
    before, after = set(change.old_types), set(change.new_types)
    return (before, after) in [
        ({"string"}, {"null", "string"}),
        ({"null", "string"}, {"string"}),
    ]


def reviewed_willys_schema_diff(diff: SchemaDiff) -> SchemaDiff:
    return SchemaDiff(
        added=diff.added,
        removed=diff.removed,
        type_changed=tuple(
            change for change in diff.type_changed if not reviewed_willys_type_change(change)
        ),
    )
