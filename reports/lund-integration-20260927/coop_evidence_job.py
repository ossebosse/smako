"""Read-only excerpts from the real current capture, never a new collection."""
import sqlite3,json,hashlib
from pathlib import Path
from job import configure,save
configure();result=[]
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 for identity,loc,digest,observed,url in db.execute("select id,payload_location,payload_hash,fetched_at,url from raw_snapshots where catalog_snapshot_id='467c7656ad314cc5accd7833c8f90c9c' and kind='coop_product_category_page'"):
  data=(Path('/work/raw')/loc).read_bytes();assert hashlib.sha256(data).hexdigest()==digest
  payload=json.loads(data)
  for row in payload.get('results',{}).get('items',[]):
   promos=[p for p in row.get('onlinePromotions',[]) if 'percentageDiscount' in p or 'adjustedPercentageDiscount' in p]
   if promos:
    result.append({'raw_id':identity,'payload_hash':digest,'observed_at':observed,'official_url':url,'product':{k:v for k,v in row.items() if k in ['id','name','gtin','ean','price','priceData','title']},'promotions':promos})
  if len(result)>=3:break
save('coop-current-schema-evidence',result);print('verified current percentage examples',len(result))
