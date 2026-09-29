"""Read-only exact normalized/source row lineage for the prior and current run."""
import subprocess,shlex,json
from pathlib import Path
R=Path(__file__).resolve().parent
program="""import json,sqlite3
result={}
for label,path in [('before','/old/browser/coop-live/own.sqlite'),('after','/new/coop-live/own.sqlite')]:
 db=sqlite3.connect('file:'+path+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
 result[label]=[dict(r) for r in db.execute('SELECT p.id AS normalized_id, s.*, r.payload_hash, r.payload_location FROM products p JOIN source_products s ON s.id=p.source_product_id JOIN raw_snapshots r ON r.id=p.raw_snapshot_id')]
print(json.dumps(result))
"""
cmd=['docker','run','--rm','--network','none','--user','10001:10001','--read-only','--mount','type=bind,source=/tmp/smako-coop-1520-20260922/data,target=/old,readonly','--mount','type=bind,source=/tmp/smako-coop-nutrition-20260922/data,target=/new,readonly','--entrypoint','/opt/ica-venv/bin/python','smako-coop-candidate:nutrition-20260922','-c',program]
code='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
d=json.loads(r.stdout);(R/'offer-lineage.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
print({k:len(v) for k,v in d.items()})
