from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from grocery_data.app.connectors.hemkop.models import (
    HemkopSchemaError,
    top_level_category_paths,
    validated_catalog_page,
)
from grocery_data.app.connectors.willys.parser import (
    WillysParser,
    parse_drained_quantity,
    parse_package_text,
)
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ParseFailure,
    PriceContextType,
    ProductParseResult,
    RawBatch,
    SourceProduct,
    SourceStore,
)


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


class HemkopParser:
    """Hemköp adapter over the verified identical Axfood product primitives.

    Transport, pagination and store-context semantics remain Hemköp-local.
    Only the observed product/package/promotion field mapping is reused from
    the Willys reference parser.  Every emitted identity and lineage version is
    rewritten to Hemköp before leaving this adapter.
    """

    parser_version = "hemkop-parser-v1"

    def __init__(self, *, accept_sales_price_object: bool = True) -> None:
        self._axfood_products = WillysParser(
            accept_sales_price_object=accept_sales_price_object
        )

    @staticmethod
    def top_level_category_paths(tree_fetch: bytes) -> tuple[str, ...]:
        return top_level_category_paths(tree_fetch)

    @staticmethod
    def category_top_level_paths(tree_fetch: bytes) -> tuple[str, ...]:
        """Compatibility alias with an explicit partition-oriented name."""

        return top_level_category_paths(tree_fetch)

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
        *,
        filter_locality: bool = True,
    ) -> list[SourceStore]:
        if len(raw.documents) != len(references):
            raise ValueError("raw references must align with documents")
        stores: dict[str, SourceStore] = {}
        city = area.city.casefold()
        for document, reference in zip(raw.documents, references, strict=True):
            if document.kind != "stores" or document.http_status != 200:
                continue
            try:
                payload = document.json_payload()
            except (TypeError, ValueError):
                continue
            if not isinstance(payload, list):
                continue
            for row in payload:
                if not isinstance(row, dict):
                    continue
                address = row.get("address") if isinstance(row.get("address"), dict) else {}
                name = str(row.get("name") or "").strip()
                town = str(address.get("town") or "").strip()
                town_key = town.casefold()
                name_has_city = re.search(
                    rf"(?<!\w){re.escape(city)}(?!\w)",
                    name.casefold(),
                )
                if filter_locality and ((town_key and town_key != city) or (
                    not town_key and not name_has_city
                )):
                    continue
                external_id = str(row.get("storeId") or "").strip()
                if not external_id or not name:
                    continue
                geo_point = row.get("geoPoint") if isinstance(row.get("geoPoint"), dict) else {}
                latitude = _decimal(address.get("latitude") or geo_point.get("latitude"))
                longitude = _decimal(address.get("longitude") or geo_point.get("longitude"))
                online_value = row.get("onlineStore")
                online_shopping = (
                    online_value
                    if isinstance(online_value, bool)
                    else str(online_value).strip().casefold() == "true"
                    if online_value is not None
                    else None
                )
                stores[external_id] = SourceStore(
                    chain=Chain.HEMKOP,
                    external_id=external_id,
                    name=name,
                    address=str(address.get("line1") or "").strip() or None,
                    postal_code=str(address.get("postalCode") or "").strip() or None,
                    city=town or None,
                    latitude=latitude,
                    longitude=longitude,
                    online_shopping=online_shopping,
                    coverage=(
                        CoverageLevel.FULL_ONLINE_CATALOG
                        if online_shopping is True
                        else CoverageLevel.PARTIAL_CATALOG
                    ),
                    price_context_type=(
                        PriceContextType.ONLINE_STORE if online_shopping is True else None
                    ),
                    physical_store_external_id=(
                        external_id if online_shopping is True else None
                    ),
                    raw_reference=f"{reference}#storeId={external_id}",
                    source_fields={
                        "coordinate_source": {"url": document.url,
                            "sha256": document.payload_hash,
                            "observed_at": document.fetched_at.isoformat()},
                        "flyer_url": row.get("flyerURL"),
                        "external": row.get("external"),
                        "clickAndCollect": row.get("clickAndCollect"),
                        "price_context": "activated_online_store"
                        if online_shopping is True
                        else None,
                        # Store discovery describes capability, not a verified
                        # price session.  The client must activate and read back
                        # this exact identity before any catalog page is fetched.
                        "price_context_activation_required": online_shopping is True,
                        "price_context_verified": False,
                    },
                )
        return sorted(stores.values(), key=lambda store: (store.name.casefold(), store.external_id))

    @staticmethod
    def _hemkop_product(
        product: SourceProduct,
        *,
        activation_confirmed: bool = False,
    ) -> SourceProduct:
        return product.model_copy(
            update={
                "chain": Chain.HEMKOP,
                "source_fields": {
                    **product.source_fields,
                    "price_context_activation_confirmed": activation_confirmed,
                },
            }
        )

    @staticmethod
    def _contains_store_id(value: object, expected: str) -> bool:
        if isinstance(value, dict):
            if str(value.get("storeId") or "") == expected:
                return True
            return any(
                HemkopParser._contains_store_id(child, expected) for child in value.values()
            )
        if isinstance(value, list):
            return any(HemkopParser._contains_store_id(child, expected) for child in value)
        return False

    def _parse_product(self, *args: object, **kwargs: object) -> SourceProduct:
        """Expose the verified product primitive for targeted repair tests."""

        product = self._axfood_products._parse_product(*args, **kwargs)
        return self._hemkop_product(product)

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        if len(raw.documents) != len(references):
            raise ValueError("raw references must align with documents")
        products: dict[str, SourceProduct] = {}
        failures: list[ParseFailure] = []
        activation_confirmed = False
        for document in raw.documents:
            if document.kind != "store_context" or document.http_status != 200:
                continue
            if document.store_external_id != store.external_id:
                continue
            try:
                context_payload = document.json_payload()
            except (TypeError, ValueError):
                continue
            if self._contains_store_id(context_payload, store.external_id):
                activation_confirmed = True
                break
        catalog_references = [
            reference
            for document, reference in zip(raw.documents, references, strict=True)
            if document.kind == "catalog_page"
        ]
        if catalog_references and not activation_confirmed:
            return ProductParseResult(
                products=[],
                failures=[
                    ParseFailure(
                        raw_record_reference=catalog_references[0],
                        error_code="price_context_unverified",
                        error_message=(
                            "catalog batch lacks a matching saved Hemköp "
                            "store-activation readback"
                        ),
                        parser_version=self.parser_version,
                        sample={"store_external_id": store.external_id},
                    )
                ],
            )
        for document, reference in zip(raw.documents, references, strict=True):
            if document.kind not in {"catalog_page", "product_detail"}:
                continue
            if document.http_status != 200:
                failures.append(
                    ParseFailure(
                        raw_record_reference=reference,
                        error_code="schema_changed",
                        error_message=f"unexpected HTTP status {document.http_status}",
                        parser_version=self.parser_version,
                    )
                )
                continue
            if document.kind == "catalog_page":
                try:
                    payload = document.json_payload()
                    validated_catalog_page(
                        payload,
                        requested_page=document.page_number,
                        expected_store_id=store.external_id,
                    )
                except (HemkopSchemaError, TypeError, ValueError) as exc:
                    failures.append(
                        ParseFailure(
                            raw_record_reference=reference,
                            error_code="schema_changed",
                            error_message=str(exc)[:300],
                            parser_version=self.parser_version,
                        )
                    )
                    continue

            delegated = self._axfood_products.parse_catalog(
                RawBatch(chain=Chain.HEMKOP, documents=(document,)),
                [reference],
                store,
            )
            failures.extend(
                failure.model_copy(update={"parser_version": self.parser_version})
                for failure in delegated.failures
            )
            for source in delegated.products:
                parsed = self._hemkop_product(
                    source,
                    activation_confirmed=activation_confirmed,
                )
                product_id = parsed.external_product_id or ""
                existing = products.get(product_id)
                if existing is not None and existing.gtin and not parsed.gtin:
                    continue
                products[product_id] = parsed
        return ProductParseResult(products=list(products.values()), failures=failures)


__all__ = [
    "HemkopParser",
    "parse_drained_quantity",
    "parse_package_text",
]
