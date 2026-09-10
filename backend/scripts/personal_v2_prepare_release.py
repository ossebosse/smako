"""Prepare an overlay against the untouched baseline, never upload runtime data."""
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

root = Path.cwd()
baseline_commit = subprocess.check_output(["git", "rev-list", "--max-parents=0", "HEAD"], text=True).strip()
paths = set(subprocess.check_output(["git", "diff", baseline_commit, "--name-only"], text=True).splitlines())
paths.update(subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], text=True).splitlines())
paths = sorted(p for p in paths if p.startswith("backend/app/") or p in {
    "backend/requirements.txt", "deploy/requirements.txt", "deploy/compose.yaml",
    "deploy/scripts/backup_sqlite.py", "deploy/scripts/privacy_erasure_ledger.py",
})
manifest = []
target = root / "reports/private/personal-v2-overlay.tar.gz"
with tarfile.open(target, "w:gz") as archive:
    for name in paths:
        old = subprocess.run(["git", "show", f"{baseline_commit}:{name}"], capture_output=True, check=False)
        data = (root / name).read_bytes().replace(b"\r\n", b"\n")
        baseline = old.stdout.replace(b"\r\n", b"\n")
        if name == "deploy/compose.yaml":
            # Reviewed pre-existing VPS TLS setting: preserve it in the overlay.
            remote = (root / "reports/private/remote-compose.yaml").read_bytes().replace(b"\r\n", b"\n")
            original, retained = b"${ACME_EMAIL:?set ACME_EMAIL in deploy/.env.production}", b"${ACME_EMAIL:-}"
            assert remote == baseline.replace(original, retained)
            baseline, data = remote, data.replace(original, retained)
        manifest.append({"path": name, "baseline": hashlib.sha256(baseline).hexdigest() if old.returncode == 0 else None, "sha256": hashlib.sha256(data).hexdigest()})
        info = tarfile.TarInfo(name)
        info.size, info.mode = len(data), 0o644
        archive.addfile(info, io.BytesIO(data))
    data = json.dumps(manifest, indent=2).encode()
    info = tarfile.TarInfo("overlay-manifest.json")
    info.size, info.mode = len(data), 0o644
    archive.addfile(info, io.BytesIO(data))
print(json.dumps({"files": len(manifest), "archive": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}))
