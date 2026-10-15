"""Explicit campaign applicability, separate from ordinary price age.

An observation proves that the official current-offer surface displayed the
contract then. It never supplies a missing historical campaign start date.
"""
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

STOCKHOLM = ZoneInfo("Europe/Stockholm")


def undated_promotion_usable(observed_at: datetime | None, on_date: date) -> bool:
    """Do not extend undated discounts when retaining an older base price.

    Keep the previous 48-hour upper bound, rounded conservatively to the
    Swedish purchase day. This is an evidence limit, not an invented end date.
    Legacy models without source evidence retain their existing local behavior.
    """
    return observed_at is None or (
        observed_at.astimezone(STOCKHOLM).date() <= on_date
        < (observed_at + timedelta(hours=48)).astimezone(STOCKHOLM).date()
    )


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
    """A product without an ordinary price depends on its dated offers.

    Source identity/qualification is validated before entering the shared
    artifact. Runtime expiry must apply to every chain, not only ICA.
    """
    return product.price is None


def has_active_campaign(product, on_date: date) -> bool:
    provenance = product.source_provenance
    if provenance is None:
        return False
    for offer in product.offers:
        if offer.valid_to is None:
            continue
        evidence = offer.campaign_evidence
        if evidence is not None and (
            evidence.store_external_id != provenance.provider_store_id
            or evidence.observed_current_at != provenance.source_observed_at
        ):
            continue
        if offer.valid_from is None and evidence is None:
            continue
        if offer.is_active(on_date):
            return True
    return False
