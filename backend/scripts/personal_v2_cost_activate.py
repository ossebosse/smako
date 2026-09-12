"""App-only activation under the existing cross-process refresh/backup lock."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path("/opt/smako")
BUILD = "personal-v2-cost-fish-20260912"

ROLLBACK = "personal-v2-dinners-20260911c-rollback"
STATE = ROOT / "evidence" / f"{BUILD}-rollback-private.json"
ENV_BACKUP = ROOT / f"production.before-{BUILD}.env"


def run(command, **kwargs):
    return subprocess.check_output(command, **kwargs).decode().strip()


def inventory():
    code = """import hashlib,json,sqlite3
from app.config import get_settings
s=get_settings()
with sqlite3.connect(s.plan_store_path) as c:
 rows=c.execute('SELECT * FROM consumer_plan_revisions').fetchall()
 print(json.dumps({'integrity':c.execute('PRAGMA integrity_check').fetchone()[0], 'plan_hashes':sorted(hashlib.sha256(json.dumps(row).encode()).hexdigest() for row in rows), 'price_manifests':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (s.price_universe_cache_root/'active').glob('*.json')}}))
"""
    return json.loads(
        run(["docker", "exec", "-i", "smako-app-1", "python", "-"], input=code.encode())
    )


def activate_source(build, env):
    target = ROOT / "releases" / build
    assert target.is_dir() and target.resolve().is_relative_to(ROOT / "releases")
    for key, value in (("APP_VERSION", "0.1.0-smako-" + build), ("BUILD_ID", build)):
        env, count = re.subn(rf"(?m)^{key}=.*$", f"{key}={value}", env)
        assert count == 1
    candidate = ROOT / "production.gaps-next.env"
    metadata = (ROOT / "production.env").stat()
    with candidate.open("x") as out:
        candidate.chmod(0o600)
        out.write(env)
        out.flush()
        os.fsync(out.fileno())
    os.chown(candidate, metadata.st_uid, metadata.st_gid)
    candidate.chmod(metadata.st_mode & 0o777)
    os.replace(candidate, ROOT / "production.env")
    link = ROOT / "current-gaps-next"
    assert not link.exists() and not link.is_symlink()
    link.symlink_to(target)
    os.replace(link, ROOT / "current")
    subprocess.run([str(ROOT / "compose"), "config", "--quiet"], check=True)
    subprocess.run(
        [str(ROOT / "compose"), "up", "-d", "--no-build", "--no-deps", "--force-recreate", "app"],
        check=True,
    )
    for _ in range(45):
        try:
            with urllib.request.urlopen("https://beta.smako.nu/ready", timeout=3) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            time.sleep(1)
    raise RuntimeError("Readiness did not recover")


def main():
    mode = sys.argv[1]
    assert mode in {"activate", "rollback", "verify", "restart"}
    helper_code = """from pathlib import Path
import sys
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
lock=RefreshRunLock(production_refresh_lock_path(Path('/srv/app/var/grocery/grocery_data.sqlite'),Path('/srv/app/var/price_universes')))
lock.acquire()
try:
 print('LOCKED',flush=True)
 sys.stdin.readline()
finally:
 lock.release()
"""
    image = run(["docker", "inspect", "-f", "{{.Config.Image}}", "smako-app-1"])
    # A separate container holds the same lock inode while app is recreated.
    helper = subprocess.Popen(
        [
            "docker",
            "run",
            "--rm",
            "-i",
            "--network",
            "none",
            "--user",
            "0",
            "--volumes-from",
            "smako-app-1:ro",
            "-v",
            "/srv/smako/data/price_universes/.refresh-locks:/srv/app/var/price_universes/.refresh-locks:rw",
            "--entrypoint",
            "python",
            image,
            "-c",
            helper_code,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert helper.stdout.readline().strip() == "LOCKED", "Shared operation lock unavailable"
        before = inventory()
        assert before["integrity"] == "ok"
        scheduler = run(["docker", "inspect", "-f", "{{.Id}}", "smako-scheduler-1"])
        old_env = (ROOT / "production.env").read_text()
        if mode == "activate":
            assert not STATE.exists() and not ENV_BACKUP.exists()
            before.update(
                source=str((ROOT / "current").resolve()), scheduler_id=scheduler, image=image
            )
            STATE.write_text(json.dumps(before))
            STATE.chmod(0o600)
            ENV_BACKUP.write_text(old_env)
            ENV_BACKUP.chmod(0o600)
            try:
                activate_source(BUILD, old_env)
            except Exception:
                activate_source(ROLLBACK, old_env)
                raise
        elif mode == "rollback":
            activate_source(ROLLBACK, old_env)
        elif mode == "restart":
            activate_source(BUILD, old_env)
        after = inventory()
        original = json.loads(STATE.read_text())
        reference = before if mode in {"restart", "rollback"} else original
        assert set(reference["plan_hashes"]) <= set(after["plan_hashes"]), (
            "Historical revision changed"
        )
        assert before["price_manifests"] == after["price_manifests"]
        assert scheduler == run(["docker", "inspect", "-f", "{{.Id}}", "smako-scheduler-1"])
        assert after["integrity"] == "ok"
        summary = {
            "status": "VERIFIED",
            "source": str((ROOT / "current").resolve()),
            "image": run(["docker", "inspect", "-f", "{{.Image}}", "smako-app-1"]),
            "prior_plan_revisions_preserved": len(reference["plan_hashes"]),
            "current_plan_revisions": len(after["plan_hashes"]),
            "shared_operation_lock": True,
            "scheduler_unchanged": True,
            "price_manifests_unchanged_during_operation": True,
            "database_integrity": "ok",
        }
        (ROOT / "evidence" / f"{BUILD}-deployment.json").write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary))
    finally:
        if helper.poll() is None:
            helper.stdin.write("RELEASE\n")
            helper.stdin.flush()
        helper.wait(timeout=15)


if __name__ == "__main__":
    main()
