"""Current-source coverage without counting unserved candidates as publication."""
import json,sqlite3,hashlib
from pathlib import Path
from datetime import datetime,UTC
from collections import Counter
from job import configure,save
configure();P=Path('/work');report={'observed_report_at':datetime.now(UTC),'municipal_sources':{},'base':[]}
for name in ['coop-municipal','citygross-municipal','lidl-municipal','willys-flyer']:
 f=P/name/'1281/source-state.json'
 if not f.exists():report['municipal_sources'][name]={'state':'absent'};continue
 state=json.loads(f.read_bytes());inventory=state.get('inventory',{});selected={r['store_id']:r for r in state.get('selection',{}).get('stores',[])}
 rows=[];membership=Counter()
 for item in inventory.get('stores',[]):
  store=item.get('store',{});identity=store.get('external_id');geo=item.get('geographic_evidence',{});status=geo.get('status','unknown');membership[status]+=1
  if status=='outside':continue
  fields=store.get('source_fields',{});outcome=state.get('last_outcomes',{}).get(identity,{})
  rows.append({'store_id':identity,'name':store.get('name'),'address':store.get('address'),'municipality_status':status,'geographic_reason':geo.get('reason'),'channel':store.get('price_context_type'),'official_sources':{k:v for k,v in fields.items() if k in ['official_store_url','canonical_url','flyer_url','store_page_path','offers_url','coordinate_source','concept']},'selection':selected.get(identity),'last_outcome':{k:v for k,v in outcome.items() if k not in ['qualification','metrics']},'qualification':outcome.get('qualification'),'approved_references':state.get('approved',{}).get(identity,[])})
 report['municipal_sources'][name]={'state_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'config':json.loads((P/name/'config.json').read_bytes()),'inventory_status':state.get('inventory_status'),'membership_counts':dict(membership),'stores':rows,'last_attempt':state.get('last_attempt_at'),'publication':state.get('publication')}
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 report['base']=[dict(r) for r in db.execute('''SELECT sp.chain,sp.store_external_id,s.name,cs.id AS snapshot_id,cs.scope_key,cs.coverage,count(*) AS own_rows,min(sp.fetched_at) AS oldest_observation,max(sp.fetched_at) AS newest_observation FROM source_products sp JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id JOIN stores s ON s.id=sp.store_id WHERE cs.is_active=1 GROUP BY sp.chain,sp.store_external_id,cs.id''')]
 report['recent_catalogs']=[{'id':r['id'],'chain':r['chain'],'scope':r['scope_key'],'state':r['state'],'active':r['is_active'],'created_at':r['created_at'],'rejection_reason':r['rejection_reason'],'metrics':json.loads(r['metrics']).get('run_metrics')} for r in db.execute("select * from catalog_snapshots where created_at>='2026-09-27' order by created_at")]
ica=P/'ica-structured/lund/structured-source.json'
if ica.exists():
 d=json.loads(ica.read_bytes());report['ica_structured']={'area':d.get('coverage',{}).get('area'),'stores':d.get('coverage',{}).get('stores'),'store_schedule':d.get('store_schedule'),'next_inventory_at':d.get('next_inventory_at')}
save('source-coverage',report);print('coverage saved')
