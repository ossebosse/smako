"""Hash-verified application overlay; reuse the deployed dependency image."""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

BUILD = "personal-v2-fast-403020-20260913c"
BASELINE = "df4685a"
PRIOR = "personal-v2-fast-403020-20260913a"
BASE_IMAGE = f"billigaste-veckomenyn:0.1.0-smako-{PRIOR}"


def digest(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def package():
    paths = subprocess.check_output(
        ["git", "diff", BASELINE, "--name-only", "--", "backend/app"], text=True
    ).splitlines()
    baseline = {}
    for path in subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASELINE, "backend/app"], text=True
    ).splitlines():
        baseline[path] = digest(subprocess.check_output(["git", "show", f"{BASELINE}:{path}"]))
    target = Path(f"reports/private/{BUILD}.tar.gz")
    manifest = {"baseline_commit": BASELINE, "baseline": baseline, "changed": {}}
    with tarfile.open(target, "w:gz") as archive:
        for name in paths:
            data = Path(name).read_bytes().replace(b"\r\n", b"\n")
            manifest["changed"][name] = digest(data)
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("overlay-manifest.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    Path("reports/performance-403020/release-source-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf8"
    )
    print(
        json.dumps(
            {
                "files": len(paths),
                "baseline_files": len(baseline),
                "archive_sha256": digest(target.read_bytes()),
            }
        )
    )


def stage():
    root = Path("/opt/smako")
    current = (root / "current").resolve(strict=True)
    assert current == root / "releases" / PRIOR
    target = root / "releases" / BUILD
    assert not target.exists()
    with tarfile.open(root / "evidence" / f"{BUILD}.tar.gz") as archive:
        manifest = json.load(archive.extractfile("overlay-manifest.json"))
        for name, expected in manifest["baseline"].items():
            assert name.startswith("backend/app/")
            path = current / name
            assert path.resolve().is_relative_to(current)
            assert digest(path.read_bytes()) == expected, name
        ignore = shutil.ignore_patterns(
            "__pycache__", ".env*", "reports", ".pytest_cache", ".ruff_cache"
        )
        shutil.copytree(current, target, ignore=ignore)
        for name, expected in manifest["changed"].items():
            assert name in manifest["baseline"]
            data = archive.extractfile(name).read()
            assert digest(data) == expected
            (target / name).write_bytes(data)
    dockerfile = target / "Dockerfile.performance"
    dockerfile.write_text(
        f"FROM {BASE_IMAGE}\nENV APP_VERSION=0.1.0-smako-{BUILD} BUILD_ID={BUILD}\n"
        "COPY --chown=app:app backend/app /srv/app/backend/app\n"
    )
    subprocess.run(
        [
            "docker",
            "build",
            "-f",
            str(dockerfile),
            "-t",
            f"billigaste-veckomenyn:0.1.0-smako-{BUILD}",
            str(target),
        ],
        check=True,
    )
    result = {
        "build": BUILD,
        "baseline_commit": BASELINE,
        "baseline_app_files_verified": len(manifest["baseline"]),
        "changed_files": manifest["changed"],
        "prior": PRIOR,
    }
    (root / "evidence/performance-403020/staging.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    {"package": package, "stage": stage}[sys.argv[1]]()
