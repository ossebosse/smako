"""Run on the server host: sanitized read-only inspection, no deployment actions."""

import json
import subprocess
from datetime import UTC, datetime


def command(*args, source=None):
    return subprocess.check_output(args, input=source, text=True)


names = ["smako-app-1", "smako-scheduler-1"]
containers = json.loads(command("docker", "inspect", *names))
safe_env = {
    "BUILD_ID",
    "OWN_SOURCES_ONLY",
    "PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS",
    "WILLYS_COLLECTION_LOCATION",
    "DEMAND_REFRESH_ENABLED",
    "DAILY_REFRESH_ENABLED",
    "COOP_RETRY_ENABLED",
    "MAX_PRICE_AGE_HOURS",
    "PRICE_AGE_WARNING_HOURS",
    "GROCERY_DATABASE_URL",
    "PLAN_STORE_PATH",
    "PRICE_UNIVERSE_CACHE_ROOT",
    "GROCERY_RAW_SNAPSHOT_ROOT",
    "SOURCE_RELAY_INBOX",
    "INTERNAL_APP_BASE_URL",
}
report = {"checked_utc": datetime.now(UTC).isoformat(), "read_only": True, "containers": []}
for item in containers:
    env = dict(v.split("=", 1) for v in item["Config"]["Env"] if "=" in v)
    report["containers"].append(
        {
            "name": item["Name"],
            "image": item["Image"],
            "state": item["State"]["Status"],
            "compose_files": item["Config"]["Labels"].get(
                "com.docker.compose.project.config_files"
            ),
            "environment": {k: env.get(k) for k in sorted(safe_env)},
            "mounts": [{k: m[k] for k in ["Source", "Destination", "RW"]} for m in item["Mounts"]],
        }
    )
cron = command("docker", "exec", "smako-scheduler-1", "cat", "/etc/cron.d/grocery-beta")
report["cron"] = [
    {"schedule": " ".join(line.split()[:5]), "script": line.split("deploy/scripts/")[1].split()[0]}
    for line in cron.splitlines()
    if "deploy/scripts/" in line
]
report["scheduler_processes"] = command(
    "docker", "top", "smako-scheduler-1", "-eo", "pid,etime,comm"
).splitlines()
probe = r"""
import hashlib,json,os,sqlite3,urllib.request,urllib.error
from pathlib import Path
root=Path(os.environ['PRICE_UNIVERSE_CACHE_ROOT'])
p=root/'active/city-lund.json'
out={'manifest_exists':p.exists(),'lock_files':[{'name':x.name,'bytes':x.stat().st_size} for x in (root/'.refresh-locks').glob('*')], 'lock_ownership_not_tested':True}
if p.exists():
    data=p.read_bytes(); m=json.loads(data)
    out['manifest_sha256']=hashlib.sha256(data).hexdigest()
    out['manifest']={k:m.get(k) for k in ['universe_id','artifact_sha256','oldest_base_observed_at','snapshot_ids']}
for route in ['ready','api/price-universe/status']:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/'+route,timeout=30) as response:
            j=json.load(response)
            out[route]={'http':response.status,**{k:j.get(k) for k in ['status','universe_id','raw_product_count','freshness','oldest_usable_price_age_hours']}}
    except urllib.error.HTTPError as e: out[route]={'http':e.code}
with sqlite3.connect(Path(os.environ['PLAN_STORE_PATH']).as_uri()+'?mode=ro',uri=True) as db:
    out['plan_revisions']=db.execute('SELECT count(*) FROM consumer_plan_revisions').fetchone()[0]
inbox=Path(os.environ['GROCERY_RAW_SNAPSHOT_ROOT'])/'source-inbox/willys'
out['old_inbox_artifacts']=[{'relative':str(p.relative_to(inbox)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(inbox.rglob('*.smako-source'))]
print(json.dumps(out))
"""
report["production"] = json.loads(
    command("docker", "exec", "-i", "smako-app-1", "python", "-", source=probe)
)
print(json.dumps(report, indent=2))
