"""App-only activation worker, invoked by scripts/beta_release.py.

Derived from the verified 2026-10-16 app activation. CONFIG is supplied by the
local CLI; this file must not be invoked by itself. Holds the existing refresh
lock across backup and swap, verifies state, and rolls back the wrapper/image
on post-swap failure without restoring databases.
"""

CONFIG = globals().get("CONFIG")
if not isinstance(CONFIG, dict):
    raise SystemExit("Use scripts/beta_release.py activate; see docs/BETA.md")
import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def run(args, **kw):
    return subprocess.check_output(args, text=True, **kw).strip()


def inspect(name):
    return json.loads(run(["docker", "inspect", name]))[0]


def save(path, data):
    path.write_text(json.dumps(data, indent=2))
    path.chmod(0o600)


def lock(image):
    code = "from pathlib import Path;from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path;import sys;lock=RefreshRunLock(production_refresh_lock_path(Path('/srv/app/var/grocery/grocery_data.sqlite'),Path('/srv/app/var/price_universes')));lock.acquire();print('LOCKED',flush=True);sys.stdin.readline();lock.release()"
    p = subprocess.Popen(
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
            code,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.stdout.readline().strip() != "LOCKED":
        _, error = p.communicate(timeout=30)
        if "RefreshAlreadyRunningError" in error:
            raise RuntimeError("Operations lease busy; no activation")
        raise RuntimeError("Operations lease helper failed: " + error[-1800:])
    return p


def app_probe(code):
    return json.loads(run(["docker", "exec", "-i", "smako-app-1", "python", "-"], input=code))


def table_hashes(path):
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        result = {}
        for (t,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ):
            quoted = '"' + t.replace('"', '""') + '"'
            result[t] = sorted(
                hashlib.sha256(json.dumps(row, default=str).encode()).hexdigest()
                for row in db.execute("SELECT * FROM " + quoted)
            )
        return result


def atomic_wrapper(data):
    temp = ROOT / ("compose." + CONFIG["release"] + ".next")
    with temp.open("xb") as f:
        os.chmod(temp, old_mode)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, wrapper)


quietcode = """import os,json,sqlite3;from pathlib import Path;from datetime import datetime,UTC,timedelta;from sqlalchemy.engine import make_url
with sqlite3.connect(Path(make_url(os.environ['GROCERY_DATABASE_URL']).database).as_uri()+'?mode=ro',uri=True) as db:
 count=db.execute("SELECT count(*) FROM beta_request_metrics WHERE created_at>=? AND (endpoint LIKE '/api/plan%' OR endpoint LIKE '/api/personal/plans%')",((datetime.now(UTC)-timedelta(minutes=2)).isoformat(),)).fetchone()[0]
print(json.dumps({'recent_plan_requests':count}))
"""

ROOT = Path("/opt/smako")
E = ROOT / "evidence" / CONFIG["release"]
candidates = json.loads((E / "candidates.json").read_bytes())
assert candidates == CONFIG["expected_candidates"], "Candidate changed since local verification"
assert set(candidates) == {"app"}
assert not (E / "activation-success.json").exists(), (
    "Already activated; verify current status instead"
)
assert shutil.disk_usage(E).free > 8_000_000_000
originals = {role: inspect("smako-" + role + "-1") for role in candidates}
for role, c in candidates.items():
    assert originals[role]["Image"] == c["base_image"], (role, "base changed")
    assert c["only_reviewed_files_changed"]
others = {
    n: inspect(n)["Id"]
    for n in run(["docker", "ps", "--format", "{{.Names}}"]).splitlines()
    if n != "smako-app-1"
}
app = originals["app"]
wrapper = ROOT / "compose"
old = wrapper.read_bytes()
old_mode = wrapper.stat().st_mode & 0o777
assert old.count(b'"$@"') == 1
before = json.loads(run([str(wrapper), "--profile", "ops", "config", "--format", "json"]))
save(E / "compose-before.private.json", before)
(E / "compose-wrapper.before").write_bytes(old)
(E / "compose-wrapper.before").chmod(0o600)
override = ROOT / "overrides" / (CONFIG["release"] + ".json")
override_value = {
    "services": {
        role: {"image": c["image"], "environment": {"BUILD_ID": c["build_id"]}}
        for role, c in candidates.items()
    }
}
if override.exists():
    assert json.loads(override.read_bytes()) == override_value
else:
    save(override, override_value)
after = json.loads(
    run([str(wrapper), "-f", str(override), "--profile", "ops", "config", "--format", "json"])
)
expected = copy.deepcopy(before)
for role, c in candidates.items():
    expected["services"][role]["image"] = c["image"]
    expected["services"][role]["environment"]["BUILD_ID"] = c["build_id"]
assert after == expected, "Unexpected compose diff"
save(E / "compose-after.private.json", after)
helper = lock(app["Image"])
try:
    print(json.dumps({"stage": "operation_lock_acquired"}), flush=True)
    assert app_probe(quietcode)["recent_plan_requests"] == 0, (
        "Recent plan traffic; activation deferred"
    )
    stat = Path("/proc") / str(app["State"]["Pid"]) / "stat"

    def ticks():
        fields = stat.read_text().split()
        return int(fields[13]) + int(fields[14])

    cpu = []
    for _ in range(24):
        first = ticks()
        time.sleep(10)
        used = (ticks() - first) / os.sysconf("SC_CLK_TCK")
        cpu = cpu + [used] if used < 0.2 else []
        if len(cpu) == 2:
            break
    else:
        raise RuntimeError("Planner CPU active; no activation")
    mounts = {m["Destination"]: m["Source"] for m in app["Mounts"]}
    env = dict(v.split("=", 1) for v in app["Config"]["Env"])
    source = Path(mounts["/srv/app/var/plans"]) / Path(env["PLAN_STORE_PATH"]).name
    grocery = Path(mounts["/srv/app/var/grocery"]) / "grocery_data.sqlite"
    backup = E / ("backup-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    backup.mkdir(mode=0o700)
    for srcpath, name in [(source, "plans.sqlite3"), (grocery, "grocery.sqlite")]:
        dest = backup / name
        with (
            sqlite3.connect(srcpath.as_uri() + "?mode=ro", uri=True) as src,
            sqlite3.connect(dest) as dst,
        ):
            src.backup(dst)
            assert dst.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            assert dst.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
        dest.chmod(0o600)
    original = table_hashes(backup / "plans.sqlite3")
    save(backup / "table-hashes.private.json", original)
    price_root = Path(mounts["/srv/app/var/price_universes"]) / "active"

    def price_hashes():
        return {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in price_root.glob("*.json")
        }

    prices = price_hashes()
    save(E / "price-manifests-before.json", prices)
    assert app_probe(quietcode)["recent_plan_requests"] == 0, "Plan traffic started during backup"
    assert wrapper.read_bytes() == old
    for role, item in originals.items():
        assert inspect("smako-" + role + "-1")["Id"] == item["Id"]
    new = old.replace(b'"$@"', ("-f " + str(override) + ' "$@"').encode())
    atomic_wrapper(new)
    try:
        assert (
            json.loads(run([str(wrapper), "--profile", "ops", "config", "--format", "json"]))
            == after
        )
        run(
            [
                str(wrapper),
                "up",
                "-d",
                "--no-deps",
                "--no-build",
                "--pull",
                "never",
                "--timeout",
                "900",
                "app",
            ],
            stderr=subprocess.PIPE,
        )
        print(json.dumps({"stage": "app_replaced"}), flush=True)
        ready = {}
        for city, postal in [("Lund", "22350"), ("Malmo", "21120")]:
            for _ in range(240):
                try:
                    with urllib.request.urlopen(
                        "https://beta.smako.nu/ready?postal_code=" + postal, timeout=10
                    ) as response:
                        body = json.load(response)
                    if (
                        body.get("build_id") == candidates["app"]["build_id"]
                        and body.get("status") == "ready"
                    ):
                        ready[city] = body
                        break
                except (OSError, TimeoutError):
                    pass
                time.sleep(1)
            else:
                raise RuntimeError(city + " readiness failed")
        for role, c in candidates.items():
            active = inspect("smako-" + role + "-1")
            assert (
                active["Image"] == c["image"]
                and active["State"]["Running"]
                and not active["State"]["OOMKilled"]
            )
            assert active["Mounts"] == originals[role]["Mounts"]
            expected_env = dict(v.split("=", 1) for v in originals[role]["Config"]["Env"])
            expected_env["BUILD_ID"] = c["build_id"]
            assert dict(v.split("=", 1) for v in active["Config"]["Env"]) == expected_env, (
                role,
                "environment changed beyond build",
            )
        assert all(inspect(n)["Id"] == i for n, i in others.items())
        updated = table_hashes(source)
        for table, hashes in original.items():
            assert not (Counter(hashes) - Counter(updated.get(table, []))), (
                "Prior rows changed",
                table,
            )
        assert price_hashes() == prices
    except Exception:
        atomic_wrapper(old)
        run(
            [
                str(wrapper),
                "up",
                "-d",
                "--no-deps",
                "--no-build",
                "--pull",
                "never",
                "--timeout",
                "900",
                "app",
            ],
            stderr=subprocess.PIPE,
        )
        raise
    report = {
        "status": "activated",
        "at": datetime.now(UTC).isoformat(),
        "runtimes": {
            role: {k: c[k] for k in ["image", "base_image", "build_id"]}
            for role, c in candidates.items()
        },
        "readiness": ready,
        "only_app_replaced": True,
        "existing_state_preserved": {t: len(rows) for t, rows in original.items()},
        "price_manifests_preserved": True,
        "mounts_preserved": True,
        "only_environment_change": "BUILD_ID",
        "cpu_quiet_samples": cpu,
        "backup": str(backup),
        "operation_lock": True,
    }
    save(E / "activation-success.json", report)
    print(json.dumps(report), flush=True)
finally:
    helper.stdin.close()
    helper.wait(timeout=30)
