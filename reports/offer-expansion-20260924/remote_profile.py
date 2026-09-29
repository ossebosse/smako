"""Stage current code and private data; never replace a production container."""
import io,json,shlex,subprocess,tarfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
STAGE='/var/tmp/smako-offer-expansion-20260924';IMAGE='smako-willys-candidate:municipality-20260922'
def ssh(code,data=None):
 r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],input=data,capture_output=True)
 print(r.stdout.decode('utf8',errors='replace'),flush=True)
 print(json.dumps({'exit':r.returncode,'stderr':r.stderr.decode('utf8',errors='replace')[-1800:]}),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
def stage():
 buf=io.BytesIO()
 with tarfile.open(fileobj=buf,mode='w:gz') as t:
  for folder in ['backend/app','grocery_data/app','grocery_data/scripts','deploy/scripts']:
   for p in (ROOT/folder).rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:t.add(p,arcname=p.relative_to(ROOT).as_posix())
  for p,name in [(HERE/'profile_job.py','profile_job.py'),(HERE/'evaluate_current_profile.py','evaluate_1520_profile.py'),(ROOT/'reports/coop-1520-20260922/request.json','request.json')]:t.add(p,arcname='evaluation/'+name)
  for arm,roots in [('before',('offer-nutrition-20260924','willys-final-1281','lidl-1281')),('after',('offer-expansion-20260924','willys-final-v2-1281','lidl-v2-1281'))]:
   base,w,l=roots
   for folder,kind in [(w,'willys'),(l,'lidl')]:
    source=ROOT/'reports'/base/folder
    for p in source.rglob('*'):
     if p.is_file() and (p.suffix=='.sqlite' or p.name in {'inventory.json','coverage.json'}):t.add(p,arcname='data/'+arm+'/'+kind+'/'+p.relative_to(source).as_posix())
 code=f'''import io,pathlib,sys,tarfile,subprocess
p=pathlib.Path({STAGE!r});assert (p/'.owner').read_text()=='offer-expansion-20260924'
import os
subprocess.run(['docker','run','--rm','--network','none','-v',str(p)+':/stage','alpine:3.20','chown','-R',str(os.getuid())+':'+str(os.getgid()),'/stage/data'],check=True)
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:
 for m in t.getmembers():
  q=p/m.name;assert m.isfile() and q.resolve().is_relative_to(p)
  q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(t.extractfile(m).read());q.chmod(0o644)
subprocess.run(['docker','run','--rm','--network','none','-v',str(p)+':/stage','alpine:3.20','sh','-c','chown -R 10001:10001 /stage/data'],check=True)
print('staged private candidate')'''
 ssh(code,buf.getvalue())
def upload():
 buf=io.BytesIO()
 with tarfile.open(fileobj=buf,mode='w:gz',compresslevel=1) as t:
  t.add(HERE/'base/refreshed.sqlite',arcname='base/refreshed.sqlite')
  for p in (HERE/'base/raw').rglob('*'):
   if p.is_file():t.add(p,arcname='raw/'+p.relative_to(HERE/'base/raw').as_posix())
 print('upload bytes',len(buf.getvalue()),flush=True)
 code=f'''import io,pathlib,sys,tarfile,subprocess
p=pathlib.Path({STAGE!r})/'data'
import os
subprocess.run(['docker','run','--rm','--network','none','-v',str(p)+':/work','alpine:3.20','chown','-R',str(os.getuid())+':'+str(os.getgid()),'/work'],check=True)
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:
 for m in t.getmembers():
  q=p/m.name;assert m.isfile() and q.resolve().is_relative_to(p)
  q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(t.extractfile(m).read());q.chmod(0o644)
subprocess.run(['docker','run','--rm','--network','none','-v',str(p)+':/work','alpine:3.20','sh','-c','chown -R 10001:10001 /work'],check=True)
print('private refreshed base copied')'''
 ssh(code,buf.getvalue())
def run():
 cmd=['docker','run','--rm','-i','--name','smako-offer-expansion-profile','--user','10001:10001','--read-only','--cpus','2','--memory','5g','--tmpfs','/tmp:rw,size=512m,mode=1777','--network','none','-e','PYTHONPATH=/evaluation:/srv/app/backend:/srv/app','-e','PYTHON_DOTENV_DISABLED=true']
 for src,dst,ro in [('backend/app','/srv/app/backend/app',True),('grocery_data/app','/srv/app/grocery_data/app',True),('grocery_data/scripts','/srv/app/grocery_data/scripts',True),('evaluation','/evaluation',True),('data','/work',False)]:cmd+=['--mount',f'type=bind,source={STAGE}/{src},target={dst}'+(',readonly' if ro else '')]
 cmd+=['--mount','type=bind,source=/srv/smako/data/raw_snapshots,target=/srv/app/var/raw_snapshots,readonly','--entrypoint','/bin/sh',IMAGE,'-c','umask 077; f=$(mktemp); cat > "$f"; set -a; . "$f"; set +a; rm "$f"; exec /opt/ica-venv/bin/python /evaluation/profile_job.py']
 ssh("import subprocess,json\nenv=subprocess.check_output(['docker','exec','-u','0','smako-scheduler-1','cat','/run/grocery-beta-environment'])\nr=subprocess.run("+repr(cmd)+",input=env,capture_output=True);del env\nprint(r.stdout.decode('utf8',errors='replace'));print(r.stderr.decode('utf8',errors='replace')[-5000:]);raise SystemExit(r.returncode)")
def retrieve():
 program="from pathlib import Path;import tarfile,sys\np=Path('/work/profile')\nwith tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:\n for q in p.glob('*.json'):\n  t.add(q,arcname=q.name)"
 cmd=['docker','run','--rm','--network','none','--user','10001:10001','--read-only','--mount',f'type=bind,source={STAGE}/data,target=/work,readonly','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',program]
 code='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
 r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
 dest=HERE/'profile';dest.mkdir(exist_ok=True)
 with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as t:
  for m in t.getmembers():
   p=dest/m.name;assert m.isfile() and p.resolve().is_relative_to(dest.resolve());p.write_bytes(t.extractfile(m).read())
 print('retrieved private profile')
if __name__=='__main__':{'stage':stage,'upload':upload,'run':run,'retrieve':retrieve}[sys.argv[1]]()
