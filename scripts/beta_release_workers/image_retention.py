"""Release-owned Docker retention. Injected into the reviewed release worker."""
import json
import re
from pathlib import Path

MANAGED_TAG = re.compile(r"smako-app:app-[0-9a-f]{12}-[0-9a-f]{8}")


def retained_image_ids(images, containers, protected):
    owners = set(protected) | {c["Image"] for c in containers}
    keep = owners.copy()
    for image in images:
        if image["Id"] in owners:
            base = (image.get("Config", {}).get("Labels") or {}).get("smako.release.base_image")
            if base:
                keep.add(base)
    # Two newest candidates are also protected before activation/verification.
    keep.update(row["Id"] for row in sorted(images, key=lambda row: row["Created"], reverse=True)[:2])
    return keep


def maintain_images(run, *, protected, completed=None):
    """No volume/container prune; unknown tags and remote digests stay intact."""
    ids = run(["docker", "image", "ls", "--filter", "label=smako.managed=app-release-v1",
               "--no-trunc", "--quiet"]).splitlines()
    images = json.loads(run(["docker", "image", "inspect", *sorted(set(ids))])) if ids else []
    container_ids = run(["docker", "ps", "-aq"]).splitlines()
    containers = json.loads(run(["docker", "inspect", *container_ids])) if container_ids else []
    keep = retained_image_ids(images, containers, protected)
    if completed is None:
        completed = set()
        for image in images:
            for tag in image.get("RepoTags") or []:
                if not MANAGED_TAG.fullmatch(tag):
                    continue
                receipt = Path("/opt/smako/evidence") / tag.split(":", 1)[1] / "activation-success.json"
                if receipt.is_file():
                    report = json.loads(receipt.read_bytes())
                    if report.get("status") == "activated" and report.get("runtimes", {}).get("app", {}).get("image") == image["Id"]:
                        completed.add(image["Id"])
    removed = []
    for image in images:
        tags = image.get("RepoTags") or []
        if (image["Id"] in keep or image["Id"] not in completed or not tags or image.get("RepoDigests")
                or not all(MANAGED_TAG.fullmatch(tag) for tag in tags)):
            continue
        # Docker serializes reference checks for its own deletion. Never use
        # --force: a newly referenced image must survive a concurrent change.
        run(["docker", "image", "rm", *tags])
        removed.append(image["Id"])
    # BuildKit evicts only unused cache. Application/rollback images and all
    # volumes are independent of this budget. Supported by the target CLI.
    run(["docker", "buildx", "prune", "--force", "--max-used-space", "2GB"])
    return {"removed_images": removed, "protected_images": sorted(keep),
            "build_cache_max_used_space": "2GB"}
