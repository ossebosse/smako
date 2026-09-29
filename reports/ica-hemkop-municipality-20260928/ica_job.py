import asyncio,os,json
from pathlib import Path
from job import configure,save
from grocery_data.app.services.ica_offer_job import run_structured_offer_job
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
async def main():
 configure()
 with RefreshRunLock(production_refresh_lock_path(Path('/work/grocery.sqlite'),Path('/work/price-universes'))):
  for code,city in [('1281','Lund'),('1280','Malmö')]:
   os.environ['REFRESH_MUNICIPALITY_CODE']=code
   result=await run_structured_offer_job(city=city,root=Path('/work/ica-structured'))
   save('ica-job-'+code,result)
   print(code,result['status'],len(result['ica_offer_store_ids']),flush=True)
asyncio.run(main())
