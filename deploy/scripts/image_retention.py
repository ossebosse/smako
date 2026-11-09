"""Daily retention of old Smako Docker images on the beta host.

Runs on the host as root (systemd timer smako-image-retention.timer), because
the scheduler container has no Docker access. Owner decision 2026-11-09: old
Smako images are removed automatically so releases and backups keep disk space.

An image is kept when any of these holds:
- a container uses it, running or stopped;
- it is the recorded release base (label smako.release.base_image) of an
  image a container uses, i.e. that release's rollback;
- it was created within the last KEEP_DAYS days (candidates, recent rollbacks);
- it is among the KEEP_NEWEST newest images of a repository that a container
  uses (smako-app, smako-scheduler: current release, rollback, candidates);
- it has a tag outside the smako* repositories or no tag;
- it is listed in /opt/smako/image-retention-protect.txt (id or tag per line).

Everything else is removed with `docker image rm <tags>`, never --force, so
Docker itself refuses an image that became referenced meanwhile. Volumes,
containers and untagged layers are not touched. Unused build cache is kept to
the same 2 GB budget as the release helper. Dry run unless --apply.
Python 3.11+ standard library only (the host's python3).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

KEEP_DAYS = 7
KEEP_NEWEST = 3
PROTECT_FILE = Path("/opt/smako/image-retention-protect.txt")
RECEIPT = Path("/opt/smako/evidence/image-retention/latest.json")
BUILD_CACHE_BUDGET = "2GB"


def created(image):
    # Docker writes nanoseconds; keep the second part for fromisoformat.
    text = image["Created"].split(".")[0].rstrip("Z")
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


def repository(tag):
    return tag.rsplit(":", 1)[0]


def plan(images, containers, *, now, protected=(), keep_days=KEEP_DAYS, keep_newest=KEEP_NEWEST):
    """Return {image id: reason} to keep and [image] to remove."""
    protected = set(protected)
    keep = {}
    for c in containers:
        keep.setdefault(c["Image"], "container")
    by_repo = {}
    for image in images:
        tags = image.get("RepoTags") or []
        if image["Id"] in protected or any(t in protected for t in tags):
            keep.setdefault(image["Id"], "protected")
        # Local builds also carry digests under the containerd image store,
        # so a digest does not mark a pulled image; the repository name does.
        if not tags or not all(t.startswith("smako") for t in tags):
            keep.setdefault(image["Id"], "foreign_or_untagged")
        if created(image) >= now - timedelta(days=keep_days):
            keep.setdefault(image["Id"], "recent")
        for tag in tags:
            by_repo.setdefault(repository(tag), []).append(image)
    ids = {i["Id"]: i for i in images}
    in_use = {repository(t) for c in containers for t in (ids.get(c["Image"], {}).get("RepoTags") or [])}
    for repo, rows in by_repo.items():
        if repo not in in_use:
            continue
        for image in sorted(rows, key=created, reverse=True)[:keep_newest]:
            keep.setdefault(image["Id"], "newest_in_repository")
    # The immediate release base of a used image is its rollback. Not the
    # whole chain: every release is built on the previous one.
    labels = {i["Id"]: ((i.get("Config") or {}).get("Labels") or {}) for i in images}
    for used in [i for i, reason in keep.items() if reason in ("container", "protected")]:
        base = labels.get(used, {}).get("smako.release.base_image")
        if base and base not in keep:
            keep[base] = "release_base"
    remove = [i for i in images if i["Id"] not in keep]
    return keep, remove


def docker(*args):
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=True).stdout


def inventory():
    ids = sorted(set(docker("image", "ls", "-a", "--no-trunc", "-q").split()))
    images = json.loads(docker("image", "inspect", *ids)) if ids else []
    container_ids = docker("ps", "-aq", "--no-trunc").split()
    containers = json.loads(docker("inspect", *container_ids)) if container_ids else []
    return images, containers


def protected_entries():
    if not PROTECT_FILE.is_file():
        return set()
    return {line.strip() for line in PROTECT_FILE.read_text(encoding="utf8").splitlines()
            if line.strip() and not line.startswith("#")}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="remove the selected images")
    args = parser.parse_args()
    now = datetime.now(UTC)
    free_before = shutil.disk_usage("/").free
    images, containers = inventory()
    keep, remove = plan(images, containers, now=now, protected=protected_entries())
    removed, refused = [], []
    for image in remove:
        tags = image["RepoTags"]
        if not args.apply:
            continue
        result = subprocess.run(["docker", "image", "rm", *tags], capture_output=True, text=True, check=False)
        (removed if result.returncode == 0 else refused).append(
            {"id": image["Id"], "tags": tags, **({} if result.returncode == 0 else {"error": result.stderr.strip()[-300:]})})
    if args.apply:
        subprocess.run(["docker", "buildx", "prune", "--force", "--max-used-space", BUILD_CACHE_BUDGET],
                       capture_output=True, text=True, check=False)
    receipt = {
        "status": "applied" if args.apply else "dry_run",
        "at": now.isoformat(),
        "policy": {"keep_days": KEEP_DAYS, "keep_newest_per_repository": KEEP_NEWEST,
                   "build_cache_budget": BUILD_CACHE_BUDGET},
        "images_total": len(images),
        "kept": {reason: sum(1 for r in keep.values() if r == reason) for reason in sorted(set(keep.values()))},
        "selected": [{"id": i["Id"], "tags": i["RepoTags"], "created": i["Created"][:19]} for i in remove],
        "removed": removed,
        "refused": refused,
        "free_bytes_before": free_before,
        "free_bytes_after": shutil.disk_usage("/").free,
    }
    if args.apply:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k: v for k, v in receipt.items() if k not in ("selected", "removed")}
                     | {"selected": len(remove), "removed": len(removed)}, indent=2))


if __name__ == "__main__":
    main()
