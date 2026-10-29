"""Reviewed optional shape variation for the existing online parser v1.

The 2026-09-27 Lund capture added the two percentage diagnostics already
parsed (and retained) by v1, and omitted localProduct's descriptive badge.
The payable promotion price still comes from priceData/price, never from a
percentage calculation. Identity, validity and explicit membership checks
remain in the parser. Raw schema differences remain persisted for review.

The 2026-10-13 full 730400 capture adds energy-label presentation metadata
and omits accreditedTags[].priority. Parser v3 does not consume these fields;
only these exact optional paths are reviewed, without accepting type changes.
"""
from __future__ import annotations

import re

from grocery_data.app.monitoring import SchemaDiff

_OPTIONAL_PATH = re.compile(
    r"(?:[0-9]+:)?coop_product_category_page:\$\[\]\.results\.items\[\]\."
    r"(?:onlinePromotions\[\]\.(?:adjustedPercentageDiscount|percentageDiscount)"
    r"|localProduct(?:\.(?:code|description|imageUrl|priority))?)\Z"
)
_PRESENTATION_PATH = re.compile(
    r"(?:[0-9]+:)?coop_product_category_page:\$\[\]\.results\.items\[\]\."
    r"(?:energyLabel(?:\.(?:accessibilityText|energyClass|productSheetUrl|smallImageUrl))?"
    r"|accreditedTags\[\]\.priority)\Z"
)


_LIMIT_PATH = re.compile(
    r"730400:coop_product_category_page:\$\[\]\.results\.items\[\]\."
    r"onlinePromotions\[\]\.(?:maxNumberOfUse|maxNumberOfUseWithUnit(?:\.(?:unit|value))?)\Z"
)


def reviewed_coop_online_schema_diff(
    diff: SchemaDiff, *, presentation_metadata: bool = False, withheld_unknown_limits: bool = False,
) -> SchemaDiff:
    """Review only the enumerated optional paths; never review type changes."""
    def reviewed(path: str) -> bool:
        return bool(_OPTIONAL_PATH.fullmatch(path) or (
            presentation_metadata and _PRESENTATION_PATH.fullmatch(path)
        ))

    return SchemaDiff(
        added=tuple(path for path in diff.added if not reviewed(path)),
        removed=tuple(path for path in diff.removed if not reviewed(path)
                      and not (withheld_unknown_limits and _LIMIT_PATH.fullmatch(path))),
        type_changed=diff.type_changed,
    )
