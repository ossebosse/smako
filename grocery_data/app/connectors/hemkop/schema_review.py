"""Shape variations already supported by HemkopParser v1.

Current 2026-09-27 raw evidence contains an EPREL lamp energy label, not
food nutrition, in energyDeclaration. These descriptive fields are unused
by the product/price parser. Results may omit null from the aggregate type
set when no category happens to need the exact-page terminal sentinel.
validated_catalog_page still checks every page's total, length and terminal
shape; the schema review cannot establish completeness on its own.
"""
import re

from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.monitoring.schema_fingerprint import SchemaTypeChange

_PREFIX = r"(?:[0-9]+:)?catalog_page:\$\[\]\.results"
_LABEL = re.compile(_PREFIX + r"\[\]\.energyDeclaration(?:\.(?:link|value|image))?\Z")
_LABEL_ROOT = re.compile(_PREFIX + r"\[\]\.energyDeclaration\Z")
_RESULTS = re.compile(_PREFIX + r"\Z")


def reviewed_hemkop_type_change(change: SchemaTypeChange) -> bool:
    before, after = set(change.old_types), set(change.new_types)
    if _RESULTS.fullmatch(change.path):
        # Only disappearance of a terminal-null sample is reviewed here.
        return before == {"null", "array"} and after == {"array"}
    if _LABEL_ROOT.fullmatch(change.path):
        return (before, after) in [
            ({"null"}, {"null", "object"}),
            ({"null", "object"}, {"null"}),
        ]
    return False


def reviewed_hemkop_schema_diff(diff: SchemaDiff) -> SchemaDiff:
    return SchemaDiff(
        added=tuple(path for path in diff.added if not _LABEL.fullmatch(path)),
        removed=tuple(path for path in diff.removed if not _LABEL.fullmatch(path)),
        type_changed=tuple(c for c in diff.type_changed if not reviewed_hemkop_type_change(c)),
    )
