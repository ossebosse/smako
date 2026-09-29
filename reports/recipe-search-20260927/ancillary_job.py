import os,json,subprocess,sys
from pathlib import Path
arm=sys.argv[1];out=Path('/work/profile')
os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
for version,cache in [('legacy',True)]+([('edible-input-v1',False)] if arm=='after' else []):
 request=json.loads(Path('/evaluation/original-request.json').read_bytes());request['purchase_planning_mode']='exact'
 label=arm+'-'+version+'-public-exact'+('' if cache else '-no-recipe-cache')
 p=out/(label+'-request.json');p.write_text(json.dumps(request))
 command=[sys.executable,'/evaluation/evaluate_profile.py','--recipe-version',version,'--artifact','/work/universe.json','--request',str(p),'--output',str(out),'--label',label,'--clock','2026-09-24T21:16:35.494010+00:00','--cases','restored-original','--universes','/work/base/price-universes']
 if not cache:command.append('--disable-recipe-cache')
 subprocess.run(command,check=True)
