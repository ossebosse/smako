"""Replay the Lund Phase-C benchmarks without touching a live source.

The script deliberately opens every grocery-data SQLite file with both
``mode=ro`` and ``immutable=1``.  It serves that database to the existing OWN
adapter through an in-process ASGI transport, then runs the ordinary federated
provider, semantic matcher, quantity resolver, basket optimizer and meal-plan
quality gates.  Socket access is disabled for the complete run.

``federated`` mode normally accepts only a credential-free frozen external
cache. One separately named operator opt-in can construct a tightly bounded
``PrimatPriceProvider`` for the acceptance run; it is never mistaken for an
offline replay.

Run from the repository root, for example::

    python backend/scripts/benchmark_lund_phase_c.py --mode own-only

    python backend/scripts/benchmark_lund_phase_c.py \
        --mode federated --external-cache path/to/sanitized-primat-cache.json

The old Lund result is retained as historical evidence: it was incomplete for
``yellow_onion`` and consequently had no valid total.  A current-code replay of
the old immutable database is reported separately so matcher changes are not
misrepresented as the historical result.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import socket
import sqlite3
import sys
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for import_root in (PROJECT_ROOT, BACKEND_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

_CENT = Decimal("0.01")
_FULL_COVERAGE = frozenset({"full_catalog", "full_online_catalog"})
_OWN_CHAINS = frozenset({"willys", "hemkop", "citygross", "coop"})
_EXTERNAL_CHAINS = frozenset({"ica", "coop", "lidl", "willys", "hemkop", "citygross"})
_REQUIRED_PROVENANCE_FIELDS = (
    "source_provider",
    "source_channel",
    "source_snapshot_id",
    "source_observed_at",
    "chain",
    "store_id",
    "store_name",
    "price_context",
    "coverage",
    "semantic_confidence",
    "quantity_confidence",
)
_FORBIDDEN_CACHE_KEY = re.compile(
    r"(?:authorization|cookie|set_cookie|api[_-]?key|access[_-]?token|"
    r"refresh[_-]?token|client[_-]?secret|session|clearance)",
    flags=re.IGNORECASE,
)
_STRUCTURED_EXACT_LINK_EVIDENCE = frozenset(
    {
        "official primary/alias store identity exact match",
        "official primary/alias context identity exact match",
        "official address and postal code exact match",
        "official coordinates exact match",
    }
)
_STRONG_PROVIDER_MAPPING_CONFIDENCE = frozenset(
    {"exact_id", "exact_address", "exact_name_and_postal", "strong_geo"}
)


@dataclass(frozen=True, slots=True)
class RepresentativeRequirement:
    canonical: str
    quantity: float
    unit: str


# This is the same canonical 13-item surface as CatalogRecipeCoverageBenchmark.
# Amounts are explicit so every price total has stable, auditable basket math.
REPRESENTATIVE_REQUIREMENTS: tuple[RepresentativeRequirement, ...] = (
    RepresentativeRequirement("milk", 1000, "ml"),
    RepresentativeRequirement("eggs", 12, "st"),
    RepresentativeRequirement("potato", 1000, "g"),
    RepresentativeRequirement("ris", 1000, "g"),
    RepresentativeRequirement("pasta", 1000, "g"),
    RepresentativeRequirement("chicken_meat", 1000, "g"),
    RepresentativeRequirement("minced_beef", 500, "g"),
    RepresentativeRequirement("yellow_onion", 1000, "g"),
    RepresentativeRequirement("carrot", 1000, "g"),
    RepresentativeRequirement("krossade_tomater", 400, "g"),
    RepresentativeRequirement("cheese", 500, "g"),
    RepresentativeRequirement("creme_fraiche", 500, "ml"),
    RepresentativeRequirement("red_lentils", 500, "g"),
)

HISTORICAL_OLD_LUND_RESULT: dict[str, Any] = {
    "evidence_kind": "historical_recorded_benchmark",
    "database": "grocery_data_live.sqlite",
    "representative_basket": {
        "requested": 13,
        "complete_for_request": False,
        "missing_ingredients": ["yellow_onion"],
        # An incomplete basket has no economically meaningful comparable total.
        "total_sek": None,
    },
    "note": (
        "The recorded OLD Lund run failed yellow_onion. Its total is intentionally null; "
        "a current-code replay is reported as a separate measurement."
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Offline immutable Lund benchmark: representative basket and the complete "
            "5x4 CHEAPEST/BALANCED/VARIED matrix."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("own-only", "federated"),
        default="own-only",
        help="Federated mode additionally requires --external-cache; neither mode uses network.",
    )
    parser.add_argument(
        "--database",
        choices=("baseline", "candidate", "both"),
        default="candidate",
        help=(
            "Immutable snapshot to replay (default candidate; historical OLD facts are always "
            "included without rerunning a stale baseline)."
        ),
    )
    parser.add_argument(
        "--baseline-db",
        type=Path,
        default=PROJECT_ROOT / "grocery_data_live.sqlite",
    )
    parser.add_argument(
        "--candidate-db",
        type=Path,
        default=PROJECT_ROOT / ".lund_phase_c_20260823.sqlite",
    )
    parser.add_argument("--external-cache", type=Path)
    parser.add_argument(
        "--allow-bounded-primat-live",
        action="store_true",
        help=(
            "Explicitly allow the federated run to use Primat instead of a frozen cache. "
            "Credentials are read only from environment configuration."
        ),
    )
    parser.add_argument(
        "--primat-max-requests",
        type=int,
        default=64,
        help="Hard request ceiling for explicit bounded Primat mode (default 64).",
    )
    parser.add_argument(
        "--frozen-cache-output",
        type=Path,
        help=(
            "Optional closed replay-cache export from the explicit bounded Primat "
            "request scope. Valid only for one candidate federated live run."
        ),
    )
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--candidate-count", type=int, default=80)
    parser.add_argument("--beam-width", type=int, default=30)
    parser.add_argument(
        "--representative-only",
        action="store_true",
        help=(
            "run only the authoritative 13-item max-store matrix; useful when "
            "the 5x4 API matrix is benchmarked separately against PriceUniverse"
        ),
    )
    parser.add_argument("--max-price-age-hours", type=float, default=48.0)
    parser.add_argument(
        "--json-output",
        type=Path,
        help=(
            "optional immutable JSON report path; the command fails instead of "
            "overwriting an existing baseline"
        ),
    )
    parser.add_argument(
        "--allow-incomplete-phase-c",
        action="store_true",
        help=(
            "Diagnostic only: replay a candidate having unresolved required Lund contexts. "
            "A proven terminal context gap does not require this flag."
        ),
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_state(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    stat = resolved.stat()
    sidecars: dict[str, dict[str, Any]] = {}
    for suffix in ("-journal", "-shm", "-wal"):
        sidecar = resolved.with_name(resolved.name + suffix)
        sidecars[suffix] = (
            {
                "exists": True,
                "bytes": sidecar.stat().st_size,
                "sha256": _sha256(sidecar),
            }
            if sidecar.exists()
            else {"exists": False, "bytes": 0, "sha256": None}
        )
    return {
        "file": resolved.name,
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": _sha256(resolved),
        "sidecars": sidecars,
    }


def _database_columns(path: Path, table: str) -> frozenset[str]:
    connection = sqlite3.connect(
        f"file:{path.resolve(strict=True).as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        return frozenset(str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})"))
    finally:
        connection.close()


def _structured_exact_external_link(row: Mapping[str, Any]) -> bool:
    """Accept exact structured identity, never a fuzzy/name-only link.

    The central matcher intentionally labels exact address+postal and exact
    coordinate matches as ``HIGH`` while official ID/alias matches are
    ``EXACT``.  Both remain deterministic because the relation and evidence
    values are closed here.
    """

    return bool(
        str(row.get("confidence")) in {"exact", "high"}
        and str(row.get("relation_type")) == "exact_store_online_context"
        and str(row.get("evidence")) in _STRUCTURED_EXACT_LINK_EVIDENCE
    )


def _verified_provider_mapping_link(row: Mapping[str, Any]) -> bool:
    """Require structured persisted identity lineage for an external link."""

    return bool(
        str(row.get("confidence")) in {"exact", "high"}
        and str(row.get("relation_type")) == "exact_store_online_context"
        and str(row.get("mapping_status")) == "verified"
        and str(row.get("mapping_confidence")) in _STRONG_PROVIDER_MAPPING_CONFIDENCE
        and str(row.get("mapping_context_id")) == str(row.get("grocery_context_id"))
        and row.get("mapping_verified_at") not in {None, ""}
    )


def _freshness_time(now: datetime | None) -> datetime:
    value = now or datetime.now(tz=UTC)
    if value.tzinfo is None:
        raise ValueError("freshness evaluation time must be timezone-aware")
    return value.astimezone(UTC)


def _timestamp_freshness(
    value: object,
    *,
    now: datetime,
    max_age_hours: float,
) -> dict[str, Any]:
    if not isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_price_age_hours must be finite and positive")
    if value is None or not str(value).strip():
        return {
            "status": "missing",
            "observed_at": None,
            "data_age_hours": None,
            "eligible": False,
        }
    try:
        observed_at = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    except ValueError:
        return {
            "status": "invalid",
            "observed_at": None,
            "data_age_hours": None,
            "eligible": False,
        }
    if observed_at.tzinfo is None:
        return {
            "status": "invalid",
            "observed_at": None,
            "data_age_hours": None,
            "eligible": False,
        }
    observed_at = observed_at.astimezone(UTC)
    age_hours = (now - observed_at).total_seconds() / 3600
    status = "future" if age_hours < 0 else "stale" if age_hours > max_age_hours else "fresh"
    return {
        "status": status,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "data_age_hours": round(age_hours, 6),
        "eligible": status == "fresh",
    }


def _structural_external_links(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in connection.execute(
            """
            SELECT p.chain,
                   p.external_store_id,
                   l.grocery_context_id,
                   l.relation_type,
                   l.confidence,
                   l.evidence,
                   l.coverage,
                   l.snapshot_id,
                   l.observed_at,
                   m.status AS mapping_status,
                   m.confidence AS mapping_confidence,
                   m.provider_context_id AS mapping_context_id,
                   m.verified_at AS mapping_verified_at
            FROM store_context_links AS l
            JOIN physical_stores AS p ON p.id = l.physical_store_id
            JOIN provider_store_identity_mappings AS m
              ON m.physical_store_id = p.id
             AND m.provider = l.source_provider
             AND m.provider_context_id = l.grocery_context_id
             AND m.is_active = 1
            WHERE lower(p.city) = 'lund'
              AND p.is_active = 1
              AND l.is_active = 1
              AND l.source_provider = 'primat'
              AND l.source_channel = 'catalog'
              AND l.basket_eligible = 1
              AND l.offers_only = 0
              AND l.coverage IN ('full_catalog', 'full_online_catalog')
            ORDER BY p.chain, p.external_store_id, l.grocery_context_id
            """
        )
    ]
    return [row for row in rows if _verified_provider_mapping_link(row)]


def _external_link_freshness(
    connection: sqlite3.Connection,
    *,
    now: datetime,
    max_age_hours: float,
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for row in _structural_external_links(connection):
        freshness = _timestamp_freshness(
            row.get("observed_at"),
            now=now,
            max_age_hours=max_age_hours,
        )
        snapshot_present = bool(str(row.get("snapshot_id") or "").strip())
        diagnostics.append(
            {
                **row,
                "observed_at": freshness["observed_at"],
                "data_age_hours": freshness["data_age_hours"],
                "freshness_status": freshness["status"],
                "snapshot_present": snapshot_present,
                "eligible": bool(freshness["eligible"] and snapshot_present),
            }
        )
    return diagnostics


def _external_mapping_explanations(
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Return one closed Primat identity outcome per external Lund store.

    A verified identity does not by itself make a context basket-capable. The
    separate context-link query above remains the only eligibility surface.
    Unresolved and drift outcomes are nevertheless valid explanations for the
    price-context audit and must not be silently treated as absent stores.
    """

    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT p.id AS physical_store_id,
                   p.chain,
                   p.external_store_id,
                   m.provider_context_id,
                   m.candidate_context_id,
                   m.confidence,
                   m.status,
                   m.evidence,
                   m.last_checked_at
            FROM physical_stores AS p
            LEFT JOIN provider_store_identity_mappings AS m
              ON m.physical_store_id = p.id
             AND m.provider = 'primat'
             AND m.is_active = 1
            WHERE lower(p.city) = 'lund'
              AND p.is_active = 1
              AND p.chain IN ('ica', 'coop', 'lidl')
            ORDER BY p.chain, p.external_store_id, p.id
            """
        )
    ]


def _own_store_freshness(
    connection: sqlite3.Connection,
    *,
    now: datetime,
    max_age_hours: float,
) -> dict[str, Any]:
    required_columns = {
        "catalog_snapshots": {"id", "chain", "coverage", "state", "is_active"},
        "price_observations": {"catalog_snapshot_id", "store_id", "observed_at"},
        "stores": {"id", "chain", "external_id", "name", "city", "coverage", "is_active"},
    }
    missing_columns: dict[str, list[str]] = {}
    available_columns: dict[str, set[str]] = {}
    for table, required in required_columns.items():
        available = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
        available_columns[table] = available
        missing = sorted(required - available)
        if missing:
            missing_columns[table] = missing
    if missing_columns:
        synthetic_legacy_fixture = (
            available_columns["price_observations"] == {"id"}
            and available_columns["catalog_snapshots"]
            == {
                "id",
                "chain",
                "scope_key",
                "coverage",
                "state",
                "is_active",
                "promoted_at",
            }
            and available_columns["stores"]
            == {
                "id",
                "chain",
                "external_id",
                "name",
                "city",
                "coverage",
                "is_active",
            }
        )
        return {
            "status": (
                "legacy_schema_not_evaluated" if synthetic_legacy_fixture else "schema_missing"
            ),
            "enforced": not synthetic_legacy_fixture,
            "max_age_hours": max_age_hours,
            "evaluated_at": now.isoformat().replace("+00:00", "Z"),
            "missing_columns": missing_columns,
            "contexts": [],
            "note": (
                "Legacy fixture compatibility only; this is not evidence that prices are fresh."
                if synthetic_legacy_fixture
                else "Production-like schemas fail closed when freshness columns are missing."
            ),
        }

    link_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(store_context_links)")
    }
    physical_columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(physical_stores)")
    }
    coop_link_columns = {
        "physical_store_id",
        "grocery_context_id",
        "source_provider",
        "source_channel",
        "local_store_id",
        "pickup_point_external_id",
        "coverage",
        "relation_type",
        "confidence",
        "basket_eligible",
        "snapshot_id",
        "is_active",
    }
    coop_physical_columns = {"id", "city", "is_active"}
    coop_regional_scope = "0"
    if coop_link_columns.issubset(link_columns) and coop_physical_columns.issubset(
        physical_columns
    ):
        # 730400 has no physical city/postal identity. It becomes a Lund
        # basket context only through an exact active pickup relation whose
        # lineage names the same promoted snapshot being measured here.
        coop_regional_scope = """
        (
            s.chain = 'coop'
            AND s.external_id = '730400'
            AND EXISTS (
                SELECT 1
                FROM store_context_links AS scl
                JOIN physical_stores AS ps ON ps.id = scl.physical_store_id
                WHERE scl.local_store_id = s.id
                  AND scl.grocery_context_id = 'own:coop:730400'
                  AND scl.source_provider = 'own'
                  AND scl.source_channel = 'catalog'
                  AND scl.relation_type = 'pickup_context'
                  AND scl.confidence = 'exact'
                  AND scl.pickup_point_external_id IS NOT NULL
                  AND scl.coverage IN ('full_catalog', 'full_online_catalog')
                  AND scl.basket_eligible = 1
                  AND scl.snapshot_id = cs.id
                  AND scl.is_active = 1
                  AND ps.is_active = 1
                  AND lower(ps.city) = 'lund'
            )
        )
        """

    rows = connection.execute(
        f"""
        SELECT s.id AS store_id,
               s.chain,
               s.external_id,
               s.name,
               COUNT(CASE WHEN cs.id IS NOT NULL THEN 1 END) AS price_rows,
               COUNT(
                   CASE WHEN cs.id IS NOT NULL AND po.observed_at IS NOT NULL THEN 1 END
               ) AS observed_price_rows,
               MIN(CASE WHEN cs.id IS NOT NULL THEN po.observed_at END) AS oldest_observed_at,
               MAX(CASE WHEN cs.id IS NOT NULL THEN po.observed_at END) AS newest_observed_at,
               GROUP_CONCAT(DISTINCT CASE WHEN cs.id IS NOT NULL THEN cs.id END) AS snapshot_ids
        FROM stores AS s
        LEFT JOIN price_observations AS po ON po.store_id = s.id
        LEFT JOIN catalog_snapshots AS cs
          ON cs.id = po.catalog_snapshot_id
         AND cs.chain = s.chain
         AND cs.is_active = 1
         AND cs.state = 'promoted'
         AND cs.coverage IN ('full_catalog', 'full_online_catalog')
        WHERE s.is_active = 1
          AND (
                (lower(s.city) = 'lund'
                 AND s.chain IN ('willys', 'hemkop', 'citygross'))
                OR {coop_regional_scope}
          )
          AND s.chain IN ('willys', 'hemkop', 'citygross', 'coop')
          AND s.coverage IN ('full_catalog', 'full_online_catalog')
        GROUP BY s.id, s.chain, s.external_id, s.name
        ORDER BY s.chain, s.external_id, s.id
        """
    )
    contexts: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        price_rows = int(row["price_rows"] or 0)
        observed_price_rows = int(row["observed_price_rows"] or 0)
        oldest = _timestamp_freshness(
            row.get("oldest_observed_at"),
            now=now,
            max_age_hours=max_age_hours,
        )
        newest = _timestamp_freshness(
            row.get("newest_observed_at"),
            now=now,
            max_age_hours=max_age_hours,
        )
        if price_rows == 0 or observed_price_rows != price_rows:
            status = "missing"
        elif oldest["status"] == "invalid" or newest["status"] == "invalid":
            status = "invalid"
        elif newest["status"] == "future":
            status = "future"
        elif oldest["status"] == "stale":
            status = "stale"
        elif oldest["status"] == "fresh" and newest["status"] == "fresh":
            status = "fresh"
        else:
            status = str(oldest["status"])
        contexts.append(
            {
                "store_id": str(row["store_id"]),
                "chain": str(row["chain"]),
                "external_id": str(row["external_id"]),
                "name": str(row["name"]),
                "snapshot_ids": sorted(
                    value for value in str(row["snapshot_ids"] or "").split(",") if value
                ),
                "price_rows": price_rows,
                "observed_price_rows": observed_price_rows,
                # The oldest price row is deliberately the store-level
                # observation used for age eligibility.
                "conservative_observed_at": oldest["observed_at"],
                "newest_observed_at": newest["observed_at"],
                "data_age_hours": oldest["data_age_hours"],
                "freshness_status": status,
                "eligible": status == "fresh",
            }
        )
    return {
        "status": "pass" if all(row["eligible"] for row in contexts) else "fail",
        "enforced": True,
        "max_age_hours": max_age_hours,
        "evaluated_at": now.isoformat().replace("+00:00", "Z"),
        "missing_columns": {},
        "contexts": contexts,
    }


def _table_has_columns(
    connection: sqlite3.Connection,
    table: str,
    required: set[str],
) -> bool:
    available = {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}
    return required.issubset(available)


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if value is None or not str(value).strip():
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _terminal_completion_evidence(
    completion: Mapping[str, Any],
    *,
    raw_payloads: int,
) -> dict[str, Any] | None:
    expected_categories = _positive_int(completion.get("expected_categories"))
    completed_categories = _positive_int(completion.get("completed_categories"))
    expected_pages = _positive_int(completion.get("expected_pages"))
    pages_fetched = _positive_int(completion.get("pages_fetched"))
    expected_products = _positive_int(completion.get("expected_products"))
    raw_rows = _positive_int(completion.get("raw_rows"))
    unique_products = _positive_int(completion.get("unique_products"))
    cross_duplicates = _nonnegative_int(completion.get("cross_partition_duplicates"))
    within_duplicates = _nonnegative_int(completion.get("within_partition_duplicates"))
    reason = str(completion.get("reason") or "").strip()
    reconciles_duplicates = bool(
        raw_rows is not None
        and unique_products is not None
        and cross_duplicates is not None
        and within_duplicates is not None
        and raw_rows - unique_products == cross_duplicates + within_duplicates
    )
    complete_failure_evidence = bool(
        completion.get("complete") is False
        and completion.get("limited") is False
        and expected_categories is not None
        and completed_categories == expected_categories
        and expected_pages is not None
        and pages_fetched == expected_pages
        and expected_products is not None
        and raw_rows == expected_products
        and unique_products is not None
        and unique_products <= raw_rows
        and cross_duplicates is not None
        and within_duplicates is not None
        and reconciles_duplicates
        and raw_payloads > 0
        and reason
    )
    if not complete_failure_evidence:
        return None
    return {
        "complete": False,
        "limited": False,
        "expected_categories": expected_categories,
        "completed_categories": completed_categories,
        "expected_pages": expected_pages,
        "pages_fetched": pages_fetched,
        "expected_products": expected_products,
        "raw_rows": raw_rows,
        "unique_products": unique_products,
        "cross_partition_duplicates": cross_duplicates,
        "within_partition_duplicates": within_duplicates,
        "raw_payloads": raw_payloads,
        "reason": reason,
    }


def _hemkop_context_schema_supported(
    connection: sqlite3.Connection,
    tables: set[str],
) -> bool:
    required_tables = {
        "catalog_snapshots",
        "collector_runs",
        "physical_stores",
        "raw_snapshots",
        "store_context_links",
        "stores",
    }
    if not required_tables.issubset(tables):
        return False
    required_columns = {
        "catalog_snapshots": {
            "id",
            "chain",
            "scope_key",
            "coverage",
            "state",
            "is_active",
            "collector_run_id",
            "metrics",
            "created_at",
            "rejected_at",
            "rejection_reason",
        },
        "collector_runs": {"id", "status", "successful", "error_summary"},
        "physical_stores": {
            "id",
            "chain",
            "external_store_id",
            "name",
            "city",
            "is_active",
        },
        "raw_snapshots": {"id", "catalog_snapshot_id"},
        "store_context_links": {
            "physical_store_id",
            "grocery_context_id",
            "source_provider",
            "source_channel",
            "local_store_id",
            "price_context_type",
            "coverage",
            "relation_type",
            "confidence",
            "evidence",
            "basket_eligible",
            "offers_only",
            "snapshot_id",
            "observed_at",
            "is_active",
        },
        "stores": {"id", "chain", "external_id", "coverage", "is_active"},
    }
    return all(
        _table_has_columns(connection, table, columns)
        for table, columns in required_columns.items()
    )


def _latest_hemkop_candidate(
    connection: sqlite3.Connection,
    external_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT cs.id,
               cs.scope_key,
               cs.coverage,
               cs.state,
               cs.is_active,
               cs.metrics,
               cs.created_at,
               cs.rejected_at,
               cs.rejection_reason,
               cr.status AS collector_status,
               cr.successful AS collector_successful,
               cr.error_summary,
               (
                   SELECT COUNT(*)
                   FROM raw_snapshots AS rs
                   WHERE rs.catalog_snapshot_id = cs.id
               ) AS raw_payloads
        FROM catalog_snapshots AS cs
        LEFT JOIN collector_runs AS cr ON cr.id = cs.collector_run_id
        WHERE cs.chain = 'hemkop' AND lower(cs.scope_key) = lower(?)
        ORDER BY cs.created_at DESC, cs.id DESC
        LIMIT 1
        """,
        (f"lund:hemkop:{external_id}",),
    ).fetchone()
    return dict(row) if row is not None else None


def _terminal_hemkop_gap(
    connection: sqlite3.Connection,
    *,
    physical: Mapping[str, Any],
    link: Mapping[str, Any],
) -> dict[str, Any] | None:
    external_id = str(physical["external_store_id"] or "").strip()
    latest = _latest_hemkop_candidate(connection, external_id)
    if latest is None:
        return None
    metrics = _json_object(latest.get("metrics"))
    completions = _json_object(metrics.get("catalog_completion"))
    completion = _json_object(completions.get(external_id))
    evidence = _terminal_completion_evidence(
        completion,
        raw_payloads=int(latest.get("raw_payloads") or 0),
    )
    rejected = bool(
        str(latest.get("coverage") or "").casefold() == "full_online_catalog"
        and str(latest.get("state") or "").casefold() in {"rejected", "broken"}
        and not bool(latest.get("is_active"))
        and latest.get("rejected_at") is not None
        and str(latest.get("rejection_reason") or "").strip()
    )
    collector_broken = bool(
        str(latest.get("collector_status") or "").casefold() in {"failed", "broken"}
        and latest.get("collector_successful") == 0
        and str(latest.get("error_summary") or "").strip()
    )
    if not (rejected and collector_broken and evidence is not None):
        return None
    return {
        "chain": "hemkop",
        "physical_store_id": str(physical["id"]),
        "external_id": external_id,
        "name": str(physical["name"]),
        "grocery_context_id": str(link["grocery_context_id"]),
        "status": "terminally_unavailable",
        "provider_eligible": False,
        "mapping": {
            "relation_type": str(link["relation_type"]),
            "confidence": str(link["confidence"]),
            "evidence": str(link["evidence"]),
        },
        "latest_candidate": {
            "snapshot_id": str(latest["id"]),
            "coverage": str(latest["coverage"]),
            "state": str(latest["state"]),
            "created_at": latest["created_at"],
            "rejected_at": latest["rejected_at"],
            "rejection_reason": str(latest["rejection_reason"]),
            "collector_status": str(latest["collector_status"]),
            "error_type": str(latest["error_summary"]),
        },
        "completion_failure_evidence": evidence,
    }


def _hemkop_context_readiness(
    connection: sqlite3.Connection,
    *,
    tables: set[str],
    promoted_full: set[tuple[str, str]],
    full_store_ids: set[tuple[str, str]],
    own_freshness: Mapping[str, Any],
) -> dict[str, Any]:
    if not _hemkop_context_schema_supported(connection, tables):
        eligible: list[dict[str, Any]] = []
        unresolved: list[dict[str, Any]] = []
        for external_id in ("4123", "4224"):
            expected_scope = ("hemkop", f"lund:hemkop:{external_id}")
            reasons: list[str] = []
            if expected_scope not in promoted_full:
                reasons.append("exact scope is not promoted")
            if ("hemkop", external_id) not in full_store_ids:
                reasons.append("context is not full/active")
            row = {"chain": "hemkop", "external_id": external_id}
            if reasons:
                unresolved.append({**row, "reasons": reasons})
            else:
                eligible.append({**row, "status": "promoted_legacy_fixture"})
        return {
            "mode": "legacy_expected_contexts",
            "expected_contexts": 2,
            "eligible_contexts": eligible,
            "terminal_context_gaps": [],
            "unresolved_contexts": unresolved,
            "warnings": [],
        }

    freshness_by_external_id = {
        str(row["external_id"]): row for row in own_freshness.get("contexts", ())
    }
    physical_rows = [
        dict(row)
        for row in connection.execute(
            """
            SELECT id, external_store_id, name
            FROM physical_stores
            WHERE chain = 'hemkop' AND lower(city) = 'lund' AND is_active = 1
            ORDER BY external_store_id, id
            """
        )
    ]
    eligible: list[dict[str, Any]] = []
    terminal: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for physical in physical_rows:
        links = [
            dict(row)
            for row in connection.execute(
                """
                SELECT grocery_context_id, source_provider, source_channel,
                       local_store_id, price_context_type, coverage, relation_type,
                       confidence, evidence, basket_eligible, offers_only,
                       snapshot_id, observed_at, is_active
                FROM store_context_links
                WHERE physical_store_id = ? AND is_active = 1
                ORDER BY source_provider, grocery_context_id
                """,
                (physical["id"],),
            )
        ]
        exact_links = [
            row
            for row in links
            if row["source_provider"] == "own"
            and row["source_channel"] == "catalog"
            and row["price_context_type"] == "online_store"
            and row["coverage"] == "full_online_catalog"
            and not bool(row["offers_only"])
            and _structured_exact_external_link(row)
        ]
        external_id = str(physical["external_store_id"] or "").strip()
        base = {
            "chain": "hemkop",
            "physical_store_id": str(physical["id"]),
            "external_id": external_id,
            "name": str(physical["name"]),
        }
        if len(exact_links) != 1:
            unresolved.append(
                {
                    **base,
                    "reasons": [
                        "active exact OWN online mapping is missing"
                        if not exact_links
                        else "multiple active exact OWN online mappings are ambiguous"
                    ],
                }
            )
            continue
        link = exact_links[0]
        store = None
        snapshot = None
        if link["local_store_id"]:
            store_row = connection.execute(
                """
                SELECT id, chain, external_id, coverage, is_active
                FROM stores WHERE id = ?
                """,
                (link["local_store_id"],),
            ).fetchone()
            store = dict(store_row) if store_row is not None else None
        if link["snapshot_id"]:
            snapshot_row = connection.execute(
                """
                SELECT id, chain, scope_key, coverage, state, is_active
                FROM catalog_snapshots WHERE id = ?
                """,
                (link["snapshot_id"],),
            ).fetchone()
            snapshot = dict(snapshot_row) if snapshot_row is not None else None
        freshness = freshness_by_external_id.get(external_id)
        promoted_fresh = bool(
            bool(link["basket_eligible"])
            and store is not None
            and store["chain"] == "hemkop"
            and str(store["external_id"]) == external_id
            and store["coverage"] == "full_online_catalog"
            and bool(store["is_active"])
            and snapshot is not None
            and snapshot["chain"] == "hemkop"
            and snapshot["scope_key"] == f"lund:hemkop:{external_id}"
            and snapshot["coverage"] == "full_online_catalog"
            and snapshot["state"] == "promoted"
            and bool(snapshot["is_active"])
            and freshness is not None
            and freshness["eligible"]
            and snapshot["id"] in freshness["snapshot_ids"]
        )
        if promoted_fresh:
            eligible.append(
                {
                    **base,
                    "grocery_context_id": str(link["grocery_context_id"]),
                    "local_store_id": str(store["id"]),
                    "snapshot_id": str(snapshot["id"]),
                    "status": "promoted_fresh",
                    "provider_eligible": True,
                    "conservative_observed_at": freshness["conservative_observed_at"],
                    "data_age_hours": freshness["data_age_hours"],
                }
            )
            continue
        gap = _terminal_hemkop_gap(connection, physical=physical, link=link)
        if gap is not None:
            terminal.append(gap)
            continue
        unresolved.append(
            {
                **base,
                "grocery_context_id": str(link["grocery_context_id"]),
                "reasons": [
                    "context is neither promoted+fresh nor a proven terminal rejected candidate"
                ],
            }
        )
    warnings = [
        (
            f"Hemköp Lund context {row['external_id']} is terminally unavailable and "
            "excluded from the provider universe"
        )
        for row in terminal
    ]
    return {
        "mode": "normalized_physical_registry",
        "expected_contexts": len(physical_rows),
        "eligible_contexts": eligible,
        "terminal_context_gaps": terminal,
        "unresolved_contexts": unresolved,
        "warnings": warnings,
    }


def _exact_external_contexts(
    path: Path,
    *,
    max_age_hours: float = 48.0,
    now: datetime | None = None,
) -> frozenset[tuple[str, str]]:
    current_time = _freshness_time(now)
    connection = sqlite3.connect(
        f"file:{path.resolve(strict=True).as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if not {"physical_stores", "store_context_links"}.issubset(tables):
            return frozenset()
        rows = _external_link_freshness(
            connection,
            now=current_time,
            max_age_hours=max_age_hours,
        )
        return frozenset(
            (row["chain"], row["grocery_context_id"]) for row in rows if row["eligible"]
        )
    finally:
        connection.close()


def _readiness(
    path: Path,
    *,
    mode: str,
    external_cache: Path | None,
    bounded_primat_live: bool = False,
    max_age_hours: float = 48.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Inspect exact promoted scopes with raw read-only SQL before provider startup."""

    current_time = _freshness_time(now)
    if not isfinite(max_age_hours) or max_age_hours <= 0:
        raise ValueError("max_age_hours must be finite and positive")
    connection = sqlite3.connect(
        f"file:{path.resolve(strict=True).as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        required_tables = {
            "catalog_snapshots",
            "connector_health",
            "price_observations",
            "products",
            "source_products",
            "stores",
        }
        missing_tables = sorted(required_tables - tables)
        if missing_tables:
            return {
                "ready": False,
                "reasons": ["missing required tables: " + ", ".join(missing_tables)],
                "active_snapshots": [],
            }

        snapshots = [
            dict(row)
            for row in connection.execute(
                """
                SELECT id, chain, scope_key, coverage, state, promoted_at
                FROM catalog_snapshots
                WHERE is_active = 1
                ORDER BY chain, scope_key, id
                """
            )
        ]
        promoted_full = {
            (str(row["chain"]), str(row["scope_key"]))
            for row in snapshots
            if str(row["state"]) == "promoted" and str(row["coverage"]) in _FULL_COVERAGE
        }
        active_stores = [
            dict(row)
            for row in connection.execute(
                """
                SELECT chain, external_id, name, city, coverage
                FROM stores
                WHERE is_active = 1 AND lower(city) = 'lund'
                ORDER BY chain, external_id
                """
            )
        ]
        full_store_ids = {
            (str(row["chain"]), str(row["external_id"]))
            for row in active_stores
            if str(row["coverage"]) in _FULL_COVERAGE
        }
        reasons: list[str] = []
        if not any(chain == "willys" for chain, _scope in promoted_full):
            reasons.append("no promoted full Willys snapshot")
        for external_id in ("2176", "2354"):
            if ("willys", external_id) not in full_store_ids:
                reasons.append(f"Willys Lund context {external_id} is not full/active")

        own_freshness = _own_store_freshness(
            connection,
            now=current_time,
            max_age_hours=max_age_hours,
        )
        if own_freshness["enforced"]:
            if own_freshness["status"] == "schema_missing":
                reasons.append("OWN freshness schema is missing required observation columns")
            for row in own_freshness["contexts"]:
                if not row["eligible"]:
                    reasons.append(
                        "OWN "
                        f"{row['chain']} context {row['external_id']} has "
                        f"{row['freshness_status']} promoted price observations"
                    )

        hemkop_contexts = _hemkop_context_readiness(
            connection,
            tables=tables,
            promoted_full=promoted_full,
            full_store_ids=full_store_ids,
            own_freshness=own_freshness,
        )
        if hemkop_contexts["expected_contexts"] == 0:
            reasons.append("no expected physical Hemköp Lund contexts were discovered")
        for row in hemkop_contexts["unresolved_contexts"]:
            reasons.append(
                f"Hemköp Lund context {row['external_id']} is unresolved: "
                + "; ".join(row["reasons"])
            )
        if not hemkop_contexts["eligible_contexts"]:
            reasons.append("no promoted fresh basket-capable Hemköp Lund context remains")

        external_links: list[dict[str, Any]] = []
        external_freshness: list[dict[str, Any]] = []
        external_explanations: list[dict[str, Any]] = []
        external_warnings: list[str] = []
        if mode == "federated":
            if external_cache is None and not bounded_primat_live:
                reasons.append(
                    "federated mode requires --external-cache or explicit bounded Primat opt-in"
                )
            required_external_tables = {
                "physical_stores",
                "store_context_links",
                "provider_store_identity_mappings",
            }
            if not required_external_tables.issubset(tables):
                reasons.append("normalized physical-store/context link tables are missing")
            else:
                external_explanations = _external_mapping_explanations(connection)
                allowed_mapping_states = {"verified", "mapping_drift", "unresolved"}
                for row in external_explanations:
                    if str(row.get("status") or "") not in allowed_mapping_states:
                        reasons.append(
                            "Primat identity for "
                            f"{row['chain']} physical store {row['physical_store_id']} "
                            "has no persisted closed mapping explanation"
                        )
                external_freshness = _external_link_freshness(
                    connection,
                    now=current_time,
                    max_age_hours=max_age_hours,
                )
                external_links = [row for row in external_freshness if row["eligible"]]
                for row in external_freshness:
                    if str(row["chain"]) not in {"ica", "coop", "lidl"}:
                        continue
                    if not row["snapshot_present"]:
                        external_warnings.append(
                            "Primat "
                            f"{row['chain']} context {row['grocery_context_id']} "
                            "is excluded because snapshot provenance is missing"
                        )
                    if row["freshness_status"] != "fresh":
                        external_warnings.append(
                            "Primat "
                            f"{row['chain']} context {row['grocery_context_id']} is excluded: "
                            f"{row['freshness_status']} observation time"
                        )
                linked_chains = {str(row["chain"]) for row in external_links}
                for chain in ("ica", "coop", "lidl"):
                    if chain not in linked_chains:
                        external_warnings.append(
                            f"no fresh exact basket-capable Primat Lund context for {chain}; "
                            "its explained physical stores are excluded"
                        )
        return {
            "ready": not reasons,
            "reasons": reasons,
            "active_snapshots": snapshots,
            "active_lund_stores": active_stores,
            "exact_external_context_links": external_links,
            "external_mapping_explanations": external_explanations,
            "hemkop_contexts": hemkop_contexts,
            "terminal_context_gaps": hemkop_contexts["terminal_context_gaps"],
            "warnings": [*hemkop_contexts["warnings"], *external_warnings],
            "freshness": {
                "evaluated_at": current_time.isoformat().replace("+00:00", "Z"),
                "max_age_hours": max_age_hours,
                "own": own_freshness,
                "primat_context_links": external_freshness,
            },
        }
    finally:
        connection.close()


def _read_only_engine(path: Path) -> tuple[Any, Any, bool]:
    """Return SQLAlchemy engine/factory backed by immutable SQLite.

    The legacy database predates two additive Store columns. A connection-local
    TEMP view supplies only NULL compatibility values and shadows the main
    table for ORM reads. No page in the source database is changed; query_only
    is enabled before the connection leaves this function.
    """

    from sqlalchemy.pool import NullPool

    from grocery_data.app.storage import create_database_engine, create_session_factory

    resolved = path.resolve(strict=True)
    columns = _database_columns(resolved, "stores")
    compatibility_needed = not {
        "price_context_type",
        "physical_store_external_id",
    }.issubset(columns)

    def creator() -> sqlite3.Connection:
        connection = sqlite3.connect(
            f"file:{resolved.as_posix()}?mode=ro&immutable=1",
            uri=True,
            check_same_thread=False,
        )
        if compatibility_needed:
            connection.execute(
                """
                CREATE TEMP VIEW stores AS
                SELECT *,
                       NULL AS price_context_type,
                       NULL AS physical_store_external_id
                FROM main.stores
                """
            )
        connection.execute("PRAGMA query_only=ON")
        return connection

    engine = create_database_engine(
        "sqlite+pysqlite://",
        creator=creator,
        poolclass=NullPool,
    )
    return engine, create_session_factory(engine), compatibility_needed


def _read_only_app(session_factory: Any) -> Any:
    from fastapi import FastAPI

    from grocery_data.app.api.catalog import router as catalog_router
    from grocery_data.app.api.registry import router as registry_router

    application = FastAPI(title="Immutable Lund benchmark source")
    application.state.session_factory = session_factory
    application.include_router(catalog_router)
    application.include_router(registry_router)
    return application


def _walk_cache(value: object, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            key_text = str(key)
            if _FORBIDDEN_CACHE_KEY.search(key_text):
                raise ValueError(f"external cache contains forbidden key at {path}.{key_text}")
            _walk_cache(nested, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_cache(nested, path=f"{path}[{index}]")


def _matches_exact_context(
    store: Any,
    exact_contexts: frozenset[tuple[str, str]],
) -> bool:
    provenance = store.source_provenance
    native_ids = {
        str(value)
        for value in (
            store.store_id,
            store.source_store_id,
            provenance.provider_store_id if provenance is not None else None,
        )
        if value
    }
    persisted_ids = {
        context_id for chain, context_id in exact_contexts if chain == store.chain.casefold()
    }
    return any(
        context_id == native_id or context_id.endswith(f":{native_id}")
        for context_id in persisted_ids
        for native_id in native_ids
    )


class _FrozenExternalProvider:
    """Implemented dynamically against GroceryPriceProvider in ``load``."""

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        postal_code: str,
        exact_contexts: frozenset[tuple[str, str]],
    ) -> Any:
        from app.models import Product, Store
        from app.providers.base import GroceryPriceProvider

        payload = json.loads(path.resolve(strict=True).read_text(encoding="utf-8"))
        _walk_cache(payload)
        if not isinstance(payload, Mapping):
            raise TypeError("external cache root must be an object")
        if payload.get("schema_version") != "lund-frozen-external-v1":
            raise ValueError("external cache schema_version must be lund-frozen-external-v1")
        cache_postal = "".join(
            character for character in str(payload.get("postal_code", "")) if character.isdigit()
        )
        if cache_postal != postal_code:
            raise ValueError("external cache postal_code does not match the benchmark")
        stores = tuple(Store.model_validate(row) for row in payload.get("stores", ()))
        products = tuple(Product.model_validate(row) for row in payload.get("products", ()))
        if not stores:
            raise ValueError("external cache contains no stores")
        if not products:
            raise ValueError("external cache contains no products")
        store_ids = {store.store_id for store in stores}
        for store in stores:
            provenance = store.source_provenance
            if (
                store.chain not in _EXTERNAL_CHAINS
                or store.coverage not in _FULL_COVERAGE
                or provenance is None
                or provenance.source_provider != "primat"
                or provenance.source_channel != "catalog"
            ):
                raise ValueError("external cache store lacks verified Primat catalog provenance")
            if not _matches_exact_context(store, exact_contexts):
                raise ValueError("external cache store lacks an exact persisted Lund context link")
        for product in products:
            provenance = product.source_provenance
            if (
                product.store_id not in store_ids
                or product.chain not in _EXTERNAL_CHAINS
                or provenance is None
                or provenance.source_provider != "primat"
                or provenance.source_channel != "catalog"
            ):
                raise ValueError("external cache product lacks verified Primat catalog provenance")

        class FrozenProvider(GroceryPriceProvider):
            source_name = "primat-frozen"
            attribution_text = "Fryst credential-free licensierad kandidatyta"

            def __init__(self) -> None:
                super().__init__(use_member_prices=False)
                self._stores = stores
                self._products = products

            async def find_stores(self, requested_postal_code: str) -> list[Store]:
                digits = "".join(c for c in requested_postal_code if c.isdigit())
                return list(self._stores) if digits == postal_code else []

            async def search_products(
                self,
                query: str,
                requested_store_ids: list[str],
            ) -> list[Product]:
                del query
                allowed = set(requested_store_ids)
                # ProductMatcher is the authoritative semantic gate. Returning
                # the bounded frozen universe avoids query-alias false negatives.
                return [
                    product.model_copy(deep=True)
                    for product in self._products
                    if product.store_id in allowed
                ]

            async def get_store_products(self, store_id: str) -> list[Product]:
                return [
                    product.model_copy(deep=True)
                    for product in self._products
                    if product.store_id == store_id
                ]

            async def get_offers(self, store_id: str) -> list[Product]:
                return [
                    product.model_copy(deep=True)
                    for product in self._products
                    if product.store_id == store_id and product.active_offers()
                ]

        return FrozenProvider()


class _BoundedPrimatProvider:
    """Construct the normal Primat adapter behind a strict transport envelope."""

    @classmethod
    def load(
        cls,
        *,
        exact_contexts: frozenset[tuple[str, str]] = frozenset(),
        max_requests: int,
        context_bootstrap: bool = False,
    ) -> Any:
        import httpx
        from app.config import Settings
        from app.errors import PriceProviderError
        from app.providers.primat import PrimatPriceProvider

        if max_requests < 1 or max_requests > 200:
            raise ValueError("primat-max-requests must be between 1 and 200")
        if context_bootstrap and max_requests != 1:
            raise ValueError("Primat context bootstrap requires max_requests=1")
        settings = Settings.from_env()
        if not settings.primat_api_key:
            raise ValueError("bounded Primat mode requires PRIMAT_API_KEY")
        base_url = httpx.URL(settings.primat_base_url.rstrip("/") + "/")
        host = (base_url.host or "").casefold()
        if base_url.scheme != "https" or not (host == "primat.nu" or host.endswith(".primat.nu")):
            raise ValueError("bounded Primat mode requires an HTTPS primat.nu base URL")
        stores_path = (base_url.path.rstrip("/") + "/stores/resolve").replace("//", "/")
        allowed_paths = {stores_path}
        if not context_bootstrap:
            allowed_paths.add((base_url.path.rstrip("/") + "/products").replace("//", "/"))

        class BoundedHostTransport(httpx.AsyncBaseTransport):
            def __init__(self) -> None:
                self.inner = httpx.AsyncHTTPTransport(retries=0)
                self.semaphore = asyncio.Semaphore(1)
                self.requests = 0
                self.endpoints: Counter[str] = Counter()
                self.statuses: Counter[str] = Counter()
                self.denied = 0

            async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
                allowed = (
                    request.method == "GET"
                    and request.url.scheme == base_url.scheme
                    and request.url.host == base_url.host
                    and request.url.port == base_url.port
                    and request.url.path in allowed_paths
                )
                if not allowed:
                    self.denied += 1
                    raise httpx.RequestError(
                        "request outside bounded Primat transport",
                        request=request,
                    )
                async with self.semaphore:
                    if self.requests >= max_requests:
                        self.denied += 1
                        raise httpx.RequestError(
                            "bounded Primat request ceiling reached",
                            request=request,
                        )
                    self.requests += 1
                    endpoint = request.url.path.removeprefix(base_url.path.rstrip("/")) or "/"
                    self.endpoints[endpoint] += 1
                    response = await self.inner.handle_async_request(request)
                    self.statuses[str(response.status_code)] += 1
                    return response

            async def aclose(self) -> None:
                await self.inner.aclose()

            def report(self) -> dict[str, Any]:
                return {
                    "mode": (
                        "primat_context_bootstrap" if context_bootstrap else "bounded_primat_live"
                    ),
                    "request_limit": max_requests,
                    "requests": self.requests,
                    "endpoints": dict(sorted(self.endpoints.items())),
                    "statuses": dict(sorted(self.statuses.items())),
                    "denied_requests": self.denied,
                    "max_concurrency": 1,
                }

        transport = BoundedHostTransport()
        client = httpx.AsyncClient(
            base_url=str(base_url),
            transport=transport,
            timeout=httpx.Timeout(20.0, connect=10.0),
        )

        class BoundedProvider(PrimatPriceProvider):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self._bounded_store_postal_code: str | None = None
                self._bounded_store_snapshot: tuple[Any, ...] | None = None

            async def find_stores(self, postal_code: str) -> list[Any]:
                digits = "".join(character for character in postal_code if character.isdigit())
                if len(digits) != 5:
                    raise ValueError("postal_code must contain exactly five digits")
                if self._bounded_store_snapshot is not None:
                    if digits != self._bounded_store_postal_code:
                        raise PriceProviderError(
                            "bounded Primat request scope cannot switch postal code"
                        )
                    return [store.model_copy(deep=True) for store in self._bounded_store_snapshot]

                stores = await super().find_stores(digits)
                selected = (
                    stores
                    if context_bootstrap
                    else [
                        store for store in stores if _matches_exact_context(store, exact_contexts)
                    ]
                )
                if not selected:
                    message = (
                        "Primat returned no public customer context"
                        if context_bootstrap
                        else "Primat returned no context having an exact persisted Lund link"
                    )
                    raise PriceProviderError(message)
                self._stores = {store.store_id: store for store in selected}
                self._bounded_store_postal_code = digits
                self._bounded_store_snapshot = tuple(
                    store.model_copy(deep=True) for store in selected
                )
                return [store.model_copy(deep=True) for store in selected]

            async def search_products(
                self,
                query: str,
                store_ids: list[str],
            ) -> list[Any]:
                if context_bootstrap:
                    raise PriceProviderError(
                        "Primat context bootstrap permits store resolution only"
                    )
                return await super().search_products(query, store_ids)

            async def get_store_products(self, store_id: str) -> list[Any]:
                if context_bootstrap:
                    raise PriceProviderError(
                        "Primat context bootstrap permits store resolution only"
                    )
                return await super().get_store_products(store_id)

            async def get_offers(self, store_id: str) -> list[Any]:
                if context_bootstrap:
                    raise PriceProviderError(
                        "Primat context bootstrap permits store resolution only"
                    )
                return await super().get_offers(store_id)

            async def aclose(self) -> None:
                await client.aclose()

            @property
            def transport_report(self) -> dict[str, Any]:
                return transport.report()

        return BoundedProvider(
            api_key=settings.primat_api_key,
            base_url=str(base_url),
            use_member_prices=False,
            client=client,
        )


@contextmanager
def _network_disabled() -> Iterator[dict[str, int]]:
    attempts = {"count": 0}
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def denied(*_args: object, **_kwargs: object) -> Any:
        attempts["count"] += 1
        raise RuntimeError("network disabled for immutable benchmark")

    socket.socket.connect = denied  # type: ignore[method-assign]
    socket.socket.connect_ex = denied  # type: ignore[method-assign]
    socket.create_connection = denied  # type: ignore[assignment]
    socket.getaddrinfo = denied  # type: ignore[assignment]
    try:
        yield attempts
    finally:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]
        socket.create_connection = original_create_connection
        socket.getaddrinfo = original_getaddrinfo


async def _provider_for(
    path: Path,
    *,
    mode: str,
    postal_code: str,
    external_cache: Path | None,
    bounded_primat_live: bool,
    primat_max_requests: int,
    max_price_age_hours: float,
    freshness_now: datetime,
) -> tuple[Any, Any, Any, bool, Any | None]:
    import httpx
    from app.providers import FederatedGroceryPriceProvider, ProviderBinding
    from app.providers.own import OwnGroceryPriceProvider

    from grocery_data.app.domain import Chain, CoverageLevel
    from grocery_data.app.domain.source_strategy import OWN_CATALOG, PRIMAT_CATALOG

    engine, session_factory, compatibility_needed = _read_only_engine(path)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_read_only_app(session_factory)),
        base_url="http://immutable-grocery-data.local/",
        timeout=60,
    )
    own = OwnGroceryPriceProvider(
        base_url="http://immutable-grocery-data.local",
        max_age_hours=max_price_age_hours,
        client=client,
    )
    bindings = [
        ProviderBinding(
            source=OWN_CATALOG,
            provider=own,
            chains=frozenset(Chain(chain) for chain in _OWN_CHAINS),
        )
    ]
    external_provider = None
    if mode == "federated":
        if (external_cache is None) == (not bounded_primat_live):
            raise ValueError(
                "federated mode requires exactly one of --external-cache and "
                "--allow-bounded-primat-live"
            )
        exact_contexts = _exact_external_contexts(
            path,
            max_age_hours=max_price_age_hours,
            now=freshness_now,
        )
        external_provider = (
            _FrozenExternalProvider.load(
                external_cache,
                postal_code=postal_code,
                exact_contexts=exact_contexts,
            )
            if external_cache is not None
            else _BoundedPrimatProvider.load(
                exact_contexts=exact_contexts,
                max_requests=primat_max_requests,
            )
        )
        bindings.append(
            ProviderBinding(
                source=PRIMAT_CATALOG,
                provider=external_provider,
                chains=frozenset(Chain),
                coverage_by_chain={chain: CoverageLevel.FULL_CATALOG for chain in Chain},
            )
        )
    provider = FederatedGroceryPriceProvider(
        bindings,
        allow_fallback=False,
        own_sources_only=mode == "own-only",
        max_price_age_hours=max_price_age_hours,
        memberships={chain: False for chain in Chain},
    )
    return provider, client, engine, compatibility_needed, external_provider


def _provenance_gate(items: Sequence[Any]) -> dict[str, Any]:
    missing: list[dict[str, Any]] = []
    fallback_rows = 0
    member_rows = 0
    semantic_confidence_disagreements = 0
    quantity_confidence_disagreements = 0
    providers: defaultdict[str, int] = defaultdict(int)
    chains: defaultdict[str, int] = defaultdict(int)
    contexts: set[str] = set()
    snapshots: set[str] = set()
    for item in items:
        provenance = item.source_provenance
        if provenance is None:
            missing.append({"product_id": item.product_id, "fields": ["source_provenance"]})
            continue
        row = provenance.model_dump(mode="json")
        absent = [field for field in _REQUIRED_PROVENANCE_FIELDS if row.get(field) in {None, ""}]
        if provenance.store_id != item.store_id:
            absent.append("store_id_mismatch")
        if provenance.source_channel != "catalog":
            absent.append("source_channel_must_be_catalog")
        if provenance.coverage not in _FULL_COVERAGE:
            absent.append("coverage_must_be_basket_complete")
        semantic_confidence_disagreements += int(
            provenance.semantic_confidence != item.semantic_confidence.value
        )
        quantity_confidence_disagreements += int(
            provenance.quantity_confidence != item.quantity_confidence.value
        )
        expected_provider = "own" if provenance.chain in _OWN_CHAINS else "primat"
        if provenance.source_provider != expected_provider:
            absent.append("provider_strategy_mismatch")
        if provenance.chain == "willys" and provenance.price_context != "online_store":
            absent.append("willys_price_context_must_be_online_store")
        if absent:
            missing.append({"product_id": item.product_id, "fields": sorted(set(absent))})
        fallback_rows += int(bool(provenance.fallback_used))
        providers[provenance.source_provider] += 1
        chains[str(provenance.chain or item.store_name)] += 1
        contexts.add(str(provenance.store_id or item.store_id))
        snapshots.add(provenance.source_snapshot_id)
        applied_offer = item.applied_offer
        member_rows += int(
            applied_offer is not None
            and (
                str(applied_offer.kind.value) == "member"
                or applied_offer.member_program is not None
            )
        )
    return {
        "status": "PASS" if not missing and fallback_rows == 0 and member_rows == 0 else "FAIL",
        "rows": len(items),
        "complete_rows": len(items) - len(missing),
        "missing": missing,
        "providers": dict(sorted(providers.items())),
        "chains": dict(sorted(chains.items())),
        "contexts": len(contexts),
        "snapshots": sorted(snapshots),
        "fallback_rows": fallback_rows,
        "member_price_rows": member_rows,
        # Source confidence and matcher/resolver confidence are intentionally
        # separate facts. Differences are useful diagnostics, not missing
        # provenance and never silently overwrite either value.
        "semantic_confidence_disagreements": semantic_confidence_disagreements,
        "quantity_confidence_disagreements": quantity_confidence_disagreements,
    }


def _basket_items(basket: Any) -> list[Any]:
    return [item for group in basket.stores for item in group.items]


def _basket_summary(basket: Any, audit: Any, provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": (
            "PASS"
            if basket.verification_status.value in {"VERIFIED", "VERIFIED_WITH_ESTIMATES"}
            and audit.status.value == "PASS"
            and audit.totals_reconciled
            and provenance["status"] == "PASS"
            else "FAIL"
        ),
        "complete_for_request": not audit.deficits,
        "total_sek": float(Decimal(str(basket.total)).quantize(_CENT)),
        "store_count": len(basket.stores),
        "stores": [
            {
                "context_id": group.store_id,
                "name": group.store_name,
                "subtotal_sek": group.subtotal,
                "items": [
                    {
                        "ingredient": item.ingredient,
                        "product_id": item.product_id,
                        "product": item.product_name,
                        "total_sek": item.total_price,
                        "sale_model": item.sale_model.value,
                        "quantity_confidence": item.quantity_confidence.value,
                        "semantic_confidence": item.semantic_confidence.value,
                        "source": (
                            item.source_provenance.model_dump(mode="json")
                            if item.source_provenance is not None
                            else None
                        ),
                    }
                    for item in group.items
                ],
            }
            for group in basket.stores
        ],
        "verification_status": basket.verification_status.value,
        "basket_audit": {
            "status": audit.status.value,
            "verification_status": audit.verification_status.value,
            "deficits": [row.canonical_name for row in audit.deficits],
            "totals_reconciled": audit.totals_reconciled,
            "calculated_total": audit.calculated_total,
            "reported_total": audit.reported_total,
        },
        "provenance": dict(provenance),
    }


def _exclude_terminal_provider_contexts(
    stores: Sequence[Any],
    terminal_context_gaps: Sequence[Mapping[str, Any]],
) -> tuple[list[Any], list[dict[str, str]]]:
    excluded_contexts = {
        (str(row.get("chain") or "").casefold(), str(row.get("external_id") or ""))
        for row in terminal_context_gaps
    }
    eligible_stores: list[Any] = []
    rejected: list[dict[str, str]] = []
    for store in stores:
        provenance = store.source_provenance
        external_id = str(
            store.source_store_id
            or (provenance.provider_store_id if provenance is not None else "")
        )
        identity = (store.chain.casefold(), external_id)
        if identity in excluded_contexts:
            rejected.append(
                {
                    "chain": identity[0],
                    "external_id": identity[1],
                    "context_id": store.store_id,
                }
            )
            continue
        eligible_stores.append(store)
    return eligible_stores, rejected


class _TerminalContextFilteredProvider:
    """Non-owning benchmark facade that keeps terminal contexts out end-to-end."""

    def __init__(
        self,
        provider: Any,
        terminal_context_gaps: Sequence[Mapping[str, Any]],
    ) -> None:
        self._provider = provider
        self._terminal_context_gaps = tuple(terminal_context_gaps)
        self._allowed_store_ids: frozenset[str] = frozenset()
        self._rejected_by_context_id: dict[str, dict[str, str]] = {}

    @property
    def rejected_contexts(self) -> list[dict[str, str]]:
        return [self._rejected_by_context_id[key] for key in sorted(self._rejected_by_context_id)]

    @property
    def diagnostics(self) -> Any:
        return getattr(self._provider, "diagnostics", ())

    async def find_stores(self, postal_code: str) -> list[Any]:
        stores = await self._provider.find_stores(postal_code)
        eligible, rejected = _exclude_terminal_provider_contexts(
            stores,
            self._terminal_context_gaps,
        )
        self._allowed_store_ids = frozenset(str(store.store_id) for store in eligible)
        for row in rejected:
            self._rejected_by_context_id[row["context_id"]] = row
        return eligible

    async def search_products(self, query: str, store_ids: list[str]) -> list[Any]:
        allowed = [store_id for store_id in store_ids if store_id in self._allowed_store_ids]
        if not allowed:
            return []
        products = await self._provider.search_products(query, allowed)
        return [product for product in products if product.store_id in self._allowed_store_ids]

    async def get_store_products(self, store_id: str) -> list[Any]:
        if store_id not in self._allowed_store_ids:
            return []
        products = await self._provider.get_store_products(store_id)
        return [product for product in products if product.store_id == store_id]

    async def get_offers(self, store_id: str) -> list[Any]:
        if store_id not in self._allowed_store_ids:
            return []
        products = await self._provider.get_offers(store_id)
        return [product for product in products if product.store_id == store_id]


async def _representative_baskets(
    provider: Any,
    postal_code: str,
    *,
    mode: str,
    require_complete_lund_universe: bool,
    terminal_context_gaps: Sequence[Mapping[str, Any]] = (),
    required_external_chains: frozenset[str] = frozenset(),
) -> dict[str, Any]:
    from app.models import NormalizedIngredient
    from app.services.basket_auditor import BasketAuditor
    from app.services.product_matcher import ProductMatcher
    from scripts.benchmark_verification import strict_live_basket_optimizer

    provider_stores = await provider.find_stores(postal_code)
    excluded_contexts = {
        (str(row.get("chain") or "").casefold(), str(row.get("external_id") or ""))
        for row in terminal_context_gaps
    }
    stores, terminal_contexts_returned = _exclude_terminal_provider_contexts(
        provider_stores,
        terminal_context_gaps,
    )
    represented_chains = {store.chain.casefold() for store in stores}
    expected_chains = {"willys", "hemkop"}
    if mode == "federated":
        expected_chains.update(required_external_chains)
    explained_but_ineligible_chains = (
        sorted({"ica", "coop", "lidl"} - required_external_chains) if mode == "federated" else []
    )
    missing_chains = (
        sorted(expected_chains - represented_chains) if require_complete_lund_universe else []
    )
    store_ids = [store.store_id for store in stores]
    ingredients = [
        NormalizedIngredient(
            canonical_name=row.canonical,
            display_name=row.canonical,
            required_quantity=row.quantity,
            unit=row.unit,
        )
        for row in REPRESENTATIVE_REQUIREMENTS
    ]
    matcher = ProductMatcher()
    products_by_name: dict[str, list[Any]] = {}
    candidates_by_name: dict[str, list[Any]] = {}
    for ingredient in ingredients:
        products = await provider.search_products(ingredient.canonical_name, store_ids)
        products_by_name[ingredient.canonical_name] = products
        candidates_by_name[ingredient.canonical_name] = matcher.match(
            ingredient,
            products,
            store_ids=store_ids,
        )
    missing = [
        ingredient.canonical_name
        for ingredient in ingredients
        if not candidates_by_name[ingredient.canonical_name]
    ]
    result: dict[str, Any] = {
        "requirements_version": "lund-representative-v1",
        "requested": len(ingredients),
        "stores_considered": [
            {
                "context_id": store.store_id,
                "name": store.name,
                "chain": store.chain,
                "coverage": store.coverage,
                "price_context": store.price_context_type,
                "source": (
                    store.source_provenance.model_dump(mode="json")
                    if store.source_provenance is not None
                    else None
                ),
            }
            for store in stores
        ],
        "candidate_counts": {name: len(candidates_by_name[name]) for name in candidates_by_name},
        "raw_product_counts": {name: len(rows) for name, rows in products_by_name.items()},
        "missing_ingredients": missing,
        "store_universe_gate": {
            "status": ("PASS" if not missing_chains and not terminal_contexts_returned else "FAIL"),
            "represented_chains": sorted(represented_chains),
            "expected_chains": sorted(expected_chains),
            "missing_chains": missing_chains,
            "explained_but_ineligible_chains": explained_but_ineligible_chains,
            "citygross": "NO_LUND_CONTEXT",
        },
        "terminal_context_exclusion_gate": {
            "status": "PASS" if not terminal_contexts_returned else "FAIL",
            "declared_terminal_contexts": [
                {
                    "chain": chain,
                    "external_id": external_id,
                }
                for chain, external_id in sorted(excluded_contexts)
            ],
            "provider_rows_rejected": terminal_contexts_returned,
        },
        "scenarios": {},
    }
    invalid_willys_contexts = [
        store.store_id
        for store in stores
        if store.chain == "willys" and store.price_context_type != "online_store"
    ]
    result["willys_online_context_gate"] = {
        "status": "PASS" if not invalid_willys_contexts else "FAIL",
        "invalid_context_ids": invalid_willys_contexts,
    }
    if missing or missing_chains or terminal_contexts_returned:
        for max_stores in (1, 2, 3):
            result["scenarios"][f"max_stores_{max_stores}"] = {
                "status": "FAIL",
                "complete_for_request": False,
                "total_sek": None,
                "missing_ingredients": missing,
                "missing_chains": missing_chains,
                "terminal_contexts_returned": terminal_contexts_returned,
            }
        return result

    optimizer = strict_live_basket_optimizer()
    auditor = BasketAuditor()
    for max_stores in (1, 2, 3):
        started = perf_counter()
        try:
            basket = optimizer.optimize(
                ingredients,
                candidates_by_name,
                stores,
                max_stores=max_stores,
            )
            audit = auditor.audit(ingredients, basket)
            summary = _basket_summary(
                basket,
                audit,
                _provenance_gate(_basket_items(basket)),
            )
        except Exception as exc:  # noqa: BLE001 - only sanitized type is retained
            summary = {
                "status": "FAIL",
                "complete_for_request": False,
                "total_sek": None,
                "error_type": type(exc).__name__,
            }
        summary["runtime_seconds"] = round(perf_counter() - started, 4)
        result["scenarios"][f"max_stores_{max_stores}"] = summary
    return result


async def _menu_plan(
    provider: Any,
    *,
    postal_code: str,
    candidate_count: int,
    beam_width: int,
    diversity_mode: str,
    max_stores: int,
    terminal_context_gaps: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    from app.config import Settings
    from app.models import DiversityMode, PlanRequest
    from app.services.meal_plan_optimizer import MealPlanService
    from scripts.benchmark_plan import _summary

    mode = DiversityMode(diversity_mode)
    request = PlanRequest(
        postal_code=postal_code,
        recipes=5,
        servings=4,
        max_stores=max_stores,
        memberships={
            "ica": False,
            "coop": False,
            "willys": False,
            "hemkop": False,
            "citygross": False,
            "lidl": False,
        },
        optimization_iterations=0,
        strategy="optimized",
        candidate_recipe_count=candidate_count,
        beam_width=beam_width,
        diversity_mode=mode,
        debug=True,
    )
    service = MealPlanService(
        Settings(
            price_provider="federated",
            meal_plan_strategy="optimized",
            openai_api_key=None,
            allow_mock_fallback=False,
            allow_medium_semantic_matches=False,
            allow_estimated_quantities=True,
            allow_unknown_quantities=False,
            allow_unknown_sale_model=False,
        )
    )
    filtered_provider = _TerminalContextFilteredProvider(provider, terminal_context_gaps)
    started = perf_counter()
    try:
        response = await service._build_optimized_with_provider(request, filtered_provider)
    except Exception as exc:  # noqa: BLE001 - only sanitized type is retained
        return {
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "runtime_seconds": round(perf_counter() - started, 4),
        }
    elapsed = perf_counter() - started
    data = response.model_dump(mode="json")
    summary = _summary(data, elapsed)
    provenance = _provenance_gate(_basket_items(response.optimized_basket))
    quality = response.quality
    quality_pass = bool(
        quality is not None
        and quality.status.value == "PASS"
        and quality.basket_audit.status.value == "PASS"
        and quality.basket_audit.totals_reconciled
        and quality.nutrition.status.value == "PASS"
        and quality.diversity.status.value == "PASS"
    )
    terminal_contexts_returned = filtered_provider.rejected_contexts
    return {
        "status": (
            "PASS"
            if quality_pass and provenance["status"] == "PASS" and not terminal_contexts_returned
            else "FAIL"
        ),
        "scenario": {
            "recipes": 5,
            "servings": 4,
            "diversity_mode": mode.value,
            "max_stores": max_stores,
            "candidate_count": candidate_count,
            "beam_width": beam_width,
            "member_prices": False,
        },
        "result": summary,
        "provenance": provenance,
        "terminal_context_exclusion_gate": {
            "status": "PASS" if not terminal_contexts_returned else "FAIL",
            "declared_terminal_contexts": [
                {
                    "chain": str(row.get("chain") or "").casefold(),
                    "external_id": str(row.get("external_id") or ""),
                }
                for row in terminal_context_gaps
            ],
            "provider_rows_rejected": terminal_contexts_returned,
        },
    }


async def _menu_matrix(
    provider: Any,
    *,
    postal_code: str,
    candidate_count: int,
    beam_width: int,
    terminal_context_gaps: Sequence[Mapping[str, Any]] = (),
) -> dict[str, dict[str, Any]]:
    """Run the required 5x4 diversity/store-limit matrix on one provider cache."""

    result: dict[str, dict[str, Any]] = {}
    for diversity_mode in ("cheapest", "balanced", "varied"):
        scenarios: dict[str, Any] = {}
        for max_stores in (1, 2):
            scenarios[f"max_stores_{max_stores}"] = await _menu_plan(
                provider,
                postal_code=postal_code,
                candidate_count=candidate_count,
                beam_width=beam_width,
                diversity_mode=diversity_mode,
                max_stores=max_stores,
                terminal_context_gaps=terminal_context_gaps,
            )
        result[diversity_mode] = scenarios
    return result


async def _run_database(
    path: Path,
    *,
    mode: str,
    postal_code: str,
    external_cache: Path | None,
    bounded_primat_live: bool,
    primat_max_requests: int,
    frozen_cache_output: Path | None,
    candidate_count: int,
    beam_width: int,
    max_price_age_hours: float,
    freshness_now: datetime,
    require_complete_lund_universe: bool,
    terminal_context_gaps: Sequence[Mapping[str, Any]],
    required_external_chains: frozenset[str],
    representative_only: bool,
) -> dict[str, Any]:
    before = _file_state(path)
    provider = client = engine = external_provider = None
    started = perf_counter()
    compatibility_needed = False
    network_attempts = 0
    try:
        provider, client, engine, compatibility_needed, external_provider = await _provider_for(
            path,
            mode=mode,
            postal_code=postal_code,
            external_cache=external_cache,
            bounded_primat_live=bounded_primat_live,
            primat_max_requests=primat_max_requests,
            max_price_age_hours=max_price_age_hours,
            freshness_now=freshness_now,
        )
        if bounded_primat_live:
            representative = await _representative_baskets(
                provider,
                postal_code,
                mode=mode,
                require_complete_lund_universe=require_complete_lund_universe,
                terminal_context_gaps=terminal_context_gaps,
                required_external_chains=required_external_chains,
            )
            menus = (
                {}
                if representative_only
                else await _menu_matrix(
                    provider,
                    postal_code=postal_code,
                    candidate_count=candidate_count,
                    beam_width=beam_width,
                    terminal_context_gaps=terminal_context_gaps,
                )
            )
        else:
            with _network_disabled() as attempts:
                try:
                    representative = await _representative_baskets(
                        provider,
                        postal_code,
                        mode=mode,
                        require_complete_lund_universe=require_complete_lund_universe,
                        terminal_context_gaps=terminal_context_gaps,
                        required_external_chains=required_external_chains,
                    )
                    menus = (
                        {}
                        if representative_only
                        else await _menu_matrix(
                            provider,
                            postal_code=postal_code,
                            candidate_count=candidate_count,
                            beam_width=beam_width,
                            terminal_context_gaps=terminal_context_gaps,
                        )
                    )
                finally:
                    network_attempts = attempts["count"]
        transport_report = (
            external_provider.transport_report
            if external_provider is not None and hasattr(external_provider, "transport_report")
            else {
                "mode": "frozen_external" if external_provider is not None else "own_only",
                "requests": 0,
                "denied_requests": 0,
            }
        )
        licensed_requests = int(transport_report.get("requests", 0))
        denied_requests = int(transport_report.get("denied_requests", 0))
        transport_ok = (
            licensed_requests <= primat_max_requests and denied_requests == 0
            if bounded_primat_live
            else network_attempts == 0
        )
        diagnostics = [row.model_dump(mode="json") for row in provider.diagnostics]
        menu_rows = [scenario for scenarios in menus.values() for scenario in scenarios.values()]
        benchmark_pass = bool(
            all(row.get("status") == "PASS" for row in representative["scenarios"].values())
            and all(row.get("status") == "PASS" for row in menu_rows)
            and transport_ok
        )
        cache_export: dict[str, Any] | None = None
        if frozen_cache_output is not None:
            from app.services.primat_phase_c_export import (
                BoundedPrimatPhaseCExporter,
                load_active_physical_stores,
                write_closed_json,
            )

            if external_provider is None:
                raise ValueError("frozen cache export requires the bounded Primat provider")
            if not benchmark_pass:
                raise RuntimeError("a failed benchmark cannot be exported as a frozen cache")
            exporter = BoundedPrimatPhaseCExporter(
                external_provider,
                load_active_physical_stores(path),
                postal_code=postal_code,
            )
            # ``find_stores`` is request-scoped in the bounded provider. This
            # resolves from that immutable cache and spends zero extra HTTP
            # requests after the benchmark provider has already discovered it.
            requests_before_export = int(external_provider.transport_report["requests"])
            contexts = await exporter.resolve_once()
            requests_after_resolve = int(external_provider.transport_report["requests"])
            if requests_after_resolve != requests_before_export:
                raise RuntimeError("frozen cache export spent an extra store-resolution request")
            bundle = exporter.frozen_external_cache()
            written = write_closed_json(frozen_cache_output, bundle)
            cache_export = {
                "file": Path(str(written["path"])).name,
                "bytes": written["bytes"],
                "sha256": _sha256(frozen_cache_output.resolve(strict=True)),
                "stores": len(bundle.stores),
                "products": len(bundle.products),
                "contexts": len(contexts),
                "additional_requests": requests_after_resolve - requests_before_export,
                "credentials_included": written["credentials_included"],
                "headers_included": written["headers_included"],
                "cookies_included": written["cookies_included"],
                "raw_responses_included": written["raw_responses_included"],
            }
        result: dict[str, Any] = {
            "status": "PASS" if benchmark_pass else "FAIL",
            "representative_basket": representative,
            "menus_5x4": menus,
            # Retain the original report field for downstream readers while
            # the complete matrix is exposed under ``menus_5x4``.
            "balanced_5x4": (
                None if representative_only else menus["balanced"]["max_stores_2"]
            ),
            "source_diagnostics": diagnostics,
            "transport": transport_report,
            "frozen_cache_export": cache_export,
            "terminal_context_gaps": list(terminal_context_gaps),
            "warnings": [
                (
                    f"{row['chain']} context {row['external_id']} was terminally unavailable "
                    "and excluded"
                )
                for row in terminal_context_gaps
            ],
        }
    except Exception as exc:  # noqa: BLE001 - output must never copy exception text
        result = {"status": "FAIL", "error_type": type(exc).__name__}
        if external_provider is not None and hasattr(external_provider, "transport_report"):
            result["transport"] = external_provider.transport_report
    finally:
        if provider is not None:
            await provider.aclose()
        if client is not None:
            await client.aclose()
        if engine is not None:
            engine.dispose()
    after = _file_state(path)
    immutable_unchanged = before == after
    result.update(
        {
            "database": before,
            "legacy_temp_store_projection": compatibility_needed,
            "network_attempts": network_attempts,
            "immutable_unchanged": immutable_unchanged,
            "runtime_seconds": round(perf_counter() - started, 4),
        }
    )
    if not immutable_unchanged:
        result["status"] = "FAIL"
    return result


def _comparison(results: Mapping[str, Any]) -> dict[str, Any]:
    baseline = results.get("baseline", {})
    candidate = results.get("candidate", {})
    baseline_replay = (
        baseline.get("representative_basket", {}).get("scenarios", {}).get("max_stores_2", {})
    )
    candidate_replay = (
        candidate.get("representative_basket", {}).get("scenarios", {}).get("max_stores_2", {})
    )
    old_total = HISTORICAL_OLD_LUND_RESULT["representative_basket"]["total_sek"]
    candidate_total = candidate_replay.get("total_sek")
    replay_baseline_total = baseline_replay.get("total_sek")
    return {
        "historical_old_vs_candidate": {
            "old_complete": False,
            "old_missing": ["yellow_onion"],
            "old_total_sek": old_total,
            "candidate_complete": candidate_replay.get("complete_for_request"),
            "candidate_total_sek": candidate_total,
            # Never manufacture a numeric delta from an invalid old basket.
            "price_delta_sek": None,
            "coverage_changed": candidate_replay.get("complete_for_request") is True,
        },
        "current_code_immutable_replay": {
            "baseline_total_sek": replay_baseline_total,
            "candidate_total_sek": candidate_total,
            "delta_sek": (
                round(float(candidate_total) - float(replay_baseline_total), 2)
                if candidate_total is not None and replay_baseline_total is not None
                else None
            ),
            "note": "This isolates snapshot coverage under current code; it is not the OLD result.",
        },
    }


async def _run(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    postal_code = "".join(character for character in args.postal_code if character.isdigit())
    if len(postal_code) != 5:
        raise ValueError("postal_code must contain five digits")
    if args.candidate_count < 10 or args.candidate_count > 300:
        raise ValueError("candidate-count must be between 10 and 300")
    if args.beam_width < 5 or args.beam_width > 100:
        raise ValueError("beam-width must be between 5 and 100")
    if not isfinite(args.max_price_age_hours) or args.max_price_age_hours <= 0:
        raise ValueError("max-price-age-hours must be finite and positive")
    if args.primat_max_requests < 1 or args.primat_max_requests > 200:
        raise ValueError("primat-max-requests must be between 1 and 200")
    if args.mode == "own-only" and (
        args.external_cache is not None
        or args.allow_bounded_primat_live
        or args.frozen_cache_output is not None
    ):
        raise ValueError("OWN-only mode cannot configure an external provider")
    if args.mode == "federated" and (
        (args.external_cache is None) == (not args.allow_bounded_primat_live)
    ):
        raise ValueError(
            "federated mode requires exactly one of --external-cache and "
            "--allow-bounded-primat-live"
        )
    if args.frozen_cache_output is not None and (
        args.mode != "federated"
        or not args.allow_bounded_primat_live
        or args.database != "candidate"
    ):
        raise ValueError(
            "--frozen-cache-output requires one candidate federated bounded-Primat run"
        )
    if args.frozen_cache_output is not None and args.frozen_cache_output.exists():
        raise FileExistsError("--frozen-cache-output refuses to overwrite an existing file")

    selected: list[tuple[str, Path]] = []
    if args.database in {"baseline", "both"}:
        selected.append(("baseline", args.baseline_db))
    if args.database in {"candidate", "both"}:
        selected.append(("candidate", args.candidate_db))

    freshness_now = datetime.now(tz=UTC)
    readiness = {
        label: _readiness(
            path,
            mode=args.mode,
            external_cache=args.external_cache,
            bounded_primat_live=args.allow_bounded_primat_live,
            max_age_hours=args.max_price_age_hours,
            now=freshness_now,
        )
        for label, path in selected
    }
    not_ready = sorted(label for label, report in readiness.items() if not report["ready"])
    if not_ready and not args.allow_incomplete_phase_c:
        return (
            {
                "benchmark": "lund_phase_c",
                "status": "NOT_READY",
                "mode": args.mode,
                "historical_old_lund": HISTORICAL_OLD_LUND_RESULT,
                "readiness": readiness,
                "results": {},
                "note": (
                    "No benchmark was run because readiness failed for: "
                    + ", ".join(not_ready)
                    + ". Use --allow-incomplete-phase-c only for diagnostics."
                ),
            },
            2,
        )

    results: dict[str, Any] = {}
    for label, path in selected:
        results[label] = await _run_database(
            path,
            mode=args.mode,
            postal_code=postal_code,
            external_cache=args.external_cache,
            bounded_primat_live=args.allow_bounded_primat_live,
            primat_max_requests=args.primat_max_requests,
            frozen_cache_output=args.frozen_cache_output,
            candidate_count=args.candidate_count,
            beam_width=args.beam_width,
            max_price_age_hours=args.max_price_age_hours,
            freshness_now=freshness_now,
            require_complete_lund_universe=label == "candidate",
            terminal_context_gaps=readiness[label].get("terminal_context_gaps", ()),
            required_external_chains=frozenset(
                str(row["chain"])
                for row in readiness[label].get("exact_external_context_links", ())
                if str(row.get("chain") or "") in {"ica", "coop", "lidl"}
            ),
            representative_only=args.representative_only,
        )
    status = (
        "PASS"
        if results and all(row.get("status") == "PASS" for row in results.values())
        else "FAIL"
    )
    return (
        {
            "benchmark": "lund_phase_c",
            "status": status,
            "mode": args.mode,
            "network_policy": (
                "bounded_primat_only" if args.allow_bounded_primat_live else "disabled"
            ),
            "primat_max_requests": (
                args.primat_max_requests if args.allow_bounded_primat_live else 0
            ),
            "postal_code": postal_code,
            "max_price_age_hours": args.max_price_age_hours,
            "freshness_evaluated_at": freshness_now.isoformat().replace("+00:00", "Z"),
            "historical_old_lund": HISTORICAL_OLD_LUND_RESULT,
            "readiness": readiness,
            "results": results,
            "comparison": _comparison(results),
        },
        0 if status == "PASS" else 1,
    )


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        result, exit_code = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - never include paths, payloads or credentials
        result = {
            "benchmark": "lund_phase_c",
            "status": "FAIL",
            "error_type": type(exc).__name__,
        }
        exit_code = 1
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(rendered)
            output.write("\n")
    print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
