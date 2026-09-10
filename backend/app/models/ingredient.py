from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .product import CanonicalUnit


class NormalizedIngredient(BaseModel):
    model_config = ConfigDict(frozen=True)

    canonical_name: str = Field(min_length=1)
    required_quantity: float = Field(gt=0)
    unit: CanonicalUnit
    display_name: str | None = None
    source_recipes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def set_display_name(self) -> NormalizedIngredient:
        if self.display_name is None:
            object.__setattr__(self, "display_name", self.canonical_name)
        return self

