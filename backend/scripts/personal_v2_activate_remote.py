"""App-only VPS activation with retained rollback; never restore/delete data."""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("/opt/smako")
BUILD = sys.argv[2] if len(sys.argv) > 2 else "personal-v2-20260910"
assert re.fullmatch(r"personal-v2-20260910[bc]?", BUILD)
TARGET = ROOT / "releases" / BUILD
EVIDENCE = ROOT / "evidence"
VERSION = "0.1.0-smako-" + BUILD
STATE = EVIDENCE / ("personal-v2-rollback-private.json" if BUILD == "personal-v2-20260910" else f"{BUILD}-rollback-private.json")
ENV_BACKUP = ROOT / ("production.before-personal-v2.env" if BUILD == "personal-v2-20260910" else f"production.before-{BUILD}.env")


def run(command, **kwargs):
    return subprocess.check_output(command, **kwargs).decode().strip()


def inventory():
    code = '''
import hashlib,json,sqlite3
from app.config import get_settings
s=get_settings()
with sqlite3.connect(s.plan_store_path) as c:
 rows=c.execute('SELECT * FROM consumer_plan_revisions').fetchall()
 print(json.dumps({'integrity':c.execute('PRAGMA integrity_check').fetchone()[0], 'plan_hashes':sorted(hashlib.sha256(json.dumps(row).encode()).hexdigest() for row in rows), 'price_manifests':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (s.price_universe_cache_root/'active').glob('*.json')}}))
'''
    return json.loads(run(["docker", "exec", "-i", "smako-app-1", "python", "-"], input=code.encode()))


def switch(path):
    assert path.resolve().is_relative_to(ROOT / "releases")
    temporary = ROOT / "current-personal-v2-next"
    assert not temporary.exists() and not temporary.is_symlink()
    temporary.symlink_to(path)
    os.replace(temporary, ROOT / "current")


def start():
    subprocess.run([str(ROOT / "compose"), "config", "--quiet"], check=True)
    subprocess.run([str(ROOT / "compose"), "up", "-d", "--no-build", "--no-deps", "--force-recreate", "app"], check=True)
    for _ in range(30):
        try:
            with urllib.request.urlopen("https://beta.smako.nu/ready", timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(1)
    raise RuntimeError("Readiness did not recover")


if sys.argv[1] == "activate":
    assert TARGET.is_dir() and not STATE.exists() and not ENV_BACKUP.exists()
    before = inventory()
    assert before["integrity"] == "ok"
    before["source"] = str((ROOT / "current").resolve(strict=True))
    before["scheduler_id"] = run(["docker", "inspect", "-f", "{{.Id}}", "smako-scheduler-1"])
    before["app_image"] = run(["docker", "inspect", "-f", "{{.Config.Image}}", "smako-app-1"])
    STATE.write_text(json.dumps(before))
    STATE.chmod(0o600)
    old = (ROOT / "production.env").read_bytes()
    ENV_BACKUP.write_bytes(old)
    ENV_BACKUP.chmod(0o600)
    updated = old.decode()
    for key, value in (("APP_VERSION", VERSION), ("BUILD_ID", BUILD)):
        updated, count = re.subn(rf"(?m)^{key}=.*$", f"{key}={value}", updated)
        assert count == 1
    candidate = ROOT / "production.personal-v2-next.env"
    candidate.write_text(updated)
    candidate.chmod(0o600)
    os.replace(candidate, ROOT / "production.env")
    switch(TARGET)
    try:
        start()
    except Exception:
        (ROOT / "production.env").write_bytes(old)
        switch(Path(before["source"]))
        start()
        raise
elif sys.argv[1] == "rollback":
    before = json.loads(STATE.read_text())
    (ROOT / "production.env").write_bytes(ENV_BACKUP.read_bytes())
    switch(Path(before["source"]))
    start()
elif sys.argv[1] != "verify":
    raise ValueError("Use activate, verify or rollback")

before = json.loads(STATE.read_text())
after = inventory()
assert set(before["plan_hashes"]) <= set(after["plan_hashes"]), "Prior plan revision changed"
assert before["price_manifests"] == after["price_manifests"], "Source activation changed; inspect independently"
assert before["scheduler_id"] == run(["docker", "inspect", "-f", "{{.Id}}", "smako-scheduler-1"])
assert after["integrity"] == "ok"
summary = {"status": "VERIFIED", "source": str((ROOT / "current").resolve()), "image": run(["docker", "inspect", "-f", "{{.Image}}", "smako-app-1"]), "prior_plan_revisions_preserved": len(before["plan_hashes"]), "current_plan_revisions": len(after["plan_hashes"]), "scheduler_unchanged": True, "price_manifests_unchanged": True, "database_integrity": after["integrity"]}
(EVIDENCE / "personal-v2-deployment.json").write_text(json.dumps(summary, indent=2))
print(json.dumps(summary))
