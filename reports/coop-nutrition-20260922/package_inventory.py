"""Read-only inventory of the exact tested image, no environment secrets."""
import subprocess,shlex,json
from pathlib import Path
program="""import hashlib,json,pathlib,importlib.metadata,sys,os
r={'python':sys.version,'uid':os.getuid(),'gid':os.getgid(),'browser_path':os.environ.get('PLAYWRIGHT_BROWSERS_PATH'),'dependencies':{k:importlib.metadata.version(k) for k in ['playwright','pydantic','sqlalchemy','httpx']},'code':{}}
for root in [pathlib.Path('/srv/app/backend/app'),pathlib.Path('/srv/app/grocery_data/app'),pathlib.Path('/srv/app/grocery_data/scripts')]:
 for p in root.rglob('*.py'):
  if '__pycache__' not in p.parts:r['code'][str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(r))
"""
cmd=['docker','run','--rm','--network','none','--read-only','--cpus','1','--memory','256m','--entrypoint','/opt/ica-venv/bin/python','smako-coop-candidate:nutrition-20260922','-c',program]
code="import subprocess,json\nimage='smako-coop-candidate:nutrition-20260922'\nd=json.loads(subprocess.check_output(['docker','inspect',image]))[0]\nr={'image_id':d['Id'],'user':d['Config']['User'],'entrypoint':d['Config']['Entrypoint'],'base_image_id':subprocess.check_output(['docker','inspect','--format','{{.Id}}','smako-ica-shadow:20260915'],text=True).strip(),'production_activation':False}\nr['runtime']=json.loads(subprocess.check_output("+repr(cmd)+"))\nprint(json.dumps(r))"
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
d=json.loads(r.stdout)
Path(__file__).with_name('package-result.json').write_text(json.dumps(d,indent=2),encoding='utf8')
print({k:v for k,v in d.items() if k!='runtime'});print(d['runtime']['dependencies'])
