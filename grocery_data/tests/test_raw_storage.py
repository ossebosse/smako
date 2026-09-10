import json
from pathlib import Path

import pytest

from grocery_data.app.domain import Chain, RawBatch, RawFetch
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore


def test_raw_is_saved_before_parsing_and_can_be_replayed(tmp_path: Path) -> None:
    raw = RawFetch(
        chain=Chain.WILLYS,
        store_external_id="2354",
        kind="catalog_page",
        method="GET",
        url="https://public.example/catalog",
        query={"page": "0"},
        http_status=200,
        content_type="application/json",
        payload=b'{"results":[{"code":"1","priceValue":19.9}]}',
        connector_version="willys-v1",
    )
    store = FilesystemRawSnapshotStore(tmp_path)
    records = store.save_batch(RawBatch(chain=Chain.WILLYS, documents=(raw,)), snapshot_id="s1")
    assert len(records) == 1
    assert records[0].payload_hash == raw.payload_hash
    assert json.loads(store.load(records[0]))["results"][0]["code"] == "1"


def test_sensitive_json_fields_are_redacted(tmp_path: Path) -> None:
    raw = RawFetch(
        chain=Chain.WILLYS,
        kind="config",
        method="GET",
        url="https://public.example/config",
        http_status=200,
        content_type="application/json",
        payload=(
            b'{"token":"do-not-save","nextPageToken":"public-pagination",'
            b'"pageToken":"page-2","paginationToken":"page-3",'
            b'"accessToken":"access-secret","csrfToken":"csrf-secret",'
            b'"sessionId":"session-secret","apiKey":"api-secret",'
            b'"idToken":"id-secret","refreshToken":"refresh-secret",'
            b'"clientSecret":"client-secret","clientId":"client-id-secret",'
            b'"subscriptionKey":"subscription-secret",'
            b'"Ocp-Apim-Subscription-Key":"apim-secret",'
            b'"credentials":"credentials-secret","product":{"name":"Pasta"}}'
        ),
        connector_version="willys-v1",
    )
    store = FilesystemRawSnapshotStore(tmp_path)
    record = store.save_batch(RawBatch(chain=Chain.WILLYS, documents=(raw,)), snapshot_id="s1")[0]
    payload = json.loads(store.load(record))
    assert payload["token"] == "[REDACTED]"
    assert payload["nextPageToken"] == "public-pagination"
    assert payload["pageToken"] == "page-2"
    assert payload["paginationToken"] == "page-3"
    for field in (
        "accessToken",
        "csrfToken",
        "sessionId",
        "apiKey",
        "idToken",
        "refreshToken",
        "clientSecret",
        "clientId",
        "subscriptionKey",
        "Ocp-Apim-Subscription-Key",
        "credentials",
    ):
        assert payload[field] == "[REDACTED]"
    assert payload["product"]["name"] == "Pasta"
    assert "do-not-save" not in store.load(record).decode()


def test_replay_rejects_tampered_raw_payload(tmp_path: Path) -> None:
    raw = RawFetch(
        chain=Chain.WILLYS,
        kind="catalog_page",
        method="GET",
        url="https://public.example/catalog",
        http_status=200,
        content_type="application/json",
        payload=b'{"results":[]}',
        connector_version="willys-v1",
    )
    store = FilesystemRawSnapshotStore(tmp_path)
    record = store.save_batch(RawBatch(chain=Chain.WILLYS, documents=(raw,)), snapshot_id="s1")[0]
    record.resolve(tmp_path.resolve()).write_bytes(b'{"results":["tampered"]}')

    with pytest.raises(ValueError, match="integrity check failed"):
        store.load(record)
