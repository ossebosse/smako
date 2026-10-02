from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

RecipeUnit = Literal["g", "kg", "ml", "l", "dl", "cl", "st"]


class RecipeComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    name: str


class RecipeStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    text: str = Field(min_length=1, max_length=2000)
    ingredient_keys: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    duration_minutes: int = Field(ge=1, le=180)
    parallel_group: str | None = None


class RecipeProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    authoring: Literal["model_assisted_original"] = "model_assisted_original"
    content_review: Literal["reviewed"] = "reviewed"
    machine_validation: Literal["passed"] = "passed"
    cooking_test: Literal["not_cooked"] = "not_cooked"
    reviewed_at: str
    notes: str


class RecipeDesign(BaseModel):
    """Immutable authored identity, cooking structure and review provenance.

    A model-valid object is not itself an approved cooking method. The library
    service verifies the entire recipe against its versioned content registry.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    base_id: str = Field(pattern=r"^smako-[a-z]+-[a-z0-9-]+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    variant_id: str = Field(pattern=r"^[a-z0-9-]+$")
    cuisines: tuple[Literal["greek", "italian", "mexican", "indian", "thai", "swedish"], ...]
    family: str
    primary_ingredient: str
    method: str
    side: str
    flavor_profile: tuple[str, ...]
    components: tuple[RecipeComponent, ...]
    steps: tuple[RecipeStep, ...]
    estimated_minutes: int = Field(ge=1, le=180)
    equipment: tuple[str, ...]
    vegetarian: bool
    fish: bool = False
    ingredient_count: int = Field(ge=1, le=40)
    provenance: RecipeProvenance
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RecipePreparation(BaseModel):
    """Versioned recipe design, never an assertion of measured cooking yield."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    version: Literal["smako-edible-input-v1"]
    origin: Literal["smako_recipe_design", "explicit_adaptation"]
    parent_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    family: str
    input_forms: dict[str, str]



class RecipeIngredient(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0, le=100000)
    unit: RecipeUnit
    canonical_name: str | None = None
    form: Literal["dry", "raw_edible", "as_sold", "cooked_drained"] | None = Field(default=None, exclude_if=lambda v: v is None)
    component: str | None = Field(default=None, exclude_if=lambda v: v is None)
    required: bool | None = Field(default=None, exclude_if=lambda v: v is None)
    role: Literal["primary", "side", "vegetable", "sauce", "flavour", "cooking"] | None = Field(default=None, exclude_if=lambda v: v is None)
    quantity_min: float | None = Field(default=None, gt=0, exclude_if=lambda v: v is None)
    quantity_max: float | None = Field(default=None, gt=0, exclude_if=lambda v: v is None)
    quantity_step: float | None = Field(default=None, gt=0, exclude_if=lambda v: v is None)


class Recipe(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1, max_length=150)
    servings: int = Field(gt=0, le=12)
    ingredients: list[RecipeIngredient] = Field(min_length=1, max_length=40)
    instructions: list[str] = Field(min_length=1, max_length=40)
    preparation: RecipePreparation | None = Field(default=None, exclude_if=lambda v: v is None)
    design: RecipeDesign | None = Field(default=None, exclude_if=lambda v: v is None)

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
