from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from grocery_data.app.services import closed_provider_cache_store as cache_store_module
from grocery_data.app.services.closed_provider_cache_store import (
    ClosedProviderCacheArtifactStore,
    ClosedProviderCacheValidationDecision,
    ClosedProviderCacheValidationRejected,
)
from grocery_data.app.services.durable_files import (
    InsufficientStorageError,
    StoragePreflight,
)
from grocery_data.app.services.freshness import FreshnessPolicy, FreshnessState

NOW = datetime(2026, 8, 29, 12, tzinfo=UTC)
POLICY = FreshnessPolicy(warning_age_hours=36, stale_age_hours=48)


def _write_cache(
    path: Path,
    *,
    captured_at: datetime | None = None,
    product_id: str = "rice",
    extra_product_fields: dict[str, object] | None = None,
) -> bytes:
    product = {
        "product_id": product_id,
        "source_provider": "primat",
        "source_provenance": {"source_snapshot_id": "primat-products-1"},
    }
    product.update(extra_product_fields or {})
    payload = {
        "schema_version": "lund-frozen-external-v1",
        "postal_code": "22350",
        "captured_at": (captured_at or NOW - timedelta(hours=2)).isoformat(),
        "stores": [
            {
                "store_id": "primat:ica:1",
                "source_provenance": {"source_snapshot_id": "primat-stores-1"},
            }
        ],
        "products": [product],
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    path.write_bytes(encoded)
    return encoded


def test_activation_is_content_addressed_and_resolves_verified_active_cache(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate.json"
    payload = _write_cache(candidate)
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")

    first = store.activate(
        candidate,
        city=" Lund ",
        policy=POLICY,
        activated_at=NOW,
    )
    second = store.activate(
        candidate,
        city="Lund",
        policy=POLICY,
        activated_at=NOW + timedelta(minutes=1),
    )

    digest = hashlib.sha256(payload).hexdigest()
    assert first.artifact_file == f"artifacts/{digest}.json"
    assert first.artifact_sha256 == digest
    assert first.artifact_bytes == len(payload)
    assert first.snapshot_ids == ("primat-products-1", "primat-stores-1")
    assert second.artifact_file == first.artifact_file
    assert len(tuple((store.root / "artifacts").glob("*.json"))) == 1

    resolved = store.resolve_active(
        "lund",
        policy=POLICY,
        now=NOW + timedelta(minutes=2),
    )

    assert resolved is not None
    artifact, status, active = resolved
    assert artifact.read_bytes() == payload
    assert active == second
    assert status.freshness is FreshnessState.FRESH
    assert status.usable is True
    assert status.stores == 1
    assert status.products == 1


def test_future_candidate_is_rejected_and_previous_manifest_remains_byte_identical(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    stale = tmp_path / "stale.json"
    _write_cache(current, product_id="rice")
    _write_cache(
        stale,
        captured_at=NOW + timedelta(hours=49),
        product_id="pasta",
    )
    active = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")

    with pytest.raises(ValueError, match="candidate is stale"):
        store.activate(stale, city="Lund", policy=POLICY, activated_at=NOW)

    assert before is not None
    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") == active
    assert len(tuple((store.root / "artifacts").glob("*.json"))) == 1


def test_credential_bearing_candidate_is_rejected_without_changing_lkg(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    credential_bearing = tmp_path / "credential-bearing.json"
    _write_cache(current)
    _write_cache(
        credential_bearing,
        product_id="pasta",
        extra_product_fields={"authorization": "Bearer must-never-be-stored"},
    )
    store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")

    with pytest.raises(ValueError, match="forbidden transport material") as error:
        store.activate(
            credential_bearing,
            city="Lund",
            policy=POLICY,
            activated_at=NOW,
        )

    assert "must-never-be-stored" not in str(error.value)
    assert store.active_manifest_bytes("Lund") == before
    artifacts = tuple((store.root / "artifacts").glob("*.json"))
    assert len(artifacts) == 1
    assert b"must-never-be-stored" not in artifacts[0].read_bytes()


def test_tampered_active_artifact_is_detected_by_hash_verification(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    candidate = tmp_path / "candidate.json"
    _write_cache(candidate, product_id="rice")
    manifest = store.activate(candidate, city="Lund", policy=POLICY, activated_at=NOW)
    artifact = store.root / Path(*manifest.artifact_file.split("/"))
    original = artifact.read_bytes()
    tampered = original.replace(b'"rice"', b'"corn"')
    assert len(tampered) == len(original)
    assert tampered != original
    artifact.write_bytes(tampered)

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        store.read_active("Lund")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        store.resolve_active("Lund", policy=POLICY, now=NOW)


@pytest.mark.parametrize("manifest_payload", [b"not-json", b"{}"])
def test_invalid_active_manifest_is_rejected(
    tmp_path: Path,
    manifest_payload: bytes,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    path = store.active_manifest_path("Lund")
    path.parent.mkdir(parents=True)
    path.write_bytes(manifest_payload)

    with pytest.raises(ValueError, match="manifest is invalid"):
        store.read_active("Lund")


def test_active_manifest_for_wrong_city_is_rejected(tmp_path: Path) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    candidate = tmp_path / "candidate.json"
    _write_cache(candidate)
    store.activate(candidate, city="Lund", policy=POLICY, activated_at=NOW)
    manifest_path = store.active_manifest_path("Lund")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["city"] = "Malmö"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="wrong city"):
        store.read_active("Lund")


def test_failed_atomic_manifest_swap_preserves_resolvable_lkg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    replacement = tmp_path / "replacement.json"
    _write_cache(current, product_id="rice")
    _write_cache(replacement, product_id="pasta")
    active = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")
    real_atomic_write = cache_store_module._atomic_write

    def fail_active_manifest_write(path: Path, payload: bytes) -> None:
        if path == store.active_manifest_path("Lund"):
            raise OSError("simulated atomic manifest swap failure")
        real_atomic_write(path, payload)

    monkeypatch.setattr(cache_store_module, "_atomic_write", fail_active_manifest_write)

    with pytest.raises(OSError, match="simulated atomic manifest swap failure"):
        store.activate(
            replacement,
            city="Lund",
            policy=POLICY,
            activated_at=NOW + timedelta(minutes=1),
        )

    assert before is not None
    assert store.active_manifest_bytes("Lund") == before
    resolved = store.resolve_active(
        "Lund",
        policy=POLICY,
        now=NOW + timedelta(minutes=2),
    )
    assert resolved is not None
    _, status, manifest = resolved
    assert manifest == active
    assert status.usable is True


def test_provider_cache_enospc_preflight_preserves_resolvable_lkg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    replacement = tmp_path / "replacement.json"
    _write_cache(current, product_id="rice")
    _write_cache(replacement, product_id="pasta")
    active = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")

    def no_space(*_args: object, **_kwargs: object) -> StoragePreflight:
        raise InsufficientStorageError(StoragePreflight(10, 20, 64))

    monkeypatch.setattr(cache_store_module, "require_free_space", no_space)

    with pytest.raises(InsufficientStorageError):
        store.activate(
            replacement,
            city="Lund",
            policy=POLICY,
            activated_at=NOW + timedelta(minutes=1),
        )

    assert store.active_manifest_bytes("Lund") == before
    resolved = store.resolve_active(
        "Lund",
        policy=POLICY,
        now=NOW + timedelta(minutes=2),
    )
    assert resolved is not None
    assert resolved[2] == active
    assert not list((store.root / "artifacts").glob(".*.tmp"))


def test_staging_does_not_activate_until_db_identity_validator_accepts(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    replacement = tmp_path / "replacement.json"
    _write_cache(current, product_id="rice")
    _write_cache(replacement, product_id="pasta")
    old = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")

    staged = store.stage(
        replacement,
        city="Lund",
        policy=POLICY,
        evaluated_at=NOW + timedelta(minutes=1),
    )

    assert before is not None
    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") == old
    validation_calls: list[Path] = []

    def validate_exact_db_identity(
        path: Path,
    ) -> ClosedProviderCacheValidationDecision[dict[str, object]]:
        assert store.active_manifest_bytes("Lund") == before
        assert b'"pasta"' in path.read_bytes()
        validation_calls.append(path)
        return ClosedProviderCacheValidationDecision(
            accepted=True,
            value={"status": "activated", "activated": 1, "rejected": 0},
        )

    manifest, validation = store.activate_staged(
        staged,
        policy=POLICY,
        validator=validate_exact_db_identity,
        activated_at=NOW + timedelta(minutes=2),
    )

    assert len(validation_calls) == 1
    assert validation == {"status": "activated", "activated": 1, "rejected": 0}
    assert manifest.artifact_file == staged.artifact_file
    assert store.read_active("Lund") == manifest
    assert store.active_manifest_bytes("Lund") != before


def test_db_identity_rejection_leaves_previous_lkg_active(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    rejected = tmp_path / "rejected.json"
    _write_cache(current, product_id="rice")
    _write_cache(rejected, product_id="pasta")
    old = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")

    def reject_ambiguous_identity(
        _path: Path,
    ) -> ClosedProviderCacheValidationDecision[dict[str, object]]:
        return ClosedProviderCacheValidationDecision(
            accepted=False,
            value={"status": "rejected", "activated": 0, "rejected": 1},
            reason_code="verified_identity_ambiguous",
        )

    with pytest.raises(ClosedProviderCacheValidationRejected) as error:
        store.activate_validated(
            rejected,
            city="Lund",
            policy=POLICY,
            validator=reject_ambiguous_identity,
            activated_at=NOW + timedelta(minutes=1),
        )

    assert error.value.reason_code == "verified_identity_ambiguous"
    assert before is not None
    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") == old


def test_active_manifest_can_be_rolled_back_after_later_commit_failure(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    replacement = tmp_path / "replacement.json"
    _write_cache(current, product_id="rice")
    _write_cache(replacement, product_id="pasta")
    old = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")
    assert before is not None

    store.activate(
        replacement,
        city="Lund",
        policy=POLICY,
        activated_at=NOW + timedelta(minutes=1),
    )
    assert store.read_active("Lund") != old

    store.restore_active_manifest("Lund", before)

    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") == old


def test_active_manifest_rollback_removes_first_candidate_when_no_lkg_existed(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    candidate = tmp_path / "candidate.json"
    _write_cache(candidate, product_id="rice")
    assert store.active_manifest_bytes("Lund") is None

    store.activate(candidate, city="Lund", policy=POLICY, activated_at=NOW)
    store.restore_active_manifest("Lund", None)

    assert store.read_active("Lund") is None


def test_truthy_rejected_report_cannot_be_mistaken_for_acceptance(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    rejected = tmp_path / "rejected.json"
    _write_cache(current, product_id="rice")
    _write_cache(rejected, product_id="pasta")
    old = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")

    def unsafe_validator(_path: Path) -> object:
        return {"status": "rejected", "activated": 0, "rejected": 1}

    with pytest.raises(TypeError, match="must return an explicit decision"):
        store.activate_validated(  # type: ignore[arg-type]
            rejected,
            city="Lund",
            policy=POLICY,
            validator=unsafe_validator,
            activated_at=NOW + timedelta(minutes=1),
        )

    assert before is not None
    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") == old


def test_staged_artifact_is_reverified_after_identity_validation(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    replacement = tmp_path / "replacement.json"
    _write_cache(current, product_id="rice")
    _write_cache(replacement, product_id="pasta")
    old = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")
    staged = store.stage(
        replacement,
        city="Lund",
        policy=POLICY,
        evaluated_at=NOW,
    )

    def mutate_after_validation(
        path: Path,
    ) -> ClosedProviderCacheValidationDecision[str]:
        payload = path.read_bytes()
        mutated = payload.replace(b'"pasta"', b'"beans"')
        assert len(mutated) == len(payload)
        path.write_bytes(mutated)
        return ClosedProviderCacheValidationDecision(
            accepted=True,
            value="accepted-before-mutation",
        )

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        store.activate_staged(
            staged,
            policy=POLICY,
            validator=mutate_after_validation,
            activated_at=NOW + timedelta(minutes=1),
        )

    assert before is not None
    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") == old


def test_staged_candidate_rejects_future_observation_before_identity_validation(
    tmp_path: Path,
) -> None:
    store = ClosedProviderCacheArtifactStore(tmp_path / "managed")
    current = tmp_path / "current.json"
    replacement = tmp_path / "replacement.json"
    _write_cache(current, captured_at=NOW, product_id="rice")
    _write_cache(replacement, captured_at=NOW, product_id="pasta")
    old = store.activate(current, city="Lund", policy=POLICY, activated_at=NOW)
    before = store.active_manifest_bytes("Lund")
    staged = store.stage(
        replacement,
        city="Lund",
        policy=POLICY,
        evaluated_at=NOW,
    )
    validator_called = False

    def validator(_path: Path) -> ClosedProviderCacheValidationDecision[None]:
        nonlocal validator_called
        validator_called = True
        return ClosedProviderCacheValidationDecision(accepted=True, value=None)

    with pytest.raises(ValueError, match="candidate is stale"):
        store.activate_staged(
            staged,
            policy=POLICY,
            validator=validator,
            activated_at=NOW - timedelta(hours=2),
        )

    assert validator_called is False
    assert before is not None
    assert store.active_manifest_bytes("Lund") == before
    assert store.read_active("Lund") == old
