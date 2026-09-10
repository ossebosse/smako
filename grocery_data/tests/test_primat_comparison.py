from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from grocery_data import __main__ as cli
from grocery_data.app.services.primat_comparison import (
    ComparisonRecord,
    PrimatComparator,
    load_product_export,
    project_product,
)


def _record(
    source: str,
    name: str,
    *,
    gtin: str | None = None,
    external_product_id: str | None = None,
    price: str = "20.00",
    brand: str | None = None,
    package_quantity: str | None = "500",
    package_unit: str | None = "g",
    sale_model: str | None = "fixed_package",
) -> ComparisonRecord:
    return ComparisonRecord(
        source=source,
        gtin=gtin,
        external_product_id=external_product_id,
        chain="Willys",
        name=name,
        brand=brand,
        sale_price=Decimal(price),
        package_quantity=Decimal(package_quantity) if package_quantity else None,
        package_unit=package_unit,
        sale_model=sale_model,
    )


def test_join_precedence_and_diagnostics_are_collision_aware() -> None:
    own = [
        _record("own", "Pasta A", gtin="4006381333931", price="20.00"),
        _record("own", "Ris B", external_product_id="B-2", price="30.00"),
        _record(
            "own",
            "Garant Spaghetti",
            brand="Garant",
            package_quantity="1000",
            price="18.90",
        ),
        _record("own", "Dublett", package_quantity="250"),
        _record("own", "Dublett", package_quantity="250"),
        _record("own", "Bara egen", gtin="9780306406157"),
    ]
    primat = [
        _record("primat", "Helt annat namn", gtin="4006381333931", price="21.00"),
        _record("primat", "Ris B", external_product_id="B-2", price="30.00"),
        _record(
            "primat",
            "GARANT spaghetti",
            brand="garant",
            package_quantity="1000",
            package_unit="g",
            price="18.90",
        ),
        _record("primat", "Dublett", package_quantity="250"),
        _record("primat", "Bara Primat", gtin="9501101530003"),
    ]

    report = PrimatComparator().compare(own, primat, store="Willys Lund", sample_limit=3)

    assert report.matched_products == 3
    assert report.matched_by_gtin == 1
    assert report.matched_by_external_product_id == 1
    assert report.matched_by_normalized_product == 1
    assert report.ambiguous_join_keys == 1
    assert report.own_with_gtin == 2
    assert report.primat_with_gtin == 2
    assert report.own_with_price == 6
    assert report.primat_with_price == 5
    assert report.same_price == 2
    assert report.price_differs == 1
    assert report.only_own == 3
    assert report.only_primat == 2
    assert report.difference_samples[0].differing_fields["price"] == {
        "own": "20.00",
        "primat": "21.00",
    }


def test_comparison_price_never_becomes_package_quantity() -> None:
    record = project_product(
        {
            "product_id": "pepper-1",
            "name": "Paprika Röd",
            "price": 10.79,
            "comparison_price": 39.90,
            "comparison_unit": "kr/kg",
        },
        source="primat",
    )

    assert record.sale_price == Decimal("10.79")
    assert record.comparison_price == Decimal("39.90")
    assert record.comparison_unit == "kg"
    assert record.package_quantity is None
    assert record.package_unit is None


def test_project_product_uses_explicit_structured_package_and_not_offer_as_sale() -> None:
    record = project_product(
        {
            "product_id": "pasta-1",
            "name": "Pasta 1 kg",
            "amount": 1,
            "unit": "kg",
            "prices": {
                "regular": 19.90,
                "offer": {"price": 9.90},
                "comparison": {"price": 19.90, "unit": "kr/kg"},
            },
        },
        source="primat",
    )

    assert record.sale_price == Decimal("19.9")
    assert record.package_quantity == Decimal(1000)
    assert record.package_unit == "g"


def test_load_export_supports_wrapped_json_and_jsonl(tmp_path: Path) -> None:
    own_path = tmp_path / "own.json"
    own_path.write_text(
        json.dumps({"items": [{"id": "1", "name": "Mjölk", "sale_price": 15.9}]}),
        encoding="utf-8",
    )
    primat_path = tmp_path / "primat.jsonl"
    primat_path.write_text(
        "\n".join(
            (
                json.dumps({"product_id": "1", "name": "Mjölk", "price": 15.9}),
                json.dumps({"not": "a product"}),
            )
        ),
        encoding="utf-8",
    )

    assert len(load_product_export(own_path, source="own")) == 1
    assert len(load_product_export(primat_path, source="primat")) == 1


def test_cli_compare_primat_is_offline_and_does_not_load_dotenv(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    own_path = tmp_path / "own.json"
    primat_path = tmp_path / "primat.json"
    own_path.write_text(
        json.dumps(
            [
                {
                    "gtin": "4006381333931",
                    "name": "Pasta",
                    "sale_price": 20,
                    "package_quantity": 500,
                    "package_unit": "g",
                }
            ]
        ),
        encoding="utf-8",
    )
    primat_path.write_text(
        json.dumps(
            [
                {
                    "gtin": "4006381333931",
                    "name": "Pasta",
                    "price": 20,
                    "amount": 500,
                    "unit": "g",
                }
            ]
        ),
        encoding="utf-8",
    )
    dotenv_calls = 0

    def unexpected_dotenv_call() -> None:
        nonlocal dotenv_calls
        dotenv_calls += 1

    monkeypatch.setattr(cli, "load_dotenv", unexpected_dotenv_call)

    exit_code = cli.main(
        [
            "compare-primat",
            "--store",
            "Willys Lund",
            "--own-export",
            str(own_path),
            "--primat-export",
            str(primat_path),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert dotenv_calls == 0
    assert payload["store"] == "Willys Lund"
    assert payload["matched_by_gtin"] == 1
    assert payload["same_price"] == 1


def test_invalid_gtin_does_not_create_false_primary_join() -> None:
    own = [
        project_product({"gtin": "1234567890123", "name": "Produkt A", "price": 10}, source="own")
    ]
    primat = [
        project_product(
            {"gtin": "1234567890123", "name": "Produkt B", "price": 10},
            source="primat",
        )
    ]

    report = PrimatComparator().compare(own, primat, store="test")

    assert report.matched_by_gtin == 0
    assert report.matched_products == 0
