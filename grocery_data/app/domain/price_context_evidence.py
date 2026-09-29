"""Optional channel lineage for future observations; absence means legacy unknown."""
from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, model_validator

from .enums import PriceContextType


class PriceContextEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # This is store metadata, never proof of a product's physical shelf price.
    scope: Literal["store_metadata"] = "store_metadata"
    source_field: Literal["store.price_context_type"] = "store.price_context_type"
    source_state: Literal["explicit", "missing", "unrecognized"]
    source_value: PriceContextType | None = None
    assignment_basis: Literal[
        "source_field", "missing", "unreviewed", "legacy_physical_store_default",
        "persisted_grocery_context", "store_metadata",
    ]

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if (self.source_state == "explicit") != (self.source_value is not None):
            raise ValueError("explicit channel evidence requires its exact source value")
        if self.assignment_basis == "source_field" and self.source_state != "explicit":
            raise ValueError("missing channel field cannot be source verification")
        if self.assignment_basis == "missing" and self.source_state != "missing":
            raise ValueError("explicit channel cannot be classified missing")
        return self

    def assigned(self, basis: str) -> Self:
        return type(self).model_validate({**self.model_dump(), "assignment_basis": basis})


def observed_store_channel(value: object) -> PriceContextEvidence:
    if value is None or not str(value).strip():
        return PriceContextEvidence(source_state="missing", assignment_basis="missing")
    try:
        exact = PriceContextType(str(value).strip())
    except ValueError:
        # Keep existing parser behavior, but never export an unknown raw value
        # or conflate an unrecognized source field with verified channel metadata.
        return PriceContextEvidence(source_state="unrecognized", assignment_basis="unreviewed")
    return PriceContextEvidence(source_state="explicit", source_value=exact,
                                assignment_basis="source_field")
