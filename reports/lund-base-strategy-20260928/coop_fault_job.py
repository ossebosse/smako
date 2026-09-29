"""One explicit retry failure on private optional state, with ordinary backoff."""
import asyncio,json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime,UTC
from job import configure,save
configure();P=Path('/work')
from grocery_data.app.services import coop_offer_job as source
from deploy.scripts import run_daily_refresh as runner
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
async def main():
 root,cfg=source.configuration();path=source.location(root,cfg);before=source.read(path)
 async def fail(*a,**k):raise ConnectionError('explicit isolated retry transport failure')
 with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')):
  with patch('grocery_data.scripts.collect_coop_physical_offers.collect',fail),patch('grocery_data.scripts.collect_coop_municipality.collect_xtra',fail):result=await source.run_offer_job()
 after=source.read(path)
 assert before['approved']==after['approved']
 save('coop-retry-fault',{'kind':'explicit injected failure at due optional-source fetch, network disabled; actual clock, ordinary existing retry backoff','outcome':result,'approved_unchanged':True,'before_plan':before['selection'],'after_plan':after['selection'],'current_plan':runner.demand_refresh_plan(now=datetime.now(UTC))})
 print('optional retry failure recorded; approved references unchanged')
asyncio.run(main())
