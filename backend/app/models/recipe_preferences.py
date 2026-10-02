"""Additive choices for the authored dinner library; legacy calls are unchanged."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Cuisine = Literal["greek", "italian", "mexican", "indian", "thai", "swedish"]


class RecipePreferences(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    mode: Literal["legacy", "complete"] = "legacy"
    cuisines: tuple[Cuisine, ...] = ()
    min_ingredients: int = Field(default=10, ge=3, le=20)
    max_ingredients: int = Field(default=15, ge=3, le=20)
    max_minutes: int | None = Field(default=None, ge=10, le=180)
    adaptation: Literal["products", "approved"] = "approved"
    min_protein_g: float | None = Field(default=None, ge=0, le=100)
    allow_fish: bool = True

    @model_validator(mode="after")
    def coherent_choices(self):
        if self.min_ingredients > self.max_ingredients:
            raise ValueError("Minsta ingrediensantal får inte överstiga det största.")
        if len(self.cuisines) != len(set(self.cuisines)):
            raise ValueError("Välj varje matkök högst en gång.")
        return self
