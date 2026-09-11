"""Hash-checked app-only overlay over e8e6f77; no model/DB/collector changes."""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

BUILD = "personal-v2-qualified-20260911b"
PRIOR = "personal-v2-qualified-20260911"
BASELINE = "e8e6f77"


def digest(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def package():
    names = set(
        subprocess.check_output(["git", "diff", BASELINE, "--name-only"], text=True).splitlines()
    )
    names.update(
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], text=True
        ).splitlines()
    )
    names = sorted(n for n in names if n.startswith("backend/app/"))
    manifest = []
    with tarfile.open(f"reports/private/{BUILD}.tar.gz", "w:gz") as archive:
        for name in names:
            old = subprocess.run(
                ["git", "show", f"{BASELINE}:{name}"], capture_output=True, check=False
            )
            data = Path(name).read_bytes().replace(b"\r\n", b"\n")
            manifest.append(
                {
                    "path": name,
                    "baseline": digest(old.stdout) if old.returncode == 0 else None,
                    "sha256": digest(data),
                }
            )
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("qualified-overlay.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    print(json.dumps({"build": BUILD, "files": manifest}))


def stage():
    root = Path("/opt/smako")
    current = (root / "current").resolve(strict=True)
    assert current == root / "releases" / PRIOR
    target = root / "releases" / BUILD
    assert not target.exists()
    for row in json.loads((current / "qualified-overlay.json").read_bytes()):
        assert digest((current / row["path"]).read_bytes()) == row["sha256"]
    with tarfile.open(root / "evidence" / f"{BUILD}.tar.gz") as archive:
        manifest = json.load(archive.extractfile("qualified-overlay.json"))
        for row in manifest:
            path = root / "releases" / "personal-v2-gaps-20260911c" / row["path"]
            assert path.resolve().is_relative_to(root / "releases" / "personal-v2-gaps-20260911c")
            assert (digest(path.read_bytes()) if path.exists() else None) == row["baseline"], row[
                "path"
            ]
            assert digest(archive.extractfile(row["path"]).read()) == row["sha256"]
        shutil.copytree(
            current,
            target,
            ignore=shutil.ignore_patterns(
                "__pycache__", ".env*", "reports", ".pytest_cache", ".ruff_cache"
            ),
        )
        for row in manifest:
            path = target / row["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(row["path"]).read())
        (target / "qualified-overlay.json").write_text(json.dumps(manifest, indent=2))
    dockerfile = target / "Dockerfile.qualified"
    dockerfile.write_text(
        f"FROM billigaste-veckomenyn:0.1.0-smako-{PRIOR}\nENV APP_VERSION=0.1.0-smako-{BUILD} BUILD_ID={BUILD}\nCOPY --chown=app:app backend/app /srv/app/backend/app\n"
    )
    subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(dockerfile),
            "-t",
            "billigaste-veckomenyn:0.1.0-smako-" + BUILD,
            str(target),
        ],
        check=True,
    )
    print(
        json.dumps({"status": "STAGED", "build": BUILD, "rollback": PRIOR, "files": len(manifest)})
    )


if __name__ == "__main__":
    {"package": package, "stage": stage}[sys.argv[1]]()
