"""Immutable app/source deltas; building does not activate either process."""
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

BASES={
 'app':('f00f5304e544','smako-member-prices:f00f5304e544','sha256:7635779a3c7640856db031c0104748217bb93576cd57e9311b370cf56c05f75c'),
 'source':('04e47c691e0c','smako-source-ops:04e47c691e0c','sha256:441e1a2b357a8248ed5e75ddc513a05fbf1d1b347ece8ee323b4c18b74aa58ca')}

def blob(commit,path):return subprocess.check_output(['git','show',commit+':'+path])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--commit',required=True);p.add_argument('--target',choices=BASES,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 commit=subprocess.check_output(['git','rev-parse',a.commit+'^{commit}']).decode().strip();base,tag,image=BASES[a.target]
 assert subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}']).decode().strip()==image
 paths=subprocess.check_output(['git','diff','--name-only','f00f5304e544',commit,'--','backend/app','grocery_data/app']).decode().splitlines()
 if a.target=='source':paths=[f for f in paths if f.startswith('grocery_data/app/')]
 else:paths=sorted(set(paths)|{'grocery_data/app/connectors/hemkop/models.py'})
 assert paths
 files={f:blob(commit,f) for f in paths}
 manifest={'schema':'comparability-patch-v1','target':a.target,'commit':commit,'base_commit':base,'base_image':image,'base_tag':tag,'files':{f:hashlib.sha256(v).hexdigest() for f,v in files.items()},'base_files':{f:hashlib.sha256(blob(base,f)).hexdigest() for f in paths}}
 # The pinned app image predates the already-activated source picking fix.
 # Include its exact dependency, without substituting an unverified base hash.
 if a.target=='app':
  manifest['base_files'].update({
   'grocery_data/app/connectors/hemkop/parser.py':'0dac30a8fc26241a7be47269d1458966da505822f7939e80c74587623bd72dc5',
   'grocery_data/app/connectors/hemkop/models.py':'c2075bde4f726dff180275c8accc640a80a3bc9a23b1b93d098e21033fe76e96'})
  manifest['dependency_note']='Include existing reviewed source picking-context validation required by Hemkop parser; source release 04e47c691e0c. Consumer base image predates this source-only fix.'
 files['COMPARABILITY-PATCH.json']=json.dumps(manifest,indent=2).encode()
 files['verify-base.py']=b"import hashlib,json;from pathlib import Path;m=json.loads(Path('/tmp/COMPARABILITY-PATCH.json').read_bytes());assert all(hashlib.sha256((Path('/srv/app')/p).read_bytes()).hexdigest()==h for p,h in m['base_files'].items()),'base code mismatch'"
 copies='\n'.join(f'COPY --chown=app:app {f} /srv/app/{f}' for f in paths)
 files['Dockerfile']=(f'FROM {tag}\nUSER root\nCOPY COMPARABILITY-PATCH.json /tmp/COMPARABILITY-PATCH.json\nCOPY verify-base.py /tmp/verify-base.py\nRUN python /tmp/verify-base.py\n'+copies+f'\nCOPY COMPARABILITY-PATCH.json /srv/app/COMPARABILITY-PATCH.json\nENV BUILD_ID=comparability-{a.target}-{commit[:12]}\nLABEL org.opencontainers.image.revision={commit}\nUSER app\n').encode()
 a.output.mkdir(parents=True,exist_ok=True);target=a.output/f'smako-comparability-{a.target}-{commit[:12]}.zip'
 with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
  for f,data in sorted(files.items()):
   info=zipfile.ZipInfo(f,(2026,1,1,0,0,0));info.external_attr=0o100644<<16;info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
 manifest['package']={'name':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'bytes':target.stat().st_size};(a.output/'package.json').write_text(json.dumps(manifest,indent=2),encoding='utf8');print(json.dumps(manifest['package']))
if __name__=='__main__':main()
