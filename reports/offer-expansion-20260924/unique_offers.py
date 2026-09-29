import json
from pathlib import Path
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
R=Path(__file__).parent;O=R.parent/'offer-nutrition-20260924'
def identity(p):
 o=p.offers[0]
 return (p.chain,p.name.casefold(),(p.brand or '').casefold(),p.package_quantity,p.package_unit,o.price,o.price_basis_unit,o.required_packages,str(o.eligibility),str(o.membership_program),str(o.valid_from),str(o.valid_to),o.max_quantity)
def unique(root):
 d={}
 for code in ['1281','1280']:
  u=PreparedPriceUniverseArtifact.model_validate_json((root/f'prepared-{code}-second.json').read_bytes()).restore()
  for p in u.universe.products:d[identity(p)]=p
 return d
before,after=unique(O),unique(R)
before_ids={p.source_provenance.retailer_product_id:p for p in before.values()}
renamed=[{'source_id':p.source_provenance.retailer_product_id,'before':before_ids[p.source_provenance.retailer_product_id].name,'after':p.name} for k,p in after.items() if k not in before and p.source_provenance.retailer_product_id in before_ids]
new=[p.model_dump(mode='json') for k,p in after.items() if k not in before and p.source_provenance.retailer_product_id not in before_ids]
r={'deduplication':'chain, complete name, brand, package or kg basis, explicit price, required packages, membership, dates, max quantity; no store copies','before':{c:sum(k[0]==c for k in before) for c in ['willys','lidl']},'after':{c:sum(k[0]==c for k in after) for c in ['willys','lidl']},'renamed_same_source_ad_variant_not_new':renamed,'new':new,'removed':[list(k) for k in before if k not in after]}
(R/'unique-new-offers.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
print(r['before'],r['after'],[(p['chain'],p['name']) for p in new],'removed',len(r['removed']))
