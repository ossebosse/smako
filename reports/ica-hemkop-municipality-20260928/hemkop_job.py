import asyncio,os
from pathlib import Path
from job import configure,save
from grocery_data.app.services.hemkop_municipal_job import run_source_job
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
async def main():
 configure();os.environ.update(HEMKOP_MUNICIPAL_OFFERS_ENABLED='true',HEMKOP_MUNICIPAL_ROOT='/work/hemkop-municipal')
 with RefreshRunLock(production_refresh_lock_path(Path('/work/grocery.sqlite'),Path('/work/price-universes'))):
  for code,city in [('1281','Lund'),('1280','Malmö')]:
   os.environ['REFRESH_MUNICIPALITY_CODE']=code
   root=Path('/work/hemkop-municipal')/code;root.mkdir(parents=True,exist_ok=True)
   if not (root/'boundary.json').exists():(root/'boundary.json').write_bytes(Path('/evaluation/boundary-'+code+'.json').read_bytes())
   result=await run_source_job(city=city)
   save('hemkop-job-'+code,result)
   print(code,result['status'],[(k,v['status'],v.get('own_rows'),v.get('reason')) for k,v in result['outcomes'].items()],flush=True)
asyncio.run(main())
