import json
from pathlib import Path
from collections import Counter
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
R=Path(__file__).parent;O=R.parent/'offer-expansion-20260924'
read=lambda p:json.loads(p.read_bytes())
write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def identity(p):
 o=p.offers[0]
 return (p.chain,p.name.casefold(),(p.brand or '').casefold(),p.package_quantity,p.package_unit,o.price,o.price_basis_unit,o.required_packages,str(o.eligibility),str(o.membership_program),str(o.valid_from),str(o.valid_to),o.max_quantity)
def nonfood(n):return any(t in n.casefold() for t in ('knoppljung','ljungplantering','fläckborttag','munskölj','micellar','babytvätt'))
def arm(root):
 result={}
 for code in ['1281','1280']:
  pu=PreparedPriceUniverseArtifact.model_validate_json((root/f'prepared-{code}-second.json').read_bytes()).restore()
  rows=read(root/f'verification-{code}.json')['purchases'];byid={(r['chain'],r['store'],r['id']):r for r in rows}
  for p in pu.universe.products:
   row=byid.get((p.chain,p.source_provenance.provider_store_id,p.source_provenance.retailer_product_id),{})
   result[identity(p)]=(p,row)
 return result
before,after=arm(O),arm(R/'final');summ=[]
for chain in ['willys','lidl']:
 entry={'chain':chain}
 for label,values in [('before',before),('after',after)]:
  allrows=[(p,r) for p,r in values.values() if p.chain==chain];food=[(p,r) for p,r in allrows if not nonfood(p.name)]
  entry[label]={'price_records_deduplicated':len(allrows),'nonfood_records':len(allrows)-len(food),'food_records':len(food),'exact_food_purchase_audit':sum(r.get('audit_passed',False) and r.get('usage','exact')=='exact' for p,r in food),'estimated_food_purchase_audit':sum(r.get('audit_passed',False) and r.get('usage')=='estimated' for p,r in food),'conditional_food_choice_audit':sum(r.get('audit_passed',False) and r.get('usage')=='conditional' for p,r in food),'nutrition_edible_grams':sum(bool(r.get('nutrition_edible_grams_available')) for p,r in food),'nutrition_compatible_gram_purchase_unit':sum(bool(r.get('nutrition_edible_grams_available')) and p.package_unit=='g' for p,r in food),'recipe_bread_test':sum(bool(r.get('recipe_nutrition_approved')) for p,r in food)}
 summ.append(entry)
oldcontracts={p.offers[0].price_contract_id for p,r in before.values()}
new=[{'product':p.model_dump(mode='json'),'purchase':r,'nonfood':nonfood(p.name),'same_existing_campaign':p.offers[0].price_contract_id in oldcontracts} for k,(p,r) in after.items() if k not in before]
write(R/'comparison.json',{'date':'2026-09-24','memberships':['willys','lidl'],'price_observations_rewritten':False,'price_sources':'identical retained captures','nutrition_new_acquisition':'2026-09-25: Arla and SLV, separated from price replay','counting':'exact full identity, brand, pack/basis, price, count, membership, dates and cap; never store copies; group records are not identified variants; existing campaign overlap explicitly subtracted','summary':summ,'new_records':new,'removed':[list(k) for k in before if k not in after],'new_campaign_prices':{c:sum(x['product']['chain']==c and not x['same_existing_campaign'] for x in new) for c in ['willys','lidl']},'new_food_campaign_prices':{c:sum(x['product']['chain']==c and not x['same_existing_campaign'] and not x['nonfood'] for x in new) for c in ['willys','lidl']}})
print(json.dumps(summ,ensure_ascii=False,indent=2))
