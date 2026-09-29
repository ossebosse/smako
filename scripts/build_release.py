"""Build deterministic, separate server/Windows source packages from a Git commit.

Only Git blobs are read. No worktree, secrets, state, environments or old source
folders enter a package. Wheels are installed separately from locked manifests.
"""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def selected(path, kind):
    parts = Path(path).parts
    if any(p in {"tests", "__pycache__", ".local", "node_modules", "runtime"} for p in parts):
        return False
    if any(path.endswith(s) for s in (".sqlite", ".sqlite3", ".db", ".log", ".smako-source")):
        raise ValueError("Tracked runtime file in release input: " + path)
    if path.startswith(("backend/", "grocery_data/", "deploy/")):
        if Path(path).name.startswith(".env") and not path.endswith((".example", ".template")):
            raise ValueError("Tracked non-template configuration: " + path)
        return True
    return path in {"Dockerfile", ".dockerignore", "pyproject.toml", "requirements-dev.lock",
                    "scripts/run_packaged_relay.py", "scripts/build_release.py"}


def build(commit, output):
    commit = git("rev-parse", "--verify", commit + "^{commit}").decode().strip()
    output.mkdir(parents=True, exist_ok=True)
    paths = git("ls-tree", "-r", "--name-only", commit).decode().splitlines()
    result = {"commit": commit, "source_tag": "consolidation-20260929-local", "packages": {}}
    for kind in ("server", "windows-relay"):
        files = {p: git("show", commit + ":" + p) for p in paths if selected(p, kind)}
        manifest = {"schema": "smako-release-v1", "commit": commit, "kind": kind,
                    "source_contract": "smako-source-snapshot-v1",
                    "files": {p: hashlib.sha256(b).hexdigest() for p, b in files.items()}}
        files["RELEASE.json"] = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
        target = output / f"smako-{kind}-{commit[:12]}.zip"
        # Fixed timestamps, permissions, ordering and compression make same-input
        # builds byte-identical. The manifest deliberately excludes itself.
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path, data in sorted(files.items()):
                info = zipfile.ZipInfo(path, (2026, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
        result["packages"][kind] = {"file": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                                     "bytes": target.stat().st_size, "files": len(files)}
    (output / "release.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.commit, args.output)
