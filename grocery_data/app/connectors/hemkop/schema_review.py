"""Shape variations already supported by HemkopParser v1.

Current 2026-09-27 raw evidence contains an EPREL lamp energy label, not
food nutrition, in energyDeclaration. These descriptive fields are unused
by the product/price parser. Results may gain or lose null in the aggregate
type set according to whether a category needs the exact-page terminal
sentinel. The 2026-09-29 Karhögstorg run gained null at this exact path.
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
_PICKING = re.compile(r"(?:[0-9]+:store_context:\$\[\]|stores:\$\[\]\[\])\.hasPickingBaseStore\Z")


def reviewed_hemkop_type_change(change: SchemaTypeChange) -> bool:
    before, after = set(change.old_types), set(change.new_types)
    if _RESULTS.fullmatch(change.path):
        # Every page is independently checked for exact pagination and the
        # proven null sentinel before this aggregate review.
        return (before, after) in [
            ({"null", "array"}, {"array"}),
            ({"array"}, {"null", "array"}),
        ]
    if _LABEL_ROOT.fullmatch(change.path):
        return (before, after) in [
            ({"null"}, {"null", "object"}),
            ({"null", "object"}, {"null"}),
        ]
    return False


def reviewed_hemkop_schema_diff(diff: SchemaDiff, *, schemas=None, picking_contract=False) -> SchemaDiff:
    def reviewed_addition(path):
        if _LABEL.fullmatch(path):
            return True
        if not picking_contract or not re.fullmatch(
            r"(?:[0-9]+:store_context:\$\[\]|stores:\$\[\]\[\])\.hasPickingBaseStore", path
        ):
            return False
        group, field = path.rsplit(":", 1)
        schema = (schemas or {}).get(group)
        paths = schema.get("paths", {}) if isinstance(schema, dict) else getattr(schema, "paths", {})
        # Value semantics are independently checked by parser and transport.
        return set(paths.get(field, ())) == {"boolean"}

    def reviewed_removal(path):
        if _LABEL.fullmatch(path):
            return True
        if not picking_contract or not _PICKING.fullmatch(path):
            return False
        group, field = path.rsplit(":", 1)
        schema = (schemas or {}).get(group)
        paths = schema.get("paths", {}) if isinstance(schema, dict) else getattr(schema, "paths", {})
        # Oct 9 retained responses omit this optional flag again. Absence is
        # already supported by validated_store_context; never synthesize false.
        # The group and exact store identity must still exist. Present invalid
        # flag values and any removed identity/binding fields remain blocked.
        identity = field.removesuffix("hasPickingBaseStore") + "storeId"
        return field not in paths and set(paths.get(identity, ())) == {"string"}

    return SchemaDiff(
        added=tuple(path for path in diff.added if not reviewed_addition(path)),
        removed=tuple(path for path in diff.removed if not reviewed_removal(path)),
        type_changed=tuple(c for c in diff.type_changed if not reviewed_hemkop_type_change(c)),
    )


# Physical campaign source (hemkop-physical-offers-v2). Row prices are never
# read from the product row; promotion price, dates and limits are validated
# per row by physical_offers.parse. Week-to-week these optional fields gain or
# lose null as campaigns with/without ordinary price or purchase limits rotate.
_OFFER_PREFIX = r"(?:[0-9]+:)?physical_offers:\$\[\]\.results\[\]"
_OFFER_NULLABLE = {
    re.compile(_OFFER_PREFIX + r"\.(?:price|priceNoUnit|displayVolume|promotionProductOrdinaryComparePriceUnit)\Z"): {"string"},
    re.compile(_OFFER_PREFIX + r"\.potentialPromotions\[\]\.(?:redeemLimit|promotionRedeemLimit)\Z"): {"number"},
}


def reviewed_hemkop_physical_offer_type_change(change: SchemaTypeChange) -> bool:
    before, after = set(change.old_types), set(change.new_types)
    for pattern, allowed in _OFFER_NULLABLE.items():
        if pattern.fullmatch(change.path):
            # Only null and the field's single reviewed type may come and go;
            # any other non-null type is blocked.
            union = {str(t) for t in before | after}
            return "null" in union and union <= allowed | {"null"}
    return False


def reviewed_hemkop_physical_offer_schema_diff(diff: SchemaDiff, *, schemas=None) -> SchemaDiff:
    picking = reviewed_hemkop_schema_diff(
        SchemaDiff(added=diff.added, removed=diff.removed, type_changed=()),
        schemas=schemas, picking_contract=True,
    )
    def store_flag(path):
        return _PICKING.fullmatch(path) is not None
    return SchemaDiff(
        added=tuple(path for path in diff.added if path in picking.added or not store_flag(path)),
        removed=tuple(path for path in diff.removed if path in picking.removed or not store_flag(path)),
        type_changed=tuple(c for c in diff.type_changed if not reviewed_hemkop_physical_offer_type_change(c)),
    )
