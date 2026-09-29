"""Read-only count reconciliation; no acquisition or publication."""
import json,sqlite3
from pathlib import Path
P=Path('/work')
query="select sp.chain,sp.store_external_id,sp.availability,count(*) as rows from source_products sp join catalog_snapshots cs on cs.id=sp.catalog_snapshot_id where cs.is_active=1 and sp.fetched_at>='2026-09-27' group by sp.chain,sp.store_external_id,sp.availability"
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 rows=[dict(r) for r in db.execute(query)]
source=json.loads((P/'ica-structured/lund/structured-source.json').read_bytes())
with sqlite3.connect('file:'+source['database']+'?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 ica=[dict(r) for r in db.execute("select sp.external_product_id,sp.gtin,sp.name,sp.availability from source_products sp join catalog_snapshots cs on cs.id=sp.catalog_snapshot_id where cs.is_active=1 and sp.store_external_id='1088004'")]
(P/'availability-reconciliation.json').write_text(json.dumps({'query':query,'base_rows':rows,'ica_1088004_active_rows':ica,'network_requests':0},ensure_ascii=False,indent=2))
print('availability reconciliation saved',len(ica))
