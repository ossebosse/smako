import json
from pathlib import Path
R=Path('reports/purchase-planning-20260925')
for path in [R/'final/willys-1281/2863/result.json',R/'final/lidl-1281/0163/result.json']:
 d=json.loads(path.read_bytes());q=d['qualification'];print(path,list(q))
 for k in ('document_qualification','automatic_product_binding','row_acceptance','document_ad_binding'):
  if k in q:print(k,str(q[k])[:850])
print('lidl draft',list(json.loads((R/'lidl-draft.json').read_bytes())))
