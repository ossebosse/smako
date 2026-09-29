import json
from pathlib import Path
from collections import Counter
R=Path(__file__).parent;O=R.parent/'offer-expansion-20260924'
read=lambda p:json.loads(p.read_bytes())
write=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
summary=[]
for code,sid,label in [('1281','2863','Willys Hemma'),('1280','2352','Willys 12 sidor')]:
 raw=read(R/f'final/willys-{code}/{sid}/result.json');q=raw['qualification'];doc=q['document_qualification'];ads=doc['automatic_decisions']
 old=next(x for x in read(O/'comparison.json')['summary'] if x['document']==('willys_hemma' if code=='1281' else 'willys_12'))
 current=[x for x in ads if x['status']=='qualified' and x['valid_from']<='2026-09-24'<=x['valid_to']]
 auto=sum(len(x['names']) for x in current)
 summary.append({'document':label,'denominator':q['advertisements'],'before':old['after'],'after':{'automatic_ads':sum(x['status']=='qualified' for x in ads),'automatic_current_records':auto,'manual_current_records':raw['own']-auto,'imported_current':raw['own'],'conditional_group_ads':sum(bool(x.get('open_variant_group')) for x in current)},'blocker_counts':dict(Counter(x.get('reason') or x['status'] for x in ads)), 'ads':ads,'row_decisions':q['advertisement_decisions'],'image_content':q['unknown_image_content']})
write(R/'willys-denominator.json',summary)
l=read(R/'final/lidl-1281/0163/result.json');a=set(l['qualification']['accepted_ids']);decisions={x['source_id']:x for x in l['qualification']['decisions']}
old=read(O/'lidl-denominator.json');rows=[]
for x in old['rows']:
 y=dict(x);sid=x['id'];y['accepted_before']=x['accepted'];y['accepted']=sid in a;y['blockers']=decisions.get(sid,{}).get('blockers',x['blockers']);y['primary_reason']='qualified' if sid in a else ('parser_quarantine' if x.get('parsed_price_fields') is None else 'missing_product_campaign_binding');rows.append(y)
write(R/'lidl-denominator.json',{'original_source_ids':380,'source_ids':len(rows),'date_food_counts':dict(Counter(x['date_status']+'/'+x['food_status'] for x in rows)),'exclusive_primary_reasons':dict(Counter(x['primary_reason'] for x in rows)),'current_food':{'total':sum(x['date_status']=='current' and x['food_status']=='food' for x in rows),'qualified':sum(x['accepted'] and x['date_status']=='current' and x['food_status']=='food' for x in rows)},'rows':rows})
print([{k:v for k,v in x.items() if k not in {'ads','row_decisions'}} for x in summary]);print('Lidl',len(a),Counter(x['primary_reason'] for x in rows))
stores=[]
for code,city in [('1281','Lund'),('1280','Malmö')]:
 for chain in ['willys','lidl']:
  for s in read(R/f'final/{chain}-{code}/coverage.json')['stores']:
   purchases=[x for x in read(R/f'final/verification-{code}.json')['purchases'] if x['chain']==chain and x['store']==s['store_id']]
   stores.append({'chain':chain,'municipality':city,**s,'purchase_usage_counts':dict(Counter(x.get('usage','unmatched') for x in purchases)),'audit_passed':sum(x.get('audit_passed',False) for x in purchases)})
write(R/'STORES.json',stores)
lines=['# Butiker – fryst prisunderlag 24 september 2026','','Officiell kommuninventering återanvänd. Alla rader är fysiska offers_only; butikskopior räknas separat från unika erbjudanden. 0 nya nätanrop till priskällor.','','| Butik/ID | Kommun | OWN/PU | Köpstatus per butik | Källa |','|---|---|---:|---|---|']
for s in stores:
 lines.append(f"| {s['name']} ({s['store_id']}) | {s['municipality']} | {s['own']}/{s['own']} | {s['purchase_usage_counts']} | [officiell källa]({s.get('source_url','https://www.lidl.se/c/reklamblad/s10007713')}) |")
(R/'STORES.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
