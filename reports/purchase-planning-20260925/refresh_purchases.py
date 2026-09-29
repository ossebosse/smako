import json
from pathlib import Path
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from verify_coverage import purchases, write
R=Path(__file__).parent
for code in ['1281','1280']:
 p=R/f'final/verification-{code}.json';d=json.loads(p.read_bytes())
 prepared=PreparedPriceUniverseArtifact.model_validate_json((R/f'final/prepared-{code}-second.json').read_bytes()).restore()
 d['purchases']=purchases(prepared);d['facts_evaluated_with']='Final code, including separately acquired 25 September Arla declaration; price observations remain original.'
 write(p,d)
 print(code,len(d['purchases']),flush=True)
