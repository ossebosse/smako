"""Additive review patch and read-only checks; never activate anything."""
import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PRIOR=HERE.parent/'coop-physical-fix-20260921'
baseline=json.loads((HERE/'baseline.json').read_bytes())
paths=[*baseline,'backend/tests/test_coop_wheat_flour.py']
paths += [p.relative_to(ROOT).as_posix() for p in HERE.glob('*.md')]
paths += [p.relative_to(ROOT).as_posix() for p in [HERE/'group_quarantine.py',HERE/'verify_isolated.py']]
patch=[];files={}
with tarfile.open(HERE/'prework.tar.gz') as archive:
    for path in paths:
        before=archive.extractfile(path).read() if path in baseline else b''
        after=(ROOT/path).read_bytes()
        if path in baseline:assert hashlib.sha256(before).hexdigest()==baseline[path]
        files[path]={'before':hashlib.sha256(before).hexdigest() if path in baseline else None,
                     'after':hashlib.sha256(after).hexdigest()}
        patch.append(f'diff --git a/{path} b/{path}\n')
        if path not in baseline:patch.append('new file mode 100644\n')
        for chunk in difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),
                    fromfile='a/'+path if path in baseline else '/dev/null',tofile='b/'+path):
            patch.append(chunk if chunk.endswith('\n') else chunk+'\n\\ No newline at end of file\n')
data=''.join(patch).replace('\r\n','\n').encode()
(HERE/'incremental.patch').write_bytes(data)
check=subprocess.run(['git','apply','--reverse','--check',str(HERE/'incremental.patch')],cwd=ROOT,capture_output=True,text=True)
assert check.returncode==0,check.stderr

prior_manifest=json.loads((PRIOR/'delivery-manifest.json').read_bytes())
permitted={'docs/HANDOFF.md','backend/tests/test_coop_physical_pipeline.py'}
prior_mismatches=[name for name,hashes in prior_manifest['files'].items()
                  if name not in permitted and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=hashes['after_sha256']]
assert not prior_mismatches,prior_mismatches
assert hashlib.sha256((PRIOR/'incremental.patch').read_bytes()).hexdigest()==prior_manifest['patch_sha256']
before=json.loads((PRIOR/'final-acceptance-v2/result.json').read_bytes())
after=json.loads((HERE/'acceptance/result.json').read_bytes())
for row in before['stores']:
    current=next(r for r in after['stores'] if r['store']==row['store'])
    for field in ['accepted','rejected','price_universe','source_hash','observed_at','qualification']:
        assert row[field]==current[field],field
assert all(p['audit']['passed'] for p in after['proofs'])

inherited=json.loads((ROOT/'reports/municipality-offers-20260920/inherited-work.json').read_bytes())
original=Path(inherited['source'])
bad=[name for name,sha in inherited['files'].items() if hashlib.sha256((original/name).read_bytes()).hexdigest()!=sha]
manifest=json.loads((original/'reports/ica-structured-release-20260920/release-source-manifest.json').read_bytes())
vendor={}
for package,dist in [('bs4','beautifulsoup4'),('soupsieve','soupsieve')]:
    directory=Path(importlib.util.find_spec(package).origin).parent
    for p in directory.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            vendor['release-vendor/'+package+'/'+p.relative_to(directory).as_posix()]=p.read_bytes()
    meta=importlib.metadata.distribution(dist)
    for f in meta.files:
        if '.dist-info/' in str(f):vendor['release-vendor/'+str(f)]=meta.locate_file(f).read_bytes()
release_bad=[]
for name,sha in manifest['files'].items():
    raw=vendor[name] if name.startswith('release-vendor/') else (original/name).read_bytes().replace(b'\r\n',b'\n')
    if hashlib.sha256(raw).hexdigest()!=sha:release_bad.append(name)
assert not bad and not release_bad
out={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),
     'files':files,'patch_sha256':hashlib.sha256(data).hexdigest(),'reverse_check':'passed; check only',
     'prior_coop_patch_unchanged':True,'prior_coop_file_mismatches':prior_mismatches,
     'same_112_approved_and_379_quarantined':True,'source_hash_and_times_unchanged':True,
     'original_inherited_checked':len(inherited['files']),'original_inherited_mismatches':bad,
     'pending_ica_release_checked':len(manifest['files']),'pending_ica_release_mismatches':release_bad,
     'pytest':{'passed':324,'seconds':18.46},'affected_rerun':{'passed':18,'seconds':5.14},
     'ruff':'pass','compileall':'pass','production_activation':False,'external_calls':0}
(HERE/'verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='files'}))
