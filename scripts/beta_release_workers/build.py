"""Build a reviewed app patch on the pinned active beta image; never activate."""

import base64
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

CONFIG = globals().get("CONFIG")
if not isinstance(CONFIG, dict):
    raise SystemExit("Use scripts/beta_release.py build; see docs/BETA.md")


def run(args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def hashes(image):
    code = "import hashlib,json;from pathlib import Path;r=Path('/srv/app');print(json.dumps({str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for d in ['backend','grocery_data','deploy'] for p in (r/d).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}))"
    return json.loads(
        run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--entrypoint",
                "python",
                image,
                "-c",
                code,
            ]
        )
    )


release = CONFIG["release"]
evidence = Path("/opt/smako/evidence") / release
evidence.mkdir(mode=0o700, exist_ok=False)
review = CONFIG["review"]
active = json.loads(run(["docker", "inspect", "smako-app-1"]))[0]
assert active["Image"] == review["base_image"], "Active image changed; prepare again"
assert review["files"] and not review["unresolved"]
data = base64.b64decode(CONFIG["archive"])
assert hashlib.sha256(data).hexdigest() == CONFIG["package_sha256"]
(evidence / "candidate.zip").write_bytes(data)
directory = evidence / "build"
directory.mkdir(mode=0o700)
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    assert set(archive.namelist()) == set(review["files"]) | {"PATCH-REVIEW.json"}
    assert all(
        not PurePosixPath(n).is_absolute() and ".." not in PurePosixPath(n).parts
        for n in archive.namelist()
    )
    archive.extractall(directory)
for path, entry in review["files"].items():
    assert hashlib.sha256((directory / path).read_bytes()).hexdigest() == entry["after"]
assert json.loads((directory / "PATCH-REVIEW.json").read_bytes()) == review
base, tag = "smako-app-base:" + release, "smako-app:" + release
base_config = json.loads(run(["docker", "image", "inspect", review["base_image"]]))[0]["Config"]
expected_config = globals()["final_image_config"](
    base_config, release=release, commit=review["commit"], base_image=review["base_image"])
flatten = globals()["flatten_instructions"](expected_config)
run(["docker", "tag", review["base_image"], base])
verifier = "import hashlib,json,sys;from pathlib import Path;m=json.loads(Path('/tmp/PATCH-REVIEW.json').read_bytes());assert all((hashlib.sha256((Path('/srv/app')/p).read_bytes()).hexdigest() if (Path('/srv/app')/p).exists() else None)==e[sys.argv[1]] for p,e in m['files'].items())\n"
(directory / "verify.py").write_text(verifier)
(directory / "Dockerfile").write_text(
    "FROM "
    + base
    + " AS patched\nUSER root\nCOPY PATCH-REVIEW.json verify.py /tmp/\nRUN python /tmp/verify.py before\n"
    + "".join("COPY --chown=app:app " + p + " /srv/app/" + p + "\n" for p in review["files"])
    + "RUN python /tmp/verify.py after\nRUN python -m compileall -q /srv/app/backend\n"
    + flatten
)
with (evidence / "build.log").open("w") as out:
    subprocess.run(
        ["docker", "build", "--network=none", "--pull=false", "-t", tag, str(directory)],
        stdout=out,
        stderr=subprocess.STDOUT,
        check=True,
    )
image = run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"])
actual_config = json.loads(run(["docker", "image", "inspect", image]))[0]["Config"]
assert actual_config == expected_config, "Flattening changed runtime configuration"
before, after = hashes(review["base_image"]), hashes(image)
changed = {p for p in set(before) | set(after) if before.get(p) != after.get(p)}
assert changed == set(review["files"]), "Unexpected runtime changes"
assert all(after[p] == v["after"] for p, v in review["files"].items())
result = {
    "app": {
        "image": image,
        "base_image": review["base_image"],
        "build_id": release,
        "tag": tag,
        "commit": review["commit"],
        "files": review["files"],
        "package_sha256": CONFIG["package_sha256"],
        "only_reviewed_files_changed": True,
        "unchanged_runtime_files": len(after) - len(changed),
        "flattened_runtime_configuration_verified": True,
    }
}
(evidence / "candidates.json").write_text(json.dumps(result, indent=2))
# The temporary base alias is not a second rollback registry.
run(["docker", "image", "rm", base])
retention = globals()["maintain_images"](run, protected={image, review["base_image"]})
(evidence / "image-retention.json").write_text(json.dumps(retention, indent=2))
print(json.dumps({"stage": "image_verified", "changed_files": len(changed)}), flush=True)
print(json.dumps(result), flush=True)
