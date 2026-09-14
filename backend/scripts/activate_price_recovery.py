"""Activate the reviewed image under the existing host-side operation lock."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

BUILD = "price-recovery-lund-20260914a"
ROOT = Path("/opt/smako")
OUT = ROOT / "evidence/recovery-22350"
LOCK = Path("/srv/smako/data/price_universes/.refresh-locks/") / (
    "daily-refresh-53942fec0d5547bd77bbe01a491ca6b7e25efb571f4f8f611496a5f8a8d28904.lock"
)
REQUIRED = (
    "context:coop:23eaae11c9661e68,context:hemkop:3288e04edd97e349,"
    "context:ica:46850f1523580803,context:ica:979e70ce1f577bc4,"
    "context:willys:383650ec6ff5a636,context:willys:4a671428fc484e43"
)


def replace_file(path, data, original_stat):
    temp = path.with_name(path.name + ".recovery-tmp")
    with temp.open("xb") as handle:
        os.chmod(temp, original_stat.st_mode & 0o777)
        os.chown(temp, original_stat.st_uid, original_stat.st_gid)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def link(target):
    temp = ROOT / "current.recovery-tmp"
    temp.symlink_to(target)
    os.replace(temp, ROOT / "current")


with LOCK.open("r+b") as handle:
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    previous = (ROOT / "current").resolve(strict=True)
    assert previous.name == "personal-v2-fast-403020-20260913c"
    target = ROOT / "releases" / BUILD
    assert target.is_dir()
    env = ROOT / "production.env"
    original = env.read_bytes()
    metadata = env.stat()
    backup = OUT / "production.env.before"
    assert not backup.exists()
    shutil.copy2(env, backup)
    os.chmod(backup, 0o600)
    changes = {
        "APP_VERSION": "0.1.0-smako-" + BUILD,
        "BUILD_ID": BUILD,
        "PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS": REQUIRED,
    }
    lines = original.decode().splitlines()
    lines = [line for line in lines if line.partition("=")[0] not in changes]
    lines.extend(key + "=" + value for key, value in changes.items())
    replace_file(env, ("\n".join(lines) + "\n").encode(), metadata)
    caddy_hash = hashlib.sha256((previous / "deploy/Caddyfile").read_bytes()).hexdigest()
    assert hashlib.sha256((target / "deploy/Caddyfile").read_bytes()).hexdigest() == caddy_hash
    link(target)
    try:
        subprocess.run([str(ROOT / "compose"), "up", "-d", "--no-deps", "app", "scheduler"], check=True)
        deadline = time.monotonic() + 150
        ready = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen("https://beta.smako.nu/ready", timeout=10) as response:
                    ready = json.load(response)
                if ready.get("build_id") == BUILD and ready["price_universe"].get("required_contexts_usable"):
                    break
            except (OSError, ValueError):
                pass
            time.sleep(2)
        else:
            raise RuntimeError("new release did not become ready with all required contexts")
    except BaseException:
        replace_file(env, original, metadata)
        link(previous)
        subprocess.run([str(ROOT / "compose"), "up", "-d", "--no-deps", "app"], check=True)
        # Scheduler is restored to its exact pre-recovery image, independently
        # of the application's later release number.
        rollback = OUT / "scheduler-rollback.yaml"
        rollback.write_text("services:\n  scheduler:\n    image: billigaste-veckomenyn:0.1.0-smako-ica-quality-20260909\n")
        subprocess.run(["docker", "compose", "-p", "smako", "-f", str(previous / "deploy/compose.yaml"),
                        "-f", str(ROOT / "compose.vps.yaml"), "-f", str(rollback), "--env-file", str(env),
                        "up", "-d", "--no-deps", "scheduler"], check=True)
        raise
    result = {"release": BUILD, "ready": ready, "caddy_unchanged": True,
              "env_mode_preserved": (env.stat().st_mode & 0o777) == (metadata.st_mode & 0o777)}
    (OUT / "deployment.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
