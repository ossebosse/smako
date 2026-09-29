import json,sqlite3,hashlib,os
from pathlib import Path
from job import configure,save
configure()
from grocery_data.app.connectors.hemkop.physical_offers import parse
from grocery_data.app.domain import RawBatch,SourceStore
from grocery_data.app.services.area_membership import collection_area
from grocery_data.app.services.hemkop_municipal_job import source_plan
report={'hemkop':{},'ica':{},'scope_restart':{}}
for code,city in [('1281','Lund'),('1280','Malmö')]:
    state=json.loads(Path('/work/hemkop-municipal/'+code+'/source-state.json').read_bytes())
    db=Path(state['database']);rows=[]
    for identity in state['approved_store_ids']:
        row=next(r for r in state['inventory']['stores'] if r['store']['external_id']==identity)
        store=SourceStore.model_validate(row['store']);outcome=state['outcomes'][identity]
        raw=RawBatch.model_validate_json((db.parent/(identity+'-offers.json')).read_bytes())
        result=parse(raw,[str(i) for i in range(len(raw.documents))],store)
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
            actual=conn.execute('select external_product_id from source_products where catalog_snapshot_id=?',(outcome['snapshot_id'],)).fetchall()
        assert {p.external_product_id for p in result.products}=={x[0] for x in actual}
        rows.append({'id':identity,'name':store.name,'raw':sum(len(d.json_payload()['results']) for d in raw.documents),
            'approved':len(result.products),'quarantined':len(result.failures),'snapshot':outcome['snapshot_id'],
            'observed_at':outcome['observed_at'],'official_source':outcome['source'],
            'source_hashes':[d.payload_hash for d in raw.documents],
            'replayed_final_parser_matches_own':True,'own_database_sha256':hashlib.sha256(db.read_bytes()).hexdigest()})
    os.environ['REFRESH_MUNICIPALITY_CODE']=code
    report['hemkop'][code]={'stores':rows,'schedule':source_plan(city=city)}
    ica=json.loads(Path('/work/ica-structured/'+code+'/structured-source.json').read_bytes())
    report['ica'][code]={'database':ica['database'],'observed_at':ica['observed_at'],'stores':[
        {k:r.get(k) for k in ['ica_account_id','name','locality','area_membership','area_reason','collection_status','row_approved_own','official_store_url','offers_url','last_success_at','error']}
        for r in ica['coverage']['stores']], 'schedule':ica['store_schedule'],'next_inventory_at':ica['next_inventory_at']}
    os.environ.pop('REFRESH_MUNICIPALITY_CODE')
    report['scope_restart'][code]=collection_area(city).model_dump(mode='json')
assert report['scope_restart']['1281']['municipality_code']=='1281'
assert report['scope_restart']['1280']['municipality_code']=='1280'
report['raw_reference_checks']={}
for code in ['1281','1280']:
    for chain in ['ica','hemkop']:
        folder=Path('/work/'+('ica-structured' if chain=='ica' else 'hemkop-municipal')+'/'+code)
        state=json.loads((folder/('structured-source.json' if chain=='ica' else 'source-state.json')).read_bytes())
        db=Path(state['database'])
        roots=list(folder.glob('*-raw')) if chain=='ica' else list((folder/'attempts').glob('*/raw'))
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
            refs=conn.execute("select distinct r.payload_location,r.payload_hash from raw_snapshots r join catalog_snapshots s on r.catalog_snapshot_id=s.id where s.is_active=1 and s.state='promoted'").fetchall()
        checked=0
        for location,digest in refs:
            candidates=[(root/location).resolve() for root in roots]
            assert all(path.is_relative_to(folder) for path in candidates)
            assert any(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest for path in candidates), (chain,code,location)
            checked+=1
        assert checked
        report['raw_reference_checks'][chain+':'+code]={'referenced_raw_files':checked,'all_hashes_valid':True}
save('source-audit-final',report)
print('final source replay and durable municipal scope PASS')
