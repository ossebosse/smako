"""VPS isolated backup rehearsal: never overwrites active databases."""
import json
import subprocess
from pathlib import Path

BUILD = "personal-v2-gaps-20260911"
IMAGE = "billigaste-veckomenyn:0.1.0-smako-" + BUILD
target = Path("/srv/smako/restore") / BUILD
assert target.parent.resolve() == Path("/srv/smako/restore")
assert not target.exists(), "Exact isolated target already exists; do not overwrite"
target.mkdir(mode=0o700)
code = '''from pathlib import Path
from deploy.scripts.privacy_erasure_ledger import export_deletion_ledger
export_deletion_ledger(Path('/srv/app/var/grocery/grocery_data.sqlite'),Path('/backups/privacy-ledgers/personal-v2-gaps-20260911.json'))
print('CURRENT_LEDGER_EXPORTED')
'''
subprocess.run(["docker", "run", "--rm", "--network", "none", "--user", "0", "--volumes-from", "smako-app-1:ro", "-v", "/srv/smako/backups:/backups:rw", "--entrypoint", "python", IMAGE, "-c", code], check=True)
result = subprocess.check_output(["docker", "run", "--rm", "--network", "none", "--user", "0", "-v", "/srv/smako/backups:/backups:ro", "-v", f"{target}:/restore:rw", "-e", "GROCERY_DATABASE_URL=sqlite+pysqlite:////restore/grocery/grocery_data.sqlite", "-e", "PLAN_STORE_PATH=/restore/plans/plans.sqlite3", "-e", "PRICE_UNIVERSE_CACHE_ROOT=/restore/price_universes", "--entrypoint", "python", IMAGE, "deploy/scripts/restore_sqlite.py", "--bundle", "/backups/20260911T084740Z", "--confirm", "--deletion-ledger", "/backups/privacy-ledgers/personal-v2-gaps-20260911.json"])
(Path("/opt/smako/evidence") / "personal-v2-gaps-restore.json").write_bytes(result)
print(json.dumps({"status": "RESTORED_AND_VERIFIED", "bundle": "20260911T084740Z", "isolated_target": str(target)}))
