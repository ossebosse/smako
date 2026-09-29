import hashlib
import io
import json
import shlex
import subprocess
import tarfile
from pathlib import Path
from remote import STAGE, IMAGE

O = Path(__file__).parent
ROOT = O.parents[1]
baseline=json.loads((O/'baseline.json').read_bytes())['app_files']
paths=[n for n,h in baseline.items() if hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h]
paths += [str(p.relative_to(ROOT)).replace('\\','/') for folder in ['grocery_data/app','backend/app'] for p in (ROOT/folder).rglob('*.py') if str(p.relative_to(ROOT)).replace('\\','/') not in baseline]
buf = io.BytesIO()
dockerfile = 'FROM smako-ica-hemkop-municipality:20260928-v8\n'+''.join('COPY '+p+' /srv/app/'+p+'\n' for p in paths)
with tarfile.open(fileobj=buf, mode='w:gz') as archive:
    for p in paths:
        archive.add(ROOT/p, arcname=p)
    data = dockerfile.encode(); info = tarfile.TarInfo('Dockerfile'); info.size=len(data); archive.addfile(info,io.BytesIO(data))
tag='smako-legacy-purchase-terms:20260929-v5'
command=['docker','build','--network','none','-t',tag,'-']
code='import subprocess,sys; r=subprocess.run('+repr(command)+',input=sys.stdin.buffer.read(),capture_output=True); print(r.stdout.decode()[-2000:]); print(r.stderr.decode()[-2000:]); raise SystemExit(r.returncode)'
result=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],input=buf.getvalue(),capture_output=True)
print(result.stdout.decode());print(result.stderr.decode());result.check_returncode()
result=subprocess.run(['ssh','smako','docker image inspect '+tag+' --format '+shlex.quote('{{.Id}}')],capture_output=True,check=True)
identity=result.stdout.decode().strip()
(O/'image.json').write_text(json.dumps({'base_image':'sha256:0790b31f3d7a781c86993a3195d1069b2bc038008f67c0ca918d7dfa3d196bd0','image':identity,'tag':tag,
    'changed_files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'production_activation':False},indent=2),encoding='utf-8')
remote=O/'remote.py';remote.write_text(remote.read_text(encoding="utf-8").replace("IMAGE='"+IMAGE+"'","IMAGE='"+identity+"'"),encoding="utf-8")
print(identity)
