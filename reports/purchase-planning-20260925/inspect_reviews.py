import json
from pathlib import Path
from grocery_data.app.connectors.willys import flyer_offers
from grocery_data.app.connectors.willys.flyer_inventory import approved_flyer_stores
from grocery_data.app.domain import RawBatch
from grocery_data.tests.test_lidl_automatic_document import parse,EXPECTED
root=Path('reports/willys-flyers-20260923')
for identity,code in [('2863','1281'),('2352','1280')]:
 inv=json.loads((root/f'inventory-{code}/inventory.json').read_bytes());raw=RawBatch.model_validate_json((root/f'live-{identity}.json').read_bytes())
 c=flyer_offers.AutomaticWillysFlyerConnector(store=approved_flyer_stores(inv)[identity],inventory=inv,raw=raw)
 ps=c.parse_catalog(raw,['listing','document'],c.store).products
 print(identity,len(ps),c.review['automation'])
 for ad in c.review['ads']:
  if ad.get('purchase_terms',{}).get('identity_scope')=='campaign_group' or ad.get('purchase_terms',{}).get('deposit_status')=='unknown':
   print(json.dumps({k:ad.get(k) for k in ['page','title','text','price','required_packages','purchase_terms','valid_from','valid_to']},ensure_ascii=False))
 Path(f'reports/purchase-planning-20260925/willys-{identity}-final-review.json').write_text(json.dumps(c.review,ensure_ascii=False,indent=2),encoding='utf-8')
ps,c=parse();print('L',len(ps.products),len(ps.failures))
for p in ps.products:
 if p.external_product_id not in EXPECTED:print('NEW',p.external_product_id,p.name,p.package_text,p.offers[0].price,p.source_fields.get('document_product_binding'))
