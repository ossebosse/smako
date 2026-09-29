"""Complete isolated fixture with exact retained source bytes, never refetch timestamps."""
from pathlib import Path
import json,sqlite3,hashlib,shutil
from job import configure,save
configure();P=Path('/work');S=Path('/prior')
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
f=PreparedUniverseArtifactStore(P/'price-universes').resolve_active_artifact('Lund',verify_hash=True)
artifact=json.loads(f.read_bytes());snapshots={x['source_provenance']['source_snapshot_id'] for x in artifact['universe']['products'] if x.get('source_provenance') and x['source_provenance']['source_provider']=='own'}
rows=[]
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 for snapshot in snapshots:rows.extend(db.execute('select distinct payload_location,payload_hash from raw_snapshots where catalog_snapshot_id=?',(snapshot,)))
missing=[];copied=[];present=[]
for location,expected in sorted(set(rows)):
 rel=Path(location);assert not rel.is_absolute() and '..' not in rel.parts
 src=S/'raw'/rel;dst=P/'raw'/rel
 if dst.exists():
  assert hashlib.sha256(dst.read_bytes()).hexdigest()==expected;present.append(location);continue
 if not src.exists():missing.append(location);continue
 assert hashlib.sha256(src.read_bytes()).hexdigest()==expected
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);copied.append(location)
if (P/'http-results.json').exists():shutil.copy2(P/'http-results.json',P/'http-results-incomplete-raw.json')
save('raw-restoration',{'referenced_files':len(set(rows)),'copied_files':len(copied),'already_present':len(present),'missing':missing,'all_copied_hashes_verified':True,'snapshots':sorted(snapshots),'external_requests':0,'observation_times_unchanged':True,'scope':'Repair incomplete private fixture: retain source byte identity and mtime; no parser, policy or price changes; incomplete-fixture HTTP results preserved separately'})
assert not missing
print('raw fixture complete',len(copied),'files')
