"""Final parser replay equivalence against every live-imported store, no network."""
import json,sqlite3,hashlib
from pathlib import Path
from collections import Counter
from decimal import Decimal
from grocery_data.app.connectors.willys.flyer_inventory import approved_flyer_stores
from grocery_data.app.connectors.willys.flyer_offers import AutomaticWillysFlyerConnector
from grocery_data.app.domain import RawBatch
R=Path(__file__).parent
rows=[];editions={}
for code in ('1281','1280'):
 root=R/f'collection-final-{code}';inv=json.loads((root/'inventory.json').read_bytes())
 for identity,store in approved_flyer_stores(inv).items():
  raw=RawBatch.model_validate_json((root/identity/'source.json').read_bytes())
  c=AutomaticWillysFlyerConnector(store=store,inventory=inv,raw=raw)
  parsed=c.parse_catalog(raw,['listing','document'],store)
  with sqlite3.connect((root/identity/'offers.sqlite').resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
   db.row_factory=sqlite3.Row
   actual={r['external_product_id']:dict(r) for r in db.execute('SELECT * FROM source_products')}
   assert set(actual)=={p.external_product_id for p in parsed.products}
   for p in parsed.products:
    a=actual[p.external_product_id]
    for field in ('name','brand','gtin','package_quantity','package_unit','sale_price','regular_price','member_price'):
     assert a[field]==getattr(p,field),(identity,p.name,field)
    assert json.loads(a['source_fields'])['document_product_binding']==p.source_fields['document_product_binding']
    offers=[dict(o) for o in db.execute('SELECT * FROM promotions WHERE source_product_id=?',(a['id'],))]
    assert len(offers)==len(p.offers)==1
    for k in ('price','quantity','member_only','max_quantity','type'):
     assert (Decimal(str(offers[0][k]))==getattr(p.offers[0],k) if k=='price' else offers[0][k]==getattr(p.offers[0],k)),(identity,p.name,k)
    for k in ('valid_from','valid_to'):
     assert offers[0][k]==getattr(p.offers[0],k).isoformat()
  automation=c.review['automation'];ads=automation['automatic_decisions']
  edition=c.review['pdf_sha256'];editions[edition]={
    'pages':c.review['pages'],'period':[c.review['valid_from'],c.review['valid_to']],
    'identified_text_ads':len(ads),'automatically_qualified':sum(a['status']=='qualified' for a in ads),
    'not_automatically_qualified':sum(a['status']!='qualified' for a in ads),
    'exclusive_review_reasons':dict(Counter(a.get('reason','').split(':')[0] for a in ads if a['status']!='qualified')),
    'current_combined_ad_status':dict(Counter(a['status'] for a in c.review['ads'])),
    'qualified_current_products':len(parsed.products),
    'legacy_qualified_advertisements_before_expiry':automation['existing_manual_advertisements'],
    'unknown_image_content':'not interpreted; number of image-only advertisements unknown',
    'unclassified_text_blocks':sum(len(p['unclassified_text_blocks']) for p in c.review['page_reports']),
    'page_reports':c.review['page_reports'],'automatic_decisions':ads}
  rows.append({'municipality':code,'store_id':identity,'name':store.name,'official_source':store.source_fields['flyer_url'],
    'document_sha256':edition,'own':len(parsed.products),'observed_at':c.observed.isoformat(),
    'final_parser_equals_live_imported_purchase_rows':True,'automatic_products':automation['automatic_advertisements'],
    'legacy_products':len(parsed.products)-automation['automatic_advertisements']})
report={'network_requests':0,'observation_times_changed':False,'kind':'final code replay equivalence, actual live captures retained separately',
 'stores':rows,'editions':editions,'final_parser_sha256':hashlib.sha256(Path('grocery_data/app/connectors/willys/flyer_offers.py').read_bytes()).hexdigest()}
(R/'FINAL-QUALIFICATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS',len(rows),'stores',sum(r['own'] for r in rows),'rows, final parser equals imported qualified data')
