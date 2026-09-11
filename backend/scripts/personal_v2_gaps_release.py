"""Audited source overlay and read-compatible emergency rollback (no data restore)."""
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

BUILD = "personal-v2-gaps-20260911"
BASELINE = "63dbca6"
BASE_IMAGE = "billigaste-veckomenyn:0.1.0-smako-personal-v2-20260910c"


def digest(data):
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def package():
    paths = set(subprocess.check_output(["git", "diff", BASELINE, "--name-only"], text=True).splitlines())
    paths.update(subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], text=True).splitlines())
    paths = sorted(p for p in paths if p.startswith("backend/app/") or p == "deploy/compose.yaml")
    target = Path(f"reports/private/{BUILD}.tar.gz")
    manifest = []
    with tarfile.open(target, "w:gz") as archive:
        for name in paths:
            old = subprocess.run(["git", "show", f"{BASELINE}:{name}"], capture_output=True, check=False)
            baseline = old.stdout.replace(b"\r\n", b"\n")
            data = Path(name).read_bytes().replace(b"\r\n", b"\n")
            if name == "deploy/compose.yaml":
                original, retained = b"${ACME_EMAIL:?set ACME_EMAIL in deploy/.env.production}", b"${ACME_EMAIL:-}"
                remote = Path("reports/private/gaps-remote-compose.yaml").read_bytes().replace(b"\r\n", b"\n")
                assert remote == baseline.replace(original, retained)
                baseline, data = remote, data.replace(original, retained)
            manifest.append({"path": name, "baseline": digest(baseline) if old.returncode == 0 else None, "sha256": digest(data)})
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), 0o644
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo("overlay-manifest.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    print(json.dumps({"files": len(manifest), "archive": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}))


def stage():
    root = Path("/opt/smako")
    current = (root / "current").resolve(strict=True)
    assert current == root / "releases/personal-v2-20260910c"
    target = root / "releases" / BUILD
    rollback = root / "releases" / f"{BUILD}-rollback"
    assert not target.exists() and not rollback.exists()
    with tarfile.open(root / "evidence" / f"{BUILD}.tar.gz") as archive:
        manifest = json.load(archive.extractfile("overlay-manifest.json"))
        for item in manifest:
            path = current / item["path"]
            assert path.resolve().is_relative_to(current)
            assert (digest(path.read_bytes()) if path.exists() else None) == item["baseline"], item["path"]
            assert digest(archive.extractfile(item["path"]).read()) == item["sha256"]
        ignore = shutil.ignore_patterns("__pycache__", ".env*", "reports", ".pytest_cache", ".ruff_cache")
        shutil.copytree(current, target, ignore=ignore)
        shutil.copytree(current, rollback, ignore=ignore)
        for item in manifest:
            path = target / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(item["path"]).read())
        (target / "overlay-manifest.json").write_text(json.dumps(manifest, indent=2))
    # Baseline engine plus forward-compatible data models. All planning/personal
    # writes are blocked during emergency rollback; deletion remains available.
    for name in ("personal.py", "basket.py", "product.py"):
        shutil.copyfile(target / "backend/app/models" / name, rollback / "backend/app/models" / name)
    main = rollback / "backend/app/main.py"
    main.write_text(main.read_text() + '''

@app.middleware("http")
async def rollback_personal_guard(request, call_next):
    if request.method not in {"GET", "HEAD", "OPTIONS", "DELETE"} and request.url.path.startswith(("/api/personal", "/api/plans", "/api/account")):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Tillfälligt läsläge efter återställning. Planer, skafferi och inköpshistorik är bevarade.", "code": "READ_ONLY_ROLLBACK"}, status_code=503)
    return await call_next(request)
''')
    page = rollback / "backend/app/static/personal.html"
    page.write_text('''<!doctype html><html lang="sv"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Smako – tillfälligt läsläge</title><link rel="stylesheet" href="/static/styles.css"><main style="max-width:700px;margin:auto;padding:24px"><h1>Smako – tillfälligt läsläge</h1><p>Planeringens uppdatering har återställts. Dina planer, skafferi och bokförda inköp är bevarade. Ändringar är tillfälligt spärrade.</p><div id="saved"></div><a href="/">Till Smako</a></main><script src="/static/personal-rollback.js"></script></html>''')
    (rollback / "backend/app/static/personal-rollback.js").write_text('''"use strict";
(async()=>{const out=document.getElementById('saved');const id=new URLSearchParams(location.hash.slice(1)).get('plan');if(!id)return;const r=await fetch('/api/plans/'+encodeURIComponent(id),{cache:'no-store'});if(!r.ok)return;const s=await r.json();const p=document.createElement('p');p.textContent='Sparad revision '+s.revision+' · '+s.plan.optimized_basket.total.toLocaleString('sv-SE')+' kr i beräknat inköp';out.append(p);for(const recipe of s.plan.recipes){const h=document.createElement('h2');h.textContent=recipe.name;out.append(h);}})();''')
    for directory, build in ((target, BUILD), (rollback, f"{BUILD}-rollback")):
        # Reuse the already deployed immutable dependency layer. No install,
        # provider collection, source mutation or runtime upload is needed.
        dockerfile = directory / "Dockerfile.gaps"
        dockerfile.write_text(f"FROM {BASE_IMAGE}\nENV APP_VERSION=0.1.0-smako-{build} BUILD_ID={build}\nCOPY --chown=app:app backend/app /srv/app/backend/app\n")
        subprocess.run(["docker", "build", "-f", str(dockerfile), "-t", f"billigaste-veckomenyn:0.1.0-smako-{build}", str(directory)], check=True)
    print(json.dumps({"status": "STAGED", "files": len(manifest), "build": BUILD, "rollback": rollback.name}))


if __name__ == "__main__":
    {"package": package, "stage": stage}[sys.argv[1]]()
