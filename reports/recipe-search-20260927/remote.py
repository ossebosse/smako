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
STAGE = '/var/tmp/smako-recipe-search-20260927'
IMAGE = 'smako-willys-candidate:municipality-20260922'


def ssh(code, data=None):
    r = subprocess.run(['ssh', '-oBatchMode=yes', 'smako', 'python3 -c '+shlex.quote(code)], input=data, capture_output=True)
    print(r.stdout.decode('utf8', errors='replace'), flush=True)
    print(json.dumps({'exit':r.returncode,'stderr':r.stderr.decode('utf8', errors='replace')[-2500:]}), flush=True)
    if r.returncode: raise SystemExit(r.returncode)


def initialize():
    ssh(f"""from pathlib import Path
import subprocess
p=Path({STAGE!r});p.mkdir(exist_ok=False);(p/'.owner').write_text('recipe-search-20260927');(p/'data').mkdir()
old=Path('/var/tmp/smako-recipe-resolution-20260926');assert (old/'.owner').read_text()=='recipe-resolution-20260926'
subprocess.run(['docker','run','--rm','--network','none','-v',str(old/'data')+':/old:ro','-v',str(p/'data')+':/new','alpine:3.20','sh','-c','cp -a /old/base /new/base && cp -a /old/raw /new/raw && cp /old/universe.json /new/universe.json && chown -R 10001:10001 /new'],check=True)
print('private baseline copied; prior release read-only')""")


def stage(arm):
    base=R/'baseline-code' if arm=='before' else ROOT
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w:gz') as t:
        for folder in ['backend/app','grocery_data/app','grocery_data/scripts']:
            for p in (base/folder).rglob('*'):
                if p.is_file() and '__pycache__' not in p.parts:t.add(p,arcname=arm+'/'+p.relative_to(base).as_posix())
        for p in ['reference_current_job.py','probe_code_only_job.py','http_rescued_job.py','inspect_candidates_job.py','profile_search_job.py','profile_job.py','evaluate_profile.py','http_job.py','probe_job.py','http_generated_job.py','raw_probe_job.py','diagnose_job.py','search_job.py','ancillary_job.py','same_menu_job.py','http_cream_job.py','final_verify_job.py','rebuild_evidence_job.py','composite_final_job.py','inspect_rebuild_job.py']:
            t.add(R/p,arcname='evaluation/'+p)
        t.add(R/'baseline/all-84.json',arcname='evaluation/search-baseline-cases.json')
        t.add(R/'baseline/all-84-diagnostics.json',arcname='evaluation/search-baseline-diagnostics.json')
        t.add(ROOT/'reports/recipe-preparation-20260926/profile/all-84.json',arcname='evaluation/prior-cases.json')
        t.add(ROOT/'reports/personal-offers-20260926/preparation-review.json',arcname='evaluation/original-rejections.json')
        t.add(ROOT/'reports/coop-1520-20260922/request.json',arcname='evaluation/original-request.json')
    ssh(f"""import pathlib,sys,tarfile,io
p=pathlib.Path({STAGE!r});assert (p/'.owner').read_text()=='recipe-search-20260927'
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as t:
 for m in t.getmembers():
  q=p/m.name;assert m.isfile() and q.resolve().is_relative_to(p)
  q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(t.extractfile(m).read());q.chmod(0o644)
print('staged {arm}')""",buf.getvalue())


def run(arm, job="profile_job.py"):
    cmd=['docker','run','--rm','-i','--name','smako-recipe-search-profile','--user','10001:10001','--read-only','--cpus','2','--memory','5g','--tmpfs','/tmp:rw,size=512m,mode=1777','--network','none','-e','PYTHONPATH=/evaluation:/srv/app/backend:/srv/app','-e','PYTHON_DOTENV_DISABLED=true']
    for src,dst,ro in [(arm+'/backend/app','/srv/app/backend/app',True),(arm+'/grocery_data/app','/srv/app/grocery_data/app',True),(arm+'/grocery_data/scripts','/srv/app/grocery_data/scripts',True),('before/backend/app','/rollback/backend/app',True),('before/grocery_data/app','/rollback/grocery_data/app',True),('before/grocery_data/scripts','/rollback/grocery_data/scripts',True),('evaluation','/evaluation',True),('data','/work',False)]:
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
    if action=='reference_current': run('after','reference_current_job.py')
    elif action=='final_code_only_probe': run('after','probe_code_only_job.py')
    elif action=='http_rescued': run('after','http_rescued_job.py')
    elif action=='inspect_candidates': run('before','inspect_candidates_job.py')
    elif action=='profile_search': run('before','profile_search_job.py')
    elif action=='fallback_final': run('after','composite_final_job.py --fallback-guard')
    elif action=='identity_final': run('after','composite_final_job.py --identity-guard')
    elif action=='inspect_rebuild': run('after','inspect_rebuild_job.py')
    elif action=='composite_final': run('after','composite_final_job.py')
    elif action=='rebuild_evidence': run('after','rebuild_evidence_job.py')
    elif action=='final_probe': run('after','final_verify_job.py --probe-only')
    elif action=='final_verify': run('after','final_verify_job.py')
    elif action=='http_cream': run('after','http_cream_job.py')
    elif action=='same_menu': run('after','same_menu_job.py')
    elif action=='ancillary': run(sys.argv[2],'ancillary_job.py')
    elif action=='search': run('after','search_job.py')
    elif action=='diagnose': run(sys.argv[2] if len(sys.argv)>2 else 'after','diagnose_job.py')
    elif action=='raw_probe': run('after','raw_probe_job.py')
    elif action=='http_generated': run('after','http_generated_job.py')
    elif action=='probe': run('after', 'probe_job.py')
    elif action in {'stage','run','http'}:globals()[action](sys.argv[2])
    else:globals()[action]()
