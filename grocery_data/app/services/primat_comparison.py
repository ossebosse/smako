from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ComparisonSource = Literal["own", "primat"]
JoinMethod = Literal["gtin", "external_product_id", "normalized_product"]


class ComparisonRecord(BaseModel):
    """Small, source-neutral projection used only for diagnostic comparison.

    The projection intentionally does not infer physical package quantity from a
    comparison price. Missing source facts remain ``None``.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    source: ComparisonSource
    gtin: str | None = None
    external_product_id: str | None = None
    chain: str | None = None
    store_ids: tuple[str, ...] = ()
    name: str
    brand: str | None = None
    sale_price: Decimal | None = Field(default=None, gt=0)
    regular_price: Decimal | None = Field(default=None, gt=0)
    comparison_price: Decimal | None = Field(default=None, gt=0)
    comparison_unit: str | None = None
    package_quantity: Decimal | None = Field(default=None, gt=0)
    package_unit: str | None = None
    package_text: str | None = None
    sale_model: str | None = None
    promotion_signatures: tuple[str, ...] = ()


class DifferenceSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    join_method: JoinMethod
    identity: str
    own_name: str
    primat_name: str
    differing_fields: dict[str, dict[str, str | None]]


class ProductSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: str
    name: str
    brand: str | None = None
    package: str | None = None


class PrimatComparisonReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_version: str = "grocery-compare-v1"
    store: str
    own_products: int = Field(ge=0)
    primat_products: int = Field(ge=0)
    own_with_gtin: int = Field(ge=0)
    primat_with_gtin: int = Field(ge=0)
    own_with_price: int = Field(ge=0)
    primat_with_price: int = Field(ge=0)
    own_with_explicit_package: int = Field(ge=0)
    primat_with_explicit_package: int = Field(ge=0)
    matched_products: int = Field(ge=0)
    matched_by_gtin: int = Field(ge=0)
    matched_by_external_product_id: int = Field(ge=0)
    matched_by_normalized_product: int = Field(ge=0)
    ambiguous_join_keys: int = Field(ge=0)
    same_price: int = Field(ge=0)
    price_differs: int = Field(ge=0)
    price_not_comparable: int = Field(ge=0)
    same_regular_price: int = Field(ge=0)
    regular_price_differs: int = Field(ge=0)
    regular_price_not_comparable: int = Field(ge=0)
    same_package: int = Field(ge=0)
    package_differs: int = Field(ge=0)
    package_not_comparable: int = Field(ge=0)
    same_comparison_price: int = Field(ge=0)
    comparison_price_differs: int = Field(ge=0)
    comparison_price_not_comparable: int = Field(ge=0)
    same_sale_model: int = Field(ge=0)
    sale_model_differs: int = Field(ge=0)
    sale_model_not_comparable: int = Field(ge=0)
    same_promotions: int = Field(ge=0)
    promotions_differ: int = Field(ge=0)
    only_own: int = Field(ge=0)
    only_primat: int = Field(ge=0)
    difference_samples: tuple[DifferenceSample, ...] = ()
    only_own_samples: tuple[ProductSample, ...] = ()
    only_primat_samples: tuple[ProductSample, ...] = ()
    notes: tuple[str, ...] = ()


def _nested(row: Mapping[str, Any], *path: str) -> Any:
    value: Any = row
    for part in path:
        if not isinstance(value, Mapping):
            return None
        value = value.get(part)
    return value


def _first(row: Mapping[str, Any], paths: Sequence[tuple[str, ...]]) -> Any:
    for path in paths:
        value = _nested(row, *path)
        if value is not None and value != "":
            return value
    return None


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number <= 0:
        return None
    return number


def _fold(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    ascii_letters = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_letters))


def _compact(value: str | None) -> str:
    return _fold(value).replace(" ", "")


def _gtin(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) not in {8, 12, 13, 14}:
        return None
    payload, check_digit = digits[:-1], int(digits[-1])
    weighted = 0
    for offset, character in enumerate(reversed(payload), start=1):
        weighted += int(character) * (3 if offset % 2 else 1)
    expected = (10 - weighted % 10) % 10
    return digits if check_digit == expected else None


def _canonical_quantity(quantity: Any, unit: Any) -> tuple[Decimal, str] | None:
    amount = _decimal(quantity)
    normalized_unit = _compact(_text(unit)).removeprefix("kr")
    definitions: dict[str, tuple[Decimal, str]] = {
        "g": (Decimal(1), "g"),
        "gram": (Decimal(1), "g"),
        "kg": (Decimal(1000), "g"),
        "ml": (Decimal(1), "ml"),
        "cl": (Decimal(10), "ml"),
        "dl": (Decimal(100), "ml"),
        "l": (Decimal(1000), "ml"),
        "liter": (Decimal(1000), "ml"),
        "st": (Decimal(1), "st"),
        "styck": (Decimal(1), "st"),
        "pcs": (Decimal(1), "st"),
    }
    definition = definitions.get(normalized_unit)
    if amount is None or definition is None:
        return None
    return amount * definition[0], definition[1]


def _comparison_unit(value: Any) -> str | None:
    unit = _compact(_text(value)).removeprefix("sek").removeprefix("kr")
    return {
        "kg": "kg",
        "l": "l",
        "liter": "l",
        "st": "st",
        "styck": "st",
    }.get(unit)


def _promotion_signatures(row: Mapping[str, Any]) -> tuple[str, ...]:
    signatures: set[str] = set()
    collections: list[Any] = [row.get("promotions"), row.get("offers")]
    for collection in collections:
        if not isinstance(collection, list | tuple):
            continue
        for promotion in collection:
            if not isinstance(promotion, Mapping):
                continue
            kind = _fold(_text(promotion.get("type") or promotion.get("kind"))) or "unknown"
            price = _decimal(promotion.get("price"))
            quantity = promotion.get("quantity") or promotion.get("required_packages") or 1
            member = bool(promotion.get("member_only")) or "member" in kind
            signatures.add(
                "|".join(
                    (
                        kind,
                        str(price) if price is not None else "",
                        str(quantity),
                        "member" if member else "public",
                        str(promotion.get("valid_from") or ""),
                        str(promotion.get("valid_to") or promotion.get("valid_until") or ""),
                    )
                )
            )

    prices = row.get("prices")
    if isinstance(prices, Mapping):
        for key in ("multiprice", "member_multiprice"):
            promotion = prices.get(key)
            if isinstance(promotion, Mapping):
                price = _decimal(promotion.get("price"))
                quantity = promotion.get("quantity")
                if price is not None and quantity:
                    signatures.add(
                        f"{key}|{price}|{quantity}|"
                        f"{'member' if key.startswith('member') else 'public'}||"
                    )
        member = _decimal(prices.get("member"))
        if member is not None:
            signatures.add(f"member_price|{member}|1|member||")
    return tuple(sorted(signatures))


def project_product(row: Mapping[str, Any], *, source: ComparisonSource) -> ComparisonRecord:
    """Project an API/source export row without fabricating package semantics."""

    name = _text(_first(row, (("name",), ("product_name",), ("display_name",))))
    if name is None:
        raise ValueError("comparison product is missing name")
    package_quantity_raw = _first(
        row,
        (("package_quantity",), ("purchase", "package_quantity"), ("amount",)),
    )
    package_unit_raw = _first(
        row,
        (("package_unit",), ("purchase", "package_unit"), ("unit",)),
    )
    package = _canonical_quantity(package_quantity_raw, package_unit_raw)
    # comparison_price/comparison_unit deliberately never participate in package.
    comparison_price = _decimal(
        _first(row, (("comparison_price",), ("prices", "comparison", "price")))
    )
    comparison_unit = _comparison_unit(
        _first(row, (("comparison_unit",), ("prices", "comparison", "unit")))
    )
    if comparison_price is None or comparison_unit is None:
        comparison_price = None
        comparison_unit = None

    external_product_id = _text(
        _first(
            row,
            (
                ("external_product_id",),
                ("product_id",),
                ("code",),
                ("source_product_key",),
            ),
        )
    )
    gtin = _gtin(_first(row, (("gtin",), ("ean",), ("ean13",), ("barcode",))))
    sale_price = _decimal(
        _first(
            row,
            (
                ("sale_price",),
                ("effective_price",),
                ("prices", "regular"),
                ("price",),
            ),
        )
    )
    regular_price = _decimal(_first(row, (("regular_price",), ("prices", "regular"), ("price",))))
    store_ids = tuple(
        dict.fromkeys(
            filter(
                None,
                (
                    _text(row.get("store_id")),
                    _text(row.get("store_external_id")),
                    _text(row.get("store_name")),
                ),
            )
        )
    )
    return ComparisonRecord(
        source=source,
        gtin=gtin,
        external_product_id=external_product_id,
        chain=_text(row.get("chain")),
        store_ids=store_ids,
        name=name,
        brand=_text(row.get("brand") or row.get("manufacturer")),
        sale_price=sale_price,
        regular_price=regular_price,
        comparison_price=comparison_price,
        comparison_unit=comparison_unit,
        package_quantity=package[0] if package else None,
        package_unit=package[1] if package else None,
        package_text=_text(row.get("package_text") or row.get("package")),
        sale_model=_text(row.get("sale_model")),
        promotion_signatures=_promotion_signatures(row),
    )


def _looks_like_product(row: Mapping[str, Any]) -> bool:
    return bool(
        _text(row.get("name") or row.get("product_name") or row.get("display_name"))
    ) and any(
        key in row
        for key in (
            "id",
            "product_id",
            "external_product_id",
            "code",
            "gtin",
            "ean",
            "sale_price",
            "price",
            "prices",
        )
    )


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        rows = [row for row in payload if isinstance(row, Mapping) and _looks_like_product(row)]
        if rows or not payload:
            return rows
    if isinstance(payload, Mapping):
        if _looks_like_product(payload):
            return [payload]
        for key in ("products", "items", "results", "data", "catalog"):
            if key in payload:
                rows = _rows_from_payload(payload[key])
                if rows or payload[key] == []:
                    return rows
    raise ValueError("export does not contain a recognized product collection")


def load_product_export(path: Path, *, source: ComparisonSource) -> list[ComparisonRecord]:
    """Load JSON/JSONL exports. No network or environment access occurs here."""

    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.casefold() in {".jsonl", ".ndjson"}:
        payload: Any = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        payload = json.loads(text)
    records: list[ComparisonRecord] = []
    for row in _rows_from_payload(payload):
        try:
            records.append(project_product(row, source=source))
        except ValueError:
            continue
    return records


def _package_key(record: ComparisonRecord) -> str | None:
    if record.package_quantity is not None and record.package_unit is not None:
        return f"{record.package_quantity.normalize()}:{record.package_unit}"
    package_text = _compact(record.package_text)
    return f"text:{package_text}" if package_text else None


def _normalized_product_key(record: ComparisonRecord) -> str | None:
    name = _fold(record.name)
    package = _package_key(record)
    if not name or package is None:
        return None
    return "|".join((_fold(record.brand), name, package))


def _external_key(record: ComparisonRecord) -> str | None:
    product_id = _compact(record.external_product_id)
    chain = _compact(record.chain)
    if not product_id or not chain:
        return None
    return f"{chain}:{product_id}"


def _identity(record: ComparisonRecord) -> str:
    return (
        f"gtin:{record.gtin}"
        if record.gtin
        else f"source:{_external_key(record)}"
        if _external_key(record)
        else f"normalized:{_normalized_product_key(record)}"
    )


def _package_display(record: ComparisonRecord) -> str | None:
    if record.package_quantity is not None and record.package_unit:
        return f"{record.package_quantity.normalize()} {record.package_unit}"
    return record.package_text


def _sample(record: ComparisonRecord) -> ProductSample:
    return ProductSample(
        identity=_identity(record),
        name=record.name,
        brand=record.brand,
        package=_package_display(record),
    )


def _group_unique(
    indexes: set[int],
    records: Sequence[ComparisonRecord],
    key: Callable[[ComparisonRecord], str | None],
) -> dict[str, int]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index in indexes:
        value = key(records[index])
        if value is not None:
            grouped[value].append(index)
    return {value: members[0] for value, members in grouped.items() if len(members) == 1}


def _ambiguous_shared_keys(
    own_indexes: set[int],
    primat_indexes: set[int],
    own: Sequence[ComparisonRecord],
    primat: Sequence[ComparisonRecord],
    key: Callable[[ComparisonRecord], str | None],
) -> int:
    own_grouped: dict[str, int] = defaultdict(int)
    primat_grouped: dict[str, int] = defaultdict(int)
    for index in own_indexes:
        if (value := key(own[index])) is not None:
            own_grouped[value] += 1
    for index in primat_indexes:
        if (value := key(primat[index])) is not None:
            primat_grouped[value] += 1
    return sum(
        own_grouped[value] > 1 or primat_grouped[value] > 1
        for value in own_grouped.keys() & primat_grouped.keys()
    )


def _field_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in value)
    return str(value)


class PrimatComparator:
    """Collision-aware deterministic comparison of two single-store exports."""

    def __init__(self, *, price_tolerance: Decimal = Decimal("0.01")) -> None:
        self.price_tolerance = price_tolerance

    def compare(
        self,
        own: Sequence[ComparisonRecord],
        primat: Sequence[ComparisonRecord],
        *,
        store: str,
        sample_limit: int = 10,
    ) -> PrimatComparisonReport:
        if sample_limit < 0:
            raise ValueError("sample_limit must be non-negative")
        own_left = set(range(len(own)))
        primat_left = set(range(len(primat)))
        matches: list[tuple[JoinMethod, int, int]] = []
        ambiguous = 0
        passes: tuple[tuple[JoinMethod, Callable[[ComparisonRecord], str | None]], ...] = (
            ("gtin", lambda record: record.gtin),
            ("external_product_id", _external_key),
            ("normalized_product", _normalized_product_key),
        )
        for method, key in passes:
            ambiguous += _ambiguous_shared_keys(
                own_left,
                primat_left,
                own,
                primat,
                key,
            )
            own_unique = _group_unique(own_left, own, key)
            primat_unique = _group_unique(primat_left, primat, key)
            for value in sorted(own_unique.keys() & primat_unique.keys()):
                own_index = own_unique[value]
                primat_index = primat_unique[value]
                matches.append((method, own_index, primat_index))
                own_left.remove(own_index)
                primat_left.remove(primat_index)

        counts = defaultdict(int)
        difference_samples: list[DifferenceSample] = []
        for method, own_index, primat_index in matches:
            own_record = own[own_index]
            primat_record = primat[primat_index]
            counts[f"matched_by_{method}"] += 1
            differing_fields: dict[str, dict[str, str | None]] = {}

            self._compare_decimal_field(
                "price",
                own_record.sale_price,
                primat_record.sale_price,
                counts,
                differing_fields,
            )
            self._compare_decimal_field(
                "regular_price",
                own_record.regular_price,
                primat_record.regular_price,
                counts,
                differing_fields,
            )
            own_package = _package_key(own_record)
            primat_package = _package_key(primat_record)
            self._compare_text_field(
                "package",
                own_package,
                primat_package,
                counts,
                differing_fields,
            )
            own_comparison = (
                (own_record.comparison_price, own_record.comparison_unit)
                if own_record.comparison_price is not None and own_record.comparison_unit
                else None
            )
            primat_comparison = (
                (primat_record.comparison_price, primat_record.comparison_unit)
                if primat_record.comparison_price is not None and primat_record.comparison_unit
                else None
            )
            self._compare_comparison_price(
                own_comparison,
                primat_comparison,
                counts,
                differing_fields,
            )
            self._compare_text_field(
                "sale_model",
                _fold(own_record.sale_model) or None,
                _fold(primat_record.sale_model) or None,
                counts,
                differing_fields,
            )
            if own_record.promotion_signatures == primat_record.promotion_signatures:
                counts["same_promotions"] += 1
            else:
                counts["promotions_differ"] += 1
                differing_fields["promotions"] = {
                    "own": _field_value(own_record.promotion_signatures),
                    "primat": _field_value(primat_record.promotion_signatures),
                }
            if differing_fields and len(difference_samples) < sample_limit:
                difference_samples.append(
                    DifferenceSample(
                        join_method=method,
                        identity=_identity(own_record),
                        own_name=own_record.name,
                        primat_name=primat_record.name,
                        differing_fields=differing_fields,
                    )
                )

        only_own_records = sorted((own[index] for index in own_left), key=lambda row: row.name)
        only_primat_records = sorted(
            (primat[index] for index in primat_left), key=lambda row: row.name
        )
        notes = (
            "Primat mismatch is diagnostic and does not by itself establish which source is wrong.",
            "Only unique keys are joined; collisions remain unmatched.",
            "Comparison price is never used to infer package quantity.",
        )
        return PrimatComparisonReport(
            store=store,
            own_products=len(own),
            primat_products=len(primat),
            own_with_gtin=sum(record.gtin is not None for record in own),
            primat_with_gtin=sum(record.gtin is not None for record in primat),
            own_with_price=sum(record.sale_price is not None for record in own),
            primat_with_price=sum(record.sale_price is not None for record in primat),
            own_with_explicit_package=sum(
                record.package_quantity is not None and record.package_unit is not None
                for record in own
            ),
            primat_with_explicit_package=sum(
                record.package_quantity is not None and record.package_unit is not None
                for record in primat
            ),
            matched_products=len(matches),
            matched_by_gtin=counts["matched_by_gtin"],
            matched_by_external_product_id=counts["matched_by_external_product_id"],
            matched_by_normalized_product=counts["matched_by_normalized_product"],
            ambiguous_join_keys=ambiguous,
            same_price=counts["same_price"],
            price_differs=counts["price_differs"],
            price_not_comparable=counts["price_not_comparable"],
            same_regular_price=counts["same_regular_price"],
            regular_price_differs=counts["regular_price_differs"],
            regular_price_not_comparable=counts["regular_price_not_comparable"],
            same_package=counts["same_package"],
            package_differs=counts["package_differs"],
            package_not_comparable=counts["package_not_comparable"],
            same_comparison_price=counts["same_comparison_price"],
            comparison_price_differs=counts["comparison_price_differs"],
            comparison_price_not_comparable=counts["comparison_price_not_comparable"],
            same_sale_model=counts["same_sale_model"],
            sale_model_differs=counts["sale_model_differs"],
            sale_model_not_comparable=counts["sale_model_not_comparable"],
            same_promotions=counts["same_promotions"],
            promotions_differ=counts["promotions_differ"],
            only_own=len(only_own_records),
            only_primat=len(only_primat_records),
            difference_samples=tuple(difference_samples),
            only_own_samples=tuple(_sample(row) for row in only_own_records[:sample_limit]),
            only_primat_samples=tuple(_sample(row) for row in only_primat_records[:sample_limit]),
            notes=notes,
        )

    def _compare_decimal_field(
        self,
        label: str,
        own: Decimal | None,
        primat: Decimal | None,
        counts: defaultdict[str, int],
        differences: dict[str, dict[str, str | None]],
    ) -> None:
        if own is None or primat is None:
            counts[f"{label}_not_comparable"] += 1
            if own != primat:
                differences[label] = {"own": _field_value(own), "primat": _field_value(primat)}
        elif abs(own - primat) <= self.price_tolerance:
            counts[f"same_{label}"] += 1
        else:
            counts[f"{label}_differs"] += 1
            differences[label] = {"own": str(own), "primat": str(primat)}

    @staticmethod
    def _compare_text_field(
        label: str,
        own: str | None,
        primat: str | None,
        counts: defaultdict[str, int],
        differences: dict[str, dict[str, str | None]],
    ) -> None:
        if own is None or primat is None:
            counts[f"{label}_not_comparable"] += 1
            if own != primat:
                differences[label] = {"own": own, "primat": primat}
        elif own == primat:
            counts[f"same_{label}"] += 1
        else:
            counts[f"{label}_differs"] += 1
            differences[label] = {"own": own, "primat": primat}

    def _compare_comparison_price(
        self,
        own: tuple[Decimal, str] | None,
        primat: tuple[Decimal, str] | None,
        counts: defaultdict[str, int],
        differences: dict[str, dict[str, str | None]],
    ) -> None:
        if own is None or primat is None:
            counts["comparison_price_not_comparable"] += 1
            if own != primat:
                differences["comparison_price"] = {
                    "own": _field_value(own),
                    "primat": _field_value(primat),
                }
        elif own[1] == primat[1] and abs(own[0] - primat[0]) <= self.price_tolerance:
            counts["same_comparison_price"] += 1
        else:
            counts["comparison_price_differs"] += 1
            differences["comparison_price"] = {
                "own": f"{own[0]} kr/{own[1]}",
                "primat": f"{primat[0]} kr/{primat[1]}",
            }


def compare_export_files(
    own_export: Path,
    primat_export: Path,
    *,
    store: str,
    sample_limit: int = 10,
) -> PrimatComparisonReport:
    own = load_product_export(own_export, source="own")
    primat = load_product_export(primat_export, source="primat")
    return PrimatComparator().compare(
        own,
        primat,
        store=store,
        sample_limit=sample_limit,
    )


__all__ = [
    "ComparisonRecord",
    "DifferenceSample",
    "PrimatComparator",
    "PrimatComparisonReport",
    "ProductSample",
    "compare_export_files",
    "load_product_export",
    "project_product",
]
