from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from statistics import median

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from grocery_data.app.domain.community_evidence import (
    AssortmentConfidence,
    CommunityEvidenceSource,
    EvidenceVerificationStatus,
    PriceEvidenceConfidence,
    ProductIdentityConfidence,
)
from grocery_data.app.domain.identifiers import normalize_gtin
from grocery_data.app.storage.community_evidence import CommunityEvidenceRepository
from grocery_data.app.storage.models import CommunityEvidenceObservationModel, utcnow


class EvidenceReconciliation(BaseModel):
    """Advisory overlay; source facts remain intact and are never rewritten."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    physical_store_id: str
    gtin: str | None = None
    source_product_id: str | None = None
    assortment_confidence: AssortmentConfidence
    price_confidence: PriceEvidenceConfidence
    promotion_confidence: PriceEvidenceConfidence
    observed_community_price: Decimal | None = None
    observed_community_price_unit: str | None = None
    source_price: Decimal | None = None
    source_price_unit: str | None = None
    price_basis_comparable: bool | None = None
    price_evidence_incomplete: bool = False
    price_conflict: bool = False
    promotion_contract_conflict: bool = False
    source_supported_available: bool | None = None
    advisory_only: bool = True
    independent_reporters: int = Field(ge=0)
    considered_reports: int = Field(ge=0)
    excluded_reports: int = Field(ge=0)
    considered_price_reports: int = Field(ge=0)
    excluded_price_reports: int = Field(ge=0)
    positive_presence_weight: float = Field(ge=0)
    not_found_weight: float = Field(ge=0)
    newest_observation_at: datetime | None = None
    explanations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _PriceFact:
    value: Decimal
    unit: str | None
    row: CommunityEvidenceObservationModel


def _normalize_price_unit(value: str | None) -> str | None:
    """Normalize only well-understood price bases; retain unknown labels distinctly."""

    if value is None:
        return None
    compact = "".join(value.strip().casefold().split())
    if not compact:
        return None
    aliases = {
        "kr/kg": "SEK/kg",
        "sek/kg": "SEK/kg",
        "kg": "SEK/kg",
        "kr/l": "SEK/l",
        "sek/l": "SEK/l",
        "kr/liter": "SEK/l",
        "liter": "SEK/l",
        "l": "SEK/l",
        "kr/st": "SEK/item",
        "sek/st": "SEK/item",
        "kr/styck": "SEK/item",
        "sek/styck": "SEK/item",
        "sek/item": "SEK/item",
        "sek/unit": "SEK/item",
        "sek/package": "SEK/item",
        "st": "SEK/item",
        "styck": "SEK/item",
        "item": "SEK/item",
        "unit": "SEK/item",
        "package": "SEK/item",
        "paket": "SEK/item",
        "förpackning": "SEK/item",
    }
    return aliases.get(compact, compact.upper())


def _price_fact(row: CommunityEvidenceObservationModel) -> _PriceFact | None:
    """Return one price with an honest basis, never a receipt-line total as unit price."""

    unit = _normalize_price_unit(row.price_unit)
    if row.evidence_source == CommunityEvidenceSource.RECEIPT.value:
        if row.unit_price is not None:
            # A receipt parser/user explicitly supplied the per-purchase-unit price.
            return _PriceFact(Decimal(row.unit_price), unit or "SEK/item", row)
        quantity = Decimal(row.quantity) if row.quantity is not None else Decimal(1)
        if quantity != Decimal(1):
            # paid/shelf_price is the whole receipt-line total and is not comparable
            # with a source unit price without an explicit unit_price.
            return None
        if row.shelf_price is not None:
            return _PriceFact(Decimal(row.shelf_price), unit or "SEK/item", row)
        return None

    price = row.unit_price if row.unit_price is not None else row.shelf_price
    if price is None:
        return None
    return _PriceFact(Decimal(price), unit, row)


def _promotion_contract(row: CommunityEvidenceObservationModel) -> tuple[object, ...]:
    """A normalized structured contract; free-text descriptions are not identity."""

    def normalized_decimal(value: Decimal | None) -> Decimal | None:
        return Decimal(value).normalize() if value is not None else None

    def normalized_text(value: str | None) -> str | None:
        return " ".join(value.casefold().split()) if value else None

    return (
        normalized_text(row.promotion_eligibility),
        normalized_text(row.promotion_mechanism),
        normalized_decimal(row.promotion_regular_price),
        normalized_decimal(row.promotion_active_price),
        row.promotion_required_quantity,
        normalized_decimal(row.promotion_total_price),
        normalized_decimal(row.promotion_percent_discount),
        row.promotion_max_quantity,
        normalized_text(row.promotion_member_program),
        row.promotion_valid_from,
        row.promotion_valid_to,
    )


class EvidenceReconciler:
    def __init__(
        self,
        session: Session,
        *,
        availability_half_life_hours: float = 168,
        recent_hours: float = 72,
        price_tolerance: Decimal = Decimal("0.50"),
    ) -> None:
        if availability_half_life_hours <= 0 or recent_hours <= 0:
            raise ValueError("evidence freshness settings must be greater than zero")
        self.session = session
        self.repository = CommunityEvidenceRepository(session)
        self.half_life_hours = availability_half_life_hours
        self.recent_hours = recent_hours
        self.price_tolerance = price_tolerance

    def reconcile(
        self,
        *,
        physical_store_id: str,
        gtin: str | None = None,
        source_product_id: str | None = None,
        source_price: Decimal | None = None,
        source_price_unit: str | None = None,
        price_unit: str | None = None,
        source_supported_available: bool | None = None,
        now: datetime | None = None,
    ) -> EvidenceReconciliation:
        if not gtin and not source_product_id:
            raise ValueError("exact gtin or source_product_id is required")
        normalized_gtin = normalize_gtin(gtin).normalized_gtin if gtin else None
        statement = select(CommunityEvidenceObservationModel).where(
            CommunityEvidenceObservationModel.physical_store_id == physical_store_id
        )
        if normalized_gtin:
            statement = statement.where(CommunityEvidenceObservationModel.gtin == normalized_gtin)
        else:
            statement = statement.where(
                CommunityEvidenceObservationModel.source_product_id == source_product_id
            )
        rows = list(self.session.scalars(statement))
        timestamp = (now or utcnow()).astimezone(UTC)
        accepted: list[CommunityEvidenceObservationModel] = []
        excluded = 0
        for row in rows:
            status = self.repository.current_status(row.id)
            if (
                status
                not in {
                    EvidenceVerificationStatus.USER_REPORTED,
                    EvidenceVerificationStatus.VALID,
                }
                or row.observed_at > timestamp
            ):
                excluded += 1
                continue
            accepted.append(row)

        positive_weight = Decimal(0)
        negative_weight = Decimal(0)
        recent_strong_positive = False
        recent_positive_actors: set[str] = set()
        recent_negative_actors: set[str] = set()
        recent_prices: list[_PriceFact] = []
        price_report_count = 0
        excluded_price_reports = 0
        promotion_contract_actors: dict[tuple[object, ...], set[str]] = defaultdict(set)
        promotion_report_count = 0
        actor_hashes: set[str] = set()
        newest = max((row.observed_at for row in accepted), default=None)
        for row in accepted:
            actor_hashes.add(row.actor_hash)
            age_hours = max(
                0.0,
                (timestamp - row.observed_at).total_seconds() / 3600,
            )
            decay = Decimal(str(math.pow(0.5, age_hours / self.half_life_hours)))
            weight = Decimal(row.evidence_confidence) * decay
            if row.physical_presence is True:
                positive_weight += weight
                if age_hours <= self.recent_hours:
                    recent_positive_actors.add(row.actor_hash)
                if (
                    age_hours <= self.recent_hours
                    and row.gtin
                    and row.evidence_source
                    in {
                        CommunityEvidenceSource.BARCODE_SCAN.value,
                        CommunityEvidenceSource.RECEIPT.value,
                    }
                ):
                    recent_strong_positive = True
            elif row.physical_presence is False:
                # Not finding an item is weaker than observing its exact barcode.
                negative_weight += weight * Decimal("0.60")
                if age_hours <= self.recent_hours:
                    recent_negative_actors.add(row.actor_hash)
            if row.shelf_price is not None or row.unit_price is not None:
                price_report_count += 1
                fact = _price_fact(row)
                if fact is None or age_hours > self.recent_hours:
                    excluded_price_reports += 1
                else:
                    recent_prices.append(fact)
            if row.promotion_mechanism is not None:
                promotion_report_count += 1
                if age_hours <= self.recent_hours:
                    promotion_contract_actors[_promotion_contract(row)].add(row.actor_hash)

        explanations: list[str] = []
        if recent_strong_positive:
            assortment = AssortmentConfidence.VERIFIED_RECENTLY_AVAILABLE
            explanations.append("Exact barcode/receipt evidence observed recently in this store.")
        elif positive_weight >= Decimal("0.70") and (
            positive_weight > negative_weight and len(recent_positive_actors) >= 2
        ):
            assortment = AssortmentConfidence.PROBABLE_AVAILABLE
            explanations.append("Fresh independent community evidence supports availability.")
        elif source_supported_available is False:
            assortment = AssortmentConfidence.SOURCE_REPORTED_UNAVAILABLE
            explanations.append("The authoritative source reports unavailable.")
        elif recent_negative_actors and negative_weight > 0 and positive_weight == 0:
            assortment = AssortmentConfidence.USER_REPORTED_NOT_FOUND
            explanations.append(
                "Users reported not finding the item; this is not verified out-of-stock."
            )
        else:
            assortment = AssortmentConfidence.UNKNOWN
            if accepted and not recent_positive_actors and not recent_negative_actors:
                explanations.append(
                    "Community availability observations are historical after freshness decay."
                )

        requested_unit = _normalize_price_unit(price_unit)
        normalized_source_unit = _normalize_price_unit(source_price_unit)
        target_unit = requested_unit or normalized_source_unit
        known_units = {fact.unit for fact in recent_prices if fact.unit is not None}
        selected_prices: list[_PriceFact] = []
        if target_unit is not None:
            selected_prices = [fact for fact in recent_prices if fact.unit == target_unit]
            excluded_price_reports += len(recent_prices) - len(selected_prices)
        elif len(known_units) == 1:
            target_unit = next(iter(known_units))
            selected_prices = [fact for fact in recent_prices if fact.unit == target_unit]
            excluded_price_reports += len(recent_prices) - len(selected_prices)
        elif recent_prices:
            # No honest common basis can be selected when units are unknown or mixed.
            excluded_price_reports += len(recent_prices)

        source_basis_matches = (
            source_price is not None
            and normalized_source_unit is not None
            and target_unit == normalized_source_unit
            and (requested_unit is None or requested_unit == normalized_source_unit)
        )
        if selected_prices:
            price_basis_comparable = source_basis_matches if source_price is not None else True
        elif price_report_count or source_price is not None:
            price_basis_comparable = False
        else:
            price_basis_comparable = None

        community_price = (
            Decimal(str(median([fact.value for fact in selected_prices])))
            if selected_prices
            else None
        )
        price_conflict = False
        if selected_prices:
            price_values = [fact.value for fact in selected_prices]
            price_conflict = max(price_values) - min(price_values) > self.price_tolerance
            if source_basis_matches and source_price is not None and community_price is not None:
                price_conflict = (
                    price_conflict or abs(community_price - source_price) > self.price_tolerance
                )
            exact_receipt = any(
                fact.row.evidence_source == CommunityEvidenceSource.RECEIPT.value
                and fact.row.identity_confidence
                in {
                    ProductIdentityConfidence.EXACT_GTIN.value,
                    ProductIdentityConfidence.EXACT_CHAIN_PRODUCT_ID.value,
                }
                for fact in selected_prices
            )
            if source_price is not None and not source_basis_matches:
                price_conflict = False
                price_confidence = PriceEvidenceConfidence.UNKNOWN
            elif price_conflict:
                price_confidence = PriceEvidenceConfidence.CONFLICTING
            elif exact_receipt:
                price_confidence = PriceEvidenceConfidence.RECEIPT_VERIFIED
            elif len({fact.row.actor_hash for fact in selected_prices}) >= 2:
                price_confidence = PriceEvidenceConfidence.CORROBORATED
            else:
                price_confidence = PriceEvidenceConfidence.USER_REPORTED
        else:
            price_confidence = PriceEvidenceConfidence.UNKNOWN

        promotion_contract_conflict = len(promotion_contract_actors) > 1
        if promotion_contract_conflict:
            promotion_confidence = PriceEvidenceConfidence.CONFLICTING
        elif promotion_contract_actors and len(next(iter(promotion_contract_actors.values()))) >= 2:
            promotion_confidence = PriceEvidenceConfidence.CORROBORATED
        elif promotion_contract_actors:
            promotion_confidence = PriceEvidenceConfidence.USER_REPORTED
        else:
            promotion_confidence = PriceEvidenceConfidence.UNKNOWN
        if (
            source_supported_available
            and assortment is AssortmentConfidence.USER_REPORTED_NOT_FOUND
        ):
            explanations.append(
                "A single/uncorroborated not-found report does not remove a source-supported product."
            )
        if price_conflict:
            explanations.append(
                "Community/source price evidence conflicts; no value was substituted."
            )
        if source_price is not None and not source_basis_matches:
            explanations.append(
                "Community and source prices lack an identical verified price unit; "
                "no price conflict was inferred."
            )
        if excluded_price_reports:
            explanations.append(
                "Price observations with stale, unknown, or incompatible units were excluded."
            )
        if promotion_contract_conflict:
            explanations.append("Recent promotion reports contain contradictory contracts.")
        elif promotion_report_count and not promotion_contract_actors:
            explanations.append("Promotion observations are historical, not current corroboration.")
        return EvidenceReconciliation(
            physical_store_id=physical_store_id,
            gtin=normalized_gtin,
            source_product_id=source_product_id,
            assortment_confidence=assortment,
            price_confidence=price_confidence,
            promotion_confidence=promotion_confidence,
            observed_community_price=community_price,
            observed_community_price_unit=target_unit if selected_prices else None,
            source_price=source_price,
            source_price_unit=normalized_source_unit,
            price_basis_comparable=price_basis_comparable,
            price_evidence_incomplete=excluded_price_reports > 0 or (
                price_report_count > 0 and not selected_prices
            ),
            price_conflict=price_conflict,
            promotion_contract_conflict=promotion_contract_conflict,
            source_supported_available=source_supported_available,
            independent_reporters=len(actor_hashes),
            considered_reports=len(accepted),
            excluded_reports=excluded,
            considered_price_reports=len(selected_prices),
            excluded_price_reports=excluded_price_reports,
            positive_presence_weight=float(positive_weight),
            not_found_weight=float(negative_weight),
            newest_observation_at=newest,
            explanations=tuple(explanations),
        )


__all__ = ["EvidenceReconciler", "EvidenceReconciliation"]
