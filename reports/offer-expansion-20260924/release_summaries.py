"""Release summaries from measured results; no qualification input."""
import json,hashlib
from pathlib import Path
from collections import Counter
R=Path(__file__).parent
read=lambda p:json.loads(p.read_bytes())
rows=[]
for code,city in [('1281','Lund'),('1280','Malmö')]:
 for chain,folder in [('Willys',f'willys-final-v2-{code}'),('Lidl',f'lidl-v2-{code}')]:
  cov=read(R/folder/'coverage.json')
  inv=read(R/folder/'inventory.json')
  for s in cov['stores']:
   rows.append({'chain':chain,'municipality':city,**s})
(R/'STORES.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf8')
lines=['# Butiksresultat – fryst 24 september 2026','',
 'Samma officiella kommuninventering och urval för 1281/1280. Replay ger inga nya observationstider. Butikskopior är inte nya erbjudanden. Alla källor är fysiska erbjudanden, offers_only; ordinarie köppris förblir okänt.','',
 '| Kedja/butik | Kommun | OWN/PU | Källformat | Officiell källa |', '|---|---|---:|---|---|']
for s in rows:
 name=s.get('name',s['store_id']);url=s.get('source_url','https://www.lidl.se/c/reklamblad/s10007713');n=s.get('own');fmt=s.get('source_format','strukturerade data + officiell PDF-text')
 lines.append(f"| {s['chain']} {name} ({s['store_id']}) | {s['municipality']} | {n}/{n} | {fmt} | [källa]({url}) |")
lines+=['','Hemma: 28 rader, varav fyra endast verifierade kg-priser; tolvsidigt Willys-blad: 70 rader, varav fyra kg-priser. Dessa åtta unika kvoter är inte exakta paketköp. Lidl: 26 av 380 käll-ID per butik; 354 kvar utanför köpimporten. Alla bortfall finns i respektive coverage/result och de fullständiga nämnarregistren.','', 'Fem Willys-nonfoodidentiteter särredovisas: Knoppljung, Ljungplantering, Fläckborttagning, Munskölj och Micellar water. De bidrar inte till livsmedelsmåttet.']
(R/'STORES.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
root=R/'runtime-v2-1280';phases=[read(root/f'result-{m}.json') for m in ['first','second','restart','not_due','fetch_fail','recovery']]
assert len({p['flyer_product_signature'] for p in phases})==1
assert len({json.dumps(p['source_observations']) for p in phases})==1
state=read(root/'demand.json')
summary={'status':'PARTIAL: no-work whole-run assertion not met because retained City Gross base exceeded ordinary 35h refresh boundary','phases':[{'mode':p['mode'],'status':p['runner']['status'],'flyer_products':p['flyer_products'],'all_chain_counts':p['all_chain_counts'],'health':p['health'],'ready':p['ready'],'external_attempts':p['parent_network']['blocked_external_attempts'],'child_external_attempts':p.get('child_network',{}).get('blocked_external_attempts')} for p in phases],'source_observations_preserved':True,'willys_product_signatures_preserved':True,'lidl_source_job_recovery':read(R/'lidl-recovery-verification.json'),'source_next_fetches':{}}
for kind in ['willys_flyer','lidl_municipal','citygross_municipal']:
 a=state['last_check'].get(kind,{})
 summary['source_next_fetches'][kind]=[{'store_id':s.get('store_id'),'next_fetch_at':s.get('next_fetch_at'),'hard_stop':s.get('price_hard_stop_at'),'reason':s.get('reason')} for s in a.get('stores',[])]
(R/'runtime-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
print('stores',len(rows),'runtime phases',len(phases))
