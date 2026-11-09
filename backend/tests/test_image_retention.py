"""Selection rules of the host's daily Docker image retention."""
from datetime import UTC, datetime
from importlib import util
from pathlib import Path

SPEC = util.spec_from_file_location(
    "image_retention", Path(__file__).resolve().parents[2] / "deploy/scripts/image_retention.py")
retention = util.module_from_spec(SPEC)
SPEC.loader.exec_module(retention)

NOW = datetime(2026, 11, 9, 16, 0, tzinfo=UTC)


def image(id_, tags, day, *, base=None, digests=None):
    labels = {"smako.release.base_image": base} if base else {}
    return {"Id": id_, "RepoTags": tags, "Created": f"2026-{day}T10:00:00.123456789Z",
            "RepoDigests": digests or [], "Config": {"Labels": labels}}


def test_keeps_used_recent_newest_bases_and_foreign_images():
    images = [
        image("active", ["smako-app:app-979312084e7c-84cf5cea"], "11-08", base="base-a"),
        image("base-a", ["smako-app:reviewed-base-old"], "10-01", base="base-b"),
        image("base-b", ["smako-app:reviewed-base-older"], "09-20"),
        image("candidate", ["smako-app:app-78c2649a2bf2-083247bf"], "11-09"),
        image("rollback", ["smako-app:app-e02a2ef7f0db-1d6fdb43"], "11-01"),
        image("older-app", ["smako-app:app-431ddb3ac0f2-28522b51"], "10-25"),
        image("oldest-app", ["smako-app:app-d949478e41b4-1d553cf8"], "10-20"),
        image("scheduler", ["smako-scheduler:source-ops-e6d4ceaca5bc"], "11-05"),
        image("stopped", ["smako-ops-runtime:7aa77aab2361"], "10-13"),
        image("one-off", ["smako-ica-estimates-app:20261014"], "10-14"),
        image("one-off-2", ["smako-ui-option3:ff241807809b", "smako-retention-base:x"], "10-14"),
        image("caddy", ["caddy:2.10.2-alpine"], "09-01", digests=["caddy@sha256:abc"]),
        image("built", ["smako-willys-picking:scheduler-98eadc2b114c"], "10-15", digests=["smako-willys-picking@sha256:def"]),
        image("mixed", ["smako-app:x", "other:y"], "09-01"),
        image("untagged", [], "09-01"),
        image("pinned", ["smako-hemkop-context:scheduler-c6607a095018"], "10-18"),
    ]
    containers = [{"Image": "active"}, {"Image": "scheduler"}, {"Image": "caddy"}, {"Image": "stopped"}]
    keep, remove = retention.plan(images, containers, now=NOW, protected={"smako-hemkop-context:scheduler-c6607a095018"})
    assert keep["active"] == "container" and keep["stopped"] == "container"
    assert keep["base-a"] == "release_base"
    assert keep["candidate"] == "recent"
    assert keep["rollback"] == "newest_in_repository"
    assert keep["caddy"] == "container" and keep["mixed"] == "foreign_or_untagged"
    assert keep["untagged"] == "foreign_or_untagged"
    assert keep["pinned"] == "protected"
    # Repositories no container uses do not get the newest-three protection.
    assert sorted(i["Id"] for i in remove) == ["base-b", "built", "older-app", "oldest-app", "one-off", "one-off-2"]


def test_newest_three_per_used_repository():
    images = [image(f"app-{n}", [f"smako-app:app-{n:012x}-00000000"], f"10-{10 + n}") for n in range(6)]
    keep, remove = retention.plan(images, [{"Image": "app-0"}], now=NOW)
    assert {i for i, r in keep.items() if r == "newest_in_repository"} == {"app-5", "app-4", "app-3"}
    assert sorted(i["Id"] for i in remove) == ["app-1", "app-2"]
