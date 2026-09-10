from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from grocery_data.app.domain.promotion_pricing import (
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.services.closed_provider_cache import load_closed_provider_cache

_STOCKHOLM = ZoneInfo("Europe/Stockholm")
_CENT = Decimal("0.01")
_MULTIBUY_TEXT = re.compile(
    r"(?:^|[-–—:]\s*)(?P<quantity>[1-9]\d*)\s*"
    r"(?:för|for)\s*(?P<total>\d+(?:[,.]\d{1,2})?)\s*"
    r"(?:kr|:-)(?:\s*/?\s*st)?\s*$",
    flags=re.IGNORECASE,
)


class ExternalStoreOfferBinding(BaseModel):
    """Exact, pre-verified physical-store to licensed-context relation.

    The caller must construct this from the persisted identity registry.  This
    module deliberately has no name/address matching fallback.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    physical_store_id: str = Field(min_length=1)
    physical_store_external_id: str = Field(min_length=1)
    store_display_name: str = Field(min_length=1)
    chain: str = Field(min_length=1)
    grocery_context_id: str = Field(min_length=1)
    provider_store_id: str = Field(min_length=1)


class ExternalCurrentOffer(BaseModel):
    """Credential-free normalized promotion contract from a closed cache."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chain: str
    store_display_name: str
    physical_store_id: str
    grocery_context_id: str
    price_context_type: str
    price_scope_label: str
    source_provider: str = "primat"
    source_channel: str = "catalog"
    snapshot_id: str
    observed_at: datetime
    data_age_hours: float = Field(ge=0)
    product_id: str
    gtin: str | None = None
    product_name: str
    brand: str | None = None
    category: str | None = None
    package_description: str | None = None
    regular_price: Decimal | None = None
    current_public_price: Decimal | None = None
    member_price: Decimal | None = None
    active_offer_price: Decimal | None = None
    eligibility: PromotionEligibility
    mechanism: PromotionMechanism
    required_quantity: int = Field(default=1, ge=1)
    multibuy_total: Decimal | None = None
    derived_unit_price: Decimal | None = None
    derived_unit_price_is_conditional: bool = False
    comparison_price: Decimal | None = None
    comparison_unit: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    validity_confidence: str
    max_quantity: int | None = Field(default=None, ge=1)
    promotion_condition: str
    member_program: str | None = None
    requires_membership: bool = False
    availability: str = "unknown"
    semantic_confidence: str
    quantity_confidence: str
    promotion_confidence: str
    savings_amount: Decimal | None = None
    savings_percent: Decimal | None = None
    stale: bool = False
    lkg_used: bool = False

    @field_validator("observed_at")
    @classmethod
    def aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value.astimezone(UTC)


class ExternalOfferSourceStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    physical_store_id: str
    grocery_context_id: str
    provider_store_id: str
    snapshot_id: str | None = None
    observed_at: datetime
    data_age_hours: float = Field(ge=0)
    fresh: bool
    lkg_used: bool
    offers_included: int = Field(ge=0)
    reason: str | None = None


class ExternalOfferLoadResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    captured_at: datetime
    data_age_hours: float = Field(ge=0)
    fresh: bool
    offers: tuple[ExternalCurrentOffer, ...] = ()
    source_statuses: tuple[ExternalOfferSourceStatus, ...] = ()
    diagnostics: Mapping[str, int] = Field(default_factory=dict)

    def rows(self) -> tuple[dict[str, Any], ...]:
        return tuple(offer.model_dump(mode="json") for offer in self.offers)


def parse_explicit_multibuy(description: str | None) -> tuple[int, Decimal] | None:
    """Parse only a terminal, explicit ``N för X kr`` source contract.

    This intentionally does not infer semantics from arbitrary numbers or
    product names.  It exists for older licensed-cache rows where the source
    text retained the full contract while the legacy normalized fields held a
    derived unit price.
    """

    match = _MULTIBUY_TEXT.search((description or "").strip())
    if match is None:
        return None
    quantity = int(match.group("quantity"))
    try:
        total = Decimal(match.group("total").replace(",", "."))
    except InvalidOperation:
        return None
    if quantity < 2 or total <= 0:
        return None
    return quantity, _money(total)


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed > 0 else None


def _date(value: object) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError("licensed offer contains an invalid calendar date") from exc


def _datetime(value: object, *, fallback: datetime) -> datetime:
    if value in (None, ""):
        return fallback
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return fallback
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return fallback
    return parsed.astimezone(UTC)


def _active(valid_from: date | None, valid_to: date | None, *, today: date) -> bool:
    return (valid_from is None or valid_from <= today) and (
        valid_to is None or valid_to >= today
    )


def _package_description(product: Mapping[str, Any]) -> str | None:
    explicit = product.get("package_description") or product.get("package_text")
    if explicit:
        return str(explicit).strip() or None
    quantity = product.get("package_quantity")
    unit = product.get("package_unit")
    if quantity is None or not unit:
        return None
    return f"{quantity} {unit}"


def _snapshot_id(row: Mapping[str, Any]) -> str | None:
    provenance = row.get("source_provenance")
    if not isinstance(provenance, Mapping):
        return None
    value = provenance.get("source_snapshot_id")
    return str(value).strip() if value else None


def _provider_store_id(row: Mapping[str, Any]) -> str | None:
    provenance = row.get("source_provenance")
    if not isinstance(provenance, Mapping):
        return None
    value = provenance.get("provider_store_id")
    return str(value).strip() if value else None


def _source_contract(
    offer: Mapping[str, Any],
) -> tuple[
    PromotionEligibility,
    PromotionMechanism,
    int,
    Decimal | None,
    Decimal | None,
    str,
]:
    description = str(offer.get("description") or "Aktuellt erbjudande").strip()
    kind = str(offer.get("kind") or "campaign").casefold().strip()
    member_program = str(offer.get("member_program") or "").strip()
    eligibility = (
        PromotionEligibility.MEMBER if member_program else PromotionEligibility.PUBLIC
    )
    explicit_multibuy = parse_explicit_multibuy(description)
    supplied_quantity = int(offer.get("required_packages") or 1)
    supplied_price = _decimal(offer.get("price"))

    if kind in {"multipack", "multibuy"}:
        if supplied_quantity < 2 or supplied_price is None:
            raise ValueError("licensed multibuy lacks quantity or total")
        if explicit_multibuy is not None:
            text_quantity, text_total = explicit_multibuy
            if text_quantity != supplied_quantity or text_total != _money(supplied_price):
                raise ValueError("licensed multibuy fields conflict with source text")
        return (
            eligibility,
            PromotionMechanism.MULTIBUY,
            supplied_quantity,
            None,
            _money(supplied_price),
            "explicit_structured_contract",
        )

    if explicit_multibuy is not None:
        quantity, total = explicit_multibuy
        return (
            eligibility,
            PromotionMechanism.MULTIBUY,
            quantity,
            None,
            total,
            "explicit_source_text",
        )

    mechanism = (
        PromotionMechanism.PERCENT_DISCOUNT
        if kind in {"percent", "percent_discount"}
        else PromotionMechanism.SALE_PRICE
    )
    return eligibility, mechanism, 1, supplied_price, None, "explicit_structured_contract"


def _savings(
    *,
    regular_price: Decimal | None,
    offer_price: Decimal | None,
    multibuy_total: Decimal | None,
    required_quantity: int,
) -> tuple[Decimal | None, Decimal | None]:
    if regular_price is None:
        return None, None
    baseline = regular_price * required_quantity if multibuy_total is not None else regular_price
    promoted = multibuy_total if multibuy_total is not None else offer_price
    if promoted is None or baseline <= promoted or baseline <= 0:
        return None, None
    amount = _money(baseline - promoted)
    percent = ((amount / baseline) * Decimal(100)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return amount, percent


def load_closed_primat_current_offers(
    path: Path,
    bindings: Sequence[ExternalStoreOfferBinding],
    *,
    now: datetime | None = None,
    max_age_hours: float = 24,
    include_stale: bool = False,
) -> ExternalOfferLoadResult:
    """Load active offers for exact, already-verified physical-store bindings.

    No provider client is constructed.  The cache loader also rejects all
    credential/session-shaped fields before any row reaches this normalizer.
    """

    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be greater than zero")
    generated_at = now or datetime.now(UTC)
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    generated_at = generated_at.astimezone(UTC)
    document, _, _ = load_closed_provider_cache(path)
    captured_at = document.captured_at.astimezone(UTC)
    age_hours = max(0.0, (generated_at - captured_at).total_seconds() / 3600)
    fresh = age_hours <= max_age_hours
    local_date = generated_at.astimezone(_STOCKHOLM).date()

    exact_bindings = {binding.provider_store_id: binding for binding in bindings}
    if len(exact_bindings) != len(bindings):
        raise ValueError("licensed offer bindings must have unique provider store IDs")

    store_rows: dict[str, Mapping[str, Any]] = {}
    invalid_store_rows = 0
    for raw_store in document.stores:
        provider_store_id = _provider_store_id(raw_store)
        binding = exact_bindings.get(provider_store_id or "")
        if binding is None:
            continue
        physical_external_id = str(raw_store.get("physical_store_external_id") or "").strip()
        provenance = raw_store.get("source_provenance")
        if not isinstance(provenance, Mapping) or str(
            provenance.get("source_provider") or ""
        ).casefold() != "primat":
            invalid_store_rows += 1
            continue
        if physical_external_id != binding.physical_store_external_id:
            invalid_store_rows += 1
            continue
        if str(raw_store.get("chain") or "").casefold() != binding.chain.casefold():
            invalid_store_rows += 1
            continue
        store_rows[provider_store_id or ""] = raw_store

    offers: list[ExternalCurrentOffer] = []
    expired = 0
    future = 0
    invalid_contracts = 0
    invalid_provenance = 0
    for product in document.products:
        provider_store_id = _provider_store_id(product)
        binding = exact_bindings.get(provider_store_id or "")
        store = store_rows.get(provider_store_id or "")
        if binding is None or store is None:
            continue
        provenance = product.get("source_provenance")
        if not isinstance(provenance, Mapping):
            invalid_provenance += 1
            continue
        if str(provenance.get("source_provider") or "").casefold() != "primat":
            invalid_provenance += 1
            continue
        if str(provenance.get("source_channel") or "").casefold() != "catalog":
            invalid_provenance += 1
            continue
        product_snapshot_id = _snapshot_id(product)
        store_snapshot_id = _snapshot_id(store)
        if not product_snapshot_id or product_snapshot_id != store_snapshot_id:
            invalid_provenance += 1
            continue
        if str(product.get("chain") or "").casefold() != binding.chain.casefold():
            invalid_provenance += 1
            continue
        product_id = str(product.get("product_id") or "").strip()
        product_name = str(product.get("name") or "").strip()
        if not product_id or not product_name:
            invalid_provenance += 1
            continue
        observed_at = _datetime(
            provenance.get("source_observed_at"), fallback=captured_at
        )
        raw_offers = product.get("offers")
        if not isinstance(raw_offers, list):
            continue
        for raw_offer in raw_offers:
            if not isinstance(raw_offer, Mapping):
                invalid_contracts += 1
                continue
            try:
                valid_from = _date(raw_offer.get("valid_from"))
                valid_to = _date(raw_offer.get("valid_to"))
            except ValueError:
                invalid_contracts += 1
                continue
            if valid_from is not None and valid_to is not None and valid_from > valid_to:
                invalid_contracts += 1
                continue
            if valid_from is not None and valid_from > local_date:
                future += 1
                continue
            if valid_to is not None and valid_to < local_date:
                expired += 1
                continue
            if not _active(valid_from, valid_to, today=local_date):
                continue
            if not fresh and not include_stale:
                continue
            try:
                (
                    eligibility,
                    mechanism,
                    quantity,
                    offer_price,
                    multibuy_total,
                    promotion_confidence,
                ) = _source_contract(raw_offer)
            except (TypeError, ValueError):
                invalid_contracts += 1
                continue

            # The closed Primat schema does not currently carry a dedicated
            # regular-price field.  ``price``/``sale_price`` may already be a
            # campaign projection, so they must never be relabelled regular.
            regular_price = _decimal(product.get("regular_price"))
            savings_amount, savings_percent = _savings(
                regular_price=regular_price,
                offer_price=offer_price,
                multibuy_total=multibuy_total,
                required_quantity=quantity,
            )
            member_program = str(raw_offer.get("member_program") or "").strip() or None
            derived_unit = (
                _money(multibuy_total / quantity)
                if multibuy_total is not None and quantity > 0
                else None
            )
            validity_confidence = (
                "explicit_period"
                if valid_from is not None and valid_to is not None
                else "source_active_without_full_period"
            )
            context_type = str(store.get("price_context_type") or "physical_store")
            scope_label = (
                "EXTERNAL PROVIDER PRICE / verifierad butikskontext"
                if context_type == "physical_store"
                else "EXTERNAL PROVIDER PRICE"
            )
            raw_max_quantity = raw_offer.get("max_quantity")
            try:
                max_quantity = (
                    int(raw_max_quantity) if raw_max_quantity is not None else None
                )
            except (TypeError, ValueError):
                invalid_contracts += 1
                continue
            if max_quantity is not None and max_quantity < 1:
                invalid_contracts += 1
                continue
            offers.append(
                ExternalCurrentOffer(
                    chain=binding.chain,
                    store_display_name=binding.store_display_name,
                    physical_store_id=binding.physical_store_id,
                    grocery_context_id=binding.grocery_context_id,
                    price_context_type=context_type,
                    price_scope_label=scope_label,
                    snapshot_id=product_snapshot_id,
                    observed_at=observed_at,
                    data_age_hours=age_hours,
                    product_id=product_id,
                    gtin=str(product.get("gtin") or "").strip() or None,
                    product_name=product_name,
                    brand=str(product.get("brand") or "").strip() or None,
                    category=str(product.get("category") or "").strip() or None,
                    package_description=_package_description(product),
                    regular_price=regular_price,
                    current_public_price=(
                        offer_price if eligibility is PromotionEligibility.PUBLIC else None
                    ),
                    member_price=(
                        offer_price if eligibility is PromotionEligibility.MEMBER else None
                    ),
                    active_offer_price=offer_price,
                    eligibility=eligibility,
                    mechanism=mechanism,
                    required_quantity=quantity,
                    multibuy_total=multibuy_total,
                    derived_unit_price=derived_unit,
                    derived_unit_price_is_conditional=derived_unit is not None,
                    comparison_price=_decimal(product.get("comparison_price")),
                    comparison_unit=(
                        str(product.get("comparison_unit") or "").strip() or None
                    ),
                    valid_from=valid_from,
                    valid_to=valid_to,
                    validity_confidence=validity_confidence,
                    max_quantity=max_quantity,
                    promotion_condition=str(
                        raw_offer.get("description") or "Aktuellt erbjudande"
                    ).strip(),
                    member_program=member_program,
                    requires_membership=eligibility is PromotionEligibility.MEMBER,
                    semantic_confidence=str(
                        product.get("semantic_confidence") or "unknown"
                    ),
                    quantity_confidence=str(
                        product.get("quantity_confidence") or "unknown"
                    ),
                    promotion_confidence=promotion_confidence,
                    savings_amount=savings_amount,
                    savings_percent=savings_percent,
                    stale=not fresh,
                    lkg_used=not fresh,
                )
            )

    offers.sort(
        key=lambda row: (
            row.store_display_name.casefold(),
            row.product_name.casefold(),
            row.eligibility.value,
            row.mechanism.value,
            row.promotion_condition.casefold(),
        )
    )
    included_by_context: dict[str, int] = {}
    snapshot_by_context: dict[str, str] = {}
    observed_by_context: dict[str, datetime] = {}
    for offer in offers:
        included_by_context[offer.grocery_context_id] = (
            included_by_context.get(offer.grocery_context_id, 0) + 1
        )
        snapshot_by_context[offer.grocery_context_id] = offer.snapshot_id
        observed_by_context[offer.grocery_context_id] = offer.observed_at

    statuses: list[ExternalOfferSourceStatus] = []
    for binding in bindings:
        store = store_rows.get(binding.provider_store_id)
        snapshot = _snapshot_id(store) if store is not None else None
        reason: str | None = None
        if store is None:
            reason = "exact provider context is absent from the active closed cache"
        elif not fresh and not include_stale:
            reason = "closed provider cache exceeds current-offers freshness limit"
        statuses.append(
            ExternalOfferSourceStatus(
                physical_store_id=binding.physical_store_id,
                grocery_context_id=binding.grocery_context_id,
                provider_store_id=binding.provider_store_id,
                snapshot_id=snapshot,
                observed_at=observed_by_context.get(
                    binding.grocery_context_id, captured_at
                ),
                data_age_hours=age_hours,
                fresh=fresh and store is not None,
                lkg_used=not fresh and store is not None,
                offers_included=included_by_context.get(binding.grocery_context_id, 0),
                reason=reason,
            )
        )

    return ExternalOfferLoadResult(
        captured_at=captured_at,
        data_age_hours=age_hours,
        fresh=fresh,
        offers=tuple(offers),
        source_statuses=tuple(statuses),
        diagnostics={
            "bindings_requested": len(bindings),
            "exact_store_rows": len(store_rows),
            "invalid_store_rows": invalid_store_rows,
            "expired_offers_excluded": expired,
            "future_offers_excluded": future,
            "invalid_contracts_excluded": invalid_contracts,
            "invalid_provenance_excluded": invalid_provenance,
        },
    )


def load_closed_primat_current_offer_rows(
    path: Path,
    bindings: Sequence[ExternalStoreOfferBinding],
    *,
    now: datetime | None = None,
    max_age_hours: float = 24,
    include_stale: bool = False,
) -> tuple[dict[str, Any], ...]:
    """Dictionary-oriented convenience wrapper used by report composition."""

    return load_closed_primat_current_offers(
        path,
        bindings,
        now=now,
        max_age_hours=max_age_hours,
        include_stale=include_stale,
    ).rows()


__all__ = [
    "ExternalCurrentOffer",
    "ExternalOfferLoadResult",
    "ExternalOfferSourceStatus",
    "ExternalStoreOfferBinding",
    "load_closed_primat_current_offer_rows",
    "load_closed_primat_current_offers",
    "parse_explicit_multibuy",
]
