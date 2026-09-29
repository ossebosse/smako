"""Private, network-disabled baseline/candidate profile; no production mutation."""
import io
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
R = Path(__file__).parent
STAGE = '/var/tmp/smako-personal-offers-20260926'
IMAGE = 'smako-willys-candidate:municipality-20260922'


def ssh(code, data=None):
    r = subprocess.run(['ssh', '-oBatchMode=yes', 'smako', 'python3 -c '+shlex.quote(code)], input=data, capture_output=True)
    print(r.stdout.decode('utf8', errors='replace'), flush=True)
    print(json.dumps({'exit':r.returncode,'stderr':r.stderr.decode('utf8', errors='replace')[-2500:]}), flush=True)
    if r.returncode: raise SystemExit(r.returncode)


def initialize():
    ssh(f"""from pathlib import Path
import subprocess
p=Path({STAGE!r});p.mkdir(exist_ok=False);(p/'.owner').write_text('personal-offers-20260926');(p/'data').mkdir()
old=Path('/var/tmp/smako-purchase-planning-20260925');assert (old/'.owner').read_text()=='purchase-planning-20260925'
subprocess.run(['docker','run','--rm','--network','none','-v',str(old/'data')+':/old:ro','-v',str(p/'data')+':/new','alpine:3.20','sh','-c','cp -a /old/base /new/base && cp -a /old/raw /new/raw && cp /old/profile/after-universe.json /new/universe.json && chown -R 10001:10001 /new'],check=True)
print('private baseline copied; prior release read-only')""")


def stage(arm):
    base=R/'baseline-code' if arm=='before' else ROOT
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as t:
        for folder in ['backend/app','grocery_data/app','grocery_data/scripts']:
            for p in (base/folder).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:t.add(p,arcname=arm+'/'+p.relative_to(base).as_posix())
        for p in ['profile_job.py','evaluate_profile.py','http_job.py']:
            t.add(R/p,arcname='evaluation/'+p)
        t.add(ROOT/'reports/coop-1520-20260922/request.json',arcname='evaluation/original-request.json')
    ssh(f"""import pathlib,sys,tarfile,io
p=pathlib.Path({STAGE!r});assert (p/'.owner').read_text()=='personal-offers-20260926'
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:
 for m in t.getmembers():
  q=p/m.name;assert m.isfile() and q.resolve().is_relative_to(p)
  q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(t.extractfile(m).read());q.chmod(0o644)
print('staged {arm}')""",buf.getvalue())


def run(arm, job="profile_job.py"):
    cmd=['docker','run','--rm','-i','--name','smako-personal-offers-profile','--user','10001:10001','--read-only','--cpus','2','--memory','5g','--tmpfs','/tmp:rw,size=512m,mode=1777','--network','none','-e','PYTHONPATH=/evaluation:/srv/app/backend:/srv/app','-e','PYTHON_DOTENV_DISABLED=true']
    for src,dst,ro in [(arm+'/backend/app','/srv/app/backend/app',True),(arm+'/grocery_data/app','/srv/app/grocery_data/app',True),(arm+'/grocery_data/scripts','/srv/app/grocery_data/scripts',True),('evaluation','/evaluation',True),('data','/work',False)]:
        cmd+=['--mount',f'type=bind,source={STAGE}/{src},target={dst}'+(',readonly' if ro else '')]
    cmd+=['--entrypoint','/bin/sh',IMAGE,'-c','umask 077; f=$(mktemp); cat > "$f"; set -a; . "$f"; set +a; rm "$f"; exec /opt/ica-venv/bin/python /evaluation/'+job+' '+arm]
    ssh("import subprocess\nenv=subprocess.check_output(['docker','exec','-u','0','smako-scheduler-1','cat','/run/grocery-beta-environment'])\nr=subprocess.run("+repr(cmd)+",input=env,capture_output=True);del env\nprint(r.stdout.decode('utf8',errors='replace'));print(r.stderr.decode('utf8',errors='replace')[-5000:]);raise SystemExit(r.returncode)")


def http(arm):
    run(arm, 'http_job.py')


def retrieve():
    cmd=['docker','run','--rm','--network','none','--user','10001:10001','--read-only','-v',STAGE+'/data:/work:ro','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',"from pathlib import Path;import tarfile,sys\nwith tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:\n for p in Path('/work/profile').glob('*.json'):t.add(p,arcname=p.name)"]
    code='import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+'))'
    r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
    target=R/'profile';target.mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as t:
        for m in t.getmembers():
            p=target/m.name;assert m.isfile() and p.resolve().is_relative_to(target.resolve());p.write_bytes(t.extractfile(m).read())
    print('retrieved')


if __name__=='__main__':
    action=sys.argv[1]
    if action in {'stage','run','http'}:globals()[action](sys.argv[2])
    else:globals()[action]()
