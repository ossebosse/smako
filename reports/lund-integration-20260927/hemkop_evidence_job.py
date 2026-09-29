import sqlite3,json,hashlib
from pathlib import Path
from job import configure,save
configure();result=[]
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 for identity,loc,digest,observed,url in db.execute("select id,payload_location,payload_hash,fetched_at,url from raw_snapshots where catalog_snapshot_id='c020d2b8cddd4dc483a92b9c6acd48ba' and kind='catalog_page'"):
  data=(Path('/work/raw')/loc).read_bytes();assert hashlib.sha256(data).hexdigest()==digest
  payload=json.loads(data)
  for row in payload.get('results') or []:
   if row.get('energyDeclaration'):
    result.append({'raw_id':identity,'payload_hash':digest,'observed_at':observed,'official_url':url,'product':{k:v for k,v in row.items() if k in ['code','name','price','priceValue','energyDeclaration','nutrition']}})
save('hemkop-current-schema-evidence',result);print(json.dumps(result,ensure_ascii=False)[:2200])
