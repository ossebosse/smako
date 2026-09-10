from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from grocery_data.app.domain import RawBatch, RawFetch, StoredRawDocument

_SENSITIVE_KEYS = {
    "access-token",
    "api-key",
    "authorization",
    "cookie",
    "csrf",
    "csrf-token",
    "credential",
    "credentials",
    "id-token",
    "password",
    "refresh-token",
    "secret",
    "session",
    "session-id",
    "token",
    "x-api-key",
}
_SENSITIVE_COMPACT_KEYS = {
    "accesstoken",
    "apikey",
    "authkey",
    "authtoken",
    "bearertoken",
    "clientsecret",
    "clientid",
    "clienttoken",
    "csrftoken",
    "idtoken",
    "ocpapimsubscriptionkey",
    "privatekey",
    "refreshtoken",
    "secretkey",
    "sessionid",
    "sessiontoken",
    "subscriptionkey",
}
_PUBLIC_PAGINATION_KEYS = {
    "nextpagetoken",
    "pagetoken",
    "paginationtoken",
}


def _is_sensitive(key: str) -> bool:
    normalized = key.casefold().replace("_", "-")
    compact = "".join(character for character in normalized if character.isalnum())
    if compact in _PUBLIC_PAGINATION_KEYS:
        return False
    return normalized in _SENSITIVE_KEYS or compact in _SENSITIVE_COMPACT_KEYS


def sanitize_json_payload(value: object) -> object:
    """Remove credential/session-shaped fields while preserving source facts."""

    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_sensitive(str(key)) else sanitize_json_payload(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [sanitize_json_payload(child) for child in value]
    return value


class FilesystemRawSnapshotStore:
    """Write immutable response bodies before parsers consume them."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_payload(self, document: RawFetch) -> bytes:
        content_type = (document.content_type or "").casefold()
        if "json" not in content_type:
            return document.payload
        try:
            parsed = document.json_payload()
        except (TypeError, ValueError):
            return document.payload
        sanitized = sanitize_json_payload(parsed)
        return json.dumps(sanitized, ensure_ascii=False, separators=(",", ":")).encode()

    def save_batch(
        self,
        batch: RawBatch,
        *,
        snapshot_id: str,
        schema_fingerprints: Mapping[str, str] | None = None,
    ) -> list[StoredRawDocument]:
        records: list[StoredRawDocument] = []
        for index, document in enumerate(batch.documents):
            suffix = ".json" if "json" in (document.content_type or "").casefold() else ".bin"
            store = document.store_external_id or "chain"
            timestamp = document.fetched_at.strftime("%Y%m%dT%H%M%S%fZ")
            document_id = uuid4().hex
            filename = f"{timestamp}_{index:04d}_{document.kind}_{document_id[:8]}{suffix}"
            relative = Path(batch.chain.value) / store / snapshot_id / filename
            target = (self.root / relative).resolve()
            if self.root not in target.parents:
                raise ValueError("raw snapshot target escapes configured root")
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation protects replay evidence from accidental overwrite.
            saved_payload = self._safe_payload(document)
            with target.open("xb") as handle:
                handle.write(saved_payload)
            records.append(
                StoredRawDocument(
                    snapshot_id=snapshot_id,
                    document_id=document_id,
                    chain=document.chain,
                    store_external_id=document.store_external_id,
                    kind=document.kind,
                    method=document.method,
                    url=document.url,
                    query=document.query,
                    relative_path=relative.as_posix(),
                    payload_hash=sha256(saved_payload).hexdigest(),
                    fetched_at=document.fetched_at,
                    http_status=document.http_status,
                    content_type=document.content_type,
                    connector_version=document.connector_version,
                    page_number=document.page_number,
                    schema_fingerprint=(schema_fingerprints or {}).get(document.payload_hash),
                )
            )
        return records

    def load(self, record: StoredRawDocument) -> bytes:
        payload = record.resolve(self.root).read_bytes()
        actual_hash = sha256(payload).hexdigest()
        if actual_hash != record.payload_hash:
            raise ValueError(
                f"raw payload integrity check failed for document {record.document_id}"
            )
        return payload
