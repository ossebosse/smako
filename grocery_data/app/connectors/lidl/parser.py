from __future__ import annotations

import html
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

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
_SWEDEN = ZoneInfo("Europe/Stockholm")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _valid_gtin(value: Any) -> str | None:
    """Accept only checksum-valid explicit GTIN-8/12/13/14 values."""

    if isinstance(value, bool):
        return None
    digits = str(value or "").strip()
    if len(digits) not in {8, 12, 13, 14} or not digits.isascii() or not digits.isdigit():
        return None
    body, supplied_check_digit = digits[:-1], int(digits[-1])
    weighted_sum = sum(
        int(digit) * (3 if index % 2 == 0 else 1) for index, digit in enumerate(reversed(body))
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
        if count <= 0 or quantity is None:
            raise LidlSchemaError("Lidl multipack quantity must be positive")
        return quantity * count, _unit(multi.group("unit")), count
    simple = _SIMPLE_PACKAGE.fullmatch(text)
    if simple:
        quantity = _decimal(simple.group("quantity"))
        if quantity is None:
            raise LidlSchemaError("Lidl package quantity must be positive")
        return quantity, _unit(simple.group("unit")), None
    return None, None, None


def _comparison(value: str | None) -> tuple[Decimal | None, str | None]:
    # A rate label such as '/kg (Ca 650 g)' describes variable package weight,
    # not an approximate comparison-price amount.
    if not re.search(r"\bkr\b", value or "", re.IGNORECASE):
        return None, None
    if re.search(r"\d\s*[-–]\s*\d|\b(?:från|upp till|cirka|ca)\b", value or "", re.IGNORECASE):
        raise LidlSchemaError("Lidl comparison-price range or approximation is not exact")
    if len(list(_COMPARISON.finditer(value or ""))) > 1:
        raise LidlSchemaError("Lidl comparison price has multiple possible amounts")
    match = _COMPARISON.search(value or "")
    if match is None:
        return None, None
    return _decimal(match.group("price")), _unit(match.group("unit"))


def _iso_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise LidlSchemaError("Lidl price date must be an ISO timestamp")
    try:
        result = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise LidlSchemaError("Lidl price date is invalid") from exc
    if result.tzinfo is None:
        raise LidlSchemaError("Lidl price timestamp lacks timezone")
    return result


def _epoch_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LidlSchemaError("Lidl store date must be epoch seconds")
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (OSError, OverflowError, ValueError) as exc:
        raise LidlSchemaError("Lidl store date is invalid") from exc


def _window(row: dict[str, Any], price: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    # A price model's start can precede its advertised in-store week. Intersect
    # the two source windows; never extend a price into a later badge/week.
    starts = [_iso_time(price.get("startDate")), _epoch_time(row.get("storeStartDate"))]
    ends = [_iso_time(price.get("endDate")), _epoch_time(row.get("storeEndDate"))]
    exclusive = _iso_time(price.get("endDateExclusive"))
    if exclusive is not None:
        ends.append(exclusive - timedelta(microseconds=1))
    start = max((value for value in starts if value is not None), default=None)
    end = min((value for value in ends if value is not None), default=None)
    if start is not None and end is not None and start > end:
        raise LidlSchemaError("Lidl price and in-store date windows do not intersect")
    return start, end


def _at_observation(start: datetime | None, end: datetime | None, at: datetime) -> bool:
    # Offers without an end stay as conditional source evidence, not an
    # indefinitely current unconditional price.
    if at.tzinfo is None:
        raise LidlSchemaError("Lidl observation timestamp lacks timezone")
    return start is not None and end is not None and start <= at <= end


def _validated_price(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise LidlSchemaError("Lidl region row lacks current price data")
    allowed = {
        "basePrice",
        "currencyCode",
        "currencyCodeSecond",
        "currencySymbol",
        "currencySymbolSecond",
        "discount",
        "endDate",
        "endDateExclusive",
        "hasStar",
        "hasVat",
        "oldPrice",
        "packaging",
        "price",
        "priceTheme",
        "priceLegendName",
        "priceLegendText",
        "specialTaxes",
        "startDate",
        "superscript",
        "variantsHaveDifferentPrices",
    }
    if set(value) - allowed:
        raise LidlSchemaError("Lidl price model contains an unreviewed field")
    for field in ("priceLegendName", "priceLegendText"):
        if field in value and not isinstance(value[field], str):
            raise LidlSchemaError("Lidl price legend must be text")
    if _decimal(value.get("price")) is None:
        raise LidlSchemaError("Lidl current price is missing or invalid")
    if value.get("oldPrice") is not None and _decimal(value["oldPrice"]) is None:
        raise LidlSchemaError("Lidl old price is invalid")
    if value.get("currencyCode", "SEK") != "SEK":
        raise LidlSchemaError("Lidl price currency is not SEK")
    if value.get("variantsHaveDifferentPrices", False) is not False:
        raise LidlSchemaError("Lidl variant prices cannot be assigned to one product")
    taxes = value.get("specialTaxes", [])
    if not isinstance(taxes, list) or taxes:
        raise LidlSchemaError("Lidl deposit or special-tax price needs explicit interpretation")
    for field in ("packaging", "basePrice", "discount"):
        if field not in value:
            continue
        obj = value[field]
        if not isinstance(obj, dict):
            raise LidlSchemaError(f"Lidl {field} must be an object")
        for text_field in ("text", "discountText"):
            if text_field in obj and not isinstance(obj[text_field], str):
                raise LidlSchemaError(f"Lidl {field}.{text_field} must be text")
    discount = value.get("discount", {})
    if set(discount) - {
        "absoluteDiscount",
        "bargainHintEnabled",
        "bargainHintText",
        "deletedPrice",
        "discountHasStar",
        "discountText",
        "fromNormalPriceForLidlPlus",
        "fromRecommendedPrice",
        "hideBargainHint",
        "percentageDiscount",
        "showDiscount",
        "showFrom",
        "showPercentage",
        "showUpTo",
    }:
        raise LidlSchemaError("Lidl discount contains an unreviewed condition")
    for flag in (
        "bargainHintEnabled",
        "discountHasStar",
        "fromNormalPriceForLidlPlus",
        "fromRecommendedPrice",
        "hideBargainHint",
        "showDiscount",
        "showFrom",
        "showPercentage",
        "showUpTo",
    ):
        if flag in discount and not isinstance(discount[flag], bool):
            raise LidlSchemaError("Lidl discount flag must be boolean")
    for numeric in ("absoluteDiscount", "deletedPrice", "percentageDiscount"):
        if numeric not in discount:
            continue
        amount = discount[numeric]
        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
            raise LidlSchemaError("Lidl discount amount must be numeric")
        number = Decimal(str(amount))
        if not number.is_finite() or number < 0:
            raise LidlSchemaError("Lidl discount amount must be finite and non-negative")
        if numeric == "percentageDiscount" and number > 100:
            raise LidlSchemaError("Lidl percentage discount exceeds 100")
    for field, allowed_fields in (
        ("basePrice", {"text", "prefix"}),
        ("packaging", {"text"}),
    ):
        if set(value.get(field, {})) - allowed_fields:
            raise LidlSchemaError("Lidl package or comparison price contains an unreviewed field")
    for flag in ("showFrom", "showUpTo"):
        if discount.get(flag, False) is not False:
            raise LidlSchemaError("Lidl from/up-to price cannot be treated as exact")
    return value


def _verify_region(row: dict[str, Any]) -> None:
    definitions = row.get("regionsV2")
    if definitions is None:
        return  # Historical fixtures have only explicit regionsPrices[1].
    if not isinstance(definitions, dict):
        raise LidlSchemaError("Lidl region definitions must be an object")
    default = [
        value
        for value in definitions.values()
        if isinstance(value, dict) and value.get("isDefault") is True
    ]
    if len(default) != 1 or default[0].get("regionPriceId") != "1":
        raise LidlSchemaError("Lidl default region no longer maps to verified price region 1")


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = html.unescape(value).strip()
    return normalized or None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


class LidlParser:
    """Offline parser for Lidl's public regional offer/search source."""

    parser_version = "lidl-parser-v4"

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
            _verify_region(page.items[0])
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
        if (
            store.external_id != LidlClient.public_offer_context_id
            or store.price_context_type != PriceContextType.REGIONAL
            or store.source_fields.get("price_region_id") != "1"
        ):
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
        _verify_region(row)
        region_id = str(store.source_fields.get("price_region_id") or "")
        regions_prices = _object(row.get("regionsPrices"))
        region = _object(regions_prices.get(region_id))
        if not region:
            raise LidlSchemaError("Lidl product lacks the declared public price region")
        for other_id, other_region in regions_prices.items():
            if other_id == region_id:
                continue
            # Reviewed additive branch; its amount is never attached to the
            # selected context. Unknown branches and conditions fail closed.
            if other_id != "2" or not isinstance(other_region, dict):
                raise LidlSchemaError("Lidl product has an unreviewed additional price region")
            if set(other_region) - {"currentPrice", "futureLidlPlusPrices", "futurePrices"}:
                raise LidlSchemaError("Lidl additional price region has an unreviewed branch")
            other_price = _validated_price(other_region.get("currentPrice"))
            _window(row, other_price)
            for field in ("futureLidlPlusPrices", "futurePrices"):
                if other_region.get(field, []) != []:
                    raise LidlSchemaError("Lidl additional region future price needs review")
        for field in ("currentLidlPlusPrice", "currentPrice"):
            if field in region and not isinstance(region[field], dict):
                raise LidlSchemaError("Lidl current price branch must be an object")
        member_wrapper = _object(region.get("currentLidlPlusPrice"))
        public_price = _object(region.get("currentPrice"))
        member_only = bool(member_wrapper)
        price_model = _validated_price(member_wrapper.get("price") if member_only else public_price)
        if member_wrapper and set(member_wrapper) - {
            "price",
            "lidlPlusText",
            "highlightText",
            "priceLegendName",
            "priceLegendText",
        }:
            raise LidlSchemaError("Lidl member wrapper contains an unreviewed condition")
        amount = _decimal(price_model.get("price"))
        if amount is None:
            raise LidlSchemaError("Lidl current price is missing or invalid")
        old_price = _decimal(price_model.get("oldPrice"))
        discount = _object(price_model.get("discount"))
        discount_text = _text(discount.get("discountText")) or ""
        highlight_text = _text(member_wrapper.get("highlightText")) or ""
        for text in (discount_text, highlight_text):
            if re.search(r"\b(?:köp|betala|välj|ta)\b", text, re.IGNORECASE):
                raise LidlSchemaError("Lidl purchase mechanic needs explicit interpretation")
            if _MULTIBUY.search(text.casefold()) and not re.fullmatch(
                r"(?:kupong\s+)?\d+\s*f[öo]r\s*:?\s*", text, re.IGNORECASE
            ):
                raise LidlSchemaError("Lidl multibuy label has unsupported additional conditions")
        multibuy_counts = {
            int(match.group("count"))
            for value in (discount_text, highlight_text)
            for match in _MULTIBUY.finditer(value.casefold())
        }
        if len(multibuy_counts) > 1 or any(count < 2 for count in multibuy_counts):
            raise LidlSchemaError("Lidl multibuy count is contradictory or invalid")
        multibuy_count = next(iter(multibuy_counts), None)
        multi = multibuy_count is not None
        package_text = _text(_object(price_model.get("packaging")).get("text"))
        base_price_text = _text(_object(price_model.get("basePrice")).get("text"))
        comparison_price, comparison_unit = _comparison(base_price_text)
        package_quantity, package_unit, package_count = _package(package_text)

        sale_unit = "st"
        basket_type = "ST"
        average_weight_kg: Decimal | None = None
        variable = _APPROX_WEIGHT.fullmatch(package_text or base_price_text or "")
        raw_unit_text = " ".join(filter(None, (package_text, base_price_text))).casefold()
        if variable is not None:
            sale_unit = _unit(variable.group("sale_unit"))
            average = _decimal(variable.group("quantity"))
            average_unit = _unit(variable.group("unit"))
            if average is not None:
                average_weight_kg = average / 1000 if average_unit in {"g", "ml"} else average
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

        start_at, end_at = _window(row, price_model)
        valid_from = start_at.astimezone(_SWEDEN).date() if start_at else None
        valid_to = end_at.astimezone(_SWEDEN).date() if end_at else None
        currently_valid = _at_observation(start_at, end_at, fetched_at)
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
        disclaimers = tuple(
            text
            for item in row.get("disclaimers", [])
            if isinstance(item, dict) and item.get("type") == "TEXT"
            if (text := _text(item.get("value")))
        )
        conditions = " ".join(
            filter(
                None,
                (
                    discount_text,
                    highlight_text,
                    lidl_plus_text,
                    _text(member_wrapper.get("priceLegendText")),
                    _text(price_model.get("priceLegendText")),
                    *disclaimers,
                ),
            )
        )
        if re.search(
            r"\bpant\b",
            " ".join((conditions, package_text or "", base_price_text or "")),
            re.IGNORECASE,
        ):
            raise LidlSchemaError("Lidl deposit text needs explicit price interpretation")
        max_mentions = list(re.finditer(r"\bmax(?:\b|\.)", conditions, re.IGNORECASE))
        limit_matches = list(
            re.finditer(
                r"\bmax\.?\s*(\d+)\s*(?:förp(?:ackningar|ackning)?\.?|st(?:yck)?)\b",
                conditions,
                re.IGNORECASE,
            )
        )
        if len(max_mentions) != len(limit_matches):
            raise LidlSchemaError("Lidl purchase limit is not an explicit package-count limit")
        limits = {int(match.group(1)) for match in limit_matches}
        if len(limits) > 1 or 0 in limits:
            raise LidlSchemaError("Lidl purchase limits are contradictory or invalid")
        max_quantity = next(iter(limits), None)
        if re.search(r"\bmax(?:\b|\.)", conditions, re.IGNORECASE) and max_quantity is None:
            raise LidlSchemaError("Lidl purchase limit cannot be interpreted")
        activation_required = bool(re.search(r"aktiver|kupong|coupon", conditions, re.IGNORECASE))
        offer_scope = classify_shared_offer_scope(
            chain=Chain.LIDL,
            member_only=member_only
            or bool(re.search(r"personlig|personal|just for you", conditions, re.IGNORECASE)),
            description=conditions,
            source_payload={"discount_text": discount_text or None},
            source_fields={"public_lidl_plus": member_only},
        )
        shared_offer_eligible = offer_scope in {
            SharedOfferScope.PUBLIC,
            SharedOfferScope.GENERIC_MEMBER,
        }
        if activation_required or start_at is None or end_at is None:
            shared_offer_eligible = False
        offer = SourceOffer(
            type=promotion_type,
            valid_from=valid_from,
            valid_to=valid_to,
            price=amount,
            quantity=multibuy_count,
            member_only=member_only,
            max_quantity=max_quantity,
            description=conditions or "Publicerad Lidl-produktrad; prisstatus ej typad",
            source_payload={
                "price_region_id": region_id,
                "discount_text": discount_text or None,
                "highlight_text": highlight_text or None,
                "percentage_discount": percentage,
                "deleted_price": str(old_price) if old_price is not None else None,
                "package_count": package_count,
                "source_base_price_text": base_price_text,
                "member_offer_scope": offer_scope.value,
                "shared_price_universe_eligible": shared_offer_eligible,
                "activation_required": activation_required,
                "conditions_text": conditions or None,
                "price_window_start_at": start_at.isoformat() if start_at else None,
                "price_window_end_at": end_at.isoformat() if end_at else None,
                "regular_price_current_verified": False,
            },
        )
        # Deleted/reference prices never prove a current ordinary price. A
        # separate public currentPrice is usable only with its own checked
        # package, conditions and intersected price/store date window.
        current_public_amount = None
        if public_price:
            public_price = _validated_price(public_price)
            public_start, public_end = _window(row, public_price)
            public_discount = _text(_object(public_price.get("discount")).get("discountText"))
            if (
                member_only
                and _text(_object(public_price.get("packaging")).get("text")) != package_text
            ):
                raise LidlSchemaError("Lidl public/member package scopes disagree")
            if _at_observation(public_start, public_end, fetched_at) and not _MULTIBUY.search(
                (public_discount or "").casefold()
            ):
                current_public_amount = _decimal(public_price.get("price"))
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
            sale_price=current_public_amount if shared_offer_eligible else None,
            regular_price=None,
            member_price=(
                amount
                if member_only and not multi and currently_valid and shared_offer_eligible
                else None
            ),
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
                "analytics_category": _object(row.get("keyfacts")).get("analyticsCategory"),
                "price_scope": "unselected_public_default_region",
                "price_region_id": region_id,
                "store_price_verified": False,
                "availability_scope": "campaign_window_not_stock",
                "stock_badges": badges if isinstance(badges, list) else [],
                "online_available": _object(row.get("stockAvailability")).get("onlineAvailable"),
                "public_lidl_plus": (
                    member_only and offer_scope is SharedOfferScope.GENERIC_MEMBER
                ),
                "personalized_coupon": offer_scope is SharedOfferScope.USER_SPECIFIC,
                "coupon_scope_unknown": offer_scope is SharedOfferScope.UNKNOWN,
                "member_offer_scope": offer_scope.value,
                "shared_price_universe_eligible": shared_offer_eligible,
                "package_count": package_count,
                "conditions_text": conditions or None,
                "activation_required": activation_required,
                "purchase_limit_verified": max_quantity is not None,
                "geographic_restrictions": [*disclaimers, *([price_model["priceLegendText"]]
                    if price_model.get("priceLegendText") else [])],
                "price_legend_name": price_model.get("priceLegendName"),
                "price_valid_at_observation": currently_valid,
                "price_window_start_at": start_at.isoformat() if start_at else None,
                "price_window_end_at": end_at.isoformat() if end_at else None,
                "ordinary_price_verified": False,
                "deleted_price": str(old_price) if old_price is not None else None,
                "deposit_amount": None,
                "deposit_status": "not_declared_in_source",
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
