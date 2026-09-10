from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class InvalidGtinError(ValueError):
    """A scanned/source identifier is not a checksum-valid supported GTIN."""


class NormalizedGtin(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_value: str
    normalized_gtin: str


def _valid_checksum(value: str) -> bool:
    body, check_digit = value[:-1], int(value[-1])
    weighted_sum = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(body))
    )
    return (10 - weighted_sum % 10) % 10 == check_digit


def normalize_gtin(raw: object) -> NormalizedGtin:
    """Normalize and checksum-validate GTIN-8/12/13/14 without guessing.

    UPC-E expansion remains scanner-provider work because its number-system
    semantics are format-dependent. The web scanner already returns expanded
    UPC-A; this function intentionally never zero-pads or derives identifiers.
    """

    raw_value = "" if raw is None else str(raw).strip()
    normalized = "".join(character for character in raw_value if character not in " -")
    if not normalized:
        raise InvalidGtinError("INVALID_GTIN: identifier is empty")
    if not normalized.isascii() or not normalized.isdigit():
        raise InvalidGtinError("INVALID_GTIN: identifier must contain only ASCII digits")
    if len(normalized) not in {8, 12, 13, 14}:
        raise InvalidGtinError("INVALID_GTIN: unsupported GTIN length")
    if not _valid_checksum(normalized):
        raise InvalidGtinError("INVALID_GTIN: checksum is invalid")
    return NormalizedGtin(raw_value=raw_value, normalized_gtin=normalized)


__all__ = ["InvalidGtinError", "NormalizedGtin", "normalize_gtin"]
