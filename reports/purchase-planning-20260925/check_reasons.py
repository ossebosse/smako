import json
from pathlib import Path
R=Path('reports/purchase-planning-20260925');O=R.parent/'offer-expansion-20260924'
a=json.loads((R/'lidl-denominator.json').read_bytes());b=json.loads((O/'lidl-denominator.json').read_bytes());x=next(x for x in b['rows'] if x['primary_reason']=='unsupported_regional_price_fields');print(x);print(next(y for y in a['rows'] if y['id']==x['id']))
