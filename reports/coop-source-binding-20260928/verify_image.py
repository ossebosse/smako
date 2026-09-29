import difflib
import hashlib
import json
import shlex
import subprocess
from pathlib import Path
from remote import IMAGE

P=Path(__file__).parent;ROOT=P.parents[1]
old=json.loads((P.parent/'lund-integration-20260927/source-manifest.json').read_bytes())
files={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in old['files']}
changed=[name for name in files if old['files'][name]!=files[name]]
assert set(changed)==set(json.loads((P/'image.json').read_bytes())['changed_files'])
(P/'source-manifest.json').write_text(json.dumps({'files':files,
    'source_tree_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
    'changed_from_verified_alternative':changed},indent=2),encoding='utf-8')
patch=[]
for name in changed:
    patch.extend(difflib.unified_diff((P/'before'/name).read_text(encoding='utf-8').splitlines(keepends=True),
        (ROOT/name).read_text(encoding='utf-8').splitlines(keepends=True),fromfile='a/'+name,tofile='b/'+name))
(P/'code.patch').write_text(''.join(patch),encoding='utf-8')
code="""import sys,json,hashlib,subprocess
from pathlib import Path
files=json.load(sys.stdin)
bad=[n for n,h in files.items() if hashlib.sha256((Path('/srv/app')/n).read_bytes()).hexdigest()!=h]
assert not bad,bad
r=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
print(json.dumps({'verified_files':len(files),'mismatches':bad,'dependency_exit':r.returncode,'dependency_check':r.stdout}))
assert r.returncode==0
"""
cmd=['docker','run','--rm','-i','--network','none','--entrypoint','/opt/ica-venv/bin/python',IMAGE,'-c',code]
remote='import sys,subprocess;r=subprocess.run('+repr(cmd)+',input=sys.stdin.buffer.read(),capture_output=True);sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)'
r=subprocess.run(['ssh','smako','python3 -c '+shlex.quote(remote)],input=json.dumps(files).encode(),capture_output=True,check=True)
(P/'image-verification.json').write_bytes(r.stdout)
previous=json.loads((P.parent/'lund-base-strategy-20260928/PACKAGE.json').read_bytes())
differences=[name for name,h in previous['evidence_hashes'].items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h]
assert not differences,differences
(P/'prior-evidence-verification.json').write_text(json.dumps({'verified_files':len(previous['evidence_hashes']),
    'unchanged':True,'previous_package_sha256':hashlib.sha256((P.parent/'lund-base-strategy-20260928/PACKAGE.json').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print(r.stdout.decode(),'Previous candidate evidence unchanged:',len(previous['evidence_hashes']))
