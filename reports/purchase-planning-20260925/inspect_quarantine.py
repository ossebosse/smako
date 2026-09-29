import json
from pathlib import Path
r=json.loads(Path('reports/purchase-planning-20260925/lidl-denominator.json').read_bytes())
print([x for x in r['rows'] if not x['accepted'] and not x['blockers']])
