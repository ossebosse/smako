import json
from pathlib import Path

import pytest

from grocery_data.app.connectors.hemkop.models import (
    HemkopCatalogPage,
    top_level_category_paths,
    validated_catalog_page,
)
from grocery_data.app.connectors.hemkop.parser import HemkopParser

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "hemkop" / "fixtures"


def _catalog_payload(
    *,
    current_page: int = 0,
    number_of_pages: int = 1,
    page_size: int = 30,
    total_results: int = 1,
    results: object | None = None,
) -> dict[str, object]:
    return {
        "results": [{"code": "101548687_ST"}] if results is None else results,
        "pagination": {
            "currentPage": current_page,
            "numberOfPages": number_of_pages,
            "pageSize": page_size,
            "totalNumberOfResults": total_results,
        },
    }


def _facets(store_id: str) -> list[dict[str, object]]:
    return [
        {
            "values": [
                {
                    "query": {
                        "query": {
                            "value": f":topRated:salableOnlineInStore_string_mv:{store_id}"
                        }
                    }
                }
            ]
        }
    ]


def test_validated_catalog_page_returns_explicit_pagination_contract() -> None:
    results = [{"code": f"product-{index}"} for index in range(12)]

    page = validated_catalog_page(
        _catalog_payload(
            current_page=1,
            number_of_pages=3,
            page_size=12,
            total_results=25,
            results=results,
        ),
        requested_page=1,
    )

    assert isinstance(page, HemkopCatalogPage)
    assert list(page.results) == results
    assert page.current_page == 1
    assert page.number_of_pages == 3
    assert page.page_size == 12
    assert page.total_results == 25


def test_zero_result_page_has_zero_declared_pages() -> None:
    page = validated_catalog_page(
        _catalog_payload(
            current_page=0,
            number_of_pages=0,
            page_size=30,
            total_results=0,
            results=[],
        ),
        requested_page=0,
    )

    assert page.results == ()
    assert page.number_of_pages == 0
    assert page.total_results == 0


def test_exact_multiple_requires_and_accepts_only_strict_null_terminal_page() -> None:
    first = _catalog_payload(
        current_page=0,
        number_of_pages=3,
        page_size=100,
        total_results=200,
        results=[{"code": f"product-{index}"} for index in range(100)],
    )
    first["facets"] = _facets("4247")
    parsed_first = validated_catalog_page(
        first,
        requested_page=0,
        requested_size=100,
        expected_store_id="4247",
    )
    assert len(parsed_first.results) == 100
    assert parsed_first.number_of_pages == 3

    terminal = _catalog_payload(
        current_page=2,
        number_of_pages=3,
        page_size=100,
        total_results=200,
        results=[],
    )
    terminal["results"] = None
    terminal["facets"] = _facets("4247")
    parsed_terminal = validated_catalog_page(
        terminal,
        requested_page=2,
        requested_size=100,
        expected_store_id="4247",
    )
    assert parsed_terminal.results == ()

    terminal["results"] = []
    with pytest.raises(ValueError, match="null"):
        validated_catalog_page(terminal, requested_page=2, expected_store_id="4247")


@pytest.mark.parametrize("facets", [None, _facets("4114")])
def test_page_local_store_context_is_exact_and_fail_closed(facets: object) -> None:
    payload = _catalog_payload()
    if facets is not None:
        payload["facets"] = facets

    with pytest.raises(ValueError, match="store facet context|facets"):
        validated_catalog_page(payload, expected_store_id="4224")


@pytest.mark.parametrize(
    "payload",
    [
        {"results": []},
        {"results": [], "pagination": None},
        {
            "results": [],
            "pagination": {
                "currentPage": 0,
                "numberOfPages": 1,
                "totalNumberOfResults": 0,
            },
        },
        {
            "results": [],
            "pagination": {
                "currentPage": 0,
                "numberOfPages": 1,
                "pageSize": 30,
            },
        },
        {
            "results": [],
            "pagination": {
                "currentPage": "0",
                "numberOfPages": 1,
                "pageSize": 30,
                "totalNumberOfResults": 0,
            },
        },
        {
            "results": [],
            "pagination": {
                "currentPage": 0,
                "numberOfPages": True,
                "pageSize": 30,
                "totalNumberOfResults": 0,
            },
        },
        {
            "results": [],
            "pagination": {
                "currentPage": 0,
                "numberOfPages": 0,
                "pageSize": 0,
                "totalNumberOfResults": 0,
            },
        },
    ],
    ids=(
        "missing-pagination",
        "pagination-not-object",
        "missing-page-size",
        "missing-total-results",
        "string-current-page",
        "boolean-number-of-pages",
        "non-positive-page-size",
    ),
)
def test_pagination_metadata_is_mandatory_and_strict(payload: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        validated_catalog_page(payload, requested_page=0)


def test_requested_page_mismatch_fails_closed() -> None:
    with pytest.raises(ValueError, match="requested"):
        validated_catalog_page(_catalog_payload(), requested_page=1)


@pytest.mark.parametrize(
    ("results", "expected_error"),
    [
        (None, "results"),
        ({}, "results"),
        ("not-a-list", "results"),
    ],
)
def test_results_must_be_an_explicit_list(
    results: object,
    expected_error: str,
) -> None:
    payload = _catalog_payload()
    payload["results"] = results

    with pytest.raises((TypeError, ValueError), match=expected_error):
        validated_catalog_page(payload, requested_page=0)


@pytest.mark.parametrize(
    "payload",
    [
        _catalog_payload(
            current_page=0,
            number_of_pages=1,
            page_size=30,
            total_results=31,
            results=[{"code": f"product-{index}"} for index in range(30)],
        ),
        _catalog_payload(
            current_page=2,
            number_of_pages=2,
            page_size=30,
            total_results=60,
            results=[],
        ),
        _catalog_payload(
            current_page=0,
            number_of_pages=2,
            page_size=30,
            total_results=60,
            results=[{"code": "short-page"}],
        ),
        _catalog_payload(
            current_page=1,
            number_of_pages=2,
            page_size=30,
            total_results=31,
            results=[],
        ),
    ],
    ids=(
        "declared-page-count-does-not-match-total",
        "current-page-out-of-bounds",
        "short-nonterminal-page",
        "terminal-row-count-does-not-match-total",
    ),
)
def test_pagination_arithmetic_must_reconcile(payload: object) -> None:
    with pytest.raises(ValueError):
        validated_catalog_page(payload)


def test_top_level_partition_uses_exactly_the_twenty_live_root_children() -> None:
    tree = (FIXTURES / "category_tree_20.json").read_bytes()
    expected = tuple(
        sorted(
            (
                "kott-fagel-och-chark",
                "frukt-och-gront",
                "mejeri-ost-och-agg",
                "skafferi",
                "fryst",
                "brod-och-kakor",
                "fisk-och-skaldjur",
                "vegetariskt",
                "fardigmat",
                "delikatessen",
                "godis-snacks-och-glass",
                "dryck",
                "barn",
                "hem-och-hushall",
                "halsa-och-skonhet",
                "apotek-och-lakemedel",
                "blommor-och-tillbehor",
                "kiosk",
                "djur",
                "ovrigt",
            )
        )
    )

    paths = tuple(top_level_category_paths(tree))

    assert paths == expected
    assert tuple(HemkopParser.top_level_category_paths(tree)) == expected
    assert len(paths) == 20
    assert "kott-fagel-och-chark/kott" not in paths
    assert "frukt-och-gront/gronsaker" not in paths
    assert "mejeri-ost-och-agg/mjolk" not in paths
    assert all("/" not in path for path in paths)
    assert all(
        not right.startswith(f"{left}/")
        for left in paths
        for right in paths
        if left != right
    )


def test_top_level_partition_ignores_invalid_children_and_never_descends() -> None:
    tree = json.dumps(
        {
            "id": "N00",
            "category": "N00",
            "title": "Alla varor",
            "url": "/alla-varor/c/",
            "valid": True,
            "children": [
                {
                    "id": "N01",
                    "category": "N01",
                    "title": "Mat",
                    "url": "mat",
                    "valid": True,
                    "children": [
                        {
                            "id": "N0101",
                            "category": "N0101",
                            "title": "Underkategori",
                            "url": "mat/underkategori",
                            "valid": True,
                            "children": [],
                        }
                    ],
                },
                {
                    "id": "N02",
                    "category": "N02",
                    "title": "Inaktiv",
                    "url": "inaktiv",
                    "valid": False,
                    "children": [],
                },
            ],
        }
    ).encode()

    assert tuple(top_level_category_paths(tree)) == ("mat",)


def test_top_level_partition_rejects_duplicate_source_paths() -> None:
    tree = json.dumps(
        {
            "id": "N00",
            "category": "N00",
            "title": "Alla varor",
            "url": "/alla-varor/c/",
            "valid": True,
            "children": [
                {"id": "N01", "title": "A", "url": "mat", "valid": True},
                {"id": "N02", "title": "B", "url": "mat", "valid": True},
            ],
        }
    ).encode()

    with pytest.raises((TypeError, ValueError)):
        top_level_category_paths(tree)
