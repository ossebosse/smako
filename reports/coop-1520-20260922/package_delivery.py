"""Additive review package against the inherited dirty baseline, no reset/apply."""
import difflib, hashlib, json, tarfile, subprocess, importlib.util, importlib.metadata
from pathlib import Path
R=Path(__file__).resolve().parent;ROOT=R.parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
before={}
with tarfile.open(R/'prework.tar.gz') as t:
 for m in t.getmembers():
  if m.isfile():before[m.name]=t.extractfile(m).read()
assert set(before)==set(json.loads((R/'baseline.json').read_bytes())),list(before)
new=['backend/app/providers/coop_municipality_offers.py','backend/tests/test_coop_municipality_provider.py']
files={};patch=[]
for name in sorted(set(before)|set(new)):
 p=ROOT/name;old=before.get(name,b'');now=p.read_bytes()
 files[name]={'before':sha(old) if name in before else None,'after':sha(now)}
 patch.extend(difflib.unified_diff(old.decode('utf8').replace('\r\n','\n').splitlines(True),now.decode('utf8').replace('\r\n','\n').splitlines(True),fromfile='a/'+name if name in before else '/dev/null',tofile='b/'+name))
data=''.join(patch).encode('utf8');(R/'incremental.patch').write_bytes(data)
r=subprocess.run(['git','apply','--reverse','--check','--ignore-space-change',str(R/'incremental.patch')],cwd=ROOT,capture_output=True)
assert r.returncode==0,r.stderr.decode()
with tarfile.open(R/'review-files.tar.gz','w:gz') as t:
 for name in files:t.add(ROOT/name,arcname=name)
prior=ROOT/'reports/xtra-text-20260922';pv=json.loads((prior/'verification.json').read_bytes())
assert all(sha((prior/n).read_bytes())==h for n,h in pv['artifact_hashes'].items())
coop=ROOT/'reports/coop-municipality-20260921';cv=json.loads((coop/'delivery-manifest.json').read_bytes())
assert all(sha((coop/n).read_bytes())==h for n,h in cv['artifact_hashes'].items())
inherited=json.loads((ROOT/'reports/municipality-offers-20260920/inherited-work.json').read_bytes());original=Path(inherited['source'])
assert all(sha((original/n).read_bytes())==h for n,h in inherited['files'].items())
release=json.loads((original/'reports/ica-structured-release-20260920/release-source-manifest.json').read_bytes())
vendor={}
for package,dist in [('bs4','beautifulsoup4'),('soupsieve','soupsieve')]:
 directory=Path(importlib.util.find_spec(package).origin).parent
 for p in directory.rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:vendor['release-vendor/'+package+'/'+p.relative_to(directory).as_posix()]=p.read_bytes()
 metadata=importlib.metadata.distribution(dist)
 for f in metadata.files:
  if '.dist-info/' in str(f):vendor['release-vendor/'+str(f)]=metadata.locate_file(f).read_bytes()
assert all(sha(vendor[n] if n.startswith('release-vendor/') else (original/n).read_bytes().replace(b'\r\n',b'\n'))==h for n,h in release['files'].items())
report={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'files':files,'patch_sha256':sha(data),'reverse_check':'PASS, checked never applied',
 'prior_xtra_artifacts':len(pv['artifact_hashes']),'prior_coop_artifacts':len(cv['artifact_hashes']),
 'original_inherited':len(inherited['files']),'pending_ica_release':len(release['files']),
 'preservation':'all checked hashes unchanged','production_activation':False,
 'artifact_hashes':{p.relative_to(R).as_posix():sha(p.read_bytes()) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='verification.json'}}
(R/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k not in ['files','artifact_hashes']}))
