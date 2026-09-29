"""Reviewed optional shape variation for the existing online parser v1.

The 2026-09-27 Lund capture added the two percentage diagnostics already
parsed (and retained) by v1, and omitted localProduct's descriptive badge.
The payable promotion price still comes from priceData/price, never from a
percentage calculation. Identity, validity and explicit membership checks
remain in the parser. Raw schema differences remain persisted for review.
"""
from __future__ import annotations

import re

from grocery_data.app.monitoring import SchemaDiff

_OPTIONAL_PATH = re.compile(
    r"(?:[0-9]+:)?coop_product_category_page:\$\[\]\.results\.items\[\]\."
    r"(?:onlinePromotions\[\]\.(?:adjustedPercentageDiscount|percentageDiscount)"
    r"|localProduct(?:\.(?:code|description|imageUrl|priority))?)\Z"
)


def reviewed_coop_online_schema_diff(diff: SchemaDiff) -> SchemaDiff:
    """Review only the enumerated optional paths; never review type changes."""
    return SchemaDiff(
        added=tuple(path for path in diff.added if not _OPTIONAL_PATH.fullmatch(path)),
        removed=tuple(path for path in diff.removed if not _OPTIONAL_PATH.fullmatch(path)),
        type_changed=diff.type_changed,
    )
