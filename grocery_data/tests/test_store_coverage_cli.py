from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from grocery_data.__main__ import main as cli_main
from grocery_data.app.storage import create_database_engine, create_schema

FIXTURE = Path(__file__).parents[1] / "app" / "services" / "fixtures" / "official_stores_lund.json"


def test_audit_store_coverage_cli_uses_reconciled_registry_evidence(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "lund-store-coverage.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    engine.dispose()
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--fixture",
                str(FIXTURE),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["catalog_requests"] == 0
    assert payload["physical_validation_required"] is False
    assert payload["discovery"]["physical_stores"] == 23
    assert payload["coverage"]["physical_stores"] == 23
    assert payload["coverage"]["official_evidence"] == "persisted_registry"
    assert payload["coverage"]["chains"]["citygross"]["official_physical_stores"] == 0
    hemkop = payload["coverage"]["chains"]["hemkop"]
    assert any(
        row["external_store_id"] == "4123" and row["name"] == "Hemköp Lund Karhögstorg"
        for row in hemkop["stores"]
    )


def test_audit_store_coverage_cli_links_credential_free_primat_context(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "lund-external-context.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    engine.dispose()
    context_export = tmp_path / "contexts.json"
    observed_at = datetime.now(tz=UTC)
    context_export.write_text(
        json.dumps(
            {
                "schema": "grocery-context-evidence-bundle-v1",
                "postal_code": "22350",
                "captured_at": observed_at.isoformat(),
                "items": [
                    {
                        "schema": "grocery-context-evidence-v1",
                        "provider": "primat",
                        "source_channel": "catalog",
                        "context_id": "primat:ica:2771",
                        "chain": "ica",
                        "name": "ICA Kvantum Malmborgs Clemenstorget",
                        "city": "Lund",
                        "price_context_type": "physical_store",
                        "coverage": "full_catalog",
                        "source_snapshot_id": "primat-licensed-observation",
                        "source_observed_at": observed_at.isoformat(),
                        "connector_status": "healthy",
                        "physical_identity": {
                            "basis": "official_external_id",
                            "official_external_store_id": "2771",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--fixture",
                str(FIXTURE),
                "--context-export",
                str(context_export),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    decisions = payload["context_reconciliation"]["decisions"]

    assert any(
        row["physical_store_id"] == "physical:ica:1004409"
        and row["grocery_context_id"] == "primat:ica:2771"
        and row["source_provider"] == "primat"
        for row in decisions
    )
    assert payload["coverage"]["chains"]["ica"]["basket_capable_contexts"] == 1


def test_context_import_only_uses_physical_lkg_without_touching_discovery(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "lund-context-import-only.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    engine.dispose()
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--fixture",
                str(FIXTURE),
            ]
        )
        == 0
    )
    capsys.readouterr()

    def persisted_state(table: str, order_by: str) -> list[tuple[object, ...]]:
        connection = sqlite3.connect(database)
        try:
            return connection.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
        finally:
            connection.close()

    health_before = persisted_state("physical_store_discovery_health", "chain")
    physical_before = persisted_state("physical_stores", "id")
    assert len(health_before) == 6
    assert len(physical_before) == 23

    observed_at = datetime.now(tz=UTC)
    context_export = tmp_path / "contexts.json"
    context_export.write_text(
        json.dumps(
            {
                "schema": "grocery-context-evidence-bundle-v1",
                "postal_code": "22350",
                "captured_at": observed_at.isoformat(),
                "items": [
                    {
                        "schema": "grocery-context-evidence-v1",
                        "provider": "primat",
                        "source_channel": "catalog",
                        "context_id": "primat:ica:2771",
                        "chain": "ica",
                        "name": "ICA Kvantum Malmborgs Clemenstorget",
                        "city": "Lund",
                        "price_context_type": "physical_store",
                        "coverage": "full_catalog",
                        "source_snapshot_id": "primat-request-snapshot",
                        "source_observed_at": observed_at.isoformat(),
                        "connector_status": "healthy",
                        "physical_identity": {
                            "basis": "official_external_id",
                            "official_external_store_id": "2771",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    def fail_if_locator_factory_is_constructed(*_args, **_kwargs):
        raise AssertionError("context-import-only must not construct locator adapters")

    monkeypatch.setattr(
        "grocery_data.__main__.live_official_store_adapters",
        fail_if_locator_factory_is_constructed,
    )
    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--context-export",
                str(context_export),
                "--skip-official-discovery",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["discovery_skipped"] is True
    assert payload["context_import_only"] is True
    assert payload["store_discovery_only"] is False
    assert payload["locator_requests"] == 0
    assert payload["catalog_requests"] == 0
    assert payload["discovery"]["mode"] == "context_import_only"
    assert payload["discovery"]["skipped"] is True
    assert payload["coverage"]["physical_stores"] == 23
    assert payload["coverage"]["official_evidence"] == "persisted_registry"
    assert payload["coverage"]["chains"]["ica"]["basket_capable_contexts"] == 1
    assert health_before == persisted_state("physical_store_discovery_health", "chain")
    assert physical_before == persisted_state("physical_stores", "id")

    connection = sqlite3.connect(database)
    try:
        link = connection.execute(
            """
            SELECT physical_store_id, grocery_context_id, source_provider, is_active
            FROM store_context_links
            WHERE grocery_context_id = 'primat:ica:2771'
            """
        ).fetchone()
    finally:
        connection.close()
    assert link == ("physical:ica:1004409", "primat:ica:2771", "primat", 1)


def test_context_import_only_requires_context_export(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--skip-official-discovery",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "error_type": "ValueError",
    }


def test_audit_store_coverage_rejects_non_closed_context_root(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "lund-rejected-context.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    engine.dispose()
    context_export = tmp_path / "contexts.json"
    context_export.write_text(
        json.dumps(
            {
                "schema": "grocery-context-evidence-bundle-v1",
                "postal_code": "22350",
                "captured_at": datetime.now(tz=UTC).isoformat(),
                "items": [],
                "authorization": "Bearer must-not-be-accepted-or-logged",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--fixture",
                str(FIXTURE),
                "--context-export",
                str(context_export),
            ]
        )
        == 2
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "status": "failed",
        "error_type": "ValidationError",
    }
    assert "must-not-be-accepted-or-logged" not in output


def test_ica_only_audit_refreshes_alias_without_retiring_other_chain_lkg(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "lund-ica-only.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    engine.dispose()
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--fixture",
                str(FIXTURE),
            ]
        )
        == 0
    )
    capsys.readouterr()
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            UPDATE physical_stores
            SET external_store_aliases = '[]'
            WHERE id = 'physical:ica:1004409'
            """
        )
        connection.commit()
    finally:
        connection.close()

    ica_only_fixture = tmp_path / "official-stores-ica-only-proof.json"
    fixture_payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    fixture_payload["chains"]["hemkop"].pop("stores")
    ica_only_fixture.write_text(json.dumps(fixture_payload), encoding="utf-8")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--chain",
                "ica",
                "--fixture",
                str(ica_only_fixture),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["chain_scope"] == "ica"
    assert set(result["discovery"]["results"]) == {"ica"}
    assert result["discovery"]["errors"] == {}
    assert result["coverage"]["physical_stores"] == 23
    assert result["coverage"]["chains"]["hemkop"]["official_physical_stores"] == 2

    connection = sqlite3.connect(database)
    try:
        aliases = connection.execute(
            """
            SELECT external_store_aliases
            FROM physical_stores
            WHERE id = 'physical:ica:1004409'
            """
        ).fetchone()[0]
    finally:
        connection.close()
    assert json.loads(aliases) == ["2771"]


def test_audit_store_coverage_cli_keeps_chain_lkg_when_one_locator_fails(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "lund-store-lkg.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    engine.dispose()
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--fixture",
                str(FIXTURE),
            ]
        )
        == 0
    )
    capsys.readouterr()

    failed_fixture = tmp_path / "official-stores-one-failed.json"
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["chains"]["hemkop"].pop("stores")
    failed_fixture.write_text(json.dumps(payload), encoding="utf-8")

    assert (
        cli_main(
            [
                "audit-store-coverage",
                "--city",
                "Lund",
                "--fixture",
                str(failed_fixture),
            ]
        )
        == 2
    )
    result = json.loads(capsys.readouterr().out)
    hemkop = result["coverage"]["chains"]["hemkop"]

    assert result["coverage"]["official_evidence"] == "persisted_registry"
    assert result["discovery"]["errors"]["hemkop"] == (
        "ValueError: schema_or_identity_contract_failed"
    )
    assert result["coverage"]["discovery_health"]["hemkop"]["status"] == "broken"
    assert hemkop["official_physical_stores"] > 0
    assert any(row["external_store_id"] == "4123" for row in hemkop["stores"])
