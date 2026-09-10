from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urljoin

from pydantic import ValidationError

from grocery_data.app.connectors.ica.models import IcaSchemaError, initial_data_from_html
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ParseFailure,
    ParserErrorCode,
    ProductParseResult,
    PromotionType,
    RawBatch,
    SourceOffer,
    SourceProduct,
    SourceStore,
)

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_EXACT_AMOUNT = re.compile(
    r"^\s*(?:ca\s*)?(?P<amount>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|cl|dl|l|st)\s*$",
    re.IGNORECASE,
)
_PACK = re.compile(r"^\s*(?P<count>\d+)\s*[- ]?pack\s*$", re.IGNORECASE)
_EXACT_COMPARISON = re.compile(
    r"^\s*(?P<price>\d+(?:[.,:]\d{1,2})?)\s*(?:kr|:-)?\s*/\s*"
    r"(?P<unit>kg|l|liter|st)\s*$",
    re.IGNORECASE,
)


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace("\u00a0", "").replace(":", ".").replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    try:
        result = Decimal(text)
    except InvalidOperation:
        return None
    return result if result.is_finite() and result > 0 else None


def _price(value: object) -> Decimal | None:
    if isinstance(value, dict):
        major = _decimal(value.get("value1") or value.get("integer") or value.get("major"))
        minor = _decimal(value.get("value2") or value.get("decimal") or value.get("minor"))
        if major is not None:
            return major + (minor or Decimal(0)) / 100
        return None
    return _decimal(value)


def _normalise_amount(amount: Decimal, unit: str) -> tuple[Decimal, str]:
    unit = unit.casefold()
    if unit == "kg":
        return amount * 1000, "g"
    if unit in {"l", "liter"}:
        return amount * 1000, "ml"
    if unit == "cl":
        return amount * 10, "ml"
    if unit == "dl":
        return amount * 100, "ml"
    return amount, unit


def parse_package(value: object) -> tuple[Decimal | None, str | None]:
    text = str(value or "").strip()
    # A range or slash-separated gross/drained shorthand is not one exact package fact.
    if "-" in text and not _PACK.fullmatch(text) or "/" in text:
        return None, None
    match = _EXACT_AMOUNT.fullmatch(text)
    if match:
        amount = _decimal(match.group("amount"))
        return _normalise_amount(amount, match.group("unit")) if amount else (None, None)
    pack = _PACK.fullmatch(text)
    count = _decimal(pack.group("count")) if pack else None
    return (count, "st") if count else (None, None)


def parse_comparison(value: object) -> tuple[Decimal | None, str | None]:
    text = str(value or "").strip()
    if "-" in text:
        return None, None
    match = _EXACT_COMPARISON.fullmatch(text)
    if not match:
        return None, None
    price = _decimal(match.group("price"))
    unit = match.group("unit").casefold().replace("liter", "l")
    return (price, unit) if price else (None, None)


def _exact_gtin(rows: object) -> str | None:
    if not isinstance(rows, list):
        return None
    values = {
        str(row.get("id") or "").strip()
        for row in rows
        if isinstance(row, dict) and re.fullmatch(r"\d{8}|\d{12,14}", str(row.get("id") or ""))
    }
    return next(iter(values)) if len(values) == 1 else None


def _first_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), {})
    return {}


def _location_key(value: object) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char)).strip()


def _promotion(row: dict[str, Any]) -> SourceOffer:
    details = _first_dict(row.get("details"))
    mechanics = _first_dict(row.get("parsedMechanics"))
    kind = str(mechanics.get("benefitType") or mechanics.get("type") or "").upper()
    quantity_raw = mechanics.get("quantity")
    quantity_decimal = _decimal(quantity_raw)
    quantity = (
        int(quantity_decimal)
        if quantity_decimal and quantity_decimal == int(quantity_decimal)
        else None
    )
    first = mechanics.get("value1")
    second = mechanics.get("value2")
    third = mechanics.get("value3")
    first_price = _decimal(first)
    second_price = _decimal(second)
    if first_price is not None:
        amount = first_price + (second_price or Decimal(0)) / 100
    else:
        # ICA's current SSR shape uses value1 for display text such as
        # "3 för" and value2 for the total conditional price.
        third_price = _decimal(third)
        amount = (
            second_price + (third_price or Decimal(0)) / 100 if second_price is not None else None
        )
    if kind == "FIXED" and quantity and quantity >= 2:
        promotion_type = PromotionType.MULTIBUY
    elif kind == "FIXED":
        promotion_type = PromotionType.SALE_PRICE
    elif kind == "PERCOFF":
        promotion_type = PromotionType.PERCENT_DISCOUNT
        amount = None
    else:
        promotion_type = PromotionType.OTHER
        amount = None
    traits = row.get("traits") if isinstance(row.get("traits"), list) else []
    trait_text = " ".join(
        str(item.get("name") if isinstance(item, dict) else item) for item in traits
    ).casefold()
    valid_to = None
    try:
        if row.get("validTo"):
            valid_to = date.fromisoformat(str(row["validTo"])[:10])
    except ValueError:
        valid_to = None
    return SourceOffer(
        external_id=str(row.get("id") or "").strip() or None,
        type=PromotionType.MEMBER_PRICE
        if "stammis" in trait_text and promotion_type == PromotionType.SALE_PRICE
        else promotion_type,
        valid_to=valid_to,
        price=amount,
        quantity=quantity if promotion_type == PromotionType.MULTIBUY else None,
        member_only="stammis" in trait_text,
        description=str(details.get("mechanicInfo") or row.get("restriction") or "").strip()
        or None,
        source_payload={"benefit_type": kind, "unit_sign": mechanics.get("unitSign")},
    )


class IcaParser:
    parser_version = "ica-parser-v3"

    def weekly_offer_rows(self, data: dict[str, Any]) -> list[object]:
        """Return the connector-local offer collection or fail on schema drift."""

        offers_root = _first_dict(data.get("offers"))
        rows = offers_root.get("weeklyOffers")
        if not isinstance(rows, list):
            raise IcaSchemaError("ICA weeklyOffers must be a list")
        return rows

    def parse_stores(
        self, raw: RawBatch, references: list[str], area: GeographicArea
    ) -> list[SourceStore]:
        stores: dict[str, SourceStore] = {}
        for document, reference in raw.with_references(references):
            if document.kind != "stores_page" or document.http_status != 200:
                continue
            data = initial_data_from_html(document.payload)
            result = _first_dict(data.get("resultStore"))
            cards = result.get("storeCards")
            if not isinstance(cards, list):
                raise IcaSchemaError("ICA storeCards must be a list")
            declared = (
                result.get("totalNrOfStores")
                or result.get("totalNumberOfStores")
                or result.get("total")
            )
            if isinstance(declared, int) and declared != len(cards):
                raise IcaSchemaError("ICA filtered store page is incomplete")
            for card in cards:
                if not isinstance(card, dict):
                    continue
                external_id = str(card.get("accountNumber") or "").strip()
                name = str(card.get("storeName") or card.get("name") or "").strip()
                offers_link = _first_dict(card.get("highlightUrls")).get("offers")
                offers_value = (
                    offers_link.get("url") if isinstance(offers_link, dict) else offers_link
                )
                offers_url = urljoin(
                    "https://www.ica.se",
                    str(offers_value or "").strip(),
                )
                address = _first_dict(card.get("address"))
                municipality = str(address.get("municipality") or address.get("city") or "")
                if _location_key(municipality) != _location_key(area.city):
                    continue
                coordinates = _first_dict(address.get("coordinates") or card.get("coordinates"))
                if not external_id or not name or not offers_url:
                    continue
                stores[external_id] = SourceStore(
                    chain=Chain.ICA,
                    external_id=external_id,
                    name=name,
                    address=str(address.get("street") or address.get("address") or "").strip()
                    or None,
                    postal_code=str(address.get("postalCode") or "").replace(" ", "") or None,
                    # The collector scope is the municipality. Preserve the
                    # source locality separately so `/stores?city=Lund`
                    # includes online stores in Lund municipality such as
                    # Södra Sandby without pretending that the street address
                    # itself says Lund.
                    city=area.city.strip(),
                    latitude=_decimal(
                        coordinates.get("latitude")
                        or coordinates.get("lat")
                        or coordinates.get("coordinateX")
                    ),
                    longitude=_decimal(
                        coordinates.get("longitude")
                        or coordinates.get("lng")
                        or coordinates.get("coordinateY")
                    ),
                    online_shopping=True,
                    coverage=CoverageLevel.OFFERS_ONLY,
                    raw_reference=reference,
                    source_fields={
                        "store_id": card.get("storeId"),
                        "offers_url": offers_url,
                        "online_url": card.get("onlineUrl"),
                        "profile": card.get("profile"),
                        "source_locality": address.get("city"),
                        "municipality": address.get("municipality"),
                    },
                )
        return sorted(stores.values(), key=lambda store: store.name.casefold())

    def parse_physical_stores(
        self, raw: RawBatch, references: list[str], area: GeographicArea
    ) -> list[SourceStore]:
        """Parse the full locator while retaining the source locality exactly.

        ICA's ``/lund/`` page is municipality-scoped.  A strict city audit must
        exclude Södra Sandby, Genarp and Veberöd instead of relabelling those
        address localities as Lund.  ``onlineUrl`` remains a capability signal;
        it is not fabricated for the physical-only cards.
        """

        stores: dict[str, SourceStore] = {}
        requested_city = _location_key(area.city)
        for document, reference in raw.with_references(references):
            if document.kind != "stores_page" or document.http_status != 200:
                continue
            data = initial_data_from_html(document.payload)
            result = _first_dict(data.get("resultStore"))
            cards = result.get("storeCards")
            if not isinstance(cards, list):
                raise IcaSchemaError("ICA physical locator storeCards must be a list")
            declared = (
                result.get("totalNrOfStores")
                or result.get("totalNumberOfStores")
                or result.get("total")
            )
            if isinstance(declared, int) and declared != len(cards):
                raise IcaSchemaError("ICA physical locator SSR page is incomplete")
            for card in cards:
                if not isinstance(card, dict):
                    continue
                address = _first_dict(card.get("address"))
                source_locality = str(address.get("city") or "").strip()
                if _location_key(source_locality) != requested_city:
                    continue
                external_id = str(card.get("accountNumber") or "").strip()
                name = str(card.get("storeName") or card.get("name") or "").strip()
                if not external_id or not name:
                    continue
                coordinates = _first_dict(address.get("coordinates") or card.get("coordinates"))
                offers_link = _first_dict(card.get("highlightUrls")).get("offers")
                offers_value = (
                    offers_link.get("url") if isinstance(offers_link, dict) else offers_link
                )
                online_url = str(card.get("onlineUrl") or "").strip() or None
                stores[external_id] = SourceStore(
                    chain=Chain.ICA,
                    external_id=external_id,
                    name=name,
                    address=str(address.get("street") or address.get("address") or "").strip()
                    or None,
                    postal_code=str(address.get("postalCode") or "").replace(" ", "") or None,
                    city=source_locality,
                    latitude=_decimal(
                        coordinates.get("latitude")
                        or coordinates.get("lat")
                        or coordinates.get("coordinateX")
                    ),
                    longitude=_decimal(
                        coordinates.get("longitude")
                        or coordinates.get("lng")
                        or coordinates.get("coordinateY")
                    ),
                    online_shopping=bool(online_url),
                    coverage=CoverageLevel.OFFERS_ONLY,
                    raw_reference=f"{reference}#accountNumber={external_id}",
                    source_fields={
                        "store_id": card.get("storeId"),
                        "account_number": external_id,
                        "offers_url": (
                            urljoin("https://www.ica.se", str(offers_value).strip())
                            if offers_value
                            else None
                        ),
                        "online_url": online_url,
                        "profile": card.get("profile"),
                        "source_locality": source_locality,
                        "municipality": address.get("municipality"),
                        "official_physical_locator": True,
                    },
                )
        return sorted(stores.values(), key=lambda store: store.name.casefold())

    def parse_catalog(
        self, raw: RawBatch, references: list[str], store: SourceStore
    ) -> ProductParseResult:
        products: list[SourceProduct] = []
        failures: list[ParseFailure] = []
        for document, reference in raw.with_references(references):
            if document.kind != "offers_page" or document.http_status != 200:
                continue
            try:
                data = initial_data_from_html(document.payload)
                rows = self.weekly_offer_rows(data)
            except (IcaSchemaError, TypeError, ValueError) as exc:
                failures.append(
                    ParseFailure(
                        raw_record_reference=reference,
                        error_code=ParserErrorCode.SCHEMA_CHANGED,
                        error_message=str(exc),
                        parser_version=self.parser_version,
                    )
                )
                continue
            for position, row in enumerate(rows):
                record_reference = f"{reference}#weeklyOffers/{position}"
                try:
                    products.append(
                        self._parse_offer(row, store, record_reference, document.fetched_at)
                    )
                except (IcaSchemaError, ValidationError, ValueError) as exc:
                    failures.append(
                        ParseFailure(
                            raw_record_reference=record_reference,
                            error_code=ParserErrorCode.UNKNOWN,
                            error_message=str(exc),
                            parser_version=self.parser_version,
                            sample={
                                "id": row.get("id"),
                                "name": _first_dict(row.get("details")).get("name"),
                            }
                            if isinstance(row, dict)
                            else {},
                        )
                    )
        return ProductParseResult(products=products, failures=failures)

    def _parse_offer(
        self, row: object, store: SourceStore, reference: str, fetched_at: Any
    ) -> SourceProduct:
        if not isinstance(row, dict):
            raise IcaSchemaError("ICA offer record must be an object")
        details = _first_dict(row.get("details"))
        name = str(details.get("name") or "").strip()
        external_id = str(row.get("id") or "").strip()
        if not name:
            raise IcaSchemaError("ICA offer is missing a product name")
        if not external_id:
            raise IcaSchemaError("ICA offer is missing an id")
        source_stores = row.get("stores") if isinstance(row.get("stores"), list) else []
        price_row = next(
            (
                item
                for item in source_stores
                if isinstance(item, dict)
                and str(item.get("BMSStoreId") or item.get("accountNumber") or "")
                in {store.external_id, str(store.source_fields.get("store_id") or "")}
            ),
            _first_dict(source_stores),
        )
        regular_price = _decimal(price_row.get("regularPrice"))
        comparison_price, comparison_unit = parse_comparison(
            row.get("comparisonPrice") or price_row.get("referencePriceText")
        )
        package_text = str(details.get("packageInformation") or "").strip() or None
        package_quantity, package_unit = parse_package(package_text)
        category = _first_dict(row.get("category"))
        offer = _promotion(row)
        mechanics = _first_dict(row.get("parsedMechanics"))
        price_suffix = str(mechanics.get("value4") or "").strip().casefold()
        sold_by_weight = price_suffix in {"/kg", "kr/kg"}
        member_price = (
            offer.price if offer.member_only and offer.type == PromotionType.MEMBER_PRICE else None
        )
        current_sale_price = (
            offer.price
            if not offer.member_only and offer.type == PromotionType.SALE_PRICE
            else regular_price
        )
        return SourceProduct(
            chain=Chain.ICA,
            store_external_id=store.external_id,
            external_product_id=external_id,
            gtin=_exact_gtin(row.get("eans")),
            name=name,
            brand=str(details.get("brand") or "").strip() or None,
            category_path=(str(category.get("articleGroupName")).strip(),)
            if category.get("articleGroupName")
            else (),
            sale_price=current_sale_price,
            regular_price=regular_price,
            member_price=member_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            package_text=package_text,
            package_quantity=package_quantity,
            package_unit=package_unit,
            sale_unit="kg" if sold_by_weight else "st" if regular_price else None,
            offers=(offer,),
            availability=None,
            basket_type="VIKT" if sold_by_weight else None,
            raw_reference=reference,
            fetched_at=fetched_at,
            source_fields={
                "coverage": CoverageLevel.OFFERS_ONLY.value,
                "variant_count": len(row.get("eans")) if isinstance(row.get("eans"), list) else 0,
            },
        )
