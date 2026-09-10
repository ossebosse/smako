from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

from grocery_data.app.connectors.coop.models import (
    CoopSchemaError,
    RenderedProductCard,
    grocery_store_records,
    product_json_ld,
    product_sitemap_urls,
    rendered_catalog_page,
    source_id_from_product_url,
    store_page_records,
)
from grocery_data.app.connectors.coop.store_locator import validated_store_locator
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

_GTIN = re.compile(r"\d{8}|\d{12,14}")
_PACKAGE = re.compile(
    r"^(?P<approx>(?:ca|cirka)\s+)?(?P<amount>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>kg|kilo|g|gram|ml|milliliter|cl|dl|l|liter|st|styck)"
    r"(?:\s+ungefärlig\s+vikt)?$",
    re.IGNORECASE,
)
_PACK = re.compile(r"^(?P<count>\d+)\s*[- ]?pack$", re.IGNORECASE)
_PACKAGE_SHAPE = re.compile(
    r"^(?:(?:(?:ca|cirka)\s+)?\d+(?:[.,]\d+)?(?:\s*[-–]\s*\d+(?:[.,]\d+)?)?"
    r"|mellan\s+(?:cirka\s+)?\d+(?:[.,]\d+)?\s+till\s+\d+(?:[.,]\d+)?)\s*"
    r"(?:kg|kilo|g|gram|ml|milliliter|cl|dl|l|liter|st|styck|pack)"
    r"(?:\s+ungefärlig\s+vikt)?$",
    re.IGNORECASE,
)
_ACTION_PREFIX = re.compile(
    r"^(?:spara\s+i\s+lista|se\s+(?P<count>\d+)\s+varor)$",
    re.IGNORECASE,
)
# Split semantic label fields while preserving a decimal comma only when it is
# genuinely surrounded by digits. A field such as ``100-110, Erbjudande`` must
# still split even though the character before the comma is numeric.
_LABEL_SEPARATOR = re.compile(r"(?:(?<!\d),|,(?!\s*\d))\s*")
_WORD_PRICE = re.compile(
    r"(?P<major>\d+)\s*kron(?:a|or)(?:\s+och\s+(?P<minor>\d+)\s*öre)?",
    re.IGNORECASE,
)
_NUMERIC_PRICE = re.compile(r"(?P<value>\d+(?:[.,]\d+)?)")
_MULTIBUY = re.compile(
    r"(?P<quantity>\d+)\s+för\s+(?P<price>\d+(?:[.,]\d+)?|\d+\s+kron(?:a|or)"
    r"(?:\s+och\s+\d+\s+öre)?)",
    re.IGNORECASE,
)
_MAX_QUANTITY = re.compile(
    r"max\s+(?P<count>\d+)\s+(?:st|styck|köp)\s+per\s+hushåll",
    re.IGNORECASE,
)
_UNIT_CODES: dict[str, tuple[Decimal, str]] = {
    "GRM": (Decimal(1), "g"),
    "KGM": (Decimal(1000), "g"),
    "MLT": (Decimal(1), "ml"),
    "LTR": (Decimal(1000), "ml"),
    "C62": (Decimal(1), "st"),
}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace("\u00a0", "").replace(",", ".")
    try:
        result = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and result > 0 else None


def _brand(value: object) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    return str(value or "").strip() or None


def _category(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    text = str(value or "").strip()
    return (text,) if text else ()


def _quantity(value: object) -> tuple[Decimal | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    amount = _decimal(value.get("value"))
    unit = str(value.get("unitCode") or "").strip().upper()
    conversion = _UNIT_CODES.get(unit)
    if amount is None or conversion is None:
        return None, None
    factor, normalized_unit = conversion
    return amount * factor, normalized_unit


def _offers(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        rows = [row for row in value if isinstance(row, dict)]
        if len(rows) == 1:
            return rows[0]
    return {}


def _page_path(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.netloc and parsed.netloc.casefold() not in {"coop.se", "www.coop.se"}:
        return None
    path = parsed.path if parsed.scheme or parsed.netloc else text
    return path if path.startswith("/butiker-erbjudanden/") else None


def _place_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _location_for_store(
    locations: tuple[dict[str, Any], ...],
    *,
    name: str,
    path: str,
    requested_city: str,
) -> dict[str, Any] | None:
    matches = [row for row in locations if _page_path(row.get("@id")) == path]
    if not matches:
        return None
    if len(matches) != 1:
        raise CoopSchemaError("Coop store page has ambiguous GroceryStore JSON-LD")
    row = matches[0]
    location_name = str(row.get("name") or "").strip()
    if location_name and location_name.casefold() != name.casefold():
        raise CoopSchemaError("Coop StorePageType and GroceryStore names disagree")
    address = row.get("address") if isinstance(row.get("address"), dict) else {}
    locality = str(address.get("addressLocality") or "").strip()
    if locality and _place_key(locality) != _place_key(requested_city):
        raise CoopSchemaError("Coop GroceryStore locality disagrees with requested city")
    return row


def _display_price(value: str) -> Decimal | None:
    word = _WORD_PRICE.search(value)
    if word:
        return Decimal(word.group("major")) + Decimal(word.group("minor") or 0) / 100
    numeric = _NUMERIC_PRICE.search(value)
    return _decimal(numeric.group("value")) if numeric else None


def _display_unit(value: str) -> str | None:
    normalized = value.casefold()
    if re.search(r"(?:kr)?\s*/\s*kg\b|\bper\s+kilo\b", normalized):
        return "kg"
    if re.search(r"(?:kr)?\s*/\s*l\b|\bper\s+liter\b", normalized):
        return "l"
    if re.search(r"(?:kr)?\s*/\s*st\b|\bstyck\b", normalized):
        return "st"
    return None


def _display_comparison(value: str | None) -> tuple[Decimal | None, str | None]:
    """Keep comparison metadata only when one exact value and unit are stated."""

    text = value or ""
    if re.search(r"\bmellan\b|\d\s+till\s+\d", text, re.IGNORECASE):
        return None, None
    unit = _display_unit(text)
    price = _display_price(text)
    return (price, unit) if price is not None and unit is not None else (None, None)


def _display_quantity(value: str) -> tuple[Decimal | None, str | None, bool]:
    text = value.strip().rstrip(".")
    match = _PACKAGE.fullmatch(text)
    if match:
        amount = _decimal(match.group("amount"))
        if amount is None:
            return None, None, False
        unit = match.group("unit").casefold()
        approximate = bool(match.group("approx")) or "ungefärlig" in text.casefold()
        if unit in {"kg", "kilo"}:
            return amount * 1000, "g", approximate
        if unit in {"g", "gram"}:
            return amount, "g", approximate
        if unit in {"l", "liter"}:
            return amount * 1000, "ml", approximate
        if unit == "dl":
            return amount * 100, "ml", approximate
        if unit == "cl":
            return amount * 10, "ml", approximate
        if unit in {"ml", "milliliter"}:
            return amount, "ml", approximate
        if unit in {"st", "styck"}:
            return amount, "st", approximate
        return amount, unit, approximate
    pack = _PACK.fullmatch(text)
    count = _decimal(pack.group("count")) if pack else None
    return (count, "st", False) if count else (None, None, False)


def _coalesce_price_markers(parts: list[str]) -> list[str]:
    """Join live a11y marker/value pairs without changing other source text."""

    merged: list[str] = []
    position = 0
    while position < len(parts):
        part = parts[position]
        if part.casefold() in {"medlemspris", "veckans tips"} and position + 1 < len(parts):
            merged.append(f"{part} {parts[position + 1]}")
            position += 2
            continue
        merged.append(part)
        position += 1
    return merged


def _split_card_label(
    card: RenderedProductCard,
) -> tuple[str, str | None, str | None, list[str], int | None]:
    parts = [
        part.strip().rstrip(".") for part in _LABEL_SEPARATOR.split(card.aria_label) if part.strip()
    ]
    group_count: int | None = None
    if parts:
        action = _ACTION_PREFIX.fullmatch(parts[0])
        if action:
            group_count = int(action.group("count")) if action.group("count") else None
            parts = parts[1:]
    parts = _coalesce_price_markers(parts)
    price_index = next(
        (
            index
            for index, part in enumerate(parts)
            if part.casefold().startswith(("pris ", "medlemspris ", "erbjudande ", "veckans tips "))
        ),
        None,
    )
    if price_index is None or price_index < 2:
        raise CoopSchemaError("Coop product card has no verified price boundary")
    preamble = parts[:price_index]
    package_index = next(
        (
            index
            for index in range(len(preamble) - 1, -1, -1)
            if _display_quantity(preamble[index])[0] is not None
        ),
        None,
    )
    if package_index is None:
        # Ranges such as 425-500 g identify source package text but do not
        # prove one purchasable quantity. Preserve the text and stay UNKNOWN.
        package_index = next(
            (
                index
                for index in range(len(preamble) - 1, -1, -1)
                if _PACKAGE_SHAPE.fullmatch(preamble[index])
            ),
            None,
        )
    if package_index is None:
        name = preamble[0]
        brand = ", ".join(preamble[1:]) or None
        package_text = None
    else:
        package_text = preamble[package_index]
        brand = preamble[package_index - 1] if package_index >= 1 else None
        name = ", ".join(preamble[: max(1, package_index - 1)])
    if not name:
        raise CoopSchemaError("Coop product card is missing a name")
    return name, brand, package_text, parts[price_index:], group_count


def _price_token(parts: list[str], *prefixes: str) -> str | None:
    lowered = tuple(prefix.casefold() for prefix in prefixes)
    return next((part for part in parts if part.casefold().startswith(lowered)), None)


def _promotion_from_parts(parts: list[str]) -> SourceOffer | None:
    member = _price_token(parts, "medlemspris")
    ordinary_offer = _price_token(
        parts,
        "erbjudande pris",
        "erbjudandepris",
        "erbjudande ",
        "kampanjpris ",
        "veckans tips ",
    )
    token = member or ordinary_offer
    if token is None:
        return None
    multi = _MULTIBUY.search(token)
    member_only = member is not None
    max_token = _price_token(parts, "max ")
    maximum_match = _MAX_QUANTITY.search(max_token or "")
    if multi:
        price = _display_price(multi.group("price"))
        promotion_type = PromotionType.MULTIBUY
        quantity = int(multi.group("quantity"))
    else:
        price = _display_price(token)
        promotion_type = PromotionType.MEMBER_PRICE if member_only else PromotionType.SALE_PRICE
        quantity = None
    if price is None:
        raise CoopSchemaError("Coop promotion lacks a valid price")
    offer_comparison = _price_token(
        parts,
        "erbjudande jämförpris",
        "erbjudande jämför pris",
        "erbj. jfr pris",
    )
    offer_comparison_price, offer_comparison_unit = _display_comparison(offer_comparison)
    return SourceOffer(
        type=promotion_type,
        price=price,
        quantity=quantity,
        member_only=member_only,
        max_quantity=int(maximum_match.group("count")) if maximum_match else None,
        description=token,
        source_payload={
            "sale_unit": _display_unit(token),
            "comparison_price": offer_comparison_price,
            "comparison_unit": offer_comparison_unit,
        },
    )


class CoopParser:
    """Offline parser for Coop source shapes independently verified as public."""

    parser_version = "coop-parser-v2"

    @staticmethod
    def sitemap_product_urls(payload: bytes) -> tuple[str, ...]:
        return product_sitemap_urls(payload)

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        stores: dict[str, SourceStore] = {}
        for document, reference in raw.with_references(references):
            if document.kind != "store_page" or document.http_status != 200:
                continue
            locations = grocery_store_records(document.payload)
            for row in store_page_records(document.payload):
                name = str(row.get("name") or "").strip()
                external_id = str(row.get("storeID") or "").strip()
                path = _page_path(row.get("url"))
                if path is None:
                    raise CoopSchemaError("Coop StorePageType has an invalid public page path")
                location = _location_for_store(
                    locations,
                    name=name,
                    path=path,
                    requested_city=area.city,
                )
                address = (
                    location.get("address")
                    if location is not None and isinstance(location.get("address"), dict)
                    else {}
                )
                source_city = str(address.get("addressLocality") or "").strip()
                geo = (
                    location.get("geo")
                    if location is not None and isinstance(location.get("geo"), dict)
                    else {}
                )
                stores[external_id] = SourceStore(
                    chain=Chain.COOP,
                    external_id=external_id,
                    name=name,
                    address=str(address.get("streetAddress") or "").strip() or None,
                    postal_code=str(address.get("postalCode") or "").strip() or None,
                    # The transport selects only paths from its verified city-scoped
                    # bootstrap set. Some live pages omit GroceryStore JSON-LD, so
                    # the explicit collection scope remains valid city evidence;
                    # address and postal code stay unknown rather than being guessed.
                    city=source_city or area.city,
                    latitude=_decimal(geo.get("latitude")),
                    longitude=_decimal(geo.get("longitude")),
                    online_shopping=None,
                    coverage=CoverageLevel.OFFERS_ONLY,
                    raw_reference=f"{reference}#storeID={external_id}",
                    source_fields={
                        "ledger_account_number": row.get("ledgerAccountNumber"),
                        "organization_unit_id": row.get("organizationUnitID"),
                        "simple_address_url": row.get("simpleAddressUrl"),
                        "route_segment": row.get("routeSegment"),
                        "store_page_url": path,
                        "store_page_path": path,
                        "city_evidence": (
                            "grocery_store_json_ld" if source_city else "verified_bootstrap_scope"
                        ),
                        "disable_store_offers_flyer": row.get("disableStoreOffersFlyer"),
                        # None means no online fulfilment-store identity has
                        # been verified. It must never be guessed from one of
                        # the physical-store identifier namespaces above.
                        "online_fulfilment_store_id": None,
                    },
                )
        return sorted(stores.values(), key=lambda item: (item.name.casefold(), item.external_id))

    def parse_physical_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        """Join rendered locator geography to stable StorePageType identities."""

        locator_documents = [
            document
            for document in raw.documents
            if document.kind == "store_locator" and document.http_status == 200
        ]
        if len(locator_documents) != 1:
            raise CoopSchemaError("Coop physical discovery requires one locator envelope")
        locator_rows = validated_store_locator(locator_documents[0].payload)
        by_path = {row["store_page_path"]: row for row in locator_rows}
        page_stores = self.parse_stores(raw, references, area)
        if len(page_stores) != len(locator_rows):
            raise CoopSchemaError("Coop locator/detail identity counts do not reconcile")
        result: list[SourceStore] = []
        seen_paths: set[str] = set()
        for store in page_stores:
            path = str(store.source_fields.get("store_page_path") or "")
            row = by_path.get(path)
            if row is None:
                raise CoopSchemaError("Coop detail identity is absent from locator evidence")
            if " ".join(store.name.split()).casefold() != " ".join(row["name"].split()).casefold():
                raise CoopSchemaError("Coop locator/detail names disagree")
            if row["city"].casefold() != area.city.strip().casefold():
                raise CoopSchemaError("Coop locator card escaped requested city")
            seen_paths.add(path)
            result.append(
                store.model_copy(
                    update={
                        "address": row["address"],
                        "postal_code": row["postal_code"],
                        "city": row["city"],
                        "source_fields": {
                            **store.source_fields,
                            "city_evidence": "rendered_official_locator",
                            "official_physical_locator": True,
                        },
                    }
                )
            )
        if seen_paths != set(by_path):
            raise CoopSchemaError("Coop locator contained a detail path without identity proof")
        return sorted(result, key=lambda item: (item.name.casefold(), item.external_id))

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        products: dict[str, SourceProduct] = {}
        failures: list[ParseFailure] = []
        for document, reference in raw.with_references(references):
            if document.kind == "product_sitemap":
                try:
                    product_sitemap_urls(document.payload)
                except CoopSchemaError as exc:
                    failures.append(self._failure(reference, ParserErrorCode.SCHEMA_CHANGED, exc))
                # The sitemap proves identities/URLs only. It intentionally
                # does not manufacture SourceProducts or current store prices.
                continue
            if document.kind != "product_detail":
                if document.kind not in {"rendered_catalog_page", "rendered_offers_page"}:
                    continue
                try:
                    page = rendered_catalog_page(document.payload)
                except CoopSchemaError as exc:
                    failures.append(self._failure(reference, ParserErrorCode.SCHEMA_CHANGED, exc))
                    continue
                if (
                    page.store_external_id is not None
                    and page.store_external_id != store.external_id
                ):
                    failures.append(
                        self._failure(
                            reference,
                            ParserErrorCode.SCHEMA_CHANGED,
                            CoopSchemaError("Coop rendered offers store identity mismatch"),
                        )
                    )
                    continue
                expected_path = str(store.source_fields.get("store_page_path") or "")
                if page.store_page_path is not None and page.store_page_path != expected_path:
                    failures.append(
                        self._failure(
                            reference,
                            ParserErrorCode.SCHEMA_CHANGED,
                            CoopSchemaError("Coop rendered offers store path mismatch"),
                        )
                    )
                    continue
                for position, card in enumerate(page.cards):
                    card_reference = f"{reference}#article[{position}]"
                    try:
                        parsed = self._parse_rendered_card(
                            card,
                            store=store,
                            reference=card_reference,
                            fetched_at=document.fetched_at,
                        )
                    except (CoopSchemaError, ValidationError, ValueError) as exc:
                        failures.append(self._failure(card_reference, ParserErrorCode.UNKNOWN, exc))
                        continue
                    identity_key = parsed.external_product_id or (
                        f"unresolved:{parsed.name.casefold()}:{card_reference}"
                    )
                    products[identity_key] = parsed
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
                row = self._parse_product_detail(
                    document.payload,
                    store=store,
                    reference=reference,
                    fetched_at=document.fetched_at,
                    source_url=document.url,
                )
            except (CoopSchemaError, ValidationError, ValueError) as exc:
                failures.append(self._failure(reference, ParserErrorCode.SCHEMA_CHANGED, exc))
                continue
            key = row.external_product_id or row.gtin or ""
            products[key] = row
        return ProductParseResult(products=list(products.values()), failures=failures)

    def _parse_rendered_card(
        self,
        card: RenderedProductCard,
        *,
        store: SourceStore,
        reference: str,
        fetched_at: datetime,
    ) -> SourceProduct:
        source_id = source_id_from_product_url(card.href or "")
        name, brand, package_text, parts, group_count = _split_card_label(card)
        package_quantity, package_unit, approximate = _display_quantity(package_text or "")
        promotion = _promotion_from_parts(parts)
        regular = _price_token(parts, "ordinarie pris", "ord. pris")
        public = _price_token(parts, "pris ")
        current = regular or public
        sale_price = _display_price(current or "")
        sale_unit = _display_unit(current or "")
        # Variable-weight cards carry both a kg rate and an estimated per-piece
        # amount. The source kg rate is the purchasable unit price; the existing
        # normalizer combines it with the explicit approximate weight.
        public_weight = next(
            (
                part
                for part in parts
                if part.casefold().startswith("pris ") and _display_unit(part) in {"kg", "l"}
            ),
            None,
        )
        if public_weight is not None and promotion is None:
            sale_price = _display_price(public_weight)
            sale_unit = _display_unit(public_weight)
        regular_comparison = _price_token(
            parts,
            "ordinarie jämförpris",
            "ord. jfr pris",
        )
        comparison = regular_comparison or _price_token(parts, "jämförpris", "jfr pris")
        comparison_price, comparison_unit = _display_comparison(comparison)
        average_weight_kg = (
            package_quantity / 1000
            if approximate and package_quantity is not None and package_unit == "g"
            else None
        )
        member_price = (
            promotion.price
            if promotion is not None
            and promotion.member_only
            and promotion.type == PromotionType.MEMBER_PRICE
            else None
        )
        if approximate and comparison_unit in {"kg", "l"}:
            # Verified variable-weight offer cards expose ordinary piece total
            # plus ordinary comparison rate. The rate, not the estimated piece
            # total, is the source price consumed by PurchaseQuantityResolver.
            sale_price = comparison_price
            sale_unit = comparison_unit
        return SourceProduct(
            chain=Chain.COOP,
            store_external_id=store.external_id,
            external_product_id=source_id,
            # A numeric URL suffix is a Coop source identity. Only explicit
            # JSON-LD gtin/gtin13 fields are allowed to populate GTIN.
            gtin=None,
            name=name,
            brand=brand,
            sale_price=sale_price,
            regular_price=sale_price,
            member_price=member_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            package_text=package_text,
            package_quantity=package_quantity,
            package_unit=package_unit,
            drained_quantity=None,
            sale_unit=sale_unit,
            offers=(promotion,) if promotion else (),
            average_weight_kg=average_weight_kg,
            basket_type=(
                "ST"
                if average_weight_kg is not None
                else "VIKT"
                if sale_unit in {"kg", "l"} and package_quantity is None
                else "ST"
            ),
            raw_reference=reference,
            fetched_at=fetched_at,
            source_fields={
                "rendered_product_url": card.href,
                "package_approximate": approximate,
                "offer_group_count": group_count,
                "offer_group_identity_unresolved": source_id is None,
                "offers_store_context": store.external_id,
                "price_context_verified": True,
            },
        )

    def _parse_product_detail(
        self,
        payload: bytes,
        *,
        store: SourceStore,
        reference: str,
        fetched_at: datetime,
        source_url: str,
    ) -> SourceProduct:
        if not store.source_fields.get("online_fulfilment_store_id"):
            raise CoopSchemaError(
                "Coop product-detail price lacks a verified online fulfilment-store context"
            )
        row = product_json_ld(payload)
        name = str(row.get("name") or "").strip()
        if not name:
            raise CoopSchemaError("Coop JSON-LD Product is missing name")
        # Schema.org `sku` and the numeric URL suffix are source identities,
        # not proof of a GTIN. Only explicit JSON-LD GTIN properties qualify.
        raw_gtins = [row.get("gtin13"), row.get("gtin")]
        gtins = {
            str(value).strip()
            for value in raw_gtins
            if value is not None and _GTIN.fullmatch(str(value).strip())
        }
        if len(gtins) > 1:
            raise CoopSchemaError("Coop JSON-LD Product GTIN fields conflict")
        gtin = next(iter(gtins), None)
        sku = str(row.get("sku") or "").strip() or None
        url_source_id = source_id_from_product_url(source_url)
        external_product_id = sku or url_source_id or gtin
        if external_product_id is None:
            raise CoopSchemaError("Coop Product identity is missing")
        offer = _offers(row.get("offers"))
        sale_price = _decimal(offer.get("price"))
        package_quantity, package_unit = _quantity(row.get("size"))
        availability = str(offer.get("availability") or "").rsplit("/", 1)[-1] or None
        return SourceProduct(
            chain=Chain.COOP,
            store_external_id=store.external_id,
            external_product_id=external_product_id,
            gtin=gtin,
            name=name,
            brand=_brand(row.get("brand")),
            category_path=_category(row.get("category")),
            sale_price=sale_price,
            regular_price=sale_price,
            package_text=(
                f"{row['size'].get('value')} {row['size'].get('unitCode')}"
                if isinstance(row.get("size"), dict)
                and row["size"].get("value") is not None
                and row["size"].get("unitCode")
                else None
            ),
            package_quantity=package_quantity,
            package_unit=package_unit,
            # A JSON-LD offer is for one Product sales unit. With an explicit
            # size this is a fixed package; without size we preserve UNKNOWN.
            sale_unit="st" if sale_price is not None and package_quantity is not None else None,
            availability=availability,
            basket_type="ST" if package_quantity is not None else None,
            raw_reference=reference,
            fetched_at=fetched_at or datetime.now(tz=UTC),
            source_fields={
                "jsonld_price_currency": offer.get("priceCurrency"),
                "jsonld_product_url": source_url,
                "url_source_id": url_source_id,
                "online_fulfilment_store_id": store.source_fields.get("online_fulfilment_store_id"),
                "price_context_verified": bool(
                    store.source_fields.get("online_fulfilment_store_id")
                ),
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
