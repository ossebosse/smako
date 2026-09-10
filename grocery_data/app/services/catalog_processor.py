from __future__ import annotations

from dataclasses import dataclass

from grocery_data.app.connectors.base import GroceryConnector
from grocery_data.app.domain import (
    CanonicalProduct,
    ParseFailure,
    ProductParseResult,
    RawBatch,
    RunMetrics,
    SaleModel,
    SourceProduct,
    SourceStore,
)
from grocery_data.app.monitoring import PriceSanityClassification, check_price_sanity
from grocery_data.app.normalization import ProductNormalizer


@dataclass(frozen=True, slots=True)
class ProcessedProduct:
    source: SourceProduct
    canonical: CanonicalProduct


@dataclass(frozen=True, slots=True)
class ProcessedCatalog:
    products: tuple[ProcessedProduct, ...]
    failures: tuple[ParseFailure, ...]
    metrics: RunMetrics
    warnings: tuple[str, ...]


class CatalogProcessor:
    def __init__(self, normalizer: ProductNormalizer | None = None) -> None:
        self.normalizer = normalizer or ProductNormalizer()

    def process(
        self,
        connector: GroceryConnector,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProcessedCatalog:
        parsed: ProductParseResult = connector.parse_catalog(raw, references, store)
        products: list[ProcessedProduct] = []
        failures = list(parsed.failures)
        warnings: list[str] = []
        for source in parsed.products:
            try:
                canonical = self.normalizer.normalize(
                    source,
                    parser_version=connector.parser_version,
                )
            except (TypeError, ValueError) as exc:
                failures.append(
                    ParseFailure(
                        raw_record_reference=source.raw_reference,
                        error_code="unknown_package_format",
                        error_message=str(exc)[:300],
                        parser_version=connector.parser_version,
                        sample={
                            "external_product_id": source.external_product_id,
                            "name": source.name,
                            "package_text": source.package_text,
                        },
                    )
                )
                continue
            sanity = check_price_sanity(
                canonical.sale_price,
                unit_price=canonical.unit_price,
            )
            if sanity.classification == PriceSanityClassification.QUARANTINE:
                failures.append(
                    ParseFailure(
                        raw_record_reference=source.raw_reference,
                        error_code="invalid_price",
                        error_message="; ".join(issue.message for issue in sanity.issues),
                        parser_version=connector.parser_version,
                        sample={
                            "external_product_id": source.external_product_id,
                            "name": source.name,
                        },
                    )
                )
                continue
            if sanity.classification == PriceSanityClassification.WARNING:
                warnings.extend(
                    f"{source.external_product_id or source.name}: {issue.message}"
                    for issue in sanity.issues
                )
            products.append(ProcessedProduct(source=source, canonical=canonical))

        if len(warnings) > 10:
            omitted = len(warnings) - 10
            warnings = [*warnings[:10], f"{omitted} additional product warnings omitted"]

        metrics = RunMetrics(
            products_fetched=len(parsed.products) + len(parsed.failures),
            products_parsed=len(products),
            products_quarantined=len(failures),
            products_with_price=sum(
                product.canonical.sale_price is not None
                or any(offer.price is not None for offer in product.source.offers)
                for product in products
            ),
            products_with_gtin=sum(bool(product.canonical.gtin) for product in products),
            products_with_package_quantity=sum(
                product.canonical.package_quantity is not None for product in products
            ),
            unknown_sale_model=sum(
                product.canonical.sale_model == SaleModel.UNKNOWN for product in products
            ),
            request_count=raw.transport.request_count or len(raw.documents),
            http_error_count=(
                raw.transport.http_error_count
                or sum(document.http_status >= 400 for document in raw.documents)
            ),
            rate_limit_count=(
                raw.transport.rate_limit_count
                or sum(document.http_status == 429 for document in raw.documents)
            ),
        )
        return ProcessedCatalog(
            products=tuple(products),
            failures=tuple(failures),
            metrics=metrics,
            warnings=tuple(warnings),
        )
