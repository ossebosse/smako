"""Application-only hotfix using the existing compose and shared operation lock.

Stage is read-only to running services. Activate requires explicit mode and a
successful recorded candidate button run. Rollback never restores databases.
"""
import argparse
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path('/opt/smako')
EVIDENCE = ROOT/'evidence/public-menu-20261002'
STATE = EVIDENCE/'deployment-before.private.json'


def run(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def inspect(name):
    return json.loads(run(['docker', 'inspect', name]))[0]


def inventory():
    code = '''import hashlib,json,sqlite3
from app.config import get_settings
s=get_settings()
with sqlite3.connect(s.plan_store_path) as c:
 rows=c.execute('SELECT * FROM consumer_plan_revisions').fetchall()
 print(json.dumps({'integrity':c.execute('PRAGMA integrity_check').fetchone()[0], 'plan_hashes':sorted(hashlib.sha256(json.dumps(row).encode()).hexdigest() for row in rows), 'price_manifests':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (s.price_universe_cache_root/'active').glob('*.json')}}))
'''
    return json.loads(run(['docker','exec','-i','smako-app-1','python','-'],input=code))


def compose_config(release, extra=()):
    command = ['docker','compose','-p','smako','--profile','ops','--env-file',str(release/'activation-private.env'),
               '-f',str(release/'deploy/compose.yaml'),'-f',str(ROOT/'compose.vps.yaml'),
               '-f',str(release/'deploy/compose.release.yaml'),'-f',str(release/'keep-existing-proxy.yaml'),*extra,
               'config','--format','json']
    result = subprocess.run(command,capture_output=True,text=True,check=False)
    if result.returncode:
        p=EVIDENCE/'compose-error.private'
        p.write_text(result.stderr)
        p.chmod(0o600)
        raise RuntimeError('Compose render failed; private error retained')
    return json.loads(result.stdout)


def atomic_text(path, text, mode):
    temporary=path.with_name(path.name+'.public-menu-next')
    with temporary.open('x') as out:
        temporary.chmod(mode)
        out.write(text)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary,path)


def switch(release, wrapper):
    temporary=ROOT/'current-public-menu-next'
    assert not temporary.exists() and not temporary.is_symlink()
    temporary.symlink_to(release)
    os.replace(temporary,ROOT/'current')
    atomic_text(ROOT/'compose',wrapper,0o755)
    subprocess.run([str(ROOT/'compose'),'config','--quiet'],check=True)
    subprocess.run([str(ROOT/'compose'),'up','-d','--no-build','--no-deps','--force-recreate','app'],check=True)
    for _ in range(55):
        try:
            with urllib.request.urlopen('https://beta.smako.nu/ready',timeout=3) as response:
                if response.status==200:
                    return
        except (OSError,TimeoutError):
            time.sleep(1)
    raise RuntimeError('Readiness did not recover')


def stage(candidate):
    old=(ROOT/'current').resolve()
    release=Path(candidate['release'])
    assert release.is_relative_to(ROOT/'releases') and old!=release
    private=release/'activation-private.env'
    private.write_bytes((old/'activation-private.env').read_bytes())
    private.chmod(0o600)
    (release/'keep-existing-proxy.yaml').write_bytes((old/'keep-existing-proxy.yaml').read_bytes())
    override=release/'public-menu-app.yaml'
    override.write_text('services:\n  app:\n    image: '+candidate['image']+'\n    environment:\n      BUILD_ID: '+candidate['commit']+'\n')
    old_override=old/'public-menu-app.yaml'
    before=compose_config(old, ('-f',str(old_override)) if old_override.exists() else ())
    after=compose_config(release,('-f',str(override)))
    assert set(before['services'])==set(after['services']) and 'caddy' not in after['services']
    for name in before['services']:
        expected=json.loads(json.dumps(before['services'][name]))
        if name=='app':
            expected['image']=candidate['image']
            expected['environment']['BUILD_ID']=candidate['commit']
        assert expected==after['services'][name], ('Unexpected service change',name)
    return {'only_image_and_app_build_changed':True,'release':str(release),'candidate':candidate}


def main():
    global EVIDENCE, STATE
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['stage','activate','rollback'])
    parser.add_argument('--evidence-root',type=Path,default=EVIDENCE)
    args=parser.parse_args()
    EVIDENCE=args.evidence_root.resolve()
    assert EVIDENCE.is_relative_to(ROOT/'evidence')
    STATE=EVIDENCE/'deployment-before.private.json'
    candidate=json.loads((EVIDENCE/'candidate-image.json').read_text())
    if args.mode=='stage':
        result=stage(candidate)
        (EVIDENCE/'deployment-stage.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
        return
    if args.mode=='activate':
        assert not STATE.exists(), 'Do not overwrite the original rollback state'
        tested=json.loads((EVIDENCE/'candidate-button-acceptance.json').read_text())
        assert tested['status']==201 and tested['body']['plan']['build_id']==candidate['commit']
        assert tested['identical_reload'] and all(tested['acceptance'].values())
        stage(candidate)
    app=inspect('smako-app-1')
    lock_code='''from pathlib import Path
import sys
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
lock=RefreshRunLock(production_refresh_lock_path(Path('/srv/app/var/grocery/grocery_data.sqlite'),Path('/srv/app/var/price_universes')))
lock.acquire()
try:
 print('LOCKED',flush=True)
 sys.stdin.readline()
finally:
 lock.release()
'''
    helper=subprocess.Popen(['docker','run','--rm','-i','--network','none','--user','0','--volumes-from','smako-app-1:ro',
                             '-v','/srv/smako/data/price_universes/.refresh-locks:/srv/app/var/price_universes/.refresh-locks:rw',
                             '--entrypoint','python',app['Image'],'-c',lock_code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        assert helper.stdout.readline().strip()=='LOCKED', 'Shared operation lock unavailable'
        before=inventory()
        assert before['integrity']=='ok'
        scheduler=inspect('smako-scheduler-1')['Id']
        proxy=inspect('smako-caddy-1')['Id']
        if args.mode=='activate':
            backup=EVIDENCE/'rollback-state'
            backup.mkdir(mode=0o700,exist_ok=False)
            plan_path=dict(v.split('=',1) for v in app['Config']['Env'])['PLAN_STORE_PATH']
            backup_code="import sqlite3,os; source=sqlite3.connect('file:'+"+repr(plan_path)+"+'?mode=ro',uri=True); target=sqlite3.connect('/backup/plans.sqlite3'); source.backup(target); target.close(); source.close(); os.chmod('/backup/plans.sqlite3',0o600)"
            subprocess.run(['docker','run','--rm','--network','none','--user','0','--volumes-from','smako-app-1:ro',
                            '-v',str(backup)+':/backup',app['Image'],'python','-c',backup_code],check=True)
            original={**before,'source':str((ROOT/'current').resolve()),'wrapper':(ROOT/'compose').read_text(),
                      'image':app['Image'],'scheduler_id':scheduler,'proxy_id':proxy}
            STATE.write_text(json.dumps(original))
            STATE.chmod(0o600)
            wrapper=original['wrapper']
            if '/opt/smako/current/public-menu-app.yaml' not in wrapper:
                wrapper=wrapper.replace(' "$@"',' -f /opt/smako/current/public-menu-app.yaml "$@"')
                assert wrapper!=original['wrapper']
            try:
                switch(Path(candidate['release']),wrapper)
            except Exception:
                switch(Path(original['source']),original['wrapper'])
                raise
        else:
            original=json.loads(STATE.read_text())
            switch(Path(original['source']),original['wrapper'])
        after=inventory()
        assert set(before['plan_hashes'])<=set(after['plan_hashes'])
        assert set(original['plan_hashes'])<=set(after['plan_hashes'])
        assert before['price_manifests']==after['price_manifests']
        assert scheduler==inspect('smako-scheduler-1')['Id'] and proxy==inspect('smako-caddy-1')['Id']
        assert after['integrity']=='ok'
        active=inspect('smako-app-1')
        old_env=dict(v.split('=',1) for v in app['Config']['Env'])
        new_env=dict(v.split('=',1) for v in active['Config']['Env'])
        old_env.pop('BUILD_ID',None)
        new_env.pop('BUILD_ID',None)
        assert old_env==new_env, 'Runtime environment changed beyond build identity'
        result={'mode':args.mode,'image':active['Image'],'source':str((ROOT/'current').resolve()),
                'prior_revisions_preserved':len(original['plan_hashes']),'all_previous_revisions_preserved':True,
                'scheduler_unchanged':True,'proxy_unchanged':True,'environment_preserved':True,
                'price_manifests_unchanged':True,'integrity':'ok','shared_operation_lock':True}
        (EVIDENCE/('deployment-'+args.mode+'.json')).write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    finally:
        if helper.poll() is None:
            helper.stdin.write('RELEASE\n')
            helper.stdin.flush()
        helper.wait(timeout=15)


if __name__=='__main__':
    main()
