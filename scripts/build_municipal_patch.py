"""Reproducible municipal delta over the separately pinned deployed app/source.

Builds local ZIPs only. No production activation or scheduled-task mutation.
"""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path

BASE_COMMIT = "5786d5fa6a0febb7a581a70e583e5c876d494da2"
BASES = {
    "app": "sha256:ca1b35327a553036d282089f20ff7b3956c737d6f83bd10c835ef3dd83b09c9f",
    "source": "sha256:63cc251fcc6f8d4632d1e9e2eb42330b31334beadaa56d235b54cd3bbf5e5742",
}
SOURCE_BACKEND = {
    "backend/app/providers/own.py",
    "backend/app/services/production_price_universe_build.py",
}
WINDOWS_ONLY = {
    "grocery_data/local_relay.py",
    "deploy/scripts/start_packaged_relay.ps1",
    "deploy/scripts/enable_municipal_relay.ps1",
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
    if not paths:
        raise ValueError("empty municipal release")
    args.output.mkdir(parents=True, exist_ok=True)
    packages = []
    for target, image in BASES.items():
        target_paths = [p for p in paths if target == "app" or (
            p not in WINDOWS_ONLY and (not p.startswith("backend/") or p in SOURCE_BACKEND))]
        probe = "import json,base64;from pathlib import Path;paths=" + repr(target_paths) + ";print(json.dumps({p:base64.b64encode((Path('/srv/app')/p).read_bytes()).decode() if (Path('/srv/app')/p).exists() else None for p in paths}))"
        tag = f"smako-comparability-{target}:{BASE_COMMIT[:12]}"
        actual = subprocess.check_output(["docker", "image", "inspect", tag, "--format", "{{.Id}}"]).decode().strip()
        if actual != image:
            raise ValueError("base image identity mismatch")
        original = json.loads(subprocess.check_output([
            "docker", "run", "--rm", "--network=none", "--read-only", "--entrypoint", "python", image, "-c", probe]))
        base_files = {p: base64.b64decode(data) if data is not None else None for p, data in original.items()}
        base_hashes = {p: hashlib.sha256(data).hexdigest() if data is not None else None for p, data in base_files.items()}
        # Apply only this feature's reviewed hunks to each actual runtime. The
        # scheduler deliberately carries an older consumer app dependency tree.
        with tempfile.TemporaryDirectory(dir=args.output.resolve()) as directory:
            work = Path(directory)
            for name, data in base_files.items():
                if data is not None:
                    destination = work / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
            if target == "source":
                patch = git("diff", "--binary", BASE_COMMIT, commit, "--", *target_paths)
                env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(args.output.resolve()))
                subprocess.run(["git", "apply", "--check", "-"], input=patch, cwd=work, env=env, check=True)
                subprocess.run(["git", "apply", "-"], input=patch, cwd=work, env=env, check=True)
                files = {p: (work / p).read_bytes() for p in target_paths}
            else:
                files = {p: git("show", commit + ":" + p) for p in target_paths}
        manifest = {"schema": "municipal-patch-v1", "target": target, "commit": commit,
            "base_commit": BASE_COMMIT, "base_image": image, "base_tag": tag, "base_files": base_hashes,
            "files": {p: hashlib.sha256(data).hexdigest() for p, data in files.items()}}
        payload = dict(files)
        payload["MUNICIPAL-PATCH.json"] = json.dumps(manifest, indent=2).encode()
        payload["verify-base.py"] = b"import hashlib,json;from pathlib import Path;m=json.loads(Path('/tmp/MUNICIPAL-PATCH.json').read_bytes());assert all((hashlib.sha256((Path('/srv/app')/p).read_bytes()).hexdigest() if (Path('/srv/app')/p).exists() else None)==h for p,h in m['base_files'].items()),'base code mismatch'"
        copies = "\n".join(f"COPY --chown=app:app {p} /srv/app/{p}" for p in target_paths)
        payload["Dockerfile"] = (f"FROM {tag}\nUSER root\nCOPY MUNICIPAL-PATCH.json verify-base.py /tmp/\nRUN python /tmp/verify-base.py\n"
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
