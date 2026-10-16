"""Expand reviewed recipe families offline into ordinary immutable meal packs.

No runtime substitution, Cartesian expansion, price or nutrition inference.
Each authored combination has explicit instructions and component amounts and
uses the existing pack validator, registry, preparation and planner afterwards.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from app.models.recipe import (
    Recipe,
    RecipeComponent,
    RecipeIngredient,
    RecipeProvenance,
    RecipeStep,
)
from app.services.meal_library_content import (
    MAX_BYTES,
    MAX_RECIPES,
    SCHEMA,
    digest,
    encoded,
    identity,
    read_json,
    validate_pack_bytes,
)
from app.services.recipe_library import _structural_check, ingredient_count, ingredient_key
from pydantic import BaseModel, ConfigDict, Field, model_validator

PositiveAmount = Annotated[float, Field(gt=0, le=100000)]


class StrictData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class QuantityRange(StrictData):
    minimum: PositiveAmount
    maximum: PositiveAmount
    step: PositiveAmount

    @model_validator(mode="after")
    def ordered(self):
        if self.minimum > self.maximum:
            raise ValueError("Mängdintervallets minimum överstiger maximum")
        return self

    def accepts(self, quantity):
        q, low, high, step = (Decimal(str(n))
                             for n in (quantity, self.minimum, self.maximum, self.step))
        return low <= q <= high and (q - low) % step == 0


class ReplacementIngredient(RecipeIngredient):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class BaseRecipe(Recipe):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    ingredients: list[ReplacementIngredient] = Field(min_length=1, max_length=40)


class Substitution(StrictData):
    ingredient_key: str
    replacement: ReplacementIngredient


class CookingDesign(StrictData):
    """Explicit variant metadata; never inherit a replaced protein or method."""
    primary_ingredient: str
    side: str
    method: str
    family: str
    vegetarian: bool
    fish: bool
    flavor_profile: tuple[str, ...]
    equipment: tuple[str, ...]
    estimated_minutes: int = Field(ge=1, le=180)
    active_minutes: int = Field(ge=1, le=180)
    waiting_minutes: int = Field(default=0, ge=0, le=1440)
    total_minutes: int = Field(ge=1, le=2880)


class ApprovedVariant(StrictData):
    variant_id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=150)
    substitutions: tuple[Substitution, ...] = Field(default=(), max_length=40)
    quantities: dict[str, PositiveAmount] = Field(default_factory=dict, max_length=40)
    # Full authored instructions and allocation required even for amount changes.
    components: tuple[RecipeComponent, ...] = Field(min_length=1, max_length=40)
    steps: tuple[RecipeStep, ...] = Field(min_length=1, max_length=40)
    cooking: CookingDesign
    review: RecipeProvenance


class FlexibleFamily(StrictData):
    base: BaseRecipe
    include_base: bool = False
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    quantity_ranges: dict[str, QuantityRange] = Field(default_factory=dict, max_length=40)
    variants: tuple[ApprovedVariant, ...] = Field(min_length=1, max_length=16)


class FlexiblePack(StrictData):
    schema_version: Literal["smako-flexible-meal-pack-v1"]
    pack_id: str = Field(min_length=1, max_length=100)
    families: tuple[FlexibleFamily, ...] = Field(min_length=1, max_length=256)


def _expand(family, variant, pack_id, source_hash):
    base = family.base
    if variant.variant_id == "base":
        raise ValueError("Variant-ID base är reserverat för grundreceptet")
    _structural_check(base)
    originals = {ingredient_key(i): i for i in base.ingredients}
    if not set(family.quantity_ranges) <= originals.keys():
        raise ValueError("Mängdintervall avser okänd ingrediens/form")
    replacements = {s.ingredient_key: s.replacement for s in variant.substitutions}
    if len(replacements) != len(variant.substitutions) or not replacements.keys() <= originals.keys():
        raise ValueError("Dubblerat eller okänt ingrediensbyte")
    if not variant.quantities.keys() <= originals.keys() - replacements.keys():
        raise ValueError("Mängdval avser okänd eller samtidigt utbytt ingrediens")
    ingredients = []
    for key, original in originals.items():
        if key in replacements:
            replacement = replacements[key]
            if ingredient_key(replacement) == key:
                raise ValueError("Använd mängdval för en oförändrad ingrediens/form")
            bounds = QuantityRange(minimum=replacement.quantity_min,
                                   maximum=replacement.quantity_max, step=replacement.quantity_step)
            if not bounds.accepts(replacement.quantity):
                raise ValueError("Bytets mängd ligger utanför godkänt intervall eller steg")
            ingredients.append(replacement)
            continue
        quantity = variant.quantities.get(key, original.quantity)
        bounds = family.quantity_ranges.get(key) or QuantityRange(
            minimum=original.quantity_min, maximum=original.quantity_max, step=original.quantity_step)
        if key in variant.quantities and not bounds.accepts(quantity):
            raise ValueError(f"{key}: mängden ligger utanför godkänt intervall eller steg")
        ingredients.append(original.model_copy(update={
            "quantity": quantity, "quantity_min": bounds.minimum,
            "quantity_max": bounds.maximum, "quantity_step": bounds.step}))
    if not replacements and all(i.quantity == o.quantity for i, o in zip(ingredients, base.ingredients)):
        raise ValueError("Varianten ändrar inga råvaror eller mängder")
    if variant.cooking.primary_ingredient not in {i.canonical_name for i in ingredients}:
        raise ValueError("Variantens primära ingrediens finns inte i rätten")
    data = base.model_dump(mode="json", exclude={"preparation"})
    data.update(name=variant.name, ingredients=[i.model_dump(mode="json") for i in ingredients],
                instructions=[s.text for s in variant.steps])
    design = data["design"]
    design.update(variant.cooking.model_dump(mode="json"))
    design.update(version=family.version, variant_id=variant.variant_id,
                  components=[c.model_dump(mode="json") for c in variant.components],
                  steps=[s.model_dump(mode="json") for s in variant.steps],
                  provenance=variant.review.model_dump(mode="json"))
    design["provenance"]["notes"] += (
        f" Bas: {identity(base)}; innehåll {base.design.content_sha256}. "
        f"Variantregler: {source_hash}. Ingen automatisk närings- eller köpkvalificering.")
    # Do not carry a base recipe's source identity into its adaptation.
    design.pop("content_source", None)
    design["ingredient_count"] = ingredient_count(Recipe.model_validate(data))
    # The ordinary validator adds content_source, seals and structural checks.
    checked = validate_pack_bytes(encoded({"schema_version": SCHEMA, "pack_id": pack_id,
                                          "recipes": [data]}))
    if checked["rejections"]:
        raise ValueError(checked["rejections"][0]["reason"])
    recipe = checked["recipes"][0]
    # Bind every variant to the entire reviewed input (not a transient row).
    row = recipe.model_dump(mode="json")
    row["design"]["content_source"].update(
        sha256=source_hash, proposal_id=f"{identity(base)}->{variant.variant_id}")
    return row


def expand_pack(path: Path):
    """Fail atomically; caller may publish only the complete validated result."""
    raw = read_json(path)
    pack = FlexiblePack.model_validate(raw)
    source_hash = digest(path.read_bytes())
    rows, identities = [], set()
    for family in pack.families:
        if family.include_base:
            rows.append(family.base.model_dump(mode="json"))
        for variant in family.variants:
            try:
                rows.append(_expand(family, variant, pack.pack_id, source_hash))
            except ValueError as exc:
                raise ValueError(f"{family.base.name}/{variant.variant_id}: {exc}") from exc
    for row in rows:
        key = identity(Recipe.model_validate(row))
        if key in identities:
            raise ValueError(f"Dubblerad variantidentitet: {key}")
        identities.add(key)
    if len(rows) > MAX_RECIPES:
        raise ValueError("För många utökade recept")
    output = {"schema_version": SCHEMA, "pack_id": pack.pack_id, "recipes": rows}
    source = encoded(output)
    if len(source) > MAX_BYTES:
        raise ValueError("Utökat receptpaket överstiger storleksgränsen")
    checked = validate_pack_bytes(source, label=str(path))
    if checked["rejections"]:
        raise ValueError(str(checked["rejections"]))
    output["recipes"] = [r.model_dump(mode="json") for r in checked["recipes"]]
    return output
