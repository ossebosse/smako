import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "release_image_retention",
    Path(__file__).resolve().parents[2] / "scripts/beta_release_workers/image_retention.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
maintain_images, retained_image_ids = module.maintain_images, module.retained_image_ids


def image(identity, created, *, base=None, tags=None):
    return {"Id": identity, "Created": created, "RepoTags": tags or [
        "smako-app:app-" + identity * 12 + "-" + identity * 8],
        "Config": {"Labels": {"smako.release.base_image": base}}}


def test_active_stopped_rollback_and_latest_candidates_stay():
    images = [image("a", "1"), image("b", "2", base="a"), image("c", "3"),
              image("d", "4"), image("e", "5")]
    keep = retained_image_ids(images, [{"Image": "b"}], {"c"})
    assert keep == {"a", "b", "c", "d", "e"}


def test_only_exact_release_tags_are_removed_and_no_volumes_or_containers_pruned():
    import json

    images = [image("a", "1"), image("b", "2", tags=["other-team:keep"]),
              image("c", "3"), image("d", "4")]
    calls = []
    def run(args):
        calls.append(args)
        if args[:3] == ["docker", "image", "ls"]:
            return "a\nb\nc\nd"
        if args[:3] == ["docker", "image", "inspect"]:
            return json.dumps(images)
        return ""
    result = maintain_images(run, protected=set(), completed={"a", "b", "c", "d"})
    assert result["removed_images"] == ["a"]
    removals = [c for c in calls if "rm" in c]
    assert removals == [["docker", "image", "rm", *images[0]["RepoTags"]]]
    assert ["docker", "buildx", "prune", "--force", "--max-used-space", "2GB"] in calls
    assert not any(c[1] in {"volume", "container", "system"} for c in calls)
