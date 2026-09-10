from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from grocery_data.app.domain.enums import Chain


class RawFetch(BaseModel):
    """Sanitised HTTP evidence retained before any chain parser runs."""

    model_config = ConfigDict(frozen=True)

    chain: Chain
    store_external_id: str | None = None
    kind: str
    method: str
    url: str
    query: dict[str, str] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    http_status: int
    content_type: str | None = None
    payload: bytes
    connector_version: str
    page_number: int | None = None

    @computed_field
    @property
    def payload_hash(self) -> str:
        return sha256(self.payload).hexdigest()

    def json_payload(self) -> Any:
        import json

        return json.loads(self.payload)


class TransportMetrics(BaseModel):
    """Physical HTTP attempt counters for one connector operation."""

    model_config = ConfigDict(frozen=True)

    request_count: int = Field(default=0, ge=0)
    http_error_count: int = Field(default=0, ge=0)
    rate_limit_count: int = Field(default=0, ge=0)


class CatalogCompletion(BaseModel):
    """Evidence that a purported full-catalog traversal actually completed."""

    model_config = ConfigDict(frozen=True)

    complete: bool = False
    limited: bool = False
    expected_categories: int | None = Field(default=None, ge=0)
    completed_categories: int = Field(default=0, ge=0)
    pages_fetched: int = Field(default=0, ge=0)
    products_observed: int = Field(default=0, ge=0)
    # Flat catalogs can expose stronger evidence than a category traversal:
    # an expected total plus an exact page/row/identity reconciliation.  These
    # fields are deliberately optional so older Willys snapshots remain
    # replayable.  Once one is supplied, however, the complete evidence suite
    # is required; a caller may not retain only the convenient parts.
    expected_products: int | None = Field(default=None, ge=0)
    raw_rows: int | None = Field(default=None, ge=0)
    unique_products: int | None = Field(default=None, ge=0)
    duplicate_products: int | None = Field(default=None, ge=0)
    # Category-partition traversals can legitimately expose the same product
    # in more than one disjoint-looking navigation branch.  The distinction
    # is explicit and optional so flat-catalog and historical evidence keeps
    # its existing contract.  A repeated row inside one partition is accepted
    # only when the connector proves that its complete product row is
    # semantically identical.  Unclassified or conflicting repeats remain a
    # hard failure.  A cross-partition repeat can be accepted only when every
    # duplicate is classified and reconciled.
    within_partition_duplicates: int | None = Field(default=None, ge=0)
    cross_partition_duplicates: int | None = Field(default=None, ge=0)
    # Additive, connector-proven classification for within-partition repeats.
    # ``exact_duplicates_removed`` counts rows whose complete purchase
    # semantics matched the earlier row. ``pagination_overlaps`` is the subset
    # repeated on a later page. A historical producer that omits these fields
    # retains the stricter rule that within-partition duplicates are unsafe.
    exact_duplicates_removed: int | None = Field(default=None, ge=0)
    conflicting_duplicates: int | None = Field(default=None, ge=0)
    pagination_overlaps: int | None = Field(default=None, ge=0)
    expected_pages: int | None = Field(default=None, ge=0)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_exact_evidence(self) -> "CatalogCompletion":
        overlap_values = (
            self.within_partition_duplicates,
            self.cross_partition_duplicates,
        )
        duplicate_classification_values = (
            self.exact_duplicates_removed,
            self.conflicting_duplicates,
            self.pagination_overlaps,
        )
        values = (
            self.expected_products,
            self.raw_rows,
            self.unique_products,
            self.duplicate_products,
            self.expected_pages,
        )
        if all(value is None for value in values):
            if any(value is not None for value in overlap_values) or any(
                value is not None for value in duplicate_classification_values
            ):
                raise ValueError("duplicate evidence requires exact catalog evidence")
            return self
        if any(value is None for value in values):
            raise ValueError("exact catalog evidence must provide every exact-count field")

        if any(value is not None for value in overlap_values) and any(
            value is None for value in overlap_values
        ):
            raise ValueError("partition duplicate evidence must provide within and cross counts")
        if any(value is not None for value in duplicate_classification_values) and any(
            value is None for value in duplicate_classification_values
        ):
            raise ValueError(
                "duplicate classification must provide exact, conflict and pagination counts"
            )
        if any(value is not None for value in duplicate_classification_values) and any(
            value is None for value in overlap_values
        ):
            raise ValueError("duplicate classification requires within and cross partition counts")

        # The preceding all-or-none check narrows these values for humans and
        # type checkers cannot express that Pydantic invariant directly.
        assert self.expected_products is not None
        assert self.raw_rows is not None
        assert self.unique_products is not None
        assert self.duplicate_products is not None
        assert self.expected_pages is not None

        if self.raw_rows != self.unique_products + self.duplicate_products:
            raise ValueError("raw catalog rows must equal unique plus duplicate products")
        if self.within_partition_duplicates is not None:
            assert self.cross_partition_duplicates is not None
            if (
                self.within_partition_duplicates + self.cross_partition_duplicates
                != self.duplicate_products
            ):
                raise ValueError("partition duplicate counts must classify every duplicate product")
        if self.exact_duplicates_removed is not None:
            assert self.within_partition_duplicates is not None
            assert self.conflicting_duplicates is not None
            assert self.pagination_overlaps is not None
            if self.exact_duplicates_removed > self.within_partition_duplicates:
                raise ValueError(
                    "exact duplicate removals cannot exceed within-partition duplicates"
                )
            if self.conflicting_duplicates > self.duplicate_products:
                raise ValueError("conflicting duplicates cannot exceed all duplicate products")
            if self.pagination_overlaps > self.exact_duplicates_removed:
                raise ValueError("pagination overlaps cannot exceed exact duplicate removals")
        if self.products_observed != self.unique_products:
            raise ValueError("products_observed must equal the exact unique product count")
        if self.unique_products > self.expected_products:
            raise ValueError("unique product count cannot exceed the source-reported total")
        if self.pages_fetched > self.expected_pages:
            raise ValueError("fetched page count cannot exceed the source-reported page count")
        if self.complete and not self.limited and not self.exact_evidence_reconciles:
            raise ValueError("complete traversal does not reconcile its exact catalog evidence")
        return self

    @property
    def has_exact_evidence(self) -> bool:
        return self.expected_products is not None

    @property
    def exact_evidence_reconciles(self) -> bool:
        """Whether exact source totals reconcile without unexplained repeats."""

        if not self.has_exact_evidence:
            return True
        common_counts_reconcile = (
            self.expected_products == self.raw_rows
            and self.products_observed == self.unique_products
            and self.expected_pages == self.pages_fetched
        )
        if not common_counts_reconcile:
            return False
        if self.duplicate_products == 0:
            return self.expected_products == self.unique_products
        safe_within_partition = self.within_partition_duplicates == 0
        if self.exact_duplicates_removed is not None:
            safe_within_partition = (
                self.exact_duplicates_removed == self.within_partition_duplicates
                and self.conflicting_duplicates == 0
            )
        return (
            safe_within_partition
            and self.cross_partition_duplicates + (self.exact_duplicates_removed or 0)
            == self.duplicate_products
            and self.unique_products
            + self.cross_partition_duplicates
            + (self.exact_duplicates_removed or 0)
            == self.raw_rows
        )

    @property
    def is_full_traversal(self) -> bool:
        return self.complete and not self.limited and self.exact_evidence_reconciles


class RawBatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    documents: tuple[RawFetch, ...]
    transport: TransportMetrics = Field(default_factory=TransportMetrics)
    catalog_completion: CatalogCompletion | None = None

    def with_references(self, references: list[str]) -> list[tuple[RawFetch, str]]:
        if len(references) != len(self.documents):
            raise ValueError("one raw reference is required per document")
        return list(zip(self.documents, references, strict=True))
