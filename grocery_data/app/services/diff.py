from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain import CanonicalProduct


class SnapshotDiff(BaseModel):
    model_config = ConfigDict(frozen=True)

    old_products: int = Field(ge=0)
    new_products: int = Field(ge=0)
    shared_products: int = Field(default=0, ge=0)
    price_changed_products: int = Field(default=0, ge=0)
    added_product_keys: tuple[str, ...]
    removed_product_keys: tuple[str, ...]
    price_changed_keys: tuple[str, ...]
    old_missing_package_rate: float = Field(ge=0, le=1)
    new_missing_package_rate: float = Field(ge=0, le=1)
    old_parser_failures: int = Field(default=0, ge=0)
    new_parser_failures: int = Field(default=0, ge=0)
    old_gtin_coverage: float = Field(default=0, ge=0, le=1)
    new_gtin_coverage: float = Field(default=0, ge=0, le=1)
    old_price_coverage: float = Field(default=0, ge=0, le=1)
    new_price_coverage: float = Field(default=0, ge=0, le=1)
    old_package_quantity_coverage: float = Field(default=0, ge=0, le=1)
    new_package_quantity_coverage: float = Field(default=0, ge=0, le=1)
    warnings: tuple[str, ...] = ()


def _identity(product: CanonicalProduct) -> str:
    store_prefix = f"{product.chain.value}:{product.store_external_id}"
    if product.gtin:
        return f"{store_prefix}:gtin:{product.gtin}"
    if product.external_product_id:
        return f"{store_prefix}:source:{product.external_product_id}"
    return f"{store_prefix}:key:{product.source_product_key}"


def _variant_signature(product: CanonicalProduct) -> str:
    """Identify unresolved duplicate variants without volatile replay lineage.

    Source pages such as physical-store offers can expose several different
    groups with the same conservative source key and no GTIN/source ID. A plain
    dict would silently collapse those rows and could report false price
    changes depending on database iteration order.
    """

    payload = product.model_dump(
        mode="json",
        exclude={
            "observed_at",
            "raw_reference",
            "parser_version",
            "normalizer_version",
        },
    )
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _bucket(products: list[CanonicalProduct]) -> dict[str, list[CanonicalProduct]]:
    result: dict[str, list[CanonicalProduct]] = defaultdict(list)
    for product in products:
        result[_identity(product)].append(product)
    return dict(result)


def _index_bucket(
    base_key: str,
    products: list[CanonicalProduct],
    *,
    distinguish_variants: bool,
) -> dict[str, CanonicalProduct]:
    if not distinguish_variants:
        return {base_key: products[0]}
    signatures: dict[str, list[CanonicalProduct]] = defaultdict(list)
    for product in products:
        signatures[_variant_signature(product)].append(product)
    indexed: dict[str, CanonicalProduct] = {}
    for signature, variants in sorted(signatures.items()):
        for occurrence, product in enumerate(variants, start=1):
            indexed[f"{base_key}:variant:{signature[:16]}:{occurrence}"] = product
    return indexed


def _missing_package_rate(products: list[CanonicalProduct]) -> float:
    if not products:
        return 1.0
    missing = sum(
        product.package_quantity is None
        and product.sale_model.value not in {"sold_by_weight", "sold_by_piece"}
        for product in products
    )
    return missing / len(products)


def _coverage(products: list[CanonicalProduct], field: str) -> float:
    if not products:
        return 0.0
    present = sum(getattr(product, field) is not None for product in products)
    return present / len(products)


class SnapshotDiffer:
    def compare(
        self,
        old: list[CanonicalProduct],
        new: list[CanonicalProduct],
        *,
        old_parser_failures: int = 0,
        new_parser_failures: int = 0,
    ) -> SnapshotDiff:
        old_buckets = _bucket(old)
        new_buckets = _bucket(new)
        old_by_key: dict[str, CanonicalProduct] = {}
        new_by_key: dict[str, CanonicalProduct] = {}
        for base_key in old_buckets.keys() | new_buckets.keys():
            old_bucket = old_buckets.get(base_key, [])
            new_bucket = new_buckets.get(base_key, [])
            distinguish_variants = max(len(old_bucket), len(new_bucket)) > 1
            if old_bucket:
                old_by_key.update(
                    _index_bucket(
                        base_key,
                        old_bucket,
                        distinguish_variants=distinguish_variants,
                    )
                )
            if new_bucket:
                new_by_key.update(
                    _index_bucket(
                        base_key,
                        new_bucket,
                        distinguish_variants=distinguish_variants,
                    )
                )
        shared = old_by_key.keys() & new_by_key.keys()
        price_changed = tuple(
            sorted(
                key for key in shared if old_by_key[key].sale_price != new_by_key[key].sale_price
            )
        )
        old_missing = _missing_package_rate(old)
        new_missing = _missing_package_rate(new)
        old_gtin_coverage = _coverage(old, "gtin")
        new_gtin_coverage = _coverage(new, "gtin")
        old_price_coverage = _coverage(old, "sale_price")
        new_price_coverage = _coverage(new, "sale_price")
        old_package_coverage = _coverage(old, "package_quantity")
        new_package_coverage = _coverage(new, "package_quantity")
        warnings: list[str] = []
        if new_missing - old_missing > 0.1:
            warnings.append("missing package quantity increased by more than 10 percentage points")
        if old and len(new) < len(old) * 0.7:
            warnings.append("product count dropped by more than 30 percent")
        if old_gtin_coverage - new_gtin_coverage > 0.1:
            warnings.append("GTIN coverage dropped by more than 10 percentage points")
        if old_price_coverage - new_price_coverage > 0.1:
            warnings.append("price coverage dropped by more than 10 percentage points")
        if new_parser_failures > old_parser_failures:
            warnings.append(
                f"parser failures increased from {old_parser_failures} to {new_parser_failures}"
            )
        return SnapshotDiff(
            old_products=len(old),
            new_products=len(new),
            shared_products=len(shared),
            price_changed_products=len(price_changed),
            added_product_keys=tuple(sorted(new_by_key.keys() - old_by_key.keys())),
            removed_product_keys=tuple(sorted(old_by_key.keys() - new_by_key.keys())),
            price_changed_keys=price_changed,
            old_missing_package_rate=old_missing,
            new_missing_package_rate=new_missing,
            old_parser_failures=old_parser_failures,
            new_parser_failures=new_parser_failures,
            old_gtin_coverage=old_gtin_coverage,
            new_gtin_coverage=new_gtin_coverage,
            old_price_coverage=old_price_coverage,
            new_price_coverage=new_price_coverage,
            old_package_quantity_coverage=old_package_coverage,
            new_package_quantity_coverage=new_package_coverage,
            warnings=tuple(warnings),
        )
