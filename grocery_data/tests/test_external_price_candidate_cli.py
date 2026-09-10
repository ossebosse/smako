from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from grocery_data.__main__ import main as cli_main
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.app.storage.models import (
    ExternalPriceCandidateModel,
    PhysicalStoreModel,
    StoreContextLinkModel,
)

NOW = datetime(2026, 8, 23, 16, tzinfo=UTC)


def test_cli_imports_persisted_primat_candidate_and_physical_report_uses_it(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "physical-external.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id="physical:ica:1004409",
                chain="ica",
                external_store_id="1004409",
                external_store_aliases=["2771"],
                name="ICA Kvantum Malmborgs Clemenstorget",
                address="Clemenstorget 5",
                postal_code="22221",
                city="Lund",
                official_source="https://www.ica.se/butiker/oppettider/lund/",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
        )
        session.add(
            StoreContextLinkModel(
                physical_store_id="physical:ica:1004409",
                grocery_context_id="primat:ica:2771",
                source_provider="primat",
                source_channel="catalog",
                grocery_context_name="ICA Clemenstorget",
                price_context_type="physical_store",
                coverage="full_catalog",
                relation_type="exact_store_online_context",
                confidence="exact",
                evidence="official ICA storeId alias exact match",
                basket_eligible=True,
                offers_only=False,
                snapshot_id="primat-snapshot-1",
                observed_at=NOW,
                linked_at=NOW,
                last_verified_at=NOW,
                is_active=True,
            )
        )
        session.commit()
    engine.dispose()

    payload_path = tmp_path / "primat-candidates.json"
    candidate = {
        "physical_store_id": "physical:ica:1004409",
        "grocery_context_id": "primat:ica:2771",
        "source_provider": "primat",
        "source_snapshot_id": "primat-snapshot-1",
        "observed_at": NOW.isoformat(),
        "product_id": "primat-milk-1",
        "product_name": "Mjölk 1 l",
        "gtin": "7310865004703",
        "current_price": "29.90",
        "regular_price": "29.90",
        "member_only": False,
        "sale_model": "fixed_package",
        "common_product_score": "1",
    }
    payload_path.write_text(
        json.dumps(
            {
                "schema": "external-price-candidates-v1",
                "candidates": [candidate],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert cli_main(["import-physical-digital-prices", "--input", str(payload_path)]) == 0
    imported = json.loads(capsys.readouterr().out)
    assert imported["products"] == 1
    assert imported["credential_free"] is True
    assert imported["live_provider_requests"] == 0

    leaked_path = tmp_path / "leaked-top-level.json"
    leaked_path.write_text(
        json.dumps(
            {
                "schema": "external-price-candidates-v1",
                "candidates": [candidate],
                "authorization": "must-not-be-accepted-or-logged",
            }
        ),
        encoding="utf-8",
    )
    assert cli_main(["import-physical-digital-prices", "--input", str(leaked_path)]) == 2
    failure = capsys.readouterr().out
    assert "must-not-be-accepted-or-logged" not in failure

    legacy_path = tmp_path / "legacy-items.json"
    legacy_path.write_text(json.dumps({"items": [candidate]}), encoding="utf-8")
    assert cli_main(["import-physical-digital-prices", "--input", str(legacy_path)]) == 2
    capsys.readouterr()

    missing_schema_path = tmp_path / "missing-schema.json"
    missing_schema_path.write_text(
        json.dumps({"candidates": [candidate]}),
        encoding="utf-8",
    )
    assert (
        cli_main(["import-physical-digital-prices", "--input", str(missing_schema_path)])
        == 2
    )
    capsys.readouterr()

    mixed_scope_path = tmp_path / "mixed-scope.json"
    mixed_scope_path.write_text(
        json.dumps(
            {
                "schema": "external-price-candidates-v1",
                "candidates": [
                    candidate,
                    {
                        **candidate,
                        "source_snapshot_id": "different-snapshot",
                        "product_id": "primat-milk-2",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    assert (
        cli_main(["import-physical-digital-prices", "--input", str(mixed_scope_path)])
        == 2
    )
    capsys.readouterr()

    assert (
        cli_main(
            [
                "record-physical-price",
                "--store",
                "physical:ica:1004409",
                "--gtin",
                "7310865004703",
                "--price",
                "29.90",
                "--observed-at",
                NOW.isoformat(),
            ]
        )
        == 0
    )
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["catalog_price_updated"] is False
    assert recorded["comparisons"][0]["source_provider"] == "primat"
    assert recorded["comparisons"][0]["status"] == "match"

    assert (
        cli_main(
            [
                "physical-price-report",
                "--chain",
                "ica",
                "--city",
                "Lund",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["sampled_only"] is True
    assert report["report"]["scope_label"].startswith("ICA, Lund")
    assert report["report"]["observation_count"] == 1
    assert report["report"]["providers"]["primat"]["exact_matches"] == 1

    verification_engine = create_database_engine(database_url)
    with create_session_factory(verification_engine)() as session:
        row = session.scalar(select(ExternalPriceCandidateModel))
        assert row is not None
        assert row.source_provider == "primat"
        assert row.is_active is True
    verification_engine.dispose()
