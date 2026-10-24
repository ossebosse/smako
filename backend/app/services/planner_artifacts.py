"""Bounded immutable qualification views/certificates in the owned PlanStore.

Private inputs, derived prices and menu identities stay in the same database as
their owner's saved plans and are erased in the same transaction. A lost/corrupt
row is a miss. SQLite commits publish a complete view atomically; no partial
qualification view can escape after a process crash. No product graphs persist.
"""
import json
import sqlite3
from uuid import uuid4

from app.services.planner_context import canonical_bytes, content_digest

SCHEMA = """
CREATE TABLE IF NOT EXISTS planner_owned_artifacts (
    owner_actor_hash TEXT NOT NULL REFERENCES personal_private_state(owner_actor_hash) ON DELETE CASCADE ON UPDATE CASCADE,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    payload BLOB NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY(owner_actor_hash, kind, key)
);
"""
VERSION = "smako-owned-planner-artifact-v1"
MAX_ROW_BYTES = 8 * 1024 * 1024
MAX_BYTES = 64 * 1024 * 1024
MAX_ROWS = 4096


class OwnedPlannerArtifacts:
    def __init__(self, store, owner):
        store._validate_owner_actor_hash(owner)
        if owner is None:
            raise ValueError("Planner artifacts need an owner")
        self.store, self.owner = store, owner
        self.stats = {"hits": 0, "misses": 0, "writes": 0, "invalid": 0}
        # Capture the existing privacy record before admission. Its random ID
        # is an erasure epoch: a worker admitted before erasure/migration must
        # never recreate the old owner's derived data afterwards.
        with store._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT OR IGNORE INTO personal_private_state VALUES (?, ?, 0, ?)",
                (uuid4().hex, owner, json.dumps({"profile": None, "items": [],
                                               "reservations": {}, "events": {}})))
            self.private_id = connection.execute(
                "SELECT id FROM personal_private_state WHERE owner_actor_hash=?", (owner,)
            ).fetchone()[0]

    def load(self, kind, key):
        try:
            with self.store._connect() as connection:
                row = connection.execute(
                    "SELECT payload, sha256 FROM planner_owned_artifacts "
                    "WHERE owner_actor_hash=? AND kind=? AND key=? AND EXISTS "
                    "(SELECT 1 FROM personal_private_state WHERE owner_actor_hash=? AND id=?)",
                    (self.owner, kind, key, self.owner, self.private_id)).fetchone()
            if row:
                if len(row["payload"]) > MAX_ROW_BYTES:
                    raise ValueError("Artifact exceeds row budget")
                value = json.loads(row["payload"])
                if (value["version"] != VERSION or value["key"] != key
                        or content_digest(value) != row["sha256"]):
                    raise ValueError("Artifact signature mismatch")
                self.stats["hits"] += 1
                return value["data"]
        except (ValueError, KeyError, TypeError, RecursionError, sqlite3.Error):
            self.stats["invalid"] += 1
        self.stats["misses"] += 1
        return None

    def save(self, kind, key, data):
        envelope = {"version": VERSION, "key": key, "data": data}
        payload = canonical_bytes(envelope)
        if len(payload) > MAX_ROW_BYTES:
            return False
        try:
            with self.store._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute(
                    "SELECT 1 FROM personal_private_state WHERE owner_actor_hash=? AND id=?",
                    (self.owner, self.private_id)).fetchone() is None:
                    return False
                current = connection.execute(
                    "SELECT COUNT(*), COALESCE(SUM(length(payload)), 0) FROM planner_owned_artifacts"
                ).fetchone()
                prior = connection.execute(
                    "SELECT length(payload) FROM planner_owned_artifacts "
                    "WHERE owner_actor_hash=? AND kind=? AND key=?",
                    (self.owner, kind, key)).fetchone()
                # Refuse growth at capacity, preserving all durable rollback and
                # predecessor evidence. RAM eviction never deletes these rows.
                if ((current[0] >= MAX_ROWS and prior is None)
                        or current[1] - (prior[0] if prior else 0) + len(payload) > MAX_BYTES):
                    return False
                connection.execute(
                    "INSERT OR REPLACE INTO planner_owned_artifacts VALUES (?, ?, ?, ?, ?)",
                    (self.owner, kind, key, payload, content_digest(envelope)))
            self.stats["writes"] += 1
            return True
        except sqlite3.Error:
            return False

    def recent_menu_records(self, context=None, *, include_certificates=True):
        """Recover owned identities even after all derived artifacts are lost.

        Saved consumer revisions are authoritative delivery history, not cache.
        Read bounded rows under the captured privacy epoch; exact-context menus
        precede other recent identities. No old prices or approvals are reused.
        Saved-only reads bind menu views to delivery history without making a
        certificate invalidate itself when its own winner is written.
        """
        try:
            with self.store._connect() as connection:
                connection.execute("BEGIN")
                if connection.execute(
                    "SELECT 1 FROM personal_private_state WHERE owner_actor_hash=? AND id=?",
                    (self.owner, self.private_id)).fetchone() is None:
                    return []
                history = connection.execute(
                    "SELECT response_json FROM consumer_plan_revisions WHERE owner_actor_hash=? "
                    "AND length(response_json)<=? AND json_valid(response_json) "
                    "ORDER BY CASE WHEN json_extract(response_json, "
                    "'$.personal.checks.verified_reference.context')=? THEN 0 ELSE 1 END, "
                    "created_at DESC, revision DESC LIMIT 8",
                    (self.owner, MAX_ROW_BYTES, context)).fetchall()
                keys = connection.execute(
                    "SELECT key FROM planner_owned_artifacts WHERE owner_actor_hash=? "
                    "AND kind='menu_certificate' ORDER BY rowid DESC LIMIT 8", (self.owner,)).fetchall() if include_certificates else ()
            records = []
            for row in history:
                try:
                    personal = json.loads(row[0]).get("personal")
                    if not isinstance(personal, dict):
                        continue
                    slots = personal.get("slots")
                    if not isinstance(slots, list) or not 1 <= len(slots) <= 21:
                        continue
                    record = [{"slot": slot["id"], "recipe": content_digest(slot["recipe"]),
                               "recipe_name": slot["recipe"]["name"] if slot["recipe"] else None}
                              for slot in slots]
                    records.append((personal.get("checks", {}).get("verified_reference", {}).get("context"), record))
                except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
                    continue
            for row in keys:
                value = self.load("menu_certificate", row[0])
                if isinstance(value, dict) and isinstance(value.get("winner"), list):
                    records.append((value.get("context"), value["winner"]))
            records.sort(key=lambda row: row[0] != context)
            result, seen = [], set()
            for _, record in records:
                digest = content_digest(record)
                if digest not in seen:
                    result.append(record)
                    seen.add(digest)
                if len(result) == 8:
                    break
            return result
        except sqlite3.Error:
            return []
