"""Reproducible municipal delta over the separately pinned deployed app/source.

Builds local ZIPs only. No production activation or scheduled-task mutation.
"""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

BASE_COMMIT = "5786d5fa6a0febb7a581a70e583e5c876d494da2"
BASES = {
    "app": "sha256:ca1b35327a553036d282089f20ff7b3956c737d6f83bd10c835ef3dd83b09c9f",
    "source": "sha256:63cc251fcc6f8d4632d1e9e2eb42330b31334beadaa56d235b54cd3bbf5e5742",
}


def git(*args):
    return subprocess.check_output(["git", *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    commit = git("rev-parse", args.commit + "^{commit}").decode().strip()
    paths = git("diff", "--name-only", BASE_COMMIT, commit, "--", "backend/app", "grocery_data", "deploy/scripts").decode().splitlines()
    paths = [p for p in paths if "/tests/" not in p]
    files = {p: git("show", commit + ":" + p) for p in paths}
    if not files:
        raise ValueError("empty municipal release")
    probe = "import json,hashlib;from pathlib import Path;paths=" + repr(paths) + ";print(json.dumps({p:hashlib.sha256((Path('/srv/app')/p).read_bytes()).hexdigest() if (Path('/srv/app')/p).exists() else None for p in paths}))"
    args.output.mkdir(parents=True, exist_ok=True)
    packages = []
    for target, image in BASES.items():
        base_hashes = json.loads(subprocess.check_output([
            "docker", "run", "--rm", "--network=none", "--read-only", "--entrypoint", "python", image, "-c", probe]))
        manifest = {"schema": "municipal-patch-v1", "target": target, "commit": commit,
            "base_commit": BASE_COMMIT, "base_image": image, "base_files": base_hashes,
            "files": {p: hashlib.sha256(data).hexdigest() for p, data in files.items()}}
        payload = dict(files)
        payload["MUNICIPAL-PATCH.json"] = json.dumps(manifest, indent=2).encode()
        payload["verify-base.py"] = b"import hashlib,json;from pathlib import Path;m=json.loads(Path('/tmp/MUNICIPAL-PATCH.json').read_bytes());assert all((hashlib.sha256((Path('/srv/app')/p).read_bytes()).hexdigest() if (Path('/srv/app')/p).exists() else None)==h for p,h in m['base_files'].items()),'base code mismatch'"
        copies = "\n".join(f"COPY --chown=app:app {p} /srv/app/{p}" for p in paths)
        payload["Dockerfile"] = (f"FROM {image}\nUSER root\nCOPY MUNICIPAL-PATCH.json verify-base.py /tmp/\nRUN python /tmp/verify-base.py\n"
            + copies + f"\nCOPY MUNICIPAL-PATCH.json /srv/app/MUNICIPAL-PATCH.json\nENV BUILD_ID=municipal-{target}-{commit[:12]}\nLABEL org.opencontainers.image.revision={commit}\nUSER app\n").encode()
        destination = args.output / f"smako-municipal-{target}-{commit[:12]}.zip"
        with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
        packages.append({"target": target, "commit": commit, "base_image": image,
            "package": str(destination), "bytes": destination.stat().st_size,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(), "files": manifest["files"]})
    (args.output / "packages.json").write_text(json.dumps(packages, indent=2), encoding="utf-8")
    print(json.dumps([{k: v for k, v in p.items() if k != "files"} for p in packages]))


if __name__ == "__main__":
    main()
