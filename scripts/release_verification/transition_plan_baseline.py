"""Assemble a later complete plan baseline before creating transition test plans.

Only run with the isolated application stopped. The 34 live-copy rows must be
an identical subset of the later 37-row verification store; preserve both.
"""

import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path

target = Path("/work/plans.sqlite")
source = Path("/later/plans.sqlite")


def rows(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        return {(r[0], r[1]): r for r in db.execute("SELECT * FROM consumer_plan_revisions")}


before, later = rows(target), rows(source)
assert len(before) == 34 and len(later) == 37
assert all(later.get(k) == v for k, v in before.items())
preserved = target.with_name("before-plan-baseline.sqlite")
assert not preserved.exists()
with (
    sqlite3.connect(target.as_uri() + "?mode=ro", uri=True) as src,
    sqlite3.connect(preserved) as dst,
):
    src.backup(dst)
temporary = target.with_name("later-plan-baseline.sqlite")
assert not temporary.exists()
with (
    sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src,
    sqlite3.connect(temporary) as dst,
):
    src.backup(dst)
assert rows(temporary) == later
for suffix in ("-wal", "-shm"):
    sidecar = Path(str(target) + suffix)
    if sidecar.exists():
        if suffix == "-wal":
            assert sidecar.stat().st_size == 0
        sidecar.rename(sidecar.with_name("before-plan-baseline" + suffix))
os.replace(temporary, target)
for old, new in [
    ("ops-private.json", "ops-private.json"),
    ("ops-cookies.json", "ops-cookies.json"),
    ("ops-created.json", "older-created.json"),
]:
    shutil.copyfile(source.parent / old, target.parent / new)
    (target.parent / new).chmod(0o600)
report = {
    "before_revisions": len(before),
    "baseline_revisions": len(later),
    "all_previous_rows_identical": True,
    "baseline_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "preserved_previous_sha256": hashlib.sha256(preserved.read_bytes()).hexdigest(),
}
(target.parent / "transition-plan-baseline.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
