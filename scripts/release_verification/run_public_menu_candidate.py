"""Run the verified candidate image on loopback, isolated state, no source writers."""
import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--name', required=True)
parser.add_argument('--evidence-root', type=Path, default=Path('/opt/smako/evidence/public-menu-20261002'))
args = parser.parse_args()
assert args.name.startswith('smako-public-menu-')
root = args.evidence_root.resolve()
assert root.is_relative_to('/opt/smako/evidence')
candidate = json.loads((root/'candidate-image.json').read_text())
app = json.loads(subprocess.check_output(['docker','inspect','smako-app-1']))[0]
env = dict(v.split('=',1) for v in app['Config']['Env'])
env.update(PLAN_STORE_PATH='/probe/plans.sqlite3',GROCERY_DATABASE_URL='sqlite:////probe/grocery.sqlite',BUILD_ID=candidate['commit'])
private = root/'candidate.private.env'
private.write_text(''.join(k+'='+v+'\n' for k,v in env.items()))
private.chmod(0o600)
command=['docker','run','-d','--name',args.name,'--env-file',str(private),
         '--cpus','2','--memory','3g','-p','127.0.0.1:18082:8000','-v',str(root/'state')+':/probe']
for mount in app['Mounts']:
    if mount['Destination'] in {'/srv/app/var/grocery','/srv/app/var/raw_snapshots','/srv/app/var/price_universes'}:
        command += ['-v',mount['Source']+':'+mount['Destination']+':ro']
command += [candidate['image'],*app['Config']['Cmd']]
print(subprocess.check_output(command,text=True).strip())
