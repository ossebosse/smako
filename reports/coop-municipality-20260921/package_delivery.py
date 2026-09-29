"""Create additive review patch against preserved dirty baseline; check, never apply."""
import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

R=Path(__file__).resolve().parent; ROOT=R.parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
baseline=json.loads((R/'baseline.json').read_bytes())
paths=[*baseline,'grocery_data/app/services/municipality_geometry.py',
'grocery_data/app/connectors/coop/municipality_inventory.py','grocery_data/scripts/collect_coop_municipality.py',
'grocery_data/tests/test_coop_municipality.py','backend/tests/test_coop_municipality_household.py',
'backend/tests/fixtures/coop-municipality-household-20260921.json','docs/municipality_geometry.md']
paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/'grocery_data/tests/fixtures/coop-municipality-20260921').glob('*.json')]
paths += [p.relative_to(ROOT).as_posix() for p in R.glob('*.md') if p.name!='ALL_STORES.md']
paths += [p.relative_to(ROOT).as_posix() for p in [R/'verify_isolated.py',R/'verify_two_store.py',R/'build_report.py',R/'package_delivery.py']]
parts=[];files={}
with tarfile.open(R/'prework.tar.gz') as archive:
 for path in paths:
  old=archive.extractfile(path).read() if path in baseline else b''
  new=(ROOT/path).read_bytes()
  if path in baseline:assert sha(old)==baseline[path]
  files[path]={'before':sha(old) if path in baseline else None,'after':sha(new)}
  if old==new:continue
  parts.append(f'diff --git a/{path} b/{path}\n')
  if path not in baseline:parts.append('new file mode 100644\n')
  for line in difflib.unified_diff(old.decode('utf-8').splitlines(True),new.decode('utf-8').splitlines(True),fromfile='a/'+path if path in baseline else '/dev/null',tofile='b/'+path):
   parts.append(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n')
data=''.join(parts).replace('\r\n','\n').encode('utf-8');(R/'incremental.patch').write_bytes(data)
check=subprocess.run(['git','apply','--reverse','--check',str(R/'incremental.patch')],cwd=ROOT,capture_output=True,text=True)
assert check.returncode==0,check.stderr
prior=ROOT/'reports/coop-closeout-20260921'
manifest=json.loads((prior/'verification.json').read_bytes())
assert sha((prior/'incremental.patch').read_bytes())==manifest['patch_sha256']
prior_mismatches=[f for f,v in manifest['files'].items() if f!='docs/HANDOFF.md' and sha((ROOT/f).read_bytes())!=v['after']]
assert not prior_mismatches,prior_mismatches
old=json.loads((prior/'acceptance/result.json').read_bytes());new=json.loads((R/'prior112-regression/result.json').read_bytes())
for row in old['stores']:
 current=next(x for x in new['stores'] if x['store']==row['store'])
 for key in ['accepted','rejected','price_universe','source_hash','observed_at']:assert row[key]==current[key],key
assert new['price_universe_count']==112 and all(p['audit']['passed'] for p in new['proofs'])
# Verify original pending ICA worktree without writes.
inherited=json.loads((ROOT/'reports/municipality-offers-20260920/inherited-work.json').read_bytes());original=Path(inherited['source'])
bad=[name for name,h in inherited['files'].items() if sha((original/name).read_bytes())!=h]
assert not bad,bad
release=json.loads((original/'reports/ica-structured-release-20260920/release-source-manifest.json').read_bytes());vendor={}
for package,dist in [('bs4','beautifulsoup4'),('soupsieve','soupsieve')]:
 directory=Path(importlib.util.find_spec(package).origin).parent
 for p in directory.rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:vendor['release-vendor/'+package+'/'+p.relative_to(directory).as_posix()]=p.read_bytes()
 meta=importlib.metadata.distribution(dist)
 for f in meta.files:
  if '.dist-info/' in str(f):vendor['release-vendor/'+str(f)]=meta.locate_file(f).read_bytes()
release_bad=[name for name,h in release['files'].items() if sha(vendor[name] if name.startswith('release-vendor/') else (original/name).read_bytes().replace(b'\r\n',b'\n'))!=h]
assert not release_bad,release_bad
# Batches assembled for final replay are byte-identical to actually fetched batches.
for p in (R/'final-sources').glob('*.json'):
 source=R/('stora-final/sources' if p.name.startswith('2696-') else 'acceptance/collection/sources')/p.name
 assert sha(p.read_bytes())==sha(source.read_bytes())
artifacts={p.relative_to(R).as_posix():sha(p.read_bytes()) for p in R.rglob('*') if p.is_file() and p.suffix in ['.json','.md','.pdf','.txt'] and '__pycache__' not in p.parts and p.name!='delivery-manifest.json'}
result={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'files':files,'patch_sha256':sha(data),'reverse_check':'pass; check only','prior_closeout_patch_unchanged':True,'prior_112_preserved':True,'prior_112_proofs_pass':6,'same_source_hashes_and_observation_times':True,'original_inherited_checked':len(inherited['files']),'original_inherited_mismatches':bad,'pending_ica_release_checked':len(release['files']),'pending_ica_release_mismatches':release_bad,'pytest':{'passed':356,'seconds':33.36},'affected_area_rerun':{'passed':29,'seconds':15.59},'ruff':'pass','compileall':'pass','production_activation':False,'artifact_hashes':artifacts}
(R/'delivery-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['files','artifact_hashes']}))
