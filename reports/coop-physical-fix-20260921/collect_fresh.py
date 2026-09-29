import asyncio,json,time
from pathlib import Path
from grocery_data.app.connectors.coop.connector import CoopConnector
from grocery_data.app.domain import SourceStore,GeographicArea,RawBatch
from grocery_data.app.services.offer_rows import qualify_rows
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
R=Path('reports/coop-physical-fix-20260921/fresh-v1');R.mkdir(exist_ok=False)
async def main():
 audit=json.loads(Path('reports/municipality-offers-20260920/coop-audit.json').read_bytes())
 connector=CoopConnector();summary=[]
 try:
  for account in ['3839','3815']:
   start=time.perf_counter();prior=next(SourceStore(**x['store']) for x in audit['stores'] if x['store']['external_id']==account)
   raw_store=await connector.client._get(prior.source_fields['store_page_path'],kind='store_page')
   locator=RawBatch(chain='coop',documents=(raw_store,))
   fresh=connector.parse_stores(locator,['official-store'],GeographicArea(city=prior.city))
   assert len(fresh)==1 and fresh[0].external_id==account
   assert fresh[0].source_fields['ledger_account_number']==prior.source_fields['ledger_account_number']
   store=fresh[0].model_copy(update={'address':fresh[0].address or prior.address,'postal_code':fresh[0].postal_code or prior.postal_code,'price_context_type':'physical_store','physical_store_external_id':account})
   batch=await connector.fetch_offers(store)
   (R/(account+'-store.json')).write_text(store.model_dump_json(indent=2),encoding='utf-8')
   (R/(account+'-locator.json')).write_text(locator.model_dump_json(indent=2),encoding='utf-8')
   (R/(account+'-batch.json')).write_text(batch.model_dump_json(indent=2),encoding='utf-8')
   parsed=connector.parse_catalog(batch,['official-offers'],store)
   (R/(account+'-parsed.json')).write_text(parsed.model_dump_json(indent=2),encoding='utf-8')
   qualified,evidence=qualify_rows(parsed,store=store,observed_at=batch.documents[0].fetched_at)
   (R/(account+'-qualification.json')).write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
   envelope=json.loads(batch.documents[0].payload)
   result={'store':account,'source':batch.documents[0].url,'observed_at':batch.documents[0].fetched_at.isoformat(),'hash':batch.documents[0].payload_hash,'ads':envelope['captured_total'],'structured':bool(envelope.get('structured_offers')),'parsed':len(parsed.products),'failures':len(parsed.failures),'qualified':len(qualified.products),'rejected':len(qualified.failures),'seconds':round(time.perf_counter()-start,3)}
   summary.append(result);print(json.dumps(result),flush=True)
  (R/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
 finally:await connector.aclose()
with RefreshRunLock(production_refresh_lock_path(R.parent/'staging.sqlite',R.parent/'price-universes',allow_missing_database=True)):asyncio.run(main())
