"""Actual clock, private receipt from actual private publication; no retailer sockets."""
import json
from datetime import UTC,datetime
from pathlib import Path
from grocery_data.local_relay import run
from grocery_data.app.services.willys_municipal_scope import relay_municipality
ROOT=Path(__file__).parent
workspace=ROOT/'not-due-relay';workspace.mkdir(exist_ok=True)
relay_municipality(workspace,'1281')
source=json.loads((ROOT/'lund-requalified/result.json').read_bytes())
publication=json.loads((ROOT/'server-results/result-cycle-final-a.json').read_bytes())
assert publication['willys_products']>0
receipt=workspace/'last-success.json'
if not receipt.exists():
 receipt.write_text(json.dumps({'municipality_code':'1281','sha256':source['sha256'],'observed_from':source['observed_from'],
  'server':{'universe_id':publication['universe_id']},'evidence':'private publication; no beta activation'}),encoding='utf-8')
calls=[]
def forbidden(*args):
 calls.append('unexpected');raise AssertionError('No collection, upload or activation is due')
result=run(workspace,collect=forbidden,push=forbidden,activate=forbidden)
assert result==0 and not calls
runs=list(workspace.glob('proof-*.json'))
(workspace/f'proof-{len(runs)+1}.json').write_text(json.dumps({'exit':result,'at':datetime.now(UTC).isoformat(),
 'external_calls':len(calls),'separate_process':True,'clock':'actual','receipt_unchanged':json.loads(receipt.read_bytes())},indent=2),encoding='utf-8')
print('not due; no external calls; persisted scope/receipt retained')
