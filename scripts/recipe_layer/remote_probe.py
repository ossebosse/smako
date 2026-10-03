"""Isolated, bounded recipe-layer evaluation helpers. Never activate or collect."""
import argparse
import hashlib
import io
import json
import re
import shlex
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STAGE = '/var/tmp/smako-complete-recipes-20261002'
IMAGE = 'sha256:80e8ba59c9b04c8bff668062da2bf1937eae236881472449e2a0180f42387180'


def ssh(code, data=None):
    result = subprocess.run(['ssh', '-oBatchMode=yes', 'smako', 'python3 -c ' + shlex.quote(code)], input=data, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-4000:] + result.stdout.decode(errors='replace')[-2000:])
    return result.stdout


def stage(arm):
    assert re.fullmatch(r'(?:baseline|candidate)(?:-[a-z0-9-]+)?', arm)
    payload = io.BytesIO()
    files = {}
    with tarfile.open(fileobj=payload, mode='w:gz') as archive:
        for folder in ('backend/app', 'grocery_data/app', 'scripts/recipe_layer'):
            for path in (ROOT / folder).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    archive.add(path, arcname=f'{arm}/{path.relative_to(ROOT).as_posix()}')
                    files[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        version = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   'files': files, 'source_sha256': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}
        data = json.dumps(version, indent=2).encode()
        info = tarfile.TarInfo(f'{arm}/scripts/recipe_layer/stage.json')
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    print(ssh(f"""import pathlib,sys,tarfile,io
p=pathlib.Path({STAGE!r});p.mkdir(exist_ok=True)
owner=p/'.owner'
if owner.exists(): assert owner.read_text()=='complete-recipes-20261002'
else: owner.write_text('complete-recipes-20261002')
assert not (p/{arm!r}).exists(), 'A staged evaluation arm is immutable; choose a new arm name'
with tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz') as archive:
 for m in archive.getmembers():
  out=(p/m.name).resolve();assert m.isfile() and out.is_relative_to(p)
  out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(archive.extractfile(m).read());out.chmod(0o644)
print('staged '+{arm!r})""", payload.getvalue()).decode())


def freeze():
    command = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '3g',
               '--read-only', '--user', '0:0', '--tmpfs', '/tmp:rw,size=128m',
               '-e', 'PYTHON_DOTENV_DISABLED=1', '-e', 'PYTHONPATH=/srv/app/backend:/srv/app',
               '-v', STAGE + '/baseline/scripts/recipe_layer:/evaluation:ro',
               '-v', STAGE + '/inputs:/work',
               '-v', '/srv/smako/data/price_universes:/source/price_universes:ro',
               '-v', '/srv/smako/data/grocery:/source/grocery:ro',
               '-v', '/srv/smako/data/raw_snapshots:/source/raw_snapshots:ro',
               '--entrypoint', 'python', IMAGE, '/evaluation/freeze_inputs.py']
    print(ssh(f"""import pathlib,subprocess
p=pathlib.Path({STAGE!r});assert (p/'.owner').read_text()=='complete-recipes-20261002'
(p/'inputs').mkdir(exist_ok=False)
subprocess.run({command!r},check=True)""").decode())


def run(arm, script, arguments):
    assert re.fullmatch(r'(?:baseline|candidate)(?:-[a-z0-9-]+)?', arm)
    command = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '2', '--memory', '3g',
               '--read-only', '--user', '0:0', '--tmpfs', '/tmp:rw,size=512m',
               '-e', 'PYTHON_DOTENV_DISABLED=1', '-e', 'PYTHONPATH=/srv/app/backend:/srv/app',
               '-e', 'GROCERY_DATABASE_URL=sqlite:////inputs/grocery.sqlite',
               '-e', 'GROCERY_RAW_SNAPSHOT_ROOT=/inputs/raw',
               '-v', STAGE + '/inputs:/inputs:ro', '-v', STAGE + '/results:/results',
               '-v', STAGE + f'/{arm}/backend/app:/srv/app/backend/app:ro',
               '-v', STAGE + f'/{arm}/grocery_data/app:/srv/app/grocery_data/app:ro',
               '-v', STAGE + f'/{arm}/scripts/recipe_layer:/evaluation:ro',
               '--entrypoint', 'python', IMAGE, '/evaluation/' + script, *arguments]
    print(ssh(f"""import pathlib,subprocess
p=pathlib.Path({STAGE!r});assert (p/'.owner').read_text()=='complete-recipes-20261002'
(p/'results').mkdir(exist_ok=True)
subprocess.run({command!r},check=True)""").decode())


def retrieve():
    command = ['docker', 'run', '--rm', '--network', 'none', '--read-only', '--user', '0:0',
               '-v', STAGE + '/results:/results:ro', '-v', STAGE + '/inputs:/inputs:ro',
               '--entrypoint', 'python', IMAGE, '-c',
               "import tarfile,sys;from pathlib import Path\nwith tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:\n for p in Path('/results').rglob('*'):\n  if p.is_file():t.add(p,arcname='results/'+p.relative_to('/results').as_posix())\n for name in ('freeze.json','manifest.json'):t.add('/inputs/'+name,arcname=name)"]
    data = ssh('import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output(' + repr(command) + '))')
    target = ROOT / '.local/complete-recipes-20261002'
    target.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive.getmembers():
            path = (target / member.name).resolve()
            assert member.isfile() and path.is_relative_to(target.resolve())
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(archive.extractfile(member).read())
    print(json.dumps({'retrieved_to': str(target)}))


def serve(arm, *, stop=False, feature_disabled=False):
    assert re.fullmatch(r'candidate(?:-[a-z0-9-]+)?', arm)
    name = 'smako-complete-recipes-isolated'
    # Dedicated test container only. Existing application/scheduler containers
    # are never inspected for credentials, stopped, replaced or reconfigured.
    command = ['docker', 'run', '-d', '--name', name,
               '--label', 'smako.test=complete-recipes-20261002',
               '--cpus', '2', '--memory', '3g', '--read-only', '--user', '0:0',
               '--tmpfs', '/tmp:rw,size=512m', '-p', '127.0.0.1:18122:8000',
               '-e', 'PYTHON_DOTENV_DISABLED=1', '-e', 'PYTHONPATH=/srv/app/backend:/srv/app',
               '-e', 'SMAKO_REPLAY_COMPLETE_RECIPES=' + ('false' if feature_disabled else 'true'),
               '-v', STAGE + '/inputs:/inputs:ro', '-v', STAGE + '/browser-state:/state',
               '-v', STAGE + '/results:/results',
               '-v', STAGE + f'/{arm}/backend/app:/srv/app/backend/app:ro',
               '-v', STAGE + f'/{arm}/grocery_data/app:/srv/app/grocery_data/app:ro',
               '-v', STAGE + f'/{arm}/scripts/recipe_layer:/evaluation:ro',
               '--entrypoint', 'python', IMAGE, '/evaluation/serve.py']
    print(ssh(f"""import json,pathlib,subprocess
p=pathlib.Path({STAGE!r});assert (p/'.owner').read_text()=='complete-recipes-20261002'
(p/'browser-state').mkdir(exist_ok=True)
r=subprocess.run(['docker','inspect',{name!r}],capture_output=True,text=True)
if r.returncode==0:
 data=json.loads(r.stdout)[0];assert data['Config']['Labels'].get('smako.test')=='complete-recipes-20261002'
 subprocess.run(['docker','stop',{name!r}],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['docker','rm',{name!r}],check=True,stdout=subprocess.DEVNULL)
if not {stop!r}: subprocess.run({command!r},check=True)
else: print('isolated container stopped; all plan revisions retained')""").decode())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('stage', 'freeze', 'run', 'retrieve', 'serve', 'stop'))
    parser.add_argument('--arm', default='candidate')
    parser.add_argument('--script', default='benchmark.py')
    parser.add_argument('--feature-disabled', action='store_true')
    parser.add_argument('arguments', nargs='*')
    args = parser.parse_args()
    if args.action == 'stage':
        stage(args.arm)
    elif args.action == 'freeze':
        freeze()
    elif args.action == 'run':
        run(args.arm, args.script, args.arguments)
    elif args.action in {'serve', 'stop'}:
        serve(args.arm, stop=args.action == 'stop', feature_disabled=args.feature_disabled)
    else:
        retrieve()
