import io,json,subprocess,shlex,tarfile,sys
from pathlib import Path
O=Path(__file__).parent
STAGE='/var/tmp/smako-coop-source-binding-20260928'
PRIOR='/var/tmp/smako-lund-base-strategy-20260928/data'
IMAGE='sha256:fdaf9c4a61e97aecef0d86c2e8feb2424e2d475287dece0bac03ab9f800a4781'
def remote(code,data=None):
 p=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],input=data,capture_output=True)
 print(p.stdout.decode(errors='replace')[-5000:]);print(p.stderr.decode(errors='replace')[-1800:]);assert p.returncode==0,p.returncode
def scripts():
 b=io.BytesIO()
 with tarfile.open(fileobj=b,mode='w:gz') as t:
  for f in [*O.glob('*.py'),O/'policy.json',O/'original-request.json']:t.add(f,arcname=f.name)
 remote(f"import pathlib,tarfile,io,sys\np=pathlib.Path({STAGE!r});p.mkdir(exist_ok=True)\nf=p/'.owner'\nif f.exists():assert f.read_text()=='coop-source-binding-20260928'\nelse:f.write_text('coop-source-binding-20260928')\np=p/'evaluation';p.mkdir(exist_ok=True)\nwith tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:\n for m in t.getmembers():\n  q=p/m.name;assert m.isfile() and q.resolve().is_relative_to(p);q.write_bytes(t.extractfile(m).read());q.chmod(0o644)",b.getvalue())
def run(mode):
 script={'publish':'refresh_job.py','fault-final':'refresh_job.py','source-audit':'source_audit_job.py','retry':'refresh_job.py','fault':'refresh_job.py','diagnostic':'diagnostic_job.py','initialize':'initialize_job.py','refresh':'refresh_job.py','second':'refresh_job.py','restart':'refresh_job.py','http':'http_job.py','contract':'contract_job.py','coverage':'coverage_job.py','faults':'faults_job.py','expiry':'expiry_job.py','lifecycle':'lifecycle_job.py','restore-raw':'restore_raw_job.py','coop-fault':'coop_fault_job.py'}[mode]
 cmd=['docker','run','--rm','-i','--name','smako-coop-binding-'+mode,'--user','10001:10001','--read-only','--cpus','2','--memory','5g','--tmpfs','/tmp:rw,size=512m,mode=1777','--network','bridge' if mode in {'refresh','retry','contract','diagnostic'} else 'none','-e','PYTHONPATH=/evaluation:/srv/app/backend:/srv/app','-e','PYTHON_DOTENV_DISABLED=true','-v',STAGE+'/data:/work','-v',STAGE+'/evaluation:/evaluation:ro','-v',PRIOR+(':/prior:rw' if mode=='initialize' else ':/prior:ro'),'--entrypoint','/bin/sh',IMAGE,'-c','umask 077; f=$(mktemp); cat > "$f"; set -a; . "$f"; set +a; rm "$f"; exec /opt/ica-venv/bin/python /evaluation/'+script+' '+mode]
 remote('import subprocess\nenv=subprocess.check_output(["docker","exec","-u","0","smako-scheduler-1","cat","/run/grocery-beta-environment"])\nr=subprocess.run('+repr(cmd)+',input=env,capture_output=True);del env\nprint(r.stdout.decode(errors="replace")[-5000:]);print(r.stderr.decode(errors="replace")[-1800:]);raise SystemExit(r.returncode)')
def prepare():
 remote(f"import pathlib,subprocess\np=pathlib.Path({STAGE!r});assert (p/'.owner').read_text()=='coop-source-binding-20260928';(p/'data').mkdir(exist_ok=True);subprocess.run(['docker','run','--rm','--network','none','-v',str(p/'data')+':/new','alpine:3.20','chown','10001:10001','/new'],check=True)")
def retrieve():
 code="""from pathlib import Path
import tarfile,sys
p=Path('/work')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for f in p.rglob('*.json'):
  if any(x in f.parts for x in ['raw','raw_snapshots','artifacts','reference-source']):continue
  if f.stat().st_size<6000000 or f.name.startswith('http-results') or f.name.startswith('planner-diagnostic-'):t.add(f,arcname=f.relative_to(p))
"""
 cmd=['docker','run','--rm','--network','none','--user','10001:10001','-v',STAGE+'/data:/work:ro','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',code]
 r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote('import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))')],capture_output=True,check=True)
 dest=O/'results';dest.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as t:
  for m in t.getmembers():
   p=dest/m.name;assert m.isfile() and p.resolve().is_relative_to(dest.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
 print('retrieved')
if __name__=='__main__':run(sys.argv[2]) if sys.argv[1]=='run' else globals()[sys.argv[1]]()
