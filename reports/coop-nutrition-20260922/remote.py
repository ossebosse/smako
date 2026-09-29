"""Isolated test container, production sources read-only. Never deploys."""
import argparse
import io
import json
import shlex
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RUN = 'coop-nutrition-20260922'
STAGE = '/tmp/smako-'+RUN
IMAGE = 'smako-coop-candidate:nutrition-20260922'

def ssh(code, data=None):
    r = subprocess.run(['ssh','-o','BatchMode=yes','smako','python3 -c '+shlex.quote(code)],input=data,capture_output=True,check=False)
    print(r.stdout.decode('utf-8',errors='replace'),flush=True)
    print(json.dumps({'exit':r.returncode,'stderr_bytes':len(r.stderr)}),flush=True)
    if r.returncode:
        raise SystemExit(r.returncode)

def stage():
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as t:
        for folder in ['backend/app','grocery_data/app','grocery_data/scripts','deploy/scripts']:
            for p in (ROOT/folder).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:t.add(p,arcname=p.relative_to(ROOT).as_posix())
        for p in HERE.glob('*.py'):t.add(p,arcname='evaluation/'+p.name)
        for p in HERE.glob('request*.json'):t.add(p,arcname='evaluation/'+p.name)
        t.add(ROOT/'reports/coop-municipality-20260921/acceptance/inventory/inventory.json',arcname='evaluation/inventory.json')
        if (HERE/'coop-local-live/own.sqlite').exists():
            t.add(HERE/'coop-local-live/own.sqlite',arcname='evaluation/coop-own.sqlite')
            t.add(HERE/'coop-local-live/coverage.json',arcname='evaluation/coop-coverage.json')
        t.add(ROOT/'deploy/coop-candidate.Dockerfile',arcname='deploy/coop-candidate.Dockerfile')
        t.add(ROOT/'grocery_data/__main__.py',arcname='grocery_data/__main__.py')
    code=f'''import pathlib,tarfile,io,sys,subprocess
p=pathlib.Path({STAGE!r});marker=p/'.owner'
assert not subprocess.check_output(['docker','ps','-q','--filter','name=^/smako-coop-nutrition-test$']).strip()
if p.exists():assert marker.read_text()=={RUN!r}
else:p.mkdir();marker.write_text({RUN!r})
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as a:
 for m in a.getmembers():
  target=p/m.name
  assert m.isfile() and target.resolve().is_relative_to(p)
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(a.extractfile(m).read());target.chmod(0o644)
subprocess.run(['docker','run','--rm','--network','none','--mount','type=bind,source='+str(p)+',target=/stage','alpine:3.20','sh','-c','mkdir -p /stage/data; chown 10001:10001 /stage/data; chmod 700 /stage/data'],check=True)
print('isolated code staged; existing application unchanged')
'''
    ssh(code,buf.getvalue())

def run(mode):
    cmd=['docker','run','--rm','-i','--name','smako-coop-nutrition-test','--user','10001:10001','--read-only',
         '--cpus','2','--memory','5g','--tmpfs','/tmp:rw,size=512m,mode=1777',
         '--network','bridge' if mode in {'collect','probe','collect-browser','collect-package','collect-package-smoke'} else 'none',
         '-e','PYTHONPATH=/evaluation:/srv/app/backend:/srv/app','-e','PYTHON_DOTENV_DISABLED=true',
         '-e','ICA_FLYER_PAID_ENABLED=false','-e','ICA_FLYER_VISUAL_COMMAND_JSON=',
         '-e','ICA_AREA_OFFER_CANDIDATES_ENABLED=false','-e','ICA_STRUCTURED_OFFERS_ENABLED=false']
    for source,dest,readonly in [
        (STAGE+'/backend/app','/srv/app/backend/app',True),
        (STAGE+'/grocery_data/app','/srv/app/grocery_data/app',True),
        (STAGE+'/grocery_data/scripts','/srv/app/grocery_data/scripts',True),
        (STAGE+'/deploy/scripts','/srv/app/deploy/scripts',True),
        (STAGE+'/grocery_data/__main__.py','/srv/app/grocery_data/__main__.py',True),
        (STAGE+'/evaluation','/evaluation',True),(STAGE+'/data','/work',False),
        ('/srv/smako/data/raw_snapshots','/srv/app/var/raw_snapshots',True),
        ('/srv/smako/data/grocery','/srv/app/var/grocery',True),
        ('/srv/smako/data/price_universes','/srv/app/var/price_universes',True),
        ('/srv/smako/data/price_universes/.refresh-locks','/srv/app/var/price_universes/.refresh-locks',False)]:
        if dest.startswith(('/srv/app/backend/app','/srv/app/grocery_data','/srv/app/deploy/scripts')):
            continue  # Exercise packaged code, never a developer code overlay.
        cmd+=['--mount',f'type=bind,source={source},target={dest}'+(',readonly' if readonly else '')]
    image = 'smako-ica-shadow:20260915' if mode=='collect-browser' else IMAGE
    executable = '/opt/ica-venv/bin/python' if mode=='collect-browser' else '/opt/ica-venv/bin/python'
    cmd+=['--entrypoint','/bin/sh',image,'-c','umask 077; f=$(mktemp); cat > "$f"; set -a; . "$f"; set +a; rm "$f"; exec '+executable+' /evaluation/job.py '+shlex.quote(mode)]
    code="import subprocess,json\nenv=subprocess.check_output(['docker','exec','-u','0','smako-scheduler-1','cat','/run/grocery-beta-environment'])\n"
    code+='r=subprocess.run('+repr(cmd)+',input=env,capture_output=True);del env\n'
    code+='print(r.stdout.decode("utf8",errors="replace"));print(json.dumps({"exit":r.returncode,"stderr_bytes":len(r.stderr)}));raise SystemExit(r.returncode)'
    ssh(code)

def build():
    code="""import subprocess,pathlib,json
p=pathlib.Path(STAGE_VALUE)
(p/'.dockerignore').write_text(chr(10).join(['data','evaluation','.owner','']))
base=subprocess.check_output(['docker','inspect','--format','{{.Id}}','smako-ica-shadow:20260915'],text=True).strip()
assert base=='sha256:4fdaeeda6c1db2c0125a15bfc964cc57a2134154a4546a6c02a6d5d03208fdd5', 'browser base changed; review required'
tag='smako-coop-browser-base:'+base.split(':')[1]
subprocess.run(['docker','tag',base,tag],check=True)
subprocess.run(['docker','build','--network','none','--build-arg','BROWSER_BASE='+tag,'-f',str(p/'deploy/coop-candidate.Dockerfile'),'-t',IMAGE_VALUE,str(p)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
built=subprocess.check_output(['docker','inspect','--format','{{.Id}}',IMAGE_VALUE],text=True).strip()
help=subprocess.run(['docker','run','--rm','--network','none','--read-only',IMAGE_VALUE,'--help'],capture_output=True)
assert help.returncode==0
print(json.dumps({'base_image':base,'candidate_image':built,'help_exit':help.returncode,'production_activation':False}))
""".replace('STAGE_VALUE',repr(STAGE)).replace('IMAGE_VALUE',repr(IMAGE))
    ssh(code)

def retrieve():
    program="""import pathlib,sys,tarfile
root=pathlib.Path('/work')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for p in root.rglob('*.json'):
  if 'artifacts' in p.parts or 'sources' in p.parts or 'raw' in p.parts or p.name=='frozen-primat.json' or p.name.endswith('-source-universe.json'):continue
  t.add(p,arcname=p.relative_to(root).as_posix())
"""
    cmd=['docker','run','--rm','--network','none','--user','10001:10001','--read-only',
         '--mount',f'type=bind,source={STAGE}/data,target=/work,readonly','--entrypoint','python',IMAGE,'-c',program]
    code='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
    result=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
    root=HERE/'server-results';root.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout),mode='r:gz') as t:
        for m in t.getmembers():
            p=root/m.name
            assert m.isfile() and p.resolve().is_relative_to(root.resolve())
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(t.extractfile(m).read())
    print('retrieved sanitized isolated results only')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode');a=p.parse_args()
    build() if a.mode=='build' else stage() if a.mode=='stage' else retrieve() if a.mode=='retrieve' else run(a.mode)
