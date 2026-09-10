from __future__ import annotations

import html
import re
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from grocery_data.app.connectors.lidl.client import LidlClient
from grocery_data.app.connectors.lidl.models import (
    LidlSchemaError,
    validated_search_page,
    validated_store_detail,
)
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ParseFailure,
    ParserErrorCode,
    PriceContextType,
    ProductParseResult,
    PromotionType,
    RawBatch,
    SourceOffer,
    SourceProduct,
    SourceStore,
)
from grocery_data.app.services.exact_identity_reconciliation import (
    SharedOfferScope,
    classify_shared_offer_scope,
)

_COMPARISON = re.compile(
    r"(?P<price>\d+(?:[.,]\d+)?)\s*kr\s*/\s*(?P<unit>kg|l|st(?:yck)?)\b",
    re.IGNORECASE,
)
_SIMPLE_PACKAGE = re.compile(
    r"(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|l|ml|st(?:yck)?)"
    r"(?:\s*/\s*f[öo]rp\.?)?",
    re.IGNORECASE,
)
_MULTIPACK_PACKAGE = re.compile(
    r"(?P<count>\d+)\s*[x×]\s*(?P<quantity>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>kg|g|l|ml|st(?:yck)?)",
    re.IGNORECASE,
)
_APPROX_WEIGHT = re.compile(
    r"/\s*(?P<sale_unit>kg|l)\s*\(\s*(?:ca|cirka)\s*"
    r"(?P<quantity>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|l|ml)\s*\)",
    re.IGNORECASE,
)
_MULTIBUY = re.compile(r"(?P<count>\d+)\s*f[öo]r\s*:?")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed > 0 else None


def _valid_gtin(value: Any) -> str | None:
    """Accept only checksum-valid explicit GTIN-8/12/13/14 values."""

    if isinstance(value, bool):
        return None
    digits = str(value or "").strip()
    if len(digits) not in {8, 12, 13, 14} or not digits.isascii() or not digits.isdigit():
        return None
    body, supplied_check_digit = digits[:-1], int(digits[-1])
    weighted_sum = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(body))
    )
    expected_check_digit = (10 - weighted_sum % 10) % 10
    return digits if supplied_check_digit == expected_check_digit else None


def _unit(value: str) -> str:
    normalized = value.casefold()
    return "st" if normalized.startswith("st") else normalized


def _package(value: str | None) -> tuple[Decimal | None, str | None, int | None]:
    text = (value or "").strip()
    multi = _MULTIPACK_PACKAGE.fullmatch(text)
    if multi:
        count = int(multi.group("count"))
        quantity = _decimal(multi.group("quantity"))
        assert quantity is not None
        return quantity * count, _unit(multi.group("unit")), count
    simple = _SIMPLE_PACKAGE.fullmatch(text)
    if simple:
        return _decimal(simple.group("quantity")), _unit(simple.group("unit")), None
    return None, None, None


def _comparison(value: str | None) -> tuple[Decimal | None, str | None]:
    match = _COMPARISON.search(value or "")
    if match is None:
        return None, None
    return _decimal(match.group("price")), _unit(match.group("unit"))


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.strip()).date()
    except ValueError:
        return None


def _epoch_date(value: Any) -> date | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC).date()
    except (OSError, OverflowError, ValueError):
        return None


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = html.unescape(value).strip()
    return normalized or None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class LidlParser:
    """Offline parser for Lidl's public regional offer/search source."""

    parser_version = "lidl-parser-v3"

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        if area.city.casefold().strip() == "sverige":
            probes = [
                (document, reference)
                for document, reference in raw.with_references(references)
                if document.kind == "offer_context_probe"
            ]
            if len(probes) != 1:
                raise LidlSchemaError("Lidl national discovery requires one context probe")
            document, reference = probes[0]
            page = validated_search_page(document.payload, requested_offset=0)
            if not page.items or "1" not in _object(page.items[0].get("regionsPrices")):
                raise LidlSchemaError("Lidl context probe does not prove public region 1")
            return [self._regional_offer_context(reference=reference, requested_city=area.city)]

        stores: dict[str, SourceStore] = {}
        index_reference: str | None = None
        for document, reference in raw.with_references(references):
            if document.kind == "store_index":
                index_reference = reference
                continue
            if document.kind != "store_detail" or document.http_status != 200:
                continue
            row = validated_store_detail(document.payload)
            source_city = str(row["city"]).strip()
            if source_city.casefold() != area.city.casefold():
                raise LidlSchemaError("Lidl store detail escaped the requested city scope")
            external_id = str(row["external_id"])
            if external_id in stores:
                raise LidlSchemaError("Lidl store discovery returned duplicate TNC identities")
            stores[external_id] = SourceStore(
                chain=Chain.LIDL,
                external_id=external_id,
                name=str(row["name"]),
                address=str(row["address"]),
                postal_code=str(row["postal_code"]),
                city=source_city,
                latitude=_decimal(row.get("latitude")),
                longitude=_decimal(row.get("longitude")),
                online_shopping=None,
                coverage=CoverageLevel.OFFERS_ONLY,
                price_context_type=PriceContextType.PHYSICAL_STORE,
                raw_reference=reference,
                source_fields={
                    "canonical_url": row["canonical_url"],
                    "external_id_namespace": row.get("id_namespace"),
                    "external_id_stability": row.get("id_stability"),
                    "public_offer_price_assigned": False,
                },
            )
        if not stores or index_reference is None:
            raise LidlSchemaError("Lidl store discovery lacks index or detail evidence")
        # Public search currently exposes one unselected default price region.
        # It is deliberately a separate commercial context: the same rows are
        # never relabelled as exact prices for any physical Lund/Malmö store.
        stores[LidlClient.public_offer_context_id] = self._regional_offer_context(
            reference=index_reference,
            requested_city=area.city,
        )
        return sorted(stores.values(), key=lambda store: (store.name.casefold(), store.external_id))

    @staticmethod
    def _regional_offer_context(*, reference: str, requested_city: str) -> SourceStore:
        return SourceStore(
            chain=Chain.LIDL,
            external_id=LidlClient.public_offer_context_id,
            name="Lidl Sverige – publika erbjudanden (standardregion)",
            city="Sverige",
            online_shopping=False,
            coverage=CoverageLevel.OFFERS_ONLY,
            price_context_type=PriceContextType.REGIONAL,
            raw_reference=reference,
            source_fields={
                "price_scope": "unselected_public_default_region",
                "price_region_id": "1",
                "store_price_verified": False,
                "requested_city": requested_city,
                "operational_collection_scope": "single_national_default_region_snapshot",
                "availability_scope": "campaign_window_not_stock",
            },
        )

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        if store.external_id != LidlClient.public_offer_context_id:
            raise LidlSchemaError("Lidl offer rows require the separate regional context")
        products: dict[str, SourceProduct] = {}
        failures: list[ParseFailure] = []
        for document, reference in raw.with_references(references):
            if document.kind != "offer_page":
                continue
            try:
                page = validated_search_page(
                    document.payload,
                    requested_offset=int(document.query.get("offset", "0")),
                )
            except LidlSchemaError as exc:
                failures.append(self._failure(reference, ParserErrorCode.SCHEMA_CHANGED, exc))
                continue
            for position, row in enumerate(page.items):
                item_reference = f"{reference}#items[{position}].gridbox.data"
                try:
                    product = self._parse_product(
                        row,
                        store=store,
                        reference=item_reference,
                        fetched_at=document.fetched_at,
                    )
                except (LidlSchemaError, ValidationError, ValueError) as exc:
                    failures.append(self._failure(item_reference, ParserErrorCode.UNKNOWN, exc))
                    continue
                identity = product.external_product_id or ""
                if identity in products:
                    failures.append(
                        self._failure(
                            item_reference,
                            ParserErrorCode.SCHEMA_CHANGED,
                            LidlSchemaError("Lidl product identity repeated across raw pages"),
                        )
                    )
                    continue
                products[identity] = product
        return ProductParseResult(products=list(products.values()), failures=failures)

    def _parse_product(
        self,
        row: dict[str, Any],
        *,
        store: SourceStore,
        reference: str,
        fetched_at: datetime,
    ) -> SourceProduct:
        product_id = str(row.get("productId") or "").strip()
        name = _text(row.get("title"))
        if not product_id:
            raise LidlSchemaError("Lidl productId is missing")
        if name is None:
            raise LidlSchemaError("Lidl product title is missing")
        region_id = str(store.source_fields.get("price_region_id") or "")
        regions_prices = _object(row.get("regionsPrices"))
        region = _object(regions_prices.get(region_id))
        if not region:
            raise LidlSchemaError("Lidl product lacks the declared public price region")
        member_wrapper = _object(region.get("currentLidlPlusPrice"))
        public_price = _object(region.get("currentPrice"))
        member_only = bool(member_wrapper)
        price_model = _object(member_wrapper.get("price")) if member_only else public_price
        if not price_model:
            raise LidlSchemaError("Lidl region row lacks current price data")
        amount = _decimal(price_model.get("price"))
        if amount is None:
            raise LidlSchemaError("Lidl current price is missing or invalid")
        old_price = _decimal(price_model.get("oldPrice"))
        discount = _object(price_model.get("discount"))
        discount_text = _text(discount.get("discountText")) or ""
        multi = _MULTIBUY.search(discount_text.casefold())
        package_text = _text(_object(price_model.get("packaging")).get("text"))
        base_price_text = _text(_object(price_model.get("basePrice")).get("text"))
        comparison_price, comparison_unit = _comparison(base_price_text)
        package_quantity, package_unit, package_count = _package(package_text)

        sale_unit = "st"
        basket_type = "ST"
        average_weight_kg: Decimal | None = None
        variable = _APPROX_WEIGHT.fullmatch(package_text or "")
        raw_unit_text = " ".join(filter(None, (package_text, base_price_text))).casefold()
        if variable is not None:
            sale_unit = _unit(variable.group("sale_unit"))
            average = _decimal(variable.group("quantity"))
            average_unit = _unit(variable.group("unit"))
            if average is not None:
                average_weight_kg = (
                    average / 1000
                    if average_unit in {"g", "ml"}
                    else average
                )
            basket_type = "ST"
            package_quantity = None
            package_unit = None
        elif re.match(r"^\s*/\s*kg\b", raw_unit_text):
            sale_unit = "kg"
            basket_type = "VIKT"
            package_quantity = None
            package_unit = None
        elif re.match(r"^\s*/\s*l\b", raw_unit_text):
            sale_unit = "l"
            basket_type = "VIKT"
            package_quantity = None
            package_unit = None

        valid_from = _iso_date(price_model.get("startDate")) or _epoch_date(
            row.get("storeStartDate")
        )
        valid_to = _iso_date(price_model.get("endDate")) or _epoch_date(row.get("storeEndDate"))
        percentage = discount.get("percentageDiscount")
        if member_only:
            promotion_type = PromotionType.MULTIBUY if multi else PromotionType.MEMBER_PRICE
        elif multi:
            promotion_type = PromotionType.MULTIBUY
        elif isinstance(percentage, (int, float)) and not isinstance(percentage, bool):
            promotion_type = PromotionType.PERCENT_DISCOUNT
        elif discount or discount_text:
            promotion_type = PromotionType.SALE_PRICE
        else:
            # Presence in the public publishing surface is useful offer
            # lineage, but without a source discount signal it is not proof
            # that the amount is a reduced sale price.
            promotion_type = PromotionType.OTHER
        lidl_plus_text = _text(member_wrapper.get("lidlPlusText"))
        offer_scope = classify_shared_offer_scope(
            chain=Chain.LIDL,
            member_only=member_only,
            description=lidl_plus_text if member_only else discount_text,
            source_payload={"discount_text": discount_text or None},
            source_fields={"public_lidl_plus": member_only},
        )
        shared_offer_eligible = offer_scope in {
            SharedOfferScope.PUBLIC,
            SharedOfferScope.GENERIC_MEMBER,
        }
        offer = SourceOffer(
            type=promotion_type,
            valid_from=valid_from,
            valid_to=valid_to,
            price=amount,
            quantity=int(multi.group("count")) if multi else None,
            member_only=member_only,
            description=(
                lidl_plus_text
                if member_only
                else discount_text or "Publicerad Lidl-produktrad; prisstatus ej typad"
            ),
            source_payload={
                "price_region_id": region_id,
                "discount_text": discount_text or None,
                "percentage_discount": percentage,
                "deleted_price": str(old_price) if old_price is not None else None,
                "package_count": package_count,
                "member_offer_scope": offer_scope.value,
                "shared_price_universe_eligible": shared_offer_eligible,
            },
        )
        brand = _text(_object(row.get("brand")).get("name"))
        category_text = _text(_object(row.get("keyfacts")).get("wonCategoryPrimary"))
        category_path = tuple(
            part.strip() for part in (category_text or "").split("/") if part.strip()
        )
        badges = _object(row.get("stockAvailability")).get("badgeInfoV2")
        raw_ean = row.get("_explicit_gridbox_meta_ean")
        gtin = _valid_gtin(raw_ean)
        return SourceProduct(
            chain=Chain.LIDL,
            store_external_id=store.external_id,
            external_product_id=product_id,
            # Only the explicitly named gridbox.meta.ean source field is
            # eligible, and only after GTIN checksum validation. Numeric Lidl
            # productId/erpNumber values are never promoted to GTIN.
            gtin=gtin,
            name=name,
            brand=brand,
            category_path=category_path,
            # A multibuy total is conditional and must never masquerade as a
            # one-package current price. Member rows retain their public
            # regular amount while member_price remains conditional.
            sale_price=(old_price if member_only else None if multi else amount),
            regular_price=(old_price or amount) if not multi or member_only else None,
            member_price=amount if member_only and not multi else None,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            package_text=package_text,
            package_quantity=package_quantity,
            package_unit=package_unit,
            sale_unit=sale_unit,
            offers=(offer,),
            availability="campaign_window" if valid_from or valid_to else None,
            average_weight_kg=average_weight_kg,
            basket_type=basket_type,
            raw_reference=reference,
            fetched_at=fetched_at,
            source_fields={
                "erp_number": row.get("erpNumber"),
                "item_id": row.get("itemId"),
                "raw_gtin": str(raw_ean).strip() if raw_ean is not None else None,
                "raw_gtin_valid": gtin is not None,
                "gtin_evidence": "explicit_gridbox_meta_ean" if gtin is not None else None,
                "canonical_path": row.get("canonicalPath"),
                "product_type": row.get("productType"),
                "analytics_category": _object(row.get("keyfacts")).get(
                    "analyticsCategory"
                ),
                "price_scope": "unselected_public_default_region",
                "price_region_id": region_id,
                "store_price_verified": False,
                "availability_scope": "campaign_window_not_stock",
                "stock_badges": badges if isinstance(badges, list) else [],
                "online_available": _object(row.get("stockAvailability")).get(
                    "onlineAvailable"
                ),
                "public_lidl_plus": (
                    member_only and offer_scope is SharedOfferScope.GENERIC_MEMBER
                ),
                "personalized_coupon": offer_scope is SharedOfferScope.USER_SPECIFIC,
                "coupon_scope_unknown": offer_scope is SharedOfferScope.UNKNOWN,
                "member_offer_scope": offer_scope.value,
                "shared_price_universe_eligible": shared_offer_eligible,
                "package_count": package_count,
            },
        )

    def _failure(
        self,
        reference: str,
        code: ParserErrorCode,
        exc: Exception,
    ) -> ParseFailure:
        return ParseFailure(
            raw_record_reference=reference,
            error_code=code,
            error_message=str(exc)[:300],
            parser_version=self.parser_version,
        )
