"""Salted browser-admin passwords, separate from the operational API token."""

import hashlib
import hmac
import re
import secrets

_ITERATIONS = 600_000
_FORMAT = re.compile(r"pbkdf2_sha256:600000:[0-9a-f]{32}:[0-9a-f]{64}")


def valid_password_hash(value: str) -> bool:
    return _FORMAT.fullmatch(value) is not None


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256:{_ITERATIONS}:{salt.hex()}:{digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    if not valid_password_hash(encoded) or len(password) > 1024:
        return False
    _, _, salt, expected = encoded.split(":")
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS)
    return hmac.compare_digest(actual, bytes.fromhex(expected))
