import io,json,subprocess,shlex,tarfile,sys
from pathlib import Path
R=Path(__file__).resolve().parents[2]; O=Path(__file__).parent
STAGE='/var/tmp/smako-lund-integration-20260927'; IMAGE='smako-lund-candidate:integration-20260927'
def remote(code,data=None):
 p=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],input=data,capture_output=True)
 print(p.stdout.decode(errors='replace')); print(p.stderr.decode(errors='replace')[-2500:]); assert p.returncode==0,p.returncode

def scripts():
 b=io.BytesIO()
 with tarfile.open(fileobj=b,mode='w:gz') as t:
  for f in O.glob('*.py'):t.add(f,arcname=f.name)
 remote(f"import pathlib,tarfile,io,sys\np=pathlib.Path({STAGE!r})/'evaluation'\nwith tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:\n for m in t.getmembers():\n  q=p/m.name;assert m.isfile() and q.resolve().is_relative_to(p);q.write_bytes(t.extractfile(m).read());q.chmod(0o644)",b.getvalue())

def stage():
 m=json.loads((O/'source-manifest.json').read_bytes()); b=io.BytesIO()
 with tarfile.open(fileobj=b,mode='w:gz') as t:
  for name in m['files']: t.add(R/name,arcname='code/'+name)
  for f in O.glob('*.py'):t.add(f,arcname='evaluation/'+f.name)
  t.add(R/'reports/coop-1520-20260922/request.json',arcname='evaluation/original-request.json')
 remote(f"""import pathlib,sys,tarfile,io,subprocess
p=pathlib.Path({STAGE!r});p.mkdir(exist_ok=True)
if (p/'.owner').exists():assert (p/'.owner').read_text()=='lund-integration-20260927'
else:(p/'.owner').write_text('lund-integration-20260927')
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:
 for m in t.getmembers():
  q=p/m.name;assert m.isfile() and q.resolve().is_relative_to(p);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(t.extractfile(m).read());q.chmod(0o644)
f=p/'code/Dockerfile';f.write_text('FROM smako-willys-candidate:municipality-20260922\\nUSER root\\nCOPY --chown=10001:10001 . /srv/app/\\nUSER 10001\\nWORKDIR /srv/app\\nENTRYPOINT []\\n')
r=subprocess.run(['docker','build','--network','none','-t',{IMAGE!r},str(p/'code')],capture_output=True);print(r.stdout.decode()[-1500:]);print(r.stderr.decode()[-1000:]);assert r.returncode==0
(p/'data').mkdir(exist_ok=True)
subprocess.run(['docker','run','--rm','--network','none','-v',str(p/'data')+':/new','alpine:3.20','chown','10001:10001','/new'],check=True)
print(subprocess.check_output(['docker','image','inspect',{IMAGE!r},'--format','{{{{.Id}}}}']).decode())
""",b.getvalue())
def run(mode):
 cmd=['docker','run','--rm','-i','--name','smako-lund-integration-'+mode,'--user','10001:10001','--read-only','--cpus','2','--memory','5g','--tmpfs','/tmp:rw,size=512m,mode=1777','--network','none' if mode in {'physical-http','final-http','physical-build','expiry','lifecycle'} else 'bridge','-e','PYTHONPATH=/evaluation:/srv/app/backend:/srv/app','-e','PYTHON_DOTENV_DISABLED=true','-v',STAGE+'/data:/work','-v',STAGE+'/evaluation:/evaluation:ro','-v','/var/tmp/smako-recipe-search-20260927/data/base:/seed:ro','-v','/var/tmp/smako-recipe-search-20260927/before:/rollback:ro','--entrypoint','/bin/sh',IMAGE,'-c','umask 077; f=$(mktemp); cat > "$f"; set -a; . "$f"; set +a; rm "$f"; exec /opt/ica-venv/bin/python /evaluation/'+({'final-http':'http_job.py','relay-retry':'relay_retry_job.py','physical-build':'physical_build_job.py','physical-http':'http_job.py','primat-identity':'primat_identity_job.py','expiry':'expiry_job.py','base-replay':'base_replay_job.py','hemkop-probe':'base_replay_job.py','hemkop-evidence':'hemkop_evidence_job.py','coop-probe':'coop_replay_job.py','coop-evidence':'coop_evidence_job.py','coop-replay':'coop_replay_job.py','inspect':'inspect_job.py','coverage':'coverage_job.py','schema':'schema_job.py','http':'http_job.py','lifecycle':'lifecycle_job.py','cycle-first':'cycle_job.py','cycle-second':'cycle_job.py','cycle-restart':'cycle_job.py'}.get(mode,'job.py'))+' '+mode]
 remote('import subprocess\nenv=subprocess.check_output(["docker","exec","-u","0","smako-scheduler-1","cat","/run/grocery-beta-environment"])\nr=subprocess.run('+repr(cmd)+',input=env,capture_output=True);del env\nprint(r.stdout.decode(errors="replace")[-3000:]);print(r.stderr.decode(errors="replace")[-1500:]);raise SystemExit(r.returncode)')
def upload():
 import hashlib
 files=[f for f in (O/'local-relay/completed').glob('*.smako-source') if not f.name.startswith('.')]
 assert len(files)==1,files
 data=files[0].read_bytes();digest=hashlib.sha256(data).hexdigest()
 code="import pathlib,sys,hashlib;data=sys.stdin.buffer.read();assert hashlib.sha256(data).hexdigest()=="+repr(digest)+";p=pathlib.Path('/work/raw/source-inbox/willys')/"+repr(digest+'.smako-source')+";assert not p.exists();p.write_bytes(data);print('validated local source artifact staged in private inbox')"
 cmd=['docker','run','--rm','-i','--network','none','--user','10001:10001','-v',STAGE+'/data:/work','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',code]
 remote('import subprocess,sys;subprocess.run('+repr(cmd)+',input=sys.stdin.buffer.read(),check=True)',data)
 (O/'relay-upload.json').write_text(json.dumps({'artifact':files[0].name,'sha256':digest,'bytes':len(data),'destination':'isolated Lund inbox, never production push'},indent=2),encoding='utf-8')

def retrieve():
 code=f"""import pathlib,tarfile,sys
p=pathlib.Path('/work')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for f in p.rglob('*'):
  if not f.is_file() or f.suffix not in {{'.json','.png'}}:continue
  if any(x in f.parts for x in ['raw','raw_snapshots']):continue
  if f.stat().st_size<5000000 or f.name=='http-results.json' or f.name.startswith('planner-diagnostic-'):t.add(f,arcname=f.relative_to(p))
"""
 cmd=['docker','run','--rm','--network','none','--user','10001:10001','-v',STAGE+'/data:/work:ro','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',code]
 code='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
 r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
 dest=O/'results';dest.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as t:
  for m in t.getmembers():
   p=dest/m.name;assert m.isfile() and p.resolve().is_relative_to(dest.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
 print('retrieved')
if __name__=='__main__':
 if sys.argv[1]=='run':run(sys.argv[2])
 else:globals()[sys.argv[1]]()
