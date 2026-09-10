from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .basket import (
    BasketAuditItem,
    BasketAuditResult,
    BasketAuditUnitTotals,
    BasketVerificationStatus,
)
from .diversity import DiversityMode


class QualityStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class RecipeNutritionQuality(BaseModel):
    """Transparent canonical estimate, not product-label nutrition data."""

    model_config = ConfigDict(frozen=True)

    recipe_name: str
    status: QualityStatus
    is_estimate: bool = True
    kcal_per_serving: float = Field(ge=0)
    protein_g_per_serving: float = Field(ge=0)
    vegetable_g_per_serving: float = Field(ge=0)
    confidence: str
    confidence_score: float = Field(ge=0, le=1)
    violations: list[str] = Field(default_factory=list)
    unestimated_ingredients: list[str] = Field(default_factory=list)
    piece_weight_assumptions: list[str] = Field(default_factory=list)


class NutritionQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: QualityStatus
    is_estimate: bool = True
    recipes: list[RecipeNutritionQuality] = Field(default_factory=list)
    average_kcal_per_serving: float = Field(ge=0)
    min_kcal_per_serving: float = Field(ge=0)
    max_kcal_per_serving: float = Field(ge=0)
    average_protein_g_per_serving: float = Field(ge=0)
    min_protein_g_per_serving: float = Field(ge=0)
    max_protein_g_per_serving: float = Field(ge=0)
    average_vegetable_g_per_serving: float = Field(ge=0)


class RecipeSimilarityPairQuality(BaseModel):
    model_config = ConfigDict(frozen=True)

    left_recipe: str
    right_recipe: str
    score: float = Field(ge=0, le=1)
    shared_ingredients: list[str] = Field(default_factory=list)
    is_near_duplicate: bool = False
    components: dict[str, float] = Field(default_factory=dict)


class DiversityRepetitionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    recipe_families: dict[str, int] = Field(default_factory=dict)
    primary_proteins: dict[str, int] = Field(default_factory=dict)
    primary_carbs: dict[str, int] = Field(default_factory=dict)
    dish_forms: dict[str, int] = Field(default_factory=dict)
    cooking_methods: dict[str, int] = Field(default_factory=dict)


class DiversityQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: QualityStatus
    mode: DiversityMode = DiversityMode.BALANCED
    threshold: float | None = Field(default=None, ge=0, le=1)
    max_pairwise_similarity: float = Field(ge=0, le=1)
    average_pairwise_similarity: float = Field(default=0, ge=0, le=1)
    diversity_score: float = Field(default=1, ge=0, le=1)
    repetition: DiversityRepetitionSummary = Field(default_factory=DiversityRepetitionSummary)
    pairs: list[RecipeSimilarityPairQuality] = Field(default_factory=list)


class PlanQualitySummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: QualityStatus
    basket_audit: BasketAuditResult
    nutrition: NutritionQualitySummary
    diversity: DiversityQualitySummary


class SurplusSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[BasketAuditItem] = Field(default_factory=list)
    unit_totals: list[BasketAuditUnitTotals] = Field(default_factory=list)
    estimated_surplus_value: float = Field(default=0, ge=0)


class StoreTradeoff(BaseModel):
    model_config = ConfigDict(frozen=True)

    one_store_total: float | None = Field(default=None, ge=0)
    selected_total: float = Field(ge=0)
    selected_store_count: int = Field(ge=0)
    extra_store_savings: float = Field(default=0, ge=0)
    one_store_names: list[str] = Field(default_factory=list)
    selected_store_names: list[str] = Field(default_factory=list)
    one_store_verification_status: BasketVerificationStatus | None = None
    selected_verification_status: BasketVerificationStatus = BasketVerificationStatus.UNVERIFIED


__all__ = [
    "DiversityQualitySummary",
    "DiversityRepetitionSummary",
    "NutritionQualitySummary",
    "PlanQualitySummary",
    "QualityStatus",
    "RecipeNutritionQuality",
    "RecipeSimilarityPairQuality",
    "StoreTradeoff",
    "SurplusSummary",
]
