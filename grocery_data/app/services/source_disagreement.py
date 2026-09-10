from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.services.catalog_snapshot_quality import is_valid_gtin


class ProviderPriceObservation(BaseModel):
    """Credential-free projection for comparing two provider observations."""

    model_config = ConfigDict(frozen=True)

    chain: str = Field(min_length=1)
    logical_context_id: str = Field(min_length=1)
    source_provider: str = Field(min_length=1)
    source_snapshot_id: str = Field(min_length=1)
    observed_at: datetime
    name: str = Field(min_length=1)
    sale_price: Decimal = Field(gt=0)
    gtin: str | None = None
    external_product_id: str | None = None


class PriceDisagreementSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: str
    name: str
    primary_price: Decimal
    secondary_price: Decimal
    difference: Decimal
    primary_observed_at: datetime
    secondary_observed_at: datetime


class SourceDisagreementReport(BaseModel):
    """Diagnostic only; it never reconciles, averages or selects a price."""

    model_config = ConfigDict(frozen=True)

    chain: str
    logical_context_id: str
    primary_provider: str
    secondary_provider: str
    primary_rows: int = Field(ge=0)
    secondary_rows: int = Field(ge=0)
    products_compared: int = Field(ge=0)
    matched_by_gtin: int = Field(ge=0)
    matched_by_external_product_id: int = Field(ge=0)
    ambiguous_identity_keys: int = Field(ge=0)
    same_price: int = Field(ge=0)
    within_one_sek: int = Field(ge=0)
    over_one_sek: int = Field(ge=0)
    only_primary: int = Field(ge=0)
    only_secondary: int = Field(ge=0)
    same_price_percent: Decimal = Field(ge=0, le=100)
    within_one_sek_percent: Decimal = Field(ge=0, le=100)
    over_one_sek_percent: Decimal = Field(ge=0, le=100)
    samples: tuple[PriceDisagreementSample, ...] = ()
    note: str = (
        "Diagnostic comparison only; prices are never averaged and source resolution "
        "remains deterministic."
    )


def _unique_index(
    indexes: set[int],
    rows: Sequence[ProviderPriceObservation],
    key: Callable[[ProviderPriceObservation], str | None],
) -> tuple[dict[str, int], set[str]]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index in indexes:
        if value := key(rows[index]):
            grouped[value].append(index)
    return (
        {value: members[0] for value, members in grouped.items() if len(members) == 1},
        {value for value, members in grouped.items() if len(members) > 1},
    )


def _gtin_key(row: ProviderPriceObservation) -> str | None:
    return row.gtin if is_valid_gtin(row.gtin) else None


def _external_key(row: ProviderPriceObservation) -> str | None:
    value = (row.external_product_id or "").strip()
    return f"{row.chain.casefold()}:{value}" if value else None


def _percent(numerator: int, denominator: int) -> Decimal:
    if denominator == 0:
        return Decimal(0)
    return (Decimal(numerator) * 100 / Decimal(denominator)).quantize(Decimal("0.01"))


class SourceDisagreementService:
    """Compare two already-resolved exports without making provider calls."""

    def __init__(self, *, same_price_tolerance: Decimal = Decimal("0.01")) -> None:
        if same_price_tolerance < 0:
            raise ValueError("same_price_tolerance must not be negative")
        self.same_price_tolerance = same_price_tolerance

    def compare(
        self,
        primary: Sequence[ProviderPriceObservation],
        secondary: Sequence[ProviderPriceObservation],
        *,
        chain: str,
        logical_context_id: str,
        sample_limit: int = 10,
    ) -> SourceDisagreementReport:
        if sample_limit < 0:
            raise ValueError("sample_limit must not be negative")
        expected_chain = chain.casefold()
        for row in (*primary, *secondary):
            if row.chain.casefold() != expected_chain:
                raise ValueError("all observations must belong to the requested chain")
            if row.logical_context_id != logical_context_id:
                raise ValueError("all observations must belong to the requested logical context")

        primary_left = set(range(len(primary)))
        secondary_left = set(range(len(secondary)))
        matches: list[tuple[str, str, int, int]] = []
        ambiguous: set[tuple[str, str]] = set()
        for method, key in (("gtin", _gtin_key), ("external_product_id", _external_key)):
            primary_keys, primary_collisions = _unique_index(primary_left, primary, key)
            secondary_keys, secondary_collisions = _unique_index(secondary_left, secondary, key)
            shared = primary_keys.keys() & secondary_keys.keys()
            shared_ambiguous = (primary_collisions | secondary_collisions) & (
                (set(primary_keys) | primary_collisions)
                & (set(secondary_keys) | secondary_collisions)
            )
            ambiguous.update((method, value) for value in shared_ambiguous)
            for value in sorted(shared):
                primary_index = primary_keys[value]
                secondary_index = secondary_keys[value]
                matches.append((method, value, primary_index, secondary_index))
                primary_left.remove(primary_index)
                secondary_left.remove(secondary_index)

        same = within_one = over_one = 0
        samples: list[PriceDisagreementSample] = []
        for _method, identity, primary_index, secondary_index in matches:
            left = primary[primary_index]
            right = secondary[secondary_index]
            difference = abs(left.sale_price - right.sale_price)
            if difference <= self.same_price_tolerance:
                same += 1
            elif difference <= Decimal(1):
                within_one += 1
            else:
                over_one += 1
            if difference > self.same_price_tolerance and len(samples) < sample_limit:
                samples.append(
                    PriceDisagreementSample(
                        identity=identity,
                        name=left.name,
                        primary_price=left.sale_price,
                        secondary_price=right.sale_price,
                        difference=difference,
                        primary_observed_at=left.observed_at,
                        secondary_observed_at=right.observed_at,
                    )
                )

        compared = len(matches)
        return SourceDisagreementReport(
            chain=chain,
            logical_context_id=logical_context_id,
            primary_provider=primary[0].source_provider if primary else "unknown",
            secondary_provider=secondary[0].source_provider if secondary else "unknown",
            primary_rows=len(primary),
            secondary_rows=len(secondary),
            products_compared=compared,
            matched_by_gtin=sum(method == "gtin" for method, *_ in matches),
            matched_by_external_product_id=sum(
                method == "external_product_id" for method, *_ in matches
            ),
            ambiguous_identity_keys=len(ambiguous),
            same_price=same,
            within_one_sek=within_one,
            over_one_sek=over_one,
            only_primary=len(primary_left),
            only_secondary=len(secondary_left),
            same_price_percent=_percent(same, compared),
            within_one_sek_percent=_percent(within_one, compared),
            over_one_sek_percent=_percent(over_one, compared),
            samples=tuple(samples),
        )


__all__ = [
    "PriceDisagreementSample",
    "ProviderPriceObservation",
    "SourceDisagreementReport",
    "SourceDisagreementService",
]
