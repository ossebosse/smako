"""Copy only an isolated release dataset, with SQLite online backups.

Run with /source mounted read-only and a new empty /destination. Never target
production. Retains raw bytes and source timestamps; does not rebuild prices.
"""

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

source = Path("/source")
destination = Path("/destination")
assert not any(destination.iterdir()), "destination must be empty"
report = {"sqlite": {}, "files": {}}
for name in ("grocery.sqlite", "plans.sqlite"):
    wal = source / (name + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0, "source has uncheckpointed WAL"
    with (
        sqlite3.connect(f"file:{source / name}?mode=ro&immutable=1", uri=True) as src,
        sqlite3.connect(destination / name) as dst,
    ):
        src.backup(dst)
        report["sqlite"][name] = dst.execute("PRAGMA quick_check").fetchone()[0]
for name in ("raw", "price-universes"):
    shutil.copytree(source / name, destination / name, copy_function=shutil.copy2)
for name in (
    "coop-municipal",
    "hemkop-municipal",
    "lidl-municipal",
    "citygross-municipal",
    "willys-flyer",
    "ica-structured",
):
    if (source / name).is_dir():
        shutil.copytree(source / name, destination / name, copy_function=shutil.copy2)
if (source / "willys-config.json").exists():
    shutil.copy2(source / "willys-config.json", destination / "willys-config.json")
for name in ("policy.json", "http-results.json", "representative-bdc9-results.json"):
    request_source = Path("/requests") if Path("/requests").is_dir() else source
    shutil.copy2(request_source / name, destination / name)
    report["files"][name] = hashlib.sha256((destination / name).read_bytes()).hexdigest()
(destination / "ops-copy.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
