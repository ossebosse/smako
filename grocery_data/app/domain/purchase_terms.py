"""Retailer-independent physical/identity evidence; never a price engine.

Prices, dates, audience and store scope remain in the existing offer contract.
These facts restrict uses of that contract without inventing product variants.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PurchaseTerms(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    version: Literal["purchase-terms-v1"] = "purchase-terms-v1"
    source_reference: str = Field(min_length=1)
    purchase_form: Literal[
        "fixed_package", "loose_weight", "variable_package", "piece", "unresolved"
    ]
    identity_scope: Literal["product", "campaign_group"] = "product"
    variant_selection: Literal["resolved", "required"] = "resolved"
    complete_group_size: int = Field(default=1, ge=1, le=100)
    eligible_variant_ids: tuple[str, ...] = ()
    mixing_allowed: bool = Field(default=False, exclude_if=lambda v: not v)
    campaign_group_id: str | None = Field(default=None, min_length=1, exclude_if=lambda v: v is None)
    uniform_weight_rate: bool = Field(default=False, exclude_if=lambda v: not v)
    exclusions: tuple[str, ...] = ()
    variant_package_minimum: float | None = Field(default=None, gt=0)
    variant_package_maximum: float | None = Field(default=None, gt=0)
    variant_package_unit: Literal["g", "ml", "st"] | None = None
    approximate_package_g: float | None = Field(default=None, gt=0)
    minimum_package_g: float | None = Field(default=None, gt=0)
    maximum_package_g: float | None = Field(default=None, gt=0)
    quantity_basis: Literal[
        "source_approximation", "source_interval", "source_exact", "requirement", "unknown"
    ] = "unknown"
    deposit_status: Literal["not_applicable", "verified_separately", "estimated_separately", "unknown"] = "not_applicable"
    critical_blockers: tuple[str, ...] = ()
    limit_scope: Literal["offer", "household_campaign"] = "offer"

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.uniform_weight_rate and (self.identity_scope != 'campaign_group'
                or not self.eligible_variant_ids
                or self.purchase_form not in {'loose_weight', 'variable_package'}):
            raise ValueError('Uniform weight rate requires source-bound weight variants')
        if self.mixing_allowed and (not self.campaign_group_id or not self.eligible_variant_ids
                                    or self.complete_group_size < 2):
            raise ValueError("Mixed variants require a source group, explicit eligible IDs and complete count")
        if len(set(self.eligible_variant_ids)) != len(self.eligible_variant_ids):
            raise ValueError("Duplicate source variant identity")
        if self.variant_package_minimum is not None and (
            self.identity_scope != "campaign_group"
            or self.variant_package_unit is None
            or self.variant_package_maximum is None
            or self.variant_package_maximum < self.variant_package_minimum
        ):
            raise ValueError(
                "variant sizes require an explicit group interval, never midpoint weight"
            )
        if self.approximate_package_g is not None and (
            self.purchase_form != "variable_package"
            or self.quantity_basis != "source_approximation"
        ):
            raise ValueError("approximate weight must retain its source approximation basis")
        if self.maximum_package_g is not None and (
            self.minimum_package_g is None or self.maximum_package_g < self.minimum_package_g
        ):
            raise ValueError("invalid documented package interval")
        if self.identity_scope == "campaign_group" and self.variant_selection != "required":
            raise ValueError("an open campaign group is not a resolved product")
        return self

    @property
    def usage(self) -> str:
        if self.critical_blockers or self.deposit_status == "unknown":
            return "blocked"
        if self.uniform_weight_rate:
            return 'estimated'
        if self.variant_selection == "required":
            return "variant_selection_required"
        if self.purchase_form in {"loose_weight", "variable_package"}:
            return "estimated"
        if self.purchase_form == "unresolved":
            return "blocked"
        return "exact"
