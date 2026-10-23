"""Small append-only SQLite store for anonymous consumer plans.

The plan payload contains the exact product/snapshot provenance returned to the
shopper.  Revisions are never updated in place, so revisiting a plan does not
silently reprice it when the active PriceUniverse changes.
"""

from __future__ import annotations

import hmac
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.models import PlanRequest, PlanResponse, SavedPlan
from app.services.member_accounts import SCHEMA as MEMBER_SCHEMA
from app.services.personal_store import SCHEMA as PERSONAL_SCHEMA
from app.services.personal_store import PersonalConflict, read_state, reserve_plan, write_state
from app.services.planner_artifacts import SCHEMA as PLANNER_ARTIFACT_SCHEMA

_SCHEMA = """
CREATE TABLE IF NOT EXISTS consumer_plan_revisions (
    plan_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    parent_revision INTEGER,
    created_at TEXT NOT NULL,
    operation TEXT NOT NULL CHECK (
        operation IN ('created', 'recipe_replaced', 'product_replaced')
    ),
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    price_universe_id TEXT,
    diversity_mode TEXT NOT NULL,
    diet_preference TEXT NOT NULL,
    max_stores INTEGER NOT NULL,
    meal_count INTEGER NOT NULL,
    servings INTEGER NOT NULL,
    app_version TEXT NOT NULL DEFAULT '0.1.0',
    build_id TEXT NOT NULL DEFAULT 'local',
    owner_actor_hash TEXT,
    PRIMARY KEY (plan_id, revision)
);
CREATE INDEX IF NOT EXISTS ix_consumer_plan_latest
    ON consumer_plan_revisions (plan_id, revision DESC);
CREATE INDEX IF NOT EXISTS ix_consumer_plan_created
    ON consumer_plan_revisions (created_at DESC);
"""


class PlanNotFoundError(KeyError):
    pass


class PlanReadOnlyError(PermissionError):
    """Raised when a legacy plan has no owner capability to authorize writes."""


class PlanOwnerMismatchError(PermissionError):
    """Raised when a write does not come from the plan's creating actor."""


@dataclass(frozen=True, slots=True)
class OwnedPlanErasureResult:
    """Opaque internal result used to purge associated privacy-safe metrics."""

    plan_ids: tuple[str, ...]
    revisions_deleted: int

    @property
    def plans_deleted(self) -> int:
        return len(self.plan_ids)


class PlanStore:
    """Append and load immutable plan revisions with process-safe locking."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            connection.executescript(PERSONAL_SCHEMA)
            connection.executescript(MEMBER_SCHEMA)
            connection.executescript(PLANNER_ARTIFACT_SCHEMA)
            existing = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(consumer_plan_revisions)"
                ).fetchall()
            }
            additions = {
                "diversity_mode": "TEXT NOT NULL DEFAULT 'balanced'",
                "diet_preference": "TEXT NOT NULL DEFAULT 'mixed'",
                "max_stores": "INTEGER NOT NULL DEFAULT 2",
                "meal_count": "INTEGER NOT NULL DEFAULT 5",
                "servings": "INTEGER NOT NULL DEFAULT 4",
                "app_version": "TEXT NOT NULL DEFAULT '0.1.0'",
                "build_id": "TEXT NOT NULL DEFAULT 'local'",
                # Nullable by design: rows created before ownership was added
                # remain readable, but cannot acquire an owner retroactively.
                "owner_actor_hash": "TEXT",
            }
            for name, declaration in additions.items():
                if name not in existing:
                    # Both identifier and declaration come from the static map
                    # above; user input is never interpolated into DDL.
                    connection.execute(
                        f"ALTER TABLE consumer_plan_revisions ADD COLUMN {name} {declaration}"
                    )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _consumer_safe_response(response: PlanResponse) -> PlanResponse:
        """Remove internal diagnostics before the immutable consumer write."""

        return response.model_copy(
            update={"source_diagnostics": [], "debug_info": None},
            deep=True,
        )

    @staticmethod
    def _validate_owner_actor_hash(owner_actor_hash: str | None) -> None:
        if owner_actor_hash is None:
            return
        if len(owner_actor_hash) != 64 or any(
            character not in "0123456789abcdef" for character in owner_actor_hash
        ):
            raise ValueError("owner_actor_hash must be a lowercase SHA-256 digest")

    @staticmethod
    def _assert_owner(
        stored_owner_actor_hash: str | None,
        supplied_owner_actor_hash: str | None,
    ) -> None:
        if stored_owner_actor_hash is None:
            raise PlanReadOnlyError("saved plan has no owner capability")
        if supplied_owner_actor_hash is None or not hmac.compare_digest(
            stored_owner_actor_hash,
            supplied_owner_actor_hash,
        ):
            raise PlanOwnerMismatchError("saved plan owner does not match")

    @staticmethod
    def _materialize(row: sqlite3.Row) -> SavedPlan:
        return SavedPlan(
            plan_id=row["plan_id"],
            revision=row["revision"],
            parent_revision=row["parent_revision"],
            created_at=datetime.fromisoformat(row["created_at"]),
            operation=row["operation"],
            app_version=row["app_version"],
            build_id=row["build_id"],
            request=PlanRequest.model_validate_json(row["request_json"]),
            plan=PlanResponse.model_validate_json(row["response_json"]),
            price_universe_id=row["price_universe_id"],
        )

    def create(
        self,
        request: PlanRequest,
        response: PlanResponse,
        *,
        owner_actor_hash: str | None = None,
    ) -> SavedPlan:
        plan_id = str(uuid4())
        return self._append(
            plan_id=plan_id,
            request=request,
            response=response,
            operation="created",
            expected_parent=None,
            owner_actor_hash=owner_actor_hash,
        )

    def append(
        self,
        *,
        plan_id: str,
        request: PlanRequest,
        response: PlanResponse,
        operation: str,
        expected_parent: int,
        owner_actor_hash: str | None,
        mutation_key: str | None = None,
    ) -> SavedPlan:
        return self._append(
            plan_id=plan_id,
            request=request,
            response=response,
            operation=operation,
            expected_parent=expected_parent,
            owner_actor_hash=owner_actor_hash,
            mutation_key=mutation_key,
        )

    def _append(
        self,
        *,
        plan_id: str,
        request: PlanRequest,
        response: PlanResponse,
        operation: str,
        expected_parent: int | None,
        owner_actor_hash: str | None,
        mutation_key: str | None = None,
    ) -> SavedPlan:
        self._validate_owner_actor_hash(owner_actor_hash)
        response = self._consumer_safe_response(response)
        observed_at = datetime.now(UTC)
        price_universe_id = response.data.price_universe_id if response.data else None
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if mutation_key and owner_actor_hash:
                state = read_state(connection, owner_actor_hash)
                prior = state.get("mutations", {}).get(mutation_key)
                if prior:
                    return self.get_owned(
                        plan_id, owner_actor_hash=owner_actor_hash, revision=prior
                    )
            row = connection.execute(
                """
                SELECT revision, owner_actor_hash
                FROM consumer_plan_revisions
                WHERE plan_id = ?
                ORDER BY revision DESC
                LIMIT 1
                """,
                (plan_id,),
            ).fetchone()
            current = int(row["revision"]) if row is not None else None
            if expected_parent is None:
                if current is not None:
                    raise ValueError("plan_id already exists")
                revision = 1
                parent_revision = None
                persisted_owner_actor_hash = owner_actor_hash
            else:
                if current is None:
                    raise PlanNotFoundError(plan_id)
                self._assert_owner(row["owner_actor_hash"], owner_actor_hash)
                if current != expected_parent:
                    if response.personal:
                        raise PersonalConflict("Planrevisionen har ändrats. Läs om innan ändring.")
                    raise ValueError("plan revision changed; reload before updating")
                revision = current + 1
                parent_revision = current
                persisted_owner_actor_hash = row["owner_actor_hash"]
            if response.personal is not None:
                if not persisted_owner_actor_hash:
                    raise PlanOwnerMismatchError("private planning requires an owner")
                reserve_plan(connection, persisted_owner_actor_hash, plan_id, response.personal)
                if mutation_key:
                    state = read_state(connection, persisted_owner_actor_hash)
                    state.setdefault("mutations", {})[mutation_key] = revision
                    write_state(connection, persisted_owner_actor_hash, state, state["revision"])
            connection.execute(
                """
                INSERT INTO consumer_plan_revisions (
                    plan_id, revision, parent_revision, created_at, operation,
                    request_json, response_json, price_universe_id,
                    diversity_mode, diet_preference, max_stores, meal_count, servings,
                    app_version, build_id, owner_actor_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    revision,
                    parent_revision,
                    observed_at.isoformat(),
                    operation,
                    request.model_dump_json(),
                    response.model_dump_json(),
                    price_universe_id,
                    request.diversity_mode.value,
                    request.diet_preference.value,
                    request.max_stores,
                    request.recipes,
                    request.servings,
                    response.app_version,
                    response.build_id,
                    persisted_owner_actor_hash,
                ),
            )
        return SavedPlan(
            plan_id=plan_id,
            revision=revision,
            parent_revision=parent_revision,
            created_at=observed_at,
            operation=operation,  # type: ignore[arg-type]
            app_version=response.app_version,
            build_id=response.build_id,
            request=request,
            plan=response,
            price_universe_id=price_universe_id,
        )

    def get(self, plan_id: str, *, revision: int | None = None) -> SavedPlan:
        with self._connect() as connection:
            if revision is None:
                row = connection.execute(
                    """
                    SELECT *
                    FROM consumer_plan_revisions
                    WHERE plan_id = ?
                    ORDER BY revision DESC
                    LIMIT 1
                    """,
                    (plan_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT *
                    FROM consumer_plan_revisions
                    WHERE plan_id = ? AND revision = ?
                    """,
                    (plan_id, revision),
                ).fetchone()
        if row is None:
            raise PlanNotFoundError(plan_id)
        return self._materialize(row)

    def get_owned(
        self,
        plan_id: str,
        *,
        owner_actor_hash: str | None,
        revision: int | None = None,
    ) -> SavedPlan:
        """Load a revision only when the caller owns its anonymous capability."""

        self._validate_owner_actor_hash(owner_actor_hash)
        with self._connect() as connection:
            if revision is None:
                row = connection.execute(
                    """
                    SELECT *
                    FROM consumer_plan_revisions
                    WHERE plan_id = ?
                    ORDER BY revision DESC
                    LIMIT 1
                    """,
                    (plan_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT *
                    FROM consumer_plan_revisions
                    WHERE plan_id = ? AND revision = ?
                    """,
                    (plan_id, revision),
                ).fetchone()
        if row is None:
            raise PlanNotFoundError(plan_id)
        self._assert_owner(row["owner_actor_hash"], owner_actor_hash)
        return self._materialize(row)

    def owned_plan_ids(self, *, owner_actor_hash: str) -> tuple[str, ...]:
        """Return only plan IDs protected by the supplied owner capability.

        This read is used immediately before privacy erasure so request metrics
        carrying one of those opaque IDs can be removed. Legacy NULL-owner rows
        deliberately remain outside the result.
        """

        self._validate_owner_actor_hash(owner_actor_hash)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT plan_id
                FROM consumer_plan_revisions
                WHERE owner_actor_hash = ?
                ORDER BY plan_id
                """,
                (owner_actor_hash,),
            ).fetchall()
        return tuple(str(row["plan_id"]) for row in rows)

    def erase_owned(self, *, owner_actor_hash: str) -> OwnedPlanErasureResult:
        """Atomically erase every revision owned by one anonymous capability.

        The select/count and delete share one ``BEGIN IMMEDIATE`` transaction.
        Ownerless legacy rows and rows belonging to other actors are untouched.
        Repeating the operation is safe and returns zero counts.
        """

        self._validate_owner_actor_hash(owner_actor_hash)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                """
                SELECT plan_id, COUNT(*) AS revision_count
                FROM consumer_plan_revisions
                WHERE owner_actor_hash = ?
                GROUP BY plan_id
                ORDER BY plan_id
                """,
                (owner_actor_hash,),
            ).fetchall()
            result = OwnedPlanErasureResult(
                plan_ids=tuple(str(row["plan_id"]) for row in rows),
                revisions_deleted=sum(int(row["revision_count"]) for row in rows),
            )
            connection.execute(
                """
                DELETE FROM consumer_plan_revisions
                WHERE owner_actor_hash = ?
                """,
                (owner_actor_hash,),
            )
            connection.execute(
                "DELETE FROM personal_private_state WHERE owner_actor_hash = ?", (owner_actor_hash,)
            )
            connection.execute(
                "DELETE FROM planner_owned_artifacts WHERE owner_actor_hash = ?", (owner_actor_hash,)
            )
        return result

    def aggregate_metrics(self) -> list[dict[str, object]]:
        """Return privacy-safe counts; no plan/session identifier is exposed."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT diversity_mode, diet_preference, max_stores,
                       meal_count, servings, COUNT(*) AS plans_generated
                FROM consumer_plan_revisions
                WHERE operation = 'created'
                GROUP BY diversity_mode, diet_preference, max_stores,
                         meal_count, servings
                ORDER BY diversity_mode, diet_preference, max_stores,
                         meal_count, servings
                """
            ).fetchall()
        return [dict(row) for row in rows]


__all__ = [
    "OwnedPlanErasureResult",
    "PlanNotFoundError",
    "PlanOwnerMismatchError",
    "PlanReadOnlyError",
    "PlanStore",
]
