"""Read-only packaged code closure; no runtime/production changes."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parents[1]
CODE = """import hashlib,json
from pathlib import Path
r=Path('/srv/app'); paths=[]
for name in ['backend/app','grocery_data/app','deploy/scripts']:
 paths.extend((r/name).rglob('*.py'))
paths.extend(r/'grocery_data'/n for n in ['source_cli.py','local_relay.py','__main__.py'])
print(json.dumps({p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
"""
image = 'smako-willys-candidate:municipality-20260922'
cmd = ['docker','run','--rm','--network','none','--read-only','--cpus','0.25','--memory','256m','--entrypoint','/opt/ica-venv/bin/python',image,'-c',CODE]
remote = 'import subprocess,sys;r=subprocess.run('+repr(cmd)+',capture_output=True);sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)'
r = subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(remote)],capture_output=True)
if r.returncode:
 print(r.stderr.decode(errors='replace')[-2000:]);raise SystemExit(r.returncode)
packaged = json.loads(r.stdout)
local = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in packaged}
differences = [name for name in packaged if packaged[name] != local[name]]
result={'image':image,'file_count':len(packaged),'differences':differences,'packaged':packaged}
(HERE/'package-code-closure.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'file_count':len(packaged),'differences':differences}))
assert not differences
