"""Seed an empty deployment runtime from existing verified local state."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

try:
    from .backup_sqlite import (
        _backup_database,
        _chmod_private,
        _copy_active_artifact,
        _private_directory,
        _secure_tree,
    )
except ImportError:  # Direct script execution.
    from backup_sqlite import (  # type: ignore[no-redef]
        _backup_database,
        _chmod_private,
        _copy_active_artifact,
        _private_directory,
        _secure_tree,
    )


def seed_runtime(
    *,
    runtime_root: Path,
    grocery_database: Path,
    plan_database: Path,
    universe_root: Path,
    raw_snapshot_root: Path | None = None,
    city_slug: str = "lund",
) -> dict[str, object]:
    runtime_root = runtime_root.resolve()
    destinations = {
        "grocery": runtime_root / "grocery/grocery_data.sqlite",
        "plans": runtime_root / "plans/consumer_plans.sqlite3",
    }
    for destination in destinations.values():
        if destination.exists():
            raise FileExistsError(f"refusing to overwrite seeded file: {destination.name}")
    active_destination = runtime_root / (
        f"price_universes/active/city-{city_slug}.json"
    )
    if active_destination.exists():
        raise FileExistsError("refusing to overwrite an active PriceUniverse manifest")

    for directory in (
        "grocery",
        "plans",
        "price_universes",
        "raw_snapshots",
        "reports",
        "backups",
    ):
        _private_directory(runtime_root / directory)
    _chmod_private(runtime_root, directory=True)

    _backup_database(grocery_database.resolve(strict=True), destinations["grocery"])
    _backup_database(plan_database.resolve(strict=True), destinations["plans"])
    universe_root = universe_root.resolve(strict=True)
    manifest = Path(f"active/city-{city_slug}.json")
    copied = _copy_active_artifact(
        source_root=universe_root,
        relative_manifest=manifest,
        destination_root=runtime_root / "price_universes",
        bundle_prefix=Path("price_universes"),
    )
    if not copied:
        raise FileNotFoundError("verified active PriceUniverse manifest is missing")
    copied.extend(
        _copy_active_artifact(
            source_root=universe_root / "external-provider-cache",
            relative_manifest=manifest,
            destination_root=(
                runtime_root / "price_universes/external-provider-cache"
            ),
            bundle_prefix=Path("price_universes/external-provider-cache"),
        )
    )
    if raw_snapshot_root is not None:
        source = raw_snapshot_root.resolve(strict=True)
        destination = runtime_root / "raw_snapshots"
        if any(destination.iterdir()):
            raise FileExistsError("raw snapshot destination is not empty")
        shutil.copytree(source, destination, dirs_exist_ok=True)
        _secure_tree(destination)
    _secure_tree(runtime_root)
    return {
        "status": "seeded",
        "runtime_root": str(runtime_root),
        "active_artifact_files": len(copied),
        "raw_snapshots_copied": raw_snapshot_root is not None,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, default=Path("deploy/runtime"))
    parser.add_argument("--grocery-db", type=Path, required=True)
    parser.add_argument("--plan-db", type=Path, required=True)
    parser.add_argument("--price-universe-root", type=Path, required=True)
    parser.add_argument("--raw-snapshot-root", type=Path)
    parser.add_argument("--city-slug", default="lund")
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = seed_runtime(
        runtime_root=args.runtime_root,
        grocery_database=args.grocery_db,
        plan_database=args.plan_db,
        universe_root=args.price_universe_root,
        raw_snapshot_root=args.raw_snapshot_root,
        city_slug=args.city_slug,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
