from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from grocery_data.app.connectors.coop.models import CoopSchemaError
from grocery_data.app.connectors.coop.online_catalog_models import (
    CoopOnlineCatalogReconciliation,
    CoopOnlineDuplicateMetrics,
    CoopOnlineResultsPage,
    flatten_terminal_categories,
    validated_results_page,
)
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ParseFailure,
    PriceContextType,
    ProductParseResult,
    PromotionType,
    RawBatch,
    RawFetch,
    SourceOffer,
    SourceProduct,
    SourceStore,
)

COOP_ONLINE_CATEGORY_TREE_KIND = "coop_category_tree"
COOP_ONLINE_PRODUCT_SEARCH_KIND = "coop_product_search"
COOP_ONLINE_CATEGORY_PAGE_KIND = "coop_product_category_page"
COOP_ONLINE_PRODUCT_BY_ID_KIND = "coop_product_by_id"
COOP_ONLINE_PROMOTION_KIND = "coop_promotion"
COOP_ONLINE_PROMOTIONS_KIND = "coop_promotions"

_GTIN_LENGTHS = frozenset({8, 12, 13, 14})
_DECIMAL = re.compile(r"-?\d+(?:[.,]\d+)?")
_COMPARISON_UNIT = re.compile(
    r"(?:kr\s*/\s*)?(kg|kilogram|g|l|lit|liter|ml|st|styck|piece|pieces)$",
    re.IGNORECASE,
)
_PACKAGE_UNITS: dict[str, tuple[Decimal, str]] = {
    "gram": (Decimal(1), "g"),
    "grams": (Decimal(1), "g"),
    "gr": (Decimal(1), "g"),
    "g": (Decimal(1), "g"),
    "kilogram": (Decimal(1000), "g"),
    "kilograms": (Decimal(1000), "g"),
    "kg": (Decimal(1000), "g"),
    "milliliter": (Decimal(1), "ml"),
    "milliliters": (Decimal(1), "ml"),
    "ml": (Decimal(1), "ml"),
    "centiliter": (Decimal(10), "ml"),
    "cl": (Decimal(10), "ml"),
    "deciliter": (Decimal(100), "ml"),
    "dl": (Decimal(100), "ml"),
    "liter": (Decimal(1000), "ml"),
    "litre": (Decimal(1000), "ml"),
    "l": (Decimal(1000), "ml"),
    "piece": (Decimal(1), "st"),
    "pieces": (Decimal(1), "st"),
    "styck": (Decimal(1), "st"),
    "st": (Decimal(1), "st"),
}
_SALE_UNITS = {
    "styck": "st",
    "piece": "st",
    "st": "st",
    "kilogram": "kg",
    "kg": "kg",
    "vikt": "kg",
    "liter": "l",
    "litre": "l",
    "l": "l",
}


class CoopOnlineCompletenessError(CoopSchemaError):
    """A page union cannot safely support a complete-catalog claim."""


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        match = _DECIMAL.search(value.replace("\u00a0", ""))
        if match is None:
            return None
        value = match.group(0).replace(",", ".")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() and result > 0 else None


def _b2c_price(value: object) -> Decimal | None:
    return _decimal(value.get("b2cPrice")) if isinstance(value, dict) else None


def _decimal_diagnostic(value: object) -> str | None:
    parsed = _decimal(value)
    return str(parsed) if parsed is not None else None


def _valid_gtin(value: str | None) -> bool:
    if value is None or len(value) not in _GTIN_LENGTHS or not value.isascii():
        return False
    if not value.isdigit():
        return False
    body, supplied = value[:-1], int(value[-1])
    weighted = sum(
        int(digit) * (3 if index % 2 == 0 else 1)
        for index, digit in enumerate(reversed(body))
    )
    return (10 - weighted % 10) % 10 == supplied


def _timestamp(value: object, *, field: str) -> datetime | None:
    if value is None or str(value).strip() == "":
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CoopSchemaError(f"Coop online promotion has invalid {field}") from exc
    if parsed.tzinfo is None:
        raise CoopSchemaError(f"Coop online promotion {field} lacks timezone")
    return parsed.astimezone(UTC)


def _positive_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        value = next(
            (value.get(key) for key in ("value", "quantity", "number") if value.get(key) is not None),
            None,
        )
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        match = re.search(r"\d+", str(value))
        result = int(match.group()) if match else 0
    return result if result > 0 else None


def _comparison_unit(row: dict[str, Any]) -> str | None:
    unit_value = row.get("comparativePriceUnit")
    if isinstance(unit_value, dict):
        explicit_unit = str(unit_value.get("unit") or "").strip().casefold()
        normalized = {
            "kg": "kg",
            "kilogram": "kg",
            "g": "g",
            "gram": "g",
            "l": "l",
            "lit": "l",
            "liter": "l",
            "ml": "ml",
            "milliliter": "ml",
            "st": "st",
            "styck": "st",
            "piece": "st",
            "pieces": "st",
        }.get(explicit_unit)
        if normalized is not None:
            # `postfix` such as "drickfärdig" or "ätklar" qualifies the
            # compared contents, not the physical price unit.
            return normalized
        unit_value = explicit_unit
    text = str(unit_value or row.get("comparativePriceText") or "").strip().casefold()
    match = _COMPARISON_UNIT.search(text)
    if match is None:
        return None
    return {
        "kilogram": "kg",
        "g": "g",
        "lit": "l",
        "liter": "l",
        "styck": "st",
        "piece": "st",
        "pieces": "st",
    }.get(match.group(1).casefold(), match.group(1).casefold())


def _package(row: dict[str, Any]) -> tuple[Decimal | None, str | None]:
    amount = _decimal(row.get("packageSize"))
    source_unit = str(row.get("packageSizeUnit") or "").strip().casefold()
    conversion = _PACKAGE_UNITS.get(source_unit)
    if conversion is None and source_unit.startswith(("gram/", "gram ")):
        conversion = _PACKAGE_UNITS["gram"]
    if amount is None or conversion is None:
        # Printed quantity is independent evidence, unlike a price quotient.
        # Do not override a provided invalid or conflicting structured unit.
        if row.get("packageSize") is None and not source_unit:
            match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(g|kg|ml|cl|dl|l|st)\s*",
                                 str(row.get("packageSizeInformation") or ""), re.IGNORECASE)
            if match:
                factor, unit = _PACKAGE_UNITS[match[2].lower()]
                value = Decimal(match[1].replace(',', '.'))
                if value > 0:
                    return value * factor, unit
        return None, None
    factor, unit = conversion
    return amount * factor, unit


def _category_path(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("navCategories")
    if not isinstance(raw, list):
        return ()
    names: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, dict):
            value = item.get("name") or item.get("displayName")
        else:
            value = item
        name = " ".join(str(value or "").split())
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        names.append(name)
    return tuple(names)


def _promotion_type(source_type: str, *, member_only: bool) -> PromotionType:
    normalized = source_type.strip().upper()
    if normalized == "MULTI_BUY_FIXED_PRICE":
        return PromotionType.MULTIBUY
    if normalized == "PERCENTAGE_DISCOUNT":
        return PromotionType.PERCENT_DISCOUNT
    if normalized == "FIXED_PRICE":
        return PromotionType.MEMBER_PRICE if member_only else PromotionType.SALE_PRICE
    return PromotionType.OTHER


def _active_offers(
    row: dict[str, Any],
    *,
    observed_at: datetime,
) -> tuple[SourceOffer, ...]:
    raw_promotions = row.get("onlinePromotions")
    if raw_promotions is None:
        return ()
    if not isinstance(raw_promotions, list):
        raise CoopSchemaError("Coop online onlinePromotions must be a list")
    offers: list[SourceOffer] = []
    for promotion in raw_promotions:
        if not isinstance(promotion, dict):
            raise CoopSchemaError("Coop online promotion must be an object")
        start = _timestamp(promotion.get("startDate"), field="startDate")
        end = _timestamp(promotion.get("endDate"), field="endDate")
        # An undated promotion is retained in the raw row but is not exposed to
        # basket maths. Active price semantics require an explicit time window.
        if start is None or end is None or not (start <= observed_at <= end):
            continue
        if start > end:
            raise CoopSchemaError("Coop online promotion validity is reversed")
        member_value = promotion.get("medMeraRequired")
        if not isinstance(member_value, bool):
            raise CoopSchemaError("Coop online promotion lacks explicit MedMera semantics")
        source_type = str(promotion.get("type") or "").strip().upper()
        if not source_type:
            raise CoopSchemaError("Coop online promotion lacks type")
        promotion_type = _promotion_type(source_type, member_only=member_value)
        quantity = (
            _positive_int(promotion.get("numberOfProductRequired"))
            if promotion_type is PromotionType.MULTIBUY
            else 1
        )
        if promotion_type is PromotionType.MULTIBUY and quantity is None:
            raise CoopSchemaError("Coop online multibuy lacks required quantity")
        price = _b2c_price(promotion.get("priceData"))
        if price is None:
            price = _decimal(promotion.get("price"))
        if price is None:
            raise CoopSchemaError("Coop online active promotion lacks price")
        external_id = str(promotion.get("id") or "").strip()
        if not external_id:
            raise CoopSchemaError("Coop online promotion lacks identity")
        piece_limit = _verified_piece_limit(promotion)
        # The shared multipack model limits complete discounted groups, while
        # Coop's explicit Styck cap counts individual packages. Never multiply
        # a piece cap by the bundle quantity in checkout.
        offer_limit = (piece_limit // quantity if piece_limit is not None
                       and promotion_type is PromotionType.MULTIBUY else piece_limit)
        limit_verified = offer_limit is not None and offer_limit > 0
        offers.append(
            SourceOffer(
                external_id=external_id,
                type=promotion_type,
                valid_from=start.date(),
                valid_to=end.date(),
                price=price,
                quantity=quantity,
                member_only=member_value,
                max_quantity=offer_limit if limit_verified else None,
                description=str(promotion.get("message") or source_type).strip(),
                source_payload={
                    "purchase_limit_verified": limit_verified,
                    "source_max_piece_quantity": piece_limit,
                    "source_type": source_type,
                    "piece_price": str(_b2c_price(promotion.get("piecePriceData")) or "") or None,
                    "comparative_price": str(
                        _b2c_price(promotion.get("comparativePrice"))
                        or _decimal(promotion.get("comparativePrice"))
                        or ""
                    )
                    or None,
                    "med_mera_required": member_value,
                    "number_of_products_required": quantity,
                    "percentage_discount": _decimal_diagnostic(
                        promotion.get("percentageDiscount")
                    ),
                    "adjusted_percentage_discount": _decimal_diagnostic(
                        promotion.get("adjustedPercentageDiscount")
                    ),
                },
            )
        )
    return tuple(offers)


def _verified_piece_limit(promotion: dict[str, Any]) -> int | None:
    """Only the explicit positive integral piece cap is currently actionable.

    Absent/null/weight caps cannot establish an unlimited promotion. The raw
    response retains those terms; v4 withholds the offer and retains base price.
    """
    limit = promotion.get("maxNumberOfUseWithUnit")
    raw = promotion.get("maxNumberOfUse")
    if (not isinstance(limit, dict) or limit.get("unit") != "Styck"
            or type(raw) is not int or raw <= 0 or type(limit.get("value")) not in {int, float}):
        return None
    value = _decimal(limit.get("value"))
    if value is None or value <= 0 or value != value.to_integral_value():
        return None
    return int(value)


def _verified_available_promotions(row: dict[str, Any]) -> bool:
    """A type summary cannot establish price, membership or purchase terms."""
    if "availablePromotions" not in row:
        return True  # Earlier reviewed responses have no presentation summary.
    summary = row["availablePromotions"]
    known = {"FIXED_PRICE", "MULTI_BUY_FIXED_PRICE", "PERCENTAGE_DISCOUNT"}
    return (isinstance(summary, list)
            and all(isinstance(value, str) and value in known for value in summary)
            and len(summary) == len(set(summary))
            and set(summary) == {offer.get("type") for offer in row.get("onlinePromotions") or []})


def _purchase_fingerprint(product: SourceProduct) -> str:
    """Fingerprint all identity and purchase semantics, excluding placement/lineage."""

    payload = {
        "external_product_id": product.external_product_id,
        "gtin": product.gtin,
        "name": product.name,
        "brand": product.brand,
        "sale_price": str(product.sale_price) if product.sale_price is not None else None,
        "regular_price": (
            str(product.regular_price) if product.regular_price is not None else None
        ),
        "member_price": str(product.member_price) if product.member_price is not None else None,
        "comparison_price": (
            str(product.comparison_price) if product.comparison_price is not None else None
        ),
        "comparison_unit": product.comparison_unit,
        "package_text": product.package_text,
        "package_quantity": (
            str(product.package_quantity) if product.package_quantity is not None else None
        ),
        "package_unit": product.package_unit,
        "sale_unit": product.sale_unit,
        "offers": [offer.model_dump(mode="json") for offer in product.offers],
        "availability": product.availability,
        "basket_type": product.basket_type,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class CoopOnlineCatalogParser:
    """Parser for Coop's regional online product context, separate from offers."""

    parser_version = "coop-online-catalog-parser-v5"

    @staticmethod
    def terminal_categories(document: RawFetch) -> tuple[tuple[str, str], ...]:
        if document.kind != COOP_ONLINE_CATEGORY_TREE_KIND or document.http_status != 200:
            raise CoopSchemaError("expected one successful Coop category-tree response")
        try:
            leaves = flatten_terminal_categories(document.json_payload())
        except (TypeError, ValueError) as exc:
            if isinstance(exc, CoopSchemaError):
                raise
            raise CoopSchemaError("Coop online category-tree JSON changed") from exc
        return tuple((node.code, node.name) for node in leaves)

    @staticmethod
    def _require_context(document: RawFetch, store: SourceStore) -> None:
        if store.chain is not Chain.COOP:
            raise CoopSchemaError("Coop online parser received another chain")
        if store.price_context_type is not PriceContextType.ONLINE_FULFILLMENT:
            raise CoopSchemaError("Coop online catalogue requires ONLINE_FULFILLMENT context")
        if store.physical_store_external_id is not None:
            raise CoopSchemaError("Coop online context must not impersonate a physical store")
        if document.chain is not Chain.COOP or document.store_external_id != store.external_id:
            raise CoopSchemaError("Coop online response context identity mismatch")
        groups = document.query.get("groups")
        if groups is not None and groups != "CUSTOMER_PRIVATE":
            raise CoopSchemaError("Coop online catalogue capture is not the verified B2C group")

    @staticmethod
    def _request_integer(document: RawFetch, name: str) -> int:
        value = document.query.get(name)
        if value is None or isinstance(value, bool):
            raise CoopSchemaError(f"Coop online raw response lacks requested {name}")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise CoopSchemaError(f"Coop online raw {name} is not an integer") from exc
        return parsed

    def parse_page(
        self,
        document: RawFetch,
        *,
        reference: str,
        store: SourceStore,
        expected_query: str | None = None,
    ) -> tuple[CoopOnlineResultsPage, tuple[SourceProduct, ...]]:
        self._require_context(document, store)
        if document.http_status != 200 or "json" not in (document.content_type or "").casefold():
            raise CoopSchemaError("Coop online product page is not successful JSON")
        skip = self._request_integer(document, "skip")
        take = self._request_integer(document, "take")
        try:
            page = validated_results_page(
                document.json_payload(),
                requested_skip=skip,
                requested_take=take,
                expected_query=expected_query,
            )
        except (TypeError, ValueError) as exc:
            if isinstance(exc, CoopSchemaError):
                raise
            raise CoopSchemaError("Coop online product page JSON changed") from exc
        products = tuple(
            self.parse_product(
                row,
                store=store,
                reference=f"{reference}#results.items[{index}]",
                fetched_at=document.fetched_at,
            )
            for index, row in enumerate(page.items)
        )
        return page, products

    def parse_product(
        self,
        row: dict[str, Any],
        *,
        store: SourceStore,
        reference: str,
        fetched_at: datetime,
    ) -> SourceProduct:
        external_id = str(row.get("id") or "").strip()
        if not external_id:
            raise CoopSchemaError("Coop online product lacks stable id")
        name = " ".join(str(row.get("name") or "").split())
        if not name:
            raise CoopSchemaError("Coop online product lacks name")
        raw_ean = str(row.get("ean") or "").strip() or None
        gtin = raw_ean if _valid_gtin(raw_ean) else None
        base_price = _b2c_price(row.get("salesPriceData"))
        if base_price is None:
            raise CoopSchemaError("Coop online product lacks valid B2C sales price")
        price_price = _b2c_price(row.get("pricePriceData"))
        if price_price is not None and price_price != base_price:
            raise CoopSchemaError("Coop online base price fields conflict")
        package_quantity, package_unit = _package(row)
        source_sale_unit = str(row.get("salesUnit") or "").strip().casefold()
        sale_unit = _SALE_UNITS.get(source_sale_unit)
        if sale_unit is None:
            raise CoopSchemaError("Coop online product has unknown salesUnit")
        package_text = " ".join(str(row.get("packageSizeInformation") or "").split()) or None
        approximate_weight = "ungefärlig vikt" in (
            f"{row.get('packageSizeUnit') or ''} {package_text or ''}"
        ).casefold()
        average_weight_kg = (
            package_quantity / 1000
            if approximate_weight and package_quantity is not None and package_unit == "g"
            else None
        )
        comparison_price = _b2c_price(row.get("comparativePriceData"))
        comparison_unit = _comparison_unit(row) if comparison_price is not None else None
        # Dishwasher-cycle and drained-content qualifiers are real source
        # comparison facts, but neither is a verified purchase quantity unit.
        # Preserve them below without manufacturing kg/l/st semantics.
        exposed_comparison_price = comparison_price if comparison_unit is not None else None
        exposed_comparison_unit = comparison_unit if comparison_unit is not None else None
        offers = _active_offers(row, observed_at=fetched_at.astimezone(UTC))
        raw_promotion_price = _b2c_price(row.get("promotionPriceData"))

        def matches_product_promotion(offer: SourceOffer) -> bool:
            if offer.price == raw_promotion_price:
                return True
            return bool(
                approximate_weight
                and sale_unit == "kg"
                and _decimal(offer.source_payload.get("piece_price"))
                == raw_promotion_price
            )

        # A kg-rate promotion whose product-level price is only an estimated
        # piece total is actionable solely when the package itself explicitly
        # says it is an approximate-weight piece. Otherwise retain the raw
        # evidence and base rate, but withhold the uncertain offer from basket
        # maths.
        withheld_uncertain = [
            offer
            for offer in offers
            if sale_unit == "kg"
            and not approximate_weight
            and offer.type is not PromotionType.MULTIBUY
            and offer.price != raw_promotion_price
            and _decimal(offer.source_payload.get("piece_price")) == raw_promotion_price
        ]
        withheld_limits = [offer for offer in offers
                           if not offer.source_payload.get("purchase_limit_verified")]
        summary_verified = _verified_available_promotions(row)
        withheld_summary = list(offers) if not summary_verified else []
        exposed_offers = tuple(offer for offer in offers
                               if offer not in withheld_uncertain and offer not in withheld_limits
                               and offer not in withheld_summary)
        matching_unconditional = [offer for offer in exposed_offers
                                  if not offer.member_only
                                  and offer.type is not PromotionType.MULTIBUY
                                  and matches_product_promotion(offer)]
        sale_price = matching_unconditional[0].price if matching_unconditional else base_price
        fixed_member_prices = [
            offer.price
            for offer in exposed_offers
            if offer.member_only and offer.type is PromotionType.MEMBER_PRICE
            and matches_product_promotion(offer)
        ]
        member_price = fixed_member_prices[0] if fixed_member_prices else None
        available = row.get("availableOnline")
        if available is not None and not isinstance(available, bool):
            raise CoopSchemaError("Coop online availableOnline must be boolean")
        return SourceProduct(
            chain=Chain.COOP,
            store_external_id=store.external_id,
            external_product_id=external_id,
            gtin=gtin,
            name=name,
            brand=" ".join(str(row.get("manufacturerName") or "").split()) or None,
            category_path=_category_path(row),
            sale_price=sale_price,
            regular_price=base_price,
            member_price=member_price,
            comparison_price=exposed_comparison_price,
            comparison_unit=exposed_comparison_unit,
            package_text=package_text,
            package_quantity=package_quantity,
            package_unit=package_unit,
            sale_unit=sale_unit,
            offers=exposed_offers,
            availability=(
                "available" if available is True else "unavailable" if available is False else None
            ),
            average_weight_kg=average_weight_kg,
            # `Vikt` is a kg rate. An explicit approximate piece weight turns
            # it into one estimated-size purchasable package; a bare kg rate
            # remains freely sold by weight.
            basket_type="ST" if approximate_weight else "VIKT" if sale_unit == "kg" else "ST",
            raw_reference=reference,
            fetched_at=fetched_at,
            source_fields={
                "raw_ean": raw_ean,
                "available_online": available,
                "customer_group": "CUSTOMER_PRIVATE",
                "price_context_type": PriceContextType.ONLINE_FULFILLMENT.value,
                "price_semantics": "online_price",
                "sales_price_b2c": str(base_price),
                "price_price_b2c": str(price_price) if price_price is not None else None,
                "promotion_price_b2c": (
                    str(raw_promotion_price) if raw_promotion_price is not None else None
                ),
                "raw_comparative_price_b2c": (
                    str(comparison_price) if comparison_price is not None else None
                ),
                "raw_comparative_price_text": row.get("comparativePriceText"),
                "raw_comparative_price_unit": row.get("comparativePriceUnit"),
                "comparison_unit_verified": comparison_unit is not None,
                "active_promotion_ids": [offer.external_id for offer in offers],
                "available_promotion_types": row.get("availablePromotions"),
                "available_promotion_summary_verified": summary_verified,
                "withheld_summary_promotion_ids": [offer.external_id for offer in withheld_summary],
                "withheld_uncertain_promotion_ids": [
                    offer.external_id for offer in withheld_uncertain
                ],
                "withheld_unverified_limit_promotion_ids": [offer.external_id for offer in withheld_limits],
                "withheld_limit_reason": "purchase_limit_unverified" if withheld_limits else None,
                "withheld_promotion_reason": (
                    "weight_piece_semantics_unproven" if withheld_uncertain else None
                ),
                "package_size_unit": row.get("packageSizeUnit"),
                "package_approximate": approximate_weight,
                "sales_unit": row.get("salesUnit"),
            },
        )

    def parse_by_id(
        self,
        document: RawFetch,
        *,
        reference: str,
        store: SourceStore,
    ) -> tuple[SourceProduct, ...]:
        if document.kind != COOP_ONLINE_PRODUCT_BY_ID_KIND:
            raise CoopSchemaError("expected Coop by-id response")
        self._require_context(document, store)
        if document.http_status != 200 or "json" not in (document.content_type or "").casefold():
            raise CoopSchemaError("Coop by-id response is not successful JSON")
        try:
            payload = document.json_payload()
        except (TypeError, ValueError) as exc:
            raise CoopSchemaError("Coop by-id response is not valid JSON") from exc
        results = payload.get("results") if isinstance(payload, dict) else None
        if not isinstance(results, dict):
            raise CoopSchemaError("Coop by-id response lacks results")
        count = results.get("count")
        items = results.get("items")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or not isinstance(items, list)
            or len(items) != count
            or any(not isinstance(item, dict) for item in items)
        ):
            raise CoopSchemaError("Coop by-id result count does not reconcile")
        return tuple(
            self.parse_product(
                row,
                store=store,
                reference=f"{reference}#results.items[{index}]",
                fetched_at=document.fetched_at,
            )
            for index, row in enumerate(items)
        )

    def parse_promotion(
        self,
        document: RawFetch,
        *,
        reference: str,
        store: SourceStore,
    ) -> tuple[SourceProduct, ...]:
        if document.kind != COOP_ONLINE_PROMOTION_KIND:
            raise CoopSchemaError("expected Coop promotion response")
        _, products = self.parse_page(document, reference=reference, store=store)
        return products

    def reconcile_search(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> CoopOnlineCatalogReconciliation:
        documents = [
            (document, reference)
            for document, reference in raw.with_references(references)
            if document.kind == COOP_ONLINE_PRODUCT_SEARCH_KIND
        ]
        if not documents:
            raise CoopOnlineCompletenessError("Coop online search traversal has no pages")
        query_values = {document.query.get("search_query") for document, _ in documents}
        if len(query_values) != 1 or None in query_values:
            raise CoopOnlineCompletenessError("Coop online search pages have inconsistent query")
        return self._reconcile_partitions(
            documents,
            store=store,
            partition_field="search_query",
            expected_partitions={str(next(iter(query_values)))},
            expected_query=str(next(iter(query_values))),
        )

    def reconcile_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
        *,
        require_full_tree: bool = True,
    ) -> CoopOnlineCatalogReconciliation:
        pairs = raw.with_references(references)
        documents = [
            (document, reference)
            for document, reference in pairs
            if document.kind == COOP_ONLINE_CATEGORY_PAGE_KIND
        ]
        if not documents:
            raise CoopOnlineCompletenessError("Coop online catalog traversal has no pages")
        tree_documents = [
            document for document, _ in pairs if document.kind == COOP_ONLINE_CATEGORY_TREE_KIND
        ]
        if require_full_tree and len(tree_documents) != 1:
            raise CoopOnlineCompletenessError(
                "Coop full catalog requires exactly one saved category tree"
            )
        if tree_documents:
            expected_partitions = {
                code for code, _ in self.terminal_categories(tree_documents[0])
            }
        else:
            expected_partitions = {
                str(document.query.get("category_id") or "") for document, _ in documents
            }
        if "" in expected_partitions:
            raise CoopOnlineCompletenessError("Coop category page lacks category identity")
        return self._reconcile_partitions(
            documents,
            store=store,
            partition_field="category_id",
            expected_partitions=expected_partitions,
            expected_query=None,
        )

    def _reconcile_partitions(
        self,
        documents: list[tuple[RawFetch, str]],
        *,
        store: SourceStore,
        partition_field: str,
        expected_partitions: set[str],
        expected_query: str | None,
    ) -> CoopOnlineCatalogReconciliation:
        by_partition: dict[str, list[tuple[RawFetch, str]]] = defaultdict(list)
        for document, reference in documents:
            partition = str(document.query.get(partition_field) or "")
            if not partition:
                raise CoopOnlineCompletenessError(
                    f"Coop online page lacks {partition_field} request evidence"
                )
            by_partition[partition].append((document, reference))
        if set(by_partition) != expected_partitions:
            missing = sorted(expected_partitions - set(by_partition))
            unexpected = sorted(set(by_partition) - expected_partitions)
            raise CoopOnlineCompletenessError(
                f"Coop online category partitions differ: missing={missing}, unexpected={unexpected}"
            )

        unique: dict[str, tuple[str, int, SourceProduct, str]] = {}
        expected_products = 0
        raw_rows = 0
        pages_fetched = 0
        expected_pages = 0
        exact_duplicates = 0
        pagination_overlaps = 0
        cross_overlaps = 0
        for partition in sorted(by_partition):
            page_rows: list[tuple[CoopOnlineResultsPage, tuple[SourceProduct, ...]]] = []
            for document, reference in by_partition[partition]:
                try:
                    page_rows.append(
                        self.parse_page(
                            document,
                            reference=reference,
                            store=store,
                            expected_query=expected_query,
                        )
                    )
                except (CoopSchemaError, ValidationError, ValueError) as exc:
                    raise CoopOnlineCompletenessError(
                        f"Coop online partition {partition} failed: {exc}"
                    ) from exc
            counts = {page.reported_count for page, _ in page_rows}
            takes = {page.take for page, _ in page_rows}
            if len(counts) != 1 or len(takes) != 1:
                raise CoopOnlineCompletenessError(
                    f"Coop online partition {partition} changed count or page size"
                )
            count = next(iter(counts))
            take = next(iter(takes))
            expected_skips = tuple(range(0, count, take)) or (0,)
            actual_skips = tuple(sorted(page.skip for page, _ in page_rows))
            if actual_skips != expected_skips:
                raise CoopOnlineCompletenessError(
                    f"Coop online partition {partition} pagination is incomplete"
                )
            expected_products += count
            expected_pages += len(expected_skips)
            pages_fetched += len(page_rows)
            for page, products in sorted(page_rows, key=lambda item: item[0].skip):
                raw_rows += len(products)
                for product in products:
                    identity = product.external_product_id
                    assert identity is not None
                    fingerprint = _purchase_fingerprint(product)
                    prior = unique.get(identity)
                    if prior is None:
                        unique[identity] = (partition, page.page_index, product, fingerprint)
                        continue
                    prior_partition, prior_page, _, prior_fingerprint = prior
                    if prior_fingerprint != fingerprint:
                        raise CoopOnlineCompletenessError(
                            "Coop online duplicate conflicts for product "
                            f"{identity} ({prior_partition} vs {partition})"
                        )
                    if prior_partition == partition:
                        exact_duplicates += 1
                        if prior_page != page.page_index:
                            pagination_overlaps += 1
                    else:
                        cross_overlaps += 1

        duplicate_metrics = CoopOnlineDuplicateMetrics(
            exact_duplicates_removed=exact_duplicates,
            pagination_overlaps=pagination_overlaps,
            cross_category_overlaps=cross_overlaps,
            conflicting_duplicates=0,
        )
        products = tuple(value[2] for _, value in sorted(unique.items()))
        completion = CatalogCompletion(
            complete=True,
            expected_categories=len(expected_partitions),
            completed_categories=len(by_partition),
            pages_fetched=pages_fetched,
            products_observed=len(products),
            expected_products=expected_products,
            raw_rows=raw_rows,
            unique_products=len(products),
            duplicate_products=duplicate_metrics.duplicate_products,
            within_partition_duplicates=exact_duplicates,
            cross_partition_duplicates=cross_overlaps,
            exact_duplicates_removed=exact_duplicates,
            conflicting_duplicates=0,
            pagination_overlaps=pagination_overlaps,
            expected_pages=expected_pages,
        )
        return CoopOnlineCatalogReconciliation(
            products=products,
            duplicate_metrics=duplicate_metrics,
            completion=completion,
        )

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        try:
            reconciliation = self.reconcile_catalog(raw, references, store)
        except (CoopOnlineCompletenessError, CoopSchemaError, ValidationError, ValueError) as exc:
            reference = references[0] if references else "raw:coop-online-catalog"
            return ProductParseResult(
                failures=[
                    ParseFailure(
                        raw_record_reference=reference,
                        error_code="schema_changed",
                        error_message=str(exc)[:300],
                        parser_version=self.parser_version,
                    )
                ]
            )
        return ProductParseResult(products=list(reconciliation.products))
