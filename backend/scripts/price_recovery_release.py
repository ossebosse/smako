"""Hash-verified application overlay; reuse the deployed dependency image."""

import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

BUILD = "price-recovery-lund-20260914a"
BASELINE = "f5935e5"
PRIOR = "personal-v2-fast-403020-20260913c"
BASE_IMAGE = f"billigaste-veckomenyn:0.1.0-smako-{PRIOR}"


def digest(data):
    return hashlib.sha256(data.replace(b"\r", b"")).hexdigest()


def package():
    paths = subprocess.check_output(
        ["git", "diff", BASELINE, "--name-only", "--", "backend/app", "grocery_data", "deploy"],
        text=True,
    ).splitlines()
    paths.append("grocery_data/app/services/refresh_diagnostics.py")
    paths = [p for p in paths if "/tests/" not in p]
    baseline = {}
    for path in subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", BASELINE, "backend/app", "grocery_data", "deploy"],
        text=True,
    ).splitlines():
        if path in {"grocery_data/relay_preflight.py", "grocery_data/relay_status.py"}:
            continue
        if path not in paths and not path.startswith("backend/app/"):
            continue
        before = subprocess.check_output(["git", "show", f"{BASELINE}:{path}"])
        if path == "deploy/compose.yaml":
            before = before.replace(b"${ACME_EMAIL:?set ACME_EMAIL in deploy/.env.production}", b"${ACME_EMAIL:-}")
        if path == "grocery_data/local_relay.py":
            before = Path("reports/recovery-22350/local_relay.py.deployed").read_bytes()
        baseline[path] = digest(before)
    target = Path(f"reports/private/{BUILD}.tar.gz")
    manifest = {"baseline_commit": BASELINE, "baseline": baseline, "changed": {}}
    with tarfile.open(target, "w:gz") as archive:
        for name in paths:
            data = Path(name).read_bytes().replace(b"\r\n", b"\n")
            if name == "deploy/compose.yaml":
                data = data.replace(b"${ACME_EMAIL:?set ACME_EMAIL in deploy/.env.production}", b"${ACME_EMAIL:-}")
            manifest["changed"][name] = digest(data)
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("overlay-manifest.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    Path("reports/recovery-22350/release-source-manifest.json").write_text(
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
            assert name.startswith(("backend/app/", "grocery_data/", "deploy/"))
            path = current / name
            assert path.resolve().is_relative_to(current)
            assert digest(path.read_bytes()) == expected, name
        ignore = shutil.ignore_patterns(
            "__pycache__", ".env*", "reports", ".pytest_cache", ".ruff_cache"
        )
        shutil.copytree(current, target, ignore=ignore)
        for name, expected in manifest["changed"].items():
            assert (
                name in manifest["baseline"]
                or name in {"grocery_data/app/services/refresh_diagnostics.py", "grocery_data/relay_preflight.py", "grocery_data/relay_status.py"}
            )
            data = archive.extractfile(name).read()
            assert digest(data) == expected
            (target / name).write_bytes(data)
    dockerfile = target / "Dockerfile.performance"
    dockerfile.write_text(
        f"FROM {BASE_IMAGE}\nENV APP_VERSION=0.1.0-smako-{BUILD} BUILD_ID={BUILD}\n"
        "COPY --chown=app:app backend/app /srv/app/backend/app\n"
        "COPY --chown=app:app grocery_data /srv/app/grocery_data\n"
        "COPY --chown=app:app deploy /srv/app/deploy\n"
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
    (root / "evidence/recovery-22350/staging.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == "__main__":
    {"package": package, "stage": stage}[sys.argv[1]]()
