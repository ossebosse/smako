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
paths = ['grocery_data/app/connectors/coop/'+name for name in ['structured_offers.py','parser.py','connector.py']] + ['grocery_data/app/services/offer_rows.py','backend/app/providers/coop_municipality_offers.py']
buf = io.BytesIO()
dockerfile = 'FROM smako-lund-candidate:integration-20260927\n'+''.join('COPY '+p+' /srv/app/'+p+'\n' for p in paths)
with tarfile.open(fileobj=buf, mode='w:gz') as archive:
    for p in paths:
        archive.add(ROOT/p, arcname=p)
    data = dockerfile.encode(); info = tarfile.TarInfo('Dockerfile'); info.size=len(data); archive.addfile(info,io.BytesIO(data))
tag='smako-coop-source-binding:20260928-v4'
command=['docker','build','--network','none','-t',tag,'-']
code='import subprocess,sys; r=subprocess.run('+repr(command)+',input=sys.stdin.buffer.read(),capture_output=True); print(r.stdout.decode()[-2000:]); print(r.stderr.decode()[-2000:]); raise SystemExit(r.returncode)'
result=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],input=buf.getvalue(),capture_output=True)
print(result.stdout.decode());print(result.stderr.decode());result.check_returncode()
result=subprocess.run(['ssh','smako','docker image inspect '+tag+' --format '+shlex.quote('{{.Id}}')],capture_output=True,check=True)
identity=result.stdout.decode().strip()
(O/'image.json').write_text(json.dumps({'base_image':'sha256:32e838155b0ef2b4b4eb9944cb7d1b31324b37e7ea56eb6d840fc70fc9e1ff87','image':identity,'tag':tag,
    'changed_files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'production_activation':False},indent=2))
remote=O/'remote.py';remote.write_text(remote.read_text().replace("IMAGE='"+IMAGE+"'","IMAGE='"+identity+"'"))
print(identity)
