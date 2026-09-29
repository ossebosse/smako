from pathlib import Path
import asyncio,json,hashlib
from collections import Counter
from grocery_data.scripts.collect_lidl_municipality import retained_bundle,collect as collect_lidl
from grocery_data.scripts.collect_willys_flyers import collect as collect_willys
from grocery_data.app.connectors.lidl.municipal_offers import MunicipalLidlOfferConnector
from grocery_data.app.connectors.lidl.municipality_inventory import approved_lidl_stores
from grocery_data.app.domain import RawBatch
R=Path(__file__).resolve().parent
O=R.parent/'offer-coverage-20260924'
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def parse(root):
 b=retained_bundle(root); inv=json.loads((R/'lidl-1281/inventory.json').read_bytes())
 c=MunicipalLidlOfferConnector(store=approved_lidl_stores(inv)['0163'],registry=inv['registry'],catalog=b['catalog'],publication=b['publication'],pdf=b['pdf'])
 p=c.parse_catalog(b['catalog'],['retained']*len(b['catalog'].documents),c.store)
 return b,c,p
async def main():
 for sid in ['2863','2352']:
  source=R/f'live-willys-{sid}';out=R/f'final-replay-live-willys-{sid}'
  if not out.exists():await collect_willys(json.loads((source/'inventory.json').read_bytes()),[sid],out,raw_by_store={sid:RawBatch.model_validate_json((source/sid/'source.json').read_bytes())})
 out=R/'final-replay-live-lidl'
 if not out.exists():await collect_lidl(json.loads((R/'lidl-1281/inventory.json').read_bytes()),['0163'],out,bundle=retained_bundle(R/'live-lidl-source'))
 b,c,p=parse(O/'lidl-live-source')
 write(R/'lidl-final.json',{'products':[x.model_dump(mode='json') for x in p.products],'decisions':c.document_decisions,'row_acceptance':c.row_acceptance})
 source={str(i['gridbox']['data']['productId']):i['gridbox']['data'] for d in b['catalog'].documents for i in d.json_payload()['items']}
 accepted={x.external_product_id for x in p.products};decisions={x['source_id']:x for x in c.row_acceptance['decisions']}
 rows=[]
 from datetime import datetime,UTC
 for sid,x in source.items():
  d=decisions.get(sid,{});category=x.get('category',{});row={'id':sid,'title':x.get('fullTitle'),'category':category,'accepted':sid in accepted,'blockers':d.get('blockers',[]),'source_start':x.get('storeStartDate'),'source_end':x.get('storeEndDate')}
  row['primary_reason']='qualified' if row['accepted'] else next(iter(row['blockers']), 'parser_quarantine')
  if 'unsupported_regional_price_fields' in row['blockers']:row['primary_reason']='unsupported_regional_price_fields'
  rows.append(row)
 write(R/'lidl-denominator.json',{'source_ids':len(source),'accepted':len(accepted),'exclusive_primary_reasons':dict(Counter(x['primary_reason'] for x in rows)),'document_captions':len(c.document_decisions),'caption_reasons':dict(Counter(x['reason'] or 'qualified' for x in c.document_decisions)),'rows':rows})
 summaries=[]
 for code,sid in [('1281','2863'),('1280','2352')]:
  j=json.loads((R/f'willys-final-{code}'/sid/'result.json').read_bytes());q=j['qualification'];a=q['document_qualification'];d=a['automatic_decisions'];summaries.append({'store':sid,'ads':q['advertisements'],'automatic_ads':a['automatic_advertisements'],'manual_ads':a['existing_manual_advertisements'],'products':j['own'],'exclusive_automatic_reasons':dict(Counter(x.get('reason') or x['status'] for x in d)), 'unknown_image_content':q['unknown_image_content']})
 write(R/'willys-denominator.json',summaries)
 print('FINAL',len(p.products),Counter(x['reason'] or 'qualified' for x in c.document_decisions),summaries)
if __name__=='__main__':asyncio.run(main())
