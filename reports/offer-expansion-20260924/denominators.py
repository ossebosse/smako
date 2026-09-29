"""Full retained denominators, not a selected-success report."""
import json,re,hashlib
from pathlib import Path
from collections import Counter
R=Path(__file__).parent;O=R.parent/'offer-nutrition-20260924'
def read(p):return json.loads(p.read_bytes())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,default=str),encoding='utf8')
def nonfood(n):return any(t in n.casefold() for t in ('knoppljung','ljungplantering','fläckborttag','munskölj','micellar'))
def count(rows):
 food=[x for x in rows if not nonfood(x['name'])]
 return {'price_rows':len(rows),'nonfood':len(rows)-len(food),'food_price_rows':len(food),'exact_food_purchase_audit':sum(bool(x.get('audit_passed')) for x in food),'rate_only_food':sum('quoted_rate' in x for x in food),'declaration_purchase_unit':sum(bool(x.get('nutrition_approved')) for x in food),'nutrition_measured_edible_grams':sum(bool(x.get('nutrition_edible_grams_available')) for x in food),'nutrition_compatible_purchase_unit_opt_in':sum(bool(x.get('nutrition_edible_grams_available')) and x['package'][1]=='g' for x in food),'recipe_qualified':sum(bool(x.get('recipe_nutrition_approved')) for x in food)}
summary=[];variant_rows=[]
for code,sid,label in [('1281','2863','willys_hemma'),('1280','2352','willys_12')]:
 before=read(O/f'willys-final-{code}'/sid/'result.json');after=read(R/f'willys-final-v2-{code}'/sid/'result.json')
 b=before['qualification']['document_qualification'];a=after['qualification']['document_qualification'];old=b['automatic_decisions'];new={x['index']:x for x in a['automatic_decisions']}
 for x in old:
  if x.get('reason')!='variant_range_or_approximate_quantity_requires_review':continue
  y=new[x['index']];text=y.get('text') or x.get('text','');reason=y.get('reason')
  if y['status']=='qualified':kind='implemented_purchase_form' if y.get('price_basis_unit')=='kg' else 'corrected_interpretation';missing='measured purchase weight for exact package cost' if y.get('price_basis_unit')=='kg' else None
  elif reason=='page_viewer_pdf_text_mismatch':kind='conflicting_official_sources';missing='viewer and PDF edition/page text agreement'
  elif re.search(r'\d\s*[-–/]\s*\d',text):kind='unsupported_or_unbound_quantity_alternatives';missing='variant-to-package-quantity mapping; range/drained/grade meaning where not explicit'
  elif 'Olika' in text:kind='missing_closed_variant_identity';missing='complete list and identity of eligible variants'
  else:kind='unresolved_source_relation';missing=reason
  variant_rows.append({'document':label,'page':x['page'],'ad':x['index'],'title':x['title'],'source_text':text,'before_reason':x['reason'],'after_status':y['status'],'after_reason':reason,'classification':kind,'exact_missing_field':missing})
 br=[x for x in read(O/f'verification-{code}.json')['purchases'] if x['chain']=='willys' and x['store']==sid]
 ar=[x for x in read(R/f'verification-{code}.json')['purchases'] if x['chain']=='willys' and x['store']==sid]
 methods={}
 for key,doc,raw in [('before',b,before),('after',a,after)]:
  ads=[x for x in doc['automatic_decisions'] if x['status']=='qualified']
  cv=sum(len(x['names']) for x in ads if x['valid_from']<='2026-09-24'<=x['valid_to'])
  methods[key]={'automatic_ads':len(ads),'automatic_variants_current':cv,'manual_ads':doc['existing_manual_advertisements'],'manual_variants_current':raw['own']-cv}
 summary.append({'document':label,'identified_ads':before['qualification']['advertisements'],'before':count(br)|methods['before'],'after':count(ar)|methods['after'],'net_unique_price_rows_same_document':len(ar)-len(br),'automatic_blockers_after':dict(Counter(x.get('reason') or x['status'] for x in a['automatic_decisions'])),'ad_ledger':after['qualification']['advertisement_decisions'],'image_content':'not_interpreted; unquantified image-only product content is not counted as zero'})
write(R/'willys-all-variant-cases.json',{'original_cases':len(variant_rows),'classifications':dict(Counter(x['classification'] for x in variant_rows)),'cases':variant_rows})
l=read(R/'lidl-draft2.json');old=read(O/'lidl-denominator.json');accepted={p['external_product_id'] for p in l['products']};byid={x['source_id']:x for x in l['row_acceptance']['decisions']};caption={}
for d in l['decisions']:
 if d.get('product_id'):caption.setdefault(d['product_id'],[]).append(d)
rows=[]
for x in old['rows']:
 y=dict(x);sid=x['id'];y['accepted']=sid in accepted;y['blockers']=byid.get(sid,{}).get('blockers',x['blockers']);y['document_decisions']=caption.get(sid,[]);y['primary_reason']='qualified' if sid in accepted else ('unsupported_regional_price_fields' if 'unsupported_regional_price_fields' in y['blockers'] else 'missing_product_campaign_binding');rows.append(y)
write(R/'lidl-denominator.json',{'original_source_ids':380,'source_ids':len(rows),'original_captions':157,'recognized_captions_after':len(l['decisions']),'caption_reasons':dict(Counter(x['reason'] or 'qualified' for x in l['decisions'])),'date_food_counts':dict(Counter(x['date_status']+'/'+x['food_status'] for x in rows)),'exclusive_primary_reasons':dict(Counter(x['primary_reason'] for x in rows)),'current_food':{'total':sum(x['date_status']=='current' and x['food_status']=='food' for x in rows),'qualified':sum(x['accepted'] and x['date_status']=='current' and x['food_status']=='food' for x in rows)},'rows':rows})
br=[x for x in read(O/'verification-1281.json')['purchases'] if x['chain']=='lidl' and x['store']=='0163'];ar=[x for x in read(R/'verification-1281.json')['purchases'] if x['chain']=='lidl' and x['store']=='0163'];summary.append({'document':'lidl_29','source_ids':380,'before':count(br)|{'automatic_variants_current':23,'manual_variants_current':0},'after':count(ar)|{'automatic_variants_current':len(ar),'manual_variants_current':0},'net_unique_price_rows_same_document':len(ar)-len(br)})
write(R/'comparison.json',{'date':'2026-09-24','memberships':['willys','lidl'],'price_observations_rewritten':False,'summary':summary,'baseline_reporting_correction':'Earlier 23/63 exact-food counts included cleaning/cosmetics/plants. Current classification is applied identically to both arms. Unknown image-only content remains unknown.'})
print(json.dumps([{k:v for k,v in x.items() if k not in {'ad_ledger','automatic_blockers_after'}} for x in summary],ensure_ascii=False,indent=2))
