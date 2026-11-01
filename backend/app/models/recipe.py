from __future__ import annotations

from typing import Literal

from app.models.compact import CompactFrozenModel as BaseModel
from pydantic import ConfigDict, Field, model_validator

RecipeUnit = Literal["g", "kg", "ml", "l", "dl", "cl", "st"]


class RecipeComponentAmount(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    ingredient_key: str
    quantity: float = Field(gt=0, le=100000)
    unit: Literal["g", "ml", "st"]
    note: str = ""
    name: str


class RecipeContentSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    pack_id: str
    proposal_id: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    priority: Literal[1, 2]
    timing_basis: Literal["authored_estimate_coarse_dependencies"]
    active_minutes: int = Field(ge=1, le=180)
    method_note: str
    scaling_note: str
    safety_sources: tuple[str, ...]
    storage_note: str


class RecipeComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    name: str
    amounts: tuple[RecipeComponentAmount, ...] | None = Field(default=None, exclude_if=lambda v: v is None)


class RecipeStep(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str
    text: str = Field(min_length=1, max_length=2000)
    ingredient_keys: tuple[str, ...]
    depends_on: tuple[str, ...] = ()
    duration_minutes: int = Field(ge=1, le=1440)
    parallel_group: str | None = None
    # Exact authored tokens, explicitly reviewed by the importer. Never scale
    # temperatures, durations or dimensions by searching arbitrary numbers.
    scalable_amounts: tuple[tuple[str, float], ...] | None = Field(default=None, exclude_if=lambda v: v is None)


class RecipeProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    authoring: Literal["model_assisted_original"] = "model_assisted_original"
    content_review: Literal["reviewed"] = "reviewed"
    machine_validation: Literal["passed"] = "passed"
    cooking_test: Literal["not_cooked"] = "not_cooked"
    reviewed_at: str
    notes: str


class RecipeUnmeasuredProcess(BaseModel):
    """Reviewed removal, not a measured retention coefficient or food yield."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    step_id: str
    ingredient_keys: tuple[str, ...] = Field(min_length=1)
    operation: Literal["drain_after_cooking", "remove_after_infusion", "deep_fry_and_drain", "strain_whey", "peel_after_cooking", "remove_bones_after_cooking", "trim_before_cooking", "drain_before_cooking"]
    description: str = Field(min_length=10, max_length=500)


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
    # This is elapsed time, including soaking, proving, draining and chilling.
    # Twelve-portion sequential batches can exceed the 180-minute user filter.
    # Retain the declared time; selection must compare the actual scaled value.
    estimated_minutes: int = Field(ge=1, le=2880)
    equipment: tuple[str, ...]
    vegetarian: bool
    fish: bool = False
    ingredient_count: int = Field(ge=1, le=40)
    provenance: RecipeProvenance
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_source: RecipeContentSource | None = Field(default=None, exclude_if=lambda v: v is None)
    meal_types: tuple[Literal["dinner", "breakfast", "snack"], ...] = Field(
        default=("dinner",), exclude_if=lambda v: v == ("dinner",))
    dinner_level: Literal["simple", "crafted"] = Field(
        default="crafted", exclude_if=lambda v: v == "crafted")
    active_minutes: int | None = Field(default=None, ge=1, le=2880,
                                      exclude_if=lambda v: v is None)
    waiting_minutes: int = Field(default=0, ge=0, le=1440, exclude_if=lambda v: v == 0)
    total_minutes: int | None = Field(default=None, ge=1, le=2880,
                                     exclude_if=lambda v: v is None)
    unmeasured_processes: tuple[RecipeUnmeasuredProcess, ...] | None = Field(
        default=None, min_length=1, exclude_if=lambda v: v is None)
    servings_multiple: int | None = Field(default=None, ge=1, le=12, exclude_if=lambda v: v is None)


class RecipePreparation(BaseModel):
    """Versioned recipe design, never an assertion of measured cooking yield."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    version: Literal["smako-edible-input-v1", "smako-authored-input-v2", "smako-authored-losses-v3"]
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
    form: Literal["dry", "raw_edible", "as_sold", "cooked_drained", "preserved_drained"] | None = Field(default=None, exclude_if=lambda v: v is None)
    component: str | None = Field(default=None, exclude_if=lambda v: v is None)
    required: bool | None = Field(default=None, exclude_if=lambda v: v is None)
    role: Literal["primary", "side", "vegetable", "sauce", "flavour", "cooking"] | None = Field(default=None, exclude_if=lambda v: v is None)
    quantity_min: float | None = Field(default=None, gt=0, exclude_if=lambda v: v is None)
    quantity_max: float | None = Field(default=None, gt=0, exclude_if=lambda v: v is None)
    quantity_step: float | None = Field(default=None, gt=0, exclude_if=lambda v: v is None)
    product_requirements: tuple[str, ...] | None = Field(default=None, exclude_if=lambda v: v is None)


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
