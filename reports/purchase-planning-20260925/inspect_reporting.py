import json
from pathlib import Path
from collections import Counter
R=Path('reports/purchase-planning-20260925');O=R.parent/'offer-expansion-20260924'
for path in [O/'comparison.json',O/'lidl-denominator.json',R/'willys-2863-final-review.json',R/'final/lidl-1281/0163/result.json',R/'final/verification-1281.json',R/'profile/exact-restored-original.json']:
 d=json.loads(path.read_bytes());print(path.name, type(d).__name__,list(d)[:20] if isinstance(d,dict) else len(d))
 if 'review' in path.name:print(str(d)[:950])
 if path.name=='result.json':print(str(d)[:900])
 if path.name=='lidl-denominator.json':print(str(d)[:800])
 if path.name=='exact-restored-original.json':print({k:v for k,v in d.items() if k not in {'request','diagnostics','selected_products','menu','nutrition','profile','result'}}.keys())
