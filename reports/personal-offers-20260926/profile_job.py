import os,json,subprocess,sys
from pathlib import Path
r=Path('/work'); arm=sys.argv[1];out=r/'profile';out.mkdir(exist_ok=True)
os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
for member in ('public','plus'):
 for mode in ('exact','estimated'):
  request=json.loads(Path('/evaluation/original-request.json').read_bytes());request['purchase_planning_mode']=mode
  if member=='plus':request['memberships']={'willys':True,'lidl':True}
  label=arm+'-'+member+'-'+mode;p=out/(label+'-request.json');p.write_text(json.dumps(request))
  subprocess.run([sys.executable,'/evaluation/evaluate_profile.py','--artifact','/work/universe.json','--request',str(p),'--output',str(out),'--label',label,'--clock','2026-09-24T21:16:35.494010+00:00','--cases','restored-original','--universes','/work/base/price-universes'],check=True)
