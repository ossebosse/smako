"""Closed backup of verified alternative; observations and approved references unchanged."""
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path

P = Path('/work')
S = Path('/prior')
assert not (P/'grocery.sqlite').exists()
lock_path = production_refresh_lock_path(P/'grocery.sqlite', P/'price-universes', allow_missing_database=True)
# Both candidates normally mount their own data at /work; lock the source's same canonical key.
with RefreshRunLock(S/'price-universes/.refresh-locks'/lock_path.name):
    with RefreshRunLock(lock_path):
        for name in ['grocery.sqlite','plans.sqlite']:
            if (S/name).exists():
                with sqlite3.connect(f'file:{S/name}?mode=ro',uri=True) as src, sqlite3.connect(P/name) as dst:
                    src.backup(dst)
        for name in ['coop-municipal','citygross-municipal','lidl-municipal','willys-flyer','ica-structured','price-universes','raw']:
            shutil.copytree(S/name,P/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns(".refresh-locks"))
        for name in ['willys-config.json','policy.json']:
            shutil.copyfile(S/name,P/name)
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute("select sp.chain,sp.store_external_id,min(sp.fetched_at) observed,count(*) products from source_products sp join catalog_snapshots cs on cs.id=sp.catalog_snapshot_id where cs.is_active=1 and sp.fetched_at>='2026-09-27' group by sp.chain,sp.store_external_id")]
policy = json.loads((P/'policy.json').read_bytes())
assert policy['id'] == 'lund-own-five-base-20260928-v1'
for row in rows:
    row['age_hours'] = (datetime.now(UTC)-datetime.fromisoformat(row['observed'])).total_seconds()/3600
(P/'initialization.json').write_text(json.dumps({'created_at':datetime.now(UTC).isoformat(),
    'policy_sha256':hashlib.sha256((P/'policy.json').read_bytes()).hexdigest(), 'base':rows,
    'basis':'closed backup, private clone under existing source and destination operation locks',
    'source_observations_unchanged':True,'production_activation':False},indent=2))
print('private candidate cloned, original policy and source observations retained')
