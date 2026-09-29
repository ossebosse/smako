import json
from pathlib import Path
from collections import Counter
for folder in ['offer-coverage-20260924','offer-nutrition-20260924','offer-expansion-20260924','purchase-planning-20260925']:
 p=Path('reports')/folder/'lidl-denominator.json'
 if not p.exists():continue
 d=json.loads(p.read_bytes());print(folder,d.get('exclusive_primary_reasons'),Counter(b for x in d['rows'] for b in x.get('blockers',[])))
 print(d['rows'][0])
