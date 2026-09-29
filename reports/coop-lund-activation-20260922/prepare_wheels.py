"""Candidate-only wheelhouse. No package installation in production."""
import json
import shlex
import subprocess
from pathlib import Path

code = '''import pathlib,subprocess,json,hashlib
p=pathlib.Path('/var/tmp/smako-coop-lund-activation-20260922')
assert (p/'.owner').read_text()=='coop-lund-activation-20260922'
w=p/'release-wheels'
if not w.exists():
 w.mkdir()
 cmd=['docker','run','--rm','--read-only','--network','bridge','--user','0:0','--cpus','1','--memory','512m','--tmpfs','/tmp:rw,size=128m','--mount','type=bind,source='+str(w)+',target=/wheels','--entrypoint','/opt/ica-venv/bin/python','smako-coop-candidate:nutrition-20260922','-m','pip','download','--no-cache-dir','--only-binary=:all:','--no-deps','--dest','/wheels','beautifulsoup4==4.15.0','soupsieve==2.9.1','PyMuPDF==1.28.2']
 r=subprocess.run(cmd,capture_output=True);assert r.returncode==0,r.stderr.decode()[-800:]
report={f.name:{'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size} for f in w.iterdir()}
assert len(report)==3
manifest=p/'wheel-manifest.json'
if manifest.exists():assert json.loads(manifest.read_bytes())==report
else:manifest.write_text(json.dumps(report,indent=2))
print(json.dumps(report))
'''
result = subprocess.run(['ssh','smako','python3 -c '+shlex.quote(code)], capture_output=True, check=True)
data = json.loads(result.stdout)
Path(__file__).with_name('wheel-manifest.json').write_text(json.dumps(data, indent=2), encoding='utf8')
print('Three pinned Linux/pure Python wheels verified; installation only in candidate image build.')
