"""Verify and atomically restore one stopped beta deployment backup bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)

try:
    from .privacy_erasure_ledger import (
        SuppressionDirective,
        apply_deletion_ledger,
        export_deletion_ledger,
        ledger_digest,
        load_deletion_ledger,
        verify_deletion_ledger,
    )
except ImportError:  # Direct script execution inside the production image.
    from privacy_erasure_ledger import (  # type: ignore[no-redef]
        SuppressionDirective,
        apply_deletion_ledger,
        export_deletion_ledger,
        ledger_digest,
        load_deletion_ledger,
        verify_deletion_ledger,
    )

try:
    from .backup_sqlite import (
        _GROCERY_STATE_TABLE_GROUPS,
        _PLAN_STATE_TABLE_GROUPS,
        _SAFE_SCOPE_PART,
        _active_artifact_state,
        _chmod_private,
        _private_directory,
        configured_database_paths,
        database_state_inventory,
    )
except ImportError:  # Direct script execution inside the production image.
    from backup_sqlite import (  # type: ignore[no-redef]
        _GROCERY_STATE_TABLE_GROUPS,
        _PLAN_STATE_TABLE_GROUPS,
        _SAFE_SCOPE_PART,
        _active_artifact_state,
        _chmod_private,
        _private_directory,
        configured_database_paths,
        database_state_inventory,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(bundle: Path) -> dict[str, Any]:
    if bundle.name.startswith(".") or bundle.name.endswith(".tmp"):
        raise ValueError("temporary/incomplete backup bundle cannot be restored")
    manifest_path = bundle / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != ("grocery-beta-backup-v1"):
        raise ValueError("unsupported backup manifest")
    files = payload.get("files")
    if not isinstance(files, list):
        raise TypeError("backup manifest lacks files")
    listed: set[str] = set()
    for row in files:
        if not isinstance(row, dict) or not isinstance(row.get("path"), str):
            raise TypeError("invalid backup file entry")
        relative = Path(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("backup file escapes its bundle")
        source = bundle / relative
        if not source.is_file() or _sha256(source) != row.get("sha256"):
            raise ValueError(f"backup hash verification failed: {relative.as_posix()}")
        listed.add(relative.as_posix())
    _verify_active_artifact_pairs(
        bundle / "price_universes",
        listed_paths=listed,
        listed_root=bundle,
    )
    return payload


def _verify_active_artifact_pairs(
    universe_root: Path,
    *,
    listed_paths: set[str] | None = None,
    listed_root: Path | None = None,
) -> None:
    """Verify every backed-up active pointer resolves inside its bundle root."""

    if not universe_root.is_dir():
        raise FileNotFoundError("backup lacks price_universes directory")
    manifests = sorted(universe_root.glob("active/*.json")) + sorted(
        (universe_root / "external-provider-cache").glob("active/*.json")
    )
    if not manifests:
        raise FileNotFoundError("backup lacks an active PriceUniverse manifest")
    for manifest_path in manifests:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("active artifact manifest must be an object")
        artifact_value = payload.get("artifact_file")
        if not isinstance(artifact_value, str):
            raise TypeError("active artifact manifest lacks artifact_file")
        relative_artifact = Path(artifact_value)
        if relative_artifact.is_absolute() or ".." in relative_artifact.parts:
            raise ValueError("active artifact path escapes its root")
        artifact_path = manifest_path.parent.parent / relative_artifact
        if not artifact_path.is_file():
            raise FileNotFoundError("active artifact referenced by manifest is missing")
        expected = payload.get("artifact_sha256")
        if not isinstance(expected, str) or _sha256(artifact_path) != expected:
            raise ValueError("active artifact hash does not match its manifest")
        expected_bytes = payload.get("artifact_bytes")
        if isinstance(expected_bytes, int) and artifact_path.stat().st_size != expected_bytes:
            raise ValueError("active artifact size does not match its manifest")
        if listed_paths is not None:
            root = listed_root or universe_root
            manifest_relative = manifest_path.relative_to(root).as_posix()
            artifact_relative = artifact_path.relative_to(root).as_posix()
            if manifest_relative not in listed_paths or artifact_relative not in listed_paths:
                raise ValueError("active PriceUniverse pair is not fully declared in bundle")


def _expected_file_hash(manifest: dict[str, Any], relative: str) -> str:
    for row in manifest["files"]:
        if row.get("path") == relative and isinstance(row.get("sha256"), str):
            return str(row["sha256"])
    raise ValueError(f"backup manifest lacks required file: {relative}")


def verify_restored_state(
    bundle: Path,
    *,
    verify_databases: bool = True,
    verify_universe: bool = True,
    deletion_entries: tuple[SuppressionDirective, ...] | None = None,
) -> dict[str, Any]:
    """Verify restored targets against the bundle without advancing any clocks."""

    bundle = bundle.resolve(strict=True)
    manifest = _load_manifest(bundle)
    checks: dict[str, Any] = {}
    if verify_databases:
        targets = configured_database_paths()
        database_specs = (
            (
                "grocery_database",
                "grocery/grocery_data.sqlite",
                targets["grocery/grocery_data.sqlite"],
                _GROCERY_STATE_TABLE_GROUPS,
            ),
            (
                "plan_database",
                "plans/consumer_plans.sqlite3",
                targets["plans/consumer_plans.sqlite3"],
                _PLAN_STATE_TABLE_GROUPS,
            ),
        )
        expected_state = manifest.get("state_integrity")
        for name, relative, target, groups in database_specs:
            actual_inventory = database_state_inventory(target, groups)
            if deletion_entries is None:
                if _sha256(target) != _expected_file_hash(manifest, relative):
                    raise ValueError(f"restored file hash differs from bundle: {relative}")
                if isinstance(expected_state, dict) and name in expected_state:
                    if actual_inventory != expected_state[name]:
                        raise ValueError(f"restored semantic state differs: {name}")
                    mode = "semantic_and_file_hash"
                else:
                    mode = "legacy_bundle_file_hash"
            else:
                # The staged copy was already matched byte-for-byte against the
                # bundle before replay. Only the suppression operations are
                # allowed to make the activated database differ afterward.
                if name == "grocery_database" and isinstance(expected_state, dict):
                    expected_database = expected_state.get(name)
                    expected_source = (
                        expected_database.get("source_freshness_and_lkg")
                        if isinstance(expected_database, dict)
                        else None
                    )
                    if (
                        expected_source is not None
                        and actual_inventory.get("source_freshness_and_lkg") != expected_source
                    ):
                        raise ValueError("deletion replay changed source freshness or LKG state")
                mode = "bundle_hash_then_deletion_reapplication"
            checks[name] = {"status": "verified", "mode": mode}

        if deletion_entries is not None:
            privacy = verify_deletion_ledger(
                targets["grocery/grocery_data.sqlite"],
                targets["plans/consumer_plans.sqlite3"],
                deletion_entries,
            )
            checks["privacy_deletion_ledger"] = privacy

    if verify_universe:
        universe_root = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).resolve()
        _verify_active_artifact_pairs(universe_root)
        city = " ".join(os.getenv("PRICE_UNIVERSE_CITY", "Lund").casefold().split())
        safe_city = _SAFE_SCOPE_PART.sub("-", city).strip("-")
        if not safe_city:
            raise ValueError("PRICE_UNIVERSE_CITY cannot form a safe restore scope")
        relative_manifest = Path(f"active/city-{safe_city}.json")
        actual_state = {
            "price_universe": _active_artifact_state(
                universe_root,
                relative_manifest,
            ),
            "external_provider_lkg": _active_artifact_state(
                universe_root / "external-provider-cache",
                relative_manifest,
            ),
        }
        expected_state = manifest.get("state_integrity")
        if isinstance(expected_state, dict) and 'municipal_price_universes' in expected_state:
            for relative, expected in expected_state['municipal_price_universes'].items():
                path = Path(relative)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('invalid municipal manifest path')
                if _active_artifact_state(universe_root, path) != expected:
                    raise ValueError('restored municipal price universe differs')
        mode = "legacy_bundle_file_hash"
        if isinstance(expected_state, dict):
            for key, state in actual_state.items():
                if key in expected_state and state != expected_state[key]:
                    raise ValueError(f"restored semantic state differs: {key}")
            mode = "semantic_and_file_hash"
        checks["price_universe"] = {"status": "verified", "mode": mode}
    if verify_databases:
        from deploy.scripts.municipal_backup import restored_target
        for row in manifest['files']:
            if row['path'].startswith('runtime/') and _sha256(restored_target(row['path'])) != row['sha256']:
                raise ValueError('restored municipal recovery state differs')
    return {
        "status": "verified",
        "bundle_schema": manifest["schema_version"],
        "price_universe_id": manifest.get("price_universe_id"),
        "checks": checks,
    }


def _restore_locked(
    bundle: Path,
    *,
    confirm: bool,
    restore_databases: bool = True,
    restore_universe: bool = True,
    deletion_ledger: Path | None = None,
) -> dict[str, Any]:
    if not confirm:
        raise ValueError("restore requires --confirm after app and scheduler are stopped")
    bundle = bundle.resolve(strict=True)
    manifest = _load_manifest(bundle)
    targets = configured_database_paths() if restore_databases else {}
    from deploy.scripts.municipal_backup import restored_target
    runtime_targets = {row['path']: restored_target(row['path']) for row in manifest['files']
                       if row['path'].startswith('runtime/')} if restore_databases else {}
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    staged: list[tuple[Path, Path]] = []
    captured_ledger: Path | None = None
    deletion_entries: tuple[SuppressionDirective, ...] | None = None
    deletion_ledger_source: str | None = None
    try:
        if restore_databases:
            if deletion_ledger is None:
                current_grocery = targets["grocery/grocery_data.sqlite"]
                captured_ledger = current_grocery.with_name(
                    f".privacy-erasure-ledger.{uuid4().hex}.restore.json"
                )
                # This independently flushed/read-back file survives the old
                # database copy throughout staging and replay. Failure occurs
                # before any configured target is replaced.
                export_deletion_ledger(current_grocery, captured_ledger)
                deletion_entries = load_deletion_ledger(captured_ledger)
                deletion_ledger_source = "captured_current_database"
            else:
                deletion_entries = load_deletion_ledger(deletion_ledger)
                deletion_ledger_source = "operator_export"

        for relative, target in targets.items():
            source = bundle / relative
            if not source.is_file():
                raise FileNotFoundError(f"required database is absent: {relative}")
            connection = sqlite3.connect(source)
            try:
                result = connection.execute("PRAGMA integrity_check").fetchone()
                if result is None or result[0] != "ok":
                    raise ValueError(f"backup database failed integrity check: {relative}")
                if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                    raise ValueError(f"backup database failed foreign-key check: {relative}")
            finally:
                connection.close()
            _private_directory(target.parent)
            temporary = target.with_name(f".{target.name}.{uuid4().hex}.restore")
            shutil.copy2(source, temporary)
            _chmod_private(temporary, directory=False)
            if _sha256(temporary) != _expected_file_hash(manifest, relative):
                raise ValueError(f"staged file hash differs from bundle: {relative}")
            state_name = (
                "grocery_database" if relative == "grocery/grocery_data.sqlite" else "plan_database"
            )
            groups = (
                _GROCERY_STATE_TABLE_GROUPS
                if state_name == "grocery_database"
                else _PLAN_STATE_TABLE_GROUPS
            )
            expected_state = manifest.get("state_integrity")
            if (
                isinstance(expected_state, dict)
                and state_name in expected_state
                and database_state_inventory(temporary, groups) != expected_state[state_name]
            ):
                raise ValueError(f"staged semantic state differs from bundle: {state_name}")
            staged.append((temporary, target))

        if restore_databases:
            assert deletion_entries is not None
            staged_by_target = {target: temporary for temporary, target in staged}
            apply_deletion_ledger(
                staged_by_target[targets["grocery/grocery_data.sqlite"]],
                staged_by_target[targets["plans/consumer_plans.sqlite3"]],
                deletion_entries,
            )
            expected_state = manifest.get("state_integrity")
            expected_grocery = (
                expected_state.get("grocery_database") if isinstance(expected_state, dict) else None
            )
            expected_source = (
                expected_grocery.get("source_freshness_and_lkg")
                if isinstance(expected_grocery, dict)
                else None
            )
            if expected_source is not None:
                actual_source = database_state_inventory(
                    staged_by_target[targets["grocery/grocery_data.sqlite"]],
                    {
                        "source_freshness_and_lkg": _GROCERY_STATE_TABLE_GROUPS[
                            "source_freshness_and_lkg"
                        ]
                    },
                )["source_freshness_and_lkg"]
                if actual_source != expected_source:
                    raise ValueError("deletion replay changed source freshness or LKG state")

        for temporary, target in staged:
            if target.exists():
                rollback = target.with_name(f"{target.name}.before-restore-{timestamp}")
                shutil.copy2(target, rollback)
                _chmod_private(rollback, directory=False)
            os.replace(temporary, target)
            _chmod_private(target, directory=False)
            target.with_name(f"{target.name}-wal").unlink(missing_ok=True)
            target.with_name(f"{target.name}-shm").unlink(missing_ok=True)

        if restore_databases:
            for relative, target in sorted(runtime_targets.items()):
                _private_directory(target.parent)
                temporary = target.with_name(f'.{target.name}.{uuid4().hex}.restore')
                shutil.copy2(bundle / relative, temporary)
                _chmod_private(temporary, directory=False)
                if target.exists():
                    rollback = target.with_name(f'{target.name}.before-restore-{timestamp}')
                    shutil.copy2(target, rollback)
                    _chmod_private(rollback, directory=False)
                os.replace(temporary, target)
        universe_source = bundle / "price_universes"
        if restore_universe and universe_source.is_dir():
            universe_target = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).resolve()
            # Immutable content-addressed blobs are copied first. Active
            # manifests are swapped last, so interruption retains the old LKG.
            universe_files = sorted(
                (path for path in universe_source.rglob("*") if path.is_file()),
                key=lambda path: ("/active/" in path.as_posix(), path.as_posix()),
            )
            for source in universe_files:
                relative = source.relative_to(universe_source)
                target = universe_target / relative
                _private_directory(target.parent)
                temporary = target.with_name(f".{target.name}.{uuid4().hex}.restore")
                shutil.copy2(source, temporary)
                _chmod_private(temporary, directory=False)
                if "active" in relative.parts and target.exists():
                    rollback = target.with_name(f"{target.name}.before-restore-{timestamp}")
                    shutil.copy2(target, rollback)
                    _chmod_private(rollback, directory=False)
                os.replace(temporary, target)
                _chmod_private(target, directory=False)
        verification = verify_restored_state(
            bundle,
            verify_databases=restore_databases,
            verify_universe=restore_universe,
            deletion_entries=deletion_entries,
        )
        if deletion_entries is not None:
            verification["deletion_ledger"] = {
                "status": "verified_and_applied",
                "source": deletion_ledger_source,
                "entries": len(deletion_entries),
                "entries_sha256": ledger_digest(deletion_entries),
            }
        return verification
    finally:
        for temporary, _target in staged:
            temporary.unlink(missing_ok=True)
        if captured_ledger is not None:
            captured_ledger.unlink(missing_ok=True)


def restore(
    bundle: Path,
    *,
    confirm: bool,
    restore_databases: bool = True,
    restore_universe: bool = True,
    deletion_ledger: Path | None = None,
) -> dict[str, Any]:
    if not confirm:
        raise ValueError("restore requires --confirm after app and scheduler are stopped")
    databases = configured_database_paths()
    universe_root = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).resolve()
    lock = RefreshRunLock(
        production_refresh_lock_path(
            databases["grocery/grocery_data.sqlite"],
            universe_root,
            allow_missing_database=True,
        )
    )
    lock.acquire()
    try:
        return _restore_locked(
            bundle,
            confirm=True,
            restore_databases=restore_databases,
            restore_universe=restore_universe,
            deletion_ledger=deletion_ledger,
        )
    finally:
        lock.release()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--confirm", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--only-databases", action="store_true")
    selection.add_argument("--only-price-universe", action="store_true")
    parser.add_argument(
        "--deletion-ledger",
        type=Path,
        help=(
            "validated independent ledger export; required for database restore "
            "when the current database is unavailable"
        ),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    verification = restore(
        args.bundle,
        confirm=args.confirm,
        restore_databases=not args.only_price_universe,
        restore_universe=not args.only_databases,
        deletion_ledger=args.deletion_ledger,
    )
    print(
        json.dumps(
            {
                "status": "restored",
                "bundle": args.bundle.name,
                "verification": verification,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
