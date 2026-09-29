"""Review this task's changes against the preserved dirty baseline."""
import difflib,hashlib,json,tarfile,subprocess,importlib.util,importlib.metadata
import xml.etree.ElementTree as ET
from pathlib import Path
R=Path(__file__).resolve().parent;ROOT=R.parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
before={}
for archive in ['prework-package.tar.gz','prework-refresh.tar.gz']:
 with tarfile.open(R/archive) as t:
  for m in t.getmembers():
   if m.isfile():before[m.name]=t.extractfile(m).read()
(R/'baseline.json').write_text(json.dumps({n:sha(b) for n,b in before.items()},indent=2),encoding='utf8')
new=['grocery_data/requirements-coop-candidate.txt','grocery_data/tests/test_coop_release_freshness.py']
files={};patch=[];binary=[]
for name in sorted(set(before)|set(new)):
 old=before.get(name,b'');now=(ROOT/name).read_bytes()
 files[name]={'before':sha(old) if name in before else None,'after':sha(now)}
 if name.endswith('.pdf'):
  binary.append(name);continue
 patch.extend(difflib.unified_diff(old.decode('utf8').replace('\r\n','\n').splitlines(True),now.decode('utf8').replace('\r\n','\n').splitlines(True),fromfile='a/'+name if name in before else '/dev/null',tofile='b/'+name))
data=''.join(line if line.endswith('\n') else line+'\n\\ No newline at end of file\n' for line in patch).encode('utf8');(R/'incremental.patch').write_bytes(data)
r=subprocess.run(['git','apply','--reverse','--check','--ignore-space-change',str(R/'incremental.patch')],cwd=ROOT,capture_output=True)
assert r.returncode==0,r.stderr.decode()
with tarfile.open(R/'review-files.tar.gz','w:gz') as t:
 for name in files:t.add(ROOT/name,arcname=name)
municipal=ROOT/'reports/coop-municipal-contract-20260922';mv=json.loads((municipal/'verification.json').read_bytes());assert all(sha((municipal/n).read_bytes())==h for n,h in mv['artifact_hashes'].items())
nutrition=ROOT/'reports/coop-nutrition-20260922';nv=json.loads((nutrition/'verification.json').read_bytes())
assert all(sha((nutrition/n).read_bytes())==h for n,h in nv['artifact_hashes'].items())
previous=ROOT/'reports/coop-1520-20260922';previous_v=json.loads((previous/'verification.json').read_bytes())
assert all(sha((previous/n).read_bytes())==h for n,h in previous_v['artifact_hashes'].items())
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

cases={}
for file in ['tests.xml','tests-final-refresh.xml']:
 for case in ET.parse(R/file).iter('testcase'):
  assert case.find('failure') is None and case.find('error') is None
  cases[(case.attrib['classname'],case.attrib['name'])]=True
report={'branch':subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 'files':files,'binary_files_in_review_archive':binary,'patch_sha256':sha(data),'reverse_check':'PASS, checked never applied',
 'prior_municipal_artifacts':len(mv['artifact_hashes']),'prior_nutrition_artifacts':len(nv['artifact_hashes']),'prior_1520_artifacts':len(previous_v['artifact_hashes']),
 'prior_xtra_artifacts':len(pv['artifact_hashes']),'prior_coop_artifacts':len(cv['artifact_hashes']),
 'original_inherited':len(inherited['files']),'pending_ica_release':len(release['files']),
 'preservation':'all checked hashes unchanged','production_activation':False,
 'validation':{'unique_pytest_cases':len(cases),'failures':0,'ruff':'PASS','compileall':'PASS','live_municipalities':['1281'],'new_inventory':False,'candidate_server_image':json.loads((R/'package-result.json').read_bytes())['image_id'],'production_deployment':False},
 'artifact_hashes':{p.relative_to(R).as_posix():sha(p.read_bytes()) for p in R.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='verification.json'}}
(R/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k not in ['files','artifact_hashes']},ensure_ascii=False))
