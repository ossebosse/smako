import json,sqlite3,shutil,hashlib
from pathlib import Path
from datetime import datetime,UTC
P=Path('/work');S=Path('/prior')
assert not (P/'grocery.sqlite').exists()
with sqlite3.connect('file:/prior/grocery.sqlite?mode=ro',uri=True) as src,sqlite3.connect(P/'grocery.sqlite') as dst:src.backup(dst)
for name in ['coop-municipal','citygross-municipal','lidl-municipal','willys-flyer','ica-structured']:
 shutil.copytree(S/name,P/name)
shutil.copytree(S/'physical-probe/price-universes',P/'price-universes')
shutil.copyfile(S/'willys-config.json',P/'willys-config.json')
shutil.copyfile('/evaluation/policy.json',P/'policy.json')
shutil.copytree(S/'raw',P/'raw')
(P/'raw/source-inbox/willys').mkdir(parents=True,exist_ok=True)
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 rows=[dict(r) for r in db.execute("select sp.chain,sp.store_external_id,min(sp.fetched_at) observed,count(*) products from source_products sp join catalog_snapshots cs on cs.id=sp.catalog_snapshot_id where cs.is_active=1 and sp.fetched_at>='2026-09-27' group by sp.chain,sp.store_external_id")]
now=datetime.now(UTC)
for r in rows:r['age_hours']=(now-datetime.fromisoformat(r['observed'])).total_seconds()/3600
assert len(rows)==5 and all(r['age_hours']<36 for r in rows)
(P/'initialization.json').write_text(json.dumps({'now':now.isoformat(),'base':rows,'policy_sha256':hashlib.sha256((P/'policy.json').read_bytes()).hexdigest(),'basis':'closed SQLite backup and copies of existing private OWN publication/sources; old policy/config and source timestamps unchanged','external_requests':0},indent=2))
print('initialized alternative from five current bases',max(r['age_hours'] for r in rows))
