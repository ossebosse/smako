import asyncio,json
from pathlib import Path
from datetime import UTC,datetime
from job import configure,save
configure()
from grocery_data.app.services.ica_offer_job import run_structured_offer_job
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
async def main():
    pointer=Path('/work/ica-structured/1281/structured-source.json')
    old=json.loads(pointer.read_bytes());now=datetime.now(UTC)
    assert datetime.fromisoformat(old['next_inventory_at'])<=now
    assert all(datetime.fromisoformat(s['next_fetch_at'])>now for s in old['store_schedule'].values())
    with RefreshRunLock(production_refresh_lock_path(Path('/work/grocery.sqlite'),Path('/work/price-universes'))):
        result=await run_structured_offer_job(city='Lund',root=Path('/work/ica-structured'))
    prior={r['ica_account_id']:r for r in old['coverage']['stores']}
    rows=[]
    for r in result['coverage']['stores']:
        if r['area_membership']!='inside':continue
        oldr=prior[r['ica_account_id']]
        assert r['collection_status']=='not_due_retained'
        assert r['row_approved_result']==oldr['row_approved_result']
        assert r['last_success_at']==oldr['last_success_at']
        rows.append({'id':r['ica_account_id'],'status':r['collection_status'],'observed_at':r['last_success_at'],'snapshot':r['row_approved_result']['snapshot_id']})
    save('ica-due-inventory-check',{'status':'PASS','scope':'actual due locator check through ordinary source job; price sources not due',
        'rows':rows,'before_next_inventory':old['next_inventory_at'],'after_next_inventory':result['next_inventory_at'],
        'same_approved_store_ids':old['ica_offer_store_ids']==result['ica_offer_store_ids'],
        'same_price_schedule':old['store_schedule']==result['store_schedule'],'external_price_requests':0})
    print('due ICA inventory check: all retained, zero price requests')
asyncio.run(main())
