"""Local membership credentials and revocable sessions in the existing private DB."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS member_accounts (
    owner TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    recovery_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS member_sessions (
    token_hash TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES member_accounts(owner) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_member_sessions_owner ON member_sessions(owner);
CREATE TABLE IF NOT EXISTS member_auth_attempts (
    key TEXT PRIMARY KEY,
    attempts INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
);
"""
COOKIE = "smako_member"
SESSION_SECONDS = 30 * 86400


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    derived = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**15,
                             r=8, p=3, maxmem=64 * 1024 * 1024).hex()
    return f"scrypt-v1${salt}${derived}"


def password_matches(password, encoded):
    return hmac.compare_digest(password_hash(password, encoded.split("$")[1]), encoded)


class AuthThrottled(Exception):
    pass


class AccountExists(Exception):
    pass


class MemberAccounts:
    def __init__(self, plans):
        self.plans = plans

    def throttle(self, identity, address):
        """Persist counters across workers/restarts; no raw addresses in storage."""
        now = int(time.time())
        blocked = False
        with self.plans._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM member_auth_attempts WHERE expires_at <= ?", (now,))
            for key, limit in (("identity:" + identity, 12), ("address:" + address, 60)):
                key = digest(key)
                db.execute("""INSERT INTO member_auth_attempts VALUES (?, 1, ?)
                    ON CONFLICT(key) DO UPDATE SET attempts=attempts+1""", (key, now + 900))
                row = db.execute("SELECT attempts FROM member_auth_attempts WHERE key=?",
                                 (key,)).fetchone()
                blocked |= row["attempts"] > limit
        if blocked:
            raise AuthThrottled

    def register(self, email, password):
        owner, recovery = secrets.token_hex(32), secrets.token_urlsafe(24)
        encoded = password_hash(password)
        try:
            with self.plans._connect() as db:
                db.execute("INSERT INTO member_accounts VALUES (?, ?, ?, ?)",
                           (owner, email, encoded, digest(recovery)))
        except sqlite3.IntegrityError as exc:
            raise AccountExists from exc
        return owner, recovery

    def authenticate(self, email, password):
        with self.plans._connect() as db:
            row = db.execute("SELECT * FROM member_accounts WHERE email=?", (email,)).fetchone()
        # Spend the same password work for unknown accounts.
        encoded = row["password_hash"] if row else "scrypt-v1$" + "00" * 16 + "$" + "00" * 64
        valid = password_matches(password, encoded)
        return (row["owner"], encoded) if row and valid else None

    def create_session(self, owner, *, expected_password_hash=None):
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.plans._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if expected_password_hash is not None:
                row = db.execute("SELECT password_hash FROM member_accounts WHERE owner=?",
                                 (owner,)).fetchone()
                if not row or not hmac.compare_digest(row["password_hash"], expected_password_hash):
                    return None
            db.execute("DELETE FROM member_sessions WHERE expires_at <= ?", (now,))
            db.execute("INSERT INTO member_sessions VALUES (?, ?, ?)",
                       (digest(token), owner, now + SESSION_SECONDS))
        return token

    def owner(self, token):
        if not token or len(token) > 128:
            return None
        with self.plans._connect() as db:
            row = db.execute("SELECT owner FROM member_sessions WHERE token_hash=? AND expires_at>?",
                             (digest(token), int(time.time()))).fetchone()
        return row["owner"] if row else None

    def logout(self, token):
        if token:
            with self.plans._connect() as db:
                db.execute("DELETE FROM member_sessions WHERE token_hash=?", (digest(token),))

    def recover(self, email, recovery, password):
        encoded = password_hash(password)
        replacement = secrets.token_urlsafe(24)
        with self.plans._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM member_accounts WHERE email=?", (email,)).fetchone()
            if not row or not hmac.compare_digest(row["recovery_hash"], digest(recovery)):
                return None
            db.execute("UPDATE member_accounts SET password_hash=?, recovery_hash=? WHERE owner=?",
                       (encoded, digest(replacement), row["owner"]))
            db.execute("DELETE FROM member_sessions WHERE owner=?", (row["owner"],))
        return replacement
