"""Explicit campaign applicability, separate from ordinary price age.

An observation proves that the official current-offer surface displayed the
contract then. It never supplies a missing historical campaign start date.
"""
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

STOCKHOLM = ZoneInfo("Europe/Stockholm")


class CampaignEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    policy: Literal["verified-current-campaign-v1"] = "verified-current-campaign-v1"
    store_external_id: str = Field(min_length=1)
    offer_id: str = Field(min_length=1)
    source_reference: str = Field(min_length=1)
    observed_current_at: datetime
    checked_at: datetime

    @model_validator(mode="after")
    def timestamps(self):
        for value in (self.observed_current_at, self.checked_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("campaign evidence requires aware source timestamps")
        if self.checked_at < self.observed_current_at:
            raise ValueError("campaign check precedes observation")
        return self

    def applies(self, on_date: date, valid_from: date | None, valid_to: date | None) -> bool:
        if valid_to is None or on_date > valid_to:
            return False
        lower = valid_from or self.observed_current_at.astimezone(STOCKHOLM).date()
        return lower <= on_date


def is_campaign_only(product) -> bool:
    """Only the opt-in OWN ICA offers channel may use this exception."""
    provenance = product.source_provenance
    return bool(product.price is None and product.coverage == "offers_only"
                and provenance is not None and provenance.source_provider == "own"
                and provenance.source_channel == "offers" and product.chain == "ica"
                and product.offers and all(o.campaign_evidence is not None
                    and o.valid_to is not None
                    and o.campaign_evidence.store_external_id == provenance.provider_store_id
                    and o.campaign_evidence.observed_current_at == provenance.source_observed_at
                    for o in product.offers))
