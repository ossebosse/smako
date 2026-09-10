from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from grocery_data.app.domain import Chain, SaleModel
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    ProductModel,
    SessionFactory,
    SourceProductModel,
    StoreModel,
    session_scope,
)

_RECIPE_CATEGORY_MARKERS = (
    "bageri",
    "balj",
    "bröd",
    "chark",
    "fisk",
    "frukt",
    "fryst",
    "fågel",
    "grön",
    "kött",
    "mat",
    "mejeri",
    "ost",
    "pasta",
    "ris",
    "skafferi",
    "vegetar",
    "ägg",
)
_NON_RECIPE_MARKERS = (
    "barnmat",
    "blöjor",
    "djur",
    "hund",
    "hushåll",
    "hygien",
    "katt",
    "kläder",
    "kosmetik",
    "lek",
    "städ",
    "tobak",
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class UnknownPurchaseModelRow:
    name: str
    store: str | None
    category_path: tuple[str, ...]
    package_text: str | None
    sale_unit: str | None
    comparison_unit: str | None
    sale_price: Decimal | None
    canonical_food: str | None


def is_recipe_relevant(category_path: tuple[str, ...]) -> bool:
    """Broad diagnostic classification, never a product eligibility decision."""

    text = " ".join(category_path).casefold()
    if not text or any(marker in text for marker in _NON_RECIPE_MARKERS):
        return False
    return any(marker in text for marker in _RECIPE_CATEGORY_MARKERS)


def package_pattern(value: str | None) -> str:
    if not value or not value.strip():
        return "(missing)"
    normalized = _SPACE.sub(" ", value.strip().casefold())
    return _NUMBER.sub("<n>", normalized)


def _percent(part: int, whole: int) -> Decimal:
    if whole == 0:
        return Decimal("0.00")
    return (Decimal(part) * Decimal(100) / Decimal(whole)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _top(counter: Counter[str], limit: int) -> list[dict[str, object]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


class PurchaseModelAnalyzer:
    def __init__(self, session_factory: SessionFactory) -> None:
        self._session_factory = session_factory

    def analyze(
        self,
        chain: Chain,
        *,
        snapshot: str = "active",
        top_limit: int = 20,
        sample_limit: int = 20,
    ) -> dict[str, object]:
        with session_scope(self._session_factory) as session:
            if snapshot == "active":
                snapshot_ids = list(
                    session.scalars(
                        select(CatalogSnapshotModel.id).where(
                            CatalogSnapshotModel.chain == chain.value,
                            CatalogSnapshotModel.is_active.is_(True),
                            CatalogSnapshotModel.state == "promoted",
                        )
                    )
                )
            else:
                row = session.get(CatalogSnapshotModel, snapshot)
                if row is None or row.chain != chain.value:
                    raise ValueError("snapshot was not found for the requested chain")
                snapshot_ids = [row.id]

            if not snapshot_ids:
                raise ValueError("no active promoted snapshot exists for the requested chain")

            rows = session.execute(
                select(ProductModel, SourceProductModel, StoreModel.name)
                .join(
                    SourceProductModel,
                    SourceProductModel.id == ProductModel.source_product_id,
                )
                .outerjoin(StoreModel, StoreModel.id == ProductModel.store_id)
                .where(ProductModel.catalog_snapshot_id.in_(snapshot_ids))
                .order_by(ProductModel.name, ProductModel.id)
            ).all()

        total = len(rows)
        unknown_rows: list[UnknownPurchaseModelRow] = []
        recipe_unknown_rows: list[UnknownPurchaseModelRow] = []
        recipe_total = 0
        recipe_unknown = 0
        for product, source, store_name in rows:
            category_path = tuple(product.category_path or ())
            relevant = is_recipe_relevant(category_path)
            recipe_total += int(relevant)
            if product.sale_model != SaleModel.UNKNOWN.value:
                continue
            recipe_unknown += int(relevant)
            unknown_row = UnknownPurchaseModelRow(
                name=product.name,
                store=store_name,
                category_path=category_path,
                package_text=source.package_text,
                sale_unit=source.sale_unit,
                comparison_unit=source.comparison_unit,
                sale_price=source.sale_price,
                canonical_food=product.canonical_food,
            )
            unknown_rows.append(unknown_row)
            if relevant:
                recipe_unknown_rows.append(unknown_row)

        category_counts: Counter[str] = Counter()
        package_counts: Counter[str] = Counter()
        sale_unit_counts: Counter[str] = Counter()
        comparison_unit_counts: Counter[str] = Counter()
        for row in unknown_rows:
            category_counts[row.category_path[-1] if row.category_path else "(missing)"] += 1
            package_counts[package_pattern(row.package_text)] += 1
            sale_unit_counts[row.sale_unit or "(missing)"] += 1
            comparison_unit_counts[row.comparison_unit or "(missing)"] += 1

        def sample(rows: list[UnknownPurchaseModelRow]) -> list[dict[str, object]]:
            return [
                {
                    "name": row.name,
                    "store": row.store,
                    "category_path": list(row.category_path),
                    "package_text": row.package_text,
                    "sale_unit": row.sale_unit,
                    "comparison_unit": row.comparison_unit,
                    "sale_price": row.sale_price,
                    "canonical_food": row.canonical_food,
                }
                for row in rows[:sample_limit]
            ]

        recipe_categories: Counter[str] = Counter(
            row.category_path[-1] if row.category_path else "(missing)"
            for row in recipe_unknown_rows
        )
        recipe_packages: Counter[str] = Counter(
            package_pattern(row.package_text) for row in recipe_unknown_rows
        )
        return {
            "chain": chain.value,
            "snapshot": snapshot,
            "snapshot_ids": snapshot_ids,
            "total_products": total,
            "unknown_products": len(unknown_rows),
            "unknown_percent": _percent(len(unknown_rows), total),
            "resolved_percent": _percent(total - len(unknown_rows), total),
            "recipe_relevant": {
                "total_products": recipe_total,
                "unknown_products": recipe_unknown,
                "unknown_percent": _percent(recipe_unknown, recipe_total),
                "resolved_percent": _percent(recipe_total - recipe_unknown, recipe_total),
                "classification": "broad category diagnostic only",
                "top_categories": _top(recipe_categories, top_limit),
                "top_package_patterns": _top(recipe_packages, top_limit),
                "representative_products": sample(recipe_unknown_rows),
            },
            "top_categories": _top(category_counts, top_limit),
            "top_package_patterns": _top(package_counts, top_limit),
            "top_sale_units": _top(sale_unit_counts, top_limit),
            "top_comparison_units": _top(comparison_unit_counts, top_limit),
            "representative_products": sample(unknown_rows),
        }
