from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from grocery_data.app.connectors.citygross.models import (
    CityGrossSchemaError,
    validated_catalog_page,
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

_PACKAGE = re.compile(
    r"^(?P<approx>CA\s*)?(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>KG|G|ML|CL|DL|L|ST|P)$",
    re.IGNORECASE,
)
_MULTIPACK = re.compile(
    r"^(?P<count>\d+)\s*[X×]\s*(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>KG|G|ML|CL|DL|L|ST|P)$",
    re.IGNORECASE,
)
_MULTIPACK_REVERSED = re.compile(
    r"^(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>KG|G|ML|CL|DL|L|ST|P)"
    r"\s*[X×]\s*(?P<count>\d+)$",
    re.IGNORECASE,
)
_GROSS_DRAINED = re.compile(
    r"^(?P<gross>\d+(?:[.,]\d+)?)/(?P<drained>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>KG|G|ML)$",
    re.IGNORECASE,
)
_MIXED_KG_GROSS_DRAINED = re.compile(
    r"^(?P<gross>\d+[.,]\d+)/(?P<drained>\d+)\s*G$",
    re.IGNORECASE,
)
_PRICE_UNITS = {"PCE": "st", "KGM": "kg", "LTR": "l"}
_COMPARISON_UNITS = {"PCE": "st", "KGM": "kg", "LTR": "l"}
_SELLING_UNITS = {1: "ST", 2: "VIKT"}
_VERIFIED_CATALOG_CONTEXTS = {
    "3203": "59",  # Malmö Stora Bernstorp
    "3211": "169",  # Malmö Hyllie
    "3229": "11",  # Staffanstorp; never relabel this context as Lund
}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() and result > 0 else None


def _coordinate(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _normalise_quantity(amount: Decimal, unit: str) -> tuple[Decimal, str]:
    unit = unit.upper()
    if unit == "KG":
        return amount * 1000, "g"
    if unit == "L":
        return amount * 1000, "ml"
    if unit == "CL":
        return amount * 10, "ml"
    if unit == "DL":
        return amount * 100, "ml"
    return amount, {"G": "g", "ML": "ml", "ST": "st", "P": "st"}[unit]


def parse_package_text(
    value: object,
) -> tuple[Decimal | None, str | None, Decimal | None, bool, bool]:
    """Return package, unit, drained, approximate and conflict flags.

    Slash notation such as the observed ``415/230G`` is retained but not
    interpreted: City Gross simultaneously supplied incompatible net/gross
    numeric fields, and the labels do not explicitly name gross/drained roles.
    """

    text = str(value or "").strip().upper().replace(" ", "")
    if not text:
        return None, None, None, False, False
    if text == "ST":
        # Unlike a price expressed per piece, the descriptive package field
        # explicitly states that the purchased unit is one piece.
        return Decimal(1), "st", None, False, False
    if _GROSS_DRAINED.fullmatch(text):
        return None, None, None, False, True
    multipack = _MULTIPACK.fullmatch(text)
    reversed_multipack = _MULTIPACK_REVERSED.fullmatch(text)
    if reversed_multipack:
        count = _decimal(reversed_multipack.group("count"))
        amount = _decimal(reversed_multipack.group("amount"))
        if count is None or amount is None:
            return None, None, None, False, False
        quantity, unit = _normalise_quantity(
            count * amount,
            reversed_multipack.group("unit"),
        )
        return quantity, unit, None, False, False
    if multipack:
        count = _decimal(multipack.group("count"))
        amount = _decimal(multipack.group("amount"))
        if count is None or amount is None:
            return None, None, None, False, False
        quantity, unit = _normalise_quantity(count * amount, multipack.group("unit"))
        return quantity, unit, None, False, False
    package = _PACKAGE.fullmatch(text)
    if package is None:
        return None, None, None, False, False
    amount = _decimal(package.group("amount"))
    if amount is None:
        return None, None, None, bool(package.group("approx")), False
    quantity, unit = _normalise_quantity(amount, package.group("unit"))
    return quantity, unit, None, bool(package.group("approx")), False


def _place_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _in_area(name: str, source_city: str, requested_city: str) -> bool:
    requested = _place_key(requested_city)
    if _place_key(source_city) == requested:
        return True
    return bool(re.search(rf"(?<!\w){re.escape(requested)}(?!\w)", _place_key(name)))


def _date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _price_object(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _valid_gtin(value: object) -> str | None:
    digits = str(value or "").strip()
    if len(digits) not in {8, 12, 13, 14} or not digits.isdigit():
        return None
    payload = [int(character) for character in digits]
    check = payload.pop()
    total = sum(
        digit * (3 if (len(payload) - position) % 2 == 1 else 1)
        for position, digit in enumerate(payload)
    )
    return digits if (10 - total % 10) % 10 == check else None


def _category_path(row: dict[str, Any]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for key in ("superCategory", "category", "bfCategory"):
        name = str(row.get(key) or "").strip()
        marker = name.casefold()
        if name and marker not in seen:
            result.append(name)
            seen.add(marker)
    return tuple(result)


class CityGrossParser:
    parser_version = "citygross-parser-v2"

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        page_data: tuple[object, str] | None = None
        site_data: object | None = None
        for document, reference in raw.with_references(references):
            if document.http_status != 200:
                continue
            if document.kind == "stores":
                page_data = (document.json_payload(), reference)
            elif document.kind == "store_number_map":
                site_data = document.json_payload()
        if page_data is None or site_data is None:
            raise CityGrossSchemaError("City Gross store discovery requires both public sources")
        rows, reference = page_data
        if not isinstance(rows, list):
            raise CityGrossSchemaError("City Gross PageData/stores must be a list")
        if not isinstance(site_data, dict) or not isinstance(site_data.get("sites"), list):
            raise CityGrossSchemaError("City Gross site mapping must contain sites")
        sites: dict[str, dict[str, Any]] = {}
        for value in site_data["sites"]:
            if isinstance(value, dict) and value.get("id") is not None:
                sites[str(value["id"])] = value

        stores: dict[str, SourceStore] = {}
        for entry in rows:
            if not isinstance(entry, dict) or not isinstance(entry.get("data"), dict):
                continue
            row = entry["data"]
            name = str(row.get("storeName") or row.get("name") or "").strip()
            address = row.get("address") if isinstance(row.get("address"), dict) else {}
            source_city = str(address.get("city") or "").strip()
            if not name or not _in_area(name, source_city, area.city):
                continue
            site_id = str(row.get("siteId") or "").strip()
            site = sites.get(site_id)
            if site is None:
                continue
            store_number = str(site.get("storeNumber") or "").strip()
            if not store_number:
                continue
            location = (
                row.get("storeLocation") if isinstance(row.get("storeLocation"), dict) else {}
            )
            coordinate_text = str(location.get("coordinates") or "")
            parts = [part.strip() for part in coordinate_text.split(",", 1)]
            latitude = _coordinate(parts[0]) if len(parts) == 2 else None
            longitude = _coordinate(parts[1]) if len(parts) == 2 else None
            context_verified = _VERIFIED_CATALOG_CONTEXTS.get(store_number) == site_id
            stores[store_number] = SourceStore(
                chain=Chain.CITY_GROSS,
                external_id=store_number,
                name=name,
                address=str(address.get("streetAddress") or "").strip() or None,
                postal_code="".join(str(address.get("zipCode") or "").split()) or None,
                city=source_city or None,
                latitude=latitude,
                longitude=longitude,
                online_shopping=True if context_verified else None,
                coverage=CoverageLevel.PARTIAL_CATALOG,
                price_context_type=(PriceContextType.ONLINE_STORE if context_verified else None),
                physical_store_external_id=site_id,
                raw_reference=f"{reference}#siteId={site_id}",
                source_fields={
                    "cms_id": row.get("id"),
                    "site_id": site_id,
                    "store_number": store_number,
                    "provider": site.get("provider"),
                    "store_page_url": row.get("url"),
                    "price_context_type": "online_store" if context_verified else None,
                    "physical_store_external_id": site_id,
                    # Loop54 proves a store-scoped online catalog/price context,
                    # but its payload does not establish a fulfillment mode.
                    "fulfillment_type": None,
                    "price_context_verified": context_verified,
                    "catalog_context_evidence": (
                        "live_loop54_store_match_2026-08-22" if context_verified else None
                    ),
                },
            )
        return sorted(stores.values(), key=lambda item: (item.name.casefold(), item.external_id))

    @staticmethod
    def _failure(reference: str, code: ParserErrorCode, exc: Exception) -> ParseFailure:
        return ParseFailure(
            raw_record_reference=reference,
            error_code=code,
            error_message=str(exc)[:300],
            parser_version=CityGrossParser.parser_version,
        )

    def _promotions(
        self,
        prices: dict[str, Any],
        *,
        reference: str,
        failures: list[ParseFailure],
    ) -> tuple[SourceOffer, ...]:
        raw_promotions = prices.get("promotions")
        candidates = list(raw_promotions) if isinstance(raw_promotions, list) else []
        active = prices.get("activePromotion")
        if isinstance(active, dict) and not any(
            isinstance(candidate, dict) and candidate == active for candidate in candidates
        ):
            candidates.append(active)
        offers: list[SourceOffer] = []
        seen: set[str] = set()
        for position, raw_promotion in enumerate(candidates):
            promotion_reference = f"{reference}#promotions[{position}]"
            if not isinstance(raw_promotion, dict):
                failures.append(
                    self._failure(
                        promotion_reference,
                        ParserErrorCode.INVALID_PROMOTION,
                        CityGrossSchemaError("City Gross promotion must be an object"),
                    )
                )
                continue
            promotion_id = str(raw_promotion.get("id") or "").strip()
            if promotion_id and promotion_id in seen:
                continue
            if promotion_id:
                seen.add(promotion_id)
            quantity_raw = raw_promotion.get("minQuantity")
            quantity = (
                quantity_raw
                if isinstance(quantity_raw, int)
                and not isinstance(quantity_raw, bool)
                and quantity_raw > 0
                else None
            )
            member_only = raw_promotion.get("membersOnly") is True
            price_details = _price_object(raw_promotion.get("priceDetails"))
            unit_price = _decimal(price_details.get("price"))
            raw_type = str(raw_promotion.get("type") or "").strip()
            effect_type = str(raw_promotion.get("effectType") or "").strip()
            if (
                raw_type == "1"
                and effect_type == "ItemsTotal"
                and quantity is not None
                and quantity > 1
            ):
                promotion_type = PromotionType.MULTIBUY
                price = _decimal(raw_promotion.get("value"))
            elif raw_type == "5" and effect_type == "PriceChangeAll":
                promotion_type = (
                    PromotionType.MEMBER_PRICE if member_only else PromotionType.SALE_PRICE
                )
                price = unit_price
            else:
                promotion_type = PromotionType.OTHER
                price = unit_price or _decimal(raw_promotion.get("value"))
            if price is None:
                failures.append(
                    self._failure(
                        promotion_reference,
                        ParserErrorCode.INVALID_PROMOTION,
                        CityGrossSchemaError("City Gross promotion lacks an explicit final price"),
                    )
                )
                continue
            max_applied_raw = raw_promotion.get("maxAppliedPerReceipt")
            max_applied = (
                max_applied_raw
                if isinstance(max_applied_raw, int)
                and not isinstance(max_applied_raw, bool)
                and max_applied_raw > 0
                else None
            )
            try:
                offers.append(
                    SourceOffer(
                        external_id=promotion_id or None,
                        type=promotion_type,
                        valid_from=_date(raw_promotion.get("from")),
                        valid_to=_date(raw_promotion.get("to")),
                        price=price,
                        quantity=quantity,
                        member_only=member_only,
                        # In the shared basket contract this is the maximum
                        # discounted package count for singles and maximum
                        # discounted group count for MULTIBUY offers.
                        max_quantity=max_applied,
                        description=str(
                            raw_promotion.get("name")
                            or raw_promotion.get("effectType")
                            or "City Gross promotion"
                        ),
                        source_payload={
                            "type": raw_promotion.get("type"),
                            "campaignTypeId": raw_promotion.get("campaignTypeId"),
                            "effectType": raw_promotion.get("effectType"),
                            "value": raw_promotion.get("value"),
                            # Keep raw source scalars here. Decimal is used in
                            # typed fields but source_payload must remain JSON-safe.
                            "unit_price": price_details.get("price"),
                            "maxAppliedPerReceipt": raw_promotion.get("maxAppliedPerReceipt"),
                            "price_unit": price_details.get("unit"),
                            "comparison_price": price_details.get("comparativePrice"),
                            "comparison_unit": price_details.get("comparativePriceUnit"),
                            "active": isinstance(active, dict) and raw_promotion == active,
                        },
                    )
                )
            except ValidationError as exc:
                failures.append(
                    self._failure(
                        promotion_reference,
                        ParserErrorCode.INVALID_PROMOTION,
                        exc,
                    )
                )
        return tuple(offers)

    def _parse_product(
        self,
        row: dict[str, Any],
        *,
        store: SourceStore,
        reference: str,
        fetched_at: datetime,
        failures: list[ParseFailure],
    ) -> SourceProduct:
        external_id = str(row.get("id") or "").strip()
        if not external_id:
            raise ValueError(ParserErrorCode.MISSING_PRODUCT_ID)
        name = str(row.get("name") or "").strip()
        if not name:
            raise ValueError(ParserErrorCode.MISSING_NAME)
        store_details = row.get("productStoreDetails")
        if not isinstance(store_details, dict):
            raise CityGrossSchemaError("productStoreDetails is missing")
        if str(store_details.get("id") or "") != store.external_id:
            raise CityGrossSchemaError("product price context does not match requested store")
        prices = store_details.get("prices")
        if not isinstance(prices, dict):
            raise CityGrossSchemaError("City Gross prices object is missing")

        current = _price_object(prices.get("currentPrice"))
        ordinary = _price_object(prices.get("ordinaryPrice"))
        member = _price_object(prices.get("memberPrice"))
        sale_price = _decimal(current.get("price"))
        regular_price = _decimal(ordinary.get("price"))
        member_price = _decimal(member.get("price"))
        if store_details.get("p_has_price") is True and sale_price is None:
            raise ValueError(ParserErrorCode.INVALID_PRICE)
        raw_sale_unit = str(current.get("unit") or "").strip().upper()
        sale_unit = _PRICE_UNITS.get(raw_sale_unit) if sale_price is not None else None
        if sale_price is not None and sale_unit is None:
            raise ValueError(ParserErrorCode.UNKNOWN_PRICE_UNIT)
        comparison_price = _decimal(current.get("comparativePrice"))
        raw_comparison_unit = str(current.get("comparativePriceUnit") or "").strip().upper()
        comparison_unit = (
            _COMPARISON_UNITS.get(raw_comparison_unit) or raw_comparison_unit.casefold() or None
            if comparison_price is not None
            else None
        )

        package_text = str(row.get("descriptiveSize") or "").strip() or None
        (
            package_quantity,
            package_unit,
            drained_quantity,
            package_approximate,
            package_conflict,
        ) = parse_package_text(package_text)
        average_weight_kg = (
            package_quantity / 1000
            if package_approximate and package_quantity is not None and package_unit == "g"
            else None
        )
        selling_unit_raw = row.get("sellingUnitOfMeasure")
        basket_type = (
            _SELLING_UNITS.get(selling_unit_raw)
            if isinstance(selling_unit_raw, int) and not isinstance(selling_unit_raw, bool)
            else None
        )
        stock_status = store_details.get("stockStatus")
        raw_gtin = str(row.get("gtin") or "").strip() or None
        offers = self._promotions(prices, reference=reference, failures=failures)
        public_single = next(
            (
                offer
                for offer in offers
                if offer.type == PromotionType.SALE_PRICE
                and offer.member_only is False
                and (offer.quantity is None or offer.quantity == 1)
                and offer.source_payload.get("active") is True
            ),
            None,
        )
        member_single = next(
            (
                offer
                for offer in offers
                if offer.type == PromotionType.MEMBER_PRICE
                and (offer.quantity is None or offer.quantity == 1)
                and offer.source_payload.get("active") is True
            ),
            None,
        )
        if public_single is not None:
            sale_price = public_single.price
            offer_comparison = _decimal(public_single.source_payload.get("comparison_price"))
            offer_comparison_unit = str(
                public_single.source_payload.get("comparison_unit") or ""
            ).upper()
            if offer_comparison is not None and offer_comparison_unit:
                comparison_price = offer_comparison
                comparison_unit = (
                    _COMPARISON_UNITS.get(offer_comparison_unit) or offer_comparison_unit.casefold()
                )
        if member_price is None and member_single is not None:
            member_price = member_single.price

        # The storefront has inconsistent generic netContent/grossWeight values.
        # Slash notation is accepted as gross/drained only when the current
        # package price and comparison rate independently prove the drained
        # quantity (for example 12.25 / 0.230 kg == 53.26 kr/kg).
        slash = _GROSS_DRAINED.fullmatch(str(package_text or "").strip().upper().replace(" ", ""))
        mixed_kg_slash = _MIXED_KG_GROSS_DRAINED.fullmatch(
            str(package_text or "").strip().upper().replace(" ", "")
        )
        package_slash_validated = False
        if (
            slash is not None
            and sale_price is not None
            and comparison_price is not None
            and comparison_unit in {"kg", "l"}
        ):
            gross_raw = _decimal(slash.group("gross"))
            drained_raw = _decimal(slash.group("drained"))
            if gross_raw is not None and drained_raw is not None:
                # The public source also emits labels such as ``1,5/800G``:
                # a decimal gross quantity in kg followed by an integer
                # drained quantity in grams.  Accept that mixed scale only for
                # the exact observed decimal/integer form and only when the
                # independent package-price/comparison-rate equation proves
                # the drained quantity below.
                if mixed_kg_slash is not None:
                    gross_quantity = gross_raw * 1000
                    slash_unit = "g"
                else:
                    gross_quantity, slash_unit = _normalise_quantity(gross_raw, slash.group("unit"))
                drained_candidate, drained_unit = _normalise_quantity(
                    drained_raw, slash.group("unit")
                )
                divisor = Decimal(1000) if drained_unit in {"g", "ml"} else Decimal(1)
                calculated = comparison_price * drained_candidate / divisor
                if (
                    slash_unit == drained_unit
                    and gross_quantity >= drained_candidate
                    and abs(calculated - sale_price) <= Decimal("0.02")
                ):
                    package_quantity = gross_quantity
                    package_unit = slash_unit
                    drained_quantity = drained_candidate
                    package_conflict = False
                    package_slash_validated = True
        return SourceProduct(
            chain=Chain.CITY_GROSS,
            store_external_id=store.external_id,
            external_product_id=external_id,
            gtin=_valid_gtin(raw_gtin),
            name=name,
            brand=str(row.get("brand") or "").strip() or None,
            category_path=_category_path(row),
            sale_price=sale_price,
            regular_price=regular_price,
            member_price=member_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            package_text=package_text,
            package_quantity=package_quantity,
            package_unit=package_unit,
            drained_quantity=drained_quantity,
            sale_unit=sale_unit,
            offers=offers,
            # stockStatus meaning has not been proven against orderability.
            availability=None,
            average_weight_kg=average_weight_kg,
            basket_type=basket_type,
            raw_reference=reference,
            fetched_at=fetched_at,
            source_fields={
                "sellingUnitOfMeasure": selling_unit_raw,
                "sellable": row.get("sellable"),
                "stockStatus": stock_status,
                "raw_gtin": raw_gtin,
                "raw_gtin_valid": _valid_gtin(raw_gtin) is not None,
                "available_from": store_details.get("p_availablefrom"),
                "available_to": store_details.get("p_availableto"),
                "netContent": row.get("netContent"),
                "grossWeight": row.get("grossWeight"),
                "package_approximate": package_approximate,
                "package_conflict": package_conflict,
                "package_slash_validated_by_comparison_price": package_slash_validated,
                "package_slash_mixed_kg_g": mixed_kg_slash is not None,
                "raw_price_unit": raw_sale_unit or None,
                "raw_comparison_unit": raw_comparison_unit or None,
                "price_context_type": "online_store",
                "price_context_verified": True,
            },
        )

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        products: dict[str, SourceProduct] = {}
        failures: list[ParseFailure] = []
        for document, reference in raw.with_references(references):
            if document.kind != "catalog_page":
                continue
            if document.http_status != 200:
                failures.append(
                    self._failure(
                        reference,
                        ParserErrorCode.SCHEMA_CHANGED,
                        ValueError(f"unexpected HTTP status {document.http_status}"),
                    )
                )
                continue
            try:
                payload = document.json_payload()
                skip = int(document.query["skip"])
                take = int(document.query["take"])
                page = validated_catalog_page(
                    payload,
                    requested_skip=skip,
                    requested_take=take,
                    expected_store_id=store.external_id,
                )
            except (KeyError, TypeError, ValueError, CityGrossSchemaError) as exc:
                failures.append(self._failure(reference, ParserErrorCode.SCHEMA_CHANGED, exc))
                continue
            for position, row in enumerate(page.items):
                row_reference = f"{reference}#items[{position}]"
                try:
                    product = self._parse_product(
                        row,
                        store=store,
                        reference=row_reference,
                        fetched_at=document.fetched_at,
                        failures=failures,
                    )
                except (ValidationError, ValueError, CityGrossSchemaError) as exc:
                    marker = str(exc)
                    codes = {item.value for item in ParserErrorCode}
                    code = ParserErrorCode(marker) if marker in codes else ParserErrorCode.UNKNOWN
                    failures.append(self._failure(row_reference, code, exc))
                    continue
                product_id = product.external_product_id or ""
                if product_id in products:
                    failures.append(
                        self._failure(
                            row_reference,
                            ParserErrorCode.SCHEMA_CHANGED,
                            CityGrossSchemaError("duplicate product identity during replay"),
                        )
                    )
                    continue
                products[product_id] = product
        return ProductParseResult(products=list(products.values()), failures=failures)
