import json
from pathlib import Path
from collections import Counter
R=Path('reports/purchase-planning-20260925')
d=json.loads((R/'lidl-draft.json').read_bytes());print('lidl draft products',len(d['products']), 'decisions',len(d['decisions']),Counter(x.get('reason') or 'qualified' for x in d['decisions']))
print(json.loads((R/'final/lidl-1281/0163/result.json').read_bytes())['qualification']['decisions'][0])
