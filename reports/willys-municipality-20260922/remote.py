"""New isolated package; no production mounts or activation commands."""
import io,json,shlex,subprocess,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).parent
STAGE='/var/tmp/smako-willys-municipality-20260922'
IMAGE='smako-willys-candidate:municipality-20260922'
def ssh(code,data=None):
 r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],input=data,capture_output=True)
 print(r.stdout.decode('utf-8',errors='replace'),flush=True)
 print(json.dumps({'exit':r.returncode,'stderr_bytes':len(r.stderr)}),flush=True)
 if r.returncode: raise SystemExit(r.returncode)
def stage():
 b=io.BytesIO()
 with tarfile.open(fileobj=b,mode='w:gz') as t:
  for root in ['backend/app','grocery_data/app','deploy/scripts']:
   for p in (ROOT/root).rglob('*.py'):
    if '__pycache__' not in p.parts:t.add(p,arcname=p.relative_to(ROOT).as_posix())
  for name in ['source_cli.py','local_relay.py','__main__.py']:t.add(ROOT/'grocery_data'/name,arcname='grocery_data/'+name)
  for p in HERE.glob('server_*.py'):t.add(p,arcname='evaluation/'+p.name)
  docker='FROM smako-coop-candidate:refresh-integration-20260922\nCOPY --chown=10001:10001 backend/app /srv/app/backend/app\nCOPY --chown=10001:10001 grocery_data /srv/app/grocery_data\nCOPY --chown=10001:10001 deploy/scripts /srv/app/deploy/scripts\n'
  item=tarfile.TarInfo('Dockerfile');body=docker.encode();item.size=len(body);t.addfile(item,io.BytesIO(body))
 code=f'''import io,sys,tarfile,pathlib,subprocess,json
p=pathlib.Path({STAGE!r});p.mkdir(exist_ok=True)
marker=p/'.owner'
if marker.exists():assert marker.read_text()=='willys-municipality-20260922'
else:marker.write_text('willys-municipality-20260922')
assert not subprocess.check_output(['docker','ps','-q','--filter','name=^/smako-willys-municipal-test$']).strip()
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:
 for m in t:
  target=p/m.name;assert m.isfile() and target.resolve().is_relative_to(p)
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(t.extractfile(m).read());target.chmod(0o644)
subprocess.run(['docker','run','--rm','--network','none','-v',str(p)+':/stage','alpine:3.20','sh','-c','mkdir -p /stage/data; chown 10001:10001 /stage/data; chmod 700 /stage/data'],check=True)
r=subprocess.run(['docker','build','--network','none','-t',{IMAGE!r},str(p)],capture_output=True)
print(json.dumps({{'build_exit':r.returncode,'image':subprocess.check_output(['docker','inspect','--format','{{{{.Id}}}}',{IMAGE!r}],text=True).strip() if r.returncode==0 else None}}))
raise SystemExit(r.returncode)
'''
 ssh(code,b.getvalue())
def upload(path):
 data=Path(path).read_bytes()
 import hashlib
 digest=hashlib.sha256(data).hexdigest()
 code=f'''import sys,pathlib,hashlib,subprocess,json
p=pathlib.Path({STAGE!r})/'incoming';p.mkdir(exist_ok=True)
data=sys.stdin.buffer.read();assert hashlib.sha256(data).hexdigest()=={digest!r}
t=p/({digest!r}+'.smako-source')
if t.exists():assert t.read_bytes()==data
else:t.write_bytes(data);t.chmod(0o644)
print('private source staged')
'''
 ssh(code,data)
def run(mode):
 cmd=['docker','run','--rm','--name','smako-willys-municipal-test','--user','10001:10001','--network','none','--read-only','--cpus','2','--memory','5g','--tmpfs','/tmp:rw,size=512m,mode=1777','-e','PYTHONPATH=/srv/app/backend:/srv/app',
 '-v',STAGE+'/data:/work','-v',STAGE+'/evaluation:/evaluation:ro','-v',STAGE+'/incoming:/incoming:ro',
 '-v','/var/tmp/smako-coop-refresh-integration-20260922/data:/previous:ro','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'/evaluation/server_job.py',mode]
 ssh('import subprocess,json\nr=subprocess.run('+repr(cmd)+',capture_output=True);print(r.stdout.decode("utf8",errors="replace"));print(json.dumps({"exit":r.returncode,"stderr_bytes":len(r.stderr)}));raise SystemExit(r.returncode)')
def retrieve():
 code=f'''import pathlib,tarfile,sys
r=pathlib.Path({STAGE!r})/'data'
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for p in r.glob('result-*.json'):t.add(p,arcname=p.name)
'''
 cmd=['docker','run','--rm','--network','none','--user','10001:10001','--read-only','-v',STAGE+'/data:/work:ro','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',code.replace(repr(STAGE),repr('/work')).replace("/'data'", "")]
 command='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
 r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(command)],capture_output=True,check=True)
 target=HERE/'server-results';target.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as t:
  for m in t:
   p=target/m.name;assert m.isfile() and p.resolve().is_relative_to(target.resolve());p.write_bytes(t.extractfile(m).read())
if __name__=='__main__':
 import sys
 mode=sys.argv[1]
 stage() if mode=='stage' else retrieve() if mode=='retrieve' else upload(sys.argv[2]) if mode=='upload' else run(mode)
