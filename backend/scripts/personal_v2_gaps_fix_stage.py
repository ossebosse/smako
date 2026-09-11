"""Stage the proven database-URL adapter correction over the verified A release."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

root = Path("/opt/smako")
bounds = len(sys.argv) > 1 and sys.argv[1] == "bounds"
prior = "personal-v2-gaps-20260911b" if bounds else "personal-v2-gaps-20260911"
build = "personal-v2-gaps-20260911c" if bounds else "personal-v2-gaps-20260911b"
current = (root / "current").resolve(strict=True)
assert current == root / "releases" / prior
target = root / "releases" / build
assert not target.exists()
name = "backend/app/services/basket_calculator.py" if bounds else "backend/app/services/personal_source_facts.py"
manifest = json.loads((current / "overlay-manifest.json").read_text())
assert hashlib.sha256((current / name).read_bytes()).hexdigest() == next(r["sha256"] for r in manifest if r["path"] == name)
shutil.copytree(current, target, ignore=shutil.ignore_patterns("__pycache__", ".env*", "reports"))
shutil.copyfile(root / "evidence" / ("basket_calculator_bounded.py" if bounds else "personal_source_facts_fixed.py"), target / name)
dockerfile = target / "Dockerfile.gaps"
dockerfile.write_text(f"FROM billigaste-veckomenyn:0.1.0-smako-{prior}\nENV APP_VERSION=0.1.0-smako-{build} BUILD_ID={build}\nCOPY --chown=app:app {name} /srv/app/{name}\n")
subprocess.run(["docker", "build", "-f", str(dockerfile), "-t", "billigaste-veckomenyn:0.1.0-smako-"+build, str(target)], check=True)
(target / "adapter-fix-manifest.json").write_text(json.dumps({"path": name, "sha256": hashlib.sha256((target/name).read_bytes()).hexdigest()}, indent=2))
print("STAGED_ADAPTER_URL_FIX")
