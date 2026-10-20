import json
from datetime import UTC, datetime

from backend.tests.test_storage_maintenance import old
from deploy.scripts import municipal_retention
from deploy.scripts.municipal_retention import prune_scope

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def attempt(root, number, *, flat=False):
    identity = f"202608{number:02d}T000000-" + ("abcdef12" if flat else "abcdef123456")
    path = root / identity if flat else root / "attempts" / identity
    path.mkdir(parents=True)
    (path / "report.json").write_text("test")
    old(path)
    return path


def test_attempts_keep_pointers_and_raw_dependencies_of_a_copied_database(tmp_path):
    paths = [attempt(tmp_path, i) for i in range(1, 7)]
    needed = paths[1] / "raw/willys/store/snapshot/body.json"
    needed.parent.mkdir(parents=True)
    needed.write_text("needed by the current copied database")
    old(paths[1])
    result = prune_scope(tmp_path, protected_tokens={paths[2].name},
                         required_raw={("willys", "store", "snapshot", "body.json")},
                         now=NOW, apply=True)
    assert set(result["removed"]) == {paths[0].name, paths[3].name}
    assert needed.exists() and paths[2].exists()
    assert all(p.exists() for p in paths[-2:])


def test_flat_attempt_database_raw_and_report_are_one_retention_group(tmp_path):
    paths = [attempt(tmp_path, i, flat=True) for i in range(1, 5)]
    database = paths[0].with_suffix(".sqlite")
    database.write_bytes(b"retired database")
    old(database)
    raw = paths[0].with_name(paths[0].name + "-raw")
    raw.mkdir()
    (raw / "body").write_text("retired raw")
    old(raw)
    protected = paths[1].with_suffix(".sqlite")
    protected.write_bytes(b"current database")
    old(protected)
    result = prune_scope(tmp_path, protected_tokens={paths[1].name},
                         required_raw=set(), now=NOW, apply=True)
    assert set(result["removed"]) == {paths[0].name, database.name, raw.name}
    assert protected.exists()


def test_recent_unknown_and_partial_reference_groups_survive(tmp_path, monkeypatch):
    base = tmp_path / "grocery/coop"
    scope = base / "1281"
    paths = [attempt(scope, i) for i in range(1, 5)]
    unknown = scope / "manual-candidate"
    unknown.mkdir()
    old(unknown)
    state = scope / "source-state.json"
    state.write_text(json.dumps({"partial_approved": {"store": [{"database": str(paths[0] / "partial.sqlite")}]}}))
    monkeypatch.setenv("COOP_MUNICIPAL_OFFERS_ROOT", str(base))
    monkeypatch.setattr(municipal_retention, "SOURCE_ROOTS", {"COOP_MUNICIPAL_OFFERS_ROOT": "coop"})
    monkeypatch.setattr(municipal_retention, "recovery_roots", lambda: {"grocery": tmp_path / "grocery"})
    monkeypatch.setattr(municipal_retention, "current_files", lambda: {"state": state})
    result = municipal_retention.maintain(now=NOW, apply=True)
    assert len(result["removed"]) == 1 and paths[0].exists() and unknown.exists()
