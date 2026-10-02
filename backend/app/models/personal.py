"""Private request contracts. Never persisted in a shared PriceUniverse."""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .recipe import Recipe

MealType = Literal["dinner", "breakfast", "snack"]
Protein = Literal["vegetarian", "chicken", "fish", "meat"]


class PrivateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class TasteProfile(PrivateModel):
    likes: list[str] = Field(default_factory=list, max_length=30)
    dislikes: list[str] = Field(default_factory=list, max_length=30)
    exclusions: list[str] = Field(default_factory=list, max_length=30)
    allergies: list[str] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def clean(self):
        for name in ("likes", "dislikes", "exclusions", "allergies"):
            values = list(
                dict.fromkeys(" ".join(v.casefold().split()) for v in getattr(self, name))
            )
            if any(not v or len(v) > 100 for v in values):
                raise ValueError("Varje val måste vara 1–100 tecken.")
            setattr(self, name, values)
        if set(self.likes) & (set(self.exclusions) | set(self.allergies)):
            raise ValueError("Samma vara är både önskad och uttryckligen förbjuden.")
        return self


class PortionLimits(PrivateModel):
    min_weight_g: float | None = Field(default=None, ge=0, le=3000)
    max_weight_g: float | None = Field(default=None, ge=0, le=3000)
    min_protein_g: float | None = Field(default=None, ge=0, le=300)
    max_protein_g: float | None = Field(default=None, ge=0, le=300)
    min_carbs_g: float | None = Field(default=None, ge=0, le=500)
    max_carbs_g: float | None = Field(default=None, ge=0, le=500)
    min_fat_g: float | None = Field(default=None, ge=0, le=300)
    max_fat_g: float | None = Field(default=None, ge=0, le=300)
    max_kcal: float | None = Field(default=None, ge=0, le=4000)

    @model_validator(mode="after")
    def ranges(self):
        for nutrient in ("weight_g", "protein_g", "carbs_g", "fat_g"):
            lower, upper = getattr(self, f"min_{nutrient}"), getattr(self, f"max_{nutrient}")
            if lower is not None and upper is not None and lower > upper:
                raise ValueError(f"Minst {nutrient} får inte överstiga maxgränsen.")
        return self

    @property
    def active(self):
        return any(v is not None for v in self.model_dump().values())


class MealSettings(PrivateModel):
    meal_type: MealType = "dinner"
    count: int = Field(default=5, ge=0, le=7)
    servings: int = Field(default=4, ge=1, le=8)
    diet: Literal["mixed", "vegetarian", "vegan"] = "mixed"
    profile: TasteProfile = Field(default_factory=TasteProfile)
    distribution: dict[Protein, int] = Field(default_factory=dict)
    limits: PortionLimits = Field(default_factory=PortionLimits)
    organic_animals: bool = False

    @model_validator(mode="after")
    def counts(self):
        if any(v < 0 for v in self.distribution.values()):
            raise ValueError("Antalet rätter kan inte vara negativt.")
        if sum(self.distribution.values()) > self.count:
            raise ValueError("Fördelningen överstiger antalet måltidstillfällen.")
        if self.diet != "mixed" and any(
            self.distribution.get(k, 0) for k in ("meat", "fish", "chicken")
        ):
            raise ValueError(
                "Vegetarisk/vegansk kost kan inte innehålla kyckling, fisk eller kött."
            )
        if (
            self.diet != "mixed"
            and "vegetarian" in self.distribution
            and self.distribution["vegetarian"] != self.count
        ):
            raise ValueError("Alla tillfällen måste vara vegetariska med vald kost.")
        return self


class ExtraNeed(PrivateModel):
    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=64)
    kind: Literal["generic", "exact", "campaign"] = "generic"
    query: str = Field(min_length=1, max_length=120)
    quantity: float = Field(gt=0, le=100000)
    unit: Literal["g", "ml", "st"]
    product_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    properties: list[str] = Field(default_factory=list, max_length=15)
    confirmed: bool = False
    use_pantry: bool = False
    food: bool = True

    @model_validator(mode="after")
    def identity(self):
        if self.kind in {"exact", "campaign"} and not self.product_key:
            raise ValueError("Exakt vara kräver identifierad produkt från sökningen.")
        if self.kind == "campaign" and (self.unit != "st" or self.quantity != int(self.quantity) or self.use_pantry):
            raise ValueError("Villkorat kampanjval kräver hela antal och får inte använda skafferi.")
        if self.kind == "generic" and self.product_key:
            raise ValueError("En generisk vara kan inte ha en låst produktidentitet.")
        if any(not p.strip() or len(p) > 100 for p in self.properties):
            raise ValueError("Ogiltig produktegenskap.")
        if not self.confirmed:
            raise ValueError("Bekräfta varan och dess tolkade egenskaper före beräkning.")
        return self


class PantryItem(PrivateModel):
    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    quantity: float = Field(ge=0, le=100000)
    unit: Literal["g", "ml", "st"]
    product_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    unusable: bool = False
    food: bool = True
    nutrition_reference: str | None = Field(default=None, max_length=60)
    form: Literal["raw_edible", "dry", "as_sold", "cooked_drained", "preserved_drained"] | None = Field(default=None, exclude_if=lambda v: v is None)

    @model_validator(mode="after")
    def reference_identity(self):
        if self.nutrition_reference:
            from app.services.nutrition_reference import validate_pantry_reference

            validate_pantry_reference(self.name, self.unit, self.nutrition_reference)
            if self.product_key:
                raise ValueError("En exakt skafferiprodukt använder sitt produktunderlag.")
        return self


class MealSlot(PrivateModel):
    id: str = Field(min_length=1, max_length=64)
    day: int = Field(ge=1, le=7)
    meal_type: MealType
    recipe: Recipe | None = None


class PersonalPlanning(PrivateModel):
    use_pantry: bool = Field(default=True, exclude_if=lambda v: v)
    profile: TasteProfile = Field(default_factory=TasteProfile)
    meals: list[MealSettings] = Field(default_factory=list, max_length=3)
    extras: list[ExtraNeed] = Field(default_factory=list, max_length=60)
    slots: list[MealSlot] | None = Field(default=None, max_length=21)
    pantry_revision: int = Field(default=0, ge=0)
    organic_percent: float = Field(default=0, ge=0, le=100)
    organic_animals: bool = False
    allow_nutrition_estimates: bool = False
    surplus_mode: Literal["minimize", "allow_larger"] = "minimize"
    product_locks: dict[str, str] = Field(default_factory=dict, max_length=80)

    @model_validator(mode="after")
    def unique(self):
        if len({m.meal_type for m in self.meals}) != len(self.meals):
            raise ValueError("Varje måltidstyp får bara ha en inställning.")
        if len({e.id for e in self.extras}) != len(self.extras):
            raise ValueError("Extravarornas rad-ID måste vara unika.")
        if self.slots is not None:
            if len({s.id for s in self.slots}) != len(self.slots):
                raise ValueError("Måltidstillfällenas ID måste vara unika.")
            for meal in self.meals:
                if sum(s.meal_type == meal.meal_type for s in self.slots) != meal.count:
                    raise ValueError("Tillfällen måste stämma med valda antal, inklusive tomma.")
            if any(s.meal_type not in {m.meal_type for m in self.meals} for s in self.slots):
                raise ValueError("Tillfället saknar måltidsinställning.")
        return self


class PersonalResult(PrivateModel):
    version: str = "personal-v2-3"
    slots: list[MealSlot]
    pantry_revision: int
    allocations: list[dict] = Field(default_factory=list)
    future_surplus: list[dict] = Field(default_factory=list)
    needs: list[dict] = Field(default_factory=list)
    checks: dict = Field(default_factory=dict)
    cache_identity: str
    purchase_confirmed: bool = False
    consumption_confirmed: bool = False
    larger_purchase_cost: float = 0
    empty_slots: int = 0
    remaining_demands: list[dict] = Field(default_factory=list)
    consumed_demands: list[dict] = Field(default_factory=list)
    available_surplus: list[dict] = Field(default_factory=list)


class PantryWrite(PrivateModel):
    revision: int = Field(ge=0)
    items: list[PantryItem] = Field(max_length=200)
    profile: TasteProfile | None = None


class ProfileWrite(PrivateModel):
    revision: int = Field(ge=0)
    profile: TasteProfile
    save_explicitly: Literal[True]


class PersonalMutation(PrivateModel):
    revision: int = Field(ge=1)
    pantry_revision: int = Field(ge=0)
    action: Literal[
        "edit",
        "remove",
        "replace",
        "recalculate",
        "purchase",
        "consume",
        "release",
        "product",
        "extras",
        "add_recipe",
        "restore_revision",
    ]
    slot_id: str | None = Field(default=None, max_length=64)
    recipe_id: str | None = Field(default=None, max_length=200)
    recipe: Recipe | None = None
    extras: list[ExtraNeed] | None = Field(default=None, max_length=60)
    ingredient: str | None = Field(default=None, max_length=120)
    product_key: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    restore_revision: int | None = Field(default=None, ge=1)
    measured_purchase_quantities: dict[str, float] = Field(default_factory=dict, max_length=200)
    consume_fraction: float = Field(default=1, gt=0, le=1)
    operation_id: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9-]{8,64}$")

    @model_validator(mode="after")
    def partial_event_identity(self):
        import math
        if any(not math.isfinite(q) or q <= 0 for q in self.measured_purchase_quantities.values()):
            raise ValueError('Uppmätta inköpsmängder måste vara positiva och ändliga.')
        if self.measured_purchase_quantities and self.action != 'purchase':
            raise ValueError('Uppmätt inköpsmängd gäller endast köpbekräftelse.')
        if self.consume_fraction != 1 and (self.action != "consume" or not self.operation_id):
            raise ValueError("Delvis förbrukning kräver ett unikt åtgärds-ID.")
        return self
