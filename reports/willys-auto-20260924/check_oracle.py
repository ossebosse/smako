import json,base64
from pathlib import Path
import pymupdf
from grocery_data.app.domain import RawBatch
from grocery_data.app.connectors.willys.flyer_text import qualify_document,flat,blocks
r=Path('reports/willys-auto-20260924')
oracle=json.loads(Path('grocery_data/app/connectors/willys/fixtures/flyer_review_20260923.json').read_bytes())
for identity in ('2863','2354'):
 raw=RawBatch.model_validate_json((r/f'live-{identity}.json').read_bytes())
 with pymupdf.open(stream=base64.b64decode(raw.documents[1].json_payload()['pdf_base64']),filetype='pdf') as doc:
  q=qualify_document(doc,raw.documents[0].json_payload())
  o=next(o for o in oracle if o['pdf_sha256']==raw.documents[1].json_payload()['sha256'])
  for a in q['ads']:
   if a['status']!='qualified':continue
   old=next((b for b in o['ads'] if b['bbox']==a['bbox'] and b['page']==a['page']),None)
   if not old:print('MISSING',a['title']);continue
   diffs={k:(a.get(k),old.get(k)) for k in ('price','required_packages','member_only','max_quantity','package_quantity','package_unit','valid_from','valid_to') if str(a.get(k))!=str(old.get(k)) and a.get(k)!=old.get(k)}
   if diffs:print(identity,a['title'],diffs)
  print(identity,'ads',len(q['ads']),'qualified',sum(a['status']=='qualified' for a in q['ads']))
  (r/f'auto-{identity}.json').write_text(json.dumps(q,ensure_ascii=False,indent=2),encoding='utf-8')
  if identity=='2863':
   for b in blocks(doc[-1]):
    if b['text'].strip() in {'KNOPPLJUNG','LJUNGPLANTERING'}:print(b['text'],[{k:s[k] for k in ('font','size','text')} for s in b['spans']])
