"""Read-only consistent production copy for isolated replay, never activation.

Source must be mounted :ro. Online SQLite backups, manifest/DB/WAL stability
checks and quick_check fail the copy if production changes while copying.
No locks, schedules or source configuration are changed.
"""

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

src = Path("/source")
dst = Path("/destination")
assert not any(dst.iterdir())
databases = {
    "grocery/grocery_data.sqlite": "grocery.sqlite",
    "plans/consumer_plans.sqlite3": "plans.sqlite",
}


def fingerprints():
    result = {}
    paths = [src / p for p in databases]
    paths += [Path(str(p) + "-wal") for p in paths]
    paths += list((src / "price_universes/active").glob("*.json"))
    for path in paths:
        if path.exists():
            with path.open("rb") as stream:
                result[str(path.relative_to(src))] = hashlib.file_digest(
                    stream, "sha256"
                ).hexdigest()
    return result


before = fingerprints()
checks = {}
for source, target in databases.items():
    wal = Path(str(src / source) + "-wal")
    assert not wal.exists() or wal.stat().st_size == 0, (
        "uncheckpointed WAL: cannot use immutable read-only copy"
    )
    with (
        sqlite3.connect(f"file:{src / source}?mode=ro&immutable=1", uri=True) as source_db,
        sqlite3.connect(dst / target) as target_db,
    ):
        source_db.backup(target_db)
        checks[target] = target_db.execute("PRAGMA quick_check").fetchone()[0]
for source, target in [("raw_snapshots", "raw"), ("price_universes", "price-universes")]:
    shutil.copytree(src / source, dst / target, copy_function=shutil.copy2)
after = fingerprints()
report = {
    "source_read_only": True,
    "source_stable_during_copy": before == after,
    "source_hashes": before,
    "sqlite": checks,
}
(dst / "ops-production-copy.json").write_text(json.dumps(report, indent=2) + "\n")
assert before == after and all(v == "ok" for v in checks.values()), "inconsistent copy, do not use"
print(json.dumps({"source_stable_during_copy": True, "sqlite": checks}))
