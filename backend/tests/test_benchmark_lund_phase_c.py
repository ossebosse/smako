from __future__ import annotations

import hashlib
import json
import socket
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import scripts.benchmark_lund_phase_c as lund_benchmark
from app.errors import PriceProviderError
from app.models import SourceProvenance, Store
from app.providers.primat import PrimatPriceProvider
from scripts.benchmark_lund_phase_c import (
    HISTORICAL_OLD_LUND_RESULT,
    REPRESENTATIVE_REQUIREMENTS,
    _BoundedPrimatProvider,
    _exact_external_contexts,
    _exclude_terminal_provider_contexts,
    _file_state,
    _network_disabled,
    _provenance_gate,
    _read_only_engine,
    _readiness,
    _TerminalContextFilteredProvider,
    _walk_cache,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _readiness_database(path: Path, *, complete: bool) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE catalog_snapshots (
                id TEXT PRIMARY KEY,
                chain TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                coverage TEXT NOT NULL,
                state TEXT NOT NULL,
                is_active INTEGER NOT NULL,
                promoted_at TEXT
            );
            CREATE TABLE connector_health (chain TEXT);
            CREATE TABLE price_observations (id TEXT);
            CREATE TABLE products (id TEXT);
            CREATE TABLE source_products (id TEXT);
            CREATE TABLE stores (
                id TEXT PRIMARY KEY,
                chain TEXT NOT NULL,
                external_id TEXT NOT NULL,
                name TEXT NOT NULL,
                city TEXT NOT NULL,
                coverage TEXT NOT NULL,
                is_active INTEGER NOT NULL
            );
            """
        )
        snapshots = [
            ("w", "willys", "lund", "full_catalog", "promoted", 1),
        ]
        stores = [
            ("w1", "willys", "2176", "Willys Lund", "Lund", "full_catalog", 1),
            ("w2", "willys", "2354", "Willys Lund Nova", "Lund", "full_catalog", 1),
        ]
        if complete:
            snapshots.extend(
                [
                    (
                        "h1",
                        "hemkop",
                        "lund:hemkop:4123",
                        "full_online_catalog",
                        "promoted",
                        1,
                    ),
                    (
                        "h2",
                        "hemkop",
                        "lund:hemkop:4224",
                        "full_online_catalog",
                        "promoted",
                        1,
                    ),
                ]
            )
            stores.extend(
                [
                    (
                        "h1",
                        "hemkop",
                        "4123",
                        "Hemköp Karhögstorg",
                        "Lund",
                        "full_online_catalog",
                        1,
                    ),
                    (
                        "h2",
                        "hemkop",
                        "4224",
                        "Hemköp Brunnshög",
                        "Lund",
                        "full_online_catalog",
                        1,
                    ),
                ]
            )
        connection.executemany(
            """
            INSERT INTO catalog_snapshots
            (id, chain, scope_key, coverage, state, is_active, promoted_at)
            VALUES (?, ?, ?, ?, ?, ?, '2026-08-23T00:00:00+00:00')
            """,
            snapshots,
        )
        connection.executemany(
            """
            INSERT INTO stores
            (id, chain, external_id, name, city, coverage, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            stores,
        )
        connection.commit()
    finally:
        connection.close()


def _external_context_tables(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE physical_stores (
                id TEXT PRIMARY KEY,
                chain TEXT NOT NULL,
                external_store_id TEXT,
                city TEXT NOT NULL,
                is_active INTEGER NOT NULL
            );
            CREATE TABLE store_context_links (
                physical_store_id TEXT NOT NULL,
                grocery_context_id TEXT NOT NULL,
                source_provider TEXT NOT NULL,
                source_channel TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                confidence TEXT NOT NULL,
                evidence TEXT,
                coverage TEXT,
                basket_eligible INTEGER NOT NULL,
                offers_only INTEGER NOT NULL,
                snapshot_id TEXT,
                observed_at TEXT,
                is_active INTEGER NOT NULL
            );
            CREATE TABLE provider_store_identity_mappings (
                physical_store_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                provider_context_id TEXT,
                candidate_context_id TEXT,
                confidence TEXT NOT NULL,
                status TEXT NOT NULL,
                evidence TEXT,
                verified_at TEXT,
                last_checked_at TEXT NOT NULL,
                is_active INTEGER NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO physical_stores VALUES (?, ?, ?, 'Lund', 1)",
            [
                ("ica-site", "ica", "ica-official"),
                ("coop-site", "coop", "coop-official"),
                ("lidl-site", "lidl", "lidl-official"),
            ],
        )
        common = (
            "primat",
            "catalog",
            "exact_store_online_context",
        )
        connection.executemany(
            """
            INSERT INTO store_context_links
            (physical_store_id, grocery_context_id, source_provider, source_channel,
             relation_type, confidence, evidence, coverage, basket_eligible,
             offers_only, snapshot_id, observed_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'full_catalog', 1, 0, 'snapshot',
                    '2026-08-23T00:00:00+00:00', 1)
            """,
            [
                (
                    "ica-site",
                    "primat:ica-context",
                    *common,
                    "exact",
                    "official primary/alias store identity exact match",
                ),
                (
                    "coop-site",
                    "primat:coop-context",
                    *common,
                    "high",
                    "official address and postal code exact match",
                ),
                (
                    "lidl-site",
                    "primat:lidl-context",
                    *common,
                    "high",
                    "official coordinates exact match",
                ),
                (
                    "lidl-site",
                    "primat:name-only-must-not-pass",
                    *common,
                    "high",
                    "similar store name",
                ),
            ],
        )
        connection.executemany(
            """
            INSERT INTO provider_store_identity_mappings
            (physical_store_id, provider, provider_context_id, candidate_context_id,
             confidence, status, evidence, verified_at, last_checked_at, is_active)
            VALUES (?, 'primat', ?, NULL, ?, 'verified', ?,
                    '2026-08-23T00:00:00+00:00',
                    '2026-08-23T00:00:00+00:00', 1)
            """,
            [
                (
                    "ica-site",
                    "primat:ica-context",
                    "exact_id",
                    "provider store ID equals official identity",
                ),
                (
                    "coop-site",
                    "primat:coop-context",
                    "exact_address",
                    "exact normalized address and chain",
                ),
                (
                    "lidl-site",
                    "primat:lidl-context",
                    "strong_geo",
                    "unique coordinates within 75 metres",
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _add_real_own_observations(
    path: Path,
    observed_by_store: dict[str, list[datetime]],
) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            ALTER TABLE price_observations ADD COLUMN catalog_snapshot_id TEXT;
            ALTER TABLE price_observations ADD COLUMN store_id TEXT;
            ALTER TABLE price_observations ADD COLUMN observed_at TEXT;
            """
        )
        snapshot_by_store = {"w1": "w", "w2": "w", "h1": "h1", "h2": "h2"}
        rows = []
        for store_id, observed_values in observed_by_store.items():
            for index, observed_at in enumerate(observed_values):
                rows.append(
                    (
                        f"price-{store_id}-{index}",
                        snapshot_by_store[store_id],
                        store_id,
                        observed_at.isoformat(),
                    )
                )
        connection.executemany(
            """
            INSERT INTO price_observations
            (id, catalog_snapshot_id, store_id, observed_at)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def _normalized_terminal_context_database(path: Path, *, now: datetime) -> None:
    _readiness_database(path, complete=True)
    _add_real_own_observations(
        path,
        {
            "w1": [now - timedelta(hours=1)],
            "w2": [now - timedelta(hours=1)],
            "h1": [],
            "h2": [now - timedelta(hours=1)],
        },
    )
    completion = {
        "catalog_completion": {
            "4123": {
                "complete": False,
                "limited": False,
                "expected_categories": 20,
                "completed_categories": 20,
                "expected_pages": 78,
                "pages_fetched": 78,
                "expected_products": 6766,
                "raw_rows": 6766,
                "unique_products": 6068,
                "cross_partition_duplicates": 697,
                "within_partition_duplicates": 1,
                "reason": "top-level partitions overlap or exact totals did not reconcile",
            }
        }
    }
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            ALTER TABLE catalog_snapshots ADD COLUMN collector_run_id TEXT;
            ALTER TABLE catalog_snapshots ADD COLUMN metrics TEXT;
            ALTER TABLE catalog_snapshots ADD COLUMN created_at TEXT;
            ALTER TABLE catalog_snapshots ADD COLUMN rejected_at TEXT;
            ALTER TABLE catalog_snapshots ADD COLUMN rejection_reason TEXT;
            CREATE TABLE collector_runs (
                id TEXT PRIMARY KEY,
                status TEXT,
                successful INTEGER,
                error_summary TEXT
            );
            CREATE TABLE raw_snapshots (
                id TEXT PRIMARY KEY,
                catalog_snapshot_id TEXT
            );
            CREATE TABLE physical_stores (
                id TEXT PRIMARY KEY,
                chain TEXT NOT NULL,
                external_store_id TEXT,
                name TEXT NOT NULL,
                city TEXT,
                is_active INTEGER NOT NULL
            );
            CREATE TABLE store_context_links (
                physical_store_id TEXT NOT NULL,
                grocery_context_id TEXT NOT NULL,
                source_provider TEXT NOT NULL,
                source_channel TEXT NOT NULL,
                local_store_id TEXT,
                price_context_type TEXT,
                coverage TEXT,
                relation_type TEXT,
                confidence TEXT,
                evidence TEXT,
                basket_eligible INTEGER NOT NULL,
                offers_only INTEGER NOT NULL,
                snapshot_id TEXT,
                observed_at TEXT,
                is_active INTEGER NOT NULL
            );
            """
        )
        connection.execute(
            """
            UPDATE catalog_snapshots
            SET created_at = ?, metrics = '{}'
            """,
            ((now - timedelta(hours=2)).isoformat(),),
        )
        connection.execute(
            """
            UPDATE catalog_snapshots
            SET state = 'rejected', is_active = 0, collector_run_id = 'run-4123',
                metrics = ?, created_at = ?, rejected_at = ?,
                rejection_reason = 'ConnectorFetchError'
            WHERE id = 'h1'
            """,
            (
                json.dumps(completion),
                (now - timedelta(minutes=20)).isoformat(),
                (now - timedelta(minutes=5)).isoformat(),
            ),
        )
        connection.execute("UPDATE stores SET is_active = 0 WHERE id = 'h1'")
        connection.execute(
            "INSERT INTO collector_runs VALUES ('run-4123', 'failed', 0, 'ConnectorFetchError')"
        )
        connection.execute("INSERT INTO raw_snapshots VALUES ('raw-4123', 'h1')")
        connection.executemany(
            "INSERT INTO physical_stores VALUES (?, 'hemkop', ?, ?, 'Lund', 1)",
            [
                ("physical:hemkop:4123", "4123", "Hemköp Lund Karhögstorg"),
                ("physical:hemkop:4224", "4224", "Hemköp Lund Brunnshög"),
            ],
        )
        connection.executemany(
            """
            INSERT INTO store_context_links
            (physical_store_id, grocery_context_id, source_provider, source_channel,
             local_store_id, price_context_type, coverage, relation_type, confidence,
             evidence, basket_eligible, offers_only, snapshot_id, observed_at, is_active)
            VALUES (?, ?, 'own', 'catalog', ?, 'online_store', 'full_online_catalog',
                    'exact_store_online_context', 'exact',
                    'official primary/alias store identity exact match', ?, 0, ?, ?, 1)
            """,
            [
                (
                    "physical:hemkop:4123",
                    "own:hemkop:4123",
                    None,
                    0,
                    None,
                    None,
                ),
                (
                    "physical:hemkop:4224",
                    "own:hemkop:4224",
                    "h2",
                    1,
                    "h2",
                    (now - timedelta(hours=1)).isoformat(),
                ),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_historical_result_never_manufactures_an_incomplete_total() -> None:
    basket = HISTORICAL_OLD_LUND_RESULT["representative_basket"]

    assert basket["complete_for_request"] is False
    assert basket["missing_ingredients"] == ["yellow_onion"]
    assert basket["total_sek"] is None
    assert [row.canonical for row in REPRESENTATIVE_REQUIREMENTS] == [
        "milk",
        "eggs",
        "potato",
        "ris",
        "pasta",
        "chicken_meat",
        "minced_beef",
        "yellow_onion",
        "carrot",
        "krossade_tomater",
        "cheese",
        "creme_fraiche",
        "red_lentils",
    ]


@pytest.mark.asyncio
async def test_menu_matrix_runs_all_modes_and_store_limits_on_one_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = object()
    calls: list[tuple[object, str, int, tuple[dict[str, str], ...]]] = []
    terminal_gaps = ({"chain": "hemkop", "external_id": "4123"},)

    async def fake_menu_plan(
        passed_provider: object,
        *,
        postal_code: str,
        candidate_count: int,
        beam_width: int,
        diversity_mode: str,
        max_stores: int,
        terminal_context_gaps: tuple[dict[str, str], ...],
    ) -> dict[str, object]:
        assert postal_code == "22350"
        assert candidate_count == 80
        assert beam_width == 30
        calls.append((passed_provider, diversity_mode, max_stores, terminal_context_gaps))
        return {
            "status": "PASS",
            "scenario": {
                "diversity_mode": diversity_mode,
                "max_stores": max_stores,
            },
        }

    monkeypatch.setattr(lund_benchmark, "_menu_plan", fake_menu_plan)

    result = await lund_benchmark._menu_matrix(
        provider,
        postal_code="22350",
        candidate_count=80,
        beam_width=30,
        terminal_context_gaps=terminal_gaps,
    )

    assert list(result) == ["cheapest", "balanced", "varied"]
    assert all(list(rows) == ["max_stores_1", "max_stores_2"] for rows in result.values())
    assert calls == [
        (provider, mode, max_stores, terminal_gaps)
        for mode in ("cheapest", "balanced", "varied")
        for max_stores in (1, 2)
    ]


def test_phase_c_readiness_requires_both_exact_hemkop_contexts(tmp_path: Path) -> None:
    incomplete = tmp_path / "incomplete.sqlite"
    complete = tmp_path / "complete.sqlite"
    _readiness_database(incomplete, complete=False)
    _readiness_database(complete, complete=True)

    incomplete_report = _readiness(incomplete, mode="own-only", external_cache=None)
    complete_report = _readiness(complete, mode="own-only", external_cache=None)

    assert incomplete_report["ready"] is False
    assert any("4123" in reason for reason in incomplete_report["reasons"])
    assert any("4224" in reason for reason in incomplete_report["reasons"])
    assert complete_report["ready"] is True
    assert complete_report["reasons"] == []
    assert complete_report["freshness"]["own"]["enforced"] is False
    assert complete_report["freshness"]["own"]["status"] == ("legacy_schema_not_evaluated")
    assert "not evidence" in complete_report["freshness"]["own"]["note"]


def test_own_readiness_uses_oldest_promoted_price_row_conservatively(
    tmp_path: Path,
) -> None:
    database = tmp_path / "freshness.sqlite"
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    _readiness_database(database, complete=True)
    _add_real_own_observations(
        database,
        {
            "w1": [now - timedelta(hours=1)],
            "w2": [now - timedelta(hours=1)],
            "h1": [now - timedelta(hours=1)],
            "h2": [now - timedelta(hours=1)],
        },
    )

    fresh = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=2,
        now=now,
    )
    assert fresh["ready"] is True
    assert fresh["freshness"]["own"]["status"] == "pass"
    assert {row["freshness_status"] for row in fresh["freshness"]["own"]["contexts"]} == {"fresh"}

    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            INSERT INTO price_observations
            (id, catalog_snapshot_id, store_id, observed_at)
            VALUES ('price-w1-old', 'w', 'w1', ?)
            """,
            ((now - timedelta(hours=3)).isoformat(),),
        )
        connection.commit()
    finally:
        connection.close()

    stale = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=2,
        now=now,
    )
    w1 = next(row for row in stale["freshness"]["own"]["contexts"] if row["external_id"] == "2176")
    assert stale["ready"] is False
    assert w1["freshness_status"] == "stale"
    assert w1["data_age_hours"] == 3.0
    assert w1["price_rows"] == 2


def test_production_like_schema_missing_observed_at_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "missing-observed-at.sqlite"
    _readiness_database(database, complete=True)
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            ALTER TABLE price_observations ADD COLUMN catalog_snapshot_id TEXT;
            ALTER TABLE price_observations ADD COLUMN store_id TEXT;
            """
        )
        connection.commit()
    finally:
        connection.close()

    report = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=48,
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )

    assert report["ready"] is False
    assert report["freshness"]["own"]["enforced"] is True
    assert report["freshness"]["own"]["status"] == "schema_missing"
    assert any("freshness schema" in reason for reason in report["reasons"])


def test_terminal_hemkop_gap_is_explicit_but_does_not_block_fresh_eligible_context(
    tmp_path: Path,
) -> None:
    database = tmp_path / "terminal-gap.sqlite"
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    _normalized_terminal_context_database(database, now=now)

    report = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=4,
        now=now,
    )

    assert report["ready"] is True
    assert report["reasons"] == []
    assert [row["external_id"] for row in report["hemkop_contexts"]["eligible_contexts"]] == [
        "4224"
    ]
    assert len(report["terminal_context_gaps"]) == 1
    gap = report["terminal_context_gaps"][0]
    assert gap["external_id"] == "4123"
    assert gap["provider_eligible"] is False
    assert gap["latest_candidate"]["state"] == "rejected"
    assert gap["completion_failure_evidence"] == {
        "complete": False,
        "limited": False,
        "expected_categories": 20,
        "completed_categories": 20,
        "expected_pages": 78,
        "pages_fetched": 78,
        "expected_products": 6766,
        "raw_rows": 6766,
        "unique_products": 6068,
        "cross_partition_duplicates": 697,
        "within_partition_duplicates": 1,
        "raw_payloads": 1,
        "reason": "top-level partitions overlap or exact totals did not reconcile",
    }
    assert report["warnings"] == [
        "Hemköp Lund context 4123 is terminally unavailable and excluded from the provider universe"
    ]


@pytest.mark.parametrize(
    "failure_mode",
    ("missing_completion", "malformed_duplicates", "wrong_coverage"),
)
def test_rejected_context_without_strict_terminal_evidence_remains_not_ready(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    database = tmp_path / "unproven-rejection.sqlite"
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    _normalized_terminal_context_database(database, now=now)
    connection = sqlite3.connect(database)
    try:
        if failure_mode == "missing_completion":
            connection.execute("UPDATE catalog_snapshots SET metrics = '{}' WHERE id = 'h1'")
        elif failure_mode == "wrong_coverage":
            connection.execute(
                "UPDATE catalog_snapshots SET coverage = 'partial_catalog' WHERE id = 'h1'"
            )
        else:
            metrics = json.loads(
                connection.execute(
                    "SELECT metrics FROM catalog_snapshots WHERE id = 'h1'"
                ).fetchone()[0]
            )
            metrics["catalog_completion"]["4123"]["cross_partition_duplicates"] = "invalid"
            connection.execute(
                "UPDATE catalog_snapshots SET metrics = ? WHERE id = 'h1'",
                (json.dumps(metrics),),
            )
        connection.commit()
    finally:
        connection.close()

    report = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=4,
        now=now,
    )

    assert report["ready"] is False
    assert report["terminal_context_gaps"] == []
    assert report["hemkop_contexts"]["unresolved_contexts"][0]["external_id"] == "4123"
    assert any("4123 is unresolved" in reason for reason in report["reasons"])


def test_arbitrary_unmapped_physical_hemkop_context_remains_not_ready(
    tmp_path: Path,
) -> None:
    database = tmp_path / "unmapped-physical.sqlite"
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    _normalized_terminal_context_database(database, now=now)
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            INSERT INTO physical_stores
            VALUES ('physical:hemkop:4999', 'hemkop', '4999',
                    'Hemköp Lund Unattempted', 'Lund', 1)
            """
        )
        connection.commit()
    finally:
        connection.close()

    report = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=4,
        now=now,
    )

    assert report["ready"] is False
    assert report["hemkop_contexts"]["expected_contexts"] == 3
    unresolved = report["hemkop_contexts"]["unresolved_contexts"]
    assert any(row["external_id"] == "4999" for row in unresolved)


def test_at_least_one_promoted_fresh_hemkop_context_is_required(tmp_path: Path) -> None:
    database = tmp_path / "no-eligible-hemkop.sqlite"
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    _normalized_terminal_context_database(database, now=now)
    connection = sqlite3.connect(database)
    try:
        connection.execute("UPDATE stores SET is_active = 0 WHERE id = 'h2'")
        connection.commit()
    finally:
        connection.close()

    report = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=4,
        now=now,
    )

    assert report["ready"] is False
    assert report["hemkop_contexts"]["eligible_contexts"] == []
    assert any("no promoted fresh" in reason for reason in report["reasons"])


def test_terminal_context_is_removed_before_provider_universe() -> None:
    stores = [
        Store(
            store_id="context:hemkop:4123",
            source_store_id="4123",
            name="Hemköp Lund Karhögstorg",
            chain="hemkop",
            city="Lund",
        ),
        Store(
            store_id="context:hemkop:4224",
            source_store_id="4224",
            name="Hemköp Lund Brunnshög",
            chain="hemkop",
            city="Lund",
        ),
    ]

    eligible, rejected = _exclude_terminal_provider_contexts(
        stores,
        [{"chain": "hemkop", "external_id": "4123"}],
    )

    assert [store.source_store_id for store in eligible] == ["4224"]
    assert rejected == [
        {
            "chain": "hemkop",
            "external_id": "4123",
            "context_id": "context:hemkop:4123",
        }
    ]


@pytest.mark.asyncio
async def test_terminal_context_filter_applies_to_complete_provider_request_scope() -> None:
    stores = [
        Store(
            store_id="context:hemkop:4123",
            source_store_id="4123",
            name="Hemköp Lund Karhögstorg",
            chain="hemkop",
            city="Lund",
        ),
        Store(
            store_id="context:hemkop:4224",
            source_store_id="4224",
            name="Hemköp Lund Brunnshög",
            chain="hemkop",
            city="Lund",
        ),
    ]

    class Provider:
        diagnostics = ("diagnostic",)

        def __init__(self) -> None:
            self.requested_store_ids: list[str] = []

        async def find_stores(self, _postal_code: str) -> list[Store]:
            return stores

        async def search_products(
            self,
            _query: str,
            store_ids: list[str],
        ) -> list[SimpleNamespace]:
            self.requested_store_ids = store_ids
            # The second row simulates a provider violating its requested
            # scope; the facade must still fail closed at the product edge.
            return [SimpleNamespace(store_id=store.store_id) for store in stores]

    provider = Provider()
    filtered = _TerminalContextFilteredProvider(
        provider,
        [{"chain": "hemkop", "external_id": "4123"}],
    )

    discovered = await filtered.find_stores("22350")
    products = await filtered.search_products(
        "milk",
        ["context:hemkop:4123", "context:hemkop:4224"],
    )

    assert [store.source_store_id for store in discovered] == ["4224"]
    assert provider.requested_store_ids == ["context:hemkop:4224"]
    assert [product.store_id for product in products] == ["context:hemkop:4224"]
    assert filtered.diagnostics == ("diagnostic",)
    assert filtered.rejected_contexts == [
        {
            "chain": "hemkop",
            "external_id": "4123",
            "context_id": "context:hemkop:4123",
        }
    ]


@pytest.mark.parametrize(
    ("unsafe_value", "expected_status"),
    [
        ("future", "future"),
        ("missing", "missing"),
    ],
)
def test_own_readiness_fails_closed_for_future_or_missing_observations(
    tmp_path: Path,
    unsafe_value: str,
    expected_status: str,
) -> None:
    database = tmp_path / f"own-{unsafe_value}.sqlite"
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    _readiness_database(database, complete=True)
    _add_real_own_observations(
        database,
        {
            "w1": [] if unsafe_value == "missing" else [now + timedelta(seconds=1)],
            "w2": [now - timedelta(hours=1)],
            "h1": [now - timedelta(hours=1)],
            "h2": [now - timedelta(hours=1)],
        },
    )

    report = _readiness(
        database,
        mode="own-only",
        external_cache=None,
        max_age_hours=2,
        now=now,
    )
    w1 = next(row for row in report["freshness"]["own"]["contexts"] if row["external_id"] == "2176")

    assert report["ready"] is False
    assert w1["freshness_status"] == expected_status
    assert w1["eligible"] is False


def test_federated_readiness_requires_persisted_exact_external_links(tmp_path: Path) -> None:
    database = tmp_path / "complete-own.sqlite"
    cache = tmp_path / "external.json"
    _readiness_database(database, complete=True)
    cache.write_text("{}", encoding="utf-8")

    report = _readiness(database, mode="federated", external_cache=cache)

    assert report["ready"] is False
    assert "normalized physical-store/context link tables are missing" in report["reasons"]


def test_federated_readiness_accepts_only_allowlisted_structured_exact_links(
    tmp_path: Path,
) -> None:
    database = tmp_path / "complete-federated.sqlite"
    cache = tmp_path / "external.json"
    _readiness_database(database, complete=True)
    _external_context_tables(database)
    cache.write_text("{}", encoding="utf-8")

    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    report = _readiness(
        database,
        mode="federated",
        external_cache=cache,
        max_age_hours=48,
        now=now,
    )
    contexts = _exact_external_contexts(database, max_age_hours=48, now=now)

    assert report["ready"] is True
    assert {row["chain"] for row in report["exact_external_context_links"]} == {
        "ica",
        "coop",
        "lidl",
    }
    assert ("coop", "primat:coop-context") in contexts
    assert ("lidl", "primat:lidl-context") in contexts
    assert ("lidl", "primat:name-only-must-not-pass") not in contexts


def test_primat_context_freshness_excludes_ineligible_provider_contexts(
    tmp_path: Path,
) -> None:
    database = tmp_path / "unsafe-external.sqlite"
    cache = tmp_path / "external.json"
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    _readiness_database(database, complete=True)
    _external_context_tables(database)
    cache.write_text("{}", encoding="utf-8")
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "UPDATE store_context_links SET observed_at = NULL WHERE grocery_context_id = ?",
            ("primat:ica-context",),
        )
        connection.execute(
            "UPDATE store_context_links SET observed_at = ? WHERE grocery_context_id = ?",
            ((now - timedelta(hours=3)).isoformat(), "primat:coop-context"),
        )
        connection.execute(
            "UPDATE store_context_links SET observed_at = ? WHERE grocery_context_id = ?",
            ((now + timedelta(seconds=1)).isoformat(), "primat:lidl-context"),
        )
        connection.commit()
    finally:
        connection.close()

    report = _readiness(
        database,
        mode="federated",
        external_cache=cache,
        max_age_hours=2,
        now=now,
    )
    contexts = _exact_external_contexts(database, max_age_hours=2, now=now)
    statuses = {
        row["chain"]: row["freshness_status"] for row in report["freshness"]["primat_context_links"]
    }

    assert report["ready"] is True
    assert statuses == {"ica": "missing", "coop": "stale", "lidl": "future"}
    assert contexts == frozenset()
    assert any("missing observation time" in warning for warning in report["warnings"])
    assert any("stale observation time" in warning for warning in report["warnings"])
    assert any("future observation time" in warning for warning in report["warnings"])


def test_federated_readiness_requires_closed_identity_explanation_per_store(
    tmp_path: Path,
) -> None:
    database = tmp_path / "unexplained-external.sqlite"
    cache = tmp_path / "external.json"
    _readiness_database(database, complete=True)
    _external_context_tables(database)
    cache.write_text("{}", encoding="utf-8")
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            "DELETE FROM provider_store_identity_mappings WHERE physical_store_id = 'coop-site'"
        )
        connection.commit()
    finally:
        connection.close()

    report = _readiness(database, mode="federated", external_cache=cache)

    assert report["ready"] is False
    assert any(
        "coop physical store coop-site has no persisted closed mapping explanation" in reason
        for reason in report["reasons"]
    )


def test_read_only_engine_uses_temp_legacy_projection_without_source_write(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(database)
    try:
        connection.execute(
            """
            CREATE TABLE stores (
                id TEXT PRIMARY KEY,
                chain TEXT,
                external_id TEXT,
                name TEXT,
                address TEXT,
                postal_code TEXT,
                city TEXT,
                latitude NUMERIC,
                longitude NUMERIC,
                online_shopping INTEGER,
                coverage TEXT,
                raw_reference TEXT,
                is_active INTEGER,
                first_seen_at TEXT,
                last_seen_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO stores VALUES
            ('w', 'willys', '2176', 'Willys Lund', NULL, '22643', 'Lund', NULL,
             NULL, 1, 'full_catalog', 'raw://fixture', 1,
             '2026-08-23T00:00:00+00:00', '2026-08-23T00:00:00+00:00')
            """
        )
        connection.commit()
    finally:
        connection.close()
    before = _sha256(database)

    engine, factory, compatibility = _read_only_engine(database)
    try:
        with factory() as session:
            row = session.execute(
                __import__("sqlalchemy").text(
                    "SELECT external_id, price_context_type, physical_store_external_id FROM stores"
                )
            ).one()
    finally:
        engine.dispose()

    assert compatibility is True
    assert tuple(row) == ("2176", None, None)
    assert _sha256(database) == before
    assert not database.with_name(database.name + "-wal").exists()
    assert not database.with_name(database.name + "-shm").exists()
    assert not database.with_name(database.name + "-journal").exists()


def test_network_guard_blocks_and_counts_socket_resolution() -> None:
    original = socket.getaddrinfo

    with (
        _network_disabled() as attempts,
        pytest.raises(
            RuntimeError,
            match="network disabled",
        ),
    ):
        socket.getaddrinfo("example.com", 443)

    assert attempts["count"] == 1
    assert socket.getaddrinfo is original


def test_frozen_cache_rejects_credential_or_session_keys() -> None:
    with pytest.raises(ValueError, match="forbidden key"):
        _walk_cache({"products": [], "request": {"Authorization": "Bearer secret"}})
    with pytest.raises(ValueError, match="forbidden key"):
        _walk_cache({"stores": [], "sessionId": "secret"})


@pytest.mark.asyncio
async def test_bounded_primat_transport_requires_official_https_host_and_starts_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRIMAT_API_KEY", "fixture-key")
    monkeypatch.setenv("PRIMAT_BASE_URL", "https://not-primat.example/api/v3")
    with pytest.raises(ValueError, match="HTTPS primat.nu"):
        _BoundedPrimatProvider.load(exact_contexts=frozenset(), max_requests=4)

    monkeypatch.setenv("PRIMAT_BASE_URL", "https://primat.nu/api/v3")
    provider = _BoundedPrimatProvider.load(exact_contexts=frozenset(), max_requests=4)
    try:
        assert provider.transport_report == {
            "mode": "bounded_primat_live",
            "request_limit": 4,
            "requests": 0,
            "endpoints": {},
            "statuses": {},
            "denied_requests": 0,
            "max_concurrency": 1,
        }
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_bounded_primat_find_stores_is_request_scoped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store(
        store_id="ica:100",
        source_store_id="100",
        name="ICA Lund",
        chain="ica",
        city="Lund",
        postal_code="22350",
        coverage="full_catalog",
    )
    calls: list[str] = []

    async def fake_find_stores(
        _provider: PrimatPriceProvider,
        postal_code: str,
    ) -> list[Store]:
        calls.append(postal_code)
        return [store]

    monkeypatch.setenv("PRIMAT_API_KEY", "fixture-key")
    monkeypatch.setenv("PRIMAT_BASE_URL", "https://primat.nu/api/v3")
    monkeypatch.setattr(PrimatPriceProvider, "find_stores", fake_find_stores)
    provider = _BoundedPrimatProvider.load(
        exact_contexts=frozenset({("ica", "primat:ica:100")}),
        max_requests=4,
    )
    try:
        first = await provider.find_stores("223 50")
        second = await provider.find_stores("22350")
        with pytest.raises(PriceProviderError, match="cannot switch postal code"):
            await provider.find_stores("21100")

        assert calls == ["22350"]
        assert [row.store_id for row in first] == ["ica:100"]
        assert second == first
        assert second is not first
        assert provider.transport_report["requests"] == 0
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_bounded_primat_context_bootstrap_is_store_only_and_cap_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store(
        store_id="coop:200",
        source_store_id="200",
        name="Coop Lund",
        chain="coop",
        city="Lund",
        postal_code="22350",
        coverage="full_catalog",
    )
    calls = 0

    async def fake_find_stores(
        _provider: PrimatPriceProvider,
        _postal_code: str,
    ) -> list[Store]:
        nonlocal calls
        calls += 1
        return [store]

    monkeypatch.setenv("PRIMAT_API_KEY", "fixture-key")
    monkeypatch.setenv("PRIMAT_BASE_URL", "https://primat.nu/api/v3")
    monkeypatch.setattr(PrimatPriceProvider, "find_stores", fake_find_stores)

    with pytest.raises(ValueError, match="requires max_requests=1"):
        _BoundedPrimatProvider.load(max_requests=2, context_bootstrap=True)

    provider = _BoundedPrimatProvider.load(max_requests=1, context_bootstrap=True)
    try:
        assert await provider.find_stores("22350") == [store]
        assert await provider.find_stores("22350") == [store]
        assert calls == 1
        with pytest.raises(PriceProviderError, match="store resolution only"):
            await provider.search_products("mjölk", [store.store_id])
        with pytest.raises(PriceProviderError, match="store resolution only"):
            await provider.get_store_products(store.store_id)
        with pytest.raises(PriceProviderError, match="store resolution only"):
            await provider.get_offers(store.store_id)
        assert provider.transport_report == {
            "mode": "primat_context_bootstrap",
            "request_limit": 1,
            "requests": 0,
            "endpoints": {},
            "statuses": {},
            "denied_requests": 0,
            "max_concurrency": 1,
        }
    finally:
        await provider.aclose()


def test_willys_provenance_requires_online_store_context() -> None:
    base = {
        "source_provider": "own",
        "source_channel": "catalog",
        "source_snapshot_id": "snapshot-willys",
        "source_observed_at": datetime.now(tz=UTC),
        "chain": "willys",
        "store_id": "context:willys:1",
        "store_name": "Willys Lund",
        "coverage": "full_catalog",
        "semantic_confidence": "high",
        "quantity_confidence": "exact",
    }
    missing = SimpleNamespace(
        product_id="p1",
        store_id="context:willys:1",
        applied_offer=None,
        semantic_confidence=SimpleNamespace(value="high"),
        quantity_confidence=SimpleNamespace(value="exact"),
        source_provenance=SourceProvenance(**base, price_context="physical_store"),
    )
    correct = SimpleNamespace(
        product_id="p1",
        store_id="context:willys:1",
        applied_offer=None,
        semantic_confidence=SimpleNamespace(value="high"),
        quantity_confidence=SimpleNamespace(value="exact"),
        source_provenance=SourceProvenance(**base, price_context="online_store"),
    )

    failed = _provenance_gate([missing])
    passed = _provenance_gate([correct])

    assert failed["status"] == "FAIL"
    assert failed["missing"][0]["fields"] == ["willys_price_context_must_be_online_store"]
    assert passed["status"] == "PASS"


def test_file_state_is_stable_for_an_untouched_database(tmp_path: Path) -> None:
    database = tmp_path / "snapshot.sqlite"
    database.write_bytes(b"immutable fixture")

    before = _file_state(database)
    after = _file_state(database)

    assert before == after
    assert json.dumps(before, sort_keys=True)
