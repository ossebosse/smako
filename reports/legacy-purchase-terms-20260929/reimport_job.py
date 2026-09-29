"""Re-evaluate retained real sources into NEW private source databases.

Ordinary connectors, collector, approval and provider source pointers. Source
observations, schedules, old databases, old plans and mandatory policy unchanged.
"""
import asyncio
import hashlib
import json
import os
import sqlite3
from datetime import UTC,datetime
from pathlib import Path
from job import configure,save
configure()
os.environ['REPLAY_PRIOR_RESULTS']='/work'
import replay
from import_replay import connector_for
from grocery_data.app.domain import GeographicArea,RawBatch,RawFetch
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine,create_session_factory
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path

P=Path('/work')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')

async def main():
    refs={
        'ica':P/'ica-structured/1281/structured-source.json',
        'hemkop':P/'hemkop-municipal/1281/source-state.json',
        'coop':P/'coop-municipal/1281/source-state.json',
    }
    original={k:read(p) for k,p in refs.items()}
    states=json.loads(json.dumps(original))
    old_dbs={'ica':Path(states['ica']['database']),'hemkop':Path(states['hemkop']['database'])}
    for chain,identity in [('coop','1158'),('xtra','3658')]:
        old_dbs[chain]=P/'coop-municipal'/states['coop']['approved'][identity][0]['database']
    engines={};collectors={};new_dbs={};results=[]
    with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')):
        for chain,old in old_dbs.items():
            root=refs['coop' if chain=='xtra' else chain].parent/'purchase-terms-replay-v5'/chain
            root.mkdir(parents=True,exist_ok=True);db=root/'own.sqlite';assert not db.exists()
            with sqlite3.connect(f'file:{old}?mode=ro',uri=True) as src,sqlite3.connect(db) as dst:src.backup(dst)
            engine=create_database_engine('sqlite:///'+str(db));engines[chain]=engine;new_dbs[chain]=db
            collectors[chain]=GroceryCollector(create_session_factory(engine),FilesystemRawSnapshotStore(root/'raw'))
        for chain,store,batch,_ in replay.inputs():
            if chain=='hemkop' and store.external_id not in states['hemkop']['approved_store_ids']:continue
            # Exact municipal scopes are inherited; not new user allowed stores.
            with sqlite3.connect(f'file:{old_dbs[chain]}?mode=ro',uri=True) as db:
                db.row_factory=sqlite3.Row
                active=db.execute('SELECT DISTINCT cs.id,cs.scope_key FROM catalog_snapshots cs JOIN source_products sp ON sp.catalog_snapshot_id=cs.id WHERE cs.is_active=1 AND sp.store_external_id=?',(store.external_id,)).fetchall()
                assert len(active)==1,[(r['id'],r['scope_key']) for r in active]
                raw=db.execute('SELECT * FROM raw_snapshots WHERE catalog_snapshot_id=?',(active[0]['id'],)).fetchall()
            docs=[]
            for r in raw:
                if r['kind'] in {d.kind for d in batch.documents}:continue
                source_root=refs['coop' if chain=='xtra' else chain].parent
                matches=[f for f in source_root.rglob(Path(r['payload_location']).name)
                         if f.is_file() and hashlib.sha256(f.read_bytes()).hexdigest()==r['payload_hash']]
                assert matches, r['payload_location']
                payload=matches[0].read_bytes()
                docs.append(RawFetch(**{k:r[k] for k in ['chain','store_external_id','kind','method','url','http_status','content_type','connector_version','page_number']},
                    query=json.loads(r['query']),fetched_at=datetime.fromisoformat(r['fetched_at']),payload=payload))
            locator=RawBatch(chain=store.chain,documents=tuple(docs))
            connector=connector_for(chain,store,batch,locator)
            scope=active[0]['scope_key']
            result=await collectors[chain].collect_area(connector,GeographicArea(city=store.city),scope_key=scope)
            if not result.promoted:
                save('reimport-failure',{'chain':chain,'store':store.external_id,'result':str(result),'evidence':connector.row_acceptance})
                raise RuntimeError(f'{chain}/{store.external_id}: ordinary approval rejected retained replay')
            observed=min(d.fetched_at for d in batch.documents).isoformat()
            row={'chain':chain,'store_id':store.external_id,'snapshot':result.snapshot_id,
                'observed_at':observed,'source_hashes':[d.payload_hash for d in batch.documents],
                'approved':result.metrics.products_parsed,'evidence':connector.row_acceptance}
            results.append(row)
            if chain in {'coop','xtra'}:
                for ref in states['coop']['approved'][store.external_id]:
                    ref.update(database=str(new_dbs[chain].relative_to(P/'coop-municipal')),
                        snapshots=[result.snapshot_id],observed_at=observed)
            elif chain=='hemkop':
                states['hemkop']['outcomes'][store.external_id].update(snapshot_id=result.snapshot_id,
                    own_rows=result.metrics.products_parsed,acceptance=connector.row_acceptance)
        for e in engines.values():e.dispose()
        states['ica']['database']=str(new_dbs['ica'])
        states['hemkop']['database']=str(new_dbs['hemkop'])
        for chain in ['coop','xtra']:
            digest=hashlib.sha256(new_dbs[chain].read_bytes()).hexdigest()
            for row in results:
                if row['chain']==chain:
                    for ref in states['coop']['approved'][row['store_id']]:ref['sha256']=digest
        for chain,state in states.items():
            state['purchase_terms_replay']={'at':datetime.now(UTC).isoformat(),'source_mode':'retained_public_bytes; no new retailer collection',
                'stores':[r for r in results if r['chain']==chain or chain=='coop' and r['chain']=='xtra']}
            write(refs[chain],state)
        assert states['hemkop']['store_schedule']==original['hemkop']['store_schedule']
        assert states['coop']['selection']==original['coop']['selection']
        save('reimport',{'source_mode':'historical replay, purchase comparison day 2026-09-28',
            'external_calls':0,'results':results,'old_databases':{k:str(v) for k,v in old_dbs.items()},
            'new_databases':{k:str(v) for k,v in new_dbs.items()},'source_observations_preserved':True,
            'policy_sha256':hashlib.sha256((P/'policy.json').read_bytes()).hexdigest()})
    print('Replayed',len(results),'physical sources through retained connectors and ordinary row approval',flush=True)

asyncio.run(main())
