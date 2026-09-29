"""Restore hash-verified retained inputs from the separately protected backup.

Run from the repository root. This never contacts retailers or production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inside(base: Path, name: str) -> Path:
    path = (base / name).resolve()
    if not path.is_relative_to(base) or path == base:
        raise ValueError("Path outside selected root")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backup", type=Path, required=True, help="Backup directory containing snapshot/"
    )
    parser.add_argument(
        "--all-evidence",
        action="store_true",
        help="Restore all selected historical evidence, not only test inputs",
    )
    parser.add_argument("--check", action="store_true", help="Verify without writing")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = (args.backup / "snapshot").resolve(strict=True)
    manifests = root / "docs/consolidation"
    names = (
        sorted(manifests.glob("evidence-*.jsonl"))
        if args.all_evidence
        else [manifests / "test-data.jsonl"]
    )
    rows = [
        json.loads(line)
        for name in names
        for line in name.read_text(encoding="utf8").splitlines()
        if line
    ]
    restored = present = 0
    for row in rows:
        target = inside(root, row["path"])
        if target.exists():
            if target.stat().st_size != row["bytes"] or digest(target) != row["sha256"]:
                raise RuntimeError("Existing file differs; preserve and review: " + row["path"])
            present += 1
            continue
        original = inside(source, row["backup_path"])
        if original.stat().st_size != row["bytes"] or digest(original) != row["sha256"]:
            raise RuntimeError("Backup checksum mismatch: " + row["path"])
        if args.check:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".restore-part")
        with temporary.open("xb") as output, original.open("rb") as incoming:
            shutil.copyfileobj(incoming, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        if digest(temporary) != row["sha256"]:
            raise RuntimeError("Restored checksum mismatch: " + row["path"])
        if target.exists():
            raise RuntimeError("Concurrent write detected: " + row["path"])
        temporary.rename(target)
        restored += 1
    print(
        f"Verified {len(rows)} inputs; {present} present, {restored} restored; check={args.check}"
    )


if __name__ == "__main__":
    main()
