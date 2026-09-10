import pytest
from pydantic import ValidationError

from grocery_data.app.domain import CatalogCompletion


def test_legacy_catalog_completion_remains_full_without_exact_counts() -> None:
    evidence = CatalogCompletion(
        complete=True,
        expected_categories=4,
        completed_categories=4,
        pages_fetched=12,
        products_observed=250,
    )

    assert evidence.has_exact_evidence is False
    assert evidence.exact_evidence_reconciles is True
    assert evidence.is_full_traversal is True


def test_exact_catalog_completion_reconciles_source_total_pages_and_identities() -> None:
    evidence = CatalogCompletion(
        complete=True,
        pages_fetched=3,
        products_observed=120,
        expected_products=120,
        raw_rows=120,
        unique_products=120,
        duplicate_products=0,
        expected_pages=3,
    )

    assert evidence.has_exact_evidence is True
    assert evidence.exact_evidence_reconciles is True
    assert evidence.is_full_traversal is True


def test_exact_category_completion_accepts_fully_explained_cross_partition_overlap() -> None:
    evidence = CatalogCompletion(
        complete=True,
        expected_categories=5,
        completed_categories=5,
        pages_fetched=17,
        products_observed=1_268,
        expected_products=1_365,
        raw_rows=1_365,
        unique_products=1_268,
        duplicate_products=97,
        within_partition_duplicates=0,
        cross_partition_duplicates=97,
        expected_pages=17,
    )

    assert evidence.exact_evidence_reconciles is True
    assert evidence.is_full_traversal is True
    assert evidence.model_dump(mode="json", exclude_none=True)["cross_partition_duplicates"] == 97


def test_exact_category_completion_accepts_proven_safe_pagination_overlap() -> None:
    evidence = CatalogCompletion(
        complete=True,
        expected_categories=5,
        completed_categories=5,
        pages_fetched=17,
        products_observed=1_268,
        expected_products=1_366,
        raw_rows=1_366,
        unique_products=1_268,
        duplicate_products=98,
        within_partition_duplicates=1,
        cross_partition_duplicates=97,
        exact_duplicates_removed=1,
        conflicting_duplicates=0,
        pagination_overlaps=1,
        expected_pages=17,
    )

    assert evidence.exact_evidence_reconciles is True
    assert evidence.is_full_traversal is True


def test_conflicting_duplicate_cannot_be_declared_complete() -> None:
    with pytest.raises(ValidationError, match="complete traversal does not reconcile"):
        CatalogCompletion(
            complete=True,
            expected_categories=1,
            completed_categories=1,
            pages_fetched=2,
            products_observed=2,
            expected_products=3,
            raw_rows=3,
            unique_products=2,
            duplicate_products=1,
            within_partition_duplicates=1,
            cross_partition_duplicates=0,
            exact_duplicates_removed=0,
            conflicting_duplicates=1,
            pagination_overlaps=0,
            expected_pages=2,
        )


@pytest.mark.parametrize(
    "partition_counts",
    [
        {},
        {
            "within_partition_duplicates": 1,
            "cross_partition_duplicates": 96,
        },
    ],
    ids=("unexplained-duplicates", "within-partition-duplicate"),
)
def test_complete_category_overlap_fails_closed_unless_every_repeat_is_cross_partition(
    partition_counts: dict[str, int],
) -> None:
    with pytest.raises(ValidationError, match="complete traversal does not reconcile"):
        CatalogCompletion(
            complete=True,
            expected_categories=5,
            completed_categories=5,
            pages_fetched=17,
            products_observed=1_268,
            expected_products=1_365,
            raw_rows=1_365,
            unique_products=1_268,
            duplicate_products=97,
            expected_pages=17,
            **partition_counts,
        )


def test_partition_duplicate_evidence_must_classify_every_duplicate() -> None:
    with pytest.raises(ValidationError, match="classify every duplicate"):
        CatalogCompletion(
            complete=False,
            pages_fetched=17,
            products_observed=1_268,
            expected_products=1_365,
            raw_rows=1_365,
            unique_products=1_268,
            duplicate_products=97,
            within_partition_duplicates=0,
            cross_partition_duplicates=96,
            expected_pages=17,
        )


def test_incomplete_exact_capture_can_retain_partial_debug_evidence() -> None:
    evidence = CatalogCompletion(
        complete=False,
        pages_fetched=2,
        products_observed=80,
        expected_products=120,
        raw_rows=80,
        unique_products=80,
        duplicate_products=0,
        expected_pages=3,
        reason="page_request_failed",
    )

    assert evidence.has_exact_evidence is True
    assert evidence.exact_evidence_reconciles is False
    assert evidence.is_full_traversal is False


def test_exact_catalog_evidence_is_all_or_none() -> None:
    with pytest.raises(ValidationError, match="every exact-count field"):
        CatalogCompletion(
            complete=False,
            pages_fetched=1,
            products_observed=20,
            expected_products=100,
        )


@pytest.mark.parametrize(
    "update",
    [
        {"raw_rows": 121, "duplicate_products": 1},
        {"unique_products": 119, "products_observed": 119, "raw_rows": 119},
        {"expected_pages": 4},
    ],
)
def test_complete_exact_catalog_evidence_fails_closed_on_mismatch(
    update: dict[str, int],
) -> None:
    values = {
        "complete": True,
        "pages_fetched": 3,
        "products_observed": 120,
        "expected_products": 120,
        "raw_rows": 120,
        "unique_products": 120,
        "duplicate_products": 0,
        "expected_pages": 3,
    }
    values.update(update)

    with pytest.raises(ValidationError, match="complete traversal does not reconcile"):
        CatalogCompletion(**values)


def test_exact_catalog_evidence_rejects_impossible_row_arithmetic() -> None:
    with pytest.raises(ValidationError, match="unique plus duplicate"):
        CatalogCompletion(
            complete=False,
            pages_fetched=1,
            products_observed=10,
            expected_products=100,
            raw_rows=12,
            unique_products=10,
            duplicate_products=1,
            expected_pages=10,
        )
