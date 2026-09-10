"""Run on VPS: verify baseline and stage a separate source release only."""
import hashlib
import json
import shutil
import sys
import tarfile
from pathlib import Path

current = Path("/opt/smako/current").resolve(strict=True)
release = sys.argv[1] if len(sys.argv) > 1 else "personal-v2-20260910"
assert release in {"personal-v2-20260910", "personal-v2-20260910b"}
target = Path("/opt/smako/releases") / release
archive_path = Path("/opt/smako/evidence") / ("personal-v2-overlay.tar.gz" if release.endswith("10") else "personal-v2-polish.tar.gz")
assert current.is_relative_to("/opt/smako/releases")
assert not target.exists(), "Release directory already exists; do not overwrite"
with tarfile.open(archive_path) as archive:
    manifest = json.load(archive.extractfile("overlay-manifest.json"))
    for item in manifest:
        path = current / item["path"]
        assert path.resolve().is_relative_to(current)
        actual = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest() if path.exists() else None
        assert actual == item["baseline"], f"Production baseline differs: {item['path']}"
        data = archive.extractfile(item["path"]).read()
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
    shutil.copytree(current, target, ignore=shutil.ignore_patterns("__pycache__", ".env", ".env.production", "reports", ".pytest_cache", ".ruff_cache"))
    for item in manifest:
        destination = target / item["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(archive.extractfile(item["path"]).read())
    (target / "overlay-manifest.json").write_text(json.dumps(manifest, indent=2))
print(json.dumps({"status": "STAGED_BASELINE_MATCHED", "files": len(manifest), "previous": str(current), "release": str(target)}))
