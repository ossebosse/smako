import json,subprocess,shlex,hashlib
from pathlib import Path
from remote import STAGE,IMAGE
O=Path(__file__).parent
manifest=json.loads((O/'source-manifest.json').read_bytes())
script="import sys,json,pathlib,hashlib,subprocess;m=json.load(sys.stdin);bad=[p for p,h in m['files'].items() if hashlib.sha256((pathlib.Path('/srv/app')/p).read_bytes()).hexdigest()!=h];r=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True);print(json.dumps({'files':len(m['files']),'mismatches':bad,'pip_check':r.stdout,'dependency_exit':r.returncode}));assert not bad and r.returncode==0"
cmd=['docker','run','--rm','-i','--network','none','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',script]
code='import sys,subprocess;sys.stdout.buffer.write(subprocess.check_output('+repr(cmd)+',input=sys.stdin.buffer.read()))'
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],input=json.dumps(manifest).encode(),capture_output=True,check=True)
(O/'results/final-image-verification.json').write_bytes(r.stdout)
code='import subprocess;print(subprocess.check_output('+repr(['docker','image','inspect',IMAGE])+').decode())'
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)],capture_output=True,check=True)
data=json.loads(r.stdout)[0]
(O/'final-image.json').write_text(json.dumps({'tag':IMAGE,'id':data['Id'],'created':data['Created'],'source_tree_sha256':manifest['source_tree_sha256'],'packaged_files':len(manifest['files']),'production_activation':False},indent=2),encoding='utf-8')
print('Final image verified',data['Id'],len(manifest['files']))
