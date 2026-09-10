from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, computed_field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.domain.promotion_pricing import (
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.domain.source_strategy import SourceProvider, source_strategy_for
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
)

STOCKHOLM = ZoneInfo("Europe/Stockholm")
LUND_SELECTED_STORES: tuple[str, ...] = (
    "Hemköp Lund Karhögstorg",
    "Hemköp Brunnshög",
    "Stora Coop Lund",
    "Coop Mårtenstorget",
    "ICA Maxi Lund",
    "ICA Malmborgs Lund",
    "Lidl Lund",
)

_MULTIBUY_RE = re.compile(
    r"(?<!\d)(?P<quantity>\d{1,3})\s*(?:st\.?\s*)?(?:för|for)\s*"
    r"(?P<total>\d+(?:[,.]\d{1,2})?)\s*(?:kr|:-)?",
    re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"(?P<percent>\d+(?:[,.]\d+)?)\s*%")
_UNAVAILABLE = frozenset(
    {
        "false",
        "no",
        "not_available",
        "out_of_stock",
        "sold_out",
        "unavailable",
        "0",
    }
)
_KNOWN_AVAILABLE = frozenset(
    {
        "available",
        "available_online",
        "in_stock",
        "true",
        "yes",
        "1",
    }
)
_GENERIC_ALIAS_TOKENS = frozenset({"i", "lund", "butik", "store"})


class OfferSavings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Decimal | None = None
    percent: Decimal | None = None
    regular_qualifying_total: Decimal | None = None
    exclusion_reason: str | None = None


class NormalizedPromotionContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    eligibility: PromotionEligibility
    mechanism: PromotionMechanism
    offer_price: Decimal | None = None
    required_quantity: int = Field(default=1, ge=1)
    multibuy_total: Decimal | None = None
    derived_unit_price: Decimal | None = None
    percent_discount: Decimal | None = None
    member_program: str | None = None
    condition: str | None = None
    semantic_confidence: str


class OfferRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chain: str
    store_alias: str
    store_display_name: str
    physical_store_id: str | None = None
    applicable_physical_store_ids: tuple[str, ...] = ()
    grocery_context_id: str
    price_context_type: str
    price_scope_label: str
    source_provider: str
    source_channel: str
    snapshot_id: str
    observed_at: datetime
    data_age_hours: float = Field(ge=0)
    lkg_used: bool = False
    product_id: str | None = None
    external_product_id: str | None = None
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
    member_program: str | None = None
    requires_membership: bool = False
    required_quantity: int = Field(default=1, ge=1)
    multibuy_total: Decimal | None = None
    derived_unit_price: Decimal | None = None
    derived_unit_price_is_conditional: bool = False
    comparison_price: Decimal | None = None
    comparison_unit: str | None = None
    max_quantity: int | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    validity_confidence: str
    availability: str
    campaign_condition: str | None = None
    semantic_confidence: str
    quantity_confidence: str
    promotion_confidence: str
    price_basis: str
    savings_amount: Decimal | None = None
    savings_percent: Decimal | None = None
    regular_qualifying_total: Decimal | None = None
    savings_exclusion_reason: str | None = None
    active_at_generated_at: bool
    current_data: bool

    @computed_field
    @property
    def promotion_dimensions(self) -> str:
        return f"{self.eligibility.value}+{self.mechanism.value}"


class StoreAliasResolution(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_alias: str
    status: Literal["exact", "ambiguous", "expanded_area_alias", "unresolved"]
    physical_store_ids: tuple[str, ...] = ()
    physical_store_names: tuple[str, ...] = ()
    message: str | None = None


class StoreOfferSection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    store_alias: str
    store_display_name: str
    physical_store_id: str | None = None
    applicable_physical_store_ids: tuple[str, ...] = ()
    grocery_context_id: str
    price_context_type: str
    price_scope_label: str
    source_provider: str
    source_channel: str
    snapshot_id: str | None = None
    observed_at: datetime | None = None
    data_age_hours: float | None = None
    freshness: str
    lkg_used: bool = False
    offers: tuple[OfferRow, ...] = ()
    unavailable_offers: tuple[OfferRow, ...] = ()
    limitation: str | None = None

    @computed_field
    @property
    def public_offer_count(self) -> int:
        return sum(
            row.current_data and row.eligibility is PromotionEligibility.PUBLIC
            for row in self.offers
        )

    @computed_field
    @property
    def member_offer_count(self) -> int:
        return sum(
            row.current_data and row.eligibility is PromotionEligibility.MEMBER
            for row in self.offers
        )

    @computed_field
    @property
    def multibuy_count(self) -> int:
        return sum(
            row.current_data and row.mechanism is PromotionMechanism.MULTIBUY for row in self.offers
        )


class StaleOrIncompleteSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    store_alias: str
    store_display_name: str
    physical_store_id: str | None = None
    grocery_context_id: str | None = None
    source_provider: str | None = None
    source_channel: str | None = None
    snapshot_id: str | None = None
    observed_at: datetime | None = None
    data_age_hours: float | None = None
    lkg_used: bool = False
    status: Literal["stale", "missing", "unavailable", "unresolved"]
    reason: str


class SourceDisagreement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    chain: str
    physical_store_id: str
    gtin: str
    product_name: str
    source_a: str
    price_a: Decimal
    observed_at_a: datetime
    source_b: str
    price_b: Decimal
    observed_at_b: datetime
    difference: Decimal


class CurrentOffersReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "current-offers-report-v1"
    city: str
    timezone: str = "Europe/Stockholm"
    generated_at_local: datetime
    generated_at_utc: datetime
    current_offers_max_age_hours: float
    requested_store_aliases: tuple[str, ...]
    resolutions: tuple[StoreAliasResolution, ...]
    sections: tuple[StoreOfferSection, ...]
    stale_or_incomplete_sources: tuple[StaleOrIncompleteSource, ...]
    source_disagreements: tuple[SourceDisagreement, ...] = ()
    include_stale: bool = False
    filter_mode: str = "all"
    sort_by: str = "savings"
    live_provider_requests: int = 0

    @computed_field
    @property
    def current_offer_count(self) -> int:
        return sum(row.current_data for section in self.sections for row in section.offers)

    @computed_field
    @property
    def refresh_needed(self) -> bool:
        return bool(self.stale_or_incomplete_sources)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    asciiish = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", asciiish.casefold()))


def _tokens(value: str) -> frozenset[str]:
    return frozenset(_fold(value).split())


def _decimal(value: object | None) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).strip().replace(",", "."))
    except Exception:  # noqa: BLE001 - untrusted parsed source field
        return None
    return parsed if parsed > 0 else None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _age_hours(observed_at: datetime, now: datetime) -> float:
    return max(0.0, (_aware_utc(now) - _aware_utc(observed_at)).total_seconds() / 3600)


def classify_offer_validity(
    valid_from: date | None,
    valid_to: date | None,
    on_date: date,
    *,
    source_active: bool = True,
) -> tuple[bool, str]:
    """Return inclusive activity and evidence confidence without inventing dates."""

    active = source_active
    if valid_from is not None and on_date < valid_from:
        active = False
    if valid_to is not None and on_date > valid_to:
        active = False
    if valid_from is not None and valid_to is not None:
        confidence = "verified_full_period"
    elif source_active:
        confidence = "source_active_without_full_period"
    else:
        confidence = "period_incomplete"
    return active, confidence


def _strict_multibuy(condition: str | None) -> tuple[int, Decimal] | None:
    if not condition:
        return None
    match = _MULTIBUY_RE.search(condition)
    if match is None:
        return None
    quantity = int(match.group("quantity"))
    total = _decimal(match.group("total"))
    if quantity < 2 or total is None:
        return None
    return quantity, total


def _member_program(chain: str, *, explicit_member: bool) -> str | None:
    if not explicit_member:
        return None
    return {
        Chain.HEMKOP.value: "Hemköp Klubb",
        Chain.COOP.value: "Coop medlem",
        Chain.ICA.value: "ICA Stammis",
        Chain.LIDL.value: "Lidl Plus",
    }.get(chain)


def normalize_promotion_contract(
    *,
    chain: str,
    promotion_type: str | None,
    price: Decimal | None,
    quantity: int | None,
    member_only: bool,
    description: str | None,
    member_program: str | None = None,
) -> NormalizedPromotionContract:
    """Project source fields onto independent eligibility/mechanism axes."""

    kind = _fold(promotion_type or "")
    description_folded = _fold(description or "")
    explicit_member = member_only or kind in {"member", "member price", "member_price"}
    explicit_member = explicit_member or any(
        marker in description_folded
        for marker in ("medlem", "stammis", "lidl plus", "hemkop klubb")
    )
    eligibility = PromotionEligibility.MEMBER if explicit_member else PromotionEligibility.PUBLIC
    resolved_member_program = member_program or _member_program(
        chain,
        explicit_member=explicit_member,
    )
    parsed_multibuy = _strict_multibuy(description)
    required = quantity if quantity is not None and quantity >= 2 else None
    total = price
    if parsed_multibuy is not None:
        parsed_quantity, parsed_total = parsed_multibuy
        if required is None:
            required = parsed_quantity
        if total is None or (quantity is None or quantity < 2):
            total = parsed_total
    is_multibuy = (
        required is not None
        or parsed_multibuy is not None
        or kind in {"multibuy", "multipack", "multi buy"}
    )
    if is_multibuy and required is not None and total is not None:
        mechanism = PromotionMechanism.MULTIBUY
        return NormalizedPromotionContract(
            eligibility=eligibility,
            mechanism=mechanism,
            offer_price=total,
            required_quantity=required,
            multibuy_total=total,
            derived_unit_price=total / Decimal(required),
            member_program=resolved_member_program,
            condition=description,
            semantic_confidence="explicit_contract",
        )
    percent_match = _PERCENT_RE.search(description or "")
    if "percent" in kind or percent_match is not None:
        percent = _decimal(percent_match.group("percent")) if percent_match else None
        return NormalizedPromotionContract(
            eligibility=eligibility,
            mechanism=PromotionMechanism.PERCENT_DISCOUNT,
            offer_price=price,
            percent_discount=percent,
            member_program=resolved_member_program,
            condition=description,
            semantic_confidence=("explicit_contract" if percent is not None else "incomplete"),
        )
    mechanism = PromotionMechanism.SALE_PRICE if price is not None else PromotionMechanism.OTHER
    return NormalizedPromotionContract(
        eligibility=eligibility,
        mechanism=mechanism,
        offer_price=price,
        member_program=resolved_member_program,
        condition=description,
        semantic_confidence=("explicit_contract" if price is not None else "incomplete"),
    )


def calculate_offer_savings(
    *,
    regular_price: Decimal | None,
    offer_price: Decimal | None,
    mechanism: PromotionMechanism,
    required_quantity: int = 1,
    price_basis_compatible: bool = True,
) -> OfferSavings:
    """Calculate only proven like-for-like savings; never fabricate a baseline."""

    if regular_price is None:
        return OfferSavings(exclusion_reason="regular_price_missing")
    if offer_price is None:
        return OfferSavings(exclusion_reason="active_offer_price_missing")
    if not price_basis_compatible:
        return OfferSavings(exclusion_reason="price_basis_not_comparable")
    quantity = required_quantity if mechanism is PromotionMechanism.MULTIBUY else 1
    if quantity < 1:
        return OfferSavings(exclusion_reason="invalid_required_quantity")
    regular_total = regular_price * Decimal(quantity)
    difference = regular_total - offer_price
    if difference <= 0:
        return OfferSavings(
            regular_qualifying_total=regular_total,
            exclusion_reason="offer_not_cheaper_than_regular",
        )
    return OfferSavings(
        amount=difference,
        percent=difference * Decimal(100) / regular_total,
        regular_qualifying_total=regular_total,
    )


def resolve_store_aliases(
    session: Session,
    city: str,
    aliases: Iterable[str],
) -> tuple[StoreAliasResolution, ...]:
    physical = list(
        session.scalars(
            select(PhysicalStoreModel)
            .where(
                PhysicalStoreModel.is_active.is_(True),
                func.lower(func.trim(PhysicalStoreModel.city)) == city.strip().casefold(),
            )
            .order_by(PhysicalStoreModel.chain, PhysicalStoreModel.name)
        )
    )
    requested = tuple(alias.strip() for alias in aliases if alias.strip())
    if not requested:
        requested = tuple(store.id for store in physical)
    resolutions: list[StoreAliasResolution] = []
    for alias in requested:
        folded = _fold(alias)
        direct = [store for store in physical if store.id.casefold() == alias.casefold()]
        if not direct:
            direct = [store for store in physical if _fold(store.name) == folded]
        if not direct:
            required = _tokens(alias) - _GENERIC_ALIAS_TOKENS
            direct = [
                store for store in physical if required and required.issubset(_tokens(store.name))
            ]
        direct.sort(key=lambda store: (store.chain, store.name, store.id))
        if not direct:
            resolutions.append(
                StoreAliasResolution(
                    requested_alias=alias,
                    status="unresolved",
                    message="No exact registry-backed Lund store matched the alias.",
                )
            )
            continue
        area_expansion = folded in {"lidl lund", "lund lidl"}
        status: Literal["exact", "ambiguous", "expanded_area_alias", "unresolved"]
        if len(direct) == 1:
            status = "exact"
        elif area_expansion and all(store.chain == Chain.LIDL.value for store in direct):
            status = "expanded_area_alias"
        else:
            status = "ambiguous"
        message = None
        if status == "ambiguous":
            message = (
                "Användarens butiksnamn var tvetydigt; samtliga exakta "
                "Lund-kandidater inkluderades separat."
            )
        elif status == "expanded_area_alias":
            message = "Samtliga fysiska Lidl-butiker i Lund inkluderades."
        resolutions.append(
            StoreAliasResolution(
                requested_alias=alias,
                status=status,
                physical_store_ids=tuple(store.id for store in direct),
                physical_store_names=tuple(store.name for store in direct),
                message=message,
            )
        )
    return tuple(resolutions)


def _availability(value: str | None) -> str:
    normalized = _fold(value or "").replace(" ", "_")
    if normalized in _UNAVAILABLE:
        return "unavailable"
    if normalized in _KNOWN_AVAILABLE:
        return "available"
    return "unknown"


def _scope_label(
    *,
    chain: str,
    physical_name: str,
    context_id: str,
    context_type: str | None,
    source_provider: str,
    source_channel: str,
) -> str:
    normalized = _fold(context_type or "")
    if chain == Chain.COOP.value and context_id == "own:coop:730400":
        return "Coop Online Syd / context 730400 – onlinepris, inte verifierat hyllpris"
    if source_provider == SourceProvider.PRIMAT.value:
        return f"Externt providerpris för {physical_name}; inte verifierat hyllpris"
    if source_channel == "offers" and normalized in {"physical store", "physical_store"}:
        return f"Fysiskt butikserbjudande för {physical_name}; availability kan vara okänd"
    if normalized in {"regional", "national", "regional offer", "regional_offer"}:
        return "Regionalt/nationellt erbjudande; inte observerat hyllpris i en viss butik"
    if normalized in {"online fulfillment", "online_fulfillment"}:
        return f"Regionalt onlinepris via {physical_name}; inte verifierat hyllpris"
    return f"Onlinepris för {physical_name}; inte verifierat hyllpris"


def _price_basis(source: SourceProductModel, product: ProductModel | None) -> str:
    sale_model = _fold(product.sale_model if product is not None else source.sale_unit or "")
    comparison_unit = _fold(source.comparison_unit or "")
    if "weight" in sale_model or comparison_unit in {"kg", "sek kg", "kr kg"}:
        return "unit_price_kg"
    if comparison_unit in {"l", "liter", "litre", "sek l", "kr l"}:
        return "unit_price_l"
    return "package_price"


def _sort_offer_rows(
    rows: Iterable[OfferRow],
    *,
    sort_by: str,
) -> tuple[OfferRow, ...]:
    if sort_by == "name":
        key = lambda row: (_fold(row.product_name), row.snapshot_id, row.product_id or "")
    elif sort_by == "category":
        key = lambda row: (
            _fold(row.category or ""),
            _fold(row.product_name),
            row.snapshot_id,
        )
    else:
        key = lambda row: (
            -(row.savings_amount or Decimal(-1)),
            -(row.savings_percent or Decimal(-1)),
            _fold(row.product_name),
            row.snapshot_id,
        )
    return tuple(sorted(rows, key=key))


def _offer_passes_filter(row: OfferRow, filter_mode: str) -> bool:
    if filter_mode == "public":
        return row.eligibility is PromotionEligibility.PUBLIC
    if filter_mode == "member":
        return row.eligibility is PromotionEligibility.MEMBER
    if filter_mode == "multibuy":
        return row.mechanism is PromotionMechanism.MULTIBUY
    return True


class CurrentOffersReportService:
    """Build a read-only current-offer projection over approved persisted sources.

    The service never creates a connector or provider client.  Refresh authority
    remains in ``daily-refresh``; this projection consumes its promoted OWN
    snapshots and optional credential-free, hash-validated Primat artifact.
    """

    def __init__(
        self,
        session: Session,
        *,
        external_cache: Path | None = None,
        max_age_hours: float = 24.0,
    ) -> None:
        if max_age_hours <= 0:
            raise ValueError("max_age_hours must be greater than zero")
        self.session = session
        self.external_cache = external_cache
        self.max_age_hours = max_age_hours

    def build(
        self,
        *,
        city: str = "Lund",
        store_aliases: Iterable[str] = (),
        now: datetime | None = None,
        include_stale: bool = False,
        filter_mode: Literal["all", "public", "member", "multibuy"] = "all",
        sort_by: Literal["savings", "name", "category"] = "savings",
        active_only: bool = True,
    ) -> CurrentOffersReport:
        generated_utc = _aware_utc(now or datetime.now(tz=UTC))
        generated_local = generated_utc.astimezone(STOCKHOLM)
        aliases = tuple(alias.strip() for alias in store_aliases if alias.strip())
        resolutions = resolve_store_aliases(self.session, city, aliases)
        if not aliases:
            aliases = tuple(resolution.requested_alias for resolution in resolutions)
        physical_by_id = {
            store.id: store
            for store in self.session.scalars(
                select(PhysicalStoreModel).where(
                    PhysicalStoreModel.id.in_(
                        tuple(
                            store_id
                            for resolution in resolutions
                            for store_id in resolution.physical_store_ids
                        )
                    )
                )
            )
        }
        sections: list[StoreOfferSection] = []
        incomplete: list[StaleOrIncompleteSource] = []
        seen_sections: set[tuple[str, str, str, str]] = set()

        for resolution in resolutions:
            if resolution.status == "unresolved":
                incomplete.append(
                    StaleOrIncompleteSource(
                        store_alias=resolution.requested_alias,
                        store_display_name=resolution.requested_alias,
                        status="unresolved",
                        reason=resolution.message or "store alias was not resolved",
                    )
                )
                continue
            stores = [
                physical_by_id[store_id]
                for store_id in resolution.physical_store_ids
                if store_id in physical_by_id
            ]
            if (
                resolution.status == "expanded_area_alias"
                and stores
                and all(store.chain == Chain.LIDL.value for store in stores)
            ):
                section, issue = self._regional_lidl_section(
                    resolution=resolution,
                    stores=stores,
                    now=generated_utc,
                    include_stale=include_stale,
                    active_only=active_only,
                    filter_mode=filter_mode,
                    sort_by=sort_by,
                )
                if section is not None:
                    sections.append(section)
                if issue is not None:
                    incomplete.append(issue)
                continue

            for physical in stores:
                built, issues = self._sections_for_physical_store(
                    resolution=resolution,
                    physical=physical,
                    now=generated_utc,
                    include_stale=include_stale,
                    active_only=active_only,
                    filter_mode=filter_mode,
                    sort_by=sort_by,
                )
                for section in built:
                    identity = (
                        section.store_alias,
                        section.grocery_context_id,
                        section.source_provider,
                        section.source_channel,
                    )
                    if identity not in seen_sections:
                        sections.append(section)
                        seen_sections.add(identity)
                incomplete.extend(issues)

        disagreements = _source_disagreements(sections)
        sections.sort(
            key=lambda item: (
                _fold(item.store_alias),
                _fold(item.store_display_name),
                item.source_provider,
                item.source_channel,
                item.grocery_context_id,
            )
        )
        incomplete.sort(
            key=lambda item: (
                _fold(item.store_alias),
                item.source_provider or "",
                item.grocery_context_id or "",
                item.status,
            )
        )
        return CurrentOffersReport(
            city=city.strip(),
            generated_at_local=generated_local,
            generated_at_utc=generated_utc,
            current_offers_max_age_hours=self.max_age_hours,
            requested_store_aliases=aliases,
            resolutions=resolutions,
            sections=tuple(sections),
            stale_or_incomplete_sources=tuple(incomplete),
            source_disagreements=disagreements,
            include_stale=include_stale,
            filter_mode=filter_mode,
            sort_by=sort_by,
        )

    def _sections_for_physical_store(
        self,
        *,
        resolution: StoreAliasResolution,
        physical: PhysicalStoreModel,
        now: datetime,
        include_stale: bool,
        active_only: bool,
        filter_mode: str,
        sort_by: str,
    ) -> tuple[list[StoreOfferSection], list[StaleOrIncompleteSource]]:
        sections: list[StoreOfferSection] = []
        issues: list[StaleOrIncompleteSource] = []
        chain = Chain(physical.chain)
        strategy = source_strategy_for(chain)
        links = list(
            self.session.scalars(
                select(StoreContextLinkModel)
                .where(
                    StoreContextLinkModel.physical_store_id == physical.id,
                    StoreContextLinkModel.is_active.is_(True),
                    StoreContextLinkModel.confidence == "exact",
                )
                .order_by(
                    StoreContextLinkModel.source_provider,
                    StoreContextLinkModel.source_channel,
                    StoreContextLinkModel.grocery_context_id,
                )
            )
        )

        primary_provider = strategy.primary_source.provider.value
        if primary_provider == SourceProvider.OWN.value:
            primary_links = [
                link
                for link in links
                if link.source_provider == SourceProvider.OWN.value
                and link.basket_eligible
                and link.coverage
                in {
                    CoverageLevel.FULL_CATALOG.value,
                    CoverageLevel.FULL_ONLINE_CATALOG.value,
                }
            ]
            for link in primary_links:
                section, issue = self._own_link_section(
                    resolution=resolution,
                    physical=physical,
                    link=link,
                    now=now,
                    include_stale=include_stale,
                    active_only=active_only,
                    filter_mode=filter_mode,
                    sort_by=sort_by,
                )
                if section is not None:
                    sections.append(section)
                if issue is not None:
                    issues.append(issue)
        elif primary_provider == SourceProvider.PRIMAT.value:
            external_links = [
                link
                for link in links
                if link.source_provider == SourceProvider.PRIMAT.value and link.basket_eligible
            ]
            for link in external_links:
                section, issue = self._external_link_section(
                    resolution=resolution,
                    physical=physical,
                    link=link,
                    now=now,
                    include_stale=include_stale,
                    active_only=active_only,
                    filter_mode=filter_mode,
                    sort_by=sort_by,
                )
                if section is not None:
                    sections.append(section)
                if issue is not None:
                    issues.append(issue)

        if strategy.offer_source is not None:
            offer_links = [
                link
                for link in links
                if link.source_provider == strategy.offer_source.provider.value and link.offers_only
            ]
            for link in offer_links:
                section, issue = self._own_link_section(
                    resolution=resolution,
                    physical=physical,
                    link=link,
                    now=now,
                    include_stale=include_stale,
                    active_only=active_only,
                    filter_mode=filter_mode,
                    sort_by=sort_by,
                )
                if section is not None:
                    sections.append(section)
                if issue is not None:
                    issues.append(issue)

        if not sections and not issues:
            issues.append(
                StaleOrIncompleteSource(
                    store_alias=resolution.requested_alias,
                    store_display_name=physical.name,
                    physical_store_id=physical.id,
                    status="unavailable",
                    reason=(
                        "No approved exact source/context link is available under the "
                        f"current {physical.chain} source strategy."
                    ),
                )
            )
        return sections, issues

    def _snapshot_for_link(
        self,
        *,
        physical: PhysicalStoreModel,
        link: StoreContextLinkModel,
    ) -> CatalogSnapshotModel | None:
        if link.snapshot_id:
            snapshot = self.session.get(CatalogSnapshotModel, link.snapshot_id)
            if snapshot is not None and snapshot.is_active:
                return snapshot
            # Catalog links own an exact immutable snapshot pointer.  Grouped
            # physical-offer links instead persist store identity while their
            # chain/city snapshot rotates, so they may resolve the newest active
            # snapshot containing that exact local store.
            if not link.offers_only:
                return None
        local_store_id = self._local_store_id_for_link(physical=physical, link=link)
        if local_store_id:
            return self.session.scalar(
                select(CatalogSnapshotModel)
                .join(
                    PromotionModel,
                    PromotionModel.catalog_snapshot_id == CatalogSnapshotModel.id,
                )
                .where(
                    CatalogSnapshotModel.is_active.is_(True),
                    CatalogSnapshotModel.chain == physical.chain,
                    PromotionModel.store_id == local_store_id,
                )
                .order_by(
                    CatalogSnapshotModel.promoted_at.desc(),
                    CatalogSnapshotModel.created_at.desc(),
                )
                .limit(1)
            )
        return None

    def _local_store_id_for_link(
        self,
        *,
        physical: PhysicalStoreModel,
        link: StoreContextLinkModel,
    ) -> str | None:
        if link.local_store_id is not None:
            return link.local_store_id
        if not link.offers_only or not physical.external_store_id:
            return None
        return self.session.scalar(
            select(StoreModel.id)
            .where(
                StoreModel.chain == physical.chain,
                StoreModel.external_id == physical.external_store_id,
                StoreModel.is_active.is_(True),
            )
            .order_by(StoreModel.last_seen_at.desc())
            .limit(1)
        )

    def _own_link_section(
        self,
        *,
        resolution: StoreAliasResolution,
        physical: PhysicalStoreModel,
        link: StoreContextLinkModel,
        now: datetime,
        include_stale: bool,
        active_only: bool,
        filter_mode: str,
        sort_by: str,
    ) -> tuple[StoreOfferSection | None, StaleOrIncompleteSource | None]:
        snapshot = self._snapshot_for_link(physical=physical, link=link)
        channel = "offers" if link.offers_only else "catalog"
        if snapshot is None:
            return None, StaleOrIncompleteSource(
                store_alias=resolution.requested_alias,
                store_display_name=physical.name,
                physical_store_id=physical.id,
                grocery_context_id=link.grocery_context_id,
                source_provider=link.source_provider,
                source_channel=channel,
                snapshot_id=link.snapshot_id,
                status="missing",
                reason="The exact context has no active promoted snapshot.",
            )
        store_filter = self._local_store_id_for_link(physical=physical, link=link)
        rows = self._promotion_rows(snapshot.id, store_id=store_filter)
        observed_at = min(
            (_aware_utc(row[2].fetched_at) for row in rows), default=None
        ) or _aware_utc(snapshot.created_at)
        age = _age_hours(observed_at, now)
        stale = age > self.max_age_hours
        issue = None
        if stale:
            issue = StaleOrIncompleteSource(
                store_alias=resolution.requested_alias,
                store_display_name=(
                    link.grocery_context_name
                    if not link.offers_only and link.grocery_context_name
                    else physical.name
                ),
                physical_store_id=physical.id,
                grocery_context_id=link.grocery_context_id,
                source_provider=link.source_provider,
                source_channel=channel,
                snapshot_id=snapshot.id,
                observed_at=observed_at,
                data_age_hours=age,
                lkg_used=True,
                status="stale",
                reason="Active LKG exceeds CURRENT_OFFERS_MAX_AGE_HOURS.",
            )
            if not include_stale:
                return None, issue
        context_type = (
            link.price_context_type
            or (rows[0][4].price_context_type if rows else None)
            or ("physical_store" if link.offers_only else "online_store")
        )
        display_name = (
            physical.name if link.offers_only else link.grocery_context_name or physical.name
        )
        scope = _scope_label(
            chain=physical.chain,
            physical_name=physical.name,
            context_id=link.grocery_context_id,
            context_type=context_type,
            source_provider=link.source_provider,
            source_channel=channel,
        )
        offers, unavailable = self._normalize_own_rows(
            rows,
            store_alias=resolution.requested_alias,
            store_display_name=display_name,
            physical_store_id=physical.id,
            applicable_physical_store_ids=(physical.id,),
            grocery_context_id=link.grocery_context_id,
            price_context_type=context_type,
            price_scope_label=scope,
            source_provider=link.source_provider,
            source_channel=channel,
            snapshot_id=snapshot.id,
            now=now,
            observed_at=observed_at,
            age=age,
            stale=stale,
            active_only=active_only,
            filter_mode=filter_mode,
            sort_by=sort_by,
        )
        section = StoreOfferSection(
            store_alias=resolution.requested_alias,
            store_display_name=display_name,
            physical_store_id=physical.id,
            applicable_physical_store_ids=(physical.id,),
            grocery_context_id=link.grocery_context_id,
            price_context_type=context_type,
            price_scope_label=scope,
            source_provider=link.source_provider,
            source_channel=channel,
            snapshot_id=snapshot.id,
            observed_at=observed_at,
            data_age_hours=age,
            freshness="stale" if stale else "fresh",
            lkg_used=stale,
            offers=offers,
            unavailable_offers=unavailable,
            limitation=("Stale LKG is shown outside current totals." if stale else None),
        )
        return section, issue

    def _promotion_rows(
        self,
        snapshot_id: str,
        *,
        store_id: str | None,
    ) -> list[
        tuple[
            PromotionModel,
            ProductModel | None,
            SourceProductModel,
            PriceObservationModel | None,
            StoreModel,
        ]
    ]:
        statement = (
            select(
                PromotionModel,
                ProductModel,
                SourceProductModel,
                PriceObservationModel,
                StoreModel,
            )
            .outerjoin(ProductModel, PromotionModel.product_id == ProductModel.id)
            .join(SourceProductModel, PromotionModel.source_product_id == SourceProductModel.id)
            .outerjoin(
                PriceObservationModel,
                PromotionModel.price_observation_id == PriceObservationModel.id,
            )
            .join(StoreModel, PromotionModel.store_id == StoreModel.id)
            .where(PromotionModel.catalog_snapshot_id == snapshot_id)
        )
        if store_id is not None:
            statement = statement.where(PromotionModel.store_id == store_id)
        return list(
            self.session.execute(
                statement.order_by(SourceProductModel.name, PromotionModel.id)
            ).all()
        )

    def _normalize_own_rows(
        self,
        rows: Iterable[
            tuple[
                PromotionModel,
                ProductModel | None,
                SourceProductModel,
                PriceObservationModel | None,
                StoreModel,
            ]
        ],
        *,
        store_alias: str,
        store_display_name: str,
        physical_store_id: str | None,
        applicable_physical_store_ids: tuple[str, ...],
        grocery_context_id: str,
        price_context_type: str,
        price_scope_label: str,
        source_provider: str,
        source_channel: str,
        snapshot_id: str,
        now: datetime,
        observed_at: datetime,
        age: float,
        stale: bool,
        active_only: bool,
        filter_mode: str,
        sort_by: str,
    ) -> tuple[tuple[OfferRow, ...], tuple[OfferRow, ...]]:
        offers: list[OfferRow] = []
        unavailable: list[OfferRow] = []
        today = now.astimezone(STOCKHOLM).date()
        for promotion, product, source, price_observation, _store in rows:
            active, validity_confidence = classify_offer_validity(
                promotion.valid_from,
                promotion.valid_to,
                today,
                source_active=True,
            )
            if active_only and not active:
                continue
            contract = normalize_promotion_contract(
                chain=source.chain,
                promotion_type=promotion.type,
                price=_decimal(promotion.price),
                quantity=promotion.quantity,
                member_only=promotion.member_only,
                description=promotion.description,
            )
            basis = _price_basis(source, product)
            regular = _decimal(
                price_observation.regular_price
                if price_observation is not None
                else source.regular_price
            )
            comparison = _decimal(
                price_observation.comparison_price
                if price_observation is not None
                else source.comparison_price
            )
            comparison_unit = (
                price_observation.comparison_unit
                if price_observation is not None
                else source.comparison_unit
            )
            offer_price = contract.offer_price
            price_basis_compatible = basis == "package_price"
            savings = calculate_offer_savings(
                regular_price=regular,
                offer_price=offer_price,
                mechanism=contract.mechanism,
                required_quantity=contract.required_quantity,
                price_basis_compatible=price_basis_compatible,
            )
            current_public_price = (
                offer_price
                if contract.eligibility is PromotionEligibility.PUBLIC
                and contract.mechanism is not PromotionMechanism.MULTIBUY
                else None
            )
            member_price = (
                offer_price
                if contract.eligibility is PromotionEligibility.MEMBER
                and contract.mechanism is not PromotionMechanism.MULTIBUY
                else None
            )
            availability = _availability(
                product.availability if product is not None else source.availability
            )
            row = OfferRow(
                chain=source.chain,
                store_alias=store_alias,
                store_display_name=store_display_name,
                physical_store_id=physical_store_id,
                applicable_physical_store_ids=applicable_physical_store_ids,
                grocery_context_id=grocery_context_id,
                price_context_type=price_context_type,
                price_scope_label=price_scope_label,
                source_provider=source_provider,
                source_channel=source_channel,
                snapshot_id=snapshot_id,
                observed_at=observed_at,
                data_age_hours=age,
                lkg_used=stale,
                product_id=product.id if product is not None else promotion.product_id,
                external_product_id=source.external_product_id,
                gtin=(product.gtin if product is not None else source.gtin),
                product_name=product.name if product is not None else source.name,
                brand=product.brand if product is not None else source.brand,
                category=(
                    (product.category_path[-1] if product.category_path else None)
                    if product is not None
                    else (source.category_path[-1] if source.category_path else None)
                ),
                package_description=source.package_text,
                regular_price=regular,
                current_public_price=current_public_price,
                member_price=member_price,
                active_offer_price=offer_price,
                eligibility=contract.eligibility,
                mechanism=contract.mechanism,
                member_program=contract.member_program,
                requires_membership=(contract.eligibility is PromotionEligibility.MEMBER),
                required_quantity=contract.required_quantity,
                multibuy_total=contract.multibuy_total,
                derived_unit_price=contract.derived_unit_price,
                derived_unit_price_is_conditional=(contract.derived_unit_price is not None),
                comparison_price=comparison,
                comparison_unit=comparison_unit,
                max_quantity=promotion.max_quantity,
                valid_from=promotion.valid_from,
                valid_to=promotion.valid_to,
                validity_confidence=validity_confidence,
                availability=availability,
                campaign_condition=promotion.description,
                semantic_confidence=(
                    product.semantic_confidence if product is not None else "unknown"
                ),
                quantity_confidence=(
                    product.quantity_confidence if product is not None else "unknown"
                ),
                promotion_confidence=contract.semantic_confidence,
                price_basis=basis,
                savings_amount=savings.amount,
                savings_percent=savings.percent,
                regular_qualifying_total=savings.regular_qualifying_total,
                savings_exclusion_reason=savings.exclusion_reason,
                active_at_generated_at=active,
                current_data=not stale and active,
            )
            if not _offer_passes_filter(row, filter_mode):
                continue
            if availability == "unavailable":
                unavailable.append(row)
            else:
                offers.append(row)
        return (
            _sort_offer_rows(offers, sort_by=sort_by),
            _sort_offer_rows(unavailable, sort_by=sort_by),
        )

    def _external_link_section(
        self,
        *,
        resolution: StoreAliasResolution,
        physical: PhysicalStoreModel,
        link: StoreContextLinkModel,
        now: datetime,
        include_stale: bool,
        active_only: bool,
        filter_mode: str,
        sort_by: str,
    ) -> tuple[StoreOfferSection | None, StaleOrIncompleteSource | None]:
        del active_only  # The closed-cache adapter always returns active offers only.
        if self.external_cache is None:
            return None, StaleOrIncompleteSource(
                store_alias=resolution.requested_alias,
                store_display_name=physical.name,
                physical_store_id=physical.id,
                grocery_context_id=link.grocery_context_id,
                source_provider=SourceProvider.PRIMAT.value,
                source_channel="catalog",
                snapshot_id=link.snapshot_id,
                status="missing",
                reason="No active credential-free Primat cache is configured.",
            )
        from grocery_data.app.services.current_offers_external import (
            ExternalStoreOfferBinding,
            load_closed_primat_current_offers,
        )

        provider_store_id = link.grocery_context_id.rsplit(":", maxsplit=1)[-1]
        binding = ExternalStoreOfferBinding(
            physical_store_id=physical.id,
            physical_store_external_id=str(physical.external_store_id or ""),
            store_display_name=physical.name,
            chain=physical.chain,
            grocery_context_id=link.grocery_context_id,
            provider_store_id=provider_store_id,
        )
        result = load_closed_primat_current_offers(
            self.external_cache,
            (binding,),
            now=now,
            max_age_hours=self.max_age_hours,
            include_stale=include_stale,
        )
        status = result.source_statuses[0]
        if status.reason is not None:
            issue_status: Literal["stale", "missing", "unavailable", "unresolved"] = (
                "stale" if status.lkg_used else "missing"
            )
            issue = StaleOrIncompleteSource(
                store_alias=resolution.requested_alias,
                store_display_name=physical.name,
                physical_store_id=physical.id,
                grocery_context_id=link.grocery_context_id,
                source_provider=SourceProvider.PRIMAT.value,
                source_channel="catalog",
                snapshot_id=status.snapshot_id,
                observed_at=status.observed_at,
                data_age_hours=status.data_age_hours,
                lkg_used=status.lkg_used,
                status=issue_status,
                reason=status.reason,
            )
            if not include_stale or not status.lkg_used:
                return None, issue
        else:
            issue = None

        rows: list[OfferRow] = []
        unavailable: list[OfferRow] = []
        for offer in result.offers:
            active_offer_price = offer.multibuy_total or offer.active_offer_price
            row = OfferRow(
                chain=offer.chain,
                store_alias=resolution.requested_alias,
                store_display_name=offer.store_display_name,
                physical_store_id=offer.physical_store_id,
                applicable_physical_store_ids=(offer.physical_store_id,),
                grocery_context_id=offer.grocery_context_id,
                price_context_type=offer.price_context_type,
                price_scope_label=(
                    f"Externt providerpris för {physical.name}; inte verifierat hyllpris"
                ),
                source_provider=offer.source_provider,
                source_channel=offer.source_channel,
                snapshot_id=offer.snapshot_id,
                observed_at=offer.observed_at,
                data_age_hours=offer.data_age_hours,
                lkg_used=offer.lkg_used,
                product_id=offer.product_id,
                external_product_id=offer.product_id,
                gtin=offer.gtin,
                product_name=offer.product_name,
                brand=offer.brand,
                category=offer.category,
                package_description=offer.package_description,
                regular_price=offer.regular_price,
                current_public_price=offer.current_public_price,
                member_price=offer.member_price,
                active_offer_price=active_offer_price,
                eligibility=offer.eligibility,
                mechanism=offer.mechanism,
                member_program=offer.member_program,
                requires_membership=offer.requires_membership,
                required_quantity=offer.required_quantity,
                multibuy_total=offer.multibuy_total,
                derived_unit_price=offer.derived_unit_price,
                derived_unit_price_is_conditional=(offer.derived_unit_price_is_conditional),
                comparison_price=offer.comparison_price,
                comparison_unit=offer.comparison_unit,
                max_quantity=offer.max_quantity,
                valid_from=offer.valid_from,
                valid_to=offer.valid_to,
                validity_confidence=offer.validity_confidence,
                availability=offer.availability,
                campaign_condition=offer.promotion_condition,
                semantic_confidence=offer.semantic_confidence,
                quantity_confidence=offer.quantity_confidence,
                promotion_confidence=offer.promotion_confidence,
                price_basis="package_price",
                savings_amount=offer.savings_amount,
                savings_percent=offer.savings_percent,
                savings_exclusion_reason=(
                    None if offer.savings_amount is not None else "regular_price_missing"
                ),
                active_at_generated_at=True,
                current_data=not offer.stale,
            )
            if not _offer_passes_filter(row, filter_mode):
                continue
            if row.availability == "unavailable":
                unavailable.append(row)
            else:
                rows.append(row)
        section = StoreOfferSection(
            store_alias=resolution.requested_alias,
            store_display_name=physical.name,
            physical_store_id=physical.id,
            applicable_physical_store_ids=(physical.id,),
            grocery_context_id=link.grocery_context_id,
            price_context_type=(
                result.offers[0].price_context_type
                if result.offers
                else link.price_context_type or "physical_store"
            ),
            price_scope_label=(
                f"Externt providerpris för {physical.name}; inte verifierat hyllpris"
            ),
            source_provider=SourceProvider.PRIMAT.value,
            source_channel="catalog",
            snapshot_id=status.snapshot_id,
            observed_at=status.observed_at,
            data_age_hours=status.data_age_hours,
            freshness="fresh" if status.fresh else "stale",
            lkg_used=status.lkg_used,
            offers=_sort_offer_rows(rows, sort_by=sort_by),
            unavailable_offers=_sort_offer_rows(unavailable, sort_by=sort_by),
            limitation=(
                "Primat/licensierad full källa; regelbundet baspris saknas i "
                "den aktuella cacheexporten, så besparing fabriceras inte."
            ),
        )
        return section, issue

    def _regional_lidl_section(
        self,
        *,
        resolution: StoreAliasResolution,
        stores: list[PhysicalStoreModel],
        now: datetime,
        include_stale: bool,
        active_only: bool,
        filter_mode: str,
        sort_by: str,
    ) -> tuple[StoreOfferSection | None, StaleOrIncompleteSource | None]:
        snapshot = self.session.scalar(
            select(CatalogSnapshotModel)
            .where(
                CatalogSnapshotModel.chain == Chain.LIDL.value,
                CatalogSnapshotModel.is_active.is_(True),
                CatalogSnapshotModel.coverage == CoverageLevel.OFFERS_ONLY.value,
            )
            .order_by(
                CatalogSnapshotModel.promoted_at.desc(),
                CatalogSnapshotModel.created_at.desc(),
            )
            .limit(1)
        )
        physical_ids = tuple(store.id for store in stores)
        display = "Lidl Lund – regionala erbjudanden"
        context_id = "own:lidl:sverige"
        if snapshot is None:
            return None, StaleOrIncompleteSource(
                store_alias=resolution.requested_alias,
                store_display_name=display,
                grocery_context_id=context_id,
                source_provider=SourceProvider.OWN.value,
                source_channel="offers",
                status="missing",
                reason="No active promoted Lidl regional offer snapshot exists.",
            )
        rows = self._promotion_rows(snapshot.id, store_id=None)
        observed_at = min(
            (_aware_utc(row[2].fetched_at) for row in rows), default=None
        ) or _aware_utc(snapshot.created_at)
        age = _age_hours(observed_at, now)
        stale = age > self.max_age_hours
        issue = None
        if stale:
            issue = StaleOrIncompleteSource(
                store_alias=resolution.requested_alias,
                store_display_name=display,
                grocery_context_id=context_id,
                source_provider=SourceProvider.OWN.value,
                source_channel="offers",
                snapshot_id=snapshot.id,
                observed_at=observed_at,
                data_age_hours=age,
                lkg_used=True,
                status="stale",
                reason="Regional Lidl offer LKG exceeds CURRENT_OFFERS_MAX_AGE_HOURS.",
            )
            if not include_stale:
                return None, issue
        scope = (
            "Lidl Sverige/regionalt erbjudande; inte observerat hyllpris i en specifik Lund-butik"
        )
        offers, unavailable = self._normalize_own_rows(
            rows,
            store_alias=resolution.requested_alias,
            store_display_name=display,
            physical_store_id=None,
            applicable_physical_store_ids=physical_ids,
            grocery_context_id=context_id,
            price_context_type="regional_offer",
            price_scope_label=scope,
            source_provider=SourceProvider.OWN.value,
            source_channel="offers",
            snapshot_id=snapshot.id,
            now=now,
            observed_at=observed_at,
            age=age,
            stale=stale,
            active_only=active_only,
            filter_mode=filter_mode,
            sort_by=sort_by,
        )
        return (
            StoreOfferSection(
                store_alias=resolution.requested_alias,
                store_display_name=display,
                applicable_physical_store_ids=physical_ids,
                grocery_context_id=context_id,
                price_context_type="regional_offer",
                price_scope_label=scope,
                source_provider=SourceProvider.OWN.value,
                source_channel="offers",
                snapshot_id=snapshot.id,
                observed_at=observed_at,
                data_age_hours=age,
                freshness="stale" if stale else "fresh",
                lkg_used=stale,
                offers=offers,
                unavailable_offers=unavailable,
                limitation=(
                    "Lidl Plus-rader är medlemsbundna; personliga eller individuellt "
                    "aktiverade kuponger ingår inte."
                ),
            ),
            issue,
        )


def _comparable_offer_price(row: OfferRow) -> Decimal | None:
    if row.mechanism is PromotionMechanism.MULTIBUY:
        return row.multibuy_total
    return row.active_offer_price


def _source_disagreements(
    sections: Iterable[StoreOfferSection],
) -> tuple[SourceDisagreement, ...]:
    """Compare only strong GTIN identity and identical promotion contracts."""

    grouped: dict[
        tuple[str, str, str, str, int],
        list[OfferRow],
    ] = defaultdict(list)
    for section in sections:
        for row in section.offers:
            if not row.current_data or not row.gtin or not row.physical_store_id:
                continue
            grouped[
                (
                    row.physical_store_id,
                    row.gtin,
                    row.eligibility.value,
                    row.mechanism.value,
                    row.required_quantity,
                )
            ].append(row)
    disagreements: list[SourceDisagreement] = []
    for (physical_id, gtin, _eligibility, _mechanism, _quantity), rows in grouped.items():
        by_source: dict[tuple[str, str, str], OfferRow] = {}
        for row in rows:
            source_key = (
                row.source_provider,
                row.source_channel,
                row.grocery_context_id,
            )
            current = by_source.get(source_key)
            current_price = _comparable_offer_price(current) if current else None
            row_price = _comparable_offer_price(row)
            if row_price is not None and (current_price is None or row_price < current_price):
                by_source[source_key] = row
        source_rows = list(by_source.values())
        source_rows.sort(
            key=lambda row: (
                row.source_provider,
                row.source_channel,
                row.grocery_context_id,
            )
        )
        for left_index, left in enumerate(source_rows):
            left_price = _comparable_offer_price(left)
            if left_price is None:
                continue
            for right in source_rows[left_index + 1 :]:
                right_price = _comparable_offer_price(right)
                if right_price is None or left_price == right_price:
                    continue
                disagreements.append(
                    SourceDisagreement(
                        chain=left.chain,
                        physical_store_id=physical_id,
                        gtin=gtin,
                        product_name=left.product_name,
                        source_a=(
                            f"{left.source_provider}/{left.source_channel}/"
                            f"{left.grocery_context_id}"
                        ),
                        price_a=left_price,
                        observed_at_a=left.observed_at,
                        source_b=(
                            f"{right.source_provider}/{right.source_channel}/"
                            f"{right.grocery_context_id}"
                        ),
                        price_b=right_price,
                        observed_at_b=right.observed_at,
                        difference=abs(left_price - right_price),
                    )
                )
    disagreements.sort(
        key=lambda item: (
            item.chain,
            item.physical_store_id,
            -item.difference,
            item.gtin,
        )
    )
    return tuple(disagreements)


def _atomic_write_text(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(value)
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def _csv_safe(value: object | None) -> object:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (tuple, list)):
        value = ";".join(str(item) for item in value)
    if isinstance(value, (PromotionEligibility, PromotionMechanism)):
        value = value.value
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value


_CSV_FIELDS: tuple[str, ...] = (
    "chain",
    "store_alias",
    "store_display_name",
    "physical_store_id",
    "applicable_physical_store_ids",
    "grocery_context_id",
    "price_context_type",
    "price_scope_label",
    "source_provider",
    "source_channel",
    "snapshot_id",
    "observed_at",
    "data_age_hours",
    "lkg_used",
    "product_id",
    "external_product_id",
    "gtin",
    "product_name",
    "brand",
    "category",
    "package_description",
    "regular_price",
    "current_public_price",
    "member_price",
    "active_offer_price",
    "eligibility",
    "mechanism",
    "member_program",
    "requires_membership",
    "required_quantity",
    "multibuy_total",
    "derived_unit_price",
    "derived_unit_price_is_conditional",
    "comparison_price",
    "comparison_unit",
    "max_quantity",
    "valid_from",
    "valid_to",
    "validity_confidence",
    "availability",
    "campaign_condition",
    "semantic_confidence",
    "quantity_confidence",
    "promotion_confidence",
    "price_basis",
    "savings_amount",
    "savings_percent",
    "regular_qualifying_total",
    "savings_exclusion_reason",
    "active_at_generated_at",
    "current_data",
)


def _all_offer_rows(report: CurrentOffersReport) -> Iterable[OfferRow]:
    for section in report.sections:
        yield from section.offers
        yield from section.unavailable_offers


def _money_label(value: Decimal | None) -> str:
    if value is None:
        return "–"
    return f"{value.quantize(Decimal('0.01'))} kr"


def _offer_label(row: OfferRow) -> str:
    if row.mechanism is PromotionMechanism.MULTIBUY:
        price = f"{row.required_quantity} för {_money_label(row.multibuy_total)}"
        if row.derived_unit_price is not None:
            price += (
                f" (härlett {_money_label(row.derived_unit_price)}/st "
                f"vid köp av {row.required_quantity})"
            )
    else:
        price = _money_label(row.active_offer_price)
    member = f"; kräver {row.member_program or 'medlemskap'}" if row.requires_membership else ""
    return f"{price}{member}"


def _md(value: object | None) -> str:
    if value is None:
        return "–"
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def render_current_offers_markdown(report: CurrentOffersReport) -> str:
    lines = [
        "# Aktuella erbjudanden",
        "",
        f"Genererad: {report.generated_at_local.isoformat()} ({report.timezone})  ",
        f"UTC: {report.generated_at_utc.isoformat()}  ",
        f"Aktuellhetsgräns: {report.current_offers_max_age_hours:g} timmar",
        "",
    ]
    for resolution in report.resolutions:
        if resolution.message:
            lines.extend(
                (
                    f"> **{_md(resolution.requested_alias)}:** {_md(resolution.message)}",
                    "",
                )
            )
    for section in report.sections:
        lines.extend(
            (
                f"## {_md(section.store_alias)} — {_md(section.store_display_name)}",
                "",
                f"- Källa: `{_md(section.source_provider)}` / `{_md(section.source_channel)}`",
                f"- Context: `{_md(section.grocery_context_id)}`",
                f"- Scope: {_md(section.price_scope_label)}",
                f"- Snapshot: `{_md(section.snapshot_id)}`",
                f"- Dataålder: {section.data_age_hours:.2f} h"
                if section.data_age_hours is not None
                else "- Dataålder: okänd",
                f"- Offentliga: {section.public_offer_count}; medlem: {section.member_offer_count}; flerköp: {section.multibuy_count}",
                "",
                "| Produkt | Förpackning | Erbjudande | Eligibility | Mekanism | Ordinarie | Besparing | Giltighet | Jämförpris |",
                "|---|---|---|---|---|---:|---:|---|---|",
            )
        )
        for row in section.offers:
            validity = f"{row.valid_from or '?'}–{row.valid_to or '?'} ({row.validity_confidence})"
            comparison = (
                f"{_money_label(row.comparison_price)} {row.comparison_unit or ''}".strip()
                if row.comparison_price is not None
                else "–"
            )
            savings = (
                f"{_money_label(row.savings_amount)} ({row.savings_percent:.1f} %)"
                if row.savings_amount is not None and row.savings_percent is not None
                else "–"
            )
            lines.append(
                "| "
                + " | ".join(
                    (
                        _md(row.product_name),
                        _md(row.package_description),
                        _md(_offer_label(row)),
                        _md(row.eligibility.value),
                        _md(row.mechanism.value),
                        _md(_money_label(row.regular_price)),
                        _md(savings),
                        _md(validity),
                        _md(comparison),
                    )
                )
                + " |"
            )
        if not section.offers:
            lines.append("| _Inga aktuella köpbara erbjudanden i denna kanal._ | | | | | | | | |")
        if section.limitation:
            lines.extend(("", f"> Begränsning: {_md(section.limitation)}"))
        lines.append("")

    lines.extend(("## Stale / incomplete sources", ""))
    if report.stale_or_incomplete_sources:
        for source in report.stale_or_incomplete_sources:
            age = f", {source.data_age_hours:.2f} h" if source.data_age_hours is not None else ""
            lkg = ", LKG" if source.lkg_used else ""
            lines.append(
                f"- **{_md(source.store_alias)} / {_md(source.store_display_name)}**: "
                f"{_md(source.status)}{age}{lkg} — {_md(source.reason)}"
            )
    else:
        lines.append("- Inga.")
    lines.extend(("", "## Source disagreements", ""))
    if report.source_disagreements:
        for conflict in report.source_disagreements:
            lines.append(
                f"- {_md(conflict.product_name)} (`{_md(conflict.gtin)}`): "
                f"{_md(conflict.source_a)} {_money_label(conflict.price_a)} vs "
                f"{_md(conflict.source_b)} {_money_label(conflict.price_b)}."
            )
    else:
        lines.append("- Inga säkert identifierade prisavvikelser mellan källor.")
    lines.append("")
    return "\n".join(lines)


def write_current_offers_exports(
    report: CurrentOffersReport,
    output_dir: Path,
) -> dict[str, Path]:
    """Atomically write JSON, CSV and Markdown from the same frozen model."""

    stamp = report.generated_at_utc.strftime("%Y%m%dT%H%M%S.%fZ")
    base = output_dir.resolve() / f"current-offers-{stamp}"
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    md_path = base.with_suffix(".md")
    _atomic_write_text(
        json_path,
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=csv_path.parent,
        prefix=f".{csv_path.name}.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in _all_offer_rows(report):
            values = row.model_dump(exclude={"promotion_dimensions"})
            writer.writerow({key: _csv_safe(values.get(key)) for key in _CSV_FIELDS})
        handle.flush()
        temporary = Path(handle.name)
    temporary.replace(csv_path)
    _atomic_write_text(md_path, render_current_offers_markdown(report))
    return {"json": json_path, "csv": csv_path, "markdown": md_path}


def render_current_offers_summary(report: CurrentOffersReport) -> str:
    lines = [
        "AKTUELLA ERBJUDANDEN",
        "=" * 72,
        (
            f"Genererad: {report.generated_at_local.strftime('%Y-%m-%d %H:%M:%S %Z')} "
            f"| UTC {report.generated_at_utc.strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        f"Aktuellhetsgräns: {report.current_offers_max_age_hours:g} h",
    ]
    for resolution in report.resolutions:
        if resolution.message:
            lines.append(f"OBS {resolution.requested_alias}: {resolution.message}")
    for section in report.sections:
        lines.extend(
            (
                "",
                f"{section.store_alias} — {section.store_display_name}",
                f"  Offentliga kampanjer: {section.public_offer_count}",
                f"  Medlemskampanjer: {section.member_offer_count}",
                f"  Flerköp: {section.multibuy_count}",
                (
                    f"  Dataålder: {section.data_age_hours:.2f} h "
                    f"({section.freshness.upper()}{', LKG' if section.lkg_used else ''})"
                    if section.data_age_hours is not None
                    else "  Dataålder: okänd"
                ),
                f"  Källa: {section.source_provider}/{section.source_channel}",
                f"  Scope: {section.price_scope_label}",
            )
        )
        current_rows = [row for row in section.offers if row.current_data]
        ranked = [row for row in current_rows if row.savings_amount is not None]
        top = (ranked or current_rows)[:5]
        if top:
            lines.append(
                "  Mest ekonomiskt attraktiva verifierbara erbjudanden:"
                if ranked
                else (
                    "  Aktuella erbjudanden (besparingsranking är inte möjlig utan "
                    "verifierat ordinarie pris):"
                )
            )
            for row in top:
                savings = (
                    f", sparar {_money_label(row.savings_amount)}"
                    if row.savings_amount is not None
                    else ", verifierbar besparing saknas"
                )
                lines.append(f"    - {row.product_name}: {_offer_label(row)}{savings}")
        else:
            lines.append("  Inga köpbara aktuella erbjudanden i huvudlistan.")
        if section.limitation:
            lines.append(f"  Begränsning: {section.limitation}")

    lines.extend(("", "STALE / INCOMPLETE SOURCES", "-" * 72))
    if report.stale_or_incomplete_sources:
        for source in report.stale_or_incomplete_sources:
            age = f" | {source.data_age_hours:.2f} h" if source.data_age_hours is not None else ""
            lkg = " | LKG" if source.lkg_used else ""
            lines.append(
                f"{source.store_alias} — {source.store_display_name}: "
                f"{source.status.upper()}{age}{lkg} | {source.reason}"
            )
    else:
        lines.append("<none>")
    lines.extend(("", "SOURCE DISAGREEMENTS", "-" * 72))
    if report.source_disagreements:
        for conflict in report.source_disagreements[:20]:
            lines.append(
                f"{conflict.product_name} [{conflict.gtin}] | "
                f"{conflict.source_a} {_money_label(conflict.price_a)} vs "
                f"{conflict.source_b} {_money_label(conflict.price_b)}"
            )
    else:
        lines.append("<none with strong identity and comparable contract>")
    return "\n".join(lines)


__all__ = [
    "LUND_SELECTED_STORES",
    "CurrentOffersReport",
    "CurrentOffersReportService",
    "NormalizedPromotionContract",
    "OfferRow",
    "OfferSavings",
    "SourceDisagreement",
    "StaleOrIncompleteSource",
    "StoreAliasResolution",
    "StoreOfferSection",
    "calculate_offer_savings",
    "classify_offer_validity",
    "normalize_promotion_contract",
    "render_current_offers_markdown",
    "render_current_offers_summary",
    "resolve_store_aliases",
    "write_current_offers_exports",
]
