"""Freeze current complete source database under the existing operation lock."""
import io,json,shlex,subprocess,tarfile
from pathlib import Path
HERE=Path(__file__).parent
STAGE='/var/tmp/smako-offer-expansion-20260924'
IMAGE='smako-willys-candidate:municipality-20260922'
program='''import json,hashlib,sqlite3,shutil
from pathlib import Path
from datetime import datetime,UTC
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
from app.services.production_primat_refresh import plan_city_primat_refresh
root=Path('/work/base');root.mkdir(exist_ok=False)
db=Path('/srv/app/var/grocery/grocery_data.sqlite');pu=Path('/srv/app/var/price_universes')
with RefreshRunLock(production_refresh_lock_path(db,pu)):
 with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as src:
  with sqlite3.connect(root/'grocery.sqlite') as dst:src.backup(dst)
 manifests={}
 for scope in ['','external-provider-cache']:
  for city in ['lund','malmö']:
   p=pu/scope/'active'/('city-'+city+'.json')
   if not p.exists():continue
   data=p.read_bytes();m=json.loads(data);artifact=(pu/scope/m['artifact_file']).read_bytes()
   assert hashlib.sha256(artifact).hexdigest()==m['artifact_sha256']
   dest=root/'price-universes'/scope/m['artifact_file'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(artifact)
   dest=root/'price-universes'/scope/'active'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
   manifests[scope+'/'+city]=m
 with sqlite3.connect((root/'grocery.sqlite').as_uri()+'?mode=ro',uri=True) as conn:
  snapshots=conn.execute("SELECT * FROM catalog_snapshots WHERE is_active=1").fetchall()
 result={'frozen_at':datetime.now(UTC).isoformat(),'database_sha256':hashlib.sha256((root/'grocery.sqlite').read_bytes()).hexdigest(),'snapshots':snapshots,'manifests':manifests,'primat_plans':{city:plan_city_primat_refresh(root/'grocery.sqlite',city,48) for city in ['Lund','Malmö']},'production_activation':False}
 (root/'manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps(result,ensure_ascii=False))
'''
code=f'''import subprocess,pathlib,json
p=pathlib.Path({STAGE!r});p.mkdir(exist_ok=True)
marker=p/'.owner'
if marker.exists():assert marker.read_text()=='offer-expansion-20260924'
else:marker.write_text('offer-expansion-20260924')
subprocess.run(['docker','run','--rm','--network','none','-v',str(p)+':/stage','alpine:3.20','sh','-c','mkdir -p /stage/data; chown 10001:10001 /stage/data; chmod 700 /stage/data'],check=True)
'''
cmd=['docker','run','--rm','--network','none','--read-only','--user','10001:10001','--cpus','1','--memory','2g','-e','PYTHONPATH=/srv/app/backend:/srv/app','--tmpfs','/tmp:rw,size=128m,mode=1777','-v',STAGE+'/data:/work','-v','/srv/smako/data/grocery:/srv/app/var/grocery:ro','-v','/srv/smako/data/price_universes:/srv/app/var/price_universes:ro','-v','/srv/smako/data/price_universes/.refresh-locks:/srv/app/var/price_universes/.refresh-locks','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',program]
code+='r=subprocess.run('+repr(cmd)+',capture_output=True);print(r.stdout.decode("utf8",errors="replace"));print(json.dumps({"exit":r.returncode,"error":r.stderr.decode("utf8",errors="replace")[-2000:]}));raise SystemExit(r.returncode)'
r=subprocess.run(['ssh','-oBatchMode=yes','smako','python3 -c '+shlex.quote(code)],capture_output=True)
(HERE/'base-freeze-log.json').write_bytes(r.stdout)
print(r.stdout.decode('utf8',errors='replace'));print('SSH exit',r.returncode)
