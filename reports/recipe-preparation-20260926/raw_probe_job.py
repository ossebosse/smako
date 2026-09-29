"""Read-only retained source inspection: chickpea quantity/declaration basis."""
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from app.services.personal_source_facts import raw_product
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

p=PreparedPriceUniverseArtifact.model_validate_json(Path('/work/universe.json').read_bytes()).restore()
ids={x.product_id:x for x in p.universe.products if x.name=='Körsbärstomater hela' or re.fullmatch(r'Kikärt(?:or|er)(?: Eko| Ekologiska| Ekologiska Naturella)?',x.name)}
rows=[]
with sqlite3.connect('file:/work/base/refreshed.sqlite?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 for row in db.execute('SELECT p.id,p.raw_reference,r.payload_location,r.payload_hash FROM products p JOIN raw_snapshots r ON r.id=p.raw_snapshot_id'):
  if row['id'] not in ids:continue
  path=Path('/work/raw')/row['payload_location'];assert path.resolve().is_relative_to(Path('/work/raw'))
  b=path.read_bytes();assert hashlib.sha256(b).hexdigest()==row['payload_hash']
  raw=raw_product(json.loads(b),row['raw_reference'])
  keep={k:v for k,v in raw.items() if re.search(r'weight|quantity|nutri|prepar|unit|size|volume|content|ingred|name|code|^id$',k,re.I)}
  rows.append({'product_id':row['id'],'source_hash':row['payload_hash'],'raw_reference':row['raw_reference'],
               'product_quantity':{'package':ids[row['id']].package_quantity,'usable':ids[row['id']].usable_quantity},
               'fields':keep})
Path('/work/profile/drained-source-review.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
print('retained public product sources inspected:',len(rows))
