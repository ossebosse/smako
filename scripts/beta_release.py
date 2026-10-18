"""Prepare, build and activate a reviewed app-only patch on the existing beta.

Uses the active immutable image and build_source_patch.transplant. No scheduler,
dependency, database schema or configuration changes are supported. See docs/BETA.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from build_source_patch import transplant

ROOT = Path(__file__).resolve().parents[1]
WORKERS = ROOT / "scripts/beta_release_workers"


def valid_path(path):
    return (
        re.fullmatch(r"[A-Za-z0-9_./-]+", path) is not None
        and not PurePosixPath(path).is_absolute()
        and ".." not in PurePosixPath(path).parts
        and path.startswith("backend/app/")
        and "__pycache__" not in path
        and not path.endswith((".pyc", ".sqlite", ".sqlite3", ".db"))
    )


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode().strip()


def blob(ref, path):
    result = subprocess.run(
        ["git", "-C", str(ROOT), "show", ref + ":" + path], capture_output=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def remote(host, code):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", host):
        raise ValueError("Use an SSH host alias or user@host, without options")
    return subprocess.check_output(
        [
            "ssh",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "ServerAliveInterval=15",
            host,
            "sudo -n python3 -u -",
        ],
        input=code.encode(),
    )


def prepare(args):
    before = git("rev-parse", "--verify", args.from_commit + "^{commit}")
    commit = git("rev-parse", "--verify", args.commit + "^{commit}")
    subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", before, commit], check=True
    )
    paths = sorted(
        set(git("diff", "--name-only", before, commit, "--", "backend/app/").splitlines())
    )
    if not paths:
        raise ValueError("No app changes: no deployment is needed for this commit range")
    if not all(valid_path(p) for p in paths):
        raise ValueError("Unsafe or unsupported app path")
    boundary_candidates = git(
        "diff",
        "--name-only",
        before,
        commit,
        "--",
        "Dockerfile",
        "*requirements*",
        "grocery_data",
        "deploy",
    ).splitlines()
    # The broad requirements glob also matches application modules such as
    # content_pack_requirements.py. They are reviewed app code, not dependency
    # manifests. The documented environment example is never installed by this
    # app-only flow; the active environment is preserved and checked at swap.
    boundary = [p for p in boundary_candidates
                if not (p.startswith("backend/app/") and p.endswith(".py"))
                and p != "deploy/.env.production.example"]
    if boundary:
        raise ValueError(
            "Dependencies/schema/compose changed: use a separately reviewed full release: "
            + "\n".join(boundary)
        )
    for path in paths:
        mode = git("ls-tree", commit, "--", path).split(" ", 1)[0]
        if mode not in ("100644", "100755"):
            raise ValueError("Deleted files and symlinks require a separate release: " + path)
    args.workdir.mkdir(parents=True, exist_ok=False)
    code = """import subprocess,json,base64
paths=PATHS
x=json.loads(subprocess.check_output(['docker','inspect','smako-app-1']))[0]
files={}
for p in paths:
 r=subprocess.run(['docker','exec','smako-app-1','python','-c',
  "from pathlib import Path;import sys;p=Path(sys.argv[1]);sys.stdout.buffer.write(p.read_bytes()) if p.is_file() else sys.exit(3)",'/srv/app/'+p],capture_output=True)
 if r.returncode not in (0,3): raise RuntimeError('Unable to read runtime file')
 files[p]=base64.b64encode(r.stdout).decode() if r.returncode==0 else None
print(json.dumps({'image':x['Image'],'files':files}))
""".replace("PATHS", repr(paths))
    live = json.loads(remote(args.host, code))
    files, hashes = {}, {}
    for path in paths:
        base = base64.b64decode(live["files"][path]) if live["files"][path] is not None else None
        old, new = blob(before, path), blob(commit, path)
        patched = transplant(base, old, new)
        if patched != new:
            raise ValueError(
                "Runtime differs from tested Git candidate; resolve explicitly: " + path
            )
        if patched == base:
            continue
        files[path] = patched
        hashes[path] = {"before": sha(base) if base is not None else None, "after": sha(patched)}
    if not files:
        raise ValueError("All selected app changes are already active")
    manifest = {
        "commit": commit,
        "from_commit": before,
        "base_image": live["image"],
        "files": hashes,
        "unresolved": [],
    }
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            archive.writestr(path, content)
        archive.writestr("PATCH-REVIEW.json", json.dumps(manifest, indent=2))
    archive = data.getvalue()
    release = "app-" + commit[:12] + "-" + sha(archive)[:8]
    config = {
        "release": release,
        "host": args.host,
        "review": manifest,
        "package_sha256": sha(archive),
    }
    (args.workdir / "candidate.zip").write_bytes(archive)
    (args.workdir / "review.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf8")
    print(
        json.dumps(
            {
                "status": "prepared",
                "release": release,
                "files": list(files),
                "review": str(args.workdir / "review.json"),
            },
            indent=2,
        )
    )


def execute(args):
    config = json.loads((args.workdir / "review.json").read_text(encoding="utf8"))
    if not re.fullmatch(r"app-[0-9a-f]{12}-[0-9a-f]{8}", config["release"]):
        raise ValueError("Invalid release identity")
    if not all(valid_path(p) for p in config["review"]["files"]):
        raise ValueError("Invalid manifest paths")
    if args.command == "build":
        data = (args.workdir / "candidate.zip").read_bytes()
        if sha(data) != config["package_sha256"]:
            raise ValueError("Package checksum changed")
        config["archive"] = base64.b64encode(data).decode()
    else:
        if not args.checks_passed:
            raise ValueError("Verify the built candidate first; see docs/BETA.md (--checks-passed)")
        config["expected_candidates"] = json.loads(
            (args.workdir / "build.json").read_text(encoding="utf8")
        )
    code = (
        "CONFIG="
        + repr(config)
        + "\n"
        + (WORKERS / (args.command + ".py")).read_text(encoding="utf8")
    )
    # Workers print stages as they happen. Keep their final JSON as the portable
    # release receipt; no credentials, compose environment or private rows leave the host.
    host = config["host"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@-]*", host):
        raise ValueError("Invalid SSH host")
    with subprocess.Popen(
        [
            "ssh",
            "-T",
            "-o",
            "BatchMode=yes",
            "-o",
            "ServerAliveInterval=15",
            host,
            "sudo -n python3 -u -",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf8",
    ) as process:
        process.stdin.write(code)
        process.stdin.close()
        last = None
        for line in process.stdout:
            row = json.loads(line)
            print(
                json.dumps(
                    {
                        k: v
                        for k, v in row.items()
                        if k in ("stage", "status", "at", "existing_state_preserved")
                    }
                ),
                flush=True,
            )
            last = row
        if process.wait() != 0:
            raise RuntimeError("Remote step failed; inspect server evidence before retrying")
    (args.workdir / (args.command + ".json")).write_text(
        json.dumps(last, indent=2) + "\n", encoding="utf8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare", help="Read active app and package Git changes; no deployment")
    prep.add_argument("--from-commit", required=True, help="Last deployed app source commit")
    prep.add_argument("--commit", default="main")
    prep.add_argument("--host", default="smako")
    prep.add_argument("--workdir", type=Path, required=True, help="New, empty output directory")
    for name in ("build", "activate"):
        command = sub.add_parser(name)
        command.add_argument("--workdir", type=Path, required=True)
        if name == "activate":
            command.add_argument(
                "--checks-passed",
                action="store_true",
                help="Candidate has passed the documented release checks",
            )
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    else:
        execute(args)


if __name__ == "__main__":
    main()
