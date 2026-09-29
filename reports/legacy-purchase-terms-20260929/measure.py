"""Full frozen denominator; capabilities, executable amounts and semantic audit separated."""
import json
from pathlib import Path
from collections import Counter
O=Path(__file__).parent
read=lambda p:json.loads(p.read_bytes())
def usage(p):
 t=p.get('source_fields',{}).get('purchase_terms') or p.get('terms')
 return 'conditional' if t and t['variant_selection']=='required' else 'estimated' if t and t['purchase_form'] in {'loose_weight','variable_package'} else 'exact'
def identity(chain,p,variant=True):
 o=p['offers'][0];v=o['source_payload']
 if chain=='coop':
  record=v['source_record'];key=(record['eagId'],record['externalId'] if variant else None)
 elif chain=='hemkop':key=(o['external_id'],p['source_fields'].get('source_variant_id') if variant else None)
 else:key=(o['external_id'],)
 return (chain,*key,o['price'],o['quantity'],o['valid_from'],o['valid_to'],o['member_only'],o['max_quantity'])
summary={'purchase_day':'2026-09-28','network':'retained source replay, no retailer collection','chains':{},'stores':[]}
for mode in ['before','after']:
 rows=read(O/(mode+'-rows.json'));checks=read(O/('before-import' if mode=='before' else 'after-import-v5')/'checkout.json')
 for chain in ['ica','coop','hemkop','xtra']:
  rs=[r for r in rows if r['chain']==chain];cs=[r for r in checks if r['chain']==chain];products=[p for r in rs for p in r['products']]
  blocked=Counter();local=Counter()
  for r in rs:
   for decision in r['evidence']['decisions']:blocked.update(decision['blockers'])
   local.update(f['error_message'] for f in r['evidence']['local_failures'])
  quotes=[p for r in cs for p in r['checks']]
  arithmetic=lambda c:bool(c.get('audit') and all(i['quantity_reconciled'] and i['cost_reconciled'] for i in c['audit']['items']))
  scenarios={}
  for member in [False,True]:
   for planning in ['exact','estimated']:
    selected=[c for p in quotes for c in p['cases'] if c['member']==member and c['mode']==planning]
    scenarios[('member' if member else 'public')+'-'+planning]={'arithmetic_pass':sum(arithmetic(c) for c in selected),'full_audit_pass':sum(c['status']=='PASS' for c in selected),'denominator':len(selected)}
  summary['chains'].setdefault(chain,{})[mode]={'stores':len(rs),'source_rows':sum(r['source_rows'] for r in rs),'approved_source_rows':len(products),
   'source_capabilities':dict(Counter(usage(p) for p in products)),
   'unique_approved_offer_variants':len({identity(chain,p) for p in products}),
   'unique_approved_campaigns':len({identity(chain,p,False) for p in products}),
   'OWN_projected':sum(r['own'] for r in cs),'PU':sum(r['pu'] for r in cs),
   'PU_capabilities':dict(Counter(usage(p) for p in quotes)),
   'arithmetic_pass_any':sum(any(arithmetic(c) for c in p['cases']) for p in quotes),
   'full_audit_pass_any':sum(any(c['status']=='PASS' for c in p['cases']) for p in quotes),
   'scenarios':scenarios,'row_blockers':dict(blocked),'parse_failures':dict(local)}
  for r in rs:
   c=next(c for c in cs if c['store']['external_id']==r['store']['external_id'])
   summary['stores'].append({'mode':mode,'chain':chain,'store_id':r['store']['external_id'],'store':r['store']['name'],'municipality':r['store']['city'],
     'denominator':r['source_rows'],'approved':len(r['products']),'PU':c['pu'],'source_hashes':r['raw_hashes'],'source_observed_at':r['evidence']['observed_at']})
for chain,values in summary['chains'].items():
 assert values['before']['source_rows']==values['after']['source_rows']
for before in [s for s in summary['stores'] if s['mode']=='before']:
 after=next(s for s in summary['stores'] if s['mode']=='after' and (s['chain'],s['store_id'])==(before['chain'],before['store_id']))
 assert before['source_hashes']==after['source_hashes'] and before['source_observed_at']==after['source_observed_at']
(O/'comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for chain,v in summary['chains'].items():print(chain,{m:{k:x for k,x in v[m].items() if k not in ['scenarios','row_blockers','parse_failures']} for m in v})
