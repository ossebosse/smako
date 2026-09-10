from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from grocery_data.app.connectors.coop.models import (
    CoopSchemaError,
    product_json_ld,
    source_id_from_product_url,
)
from grocery_data.app.connectors.coop.online_models import (
    CoopOnlineCaptureContext,
    CoopOnlineCaptureSurface,
    CoopOnlineCategoryCapture,
    CoopOnlineContextEvidence,
    CoopOnlineContextIdVerification,
    CoopOnlineContextKind,
    CoopOnlineProductDetailObservation,
    CoopOnlineProductDetailSampleEnvelope,
)
from grocery_data.app.domain import Chain, RawFetch

COOP_ONLINE_CATEGORY_CAPTURE_KIND = "coop_online_category_capture"
COOP_ONLINE_PRODUCT_DETAIL_KIND = "coop_online_product_detail"
COOP_ONLINE_PRODUCT_DETAIL_SAMPLE_KIND = "coop_online_product_detail_sample"
COOP_ONLINE_ACCESS_CHALLENGE_KIND = "coop_online_access_challenge"

_GTIN = re.compile(r"(?:\d{8}|\d{12,14})")
_UNIT_CODES: dict[str, tuple[Decimal, str]] = {
    "GRM": (Decimal(1), "g"),
    "KGM": (Decimal(1000), "g"),
    "MLT": (Decimal(1), "ml"),
    "LTR": (Decimal(1000), "ml"),
    "C62": (Decimal(1), "st"),
    "H87": (Decimal(1), "st"),
}


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and result > 0 else None


def _brand(value: object) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    return str(value or "").strip() or None


def _category(value: object) -> tuple[str, ...]:
    if isinstance(value, list):
        values = [unescape(str(item)).strip() for item in value]
        return tuple(item for item in values if item)
    text = unescape(str(value or "")).strip()
    return tuple(part.strip() for part in text.split(">") if part.strip())


def _single_offer(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        offers = [item for item in value if isinstance(item, dict)]
        if len(offers) == 1:
            return offers[0]
    return {}


def _quantity(value: object) -> tuple[Decimal | None, str | None]:
    if not isinstance(value, dict):
        return None, None
    amount = _decimal(value.get("value"))
    conversion = _UNIT_CODES.get(str(value.get("unitCode") or "").strip().upper())
    if amount is None or conversion is None:
        return None, None
    factor, unit = conversion
    return amount * factor, unit


class CoopOnlineDiagnosticParser:
    """Offline-only parser for sanitized Coop online discovery evidence."""

    parser_version = "coop-online-diagnostic-parser-v1"

    @staticmethod
    def _require_document(document: RawFetch, *, kind: str) -> None:
        if document.chain != Chain.COOP:
            raise CoopSchemaError("Coop online diagnostic received another chain")
        if document.kind != kind:
            raise CoopSchemaError(
                f"expected Coop online diagnostic kind {kind!r}, got {document.kind!r}"
            )
        if document.http_status != 200:
            raise CoopSchemaError(
                f"Coop online diagnostic expected HTTP 200, got {document.http_status}"
            )

    def parse_category_capture(self, document: RawFetch) -> CoopOnlineCategoryCapture:
        self._require_document(document, kind=COOP_ONLINE_CATEGORY_CAPTURE_KIND)
        if "json" not in (document.content_type or "").casefold():
            raise CoopSchemaError("Coop online category capture must be sanitized JSON")
        try:
            return CoopOnlineCategoryCapture.model_validate_json(document.payload)
        except (ValidationError, ValueError) as exc:
            raise CoopSchemaError("Coop online category capture schema changed") from exc

    @staticmethod
    def normalize_context(context: CoopOnlineCaptureContext) -> CoopOnlineContextEvidence:
        # ``visible_selected_context`` proves the selected label, not the
        # frontend's online production-unit identity. A non-null future value
        # still needs a stronger evidence profile before it may become VERIFIED.
        return CoopOnlineContextEvidence(
            kind=CoopOnlineContextKind.ONLINE_FULFILLMENT,
            fulfillment_mode=context.fulfillment_mode,
            selected_label=context.label,
            external_online_context_id=context.external_context_id,
            external_context_id_verification=CoopOnlineContextIdVerification.UNVERIFIED,
            physical_store_external_id=context.physical_store_external_id,
        )

    def context_evidence(self, capture: CoopOnlineCategoryCapture) -> CoopOnlineContextEvidence:
        return self.normalize_context(capture.context)

    @staticmethod
    def require_context_identity(
        document: RawFetch,
        context: CoopOnlineContextEvidence,
    ) -> None:
        if context.external_context_id_verification != CoopOnlineContextIdVerification.VERIFIED:
            if document.store_external_id is not None:
                raise CoopSchemaError(
                    "physical store ID must not be persisted as online fulfillment identity"
                )
            return
        if document.store_external_id != context.external_online_context_id:
            raise CoopSchemaError("Coop online raw store identity disagrees with verified context")

    @staticmethod
    def _product_observation(
        row: dict[str, Any],
        *,
        reference: str,
        context: CoopOnlineContextEvidence,
        source_url: str,
        offer_key: str,
    ) -> CoopOnlineProductDetailObservation:
        parsed_url = urlsplit(source_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname != "www.coop.se"
            or not parsed_url.path.startswith("/handla/varor/")
        ):
            raise CoopSchemaError("Coop online product detail URL is not an official product path")
        name = str(row.get("name") or "").strip()
        if not name:
            raise CoopSchemaError("Coop online JSON-LD Product is missing name")

        explicit_gtins = {
            str(value).strip()
            for value in (row.get("gtin13"), row.get("gtin"))
            if value is not None and _GTIN.fullmatch(str(value).strip())
        }
        if len(explicit_gtins) > 1:
            raise CoopSchemaError("Coop online JSON-LD Product GTIN fields conflict")
        gtin = next(iter(explicit_gtins), None)

        sku = str(row.get("sku") or "").strip() or None
        url_source_id = source_id_from_product_url(parsed_url.path)
        external_product_id = sku or url_source_id
        if external_product_id is None:
            raise CoopSchemaError("Coop online JSON-LD Product has no source identity")

        offer = _single_offer(row.get(offer_key))
        sale_price = _decimal(offer.get("price"))
        currency = str(offer.get("priceCurrency") or "").strip().upper() or None
        if sale_price is not None and currency != "SEK":
            raise CoopSchemaError("Coop online JSON-LD price is not explicitly SEK")
        package_quantity, package_unit = _quantity(row.get("size"))
        availability = str(offer.get("availability") or "").rstrip("/").rsplit("/", 1)[-1]
        context_verified = (
            context.external_context_id_verification == CoopOnlineContextIdVerification.VERIFIED
            and context.external_online_context_id is not None
        )
        return CoopOnlineProductDetailObservation(
            context=context,
            surface=CoopOnlineCaptureSurface.PRODUCT_DETAIL_JSON_LD,
            external_product_id=external_product_id,
            url_source_id=url_source_id,
            gtin=gtin,
            gtin_evidence="explicit_jsonld" if gtin is not None else None,
            name=name,
            brand=_brand(row.get("brand")),
            category_path=_category(row.get("category")),
            package_quantity=package_quantity,
            package_unit=package_unit,
            sale_price=sale_price,
            price_currency=currency,
            availability=availability or None,
            price_context_verified=context_verified,
            raw_reference=reference,
            source_url=source_url,
        )

    def parse_product_detail(
        self,
        document: RawFetch,
        *,
        reference: str,
        context: CoopOnlineContextEvidence,
    ) -> CoopOnlineProductDetailObservation:
        self._require_document(document, kind=COOP_ONLINE_PRODUCT_DETAIL_KIND)
        self.require_context_identity(document, context)
        row = product_json_ld(document.payload)
        return self._product_observation(
            row,
            reference=reference,
            context=context,
            source_url=document.url,
            offer_key="offers",
        )

    def parse_product_detail_sample(
        self,
        document: RawFetch,
        *,
        reference: str,
    ) -> tuple[CoopOnlineContextEvidence, tuple[CoopOnlineProductDetailObservation, ...]]:
        self._require_document(document, kind=COOP_ONLINE_PRODUCT_DETAIL_SAMPLE_KIND)
        if "json" not in (document.content_type or "").casefold():
            raise CoopSchemaError("Coop online product detail sample must be sanitized JSON")
        try:
            envelope = CoopOnlineProductDetailSampleEnvelope.model_validate_json(document.payload)
        except (ValidationError, ValueError) as exc:
            raise CoopSchemaError("Coop online product detail sample schema changed") from exc
        context = self.normalize_context(envelope.context)
        self.require_context_identity(document, context)
        observations: list[CoopOnlineProductDetailObservation] = []
        for position, sample in enumerate(envelope.samples):
            if sample.challenge:
                raise CoopSchemaError("ACCESS_CHALLENGE in Coop online product detail sample")
            row = sample.products[0].model_dump(by_alias=True)
            # The sanitized sample calls this singular object ``offer``.
            observations.append(
                self._product_observation(
                    row,
                    reference=f"{reference}#sample[{position}]",
                    context=context,
                    source_url=f"https://www.coop.se{sample.product_path}",
                    offer_key="offer",
                )
            )
        return context, tuple(observations)
