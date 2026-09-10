from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RecipeUnit = Literal["g", "kg", "ml", "l", "dl", "cl", "st"]


class RecipeIngredient(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0, le=100000)
    unit: RecipeUnit
    canonical_name: str | None = None


class Recipe(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=150)
    servings: int = Field(gt=0, le=12)
    ingredients: list[RecipeIngredient] = Field(min_length=1, max_length=40)
    instructions: list[str] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def validate_instructions(self) -> Recipe:
        if any(not instruction.strip() for instruction in self.instructions):
            raise ValueError("instructions may not contain empty steps")
        if any(len(instruction) > 2000 for instruction in self.instructions):
            raise ValueError("Tillagningssteget är för långt.")
        return self


class RecipeCollection(BaseModel):
    """Top-level schema suitable for OpenAI structured output."""

    recipes: list[Recipe] = Field(min_length=1)
