"""Audited source overlay and read-compatible emergency rollback (no data restore)."""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

BUILD = "personal-v2-combined-403020-20260913b"
BASELINE = "4cb6bc8"
BASE_IMAGE = "billigaste-veckomenyn:0.1.0-smako-personal-v2-fishfree-20260913b"


def digest(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def package():
    paths = set(
        subprocess.check_output(["git", "diff", BASELINE, "--name-only"], text=True).splitlines()
    )
    paths.update(
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], text=True
        ).splitlines()
    )
    paths = sorted(p for p in paths if p.startswith("backend/app/"))
    target = Path(f"reports/private/{BUILD}.tar.gz")
    manifest = []
    with tarfile.open(target, "w:gz") as archive:
        for name in paths:
            old = subprocess.run(
                ["git", "show", f"{BASELINE}:{name}"], capture_output=True, check=False
            )
            baseline = old.stdout.replace(b"\r\n", b"\n")
            data = Path(name).read_bytes().replace(b"\r\n", b"\n")
            manifest.append(
                {
                    "path": name,
                    "baseline": digest(baseline) if old.returncode == 0 else None,
                    "sha256": digest(data),
                }
            )
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("overlay-manifest.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    print(
        json.dumps(
            {
                "files": len(manifest),
                "archive": target.name,
                "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    )


def stage():
    root = Path("/opt/smako")
    current = (root / "current").resolve(strict=True)
    assert current == root / "releases/personal-v2-fishfree-20260913b"
    target = root / "releases" / BUILD
    assert not target.exists()
    with tarfile.open(root / "evidence" / f"{BUILD}.tar.gz") as archive:
        manifest = json.load(archive.extractfile("overlay-manifest.json"))
        for item in manifest:
            path = current / item["path"]
            assert path.resolve().is_relative_to(current)
            assert (digest(path.read_bytes()) if path.exists() else None) == item["baseline"], item[
                "path"
            ]
            assert digest(archive.extractfile(item["path"]).read()) == item["sha256"]
        ignore = shutil.ignore_patterns(
            "__pycache__", ".env*", "reports", ".pytest_cache", ".ruff_cache"
        )
        shutil.copytree(current, target, ignore=ignore)
        for item in manifest:
            path = target / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(item["path"]).read())
        (target / "overlay-manifest.json").write_text(json.dumps(manifest, indent=2))
    # Preserve the server's existing TLS/operator configuration verbatim.
    caddy = target / "deploy/Caddyfile"
    original = caddy.read_text()
    assert original.count("\treverse_proxy app:8000 {") == 1
    scoped = "\t# Personal multi-meal planning and edits may need several minutes. Other\n\t# routes, including the existing relay, retain their original timeout.\n\t@planning path /api/plans /api/personal/plans/*/change\n\treverse_proxy @planning app:8000 {\n\t\ttransport http {\n\t\t\tdial_timeout 5s\n\t\t\tresponse_header_timeout 540s\n\t\t}\n\t}\n"
    caddy.write_text(
        original.replace("\treverse_proxy app:8000 {", scoped + "\treverse_proxy app:8000 {")
    )
    (target / "caddy-change.json").write_text(
        json.dumps(
            {
                "before": digest(original.encode()),
                "after": digest(caddy.read_bytes()),
                "paths": ["/api/plans", "/api/personal/plans/*/change"],
                "timeout_seconds": 540,
            }
        )
    )
    for directory, build in ((target, BUILD),):
        # Reuse the already deployed immutable dependency layer. No install,
        # provider collection, source mutation or runtime upload is needed.
        dockerfile = directory / "Dockerfile.gaps"
        dockerfile.write_text(
            f"FROM {BASE_IMAGE}\nENV APP_VERSION=0.1.0-smako-{build} BUILD_ID={build}\nCOPY --chown=app:app backend/app /srv/app/backend/app\n"
        )
        subprocess.run(
            [
                "docker",
                "build",
                "-f",
                str(dockerfile),
                "-t",
                f"billigaste-veckomenyn:0.1.0-smako-{build}",
                str(directory),
            ],
            check=True,
        )
    print(
        json.dumps(
            {
                "status": "STAGED",
                "files": len(manifest),
                "build": BUILD,
                "rollback": "personal-v2-dinners-20260911c-rollback",
            }
        )
    )


if __name__ == "__main__":
    {"package": package, "stage": stage}[sys.argv[1]]()
